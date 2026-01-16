#!/bin/bash
# Record demo using asciinema + agg
# This captures your actual terminal, so icons render correctly

set -e

DEMO_DIR="$HOME/textual-cmdorc-demo"
SOURCE_DIR="/workspaces/textual-cmdorc"
CAST_FILE="$DEMO_DIR/demos/recordings/quick-start.cast"
GIF_FILE="$DEMO_DIR/demos/recordings/quick-start.gif"

if [ ! -d "$DEMO_DIR" ]; then
    echo "❌ Demo environment not found. Run setup-demo-env.sh first"
    exit 1
fi

cd "$DEMO_DIR"

echo "📹 Recording demo with asciinema..."
echo ""
echo "=== DEMO SCRIPT ==="
echo "1. Type: cmdorc-tui --config demos/demo.toml"
echo "2. Wait for TUI to load"
echo "3. Press '1' to trigger Lint (starts chain: Lint → Format → Build → Test → Deploy)"
echo "4. Wait for chain to complete (~5s)"
echo "5. Press '6' for Status"
echo "6. Press '7' for Logs"
echo "7. Press 'q' to quit"
echo "8. Type 'exit' to end recording"
echo "==================="
echo ""
echo "Press Enter to start recording..."
read _

# Remove the old cast and gif files if they exist
rm -f "$CAST_FILE" "$GIF_FILE"

# Record the session (start in demo directory so file watchers work)
asciinema rec "$CAST_FILE" --cols 80 --rows 24 --command "bash -l -c 'cd $DEMO_DIR && exec bash'"

echo ""
echo "🎬 Converting to GIF..."
agg "$CAST_FILE" "$GIF_FILE" \
    --font-family "DejaVu Sans Mono" \
    --font-size 20 \
    --theme dracula

echo ""
echo "📦 Copying outputs back to project..."
cp "$GIF_FILE" "$SOURCE_DIR/demos/recordings/" 2>/dev/null || echo "   (no .gif output)"
cp "$CAST_FILE" "$SOURCE_DIR/demos/recordings/" 2>/dev/null || echo "   (no .cast output)"

echo ""
echo "✅ Demo recorded!"
ls -lh "$SOURCE_DIR/demos/recordings/quick-start."* 2>/dev/null || true
