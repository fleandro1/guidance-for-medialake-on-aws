# Prompt: Media Lake Ingest Application

## Overview

Build a standalone desktop ingest application for Media Lake, called **LakeLoader**. It is a Python application with a PyQt/PySide6 GUI that allows users to upload media files to Media Lake in bulk, with full progress tracking, detailed error reporting, and persistent ingest history.

---

## Architecture

The application follows a client/server design within a single process:

- **Backend service layer** (`services/`): Python classes that interact with the Media Lake REST API. No UI code here.
- **Frontend UI layer** (`ui/`): PySide6 widgets and windows. No business logic here.
- **Signal/slot bridge**: Qt signals decouple the service layer from the UI.

```
medialake_ingest/
├── main.py                     # Entry point
├── core/
│   ├── config.py               # Config dataclass + JSON persistence
│   ├── history.py              # IngestHistory dataclass + JSON persistence
│   └── models.py               # IngestTask, IngestStatus, ConnectorInfo, etc.
├── services/
│   ├── auth_service.py         # Cognito authentication (USER_PASSWORD_AUTH)
│   ├── api_client.py           # Synchronous HTTP client wrapping Media Lake REST API
│   ├── upload_service.py       # Orchestrates single-part and multipart upload flows
│   └── ingest_manager.py       # Queue manager: concurrency, retry, progress
├── ui/
│   ├── main_window.py          # Main application window with tab navigation
│   ├── ingest_panel.py         # File selection, queue table, start/stop controls
│   ├── history_panel.py        # History viewer with filter, delete-last-N, export
│   ├── settings_dialog.py      # Settings editor (all editable fields)
│   └── widgets/
│       ├── progress_delegate.py # Custom QStyledItemDelegate for progress bars in table
│       └── status_badge.py      # Colored status indicator widget
└── tests/
    └── ...
```

---

## Technology Stack

| Component | Library |
|---|---|
| GUI framework | **PySide6** (Qt 6) |
| HTTP requests | `requests` (synchronous, run in `QThread`) |
| S3 multipart upload | `requests` + presigned URLs from Media Lake API |
| Config/history | `json` (stdlib), stored in `~/.medialake_ingest/` |
| Auth | `boto3` → `cognito-idp` (USER_PASSWORD_AUTH) |
| Packaging | `pyproject.toml` + `setuptools` |

---

## Media Lake API Reference

All endpoints are under the base URL configured in settings. All requests must include:
```
Authorization: Bearer <id_token>
Content-Type: application/json
```

### Authentication — Cognito USER_PASSWORD_AUTH

Use `boto3` with `cognito-idp`:

```python
response = cognito_client.initiate_auth(
    AuthFlow="USER_PASSWORD_AUTH",
    ClientId=client_id,
    AuthParameters={"USERNAME": username, "PASSWORD": password},
)
tokens = response["AuthenticationResult"]
# tokens: { AccessToken, IdToken, RefreshToken, ExpiresIn }
```

Use `IdToken` as the Bearer token in API requests. Refresh using `REFRESH_TOKEN_AUTH` before expiry.

Handle challenges:
- `NEW_PASSWORD_REQUIRED` → surface a clear error telling the user to log in to the web UI first.

### `GET /api/connectors`

Returns a list of available storage connectors.

```json
{
  "status": "success",
  "data": {
    "connectors": [
      {
        "id": "connector-id",
        "name": "My S3 Bucket",
        "storageIdentifier": "my-bucket-name",
        "region": "us-east-1",
        "objectPrefix": "uploads/",
        "status": "active"
      }
    ]
  }
}
```

### `POST /api/assets/upload`

Initiate an upload and get either a presigned POST URL (files ≤ 100 MB) or multipart upload info (files > 100 MB).

**Request body:**
```json
{
  "connector_id": "string",
  "filename": "string",         // must match ^[a-zA-Z0-9!\-_.*'()]+$
  "content_type": "string",    // audio/*, video/*, image/*, application/x-mpegURL, application/dash+xml
  "file_size": 1234567,        // integer, bytes
  "path": "optional/subfolder" // optional, defaults to ""
}
```

**Response — single-part upload (≤ 100 MB):**
```json
{
  "data": {
    "multipart": false,
    "bucket": "bucket-name",
    "key": "path/to/filename.mp4",
    "presigned_post": {
      "url": "https://bucket.s3.amazonaws.com/",
      "fields": { "key": "...", "Content-Type": "...", "AWSAccessKeyId": "...", "Policy": "...", "Signature": "..." }
    },
    "expires_in": 3600
  }
}
```

**Uploading single-part file:** HTTP `POST` to `presigned_post.url` as `multipart/form-data`, with all `presigned_post.fields` included as form fields, plus the file as the `file` field.

**Response — multipart upload (> 100 MB):**
```json
{
  "data": {
    "multipart": true,
    "bucket": "bucket-name",
    "key": "path/to/filename.mp4",
    "upload_id": "abc123...",
    "part_size": 5242880,
    "total_parts": 42,
    "expires_in": 3600
  }
}
```

### `POST /api/assets/upload/multipart/sign`

Get a presigned PUT URL for a single part. Call this on-demand as each part is about to be uploaded (do not pre-generate all URLs at once).

**Request body:**
```json
{
  "connector_id": "string",
  "upload_id": "string",
  "key": "path/to/filename.mp4",
  "part_number": 1
}
```

**Response:**
```json
{ "data": { "url": "https://presigned-put-url..." } }
```

**Uploading a part:** HTTP `PUT` to the returned URL, with the raw binary chunk as the body. Capture the `ETag` response header.

### `POST /api/assets/upload/multipart/complete`

Finalize the multipart upload after all parts are uploaded.

**Request body:**
```json
{
  "connector_id": "string",
  "upload_id": "string",
  "key": "path/to/filename.mp4",
  "parts": [
    { "PartNumber": 1, "ETag": "\"etag-value-1\"" },
    { "PartNumber": 2, "ETag": "\"etag-value-2\"" }
  ]
}
```

### `POST /api/assets/upload/multipart/abort`

Abort an in-progress multipart upload (call on cancel or unrecoverable error).

**Request body:**
```json
{
  "connector_id": "string",
  "upload_id": "string",
  "key": "path/to/filename.mp4"
}
```

---

## Core Data Models (`core/models.py`)

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

class IngestStatus(Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class IngestTask:
    task_id: str
    file_path: str                  # Absolute local path
    filename: str                   # Sanitized S3-safe filename
    file_size: int
    content_type: str
    connector_id: str
    destination_path: str = ""
    status: IngestStatus = IngestStatus.PENDING
    progress: float = 0.0           # 0.0 to 100.0
    error_message: Optional[str] = None
    error_detail: Optional[str] = None   # Full traceback / API response body
    bytes_uploaded: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

@dataclass
class HistoryRecord:
    record_id: str
    task_id: str
    filename: str
    file_path: str
    file_size: int
    connector_id: str
    connector_name: str
    destination_path: str
    status: str                      # final status as string
    error_message: Optional[str]
    error_detail: Optional[str]
    timestamp: datetime              # ISO 8601 string when serialized
    duration_seconds: Optional[float]
```

---

## Configuration (`core/config.py`)

Store in `~/.medialake_ingest/config.json`. All fields must be editable through the Settings UI.

```python
@dataclass
class Config:
    # Media Lake connection
    api_base_url: str = ""            # e.g. https://abc123.execute-api.us-east-1.amazonaws.com/prod

    # Cognito auth
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"

    # Stored credentials (optional, for auto-login)
    saved_username: str = ""
    # NOTE: Never store passwords. Store only tokens with expiry.

    # Ingest behaviour
    max_concurrent_uploads: int = 5
    default_connector_id: str = ""
    default_destination_path: str = ""
    retry_on_failure: bool = True
    max_retries: int = 3
    chunk_size_mb: int = 5           # Part size used for multipart uploads

    # History
    max_history_records: int = 10000
```

Load via `Config.load()` / save via `config.save()`. Use `json` stdlib with `dataclasses.asdict()`.

---

## Ingest History (`core/history.py`)

Store in `~/.medialake_ingest/history.json` as a JSON array of `HistoryRecord` objects, most recent first.

Implement:
- `history.append(record: HistoryRecord)` — prepends to list
- `history.delete_latest(n: int)` — removes the first `n` records
- `history.save()` / `history.load()`
- `history.clear_all()`

---

## Upload Service Logic (`services/upload_service.py`)

The upload service runs each upload task in a `QThread` (or `concurrent.futures.ThreadPoolExecutor`). It must:

1. **Sanitize filename** — strip characters not matching `^[a-zA-Z0-9!\-_.*'()]+$` before calling the API (replace disallowed chars with `_`).
2. **Detect content type** using `mimetypes.guess_type(file_path)`, map to allowed Media Lake types:
   - `audio/*`, `video/*`, `image/*`, `application/x-mpegURL`, `application/dash+xml`
   - Reject files whose content type doesn't match any allowed prefix.
3. **Call `POST /api/assets/upload`** with `connector_id`, `filename`, `content_type`, `file_size`, `path`.
4. **Branch on `multipart` flag**:
   - `False` → presigned POST: use `requests.post(url, data=fields, files={"file": file_bytes})`
   - `True` → multipart flow:
     - For each part (1-indexed): sign → `requests.put(signed_url, data=chunk)` → collect `ETag`
     - After all parts: call `POST /api/assets/upload/multipart/complete`
     - On cancellation or error: call `POST /api/assets/upload/multipart/abort`
5. **Emit progress signals** after each part or chunk of single-part upload.
6. **Capture full error detail** on any non-2xx response: status code + response body + exception traceback.

---

## Ingest Manager (`services/ingest_manager.py`)

Manages the queue with bounded concurrency:

- Holds a `queue` of `IngestTask` objects.
- At any given time, at most `config.max_concurrent_uploads` tasks are active.
- Uses `QThreadPool` or a pool of dedicated `QThread` workers (one per slot).
- When a slot becomes free, dequeues the next `PENDING` task and starts it.
- Emits Qt signals: `task_started(task_id)`, `task_progress(task_id, percent)`, `task_completed(task_id)`, `task_failed(task_id, message, detail)`, `queue_updated(pending, active, done, failed)`.
- Supports `pause_all()`, `resume_all()`, `cancel_task(task_id)`, `cancel_all()`.
- On completion (success or failure), records to `IngestHistory`.

---

## UI — Main Window (`ui/main_window.py`)

A `QMainWindow` with a left navigation panel (or top `QTabWidget`) with tabs:
1. **Ingest** — file queue and upload controls
2. **History** — past ingest records
3. **Settings** — configuration editor

Show a persistent status bar with: active upload count / total queued / completed / failed.

---

## UI — Ingest Panel (`ui/ingest_panel.py`)

**File Addition Methods:**
The panel must support **three ways** to add files to the ingest queue:
1. **Add Files** button — opens `QFileDialog` for multi-file selection
2. **Add Folder** button — opens folder picker, recursively adds media files
3. **Drag and Drop** — accept files and folders dragged from Finder (macOS) or Windows Explorer directly onto the queue area

**Drag-and-Drop Implementation:**
- Enable `setAcceptDrops(True)` on the ingest panel or the queue table widget.
- Override `dragEnterEvent()` to accept `QMimeData` containing `urls` (file paths).
- Override `dropEvent()` to extract file paths from `event.mimeData().urls()`.
- For dropped folders, recursively scan for supported media files (same logic as Add Folder).
- Provide visual feedback during drag: highlight the drop zone with a dashed border or color change.
- Display a brief toast or status message confirming how many files were added after a drop.

**Controls row:**
- **Add Files** button (opens `QFileDialog` for multi-file selection)
- **Add Folder** button (opens folder picker, recursively adds media files)
- **Connector** dropdown (populated from `GET /api/connectors`)
- **Destination Path** text field (optional subfolder prefix)
- **Start Upload** / **Pause** / **Cancel All** buttons

**Queue table (`QTableView` + model):**

| # | Filename | Size | Status | Progress | Speed | ETA | Error |
|---|---|---|---|---|---|---|---|

- The **Progress** column renders a `QProgressBar` via a custom `QStyledItemDelegate`.
- The **Status** column shows a colored badge: grey (pending), blue (uploading), green (completed), red (failed), orange (cancelled).
- The **Error** column shows a short message. Clicking it opens a modal dialog with the full error detail (API response body, HTTP status code, traceback).
- Right-click context menu: **Remove** (pending only), **Retry** (failed only), **Show Error Details**.

**Summary bar** below the table:
```
0 pending  |  2 uploading  |  15 completed  |  1 failed
```

---

## UI — History Panel (`ui/history_panel.py`)

- `QTableView` showing all `HistoryRecord` entries with columns: Timestamp, Filename, Size, Connector, Destination, Status, Duration, Error.
- **Filter bar**: text search on filename, status filter dropdown (All / Completed / Failed / Cancelled).
- **Delete Latest N Records** button: opens a `QInputDialog` asking for N, then calls `history.delete_latest(n)`.
- **Clear All History** button (with confirmation dialog).
- **Export CSV** button.
- Clicking any failed row opens the error detail modal.

---

## UI — Settings Dialog (`ui/settings_dialog.py`)

A `QDialog` with form layout. Every `Config` field must have a corresponding input widget:

| Field | Widget |
|---|---|
| API Base URL | `QLineEdit` |
| Cognito User Pool ID | `QLineEdit` |
| Cognito Client ID | `QLineEdit` |
| Cognito Region | `QComboBox` (AWS regions) |
| Saved Username | `QLineEdit` |
| Max Concurrent Uploads | `QSpinBox` (1–20) |
| Default Connector | `QComboBox` (loaded from API) |
| Default Destination Path | `QLineEdit` |
| Retry on Failure | `QCheckBox` |
| Max Retries | `QSpinBox` (0–10) |
| Multipart Chunk Size (MB) | `QSpinBox` (5–100) |
| Max History Records | `QSpinBox` (100–100000) |

**OK** saves to `~/.medialake_ingest/config.json`. **Cancel** discards.

Add a **Test Connection** button that attempts authentication and `GET /api/connectors`, then shows a success/failure message inline.

---

## Error Handling Requirements

- Every API call must capture HTTP status code + response body on non-2xx.
- Timeouts (`requests.Timeout`) must be caught and reported as `"Connection timed out. Check API URL and network."`.
- Auth errors (401, Cognito `NotAuthorizedException`) must prompt re-authentication.
- Failed tasks must store `error_message` (short, user-friendly) and `error_detail` (full technical context).
- The history record for a failed task must preserve both.
- Network errors during multipart upload must abort the multipart upload cleanly.

---

## File & Folder Ingestion Rules

- Supported file extensions for auto-detection when adding a folder: `.mp4`, `.mov`, `.mxf`, `.avi`, `.mkv`, `.mp3`, `.wav`, `.aiff`, `.flac`, `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`, `.exr`, `.dpx`, `.m4v`, `.webm`, `.m3u8`, `.mpd`.
- Files already in the queue (same `file_path`) should be skipped with a warning (do not duplicate).
- Filenames must be sanitized to match the S3 regex `^[a-zA-Z0-9!\-_.*'()]+$` before uploading. Inform the user which characters were replaced.

---

## Persistence File Locations

| File | Location |
|---|---|
| `config.json` | `~/.medialake_ingest/config.json` |
| `history.json` | `~/.medialake_ingest/history.json` |

Create the directory on first run if it doesn't exist (`Path.mkdir(parents=True, exist_ok=True)`).

---

## Non-Goals (Out of Scope)

- Do not build a download/browse feature.
- Do not integrate with DaVinci Resolve.
- Do not implement any server-side component. All Media Lake interaction is via the existing REST API.

---

## Reference: Existing Plugin

The workspace contains a DaVinci Resolve plugin at `davinci_resolve_plugin/medialake_resolve/` that implements the same authentication flow, API client pattern, and PySide6 upload worker architecture. Use it as a reference for:
- **Auth**: `davinci_resolve_plugin/medialake_resolve/auth/auth_service.py` — exactly the Cognito flow to replicate.
- **API client**: `davinci_resolve_plugin/medialake_resolve/api/api_client.py`
- **Upload worker pattern**: `davinci_resolve_plugin/medialake_resolve/upload/upload_worker.py`
- **Config persistence**: `davinci_resolve_plugin/medialake_resolve/core/config.py`

Do **not** copy the Resolve-specific code (media pool, DaVinci bridge). Implement fresh, standalone equivalents.
