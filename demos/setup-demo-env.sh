#!/bin/bash
# Setup fast demo recording environment in WSL native filesystem
# This avoids the 25s import time on Windows/WSL P9 mounts

set -e

DEMO_DIR="$HOME/textual-cmdorc-demo"
SOURCE_DIR="/workspaces/textual-cmdorc"

echo "🚀 Setting up demo recording environment..."

# Create demo directory in WSL native filesystem
echo "📁 Creating demo directory at $DEMO_DIR"
mkdir -p "$DEMO_DIR"

# Copy only necessary files (not __pycache__, .venv, etc.)
echo "📋 Copying project files..."
cp -r "$SOURCE_DIR"/* "$DEMO_DIR/"

# Clean up unwanted directories
echo "🧹 Cleaning up..."
rm -rf "$DEMO_DIR/__pycache__" \
       "$DEMO_DIR/.venv" \
       "$DEMO_DIR/venv" \
       "$DEMO_DIR/.git" \
       "$DEMO_DIR/.pytest_cache" \
       "$DEMO_DIR/htmlcov" \
       "$DEMO_DIR/.coverage" \
       "$DEMO_DIR/dist" \
       "$DEMO_DIR/.pdm-build" \
       "$DEMO_DIR/.cmdorc" \
       2>/dev/null || true
find "$DEMO_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$DEMO_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

cd "$DEMO_DIR"

# Install textual-cmdorc with pip (like a real user would)
echo "📦 Installing textual-cmdorc..."
pip install --quiet .

# Verify installation
echo ""
echo "⚡ Verifying installation..."
cmdorc-tui --version

echo ""
echo "✅ Demo environment ready at: $DEMO_DIR"
echo ""
echo "📹 To record demo:"
echo "   cd $DEMO_DIR"
echo "   vhs demos/quick-start.tape"
echo ""
echo "📦 To copy outputs back:"
echo "   cp $DEMO_DIR/demos/quick-start.* $SOURCE_DIR/demos/"
