#!/bin/bash
# Install script for Media Lake DaVinci Resolve Plugin on macOS

set -e

echo "=================================="
echo "Media Lake Resolve Plugin Installer"
echo "=================================="
echo ""

# Check for Python 3.10+
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            echo "✓ Python $PYTHON_VERSION found"
            return 0
        fi
    fi
    
    echo "✗ Python 3.10 or higher is required"
    echo "  Please install Python from https://www.python.org/downloads/"
    exit 1
}

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Project directory: $PROJECT_DIR"
echo ""

# Check Python version
check_python

# Create virtual environment
VENV_DIR="$PROJECT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists"
    read -p "Do you want to recreate it? (y/N): " RECREATE
    if [ "$RECREATE" = "y" ] || [ "$RECREATE" = "Y" ]; then
        rm -rf "$VENV_DIR"
        echo "Creating new virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
else
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r "$PROJECT_DIR/requirements.txt"

# Install the package in development mode
echo ""
echo "Installing Media Lake Resolve Plugin..."
pip install -e "$PROJECT_DIR"

# Download FFmpeg if not present
FFMPEG_DIR="$PROJECT_DIR/medialake_resolve/ffmpeg/bin"
if [ ! -f "$FFMPEG_DIR/ffmpeg" ]; then
    echo ""
    echo "Downloading FFmpeg..."
    
    mkdir -p "$FFMPEG_DIR"
    
    # Download FFmpeg for macOS (arm64/x86_64)
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/7z"
    else
        FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/7z"
    fi
    
    # Try to download FFmpeg
    if command -v curl &> /dev/null; then
        echo "Note: FFmpeg download is optional. You can skip this step."
        echo "If you have FFmpeg installed system-wide, it will be used automatically."
        echo ""
        read -p "Download FFmpeg? (y/N): " DOWNLOAD_FFMPEG
        
        if [ "$DOWNLOAD_FFMPEG" = "y" ] || [ "$DOWNLOAD_FFMPEG" = "Y" ]; then
            echo "Please download FFmpeg manually from: https://evermeet.cx/ffmpeg/"
            echo "And place the 'ffmpeg' and 'ffprobe' binaries in:"
            echo "  $FFMPEG_DIR"
        fi
    fi
fi

# Create launch script
LAUNCH_SCRIPT="$PROJECT_DIR/launch_medialake.sh"
cat > "$LAUNCH_SCRIPT" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/venv/bin/activate"
python -m medialake_resolve "$@"
EOF
chmod +x "$LAUNCH_SCRIPT"

# Create macOS app bundle (optional)
read -p "Create macOS application bundle? (y/N): " CREATE_APP

if [ "$CREATE_APP" = "y" ] || [ "$CREATE_APP" = "Y" ]; then
    APP_NAME="Media Lake for Resolve"
    APP_DIR="$HOME/Applications/$APP_NAME.app"
    
    echo "Creating application bundle at: $APP_DIR"
    
    mkdir -p "$APP_DIR/Contents/MacOS"
    mkdir -p "$APP_DIR/Contents/Resources"
    
    # Create Info.plist
    cat > "$APP_DIR/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>MediaLakeResolve</string>
    <key>CFBundleIdentifier</key>
    <string>com.medialake.resolve-plugin</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF
    
    # Create launcher script
    cat > "$APP_DIR/Contents/MacOS/MediaLakeResolve" << EOF
#!/bin/bash
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"
python -m medialake_resolve "\$@"
EOF
    chmod +x "$APP_DIR/Contents/MacOS/MediaLakeResolve"
    
    echo "✓ Application bundle created"
fi

echo ""
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "To run the plugin:"
echo "  $LAUNCH_SCRIPT"
echo ""
echo "Or from the command line:"
echo "  source $VENV_DIR/bin/activate"
echo "  medialake-resolve"
echo ""

if [ "$CREATE_APP" = "y" ] || [ "$CREATE_APP" = "Y" ]; then
    echo "You can also find 'Media Lake for Resolve' in ~/Applications"
    echo ""
fi

echo "Make sure DaVinci Resolve is running before launching the plugin."
