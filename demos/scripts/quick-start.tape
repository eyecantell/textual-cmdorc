# VHS tape file for textual-cmdorc quick start demo
# Run with: vhs demos/quick-start.tape

Output demos/recordings/quick-start.gif
Output demos/recordings/quick-start.mp4

# Set up the environment
Set FontFamily "Symbola, Noto Sans Mono, Noto Color Emoji, monospace"
Set FontSize 18
Set Width 1400
Set Height 700
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 40ms
Set PlaybackSpeed 0.75

# Start tmux with side-by-side panes (hidden from viewer)
Hide
Type "tmux -u new-session -d -s demo && tmux split-window -h -p 80 && tmux select-pane -t 0 && tmux -u attach"
Enter
Sleep 1s
Show

# In left pane: start cmdorc-tui
Type "cmdorc-tui --config demos/demo.toml"
Sleep 500ms
Enter

# Wait for TUI to load
Sleep 2s

# Switch to right pane
Hide
Ctrl+B
Type "o"
Sleep 300ms
Show

# Show the file modification that triggers the chain
Type "# Saving a file triggers the chain:"
Enter
Sleep 500ms
Type "# Lint → Format → Build → Test → Deploy"
Enter
Sleep 1s
Type "touch demos/trigger.txt"
Sleep 500ms
Enter

# Switch back to left pane to watch the chain
Hide
Ctrl+B
Type "o"
Sleep 300ms
Show

# Wait for chain to complete (Lint → Format → Build → Test → Deploy)
Sleep 8s

# Show Status command manually
Type "6"
Sleep 2s

# Show Logs command
Type "7"
Sleep 2s

# Exit TUI
Type "q"
Sleep 500ms

# Clean exit (hidden)
Hide
Type "exit"
Enter
Sleep 200ms
Type "exit"
Enter
Sleep 200ms
