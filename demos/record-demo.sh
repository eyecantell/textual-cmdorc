#!/bin/bash
# Record demo and copy outputs back to project

set -e

DEMO_DIR="$HOME/textual-cmdorc-demo"
SOURCE_DIR="/workspaces/textual-cmdorc"

if [ ! -d "$DEMO_DIR" ]; then
    echo "❌ Demo environment not found. Run setup-demo-env.sh first"
    exit 1
fi

cd "$DEMO_DIR"

echo "📹 Recording demo..."
vhs demos/quick-start.tape

echo ""
echo "📦 Copying outputs back to project..."
cp demos/quick-start.gif "$SOURCE_DIR/demos/" 2>/dev/null || echo "   (no .gif output)"
cp demos/quick-start.mp4 "$SOURCE_DIR/demos/" 2>/dev/null || echo "   (no .mp4 output)"

echo ""
echo "✅ Demo recorded and copied to: $SOURCE_DIR/demos/"
ls -lh "$SOURCE_DIR/demos/quick-start."* 2>/dev/null || true
