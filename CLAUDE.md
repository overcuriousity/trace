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

### Modular Structure (Optimized for AI Coding Agents)

The codebase is organized into focused, single-responsibility modules to make it easier for AI agents and developers to navigate, understand, and modify specific functionality:

**`trace/models/`**: Data models package
- `__init__.py`: Main model classes (Note, Evidence, Case) with dataclass definitions
- `extractors/tag_extractor.py`: Tag extraction logic (hashtag parsing)
- `extractors/ioc_extractor.py`: IOC extraction logic (IPs, domains, URLs, hashes, emails)
- All models implement `to_dict()`/`from_dict()` for JSON serialization
- Models use extractors for automatic tag and IOC detection

**`trace/storage_impl/`**: Storage implementation package
- `storage.py`: Main Storage class managing `~/.trace/data.json` with atomic writes
- `state_manager.py`: StateManager for active context and settings persistence
- `lock_manager.py`: Cross-platform file locking to prevent concurrent access
- `demo_data.py`: Demo case creation for first-time users
- Backward compatible via `trace/storage.py` wrapper

**`trace/tui/`**: Text User Interface package
- `tui.py`: Main TUI class with view hierarchy and event loop (3307 lines - target for future refactoring)
- `rendering/colors.py`: Color pair initialization and constants
- `rendering/text_renderer.py`: Text rendering with IOC/tag highlighting
- `handlers/export_handler.py`: Export functionality (IOCs, markdown reports)
- Future refactoring will extract views, dialogs, and input handlers

**`trace/crypto.py`**: Integrity features
- `sign_content()`: GPG clearsign via subprocess (falls back gracefully if GPG unavailable)
- `hash_content()`: SHA256 of timestamp:content to ensure temporal integrity

**`trace/cli.py`**: Entry point and CLI operations
- `quick_add_note()`: Adds note to active context from command line
- `export_markdown()`: Generates full case report with hashes and signatures
- `main()`: Argument parsing, routes to TUI or CLI functions

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

## AI Agent Optimization

The codebase has been restructured to be optimal for AI coding agents:

### Module Organization Benefits
- **Focused Files**: Each module has a single, clear responsibility (50-250 lines typically)
- **Easy Navigation**: Functionality is easy to locate by purpose (e.g., IOC extraction, export handlers)
- **Independent Modification**: Changes to one module rarely affect others
- **Clear Interfaces**: Modules communicate through well-defined imports
- **Reduced Context**: AI agents can focus on relevant files without loading massive monoliths

### File Size Guidelines
- **Small modules** (< 150 lines): Ideal for focused tasks
- **Medium modules** (150-300 lines): Acceptable for cohesive functionality
- **Large modules** (> 500 lines): Consider refactoring into smaller components
- **Very large modules** (> 1000 lines): Priority target for extraction and modularization

### Current Status
- ✅ Models: Organized into package with extractors separated
- ✅ Storage: Split into focused modules (storage, state, locking, demo data)
- ✅ TUI Utilities: Rendering and export handlers extracted
- ⏳ TUI Main: Still monolithic (3307 lines) - future refactoring needed

### Future Refactoring Targets
The `trace/tui.py` file (3307 lines) should be further split into:
- `tui/views/` - Individual view classes (case list, evidence detail, etc.)
- `tui/dialogs/` - Dialog functions (input, confirm, settings, etc.)
- `tui/handlers/` - Input and navigation handlers
- `tui/app.py` - Main TUI orchestration class
