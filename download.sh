#!/bin/bash

# GoPro Cloud Downloader - Enhanced Edition
# Downloads media into YYYY/Mon/DD folder structure with rich metadata
#
# Usage:
#   ./download.sh [download_path]           - Download all media
#   ./download.sh --retry ID1,ID2,ID3       - Retry specific media IDs
#   ./download.sh --retry-failed            - Retry all failed from retry_ids.txt
#
# Examples:
#   ./download.sh /Volumes/H4TB/GoPro
#   ./download.sh --retry P3zD0D8JyW4Og,X7yK2L9MnQ3Rp
#   ./download.sh --retry-failed

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env file if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Handle retry flags
if [ "$1" = "--retry" ] && [ -n "$2" ]; then
    export RETRY_IDS="$2"
    echo "🔄 Retry mode: specific IDs"
    shift 2
elif [ "$1" = "--retry-failed" ]; then
    if [ -f "$SCRIPT_DIR/downloads/retry_ids.txt" ]; then
        RETRY_IDS=$(grep -v '^#' "$SCRIPT_DIR/downloads/retry_ids.txt" | tr -d '\n')
        export RETRY_IDS
        echo "🔄 Retry mode: loading IDs from retry_ids.txt"
    else
        echo "❌ No retry_ids.txt found. Run a full download first."
        exit 1
    fi
    shift
fi

# Check if credentials are set
if [ -z "$GOPRO_AUTH_TOKEN" ] || [ -z "$GOPRO_USER_ID" ]; then
    echo "========================================"
    echo "GoPro Cloud Downloader - By Date"
    echo "========================================"
    echo ""
    echo "Downloads media organized by date:"
    echo "  /path/to/folder/2024/Feb/26/video1.mp4"
    echo "  /path/to/folder/2024/Feb/26/video2.mp4"
    echo "  /path/to/folder/2024/Mar/01/photo1.jpg"
    echo ""
    echo "Get your credentials:"
    echo ""
    echo "1. Go to https://plus.gopro.com and log in"
    echo "2. Open DevTools (Cmd+Option+I)"
    echo "3. Go to Application → Cookies → plus.gopro.com"
    echo "4. Copy these values:"
    echo "   - gp_access_token (AUTH_TOKEN)"
    echo "   - gp_user_id (USER_ID)"
    echo ""
    echo "Then run:"
    echo "  export GOPRO_AUTH_TOKEN='your_token_here'"
    echo "  export GOPRO_USER_ID='your_user_id_here'"
    echo "  ./download.sh"
    echo ""
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is required. Please install it first."
    exit 1
fi

# Install dependencies if needed
if ! python3 -c "import requests" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Get download path
echo "========================================"
echo "GoPro Cloud Downloader - By Date"
echo "========================================"
echo ""

# Check if path was provided as argument
if [ -n "$1" ]; then
    DOWNLOAD_PATH="$1"
else
    # List available volumes (external drives)
    echo "📁 Available volumes:"
    ls -1 /Volumes/ 2>/dev/null | while read vol; do
        if [ "$vol" != "Macintosh HD" ]; then
            echo "   /Volumes/$vol"
        fi
    done
    echo ""
    echo "Enter the absolute path to download folder"
    echo "(e.g., /Volumes/MyHDD/GoPro or press Enter for ./downloads):"
    echo ""
    read -p "📂 Download path: " DOWNLOAD_PATH
fi

# Default to local downloads folder if empty
if [ -z "$DOWNLOAD_PATH" ]; then
    DOWNLOAD_PATH="$SCRIPT_DIR/downloads"
fi

# Expand ~ if used
DOWNLOAD_PATH="${DOWNLOAD_PATH/#\~/$HOME}"

# Validate path
if [[ ! "$DOWNLOAD_PATH" = /* ]]; then
    echo "❌ Please provide an absolute path (starting with /)"
    exit 1
fi

# Check if parent directory exists (for external drives)
PARENT_DIR="$(dirname "$DOWNLOAD_PATH")"
if [ ! -d "$PARENT_DIR" ]; then
    echo "❌ Parent directory does not exist: $PARENT_DIR"
    echo "   Make sure your external drive is connected."
    exit 1
fi

# Create download directory if it doesn't exist
mkdir -p "$DOWNLOAD_PATH"
if [ $? -ne 0 ]; then
    echo "❌ Failed to create directory: $DOWNLOAD_PATH"
    exit 1
fi

echo ""
echo "✅ Download location: $DOWNLOAD_PATH"
echo ""

# Run the downloader
export DOWNLOAD_PATH
python3 gopro_downloader.py
