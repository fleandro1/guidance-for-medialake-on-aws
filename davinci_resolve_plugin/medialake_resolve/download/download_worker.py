"""Download worker for background file downloads."""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime
from PySide6.QtCore import QObject, Signal, Slot, QThread, QMutex, QWaitCondition
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtCore import QUrl, QFile, QIODevice

from medialake_resolve.core.models import Asset, DownloadTask, DownloadStatus, AssetVariant


class DownloadWorker(QObject):
    """Worker for downloading files in a background thread.
    
    Uses Qt networking for downloads with progress reporting.
    
    Signals:
        download_started: Emitted when download begins. (task_id)
        download_progress: Emitted for progress updates. (task_id, bytes_downloaded, total_bytes)
        download_completed: Emitted on successful completion. (task_id, file_path)
        download_failed: Emitted on failure. (task_id, error_message)
        download_cancelled: Emitted when cancelled. (task_id)
        start_download: Internal signal to trigger download in worker thread.
    """
    
    # Signals
    download_started = Signal(str)
    download_progress = Signal(str, int, int)
    download_completed = Signal(str, str)
    download_failed = Signal(str, str)
    download_cancelled = Signal(str)
    
    # Internal signal for cross-thread invocation
    _start_download_signal = Signal(object, str)  # (task, access_token)
    
    def __init__(self, parent: Optional[QObject] = None):
        """Initialize download worker."""
        super().__init__(parent)
        
        self._network_manager: Optional[QNetworkAccessManager] = None
        self._current_reply: Optional[QNetworkReply] = None
        self._current_file: Optional[QFile] = None
        self._current_task: Optional[DownloadTask] = None
        self._cancelled = False
        self._mutex = QMutex()
        
        # Connect internal signal to slot for cross-thread invocation
        self._start_download_signal.connect(self._do_download)
    
    def set_network_manager(self, manager: QNetworkAccessManager) -> None:
        """Set the network manager to use for downloads.
        
        Args:
            manager: QNetworkAccessManager instance.
        """
        self._network_manager = manager
    
    def download(self, task: DownloadTask, access_token: Optional[str] = None) -> None:
        """Start downloading a file (thread-safe).
        
        This method can be called from any thread. It emits a signal to
        perform the actual download in the worker's thread.
        
        Args:
            task: The download task to execute.
            access_token: Optional access token for authentication.
        """
        print(f"  [Worker] download() called for task {task.task_id}")
        print(f"  [Worker] download_url in task: {task.download_url[:80] if task.download_url else 'NONE'}...")
        
        # Store task reference for status checking
        self._mutex.lock()
        self._cancelled = False
        self._current_task = task
        self._mutex.unlock()
        
        # Emit signal to trigger download in worker's thread
        print(f"  [Worker] Emitting _start_download_signal...")
        self._start_download_signal.emit(task, access_token or "")
        print(f"  [Worker] Signal emitted")
    
    @Slot(object, str)
    def _do_download(self, task: DownloadTask, access_token: str) -> None:
        """Actually perform the download (runs in worker thread).
        
        Args:
            task: The download task to execute.
            access_token: Access token for authentication (empty string if none).
        """
        print(f"  [Worker] _do_download called for task {task.task_id}")
        
        # Ensure network manager exists (created in this thread)
        if not self._network_manager:
            self._network_manager = QNetworkAccessManager(self)
        
        # Get download URL
        download_url = task.download_url
        print(f"  [Worker] Download URL: {download_url[:80] if download_url else 'NONE'}...")
        
        if not download_url:
            self.download_failed.emit(task.task_id, "No download URL available")
            return
        
        # Create request
        request = QNetworkRequest(QUrl(download_url))
        
        # S3 presigned URLs should NOT have auth headers - they're self-contained
        # Only add auth for API URLs, not S3
        # if access_token:
        #     request.setRawHeader(b"Authorization", f"Bearer {access_token}".encode())
        
        # Ensure destination directory exists
        dest_path = Path(task.destination_path)
        print(f"  [Worker] Destination path: {dest_path}")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open file for writing
        self._current_file = QFile(task.destination_path)
        if not self._current_file.open(QIODevice.OpenModeFlag.WriteOnly):
            print(f"  [Worker] Failed to open file for writing")
            self.download_failed.emit(
                task.task_id,
                f"Could not open file for writing: {task.destination_path}"
            )
            return
        
        print(f"  [Worker] Starting network request...")
        
        # Start download
        self._current_reply = self._network_manager.get(request)
        
        # Connect signals
        self._current_reply.downloadProgress.connect(self._on_download_progress)
        self._current_reply.finished.connect(self._on_download_finished)
        self._current_reply.readyRead.connect(self._on_ready_read)
        self._current_reply.errorOccurred.connect(self._on_error)
        
        # Update task status
        task.status = DownloadStatus.DOWNLOADING
        task.started_at = datetime.now()
        
        print(f"  [Worker] Emitting download_started for {task.task_id}")
        self.download_started.emit(task.task_id)
    
    def cancel(self) -> None:
        """Cancel the current download."""
        self._mutex.lock()
        self._cancelled = True
        self._mutex.unlock()
        
        if self._current_reply:
            self._current_reply.abort()
    
    def _on_ready_read(self) -> None:
        """Handle data ready to read."""
        if self._current_reply and self._current_file:
            data = self._current_reply.readAll()
            self._current_file.write(data)
    
    def _on_download_progress(self, bytes_received: int, bytes_total: int) -> None:
        """Handle download progress update."""
        if not self._current_task:
            return
        
        self._current_task.bytes_downloaded = bytes_received
        self._current_task.total_bytes = bytes_total
        
        if bytes_total > 0:
            self._current_task.progress = bytes_received / bytes_total
        
        self.download_progress.emit(
            self._current_task.task_id,
            bytes_received,
            bytes_total
        )
    
    def _on_download_finished(self) -> None:
        """Handle download completion."""
        if not self._current_task:
            return
        
        task = self._current_task
        
        # Close file
        if self._current_file:
            self._current_file.close()
            self._current_file = None
        
        # Check if cancelled
        self._mutex.lock()
        was_cancelled = self._cancelled
        self._mutex.unlock()
        
        if was_cancelled:
            task.status = DownloadStatus.CANCELLED
            # Delete partial file
            try:
                Path(task.destination_path).unlink(missing_ok=True)
            except Exception:
                pass
            self.download_cancelled.emit(task.task_id)
            return
        
        # Check for errors
        if self._current_reply and self._current_reply.error() != QNetworkReply.NetworkError.NoError:
            task.status = DownloadStatus.FAILED
            task.error_message = self._current_reply.errorString()
            # Delete partial file
            try:
                Path(task.destination_path).unlink(missing_ok=True)
            except Exception:
                pass
            self.download_failed.emit(task.task_id, task.error_message)
            return
        
        # Success
        task.status = DownloadStatus.COMPLETED
        task.progress = 1.0
        task.completed_at = datetime.now()
        
        self.download_completed.emit(task.task_id, task.destination_path)
        
        # Cleanup
        self._current_reply = None
        self._current_task = None
    
    def _on_error(self, error: QNetworkReply.NetworkError) -> None:
        """Handle network error."""
        if not self._current_task:
            return
        
        # Error will be handled in finished signal
        pass


class DownloadThread(QThread):
    """Thread for running download worker."""
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.worker: Optional[DownloadWorker] = None
    
    def run(self) -> None:
        """Run the thread's event loop."""
        self.exec()
