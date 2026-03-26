"""Ingest manager for coordinating uploads with bounded concurrency."""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from PySide6.QtCore import QObject, QThreadPool, Signal

from lake_loader.core.config import Config
from lake_loader.core.history import IngestHistory
from lake_loader.core.models import (
    ConnectorInfo,
    HistoryRecord,
    IngestStatus,
    IngestTask,
    SUPPORTED_EXTENSIONS,
    get_content_type,
    is_content_type_allowed,
    is_supported_file,
    sanitize_filename,
)
from lake_loader.services.api_client import MediaLakeAPIClient
from lake_loader.services.upload_service import UploadWorker


class IngestManager(QObject):
    """
    Manages the ingest queue with bounded concurrency.

    Coordinates file uploads, tracks progress, and records history.
    """

    # Signals
    task_added = Signal(str)  # task_id
    task_started = Signal(IngestTask)  # task
    task_progress = Signal(IngestTask, int)  # task, percent
    task_completed = Signal(IngestTask)  # task
    task_failed = Signal(IngestTask, str)  # task, error_message
    task_cancelled = Signal(str)  # task_id
    task_removed = Signal(str)  # task_id
    queue_updated = Signal(int, int, int, int)  # pending, active, completed, failed
    queue_changed = Signal()  # simple signal for queue changes

    def __init__(
        self,
        config: Config,
        api_client: MediaLakeAPIClient,
        history: IngestHistory,
        parent: Optional[QObject] = None,
    ):
        """
        Initialize ingest manager.

        Args:
            config: Application configuration.
            api_client: Media Lake API client.
            history: Ingest history manager.
            parent: Parent QObject.
        """
        super().__init__(parent)

        self._config = config
        self._api_client = api_client
        self._history = history

        # Task tracking
        self._tasks: Dict[str, IngestTask] = {}
        self._task_order: List[str] = []  # Maintains insertion order
        self._active_workers: Dict[str, UploadWorker] = {}

        # Thread pool for concurrent uploads
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(config.max_concurrent_uploads)

        # Connector cache for history records
        self._connectors: Dict[str, ConnectorInfo] = {}

        # Pause state
        self._paused = False

        # Files already in queue (to prevent duplicates)
        self._queued_paths: Set[str] = set()

    @property
    def tasks(self) -> List[IngestTask]:
        """Get all tasks in order."""
        return [self._tasks[tid] for tid in self._task_order if tid in self._tasks]

    @property
    def pending_count(self) -> int:
        """Get count of pending tasks."""
        return sum(1 for t in self._tasks.values() if t.status == IngestStatus.PENDING)

    @property
    def active_count(self) -> int:
        """Get count of active (uploading) tasks."""
        return sum(1 for t in self._tasks.values() if t.status == IngestStatus.UPLOADING)

    @property
    def completed_count(self) -> int:
        """Get count of completed tasks."""
        return sum(1 for t in self._tasks.values() if t.status == IngestStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        """Get count of failed tasks."""
        return sum(1 for t in self._tasks.values() if t.status == IngestStatus.FAILED)

    @property
    def is_paused(self) -> bool:
        """Check if uploads are paused."""
        return self._paused

    def set_connectors(self, connectors: List[ConnectorInfo]) -> None:
        """Cache connector info for history records."""
        self._connectors = {c.id: c for c in connectors}

    def update_max_concurrent(self, max_concurrent: int) -> None:
        """Update maximum concurrent uploads."""
        self._thread_pool.setMaxThreadCount(max_concurrent)

    def set_max_concurrent(self, max_concurrent: int) -> None:
        """Alias for update_max_concurrent."""
        self.update_max_concurrent(max_concurrent)

    def get_all_tasks(self) -> List[IngestTask]:
        """Get all tasks (alias for tasks property)."""
        return self.tasks

    def add_file(
        self,
        file_path: str,
        connector_id: str,
        destination_path: str = "",
    ) -> Optional[IngestTask]:
        """
        Add a single file to the ingest queue.

        Args:
            file_path: Absolute path to the file.
            connector_id: Target connector ID.
            destination_path: Optional destination subfolder.

        Returns:
            Created IngestTask or None if file is invalid/duplicate.
        """
        # Normalize path
        file_path = os.path.abspath(file_path)

        # Check for duplicates
        if file_path in self._queued_paths:
            return None

        # Validate file exists
        if not os.path.isfile(file_path):
            return None

        # Check if supported
        if not is_supported_file(file_path):
            return None

        # Get content type
        content_type = get_content_type(file_path)
        if not content_type or not is_content_type_allowed(content_type):
            return None

        # Get file info
        file_size = os.path.getsize(file_path)
        original_filename = os.path.basename(file_path)
        sanitized_filename, was_modified = sanitize_filename(original_filename)

        # Create task
        task = IngestTask(
            task_id=str(uuid.uuid4()),
            file_path=file_path,
            filename=sanitized_filename,
            file_size=file_size,
            content_type=content_type,
            connector_id=connector_id,
            destination_path=destination_path,
            status=IngestStatus.PENDING,
        )

        # Add to tracking
        self._tasks[task.task_id] = task
        self._task_order.append(task.task_id)
        self._queued_paths.add(file_path)

        self.task_added.emit(task.task_id)
        self._emit_queue_updated()

        return task

    def add_files(
        self,
        file_paths: List[str],
        connector_id: str,
        destination_path: str = "",
    ) -> List[IngestTask]:
        """
        Add multiple files to the ingest queue.

        Args:
            file_paths: List of file paths.
            connector_id: Target connector ID.
            destination_path: Optional destination subfolder.

        Returns:
            List of created IngestTasks (excluding failures).
        """
        tasks = []
        for path in file_paths:
            task = self.add_file(path, connector_id, destination_path)
            if task:
                tasks.append(task)
        return tasks

    def add_folder(
        self,
        folder_path: str,
        connector_id: str,
        destination_path: str = "",
    ) -> List[IngestTask]:
        """
        Recursively add all supported files from a folder.

        Args:
            folder_path: Path to folder.
            connector_id: Target connector ID.
            destination_path: Optional destination subfolder.

        Returns:
            List of created IngestTasks.
        """
        file_paths = []
        folder = Path(folder_path)

        if folder.is_dir():
            for ext in SUPPORTED_EXTENSIONS:
                file_paths.extend(str(p) for p in folder.rglob(f"*{ext}"))
                # Also check uppercase
                file_paths.extend(str(p) for p in folder.rglob(f"*{ext.upper()}"))

        return self.add_files(file_paths, connector_id, destination_path)

    def get_task(self, task_id: str) -> Optional[IngestTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the queue.

        Only pending tasks can be removed.

        Returns:
            True if removed, False otherwise.
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status != IngestStatus.PENDING:
            return False

        # Remove from tracking
        self._queued_paths.discard(task.file_path)
        del self._tasks[task_id]
        if task_id in self._task_order:
            self._task_order.remove(task_id)

        self.task_removed.emit(task_id)
        self._emit_queue_updated()
        return True

    def start_uploads(self) -> None:
        """Start processing the upload queue."""
        self._paused = False
        self._process_queue()

    def pause_uploads(self) -> None:
        """Pause processing new uploads (active uploads continue)."""
        self._paused = True

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a specific task.

        Args:
            task_id: Task ID to cancel.

        Returns:
            True if cancellation was initiated.
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == IngestStatus.PENDING:
            task.status = IngestStatus.CANCELLED
            task.completed_at = datetime.now()
            self._record_history(task)
            self.task_cancelled.emit(task_id)
            self._emit_queue_updated()
            return True

        if task.status == IngestStatus.UPLOADING:
            worker = self._active_workers.get(task_id)
            if worker:
                worker.cancel()
            return True

        return False

    def cancel_all(self) -> None:
        """Cancel all pending and active tasks."""
        # Cancel active uploads
        for worker in list(self._active_workers.values()):
            worker.cancel()

        # Cancel pending tasks
        for task in self._tasks.values():
            if task.status == IngestStatus.PENDING:
                task.status = IngestStatus.CANCELLED
                task.completed_at = datetime.now()
                self._record_history(task)
                self.task_cancelled.emit(task.task_id)

        self._emit_queue_updated()

    def retry_task(self, task_id: str, connector_id: Optional[str] = None) -> Optional[IngestTask]:
        """
        Retry a failed task.

        Args:
            task_id: Task ID to retry.
            connector_id: Optional new connector ID.

        Returns:
            New task if retry was initiated.
        """
        task = self._tasks.get(task_id)
        if not task or task.status != IngestStatus.FAILED:
            return None

        # Create new task for retry
        return self.add_file(
            task.file_path,
            connector_id or task.connector_id,
            task.destination_path,
        )

    def clear_completed(self) -> int:
        """
        Remove all completed and cancelled tasks from the queue.

        Returns:
            Number of tasks removed.
        """
        to_remove = [
            tid
            for tid, task in self._tasks.items()
            if task.status in (IngestStatus.COMPLETED, IngestStatus.CANCELLED)
        ]

        for tid in to_remove:
            task = self._tasks[tid]
            self._queued_paths.discard(task.file_path)
            del self._tasks[tid]
            if tid in self._task_order:
                self._task_order.remove(tid)
            self.task_removed.emit(tid)

        if to_remove:
            self._emit_queue_updated()

        return len(to_remove)

    def _process_queue(self) -> None:
        """Process pending tasks up to concurrency limit."""
        if self._paused:
            return

        # Count active uploads
        active = len(self._active_workers)
        max_concurrent = self._thread_pool.maxThreadCount()

        # Start pending tasks up to limit
        for task_id in self._task_order:
            if active >= max_concurrent:
                break

            task = self._tasks.get(task_id)
            if task and task.status == IngestStatus.PENDING:
                self._start_task(task)
                active += 1

    def _start_task(self, task: IngestTask) -> None:
        """Start uploading a task."""
        worker = UploadWorker(
            task=task,
            api_client=self._api_client,
            chunk_size=self._config.get_chunk_size_bytes(),
        )

        # Connect signals
        worker.signals.started.connect(self._on_task_started)
        worker.signals.progress.connect(self._on_task_progress)
        worker.signals.completed.connect(self._on_task_completed)
        worker.signals.failed.connect(self._on_task_failed)
        worker.signals.cancelled.connect(self._on_task_cancelled)

        # Track worker
        self._active_workers[task.task_id] = worker

        # Start in thread pool
        self._thread_pool.start(worker)

    def _on_task_started(self, task_id: str) -> None:
        """Handle task started."""
        task = self._tasks.get(task_id)
        if task:
            self.task_started.emit(task)
        self._emit_queue_updated()

    def _on_task_progress(self, task_id: str, percent: float, bytes_uploaded: int) -> None:
        """Handle task progress update."""
        task = self._tasks.get(task_id)
        if task:
            self.task_progress.emit(task, int(percent))

    def _on_task_completed(self, task_id: str) -> None:
        """Handle task completion."""
        task = self._tasks.get(task_id)
        if task:
            self._record_history(task)
            self.task_completed.emit(task)

        # Remove from active workers
        self._active_workers.pop(task_id, None)

        self._emit_queue_updated()

        # Process more tasks
        self._process_queue()

    def _on_task_failed(self, task_id: str, error_message: str, error_detail: str) -> None:
        """Handle task failure."""
        task = self._tasks.get(task_id)
        if task:
            self._record_history(task)
            self.task_failed.emit(task, error_message)

        # Remove from active workers
        self._active_workers.pop(task_id, None)

        self._emit_queue_updated()

        # Process more tasks
        self._process_queue()

    def _on_task_cancelled(self, task_id: str) -> None:
        """Handle task cancellation."""
        task = self._tasks.get(task_id)
        if task:
            self._record_history(task)

        # Remove from active workers
        self._active_workers.pop(task_id, None)

        self.task_cancelled.emit(task_id)
        self._emit_queue_updated()

        # Process more tasks
        self._process_queue()

    def _record_history(self, task: IngestTask) -> None:
        """Record a completed task to history."""
        connector = self._connectors.get(task.connector_id)
        connector_name = connector.name if connector else task.connector_id

        duration = None
        if task.started_at and task.completed_at:
            duration = (task.completed_at - task.started_at).total_seconds()

        record = HistoryRecord(
            record_id=str(uuid.uuid4()),
            task_id=task.task_id,
            filename=task.filename,
            file_path=task.file_path,
            file_size=task.file_size,
            connector_id=task.connector_id,
            connector_name=connector_name,
            destination_path=task.destination_path,
            status=task.status.value,
            error_message=task.error_message,
            error_detail=task.error_detail,
            timestamp=task.completed_at or datetime.now(),
            duration_seconds=duration,
        )

        self._history.append(record)

    def _emit_queue_updated(self) -> None:
        """Emit queue updated signal with current counts."""
        self.queue_updated.emit(
            self.pending_count,
            self.active_count,
            self.completed_count,
            self.failed_count,
        )
        self.queue_changed.emit()
