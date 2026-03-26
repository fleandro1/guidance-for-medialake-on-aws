"""Upload service for handling file uploads to Media Lake."""

import os
import time
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import requests
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from lake_loader.core.models import IngestStatus, IngestTask
from lake_loader.services.api_client import APIError, MediaLakeAPIClient


class UploadSignals(QObject):
    """Signals for upload worker communication."""

    started = Signal(str)  # task_id
    progress = Signal(str, float, int)  # task_id, percent, bytes_uploaded
    completed = Signal(str)  # task_id
    failed = Signal(str, str, str)  # task_id, error_message, error_detail
    cancelled = Signal(str)  # task_id


class UploadWorker(QRunnable):
    """
    Worker for uploading a single file.

    Runs in a thread pool and handles both single-part and multipart uploads.
    """

    # Multipart threshold: 100MB
    MULTIPART_THRESHOLD = 100 * 1024 * 1024

    def __init__(
        self,
        task: IngestTask,
        api_client: MediaLakeAPIClient,
        chunk_size: int = 5 * 1024 * 1024,
    ):
        """
        Initialize upload worker.

        Args:
            task: The ingest task to process.
            api_client: API client for Media Lake requests.
            chunk_size: Chunk size for multipart uploads (default 5MB).
        """
        super().__init__()
        self.task = task
        self.api_client = api_client
        self.chunk_size = chunk_size
        self.signals = UploadSignals()
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the upload."""
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        """Execute the upload."""
        try:
            self.task.status = IngestStatus.UPLOADING
            self.task.started_at = datetime.now()
            self.signals.started.emit(self.task.task_id)

            if self._cancelled:
                self._handle_cancellation()
                return

            # Initiate upload with Media Lake API
            upload_info = self.api_client.initiate_upload(
                connector_id=self.task.connector_id,
                filename=self.task.filename,
                content_type=self.task.content_type,
                file_size=self.task.file_size,
                path=self.task.destination_path,
            )

            if self._cancelled:
                self._handle_cancellation()
                return

            # Check if multipart or single-part
            is_multipart = upload_info.get("multipart", False)

            if is_multipart:
                self._upload_multipart(upload_info)
            else:
                self._upload_single_part(upload_info)

            if self._cancelled:
                return

            # Success
            self.task.status = IngestStatus.COMPLETED
            self.task.progress = 100.0
            self.task.completed_at = datetime.now()
            self.signals.completed.emit(self.task.task_id)

        except Exception as e:
            self._handle_error(e)

    def _upload_single_part(self, upload_info: Dict[str, Any]) -> None:
        """
        Upload file using presigned POST (single-part).

        Args:
            upload_info: Upload info from API with presigned_post data.
        """
        presigned_post = upload_info.get("presigned_post", {})
        upload_url = presigned_post.get("url", "")
        fields = presigned_post.get("fields", {})

        if not upload_url:
            raise APIError("No upload URL provided by API")

        # Emit initial progress
        self.task.progress = 10.0
        self.signals.progress.emit(self.task.task_id, 10.0, 0)
        time.sleep(0.15)

        if self._cancelled:
            return

        # Read file
        with open(self.task.file_path, "rb") as f:
            file_data = f.read()

        # Emit reading complete progress
        self.task.progress = 25.0
        self.signals.progress.emit(self.task.task_id, 25.0, 0)
        time.sleep(0.1)

        if self._cancelled:
            return

        # Emit uploading progress
        self.task.progress = 50.0
        self.signals.progress.emit(self.task.task_id, 50.0, int(self.task.file_size * 0.5))
        time.sleep(0.1)

        # Upload with progress tracking
        # For single-part, we upload in one go but can track via callback
        response = requests.post(
            upload_url,
            data=fields,
            files={"file": (self.task.filename, file_data, self.task.content_type)},
            timeout=600,  # 10 minute timeout for large files
        )

        if not response.ok:
            raise APIError(
                message=f"Upload failed: {response.status_code}",
                status_code=response.status_code,
                response_body=response.text,
            )

        # Emit near-complete progress
        self.task.progress = 90.0
        self.signals.progress.emit(self.task.task_id, 90.0, int(self.task.file_size * 0.9))
        time.sleep(0.15)

        self.task.bytes_uploaded = self.task.file_size
        self.task.progress = 100.0
        self.signals.progress.emit(self.task.task_id, 100.0, self.task.file_size)

    def _upload_multipart(self, upload_info: Dict[str, Any]) -> None:
        """
        Upload file using multipart upload.

        Args:
            upload_info: Upload info from API with multipart data.
        """
        upload_id = upload_info.get("upload_id", "")
        s3_key = upload_info.get("key", "")
        part_size = upload_info.get("part_size", self.chunk_size)
        total_parts = upload_info.get("total_parts", 0)

        if not upload_id or not s3_key:
            raise APIError("Invalid multipart upload info from API")

        # Store for potential abort
        self.task.upload_id = upload_id
        self.task.s3_key = s3_key
        self.task.total_parts = total_parts

        completed_parts = []
        bytes_uploaded = 0

        try:
            with open(self.task.file_path, "rb") as f:
                part_number = 1

                while True:
                    if self._cancelled:
                        self._abort_multipart()
                        return

                    chunk = f.read(part_size)
                    if not chunk:
                        break

                    # Get presigned URL for this part
                    presigned_url = self.api_client.sign_multipart_part(
                        connector_id=self.task.connector_id,
                        upload_id=upload_id,
                        key=s3_key,
                        part_number=part_number,
                    )

                    if self._cancelled:
                        self._abort_multipart()
                        return

                    # Upload the part
                    response = requests.put(
                        presigned_url,
                        data=chunk,
                        timeout=300,  # 5 minute timeout per part
                    )

                    if not response.ok:
                        raise APIError(
                            message=f"Part {part_number} upload failed: {response.status_code}",
                            status_code=response.status_code,
                            response_body=response.text,
                        )

                    # Get ETag from response
                    etag = response.headers.get("ETag", "")
                    if not etag:
                        raise APIError(f"No ETag returned for part {part_number}")

                    completed_parts.append({
                        "PartNumber": part_number,
                        "ETag": etag,
                    })

                    # Update progress
                    bytes_uploaded += len(chunk)
                    progress = (bytes_uploaded / self.task.file_size) * 100.0
                    self.task.bytes_uploaded = bytes_uploaded
                    self.task.progress = progress
                    self.task.completed_parts = completed_parts.copy()
                    self.signals.progress.emit(self.task.task_id, progress, bytes_uploaded)

                    part_number += 1

            if self._cancelled:
                self._abort_multipart()
                return

            # Complete the multipart upload
            self.api_client.complete_multipart_upload(
                connector_id=self.task.connector_id,
                upload_id=upload_id,
                key=s3_key,
                parts=completed_parts,
            )

        except Exception:
            # Abort on any error
            self._abort_multipart()
            raise

    def _abort_multipart(self) -> None:
        """Abort an in-progress multipart upload."""
        if self.task.upload_id and self.task.s3_key:
            try:
                self.api_client.abort_multipart_upload(
                    connector_id=self.task.connector_id,
                    upload_id=self.task.upload_id,
                    key=self.task.s3_key,
                )
            except Exception as e:
                print(f"Warning: Failed to abort multipart upload: {e}")

    def _handle_cancellation(self) -> None:
        """Handle upload cancellation."""
        self.task.status = IngestStatus.CANCELLED
        self.task.completed_at = datetime.now()
        self.signals.cancelled.emit(self.task.task_id)

    def _handle_error(self, error: Exception) -> None:
        """Handle upload error."""
        self.task.status = IngestStatus.FAILED
        self.task.completed_at = datetime.now()

        if isinstance(error, APIError):
            self.task.error_message = error.message
            self.task.error_detail = error.detail
        else:
            self.task.error_message = str(error)
            self.task.error_detail = traceback.format_exc()

        self.signals.failed.emit(
            self.task.task_id,
            self.task.error_message or "Unknown error",
            self.task.error_detail or "",
        )
