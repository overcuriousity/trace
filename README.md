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

**Optional: Create Ultra-Fast Alias**

For maximum speed when logging, create a single-character alias:

**Linux / macOS (Bash):**
```bash
echo 'alias t="trace"' >> ~/.bashrc && source ~/.bashrc
```

**Linux / macOS (Zsh):**
```bash
echo 'alias t="trace"' >> ~/.zshrc && source ~/.zshrc
```

**Windows (PowerShell):**
```powershell
New-Item -ItemType File -Force $PROFILE; Add-Content $PROFILE 'function t { trace $args }'; . $PROFILE
```

After this, you can log with just: `t "Your note here"`

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

## Cryptographic Integrity & Chain of Custody

`trace` implements a dual-layer cryptographic system designed for legal admissibility and forensic integrity:

### Layer 1: Note-Level Integrity (Always Active)

**Process:**
1. **Timestamp Generation** - Precise Unix timestamp captured at note creation
2. **Content Hashing** - SHA256 hash computed from `timestamp:content`
3. **Optional Signature** - Hash is signed with investigator's GPG private key

**Mathematical Representation:**
```
hash = SHA256(timestamp + ":" + content)
signature = GPG_Sign(hash, private_key)
```

**Security Properties:**
- **Temporal Integrity**: Timestamp is cryptographically bound to content (cannot backdate notes)
- **Tamper Detection**: Any modification to content or timestamp invalidates the hash
- **Non-Repudiation**: GPG signature proves who created the note (if signing enabled)
- **Efficient Storage**: Signing only the hash (64 hex chars) instead of full content

### Layer 2: Export-Level Integrity (On Demand)

When exporting to markdown (`--export`), the **entire export document** is GPG-signed if signing is enabled.

**Process:**
1. Generate complete markdown export with all cases, evidence, and notes
2. Individual note signatures are preserved within the export
3. Entire document is clearsigned with GPG

**Security Properties:**
- **Document Integrity**: Proves export hasn't been modified after generation
- **Dual Verification**: Both individual notes AND complete document can be verified
- **Chain of Custody**: Establishes provenance from evidence collection through report generation

### First-Run GPG Setup

On first launch, `trace` runs an interactive wizard to configure GPG signing:

1. **GPG Detection** - Checks if GPG is installed (gracefully continues without if missing)
2. **Key Selection** - Lists available secret keys from your GPG keyring
3. **Configuration** - Saves selected key ID to `~/.trace/settings.json`

**If GPG is not available:**
- Application continues to function normally
- Notes are hashed (SHA256) but not signed
- You can enable GPG later by editing `~/.trace/settings.json`

### Verification Workflows

#### Internal Verification (Within trace TUI)

The TUI automatically verifies signatures and displays status symbols:
- `✓` - Signature verified with public key in keyring
- `✗` - Signature verification failed (tampered or missing key)
- `?` - Note is unsigned

**To verify a specific note:**
1. Navigate to the note in TUI
2. Press `Enter` to view note details
3. Press `v` to see detailed verification information

#### External Verification (Manual/Court)

**Scenario**: Forensic investigator sends evidence to court/auditor

**Step 1 - Investigator exports evidence:**
```bash
# Export all notes with signatures
trace --export --output investigation-2024-001.md

# Export public key for verification
gpg --armor --export investigator@agency.gov > investigator-pubkey.asc

# Send both files to recipient
```

**Step 2 - Recipient verifies document:**
```bash
# Import investigator's public key
gpg --import investigator-pubkey.asc

# Verify entire export document
gpg --verify investigation-2024-001.md
```

**Expected output if valid:**
```
gpg: Signature made Mon Dec 13 14:23:45 2024
gpg: using RSA key ABC123DEF456
gpg: Good signature from "John Investigator <investigator@agency.gov>"
```

**Step 3 - Verify individual notes (optional):**

Individual note signatures are embedded in the markdown export. To verify a specific note:

1. Open `investigation-2024-001.md` in a text editor
2. Locate the note's signature block:
   ```
   - **GPG Signature of Hash:**
     ```
     -----BEGIN PGP SIGNED MESSAGE-----
     Hash: SHA256

     a3f5b2c8d9e1f4a7b6c3d8e2f5a9b4c7d1e6f3a8b5c2d9e4f7a1b8c6d3e0f5a2
     -----BEGIN PGP SIGNATURE-----
     ...
     -----END PGP SIGNATURE-----
     ```
3. Extract the signature block (from `-----BEGIN PGP SIGNED MESSAGE-----` to `-----END PGP SIGNATURE-----`)
4. Save to a file and verify:
   ```bash
   cat > note-signature.txt
   <paste signature block>
   Ctrl+D

   gpg --verify note-signature.txt
   ```

**What gets verified:**
- The SHA256 hash proves the note content and timestamp haven't changed
- The GPG signature proves who created that hash
- Together: Proves this specific content was created by this investigator at this time

### Cryptographic Trust Model

```
┌─────────────────────────────────────────────────────────┐
│ Note Creation (Investigator)                           │
├─────────────────────────────────────────────────────────┤
│ 1. Content: "Malware detected on host-192.168.1.50"   │
│ 2. Timestamp: 1702483425.123456                        │
│ 3. Hash: SHA256(timestamp:content)                     │
│    → a3f5b2c8d9e1f4a7b6c3d8e2f5a9b4c7...              │
│ 4. Signature: GPG_Sign(hash, private_key)             │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Export Generation                                       │
├─────────────────────────────────────────────────────────┤
│ 1. Build markdown with all notes + individual sigs     │
│ 2. Sign entire document: GPG_Sign(document)            │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Verification (Court/Auditor)                           │
├─────────────────────────────────────────────────────────┤
│ 1. Import investigator's public key                    │
│ 2. Verify document signature → Proves export integrity │
│ 3. Verify individual notes → Proves note authenticity  │
│ 4. Recompute hashes → Proves content hasn't changed   │
└─────────────────────────────────────────────────────────┘
```

### Security Considerations

**What is protected:**
- ✓ Content integrity (hash detects any modification)
- ✓ Temporal integrity (timestamp cryptographically bound)
- ✓ Attribution (signature proves who created it)
- ✓ Export completeness (document signature proves no additions/removals)

**What is NOT protected:**
- ✗ Note deletion (signatures can't prevent removal from database)
- ✗ Selective disclosure (investigator can choose which notes to export)
- ✗ Sequential ordering (signatures are per-note, not chained)

**Trust Dependencies:**
- You must trust the investigator's GPG key (verify fingerprint out-of-band)
- You must trust the investigator's system clock was accurate
- You must trust the investigator didn't destroy contradictory evidence

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
