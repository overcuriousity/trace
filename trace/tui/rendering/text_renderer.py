"""Text rendering utilities with highlighting support"""

import curses
import re
from ...models import Note
from .colors import ColorPairs


class TextRenderer:
    """Utility class for rendering text with highlights"""

    @staticmethod
    def safe_truncate(text, max_width, ellipsis="..."):
        """
        Safely truncate text to fit within max_width, handling Unicode characters.
        Uses a conservative approach to avoid curses display errors.
        """
        if not text:
            return text

        # Try to fit the text as-is
        if len(text) <= max_width:
            return text

        # Need to truncate - account for ellipsis
        if max_width <= len(ellipsis):
            return ellipsis[:max_width]

        # Truncate conservatively (character by character) to handle multi-byte UTF-8
        target_len = max_width - len(ellipsis)
        truncated = text[:target_len]

        # Encode and check actual byte length to be safe with UTF-8
        # If it's too long, trim further
        while len(truncated) > 0:
            try:
                # Test if this will fit when displayed
                test_str = truncated + ellipsis
                if len(test_str) <= max_width:
                    return test_str
            except:
                pass
            # Trim one more character
            truncated = truncated[:-1]

        return ellipsis[:max_width]

    @staticmethod
    def display_line_with_highlights(screen, y, x_start, line, is_selected=False):
        """
        Display a line with intelligent highlighting.
        - IOCs are highlighted with ColorPairs.ERROR (red)
        - Tags are highlighted with ColorPairs.WARNING (yellow)
        - Selection background is ColorPairs.SELECTION (cyan) for non-IOC text
        - IOC highlighting takes priority over selection
        """
        # Extract IOCs and tags
        highlights = []

        # Get IOCs with positions
        for text, start, end, ioc_type in Note.extract_iocs_with_positions(line):
            highlights.append((text, start, end, 'ioc'))

        # Get tags
        for match in re.finditer(r'#\w+', line):
            highlights.append((match.group(), match.start(), match.end(), 'tag'))

        # Sort by position and remove overlaps (IOCs take priority over tags)
        highlights.sort(key=lambda x: x[1])
        deduplicated = []
        last_end = -1
        for text, start, end, htype in highlights:
            if start >= last_end:
                deduplicated.append((text, start, end, htype))
                last_end = end
        highlights = deduplicated

        if not highlights:
            # No highlights - use selection color if selected
            if is_selected:
                screen.attron(curses.color_pair(ColorPairs.SELECTION))
                screen.addstr(y, x_start, line)
                screen.attroff(curses.color_pair(ColorPairs.SELECTION))
            else:
                screen.addstr(y, x_start, line)
            return

        # Display with intelligent highlighting
        x_pos = x_start
        last_pos = 0

        for text, start, end, htype in highlights:
            # Add text before this highlight
            if start > last_pos:
                text_before = line[last_pos:start]
                if is_selected:
                    screen.attron(curses.color_pair(ColorPairs.SELECTION))
                    screen.addstr(y, x_pos, text_before)
                    screen.attroff(curses.color_pair(ColorPairs.SELECTION))
                else:
                    screen.addstr(y, x_pos, text_before)
                x_pos += len(text_before)

            # Add highlighted text
            if htype == 'ioc':
                # IOC highlighting: red on cyan if selected, red on black otherwise
                if is_selected:
                    screen.attron(curses.color_pair(ColorPairs.IOC_SELECTED) | curses.A_BOLD)
                    screen.addstr(y, x_pos, text)
                    screen.attroff(curses.color_pair(ColorPairs.IOC_SELECTED) | curses.A_BOLD)
                else:
                    screen.attron(curses.color_pair(ColorPairs.ERROR) | curses.A_BOLD)
                    screen.addstr(y, x_pos, text)
                    screen.attroff(curses.color_pair(ColorPairs.ERROR) | curses.A_BOLD)
            else:  # tag
                # Tag highlighting: yellow on cyan if selected, yellow on black otherwise
                if is_selected:
                    screen.attron(curses.color_pair(ColorPairs.TAG_SELECTED))
                    screen.addstr(y, x_pos, text)
                    screen.attroff(curses.color_pair(ColorPairs.TAG_SELECTED))
                else:
                    screen.attron(curses.color_pair(ColorPairs.WARNING))
                    screen.addstr(y, x_pos, text)
                    screen.attroff(curses.color_pair(ColorPairs.WARNING))

            x_pos += len(text)
            last_pos = end

        # Add remaining text
        if last_pos < len(line):
            text_after = line[last_pos:]
            if is_selected:
                screen.attron(curses.color_pair(ColorPairs.SELECTION))
                screen.addstr(y, x_pos, text_after)
                screen.attroff(curses.color_pair(ColorPairs.SELECTION))
            else:
                screen.addstr(y, x_pos, text_after)
