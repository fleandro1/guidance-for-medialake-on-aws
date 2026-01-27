#!/bin/bash
#
# Media Lake - DaVinci Resolve Plugin Uninstaller
#
# This script removes the Media Lake plugin from DaVinci Resolve's
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
echo "║          AWS Media Lake - DaVinci Resolve Plugin Uninstaller      ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

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
    # Linux
    RESOLVE_PLUGINS_DIR="/opt/resolve/Workflow Integration Plugins"
    OS_NAME="Linux"
else
    echo -e "${RED}Error: Unsupported operating system: $OSTYPE${NC}"
    exit 1
fi

PLUGIN_TARGET_FILE="$RESOLVE_PLUGINS_DIR/MediaLake.py"

echo -e "Operating System: ${GREEN}$OS_NAME${NC}"
echo -e "Plugin File: ${GREEN}$PLUGIN_TARGET_FILE${NC}"
echo ""

# Check if plugin is installed
if [[ ! -f "$PLUGIN_TARGET_FILE" ]]; then
    echo -e "${YELLOW}Media Lake plugin is not installed.${NC}"
    exit 0
fi

# Confirm uninstallation
echo -e "${YELLOW}This will remove the Media Lake plugin from DaVinci Resolve.${NC}"
read -p "Are you sure you want to uninstall? [y/N]: " CONFIRM

if [[ "$CONFIRM" != "y" ]] && [[ "$CONFIRM" != "Y" ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

# Remove the plugin
echo -e "${BLUE}Removing Media Lake plugin...${NC}"
sudo rm -f "$PLUGIN_TARGET_FILE"

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Uninstallation Complete!                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "The Media Lake plugin has been removed from DaVinci Resolve."
echo "Please restart DaVinci Resolve for changes to take effect."
echo ""
