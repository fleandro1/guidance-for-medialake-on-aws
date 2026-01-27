"""Upload worker for background file uploads."""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime
from PySide6.QtCore import QObject, Signal, Slot, QThread, QMutex, QWaitCondition
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtCore import QUrl, QFile, QIODevice, QByteArray

from medialake_resolve.core.models import UploadTask, UploadStatus


class UploadWorker(QObject):
    """Worker for uploading files in a background thread.
    
    Uses Qt networking for uploads with progress reporting.
    
    Signals:
        upload_started: Emitted when upload begins. (task_id)
        upload_progress: Emitted for progress updates. (task_id, bytes_uploaded, total_bytes)
        upload_completed: Emitted on successful completion. (task_id, file_path)
        upload_failed: Emitted on failure. (task_id, error_message)
        upload_cancelled: Emitted when cancelled. (task_id)
    """
    
    # Signals
    upload_started = Signal(str)
    upload_progress = Signal(str, int, int)
    upload_completed = Signal(str, str)
    upload_failed = Signal(str, str)
    upload_cancelled = Signal(str)
    
    # Internal signal for cross-thread invocation
    _start_upload_signal = Signal(object, str)  # (task, access_token)
    
    def __init__(self, parent: Optional[QObject] = None):
        """Initialize upload worker."""
        super().__init__(parent)
        
        self._network_manager: Optional[QNetworkAccessManager] = None
        self._current_reply: Optional[QNetworkReply] = None
        self._current_file: Optional[QFile] = None
        self._current_task: Optional[UploadTask] = None
        self._cancelled = False
        self._mutex = QMutex()
        
        # Connect internal signal to slot for cross-thread invocation
        self._start_upload_signal.connect(self._do_upload)
    
    def set_network_manager(self, manager: QNetworkAccessManager) -> None:
        """Set the network manager to use for uploads.
        
        Args:
            manager: QNetworkAccessManager instance.
        """
        self._network_manager = manager
    
    def upload(self, task: UploadTask, access_token: Optional[str] = None) -> None:
        """Start uploading a file (thread-safe).
        
        This method can be called from any thread. It emits a signal to
        perform the actual upload in the worker's thread.
        
        Args:
            task: The upload task to execute.
            access_token: Optional access token for authentication.
        """
        print(f"  [Worker] upload() called for task {task.task_id}")
        print(f"  [Worker] upload_url in task: {task.upload_url[:80] if task.upload_url else 'NONE'}...")
        
        # Store task reference for status checking
        self._mutex.lock()
        self._cancelled = False
        self._current_task = task
        self._mutex.unlock()
        
        # Emit signal to trigger upload in worker's thread
        print(f"  [Worker] Emitting _start_upload_signal...")
        self._start_upload_signal.emit(task, access_token or "")
        print(f"  [Worker] Signal emitted")
    
    @Slot(object, str)
    def _do_upload(self, task: UploadTask, access_token: str) -> None:
        """Actually perform the upload (runs in worker thread).
        
        Args:
            task: The upload task to execute.
            access_token: Access token for authentication (empty string if none).
        """
        print(f"  [Worker] _do_upload called for task {task.task_id}")
        
        # Ensure network manager exists (created in this thread)
        if not self._network_manager:
            self._network_manager = QNetworkAccessManager(self)
        
        # Get upload URL
        upload_url = task.upload_url
        print(f"  [Worker] Upload URL: {upload_url[:80] if upload_url else 'NONE'}...")
        
        if not upload_url:
            self.upload_failed.emit(task.task_id, "No upload URL available")
            return
        
        # Open file for reading
        self._current_file = QFile(task.source_path)
        if not self._current_file.open(QIODevice.OpenModeFlag.ReadOnly):
            print(f"  [Worker] Failed to open file for reading")
            self.upload_failed.emit(
                task.task_id,
                f"Could not open file for reading: {task.source_path}"
            )
            return
        
        # Read file data
        file_data = self._current_file.readAll()
        
        # Check if we have presigned POST fields (from /assets/upload endpoint)
        if task.presigned_fields:
            print(f"  [Worker] Using presigned POST upload with fields")
            self._do_presigned_post_upload(task, upload_url, file_data)
        else:
            print(f"  [Worker] Using direct PUT upload")
            self._do_put_upload(task, upload_url, file_data)
    
    def _do_put_upload(self, task: UploadTask, upload_url: str, file_data: QByteArray) -> None:
        """Perform a direct PUT upload to a presigned URL.
        
        Args:
            task: The upload task.
            upload_url: The presigned PUT URL.
            file_data: The file data to upload.
        """
        # Create request
        request = QNetworkRequest(QUrl(upload_url))
        
        # Set content type
        content_type = task.content_type or "application/octet-stream"
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, content_type)
        
        print(f"  [Worker] Starting PUT upload...")
        
        # Start upload
        self._current_reply = self._network_manager.put(request, file_data)
        
        # Connect signals
        self._current_reply.uploadProgress.connect(self._on_upload_progress)
        self._current_reply.finished.connect(self._on_upload_finished)
        self._current_reply.errorOccurred.connect(self._on_error)
        
        # Update task status
        task.status = UploadStatus.UPLOADING
        task.started_at = datetime.now()
        
        print(f"  [Worker] Emitting upload_started for {task.task_id}")
        self.upload_started.emit(task.task_id)
    
    def _do_presigned_post_upload(self, task: UploadTask, upload_url: str, file_data: QByteArray) -> None:
        """Perform a presigned POST upload with form fields.
        
        This is used for uploads via the /assets/upload endpoint which returns
        presigned POST data with fields that must be included in the form.
        
        Args:
            task: The upload task.
            upload_url: The presigned POST URL.
            file_data: The file data to upload.
        """
        from PySide6.QtNetwork import QHttpMultiPart, QHttpPart
        
        # Create multipart form data
        multipart = QHttpMultiPart(QHttpMultiPart.ContentType.FormDataType)
        
        # Add presigned fields first (order matters for S3)
        for field_name, field_value in task.presigned_fields.items():
            text_part = QHttpPart()
            text_part.setHeader(
                QNetworkRequest.KnownHeaders.ContentDispositionHeader,
                f'form-data; name="{field_name}"'
            )
            text_part.setBody(field_value.encode('utf-8'))
            multipart.append(text_part)
            print(f"  [Worker] Added form field: {field_name}")
        
        # Add the file last
        file_part = QHttpPart()
        filename = Path(task.source_path).name
        content_type = task.content_type or "application/octet-stream"
        
        file_part.setHeader(
            QNetworkRequest.KnownHeaders.ContentDispositionHeader,
            f'form-data; name="file"; filename="{filename}"'
        )
        file_part.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            content_type
        )
        file_part.setBody(file_data.data())
        multipart.append(file_part)
        
        print(f"  [Worker] Added file: {filename} ({content_type})")
        
        # Create request
        request = QNetworkRequest(QUrl(upload_url))
        
        print(f"  [Worker] Starting POST upload...")
        
        # Start upload - multipart will be deleted when reply is deleted
        self._current_reply = self._network_manager.post(request, multipart)
        multipart.setParent(self._current_reply)  # Ensure multipart is deleted with reply
        
        # Connect signals
        self._current_reply.uploadProgress.connect(self._on_upload_progress)
        self._current_reply.finished.connect(self._on_upload_finished)
        self._current_reply.errorOccurred.connect(self._on_error)
        
        # Update task status
        task.status = UploadStatus.UPLOADING
        task.started_at = datetime.now()
        
        print(f"  [Worker] Emitting upload_started for {task.task_id}")
        self.upload_started.emit(task.task_id)
    
    def cancel(self) -> None:
        """Cancel the current upload."""
        self._mutex.lock()
        self._cancelled = True
        self._mutex.unlock()
        
        if self._current_reply:
            self._current_reply.abort()
    
    def _on_upload_progress(self, bytes_sent: int, bytes_total: int) -> None:
        """Handle upload progress update."""
        if not self._current_task:
            return
        
        self._current_task.bytes_uploaded = bytes_sent
        self._current_task.total_bytes = bytes_total
        
        if bytes_total > 0:
            self._current_task.progress = bytes_sent / bytes_total
        
        self.upload_progress.emit(
            self._current_task.task_id,
            bytes_sent,
            bytes_total
        )
    
    def _on_upload_finished(self) -> None:
        """Handle upload completion."""
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
            task.status = UploadStatus.CANCELLED
            self.upload_cancelled.emit(task.task_id)
            return
        
        # Check for errors
        if self._current_reply and self._current_reply.error() != QNetworkReply.NetworkError.NoError:
            task.status = UploadStatus.FAILED
            task.error_message = self._current_reply.errorString()
            self.upload_failed.emit(task.task_id, task.error_message)
            return
        
        # Success
        task.status = UploadStatus.COMPLETED
        task.progress = 1.0
        task.completed_at = datetime.now()
        
        self.upload_completed.emit(task.task_id, task.source_path)
        
        # Cleanup
        self._current_reply = None
        self._current_task = None
    
    def _on_error(self, error: QNetworkReply.NetworkError) -> None:
        """Handle network error."""
        if not self._current_task:
            return
        
        # Error will be handled in finished signal
        pass


class UploadThread(QThread):
    """Thread for running upload worker."""
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.worker: Optional[UploadWorker] = None
    
    def run(self) -> None:
        """Run the thread's event loop."""
        self.exec()