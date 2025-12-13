"""IOC (Indicator of Compromise) extraction logic for notes"""

import re
from typing import List, Tuple


class IOCExtractor:
    """Extract Indicators of Compromise from text content"""

    # Regex patterns for different IOC types
    SHA256_PATTERN = r'\b[a-fA-F0-9]{64}\b'
    SHA1_PATTERN = r'\b[a-fA-F0-9]{40}\b'
    MD5_PATTERN = r'\b[a-fA-F0-9]{32}\b'
    IPV4_PATTERN = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    IPV6_PATTERN = r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b(?:[0-9a-fA-F]{1,4}:)*::(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{0,4}\b'
    URL_PATTERN = r'https?://[^\s<>\"\']+(?<![.,;:!?\)\]\}])'
    DOMAIN_PATTERN = r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    @staticmethod
    def extract_iocs(text: str) -> List[str]:
        """
        Extract IOCs from text and return as simple list

        Args:
            text: The text to extract IOCs from

        Returns:
            List of unique IOC strings
        """
        seen = set()
        covered_ranges = set()
        iocs = []

        def add_ioc_if_not_covered(match_obj):
            """Add IOC if its range doesn't overlap with already covered ranges"""
            start, end = match_obj.start(), match_obj.end()
            # Check if this range overlaps with any covered range
            for covered_start, covered_end in covered_ranges:
                if not (end <= covered_start or start >= covered_end):
                    return False  # Overlaps, don't add
            ioc_text = match_obj.group()
            if ioc_text not in seen:
                seen.add(ioc_text)
                covered_ranges.add((start, end))
                iocs.append(ioc_text)
                return True
            return False

        # Process in order of priority to avoid false positives
        # SHA256 hashes (64 hex chars) - check longest first to avoid substring matches
        for match in re.finditer(IOCExtractor.SHA256_PATTERN, text):
            add_ioc_if_not_covered(match)

        # SHA1 hashes (40 hex chars)
        for match in re.finditer(IOCExtractor.SHA1_PATTERN, text):
            add_ioc_if_not_covered(match)

        # MD5 hashes (32 hex chars)
        for match in re.finditer(IOCExtractor.MD5_PATTERN, text):
            add_ioc_if_not_covered(match)

        # IPv4 addresses
        for match in re.finditer(IOCExtractor.IPV4_PATTERN, text):
            add_ioc_if_not_covered(match)

        # IPv6 addresses (supports compressed format)
        for match in re.finditer(IOCExtractor.IPV6_PATTERN, text):
            add_ioc_if_not_covered(match)

        # URLs (check before domains to prevent double-matching)
        for match in re.finditer(IOCExtractor.URL_PATTERN, text):
            add_ioc_if_not_covered(match)

        # Domain names (basic pattern)
        for match in re.finditer(IOCExtractor.DOMAIN_PATTERN, text):
            # Filter out common false positives
            if not match.group().startswith('example.'):
                add_ioc_if_not_covered(match)

        # Email addresses
        for match in re.finditer(IOCExtractor.EMAIL_PATTERN, text):
            add_ioc_if_not_covered(match)

        return iocs

    @staticmethod
    def extract_iocs_with_types(text: str) -> List[Tuple[str, str]]:
        """
        Extract IOCs from text and return as list of (ioc, type) tuples

        Args:
            text: The text to extract IOCs from

        Returns:
            List of (ioc_text, ioc_type) tuples
        """
        iocs = []
        seen = set()
        covered_ranges = set()

        def add_ioc_if_not_covered(match_obj, ioc_type):
            """Add IOC if its range doesn't overlap with already covered ranges"""
            start, end = match_obj.start(), match_obj.end()
            # Check if this range overlaps with any covered range
            for covered_start, covered_end in covered_ranges:
                if not (end <= covered_start or start >= covered_end):
                    return False  # Overlaps, don't add
            ioc_text = match_obj.group()
            if ioc_text not in seen:
                seen.add(ioc_text)
                covered_ranges.add((start, end))
                iocs.append((ioc_text, ioc_type))
                return True
            return False

        # Process in priority order: longest hashes first
        for match in re.finditer(IOCExtractor.SHA256_PATTERN, text):
            add_ioc_if_not_covered(match, 'sha256')

        for match in re.finditer(IOCExtractor.SHA1_PATTERN, text):
            add_ioc_if_not_covered(match, 'sha1')

        for match in re.finditer(IOCExtractor.MD5_PATTERN, text):
            add_ioc_if_not_covered(match, 'md5')

        for match in re.finditer(IOCExtractor.IPV4_PATTERN, text):
            add_ioc_if_not_covered(match, 'ipv4')

        for match in re.finditer(IOCExtractor.IPV6_PATTERN, text):
            add_ioc_if_not_covered(match, 'ipv6')

        # URLs (check before domains to avoid double-matching)
        for match in re.finditer(IOCExtractor.URL_PATTERN, text):
            add_ioc_if_not_covered(match, 'url')

        # Domain names
        for match in re.finditer(IOCExtractor.DOMAIN_PATTERN, text):
            # Filter out common false positives
            if not match.group().startswith('example.'):
                add_ioc_if_not_covered(match, 'domain')

        # Email addresses
        for match in re.finditer(IOCExtractor.EMAIL_PATTERN, text):
            add_ioc_if_not_covered(match, 'email')

        return iocs

    @staticmethod
    def extract_iocs_with_positions(text: str) -> List[Tuple[str, int, int, str]]:
        """
        Extract IOCs with their positions for highlighting

        Args:
            text: The text to extract IOCs from

        Returns:
            List of (ioc_text, start_pos, end_pos, ioc_type) tuples
        """
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

        # Process in priority order: longest hashes first to avoid substring matches
        for match in re.finditer(IOCExtractor.SHA256_PATTERN, text):
            add_highlight(match, 'sha256')

        for match in re.finditer(IOCExtractor.SHA1_PATTERN, text):
            add_highlight(match, 'sha1')

        for match in re.finditer(IOCExtractor.MD5_PATTERN, text):
            add_highlight(match, 'md5')

        for match in re.finditer(IOCExtractor.IPV4_PATTERN, text):
            add_highlight(match, 'ipv4')

        for match in re.finditer(IOCExtractor.IPV6_PATTERN, text):
            add_highlight(match, 'ipv6')

        # URLs (check before domains to prevent double-matching)
        for match in re.finditer(IOCExtractor.URL_PATTERN, text):
            add_highlight(match, 'url')

        # Domain names
        for match in re.finditer(IOCExtractor.DOMAIN_PATTERN, text):
            if not match.group().startswith('example.'):
                add_highlight(match, 'domain')

        # Email addresses
        for match in re.finditer(IOCExtractor.EMAIL_PATTERN, text):
            add_highlight(match, 'email')

        return highlights

    @staticmethod
    def classify_ioc(ioc: str) -> str:
        """
        Classify an IOC by its type

        Args:
            ioc: The IOC string to classify

        Returns:
            The IOC type as a string
        """
        if re.fullmatch(IOCExtractor.SHA256_PATTERN, ioc):
            return 'sha256'
        elif re.fullmatch(IOCExtractor.SHA1_PATTERN, ioc):
            return 'sha1'
        elif re.fullmatch(IOCExtractor.MD5_PATTERN, ioc):
            return 'md5'
        elif re.fullmatch(IOCExtractor.IPV4_PATTERN, ioc):
            return 'ipv4'
        elif re.fullmatch(IOCExtractor.IPV6_PATTERN, ioc):
            return 'ipv6'
        elif re.fullmatch(IOCExtractor.EMAIL_PATTERN, ioc):
            return 'email'
        elif re.fullmatch(IOCExtractor.URL_PATTERN, ioc):
            return 'url'
        elif re.fullmatch(IOCExtractor.DOMAIN_PATTERN, ioc):
            return 'domain'
        else:
            return 'unknown'
