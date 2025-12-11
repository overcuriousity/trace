# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`trace` is a minimal, terminal-based forensic note-taking application for digital investigators and incident responders. It focuses on data integrity through SHA256 hashing and optional GPG signing of all notes, with zero external dependencies beyond Python's standard library.

## Development Commands

### Running the Application
```bash
# Run directly from source
python3 main.py

# Quick CLI note addition (requires active case/evidence set in TUI)
python3 main.py "Your note content here"

# Export to markdown
python3 main.py --export --output report.md

# Open TUI directly at active case/evidence
python3 main.py --open
```

### Building Binary
```bash
# Install dependencies first
pip install -r requirements.txt

# Build on Linux/macOS
./build_binary.sh

# Build on Windows
pyinstaller --onefile --name trace --clean --paths . --hidden-import curses main.py
```

### Testing
```bash
# Run unit tests
python3 -m unittest trace/tests/test_models.py

# Run all tests with discovery
python3 -m unittest discover -s trace/tests
```

## Architecture

### Data Model Hierarchy
The application uses a three-level hierarchy:
- **Case** → **Evidence** → **Note** (with Notes also attachable directly to Cases)

Each level has unique IDs (UUIDs) for reliable lookups across the hierarchy.

### Core Modules

**`trace/models.py`**: Data models using dataclasses
- `Note`: Content + timestamp + SHA256 hash + optional GPG signature + auto-extracted tags/IOCs
- `Evidence`: Container for notes about a specific piece of evidence, includes metadata dict for source hashes
- `Case`: Top-level container with case number, investigator, evidence list, and notes
- All models implement `to_dict()`/`from_dict()` for JSON serialization

**`trace/storage.py`**: Persistence layer
- `Storage`: Manages `~/.trace/data.json` with atomic writes (temp file + rename)
- `StateManager`: Manages `~/.trace/state` (active case/evidence) and `~/.trace/settings.json` (PGP enabled/disabled)
- Data is loaded into memory on init, modified, then saved atomically

**`trace/crypto.py`**: Integrity features
- `sign_content()`: GPG clearsign via subprocess (falls back gracefully if GPG unavailable)
- `hash_content()`: SHA256 of timestamp:content to ensure temporal integrity

**`trace/cli.py`**: Entry point and CLI operations
- `quick_add_note()`: Adds note to active context from command line
- `export_markdown()`: Generates full case report with hashes and signatures
- `main()`: Argument parsing, routes to TUI or CLI functions

**`trace/tui.py`**: Curses-based Text User Interface
- View hierarchy: case_list → case_detail → evidence_detail
- Additional views: tags_list, tag_notes_list, ioc_list, ioc_notes_list, note_detail
- Multi-line note editor with Ctrl+G to submit, Esc to cancel
- Filter mode (press `/`), active context management (press `a`)
- All note additions automatically extract tags (#hashtag) and IOCs (IPs, domains, URLs, hashes, emails)

### Key Features Implementation

**Integrity System**: Every note automatically gets:
1. SHA256 hash of `timestamp:content` (via `Note.calculate_hash()`)
2. Optional GPG clearsign signature (if `pgp_enabled` in settings and GPG available)

**Tag System**: Regex-based hashtag extraction (`#word`)
- Extracted on note creation and stored in `Note.tags` list
- Case-insensitive matching, stored lowercase
- TUI provides tag browser with usage counts

**IOC Detection**: Automatic extraction of forensic indicators
- Patterns: IPv4, IPv6, domains, URLs, MD5/SHA1/SHA256 hashes, emails
- Extracted on note creation and stored in `Note.iocs` list
- TUI provides IOC browser with type categorization and export capability

**Active Context**: Persistent state across TUI/CLI sessions
- Set via 'a' key in TUI on any Case or Evidence
- Enables `trace "note"` CLI shorthand to append to active context
- State persists in `~/.trace/state` JSON file

### Data Storage

All data lives in `~/.trace/`:
- `data.json`: All cases, evidence, and notes
- `state`: Active context (case_id, evidence_id)
- `settings.json`: User preferences (pgp_enabled)
- `exports/`: IOC exports directory

JSON structure mirrors the data model hierarchy exactly (Case → Evidence → Note).

### Important Patterns

**Atomic Writes**: All saves use temp file + rename pattern to prevent corruption
```python
temp_file = self.data_file.with_suffix(".tmp")
with open(temp_file, 'w') as f:
    json.dump(data, f, indent=2)
temp_file.replace(self.data_file)
```

**Graceful Degradation**: GPG signing is optional and fails silently if GPG unavailable

**Zero External Dependencies**: Only stdlib (except PyInstaller for builds and windows-curses for Windows)

## Testing Notes

Tests use temporary directories created with `tempfile.mkdtemp()` and cleaned up in `tearDown()` to avoid polluting `~/.trace/`.
