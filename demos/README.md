# Demos

This directory contains demo configurations and recording tools for textual-cmdorc.

## Directory Structure

```
demos/
├── configs/              # Multi-config demo
│   ├── cmdorc-tui.toml  # Named configs definition
│   ├── dev.toml         # Lint → Format → Test (with file watcher)
│   ├── build.toml       # Clean → Compile → Package → Verify
│   ├── deploy.toml      # Pre-flight → Staging → Smoke Test → Production
│   └── utils.toml       # Status, Logs, Health Check, Disk Usage
├── recordings/           # Demo GIFs and videos
├── scripts/              # Recording scripts
├── demo.toml             # Simple single-config demo
└── README.md
```

## Quick Start

### Single-Config Demo

```bash
cd demos
pdm run cmdorc-tui --config demo.toml
```

### Multi-Config Demo

```bash
cd demos/configs
pdm run cmdorc-tui
```

This loads `cmdorc-tui.toml` automatically and provides these named configs:

| Config | Description | Files |
|--------|-------------|-------|
| **Development** | Fast feedback loop with file watcher | dev.toml + utils.toml |
| **Full Pipeline** | Complete CI/CD workflow | dev + build + deploy |
| **Build** | Release artifact creation | build.toml + utils.toml |
| **Deploy** | Deployment operations | deploy.toml + utils.toml |
| **Quick Check** | Just lint & format | dev.toml only |
| **Utilities** | Monitoring tools | utils.toml only |

Use **Ctrl+K** or the dropdown to switch between configs.

### Start with Specific Config

```bash
pdm run cmdorc-tui --config "Full Pipeline"
pdm run cmdorc-tui --config "Deploy"
```

## Command Chains

### Development (dev.toml)
```
Lint [1] → Format [2] → Test [3]
Type Check [4] (manual)
```
File watcher triggers Lint automatically on `.py` file changes.

### Build (build.toml)
```
Clean [c] → Compile [1] → Package [2] → Verify [3]
```

### Deploy (deploy.toml)
```
Pre-flight Check [p] → Deploy Staging [s] → Smoke Test [t] → Deploy Production [d]
Rollback [r] (manual)
```

### Utilities (utils.toml)
```
Status [s], Logs [l], Health Check [h], Disk Usage [d]
```

## Recording Demos

### Problem

On WSL with Windows mounts (P9 filesystem), Python imports can be very slow (~25s). This makes demo recording impractical.

### Solution

Record from a WSL native filesystem location where imports are fast (<1s).

### One-time Setup

```bash
./demos/scripts/setup-demo-env.sh
```

This copies the project to `~/textual-cmdorc-demo` and installs dependencies.

### Recording

```bash
./demos/scripts/record-demo.sh
```

This runs VHS in the fast demo environment and copies outputs back.

### Manual Recording

```bash
cd ~/textual-cmdorc-demo
vhs demos/scripts/quick-start.tape
cp demos/recordings/quick-start.* /workspaces/textual-cmdorc/demos/recordings/
```

## Demo Files

### Configs
- **demo.toml** - Simple single-file demo with Lint → Format → Build → Test → Deploy chain
- **configs/** - Multi-config demo showcasing config switching

### Scripts
- **scripts/quick-start.tape** - VHS tape for main demo recording
- **scripts/setup-demo-env.sh** - Sets up fast recording environment
- **scripts/record-demo.sh** - Convenience script for recording
- **scripts/build-gif.sh** - Converts recordings to optimized GIFs

### Recordings
- **recordings/quick-start.gif** - Main demo GIF
- **recordings/quick-start.mp4** - Main demo video

## Requirements

- VHS installed: https://github.com/charmbracelet/vhs
- pdm for dependency management
