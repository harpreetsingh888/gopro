#!/bin/bash

# GoPro Cloud - List Media (test credentials)
# Usage: ./list.sh

if [ -z "$GOPRO_AUTH_TOKEN" ] || [ -z "$GOPRO_USER_ID" ]; then
    echo "Set credentials first:"
    echo "  export GOPRO_AUTH_TOKEN='your_token'"
    echo "  export GOPRO_USER_ID='your_user_id'"
    exit 1
fi

echo "Testing credentials and listing first page of media..."

docker run --rm \
    -e AUTH_TOKEN="$GOPRO_AUTH_TOKEN" \
    -e USER_ID="$GOPRO_USER_ID" \
    -e ACTION="list" \
    -e START_PAGE="1" \
    -e PAGES="1" \
    -e PER_PAGE="10" \
    -e DOWNLOAD_PATH="/app/download" \
    -e PROGRESS_MODE="inline" \
    itsankoff/gopro
