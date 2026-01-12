#!/bin/bash
# Convert cast file to GIF using agg
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAST_FILE="$SCRIPT_DIR/quick-start.cast"
GIF_FILE="$SCRIPT_DIR/quick-start.gif"

# Configurable settings
FONT_SIZE="${FONT_SIZE:-20}"  # Default 20, override with: FONT_SIZE=24 ./build-gif.sh

if [ ! -f "$CAST_FILE" ]; then
    echo "❌ Cast file not found: $CAST_FILE"
    exit 1
fi

if ! command -v agg &> /dev/null; then
    echo "❌ agg not found. Install with: cargo install agg"
    exit 1
fi

echo "🎬 Converting $CAST_FILE to GIF (font size: $FONT_SIZE)..."
agg "$CAST_FILE" "$GIF_FILE" \
    --font-family "DejaVu Sans Mono" \
    --font-size "$FONT_SIZE" \
    --theme dracula

echo "✅ Created: $GIF_FILE"
ls -lh "$GIF_FILE"
