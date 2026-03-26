# LakeLoader

A desktop application for bulk file ingestion into Media Lake.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

- **Drag-and-Drop Support**: Drag files or folders directly from Finder/Explorer
- **Bulk File Selection**: Browse and select multiple files or entire folders
- **Concurrent Uploads**: Configure parallel uploads for faster ingestion
- **Progress Tracking**: Real-time progress bars for each file
- **Multipart Upload**: Automatic chunked upload for large files (>100MB)
- **Upload History**: Track all completed and failed uploads with export to CSV
- **Retry Failed Uploads**: Automatic or manual retry for failed uploads
- **Connector Selection**: Choose target storage connector for each batch

## Installation

### Prerequisites

- Python 3.10 or higher
- Access to a deployed Media Lake instance
- Media Lake Cognito user credentials

### Install from Source

```bash
# Clone or navigate to the repository
cd lake-loader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

### Install Dependencies Only

```bash
pip install PySide6 requests boto3
```

## Usage

### Running the Application

```bash
# Using the installed entry point
lake-loader

# Or run directly
python -m lake_loader.main
```

### First-Time Setup

1. On first launch, you'll be prompted to configure your connection settings:
   - **API Base URL**: Your Media Lake API Gateway URL (e.g., `https://xxx.execute-api.us-east-1.amazonaws.com/prod`)
   - **User Pool ID**: Your Cognito User Pool ID
   - **Client ID**: Your Cognito App Client ID
   - **Region**: AWS region where Cognito is deployed

2. After entering settings, log in with your Media Lake username and password.

### Uploading Files

#### Using Drag-and-Drop
1. Drag files or folders from Finder (macOS) or Explorer (Windows) into the drop zone
2. Select a target connector from the dropdown
3. Optionally specify a destination path/prefix
4. Click **"Start All"** to begin uploading

#### Using File Browser
1. Click **"Add Files"** to select individual files
2. Click **"Add Folder"** to select an entire folder (recursive)
3. Select connector and destination path
4. Click **"Start All"**

### Managing Uploads

- **Pause/Resume**: Click individual row controls or use **"Pause All"/"Resume All"**
- **Cancel**: Right-click a row and select "Cancel" or use **"Cancel All"**
- **Retry Failed**: Select failed uploads in the queue and click **"Retry Selected"**
- **Clear Completed**: Remove finished uploads from the queue

### Viewing History

Switch to the **History** tab to:
- View all past uploads (completed and failed)
- Filter by status or search by filename
- Export history to CSV
- Delete old records

### Configuration Options

Access settings via the **Settings** tab:

| Setting | Description | Default |
|---------|-------------|---------|
| API Base URL | Media Lake API endpoint | (required) |
| User Pool ID | Cognito User Pool | (required) |
| Client ID | Cognito App Client | (required) |
| Region | AWS Region | us-east-1 |
| Max Concurrent | Parallel uploads | 3 |
| Chunk Size | Multipart chunk size | 10 MB |
| Max Retries | Automatic retry attempts | 3 |
| Max History | Records to keep | 10000 |

## Architecture

```
lake_loader/
├── core/
│   ├── models.py      # Data models (IngestTask, HistoryRecord, etc.)
│   ├── config.py      # Configuration management
│   └── history.py     # Upload history persistence
├── services/
│   ├── auth_service.py    # Cognito authentication
│   ├── api_client.py      # Media Lake API client
│   ├── upload_service.py  # File upload worker
│   └── ingest_manager.py  # Upload queue management
├── ui/
│   ├── main_window.py     # Main application window
│   ├── ingest_panel.py    # File queue and controls
│   ├── history_panel.py   # Upload history viewer
│   ├── settings_dialog.py # Configuration dialog
│   ├── login_dialog.py    # Authentication dialog
│   └── widgets/           # Custom UI components
└── main.py                # Application entry point
```

## Configuration Files

Configuration is stored in `~/.medialake_ingest/`:

- `config.json` - Application settings
- `history.json` - Upload history records

## Troubleshooting

### "Connection failed" on login
- Verify your API Base URL is correct and accessible
- Check Cognito User Pool ID and Client ID
- Ensure your user account exists and password is correct

### "Failed to load connectors"
- Check your network connection
- Verify API permissions for your user
- Ensure the Media Lake backend is running

### Slow uploads
- Increase concurrent upload count in Settings
- Check your network bandwidth
- For large files, multipart upload will automatically be used

### Authentication errors after idle
- The app automatically refreshes tokens
- If issues persist, log out and log back in

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Building

```bash
pip install build
python -m build
```

## License

This project is part of the Media Lake solution.
