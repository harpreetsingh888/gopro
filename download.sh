#!/bin/bash
# GoPro Cloud Downloader - Shell wrapper
# All logic is now in downloader.py
#
# Usage:
#   ./download.sh                        # Interactive
#   ./download.sh /path/to/folder        # Direct path
#   ./download.sh --date 2024-03-12      # Specific date
#   ./download.sh --retry ID1,ID2        # Retry specific IDs
#   ./download.sh --retry-failed         # Retry from retry_ids.txt
#   ./download.sh --help                 # Show help

cd "$(dirname "$0")"
python3 downloader.py "$@"
