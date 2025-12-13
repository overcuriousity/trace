"""Color pair initialization and constants for TUI"""

import curses


class ColorPairs:
    """Color pair constants"""
    SELECTION = 1  # Black on cyan
    SUCCESS = 2  # Green on black
    WARNING = 3  # Yellow on black
    ERROR = 4  # Red on black
    HEADER = 5  # Cyan on black
    METADATA = 6  # White on black
    BORDER = 7  # Blue on black
    TAG = 8  # Magenta on black
    IOC_SELECTED = 9  # Red on cyan
    TAG_SELECTED = 10  # Yellow on cyan


def init_colors():
    """Initialize color pairs for the TUI"""
    curses.start_color()
    if curses.has_colors():
        # Selection / Highlight
        curses.init_pair(ColorPairs.SELECTION, curses.COLOR_BLACK, curses.COLOR_CYAN)
        # Success / Active indicators
        curses.init_pair(ColorPairs.SUCCESS, curses.COLOR_GREEN, curses.COLOR_BLACK)
        # Info / Warnings
        curses.init_pair(ColorPairs.WARNING, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        # Errors / Critical / IOCs
        curses.init_pair(ColorPairs.ERROR, curses.COLOR_RED, curses.COLOR_BLACK)
        # Headers / Titles (bright cyan)
        curses.init_pair(ColorPairs.HEADER, curses.COLOR_CYAN, curses.COLOR_BLACK)
        # Metadata / Secondary text (dim)
        curses.init_pair(ColorPairs.METADATA, curses.COLOR_WHITE, curses.COLOR_BLACK)
        # Borders / Separators (blue)
        curses.init_pair(ColorPairs.BORDER, curses.COLOR_BLUE, curses.COLOR_BLACK)
        # Tags (magenta)
        curses.init_pair(ColorPairs.TAG, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        # IOCs on selected background (red on cyan)
        curses.init_pair(ColorPairs.IOC_SELECTED, curses.COLOR_RED, curses.COLOR_CYAN)
        # Tags on selected background (yellow on cyan)
        curses.init_pair(ColorPairs.TAG_SELECTED, curses.COLOR_YELLOW, curses.COLOR_CYAN)
