#!/bin/bash
#
# Media Lake - DaVinci Resolve Plugin Installer
#
# This script installs the Media Lake plugin into DaVinci Resolve's
# Workflow Integration Plugins directory.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║           AWS Media Lake - DaVinci Resolve Plugin Installer       ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Determine the plugin source directory (where this script is located)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Determine OS and set paths
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    RESOLVE_PLUGINS_DIR="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins"
    OS_NAME="macOS"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows
    RESOLVE_PLUGINS_DIR="$PROGRAMDATA/Blackmagic Design/DaVinci Resolve/Support/Workflow Integration Plugins"
    OS_NAME="Windows"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux (Note: Workflow Integration Plugins may not be supported on Linux)
    RESOLVE_PLUGINS_DIR="/opt/resolve/Workflow Integration Plugins"
    OS_NAME="Linux"
    echo -e "${YELLOW}Warning: Workflow Integration Plugins may not be fully supported on Linux.${NC}"
else
    echo -e "${RED}Error: Unsupported operating system: $OSTYPE${NC}"
    exit 1
fi

echo -e "Operating System: ${GREEN}$OS_NAME${NC}"
echo -e "Source Directory: ${GREEN}$SCRIPT_DIR${NC}"
echo -e "Target Directory: ${GREEN}$RESOLVE_PLUGINS_DIR${NC}"
echo ""

# Check if source files exist
if [[ ! -f "$SCRIPT_DIR/MediaLake.py" ]]; then
    echo -e "${RED}Error: MediaLake.py not found in $SCRIPT_DIR${NC}"
    exit 1
fi

if [[ ! -d "$SCRIPT_DIR/medialake_resolve" ]]; then
    echo -e "${RED}Error: medialake_resolve directory not found in $SCRIPT_DIR${NC}"
    exit 1
fi

# Create plugins directory if it doesn't exist
if [[ ! -d "$RESOLVE_PLUGINS_DIR" ]]; then
    echo -e "${YELLOW}Creating plugins directory...${NC}"
    sudo mkdir -p "$RESOLVE_PLUGINS_DIR"
fi

# Update the MEDIALAKE_PLUGIN_DIR path in MediaLake.py
echo -e "${BLUE}Configuring plugin path...${NC}"
ESCAPED_PATH=$(echo "$SCRIPT_DIR" | sed 's/[\/&]/\\&/g')
sed -i.bak "s|^MEDIALAKE_PLUGIN_DIR = .*|MEDIALAKE_PLUGIN_DIR = \"$SCRIPT_DIR\"|" "$SCRIPT_DIR/MediaLake.py"
rm -f "$SCRIPT_DIR/MediaLake.py.bak"

# Remove existing installation if present
if [[ -f "$RESOLVE_PLUGINS_DIR/MediaLake.py" ]]; then
    echo -e "${YELLOW}Removing existing installation...${NC}"
    sudo rm -f "$RESOLVE_PLUGINS_DIR/MediaLake.py"
fi

# Copy the script to the plugins directory
# Note: For Python Workflow Integration Scripts, only the .py file goes in the plugins dir
echo -e "${BLUE}Installing MediaLake.py to Resolve plugins directory...${NC}"
sudo cp "$SCRIPT_DIR/MediaLake.py" "$RESOLVE_PLUGINS_DIR/"
echo -e "${GREEN}✓ MediaLake.py installed${NC}"

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Installation Complete!                         ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "To use Media Lake in DaVinci Resolve:"
echo ""
echo "  1. Restart DaVinci Resolve (if running)"
echo "  2. Go to: Workspace → Workflow Integrations → MediaLake"
echo "  3. Click 'Open Media Lake Browser' to launch the application"
echo ""
echo -e "${YELLOW}Note: The medialake_resolve package remains in:${NC}"
echo -e "${YELLOW}      $SCRIPT_DIR${NC}"
echo ""
echo -e "${YELLOW}Make sure Python 3 with PySide6 is installed.${NC}"
echo -e "${YELLOW}You can install PySide6 with: pip install PySide6${NC}"
echo ""
