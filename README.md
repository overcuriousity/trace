# trace - Digital Evidence Log Utility

`trace` is a bare-bones, terminal-centric note-taking utility for digital forensics and incident response. It is designed for maximum operational efficiency, ensuring that the integrity of your log data is never compromised by the need to slow down.

This tool mandates minimal system overhead, relying solely on standard libraries where possible.

## ⚡ Key Feature: Hot Logging (CLI Shorthand)

The primary operational benefit of `trace` is its ability to accept input directly from the command line, bypassing the full interface. Once your active target context is set, you can drop notes instantly.

**Configuration:** Use the TUI to set a Case or Evidence ID as "Active" (`a`). This state persists across sessions.

**Syntax for Data Injection:**

```bash
# Log an immediate status update
trace "IR team gained shell access. Initial persistence checks running."

# Log data and tag it for later triage
trace "Observed outbound connection to 192.168.1.55 on port 80. #suspicious #network"
```

**System Integrity Chain:** Each command-line note is immediately stamped, concatenated with its content, and hashed using SHA256 before storage. This ensures a non-repudiable log entry.

## Installation & Deployment

### Quick Install from Latest Release

**Linux / macOS:**
```bash
curl -L https://github.com/overcuriousity/trace/releases/latest/download/trace -o trace && sudo mv trace /usr/local/bin/ && sudo chmod +x /usr/local/bin/trace
```

**Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri "https://github.com/overcuriousity/trace/releases/latest/download/trace.exe" -OutFile "$env:USERPROFILE\bin\trace.exe"; [Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:USERPROFILE\bin", "User")
```
*Note: Create `$env:USERPROFILE\bin` directory first if it doesn't exist, then restart your shell.*

---

### Platform: Linux / UNIX (including macOS)

**Prerequisites:** Python 3.x and the binary build utility (PyInstaller).

**Deployment:**

1.  **Build Binary:** Execute the build script in the source directory.

    ```bash
    ./build_binary.sh
    ```

    *The output executable will land in `dist/trace`.*

2.  **Path Integration:** For universal access, the binary must reside in a directory referenced by your `$PATH` environment variable (e.g., `/usr/local/bin`).

    ```bash
    # Place executable in system path
    sudo mv dist/trace /usr/local/bin/

    # Ensure execute bit is set
    sudo chmod +x /usr/local/bin/trace
    ```

    You are now cleared to run `trace` from any shell prompt.

### Platform: Windows

**Prerequisites:** Python 3.x, `pyinstaller`, and the `windows-curses` library.

**Deployment:**

1.  **Build Binary:** Run the build command in a PowerShell or CMD environment.

    ```powershell
    pyinstaller --onefile --name trace --clean --paths . --hidden-import curses main.py
    ```

    *The executable is located at `dist\trace.exe`.*

2.  **Path Integration:** The executable must be accessible via your user or system `%PATH%` variable for the hot-logging feature to function correctly.

    *Option A: System Directory (Requires Administrator Privilege)*

    ```powershell
    Copy-Item dist\trace.exe C:\Windows\System32\
    ```

    *Option B: User-Defined Bin Directory (Recommended)*

    ```powershell
    # Create the user bin location
    New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\bin"
    Copy-Item dist\trace.exe "$env:USERPROFILE\bin\"

    # Inject the directory into the User PATH variable
    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:USERPROFILE\bin", "User")
    ```

    **ATTENTION:** You must cycle your command shell (exit and reopen) before the `trace` command will resolve correctly.

## Core Feature Breakdown

| Feature | Description | Operational Impact |
| :--- | :--- | :--- |
| **Integrity Hashing** | SHA256 applied to every log entry (content + timestamp). | **Guaranteed log integrity.** No modification possible post-entry. |
| **GPG Signing** | Optional PGP/GPG signature applied to notes. | **Non-repudiation** for formal evidence handling. |
| **IOC Extraction** | Automatic parsing of IPv4, FQDNs, URLs, hashes, and email addresses. | **Immediate intelligence gathering** from raw text. |
| **Tag System** | Supports `#hashtags` for classification and filtering. | **Efficient triage** of large log sets. |
| **Minimal Footprint** | Built solely on Python standard library modules. | **Maximum portability** on restricted forensic environments. |

## TUI Reference (Management Console)

Execute `trace` (no arguments) to enter the Text User Interface. This environment is used for setup, review, and reporting.

| Key | Function | Detail |
| :--- | :--- | :--- |
| `a` | **Set Active** | Designate the current item as the target for CLI injection (hot-logging). |
| `n` | **New Note** | Enter the multi-line log editor. Use $\text{Ctrl+G}$ to save block. |
| `i` | **IOC Index** | View extracted indicators. Option to export IOC list (`e`). |
| `t` | **Tag Index** | View classification tags and filter notes by frequency. |
| `v` | **Full View** | Scrollable screen showing all log entries with automatic IOC/Tag highlighting. |
| `/` | **Filter** | Initiate text-based search/filter on lists. |
| $\text{Enter}$ | **Drill Down** | Access details for Case or Evidence. |
| `q` | **Exit** | Close the application. |

## Report Generation

To generate the Markdown report package, use the `--export` flag.

```bash
trace --export
# Creates trace_export.md in the current directory.
```

## Data Persistence

Trace maintains a simple flat-file structure in the user's home directory.

  * `~/.trace/data.json`: Case log repository.
  * `~/.trace/state`: Active context pointer.

-----

*License: MIT*

**DISCLAIMER**
This program was mostly vibe-coded. This was a deliberate decision as I wanted to focus on producing a usable result with okay user experience rather than implementation details and educating myself by lengthy coding sessions.
I reviewed sections of the code manually and found no issues. The application should be safe to use from a integrity, security and admissability standpoint, while I wont ever make any warranties on this.
The coding agents I mostly used were in this order: Claude Sonnett 45 (CLI), Claude Haiku 4.5 (VSCode Copilot), Google Jules (version unknown).
