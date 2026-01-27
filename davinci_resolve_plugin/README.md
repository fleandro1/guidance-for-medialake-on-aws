# DaVinci Resolve Media Lake Plugin

A Qt-based panel for DaVinci Resolve that integrates with Media Lake for asset browsing, searching, and importing.

## Features

- **Library-style Browser**: Grid/list view of Media Lake assets with thumbnails
- **Dual Search**: Keyword and semantic search capabilities
- **Multi-select Downloads**: Batch download up to 50 assets at once
- **Original/Proxy Support**: Download originals or proxies, with automatic linking in Resolve
- **Secure Authentication**: Credentials stored in OS keychain
- **Video Preview**: Built-in preview player with bundled FFmpeg codecs
- **Pagination**: Configurable page sizes (10, 20, 30, 50 items per page)

## Requirements

- DaVinci Resolve 18+ (Free or Studio)
- Python 3.10+
- PySide6 6.5+
- macOS, Windows, or Linux

## Installation Options

### Option 1: Integrate with DaVinci Resolve (Recommended)

This installs Media Lake as a Workflow Integration that appears in Resolve's **Workspace → Workflow Integrations** menu.

```bash
# Run the installer
./install_resolve_plugin.sh
```

The installer will:
1. Create a symlink (for development) or copy files (for production) to Resolve's plugins directory
2. After installation, restart DaVinci Resolve
3. Access Media Lake from: **Workspace → Workflow Integrations → MediaLake**

**Plugin Directory Locations:**
- macOS: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/`
- Windows: `%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins\`

### Option 2: Run as Standalone Application

Run Media Lake as a standalone window alongside DaVinci Resolve:

```bash
./launch_medialake.sh
```

Or manually:

```bash
source /opt/conda/envs/python_3_11/bin/activate  # or your Python environment
python -m medialake_resolve
```

### macOS Installation Script

```bash
./scripts/install_macos.sh
```

### Windows

```powershell
.\scripts\install_windows.ps1
```

### Linux

```bash
./scripts/install_linux.sh
```

## Manual Installation

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install the package:
   ```bash
   pip install -e .
   ```

4. Run the plugin:
   ```bash
   medialake-resolve
   ```

## Configuration

On first launch, you'll be prompted to configure:

1. **Media Lake Instance URL**: Your Media Lake deployment URL
2. **Authentication**: Sign in with your Cognito credentials
3. **Resolve Integration**: The plugin will auto-detect DaVinci Resolve

## Usage

### Connecting to Media Lake

1. Click the **Settings** (gear) icon
2. Enter your Media Lake URL (e.g., `https://medialake.example.com`)
3. Click **Sign In** and enter your credentials
4. Credentials are securely stored in your OS keychain

### Browsing Assets

- Use the **Collection** dropdown to filter by collection
- Toggle between **Grid** and **List** view
- Click thumbnails to preview assets
- Use checkboxes for multi-select

### Searching

- **Keyword Search**: Type search terms and press Enter
- **Semantic Search**: Toggle the "Semantic" switch for AI-powered search
- Filter results by media type, date range, and more

### Downloading & Importing

1. Select one or more assets (up to 50)
2. Click **Download** or **Download Proxy**
3. Assets are downloaded to Resolve's Working Folders
4. Proxies are automatically linked to originals in the Media Pool

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
black medialake_resolve/
isort medialake_resolve/
```

## Architecture

```
medialake_resolve/
├── __init__.py
├── __main__.py              # Entry point
├── core/                    # Core functionality
│   ├── config.py           # Configuration management
│   ├── version.py          # Version info
│   ├── models.py           # Data models
│   └── errors.py           # Custom exceptions
├── auth/                    # Authentication
│   ├── credential_manager.py
│   ├── auth_service.py
│   └── token_manager.py
├── api/                     # Media Lake API client
│   └── api_client.py
├── resolve/                 # DaVinci Resolve integration
│   ├── connection.py
│   ├── project_settings.py
│   └── media_importer.py
├── download/                # Download management
│   ├── download_worker.py
│   └── download_import_controller.py
├── ui/                      # Qt UI components
│   ├── main_window.py
│   ├── login_dialog.py
│   ├── search_panel.py
│   ├── browser_view.py
│   └── preview_panel.py
├── utils/                   # Utilities
│   ├── ffmpeg_utils.py
│   ├── format_utils.py
│   └── file_utils.py
└── resources/               # Assets
    ├── icons/
    └── styles/
```

## License

MIT License - see LICENSE file for details.
