"""Data models for trace application"""

import time
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

from .extractors import TagExtractor, IOCExtractor


@dataclass
class Note:
    content: str
    # Unix timestamp: seconds since 1970-01-01 00:00:00 UTC as float
    # Example: 1702345678.123456
    # This exact float value (with full precision) is used in hash calculation
    timestamp: float = field(default_factory=time.time)
    note_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_hash: str = ""
    signature: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    iocs: List[str] = field(default_factory=list)

    def extract_tags(self):
        """Extract hashtags from content (case-insensitive, stored lowercase)"""
        self.tags = TagExtractor.extract_tags(self.content)

    def extract_iocs(self):
        """Extract Indicators of Compromise from content"""
        self.iocs = IOCExtractor.extract_iocs(self.content)

    def calculate_hash(self):
        """Calculate SHA256 hash of timestamp:content.

        Hash input format: "{timestamp}:{content}"
        - timestamp: Unix epoch timestamp as float (e.g., "1702345678.123456")
        - The float is converted to string using Python's default str() conversion
        - Colon separator between timestamp and content
        - Ensures integrity of both WHAT was said and WHEN it was said

        Example hash input: "1702345678.123456:Suspicious process detected"
        """
        data = f"{self.timestamp}:{self.content}".encode('utf-8')
        self.content_hash = hashlib.sha256(data).hexdigest()

    def verify_signature(self) -> Tuple[bool, str]:
        """
        Verify the GPG signature of this note.

        Returns:
            A tuple of (verified: bool, info: str)
            - verified: True if signature is valid, False if invalid or unsigned
            - info: Signer information or error/status message
        """
        # Import here to avoid circular dependency
        from ..crypto import Crypto

        if not self.signature:
            return False, "unsigned"

        return Crypto.verify_signature(self.signature)

    @staticmethod
    def extract_iocs_from_text(text):
        """Extract IOCs from text and return as list of (ioc, type) tuples"""
        return IOCExtractor.extract_iocs_with_types(text)

    @staticmethod
    def extract_iocs_with_positions(text):
        """Extract IOCs with their positions for highlighting. Returns list of (text, start, end, type) tuples"""
        return IOCExtractor.extract_iocs_with_positions(text)

    def to_dict(self):
        return {
            "note_id": self.note_id,
            "content": self.content,
            "timestamp": self.timestamp,
            "content_hash": self.content_hash,
            "signature": self.signature,
            "tags": self.tags,
            "iocs": self.iocs
        }

    @staticmethod
    def from_dict(data):
        note = Note(
            content=data["content"],
            timestamp=data["timestamp"],
            note_id=data["note_id"],
            content_hash=data.get("content_hash", ""),
            signature=data.get("signature"),
            tags=data.get("tags", []),
            iocs=data.get("iocs", [])
        )
        return note


@dataclass
class Evidence:
    name: str
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)
    notes: List[Note] = field(default_factory=list)

    def to_dict(self):
        return {
            "evidence_id": self.evidence_id,
            "name": self.name,
            "description": self.description,
            "metadata": self.metadata,
            "notes": [n.to_dict() for n in self.notes]
        }

    @staticmethod
    def from_dict(data):
        ev = Evidence(
            name=data["name"],
            evidence_id=data["evidence_id"],
            description=data.get("description", ""),
            metadata=data.get("metadata", {})
        )
        ev.notes = [Note.from_dict(n) for n in data.get("notes", [])]
        return ev


@dataclass
class Case:
    case_number: str
    case_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    investigator: str = ""
    evidence: List[Evidence] = field(default_factory=list)
    notes: List[Note] = field(default_factory=list)

    def to_dict(self):
        return {
            "case_id": self.case_id,
            "case_number": self.case_number,
            "name": self.name,
            "investigator": self.investigator,
            "evidence": [e.to_dict() for e in self.evidence],
            "notes": [n.to_dict() for n in self.notes]
        }

    @staticmethod
    def from_dict(data):
        case = Case(
            case_number=data["case_number"],
            case_id=data["case_id"],
            name=data.get("name", ""),
            investigator=data.get("investigator", "")
        )
        case.evidence = [Evidence.from_dict(e) for e in data.get("evidence", [])]
        case.notes = [Note.from_dict(n) for n in data.get("notes", [])]
        return case


__all__ = ['Note', 'Evidence', 'Case', 'TagExtractor', 'IOCExtractor']
