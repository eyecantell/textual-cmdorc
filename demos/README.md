# Demo Recording

This directory contains VHS tape files for recording demos and the scripts to set up a fast recording environment.

## Problem

On WSL with Windows mounts (P9 filesystem), Python imports can be very slow (~25s for textual-cmdorc). This makes demo recording impractical.

## Solution

Record from a WSL native filesystem location where imports are fast (<1s).

## Usage

### One-time Setup

```bash
# Setup demo environment in WSL native filesystem (~/.../textual-cmdorc-demo)
./demos/setup-demo-env.sh
```

This copies the project to `~/textual-cmdorc-demo` and installs dependencies.

### Recording Demos

```bash
# Record and copy outputs back
./demos/record-demo.sh
```

This will:
1. Run VHS in the fast demo environment
2. Copy the generated GIF/MP4 back to this directory

### Manual Recording

If you want to customize:

```bash
cd ~/textual-cmdorc-demo
vhs demos/quick-start.tape
# Copy outputs back manually
cp demos/quick-start.* /workspaces/textual-cmdorc/demos/
```

## Demo Files

- **quick-start.tape** - Main demo showing command chaining, keyboard shortcuts, and command details
- **setup-demo-env.sh** - Setup script for creating fast recording environment
- **record-demo.sh** - Convenience script for recording and copying outputs back

## Requirements

- VHS installed: https://github.com/charmbracelet/vhs
- pdm for dependency management
