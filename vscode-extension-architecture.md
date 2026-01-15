# VS Code Extension Architecture

> Future reference document for building a VS Code extension with similar functionality to textual-cmdorc.

## Overview

This document outlines an architecture for a VS Code extension that reuses the Python `cmdorc_frontend` backend while providing a native VS Code UI. The pattern uses a Python backend server communicating with a TypeScript extension via JSON-RPC over stdio.

## Key Decisions

### Why Python Backend?

Using a Python backend is a **standard, accepted practice** for VS Code extensions, especially for Python tooling:

- **Python extension (Microsoft)** - Uses Python for debugging, environment detection, testing
- **Pylint, Flake8, Black, Ruff extensions** - Spawn Python processes
- **Jupyter extension** - Communicates with Python kernels
- **LSP-based extensions** - Pylsp, Jedi-LSP run Python servers

**Pros:**
- Leverage existing Python libraries (cmdorc, watchdog, cmdorc_frontend)
- Single source of truth for orchestration logic
- Python ecosystem expected for Python tooling

**Cons:**
- Requires Python installed (or bundle it)
- Startup latency (~100-500ms to spawn Python)
- Dependency management considerations

### Embedding Considerations

VS Code's extension model differs from Textual's composable widgets:

- Extensions can expose APIs via `extension.exports` for other extensions
- Webview providers can be contributed and displayed in various locations
- True "widget nesting" like React components isn't native to VS Code

**Recommendation:** Build the core as an npm package with React/Preact webview components. Both standalone and "parent" extensions can import and render the same components.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VS Code Extension (TypeScript)                │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │
│  │ Extension    │  │ Webview UI   │  │ CmdorcClient               │ │
│  │ Entry Point  │  │ (React/Svelte│  │ - connect()                │ │
│  │              │  │  or plain)   │  │ - runCommand(name)         │ │
│  │ - activate() │  │              │  │ - cancelCommand(name)      │ │
│  │ - spawn      │  │ - Command    │  │ - getCommands()            │ │
│  │   backend    │  │   list       │  │ - onStateChange(callback)  │ │
│  │              │  │ - Status     │  │                            │ │
│  └──────┬───────┘  │ - Controls   │  └─────────────┬──────────────┘ │
│         │          └──────────────┘                │                │
└─────────┼──────────────────────────────────────────┼────────────────┘
          │                                          │
          │  spawns                                  │ JSON-RPC over stdio
          │                                          │
┌─────────┼──────────────────────────────────────────┼────────────────┐
│         ▼                                          ▼                │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    cmdorc-server (Python)                       ││
│  │                                                                 ││
│  │  ┌─────────────────┐    ┌─────────────────────────────────────┐ ││
│  │  │ JSON-RPC Handler│    │ cmdorc_frontend                     │ ││
│  │  │                 │    │                                     │ ││
│  │  │ Methods:        │───▶│ OrchestratorAdapter                 │ ││
│  │  │ - run_command   │    │   └─► cmdorc.CommandOrchestrator    │ ││
│  │  │ - cancel_command│    │                                     │ ││
│  │  │ - get_commands  │    │ FileWatcherManager                  │ ││
│  │  │ - reload_config │    │   └─► watchdog observers            │ ││
│  │  │                 │    │                                     │ ││
│  │  │ Notifications:  │◀───│ Callbacks:                          │ ││
│  │  │ - state_changed │    │ - on_command_started                │ ││
│  │  │ - output_line   │    │ - on_command_success/failed         │ ││
│  │  │ - watcher_event │    │ - on_output                         │ ││
│  │  └─────────────────┘    └─────────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────┘│
│                         Python Backend                               │
└─────────────────────────────────────────────────────────────────────┘
```

## Package Structure

```
cmdorc-vscode/
├── extension/                    # TypeScript (npm package)
│   ├── src/
│   │   ├── extension.ts          # activate(), spawn backend
│   │   ├── client.ts             # CmdorcClient - JSON-RPC wrapper
│   │   ├── webview/
│   │   │   ├── App.tsx           # UI components
│   │   │   └── CommandList.tsx
│   │   └── types.ts              # Shared types
│   ├── package.json
│   └── tsconfig.json
│
├── server/                       # Python (PyPI package)
│   ├── cmdorc_server/
│   │   ├── __main__.py           # Entry point: python -m cmdorc_server
│   │   ├── server.py             # JSON-RPC server loop
│   │   ├── handlers.py           # Method handlers
│   │   └── protocol.py           # Message types
│   └── pyproject.toml
│
└── cmdorc_frontend/              # Python (separate PyPI package)
    ├── orchestrator_adapter.py   # Extracted from textual-cmdorc
    ├── file_watcher.py
    ├── config.py
    └── models.py
```

## JSON-RPC Protocol

### Requests (extension → server)

```typescript
// extension/src/types.ts

interface RunCommandRequest {
  method: "run_command";
  params: { name: string };
}

interface CancelCommandRequest {
  method: "cancel_command";
  params: { name: string };
}

interface GetCommandsRequest {
  method: "get_commands";
  params: {};
}

interface ReloadConfigRequest {
  method: "reload_config";
  params: { config_path?: string };
}
```

### Notifications (server → extension)

```typescript
interface StateChangedNotification {
  method: "state_changed";
  params: {
    command: string;
    state: "idle" | "running" | "success" | "failed" | "cancelled";
    duration_ms?: number;
    exit_code?: number;
  };
}

interface OutputLineNotification {
  method: "output_line";
  params: {
    command: string;
    line: string;
    stream: "stdout" | "stderr";
  };
}
```

## Implementation Sketches

### Python Server

```python
# server/cmdorc_server/server.py

import asyncio
import json
import sys
from cmdorc_frontend import OrchestratorAdapter

class CmdorcServer:
    def __init__(self, config_path: str):
        self.adapter = OrchestratorAdapter(config_path)
        self.loop = asyncio.get_event_loop()

        # Wire callbacks to send notifications
        self.adapter.on_command_started = self._notify_started
        self.adapter.on_command_success = self._notify_success
        self.adapter.on_command_failed = self._notify_failed

    async def handle_request(self, request: dict) -> dict:
        method = request["method"]
        params = request.get("params", {})

        if method == "run_command":
            await self.adapter.run_command(params["name"])
            return {"result": "ok"}

        elif method == "cancel_command":
            await self.adapter.cancel_command(params["name"])
            return {"result": "ok"}

        elif method == "get_commands":
            commands = self.adapter.get_command_list()
            return {"result": [cmd.to_dict() for cmd in commands]}

        elif method == "reload_config":
            self.adapter.reload_config(params.get("config_path"))
            return {"result": "ok"}

    def _notify_started(self, name: str, handle):
        self._send_notification("state_changed", {
            "command": name,
            "state": "running"
        })

    def _send_notification(self, method: str, params: dict):
        msg = json.dumps({"method": method, "params": params})
        # LSP-style content-length header
        sys.stdout.write(f"Content-Length: {len(msg)}\r\n\r\n{msg}")
        sys.stdout.flush()

    async def run(self):
        self.adapter.attach(self.loop)
        # Read JSON-RPC from stdin, write to stdout
        reader = asyncio.StreamReader()
        await self.loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader),
            sys.stdin
        )
        while True:
            request = await self._read_message(reader)
            response = await self.handle_request(request)
            self._send_response(request["id"], response)
```

### TypeScript Client

```typescript
// extension/src/client.ts

import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";

export class CmdorcClient extends EventEmitter {
  private process: ChildProcess | null = null;
  private requestId = 0;
  private pending = new Map<number, (response: any) => void>();

  async connect(pythonPath: string, configPath: string): Promise<void> {
    this.process = spawn(pythonPath, ["-m", "cmdorc_server", configPath]);

    this.process.stdout!.on("data", (data) => {
      const messages = this.parseMessages(data);
      for (const msg of messages) {
        if (msg.id) {
          // Response to our request
          this.pending.get(msg.id)?.(msg.result);
          this.pending.delete(msg.id);
        } else {
          // Notification from server
          this.emit(msg.method, msg.params);
        }
      }
    });
  }

  async runCommand(name: string): Promise<void> {
    await this.request("run_command", { name });
  }

  async cancelCommand(name: string): Promise<void> {
    await this.request("cancel_command", { name });
  }

  async getCommands(): Promise<Command[]> {
    return this.request("get_commands", {});
  }

  private request(method: string, params: object): Promise<any> {
    return new Promise((resolve) => {
      const id = ++this.requestId;
      this.pending.set(id, resolve);
      const msg = JSON.stringify({ jsonrpc: "2.0", id, method, params });
      this.process!.stdin!.write(`Content-Length: ${msg.length}\r\n\r\n${msg}`);
    });
  }
}
```

### Extension Entry Point

```typescript
// extension/src/extension.ts

import * as vscode from "vscode";
import { CmdorcClient } from "./client";
import { CmdorcViewProvider } from "./webview/provider";

let client: CmdorcClient;

export async function activate(context: vscode.ExtensionContext) {
  client = new CmdorcClient();

  // Find Python and config
  const pythonPath = await getPythonPath();
  const configPath = findConfigFile();

  // Start backend
  await client.connect(pythonPath, configPath);

  // Register webview provider
  const provider = new CmdorcViewProvider(context, client);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("cmdorc.commandList", provider)
  );

  // Listen for state changes, forward to webview
  client.on("state_changed", (params) => {
    provider.updateState(params);
  });
}

export function deactivate() {
  client?.disconnect();
}
```

### Embedding Support

For embedding into another extension:

```typescript
// Expose API for other extensions
export function activate(context: vscode.ExtensionContext) {
  // ... setup ...

  // Export API for other extensions to consume
  return {
    getClient: () => client,
    createWebviewPanel: (viewColumn: vscode.ViewColumn) => {
      return vscode.window.createWebviewPanel(
        "cmdorc",
        "Command Orchestrator",
        viewColumn,
        { enableScripts: true }
      );
    }
  };
}

// Other extension uses it:
const cmdorcExt = vscode.extensions.getExtension("yourname.cmdorc-vscode");
const api = await cmdorcExt.activate();
const panel = api.createWebviewPanel(vscode.ViewColumn.Three);
```

## Code Reuse from textual-cmdorc

### Direct Reuse (extract to cmdorc_frontend package)

| File | Notes |
|------|-------|
| `orchestrator_adapter.py` | Core backend, no changes needed |
| `file_watcher.py` | Watchdog integration |
| `config.py` | TOML parsing |
| `models.py` | Dataclasses, add `to_dict()` methods for JSON serialization |
| `multiconfig.py` | Multi-config support |

### Rewrite for TypeScript/React

| File | Notes |
|------|-------|
| `cmdorc_app.py` | Textual-specific, rewrite as React/Svelte webview |
| `tooltip_builders.py` | Logic reusable, rewrite in TS or expose via RPC |
| `formatting.py` | Simple utils, likely rewrite in TS |

## Communication Patterns Reference

| Pattern | Use Case |
|---------|----------|
| **Language Server Protocol (LSP)** | Long-running server, JSON-RPC over stdio/TCP |
| **Subprocess per task** | Spawn Python, capture stdout, parse results |
| **Long-running daemon** | Custom protocol over stdio/socket |

This architecture uses the LSP-style pattern (JSON-RPC over stdio) for real-time bidirectional communication.

## References

- [VS Code Extension API](https://code.visualstudio.com/api)
- [VS Code Webview API](https://code.visualstudio.com/api/extension-guides/webview)
- [Language Server Protocol](https://microsoft.github.io/language-server-protocol/)
- [Ruff VS Code Extension](https://github.com/astral-sh/ruff-vscode) - Good reference for Python backend pattern
