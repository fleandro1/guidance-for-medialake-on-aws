#!/bin/bash

# Install script for Media Lake DaVinci Resolve Plugin on Linux

set -e

echo "=================================="
echo "Media Lake Resolve Plugin Installer"
echo "=================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Project directory: $PROJECT_DIR"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check Python version
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"
            return 0
        fi
    fi
    
    echo -e "${RED}✗${NC} Python 3.10 or higher is required"
    echo "  Install with your package manager:"
    echo "  - Ubuntu/Debian: sudo apt install python3.10 python3.10-venv"
    echo "  - Fedora: sudo dnf install python3.10"
    echo "  - Arch: sudo pacman -S python"
    exit 1
}

# Function to check for FFmpeg
check_ffmpeg() {
    if command -v ffmpeg &> /dev/null; then
        FFMPEG_VERSION=$(ffmpeg -version | head -n1 | awk '{print $3}')
        echo -e "${GREEN}✓${NC} FFmpeg $FFMPEG_VERSION found"
        return 0
    else
        echo -e "${YELLOW}!${NC} FFmpeg not found (optional)"
        echo "  Install with your package manager:"
        echo "  - Ubuntu/Debian: sudo apt install ffmpeg"
        echo "  - Fedora: sudo dnf install ffmpeg"
        echo "  - Arch: sudo pacman -S ffmpeg"
        return 1
    fi
}

# Function to check for pip packages required for Qt
check_qt_dependencies() {
    echo ""
    echo "Checking Qt dependencies..."
    
    # Check for common Qt dependencies on Linux
    MISSING_DEPS=()
    
    # Check for libxcb and related packages
    if ! ldconfig -p 2>/dev/null | grep -q libxcb.so; then
        MISSING_DEPS+=("libxcb1")
    fi
    
    if ! ldconfig -p 2>/dev/null | grep -q libGL.so; then
        MISSING_DEPS+=("libgl1")
    fi
    
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo -e "${YELLOW}!${NC} Some Qt dependencies may be missing"
        echo "  If you encounter issues, install:"
        echo "  - Ubuntu/Debian: sudo apt install libxcb1 libxcb-xinerama0 libxcb-cursor0 libgl1"
        echo "  - Fedora: sudo dnf install libxcb xcb-util-wm xcb-util-cursor mesa-libGL"
    else
        echo -e "${GREEN}✓${NC} Qt dependencies appear to be installed"
    fi
}

# Check Python
check_python

# Check FFmpeg
check_ffmpeg

# Check Qt dependencies
check_qt_dependencies

# Create virtual environment
echo ""
VENV_DIR="$PROJECT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists."
    read -p "Do you want to recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
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

# Create launch script
LAUNCH_SCRIPT="$PROJECT_DIR/launch_medialake.sh"
cat > "$LAUNCH_SCRIPT" << EOF
#!/bin/bash
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"
python -m medialake_resolve "\$@"
EOF
chmod +x "$LAUNCH_SCRIPT"

# Create symlink in user's local bin (if it exists)
LOCAL_BIN="$HOME/.local/bin"
if [ -d "$LOCAL_BIN" ]; then
    echo ""
    read -p "Create symlink in ~/.local/bin? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ln -sf "$LAUNCH_SCRIPT" "$LOCAL_BIN/medialake-resolve"
        echo -e "${GREEN}✓${NC} Symlink created at $LOCAL_BIN/medialake-resolve"
    fi
fi

# Create .desktop file for application menu
DESKTOP_FILE="$HOME/.local/share/applications/medialake-resolve.desktop"
echo ""
read -p "Create desktop menu entry? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mkdir -p "$HOME/.local/share/applications"
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Media Lake for Resolve
Comment=Media Lake Plugin for DaVinci Resolve
Exec=$LAUNCH_SCRIPT
Terminal=false
Categories=AudioVideo;Video;
StartupWMClass=medialake-resolve
EOF
    echo -e "${GREEN}✓${NC} Desktop entry created"
fi

echo ""
echo "=================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "=================================="
echo ""
echo "To run the plugin:"
echo "  $LAUNCH_SCRIPT"
echo ""
echo "Or if you created the symlink:"
echo "  medialake-resolve"
echo ""
echo "Or activate the virtual environment manually:"
echo "  source $VENV_DIR/bin/activate"
echo "  medialake-resolve"
echo ""
echo "Make sure DaVinci Resolve is running before launching the plugin."
