"""Visual constants for consistent TUI layout and styling"""


class Layout:
    """Screen layout constants"""
    HEADER_Y = 0
    HEADER_X = 2
    CONTENT_START_Y = 2
    CONTENT_INDENT = 4
    FOOTER_OFFSET_FROM_BOTTOM = 3
    BORDER_OFFSET_FROM_BOTTOM = 2


class Spacing:
    """Spacing and padding constants"""
    SECTION_VERTICAL_GAP = 2
    ITEM_VERTICAL_GAP = 1
    DIALOG_MARGIN = 4
    HORIZONTAL_PADDING = 6  # width - 6 for truncation
    HASH_DISPLAY_PADDING = 20  # width - 20


class ColumnWidths:
    """Fixed column widths for list displays"""
    TAG_COLUMN = 30
    IOC_COLUMN = 50
    CONTENT_PREVIEW = 50
    NOTE_PREVIEW = 60


class DialogSize:
    """Standard dialog dimensions (width, height)"""
    SMALL = (40, 8)   # Confirm dialogs
    MEDIUM = (60, 15)  # Settings, single input
    LARGE = (70, 20)   # Multiline, help


class Icons:
    """Unicode symbols used throughout UI"""
    ACTIVE = "●"
    INACTIVE = "○"
    DIAMOND = "◆"
    SQUARE = "■"
    SMALL_SQUARE = "▪"
    ARROW_RIGHT = "▸"
    WARNING = "⚠"
    HASH = "⌗"
    FILTER = "◈"
    VERIFIED = "✓"
    FAILED = "✗"
    UNSIGNED = "?"
    SEPARATOR_H = "─"
    SEPARATOR_V = "│"
    SEPARATOR_GROUP = "│"  # For grouping footer commands
    BOX_TL = "┌"
    BOX_BL = "└"
    # Box drawing for improved empty states
    BOX_DOUBLE_TL = "╔"
    BOX_DOUBLE_TR = "╗"
    BOX_DOUBLE_BL = "╚"
    BOX_DOUBLE_BR = "╝"
    BOX_DOUBLE_H = "═"
    BOX_DOUBLE_V = "║"


class Timing:
    """Timing constants"""
    FLASH_MESSAGE_DURATION = 3  # seconds
