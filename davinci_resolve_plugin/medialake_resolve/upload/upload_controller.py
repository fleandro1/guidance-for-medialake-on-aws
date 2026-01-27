"""Controller for managing uploads from Resolve to Media Lake."""

import json
import uuid
import os
from typing import List, Optional, Dict, Callable, Any
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtNetwork import QNetworkAccessManager

from medialake_resolve.core.models import UploadTask, UploadStatus
from medialake_resolve.core.config import Config
from medialake_resolve.upload.upload_worker import UploadWorker, UploadThread
from medialake_resolve.resolve.connection import ResolveConnection


class UploadController(QObject):
    """Orchestrates uploading assets from Resolve to Media Lake.
    
    Features:
    - Queue management for batch uploads
    - Concurrent upload limiting
    - Progress tracking
    - Automatic extraction from Resolve Media Pool
    - Requests presigned URLs from /assets/upload endpoint before uploading
    
    Signals:
        queue_updated: Emitted when upload queue changes. (pending_count, active_count)
        upload_started: Emitted when an upload starts. (task_id, file_name)
        upload_progress: Emitted for progress updates. (task_id, progress_percent)
        upload_completed: Emitted on completion. (task_id, file_path)
        upload_failed: Emitted on failure. (task_id, error_message)
        batch_completed: Emitted when all uploads in batch complete. (success_count, fail_count)
        upload_url_needed: Emitted when a presigned URL is needed. (task_id, connector_id, filename, content_type, file_size)
    """
    
    # Maximum assets per batch
    MAX_BATCH_SIZE = 50
    
    # Signals
    queue_updated = Signal(int, int)
    upload_started = Signal(str, str)
    upload_progress = Signal(str, float)
    upload_completed = Signal(str, str)
    upload_failed = Signal(str, str)
    batch_completed = Signal(int, int)
    upload_url_needed = Signal(str, str, str, str, int)  # task_id, connector_id, filename, content_type, file_size
    
    def __init__(
        self,
        config: Config,
        token_provider: Callable[[], Optional[str]],
        parent: Optional[QObject] = None,
    ):
        """Initialize upload controller.
        
        Args:
            config: Application configuration.
            token_provider: Callable that returns current access token.
            parent: Parent QObject.
        """
        super().__init__(parent)
        
        self._config = config
        self._token_provider = token_provider
        
        # Upload queue and tracking
        self._pending_tasks: List[UploadTask] = []
        self._active_tasks: Dict[str, UploadTask] = {}
        self._completed_tasks: Dict[str, UploadTask] = {}
        
        # Tasks waiting for presigned URLs
        self._waiting_for_url: Dict[str, UploadTask] = {}
        
        # Connectors mapping: bucket_name -> connector info
        self._connectors: Dict[str, Dict[str, Any]] = {}
        
        # Workers and threads for concurrent uploads
        self._workers: List[UploadWorker] = []
        self._threads: List[UploadThread] = []
        
        # Resolve connection
        self._resolve_connection: Optional[ResolveConnection] = None
        
        # Initialize workers
        self._init_workers()
    
    def _init_workers(self) -> None:
        """Initialize upload workers and threads."""
        for i in range(self._config.max_concurrent_uploads):
            thread = UploadThread(self)
            worker = UploadWorker()
            worker.moveToThread(thread)
            
            # Connect worker signals
            worker.upload_started.connect(self._on_worker_started)
            worker.upload_progress.connect(self._on_worker_progress)
            worker.upload_completed.connect(self._on_worker_completed)
            worker.upload_failed.connect(self._on_worker_failed)
            worker.upload_cancelled.connect(self._on_worker_cancelled)
            
            self._workers.append(worker)
            self._threads.append(thread)
            thread.start()
    
    def set_resolve_connection(self, connection: ResolveConnection) -> None:
        """Set the Resolve connection for accessing Media Pool.
        
        Args:
            connection: ResolveConnection instance.
        """
        self._resolve_connection = connection
    
    def set_connectors(self, connectors: List[Dict[str, Any]]) -> None:
        """Set the available connectors for uploads.
        
        Args:
            connectors: List of connector dicts with 'id', 'storageIdentifier', 'name', 'status'.
        """
        self._connectors.clear()
        print(f"  [Controller] Setting {len(connectors)} connectors:")
        for connector in connectors:
            bucket_name = connector.get("storageIdentifier", "")
            if bucket_name:
                self._connectors[bucket_name] = connector
                print(f"  [Controller] Registered connector: '{bucket_name}' -> {connector.get('id')}")
            else:
                print(f"  [Controller] WARNING: Connector has no storageIdentifier: {connector}")
        print(f"  [Controller] Total registered connectors: {len(self._connectors)}")
        print(f"  [Controller] Registered bucket names: {list(self._connectors.keys())}")
    
    def get_connector_id(self, bucket_name: str) -> Optional[str]:
        """Get the connector ID for a bucket name.
        
        Args:
            bucket_name: The bucket name (storageIdentifier).
            
        Returns:
            The connector ID or None if not found.
        """
        connector = self._connectors.get(bucket_name)
        if connector:
            return connector.get("id")
        return None
    
    def _get_content_type(self, file_path: str) -> str:
        """Determine content type based on file extension.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            MIME type string.
        """
        ext = Path(file_path).suffix.lower()
        mime_types = {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".mxf": "application/mxf",
            ".avi": "video/x-msvideo",
            ".mkv": "video/x-matroska",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".bmp": "image/bmp",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".aac": "audio/aac",
            ".flac": "audio/flac",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".xml": "application/xml",
            ".json": "application/json",
        }
        return mime_types.get(ext, "application/octet-stream")
    
    def queue_upload(
        self,
        source_path: str,
        bucket_name: str,
        destination_key: Optional[str] = None,
    ) -> Optional[UploadTask]:
        """Add a file to the upload queue.
        
        Args:
            source_path: Path to the file to upload.
            bucket_name: S3 bucket name (storageIdentifier) to upload to.
            destination_key: Optional S3 key for the uploaded file. If not provided,
                             the filename will be used.
            
        Returns:
            The created UploadTask, or None if queue is full or connector not found.
        """
        # Check batch size limit
        total_queued = len(self._pending_tasks) + len(self._active_tasks) + len(self._waiting_for_url)
        if total_queued >= self.MAX_BATCH_SIZE:
            print(f"  [Controller] Queue full, cannot add upload for {source_path}")
            return None
        
        # Look up connector ID for this bucket
        connector_id = self.get_connector_id(bucket_name)
        if not connector_id:
            print(f"  [Controller] ERROR: No connector found for bucket '{bucket_name}'")
            print(f"  [Controller] Available bucket names: {list(self._connectors.keys())}")
            print(f"  [Controller] Total connectors registered: {len(self._connectors)}")
            # Still create the task but it will fail when we try to get the URL
        
        # Determine destination key if not provided
        if not destination_key:
            destination_key = os.path.basename(source_path)
        
        # Determine content type
        content_type = self._get_content_type(source_path)
        
        # Get file size
        try:
            file_size = os.path.getsize(source_path)
        except (OSError, IOError):
            file_size = 0
        
        # Create task
        task = UploadTask(
            task_id=str(uuid.uuid4()),
            source_path=source_path,
            bucket_name=bucket_name,
            destination_key=destination_key,
            connector_id=connector_id,
            content_type=content_type,
            status=UploadStatus.PENDING,
            total_bytes=file_size,
        )
        
        print(f"  [Controller] Created upload task {task.task_id} for {destination_key}")
        print(f"  [Controller] Connector ID: {connector_id}, Content-Type: {content_type}, Size: {file_size}")
        
        self._pending_tasks.append(task)
        self._emit_queue_updated()
        
        # Try to start upload (which will first request presigned URL)
        self._process_queue()
        
        return task
    
    def queue_uploads(
        self,
        file_paths: List[str],
        bucket_name: str,
        destination_prefix: str = "",
    ) -> List[UploadTask]:
        """Queue multiple files for upload.
        
        Args:
            file_paths: List of file paths to upload.
            bucket_name: S3 bucket name to upload to.
            destination_prefix: Optional prefix to add to destination keys.
            
        Returns:
            List of created UploadTasks.
        """
        # Limit to max batch size
        files_to_queue = file_paths[:self.MAX_BATCH_SIZE]
        
        tasks = []
        for file_path in files_to_queue:
            filename = os.path.basename(file_path)
            destination_key = f"{destination_prefix}{filename}" if destination_prefix else filename
            
            task = self.queue_upload(file_path, bucket_name, destination_key)
            if task:
                tasks.append(task)
        
        return tasks
    
    def cancel_upload(self, task_id: str) -> bool:
        """Cancel a pending or active upload.
        
        Args:
            task_id: The task ID to cancel.
            
        Returns:
            True if task was cancelled.
        """
        # Check pending tasks
        for i, task in enumerate(self._pending_tasks):
            if task.task_id == task_id:
                task.status = UploadStatus.CANCELLED
                self._pending_tasks.pop(i)
                self._emit_queue_updated()
                return True
        
        # Check active tasks
        if task_id in self._active_tasks:
            # Find worker handling this task and cancel
            for worker in self._workers:
                if (worker._current_task and 
                    worker._current_task.task_id == task_id):
                    worker.cancel()
                    return True
        
        return False
    
    def cancel_all(self) -> None:
        """Cancel all pending and active uploads."""
        # Cancel all pending
        for task in self._pending_tasks:
            task.status = UploadStatus.CANCELLED
        self._pending_tasks.clear()
        
        # Cancel all active
        for worker in self._workers:
            worker.cancel()
        
        self._emit_queue_updated()
    
    def get_task(self, task_id: str) -> Optional[UploadTask]:
        """Get a task by ID.
        
        Args:
            task_id: The task ID.
            
        Returns:
            The UploadTask or None.
        """
        # Check pending
        for task in self._pending_tasks:
            if task.task_id == task_id:
                return task
        
        # Check active
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]
        
        # Check completed
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id]
        
        return None
    
    def get_queue_status(self) -> dict:
        """Get current queue status.
        
        Returns:
            Dict with queue statistics.
        """
        return {
            "pending": len(self._pending_tasks),
            "active": len(self._active_tasks),
            "completed": len([t for t in self._completed_tasks.values() 
                            if t.status == UploadStatus.COMPLETED]),
            "failed": len([t for t in self._completed_tasks.values() 
                          if t.status == UploadStatus.FAILED]),
        }
    
    def _process_queue(self) -> None:
        """Process pending uploads by requesting presigned URLs.
        
        This method takes tasks from the pending queue and requests presigned
        upload URLs for them. Once the URL is received (via on_upload_url_ready),
        the actual upload will be started.
        """
        print(f"  [Controller] _process_queue called, pending: {len(self._pending_tasks)}, waiting_for_url: {len(self._waiting_for_url)}")
        
        # Process pending tasks that need presigned URLs
        while self._pending_tasks:
            # Check if we have capacity for more URL requests
            if len(self._waiting_for_url) + len(self._active_tasks) >= self._config.max_concurrent_uploads:
                print(f"  [Controller] At capacity, waiting for URLs or uploads to complete")
                break
            
            task = self._pending_tasks.pop(0)
            
            # Check if we have a connector ID
            if not task.connector_id:
                print(f"  [Controller] ERROR: Task {task.task_id} has no connector_id")
                available_buckets = list(self._connectors.keys())
                if available_buckets:
                    error_msg = f"No connector found for bucket '{task.bucket_name}'. Available buckets: {', '.join(available_buckets)}"
                else:
                    error_msg = f"No connectors available. Please refresh the bucket list or check your Media Lake configuration."
                task.status = UploadStatus.FAILED
                task.error_message = error_msg
                self._completed_tasks[task.task_id] = task
                self.upload_failed.emit(task.task_id, error_msg)
                continue
            
            # Move to waiting for URL
            self._waiting_for_url[task.task_id] = task
            
            print(f"  [Controller] Requesting presigned URL for task {task.task_id}")
            print(f"  [Controller] Connector: {task.connector_id}, File: {task.destination_key}")
            
            # Emit signal to request presigned URL
            # The main window will connect this to the API client
            self.upload_url_needed.emit(
                task.task_id,
                task.connector_id,
                task.destination_key,  # filename
                task.content_type,
                task.total_bytes,
            )
        
        self._emit_queue_updated()
    
    def on_upload_url_ready(self, task_id: str, upload_url: str, presigned_fields_json: str) -> None:
        """Handle presigned upload URL received from API.
        
        This is called when the API returns a presigned URL for an upload task.
        
        Args:
            task_id: The task ID.
            upload_url: The presigned upload URL.
            presigned_fields_json: JSON string of presigned POST fields, or destination key.
        """
        print(f"  [Controller] on_upload_url_ready called for task {task_id}")
        print(f"  [Controller] URL: {upload_url[:80] if upload_url else 'NONE'}...")
        
        # Find the task waiting for this URL
        task = self._waiting_for_url.pop(task_id, None)
        if not task:
            print(f"  [Controller] ERROR: No task found waiting for URL with id {task_id}")
            return
        
        if not upload_url:
            print(f"  [Controller] ERROR: Empty upload URL received for task {task_id}")
            task.status = UploadStatus.FAILED
            task.error_message = "Failed to get upload URL from server"
            self._completed_tasks[task_id] = task
            self.upload_failed.emit(task_id, task.error_message)
            self._check_batch_complete()
            return
        
        # Set the upload URL on the task
        task.upload_url = upload_url
        
        # Try to parse presigned fields
        try:
            if presigned_fields_json and presigned_fields_json.startswith("{"):
                task.presigned_fields = json.loads(presigned_fields_json)
                if task.presigned_fields:
                    print(f"  [Controller] Parsed presigned fields: {list(task.presigned_fields.keys())}")
        except json.JSONDecodeError:
            # Not JSON, might be destination key
            print(f"  [Controller] presigned_fields_json is not JSON: {presigned_fields_json[:50]}")
        
        # Move to active and start upload
        self._active_tasks[task_id] = task
        
        # Find an available worker
        for i, worker in enumerate(self._workers):
            if worker._current_task is None:
                print(f"  [Controller] Assigning task {task_id} to worker {i}")
                token = self._token_provider()
                worker.upload(task, token)
                print(f"  [Controller] Called worker.upload()")
                break
        else:
            # No worker available, put back in pending
            print(f"  [Controller] No worker available, task {task_id} will wait")
            self._active_tasks.pop(task_id, None)
            self._pending_tasks.insert(0, task)
        
        self._emit_queue_updated()
    
    def _on_worker_started(self, task_id: str) -> None:
        """Handle worker upload started."""
        task = self._active_tasks.get(task_id)
        if task:
            filename = os.path.basename(task.source_path)
            self.upload_started.emit(task_id, filename)
    
    def _on_worker_progress(self, task_id: str, bytes_uploaded: int, total_bytes: int) -> None:
        """Handle worker progress update."""
        if total_bytes > 0:
            progress = (bytes_uploaded / total_bytes) * 100
            self.upload_progress.emit(task_id, progress)
    
    def _on_worker_completed(self, task_id: str, file_path: str) -> None:
        """Handle worker upload completed."""
        task = self._active_tasks.pop(task_id, None)
        if task:
            self._completed_tasks[task_id] = task
            self.upload_completed.emit(task_id, file_path)
            
            # Check if this completes a batch
            self._check_batch_complete()
        
        # Process more from queue
        self._process_queue()
    
    def _on_worker_failed(self, task_id: str, error_message: str) -> None:
        """Handle worker upload failed."""
        task = self._active_tasks.pop(task_id, None)
        if task:
            self._completed_tasks[task_id] = task
            self.upload_failed.emit(task_id, error_message)
            
            # Check if this completes a batch
            self._check_batch_complete()
        
        # Process more from queue
        self._process_queue()
    
    def _on_worker_cancelled(self, task_id: str) -> None:
        """Handle worker upload cancelled."""
        task = self._active_tasks.pop(task_id, None)
        if task:
            self._completed_tasks[task_id] = task
        
        # Process more from queue
        self._process_queue()
    
    def _check_batch_complete(self) -> None:
        """Check if all uploads in batch are complete."""
        if not self._pending_tasks and not self._active_tasks:
            success_count = len([t for t in self._completed_tasks.values() 
                               if t.status == UploadStatus.COMPLETED])
            fail_count = len([t for t in self._completed_tasks.values() 
                            if t.status == UploadStatus.FAILED])
            
            self.batch_completed.emit(success_count, fail_count)
    
    def _emit_queue_updated(self) -> None:
        """Emit queue updated signal."""
        self.queue_updated.emit(
            len(self._pending_tasks),
            len(self._active_tasks)
        )
    
    def cleanup(self) -> None:
        """Clean up workers and threads."""
        self.cancel_all()
        
        for thread in self._threads:
            thread.quit()
            thread.wait()
        
        self._workers.clear()
        self._threads.clear()