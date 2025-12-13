import json
import time
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from .models import Case, Evidence, Note

DEFAULT_APP_DIR = Path.home() / ".trace"

class LockManager:
    """Cross-platform file lock manager to prevent concurrent access"""
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.acquired = False

    def acquire(self, timeout: int = 5):
        """Acquire lock with timeout. Returns True if successful."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try to create lock file exclusively (fails if exists)
                # Use 'x' mode which fails if file exists (atomic on most systems)
                fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self.acquired = True
                return True
            except FileExistsError:
                # Lock file exists, check if process is still alive
                if self._is_stale_lock():
                    # Remove stale lock and retry
                    try:
                        self.lock_file.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                # Active lock, wait a bit
                time.sleep(0.1)
            except Exception:
                # Other errors, wait and retry
                time.sleep(0.1)
        return False

    def _is_stale_lock(self):
        """Check if lock file is stale (process no longer exists)"""
        try:
            if not self.lock_file.exists():
                return False
            with open(self.lock_file, 'r') as f:
                pid = int(f.read().strip())

            # Check if process exists (cross-platform)
            if sys.platform == 'win32':
                import ctypes
                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_INFORMATION = 0x0400
                handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return False
                return True
            else:
                # Unix/Linux - send signal 0 to check if process exists
                try:
                    os.kill(pid, 0)
                    return False  # Process exists
                except OSError:
                    return True  # Process doesn't exist
        except (ValueError, FileNotFoundError, PermissionError):
            return True

    def release(self):
        """Release the lock"""
        if self.acquired:
            try:
                self.lock_file.unlink()
            except FileNotFoundError:
                pass
            self.acquired = False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("Could not acquire lock: another instance is running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

class Storage:
    def __init__(self, app_dir: Path = DEFAULT_APP_DIR, acquire_lock: bool = True):
        self.app_dir = app_dir
        self.data_file = self.app_dir / "data.json"
        self.lock_file = self.app_dir / "app.lock"
        self.lock_manager = None
        self._ensure_app_dir()

        # Acquire lock to prevent concurrent access
        if acquire_lock:
            self.lock_manager = LockManager(self.lock_file)
            if not self.lock_manager.acquire(timeout=5):
                raise RuntimeError("Another instance of trace is already running. Please close it first.")

        self.cases: List[Case] = self._load_data()

        # Create demo case on first launch (only if data loaded successfully and is empty)
        if not self.cases and self.data_file.exists():
            # File exists but is empty - could be first run after successful load
            pass
        elif not self.cases and not self.data_file.exists():
            # No file exists - first run
            self._create_demo_case()

    def __del__(self):
        """Release lock when Storage object is destroyed"""
        if self.lock_manager:
            self.lock_manager.release()

    def _ensure_app_dir(self):
        if not self.app_dir.exists():
            self.app_dir.mkdir(parents=True, exist_ok=True)

    def _create_demo_case(self):
        """Create a demo case with evidence showcasing all features"""
        demo_case = Case(
            case_number="DEMO-2024-001",
            name="Sample Investigation",
            investigator="Demo User"
        )

        # Add case-level notes to demonstrate case notes feature
        case_note1 = Note(content="""Initial case briefing: Suspected data exfiltration incident.

Key objectives:
- Identify compromised systems
- Determine scope of data loss
- Document timeline of events

#incident-response #data-breach #investigation""")
        case_note1.calculate_hash()
        case_note1.extract_tags()
        case_note1.extract_iocs()
        demo_case.notes.append(case_note1)

        case_note2 = Note(content="""Investigation lead: Employee reported suspicious email from sender@phishing-domain.com
Initial analysis shows potential credential harvesting attempt.
Review email headers and attachments for IOCs. #phishing #email-analysis""")
        case_note2.calculate_hash()
        case_note2.extract_tags()
        case_note2.extract_iocs()
        demo_case.notes.append(case_note2)

        # Create evidence 1: Compromised laptop
        evidence1 = Evidence(
            name="Employee Laptop HDD",
            description="Primary workstation hard drive - user reported suspicious activity"
        )
        # Add source hash for chain of custody demonstration
        evidence1.metadata["source_hash"] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        # Add notes to evidence 1 with various features
        note1 = Note(content="""Forensic imaging completed. Drive imaged using FTK Imager.
Image hash verified: SHA256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

Chain of custody maintained throughout process. #forensics #imaging #chain-of-custody""")
        note1.calculate_hash()
        note1.extract_tags()
        note1.extract_iocs()
        evidence1.notes.append(note1)

        note2 = Note(content="""Discovered suspicious connections to external IP addresses:
- 192.168.1.100 (local gateway)
- 203.0.113.45 (external, geolocation: Unknown)
- 198.51.100.78 (command and control server suspected)

Browser history shows visits to malicious-site.com and data-exfil.net.
#network-analysis #ioc #c2-server""")
        note2.calculate_hash()
        note2.extract_tags()
        note2.extract_iocs()
        evidence1.notes.append(note2)

        note3 = Note(content="""Malware identified in temp directory:
File: evil.exe
MD5: d41d8cd98f00b204e9800998ecf8427e
SHA1: da39a3ee5e6b4b0d3255bfef95601890afd80709
SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

Submitting to VirusTotal for analysis. #malware #hash-analysis #virustotal""")
        note3.calculate_hash()
        note3.extract_tags()
        note3.extract_iocs()
        evidence1.notes.append(note3)

        note4 = Note(content="""Timeline analysis reveals:
- 2024-01-15 09:23:45 - Suspicious email received
- 2024-01-15 09:24:12 - User clicked phishing link https://evil-domain.com/login
- 2024-01-15 09:25:03 - Credentials submitted to attacker-controlled site
- 2024-01-15 09:30:15 - Lateral movement detected

User credentials compromised. Recommend immediate password reset. #timeline #lateral-movement""")
        note4.calculate_hash()
        note4.extract_tags()
        note4.extract_iocs()
        evidence1.notes.append(note4)

        demo_case.evidence.append(evidence1)

        # Create evidence 2: Network logs
        evidence2 = Evidence(
            name="Firewall Logs",
            description="Corporate firewall logs from incident timeframe"
        )
        evidence2.metadata["source_hash"] = "a3f5c8b912e4d67f89b0c1a2e3d4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2"

        note5 = Note(content="""Log analysis shows outbound connections to suspicious domains:
- attacker-c2.com on port 443 (encrypted channel)
- data-upload.net on port 8080 (unencrypted)
- exfil-server.org on port 22 (SSH tunnel)

Total data transferred: approximately 2.3 GB over 4 hours.
#log-analysis #data-exfiltration #network-traffic""")
        note5.calculate_hash()
        note5.extract_tags()
        note5.extract_iocs()
        evidence2.notes.append(note5)

        note6 = Note(content="""Contact information found in malware configuration:
Email: attacker@malicious-domain.com
Backup C2: 2001:0db8:85a3:0000:0000:8a2e:0370:7334 (IPv6)

Cross-referencing with threat intelligence databases. #threat-intel #attribution""")
        note6.calculate_hash()
        note6.extract_tags()
        note6.extract_iocs()
        evidence2.notes.append(note6)

        demo_case.evidence.append(evidence2)

        # Create evidence 3: Email forensics
        evidence3 = Evidence(
            name="Phishing Email",
            description="Original phishing email preserved in .eml format"
        )

        note7 = Note(content="""Email headers analysis:
From: sender@phishing-domain.com (spoofed)
Reply-To: attacker@evil-mail-server.net
X-Originating-IP: 198.51.100.99

Email contains embedded tracking pixel at http://tracking.malicious-site.com/pixel.gif
Attachment: invoice.pdf.exe (double extension trick) #email-forensics #phishing-analysis""")
        note7.calculate_hash()
        note7.extract_tags()
        note7.extract_iocs()
        evidence3.notes.append(note7)

        demo_case.evidence.append(evidence3)

        # Add the demo case to storage
        self.cases.append(demo_case)
        self.save_data()

    def _load_data(self) -> List[Case]:
        if not self.data_file.exists():
            return []
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [Case.from_dict(c) for c in data]
        except (json.JSONDecodeError, IOError, KeyError, ValueError) as e:
            # Corrupted JSON - create backup and raise exception
            import shutil
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.app_dir / f"data.json.corrupted.{timestamp}"
            try:
                shutil.copy2(self.data_file, backup_file)
            except Exception:
                pass
            # Raise exception with information about backup
            raise RuntimeError(f"Data file is corrupted. Backup saved to: {backup_file}\nError: {e}")

    def start_fresh(self):
        """Start with fresh data (for corrupted JSON recovery)"""
        self.cases = []
        self._create_demo_case()

    def save_data(self):
        data = [c.to_dict() for c in self.cases]
        # Write to temp file then rename for atomic-ish write
        temp_file = self.data_file.with_suffix(".tmp")
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.data_file)

    def add_case(self, case: Case):
        self.cases.append(case)
        self.save_data()

    def get_case(self, case_id: str) -> Optional[Case]:
        # Case ID lookup
        for c in self.cases:
            if c.case_id == case_id:
                return c
        return None

    def delete_case(self, case_id: str):
        self.cases = [c for c in self.cases if c.case_id != case_id]
        self.save_data()

    def delete_evidence(self, case_id: str, evidence_id: str):
        case = self.get_case(case_id)
        if case:
            case.evidence = [e for e in case.evidence if e.evidence_id != evidence_id]
            self.save_data()

    def find_evidence(self, evidence_id: str) -> Tuple[Optional[Case], Optional[Evidence]]:
        for c in self.cases:
            for e in c.evidence:
                if e.evidence_id == evidence_id:
                    return c, e
        return None, None

class StateManager:
    def __init__(self, app_dir: Path = DEFAULT_APP_DIR):
        self.app_dir = app_dir
        self.state_file = self.app_dir / "state"
        self.settings_file = self.app_dir / "settings.json"
        self._ensure_app_dir()

    def _ensure_app_dir(self):
        if not self.app_dir.exists():
            self.app_dir.mkdir(parents=True, exist_ok=True)

    def set_active(self, case_id: Optional[str] = None, evidence_id: Optional[str] = None):
        state = self.get_active()
        state["case_id"] = case_id
        state["evidence_id"] = evidence_id
        # Atomic write: write to temp file then rename
        temp_file = self.state_file.with_suffix(".tmp")
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False)
        temp_file.replace(self.state_file)

    def get_active(self) -> dict:
        if not self.state_file.exists():
            return {"case_id": None, "evidence_id": None}
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"case_id": None, "evidence_id": None}

    def validate_and_clear_stale(self, storage: 'Storage') -> str:
        """Validate active state against storage and clear stale references.
        Returns warning message if state was cleared, empty string otherwise."""
        state = self.get_active()
        case_id = state.get("case_id")
        evidence_id = state.get("evidence_id")
        warning = ""

        if case_id:
            case = storage.get_case(case_id)
            if not case:
                warning = f"Active case (ID: {case_id[:8]}...) no longer exists. Clearing active context."
                self.set_active(None, None)
                return warning

            # Validate evidence if set
            if evidence_id:
                _, evidence = storage.find_evidence(evidence_id)
                if not evidence:
                    warning = f"Active evidence (ID: {evidence_id[:8]}...) no longer exists. Clearing to case level."
                    self.set_active(case_id, None)
                    return warning

        elif evidence_id:
            # Evidence set but no case - invalid state
            warning = "Invalid state: evidence set without case. Clearing active context."
            self.set_active(None, None)
            return warning

        return warning

    def get_settings(self) -> dict:
        if not self.settings_file.exists():
            return {"pgp_enabled": True}
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"pgp_enabled": True}

    def set_setting(self, key: str, value):
        settings = self.get_settings()
        settings[key] = value
        # Atomic write: write to temp file then rename
        temp_file = self.settings_file.with_suffix(".tmp")
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False)
        temp_file.replace(self.settings_file)
