"""Example: Embedding CmdorcWidget in a 3-column layout.

This demonstrates how to use CmdorcWidget as a composable component
within a larger Textual application with a 3-column layout.

Usage:
    python examples/embedding_3column.py
"""

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Label, Static

from textual_cmdorc import CmdorcWidget


class LeftPanel(Static):
    """Left sidebar panel."""

    def compose(self) -> ComposeResult:
        yield Label("📁 File Explorer", id="left-header")
        yield Static(
            """
[dim]project/[/dim]
  ├── src/
  │   ├── main.py
  │   └── utils.py
  ├── tests/
  │   └── test_main.py
  ├── config.toml
  └── README.md
            """,
            id="file-tree",
        )


class RightPanel(Static):
    """Right sidebar panel."""

    def compose(self) -> ComposeResult:
        yield Label("📊 Statistics", id="right-header")
        yield Static(
            """
[b]Build Status:[/b]
  ✅ Lint: Passed
  ✅ Tests: 25/25
  ⏳ Build: Running...

[b]Coverage:[/b]
  📈 85% overall
  📉 utils.py: 62%

[b]Last Commit:[/b]
  🕐 2 hours ago
  👤 developer
            """,
            id="stats",
        )


class ThreeColumnApp(App):
    """Example app with CmdorcWidget in center column.

    Layout:
    ┌─────────────────────────────────────────┐
    │ Header                                  │
    ├─────────┬───────────────┬───────────────┤
    │  Left   │   CmdorcWidget │    Right      │
    │  Panel  │   (Commands)   │    Panel      │
    │         │                │               │
    └─────────┴───────────────┴───────────────┘
    │ Footer                                  │
    └─────────────────────────────────────────┘
    """

    TITLE = "3-Column Layout with CmdorcWidget"

    CSS = """
    Screen {
        layout: vertical;
    }

    Horizontal {
        height: 1fr;
    }

    LeftPanel {
        width: 25%;
        border-right: solid $accent;
        padding: 1;
    }

    #left-header {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #file-tree {
        color: $text-muted;
    }

    CmdorcWidget {
        width: 50%;
    }

    RightPanel {
        width: 25%;
        border-left: solid $accent;
        padding: 1;
    }

    #right-header {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #stats {
        color: $text-muted;
    }
    """

    def __init__(self, config_path: str = "config.toml"):
        super().__init__()
        self.config_path = config_path

    def compose(self) -> ComposeResult:
        """Compose the 3-column layout."""
        yield Header()

        with Horizontal():
            yield LeftPanel()
            yield CmdorcWidget(self.config_path)
            yield RightPanel()

        yield Footer()


def main():
    """Run the 3-column example app."""
    import sys
    from pathlib import Path

    # Use config.toml from repo root if available
    config_path = Path("config.toml")
    if not config_path.exists():
        print("❌ config.toml not found. Please run from repo root or provide a config file.")
        sys.exit(1)

    app = ThreeColumnApp(config_path=str(config_path))
    app.run()


if __name__ == "__main__":
    main()
