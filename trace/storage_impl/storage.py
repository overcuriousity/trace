"""Main storage class for persisting cases, evidence, and notes"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

from ..models import Case, Evidence
from .lock_manager import LockManager
from .demo_data import create_demo_case

DEFAULT_APP_DIR = Path.home() / ".trace"


class Storage:
    """Manages persistence of all forensic data"""

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
            demo_case = create_demo_case()
            self.cases.append(demo_case)
            self.save_data()

    def __del__(self):
        """Release lock when Storage object is destroyed"""
        if self.lock_manager:
            self.lock_manager.release()

    def _ensure_app_dir(self):
        if not self.app_dir.exists():
            self.app_dir.mkdir(parents=True, exist_ok=True)

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
        demo_case = create_demo_case()
        self.cases.append(demo_case)
        self.save_data()

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
