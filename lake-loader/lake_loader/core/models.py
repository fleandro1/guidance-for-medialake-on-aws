"""Data models for LakeLoader application."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import re
import mimetypes


class IngestStatus(Enum):
    """Status of an ingest task."""

    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class IngestTask:
    """Represents a single file upload task."""

    task_id: str
    file_path: str  # Absolute local path
    filename: str  # Sanitized S3-safe filename
    file_size: int
    content_type: str
    connector_id: str
    destination_path: str = ""
    status: IngestStatus = IngestStatus.PENDING
    progress: float = 0.0  # 0.0 to 100.0
    error_message: Optional[str] = None
    error_detail: Optional[str] = None  # Full traceback / API response body
    bytes_uploaded: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Multipart upload tracking
    upload_id: Optional[str] = None
    s3_key: Optional[str] = None
    total_parts: int = 0
    completed_parts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "file_path": self.file_path,
            "filename": self.filename,
            "file_size": self.file_size,
            "content_type": self.content_type,
            "connector_id": self.connector_id,
            "destination_path": self.destination_path,
            "status": self.status.value,
            "progress": self.progress,
            "error_message": self.error_message,
            "error_detail": self.error_detail,
            "bytes_uploaded": self.bytes_uploaded,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "upload_id": self.upload_id,
            "s3_key": self.s3_key,
            "total_parts": self.total_parts,
            "completed_parts": self.completed_parts,
        }

    def to_history_record(self, connector_name: str = "") -> "HistoryRecord":
        """Convert to a HistoryRecord for persistence."""
        import uuid
        
        duration = None
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()
        
        return HistoryRecord(
            record_id=str(uuid.uuid4()),
            task_id=self.task_id,
            filename=self.filename,
            file_path=self.file_path,
            file_size=self.file_size,
            connector_id=self.connector_id,
            connector_name=connector_name,
            destination_path=self.destination_path,
            status=self.status.value,
            error_message=self.error_message,
            error_detail=self.error_detail,
            timestamp=self.completed_at or datetime.now(),
            duration_seconds=duration,
        )


@dataclass
class HistoryRecord:
    """Record of a completed (success or failure) ingest task."""

    record_id: str
    task_id: str
    filename: str
    file_path: str
    file_size: int
    connector_id: str
    connector_name: str
    destination_path: str
    status: str  # final status as string
    error_message: Optional[str]
    error_detail: Optional[str]
    timestamp: datetime  # ISO 8601 string when serialized
    duration_seconds: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "record_id": self.record_id,
            "task_id": self.task_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "connector_id": self.connector_id,
            "connector_name": self.connector_name,
            "destination_path": self.destination_path,
            "status": self.status,
            "error_message": self.error_message,
            "error_detail": self.error_detail,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryRecord":
        """Create from dictionary."""
        return cls(
            record_id=data["record_id"],
            task_id=data["task_id"],
            filename=data["filename"],
            file_path=data["file_path"],
            file_size=data["file_size"],
            connector_id=data["connector_id"],
            connector_name=data["connector_name"],
            destination_path=data["destination_path"],
            status=data["status"],
            error_message=data.get("error_message"),
            error_detail=data.get("error_detail"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            duration_seconds=data.get("duration_seconds"),
        )


@dataclass
class ConnectorInfo:
    """Information about a Media Lake storage connector."""

    id: str
    name: str
    storage_identifier: str  # bucket name
    region: str
    object_prefix: str
    status: str

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "ConnectorInfo":
        """Create from API response."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            storage_identifier=data.get("storageIdentifier", ""),
            region=data.get("region", ""),
            object_prefix=data.get("objectPrefix", ""),
            status=data.get("status", "unknown"),
        )


@dataclass
class TokenInfo:
    """Authentication token information."""

    access_token: str
    id_token: str
    refresh_token: str
    expires_at: datetime

    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.now() >= self.expires_at

    def is_expiring_soon(self, threshold_seconds: int = 300) -> bool:
        """Check if the token will expire within threshold_seconds."""
        from datetime import timedelta

        return datetime.now() >= (self.expires_at - timedelta(seconds=threshold_seconds))


# Supported media file extensions
SUPPORTED_EXTENSIONS = {
    # Video
    ".mp4",
    ".mov",
    ".mxf",
    ".avi",
    ".mkv",
    ".m4v",
    ".webm",
    # Audio
    ".mp3",
    ".wav",
    ".aiff",
    ".flac",
    # Image
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".tif",
    ".exr",
    ".dpx",
    # Streaming
    ".m3u8",
    ".mpd",
}

# Allowed content type prefixes for Media Lake
ALLOWED_CONTENT_TYPE_PREFIXES = [
    "audio/",
    "video/",
    "image/",
    "application/x-mpegURL",
    "application/dash+xml",
]

# S3-safe filename regex
S3_SAFE_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9!\-_.*'()]+$")


def sanitize_filename(filename: str) -> tuple[str, bool]:
    """
    Sanitize filename to be S3-safe.

    Returns:
        Tuple of (sanitized_filename, was_modified)
    """
    if S3_SAFE_FILENAME_REGEX.match(filename):
        return filename, False

    # Replace disallowed characters with underscore
    sanitized = re.sub(r"[^a-zA-Z0-9!\-_.*'()]", "_", filename)
    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    # Ensure we have a valid filename
    if not sanitized:
        sanitized = "unnamed_file"

    return sanitized, True


def get_content_type(file_path: str) -> Optional[str]:
    """
    Get the MIME type for a file.

    Returns:
        Content type string or None if not supported.
    """
    mime_type, _ = mimetypes.guess_type(file_path)

    if mime_type is None:
        # Try to determine from extension
        ext = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""
        extension_map = {
            "mp4": "video/mp4",
            "mov": "video/quicktime",
            "mxf": "video/mxf",
            "avi": "video/x-msvideo",
            "mkv": "video/x-matroska",
            "m4v": "video/x-m4v",
            "webm": "video/webm",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "aiff": "audio/aiff",
            "flac": "audio/flac",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "tiff": "image/tiff",
            "tif": "image/tiff",
            "exr": "image/x-exr",
            "dpx": "image/x-dpx",
            "m3u8": "application/x-mpegURL",
            "mpd": "application/dash+xml",
        }
        mime_type = extension_map.get(ext)

    return mime_type


def is_content_type_allowed(content_type: Optional[str]) -> bool:
    """Check if a content type is allowed by Media Lake."""
    if content_type is None:
        return False

    for prefix in ALLOWED_CONTENT_TYPE_PREFIXES:
        if content_type.startswith(prefix) or content_type == prefix.rstrip("/"):
            return True

    return False


def is_supported_file(file_path: str) -> bool:
    """Check if a file has a supported extension."""
    ext = "." + file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""
    return ext in SUPPORTED_EXTENSIONS


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
