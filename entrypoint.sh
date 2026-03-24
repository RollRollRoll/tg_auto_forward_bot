#!/bin/sh
echo "Upgrading yt-dlp to latest version..."
pip install --no-cache-dir -U yt-dlp 2>&1 | tail -1
exec "$@"
