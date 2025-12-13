"""State manager for active context and settings"""

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import Storage

DEFAULT_APP_DIR = Path.home() / ".trace"


class StateManager:
    """Manages active context and user settings"""

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
