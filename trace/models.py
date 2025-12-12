import time
import hashlib
import uuid
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class Note:
    content: str
    timestamp: float = field(default_factory=time.time)
    note_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_hash: str = ""
    signature: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    iocs: List[str] = field(default_factory=list)

    def extract_tags(self):
        """Extract hashtags from content (case-insensitive, stored lowercase)"""
        # Match hashtags: # followed by word characters
        tag_pattern = r'#(\w+)'
        matches = re.findall(tag_pattern, self.content)
        # Convert to lowercase and remove duplicates while preserving order
        seen = set()
        self.tags = []
        for tag in matches:
            tag_lower = tag.lower()
            if tag_lower not in seen:
                seen.add(tag_lower)
                self.tags.append(tag_lower)

    def extract_iocs(self):
        """Extract Indicators of Compromise from content"""
        seen = set()
        self.iocs = []

        # IPv4 addresses
        ipv4_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        for match in re.findall(ipv4_pattern, self.content):
            if match not in seen:
                seen.add(match)
                self.iocs.append(match)

        # IPv6 addresses (supports compressed format)
        ipv6_pattern = r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b(?:[0-9a-fA-F]{1,4}:)*::(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{0,4}\b'
        for match in re.findall(ipv6_pattern, self.content):
            if match not in seen:
                seen.add(match)
                self.iocs.append(match)

        # URLs (check before domains to prevent double-matching)
        url_pattern = r'https?://[^\s]+'
        for match in re.findall(url_pattern, self.content):
            if match not in seen:
                seen.add(match)
                self.iocs.append(match)

        # Domain names (basic pattern)
        domain_pattern = r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
        for match in re.findall(domain_pattern, self.content):
            # Filter out common false positives
            if match not in seen and not match.startswith('example.'):
                seen.add(match)
                self.iocs.append(match)

        # SHA256 hashes (64 hex chars) - check longest first
        sha256_pattern = r'\b[a-fA-F0-9]{64}\b'
        for match in re.findall(sha256_pattern, self.content):
            if match not in seen:
                seen.add(match)
                self.iocs.append(match)

        # SHA1 hashes (40 hex chars)
        sha1_pattern = r'\b[a-fA-F0-9]{40}\b'
        for match in re.findall(sha1_pattern, self.content):
            if match not in seen:
                seen.add(match)
                self.iocs.append(match)

        # MD5 hashes (32 hex chars)
        md5_pattern = r'\b[a-fA-F0-9]{32}\b'
        for match in re.findall(md5_pattern, self.content):
            if match not in seen:
                seen.add(match)
                self.iocs.append(match)

        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.findall(email_pattern, self.content):
            if match not in seen:
                seen.add(match)
                self.iocs.append(match)

    def calculate_hash(self):
        # We hash the content + timestamp to ensure integrity of 'when' it was said
        data = f"{self.timestamp}:{self.content}".encode('utf-8')
        self.content_hash = hashlib.sha256(data).hexdigest()

    @staticmethod
    def extract_iocs_from_text(text):
        """Extract IOCs from text and return as list of (ioc, type) tuples"""
        iocs = []
        seen = set()

        # IPv4 addresses
        ipv4_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        for match in re.findall(ipv4_pattern, text):
            if match not in seen:
                seen.add(match)
                iocs.append((match, 'ipv4'))

        # IPv6 addresses (supports compressed format)
        ipv6_pattern = r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b(?:[0-9a-fA-F]{1,4}:)*::(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{0,4}\b'
        for match in re.findall(ipv6_pattern, text):
            if match not in seen:
                seen.add(match)
                iocs.append((match, 'ipv6'))

        # URLs (check before domains to avoid double-matching)
        url_pattern = r'https?://[^\s]+'
        for match in re.findall(url_pattern, text):
            if match not in seen:
                seen.add(match)
                iocs.append((match, 'url'))

        # Domain names (basic pattern)
        domain_pattern = r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
        for match in re.findall(domain_pattern, text):
            # Filter out common false positives and already seen URLs
            if match not in seen and not match.startswith('example.'):
                seen.add(match)
                iocs.append((match, 'domain'))

        # SHA256 hashes (64 hex chars) - check before SHA1 and MD5
        sha256_pattern = r'\b[a-fA-F0-9]{64}\b'
        for match in re.findall(sha256_pattern, text):
            if match not in seen:
                seen.add(match)
                iocs.append((match, 'sha256'))

        # SHA1 hashes (40 hex chars) - check before MD5
        sha1_pattern = r'\b[a-fA-F0-9]{40}\b'
        for match in re.findall(sha1_pattern, text):
            if match not in seen:
                seen.add(match)
                iocs.append((match, 'sha1'))

        # MD5 hashes (32 hex chars)
        md5_pattern = r'\b[a-fA-F0-9]{32}\b'
        for match in re.findall(md5_pattern, text):
            if match not in seen:
                seen.add(match)
                iocs.append((match, 'md5'))

        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.findall(email_pattern, text):
            if match not in seen:
                seen.add(match)
                iocs.append((match, 'email'))

        return iocs

    @staticmethod
    def extract_iocs_with_positions(text):
        """Extract IOCs with their positions for highlighting. Returns list of (text, start, end, type) tuples"""
        import re
        highlights = []
        covered_ranges = set()

        def overlaps(start, end):
            """Check if range overlaps with any covered range"""
            for covered_start, covered_end in covered_ranges:
                if not (end <= covered_start or start >= covered_end):
                    return True
            return False

        def add_highlight(match, ioc_type):
            """Add highlight if it doesn't overlap with existing ones"""
            start, end = match.start(), match.end()
            if not overlaps(start, end):
                highlights.append((match.group(), start, end, ioc_type))
                covered_ranges.add((start, end))

        # IPv4 addresses
        ipv4_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        for match in re.finditer(ipv4_pattern, text):
            add_highlight(match, 'ipv4')

        # IPv6 addresses (supports compressed format)
        ipv6_pattern = r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b(?:[0-9a-fA-F]{1,4}:)*::(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{0,4}\b'
        for match in re.finditer(ipv6_pattern, text):
            add_highlight(match, 'ipv6')

        # URLs (check before domains to prevent double-matching)
        for match in re.finditer(r'https?://[^\s]+', text):
            add_highlight(match, 'url')

        # Domain names
        for match in re.finditer(r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b', text):
            if not match.group().startswith('example.'):
                add_highlight(match, 'domain')

        # SHA256 hashes (64 hex chars) - check longest first
        for match in re.finditer(r'\b[a-fA-F0-9]{64}\b', text):
            add_highlight(match, 'sha256')

        # SHA1 hashes (40 hex chars)
        for match in re.finditer(r'\b[a-fA-F0-9]{40}\b', text):
            add_highlight(match, 'sha1')

        # MD5 hashes (32 hex chars)
        for match in re.finditer(r'\b[a-fA-F0-9]{32}\b', text):
            add_highlight(match, 'md5')

        # Email addresses
        for match in re.finditer(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
            add_highlight(match, 'email')

        return highlights

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
