# trace - Forensic Notes

`trace` is a minimal, terminal-based forensic note-taking application designed for digital investigators and incident responders. It provides a secure, integrity-focused environment for case management and evidence logging.

## Features

*   **Integrity Focused:**
    *   **Hashing:** Every note is automatically SHA256 hashed (content + timestamp).
    *   **Signing:** Optional GPG signing of notes for non-repudiation (requires system `gpg`).
*   **Minimal Dependencies:** Written in Python using only the standard library (`curses`, `json`, `sqlite3` avoided, etc.) + `pyinstaller` for packaging.
*   **Dual Interface:**
    *   **TUI (Text User Interface):** Interactive browsing of Cases and Evidence hierarchies with multi-line note editor.
    *   **CLI Shorthand:** Quickly append notes to the currently active Case/Evidence from your shell (`trace "Found a USB key"`).
*   **Multi-Line Notes:** Full-featured text editor supports detailed forensic observations with multiple lines, arrow key navigation, and scrolling.
*   **Evidence Source Hashing:** Optionally store source hash values (e.g., SHA256) as metadata when creating evidence items for chain of custody tracking.
*   **Tag System:** Organize notes with hashtags (e.g., `#malware #windows #critical`). View tags sorted by usage, filter notes by tag, and navigate tagged notes with full context.
*   **IOC Detection:** Automatically extracts Indicators of Compromise (IPs, domains, URLs, hashes, emails) from notes. View, filter, and export IOCs with occurrence counts and context separators.
*   **Context Awareness:** Set an "Active" context in the TUI, which persists across sessions for CLI note taking. Recent notes displayed inline for reference.
*   **Filtering:** Quickly filter Cases and Evidence lists (press `/`).
*   **Export:** Export all data to a formatted Markdown report with verification details, including evidence source hashes.

## Installation

### From Source

Requires Python 3.x.

```bash
git clone <repository_url>
cd trace
# Run directly
python3 main.py
```

### Building Binary

You can build a single-file executable using PyInstaller.

#### Linux/macOS

```bash
pip install -r requirements.txt
./build_binary.sh
# Binary will be in dist/trace
./dist/trace
```

#### Windows

```powershell
# Install dependencies (includes windows-curses)
pip install -r requirements.txt

# Build the executable
pyinstaller --onefile --name trace --clean --paths . --hidden-import curses main.py

# Binary will be in dist\trace.exe
.\dist\trace.exe
```

### Installing to PATH

After building the binary, you can install it to your system PATH for easy access:

#### Linux/macOS

```bash
# Option 1: Copy to /usr/local/bin (requires sudo)
sudo cp dist/trace /usr/local/bin/

# Option 2: Copy to ~/.local/bin (user-only, ensure ~/.local/bin is in PATH)
mkdir -p ~/.local/bin
cp dist/trace ~/.local/bin/

# Add to PATH if not already (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"
```

#### Windows

```powershell
# Option 1: Copy to a directory in PATH (e.g., C:\Windows\System32 - requires admin)
Copy-Item dist\trace.exe C:\Windows\System32\

# Option 2: Create a local bin directory and add to PATH
# 1. Create directory
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\bin"
Copy-Item dist\trace.exe "$env:USERPROFILE\bin\"

# 2. Add to PATH permanently (run as admin or use GUI: System Properties > Environment Variables)
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:USERPROFILE\bin", "User")

# 3. Restart terminal/PowerShell for changes to take effect
```

## Usage

### TUI Mode
Run `trace` without arguments to open the interface.

**Navigation:**
*   `Arrow Keys`: Navigate lists.
*   `Enter`: Select Case / View Evidence details.
*   `b`: Back.
*   `q`: Quit.

**Management:**
*   `n`: Add a Note to the current context (works in any view).
    *   **Multi-line support**: Notes can span multiple lines - press `Enter` for new lines.
    *   **Tagging**: Use hashtags in your notes (e.g., `#malware #critical`) for organization.
    *   Press `Ctrl+G` to submit the note, or `Esc` to cancel.
    *   Recent notes are displayed inline for context (non-blocking).
*   `N` (Shift+n): New Case (in Case List) or New Evidence (in Case Detail).
*   `t`: **Tags View**. Browse all tags in the current context (case or evidence), sorted by usage count.
    *   Press `Enter` on a tag to see all notes with that tag.
    *   Press `Enter` on a note to view full details with tag highlighting.
    *   Navigate back with `b`.
*   `i`: **IOCs View**. View all Indicators of Compromise extracted from notes in the current context.
    *   Shows IOC types (IPv4, domain, URL, hash, email) with occurrence counts.
    *   Press `Enter` on an IOC to see all notes containing it.
    *   Press `e` to export IOCs to `~/.trace/exports/` in plain text format.
    *   IOC counts are displayed in red in case and evidence views.
*   `a`: **Set Active**. Sets the currently selected Case or Evidence as the global "Active" context.
*   `d`: Delete the selected Case or Evidence (with confirmation).
*   `v`: View all notes for the current Case (in Case Detail view).
*   `/`: Filter list (type to search, `Esc` or `Enter` to exit filter mode).
*   `s`: Settings menu (in Case List view).
*   `Esc`: Cancel during input dialogs.

### CLI Mode
Once a Case or Evidence is set as **Active** in the TUI, you can add notes directly from the command line:

```bash
trace "Suspect system is powered on, attempting live memory capture."
```

This note is automatically timestamped, hashed, signed, and appended to the active context.

### Exporting
To generate a report:

```bash
trace --export
# Creates trace_export.md
```

## Data Storage
Data is stored in JSON format at `~/.trace/data.json`.
Application state (active context) is stored at `~/.trace/state`.

## License
MIT
