"""Tag extraction logic for notes"""

import re


class TagExtractor:
    """Extract hashtags from text content"""

    TAG_PATTERN = r'#(\w+)'

    @staticmethod
    def extract_tags(text: str) -> list[str]:
        """
        Extract hashtags from content (case-insensitive, stored lowercase)

        Args:
            text: The text to extract tags from

        Returns:
            List of unique tags in lowercase, preserving order
        """
        # Match hashtags: # followed by word characters
        matches = re.findall(TagExtractor.TAG_PATTERN, text)

        # Convert to lowercase and remove duplicates while preserving order
        seen = set()
        tags = []
        for tag in matches:
            tag_lower = tag.lower()
            if tag_lower not in seen:
                seen.add(tag_lower)
                tags.append(tag_lower)

        return tags
