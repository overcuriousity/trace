import json
import os
from pathlib import Path
from typing import List, Optional, Tuple
from .models import Case, Evidence, Note

DEFAULT_APP_DIR = Path.home() / ".trace"

class Storage:
    def __init__(self, app_dir: Path = DEFAULT_APP_DIR):
        self.app_dir = app_dir
        self.data_file = self.app_dir / "data.json"
        self._ensure_app_dir()
        self.cases: List[Case] = self._load_data()

    def _ensure_app_dir(self):
        if not self.app_dir.exists():
            self.app_dir.mkdir(parents=True, exist_ok=True)

    def _load_data(self) -> List[Case]:
        if not self.data_file.exists():
            return []
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                return [Case.from_dict(c) for c in data]
        except (json.JSONDecodeError, IOError):
            return []

    def reload(self):
        """Reloads data from disk to refresh state."""
        self.cases = self._load_data()

    def save_data(self):
        data = [c.to_dict() for c in self.cases]
        # Write to temp file then rename for atomic-ish write
        temp_file = self.data_file.with_suffix(".tmp")
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
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
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    def get_active(self) -> dict:
        if not self.state_file.exists():
            return {"case_id": None, "evidence_id": None}
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
             return {"case_id": None, "evidence_id": None}

    def get_settings(self) -> dict:
        if not self.settings_file.exists():
            return {"pgp_enabled": True}
        try:
            with open(self.settings_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"pgp_enabled": True}

    def set_setting(self, key: str, value):
        settings = self.get_settings()
        settings[key] = value
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f)
