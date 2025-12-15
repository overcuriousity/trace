"""Visual constants for consistent TUI layout and styling"""


class Layout:
    """Screen layout constants"""
    HEADER_Y = 0
    HEADER_X = 2
    CONTENT_START_Y = 2
    CONTENT_INDENT = 4
    FOOTER_OFFSET_FROM_BOTTOM = 3
    BORDER_OFFSET_FROM_BOTTOM = 2
    STATUS_LINE_OFFSET_FROM_BOTTOM = 1  # height - 1 for status bar
    NOTE_DETAIL_BOTTOM_RESERVE = 6  # height - 6 for note detail view


class Spacing:
    """Spacing and padding constants"""
    SECTION_VERTICAL_GAP = 2
    ITEM_VERTICAL_GAP = 1
    DIALOG_MARGIN = 4
    HORIZONTAL_PADDING = 6  # width - 6 for truncation
    HASH_DISPLAY_PADDING = 20  # width - 20
    HASH_SHORT_PADDING = 12  # width - 12 for shorter hash displays
    EMPTY_STATE_PADDING = 8  # width - 8 for empty state boxes
    STATUS_BAR_PADDING = 2  # width - 2 for status bar


class ColumnWidths:
    """Column widths for list displays - can be percentage-based"""
    TAG_COLUMN_MIN = 30
    IOC_COLUMN_MIN = 50
    CONTENT_PREVIEW_MIN = 50
    NOTE_PREVIEW_MIN = 60

    @staticmethod
    def get_tag_width(terminal_width):
        """Get responsive tag column width (40% of terminal or min 30)"""
        return max(ColumnWidths.TAG_COLUMN_MIN, int(terminal_width * 0.4))

    @staticmethod
    def get_ioc_width(terminal_width):
        """Get responsive IOC column width (50% of terminal or min 50)"""
        return max(ColumnWidths.IOC_COLUMN_MIN, int(terminal_width * 0.5))

    @staticmethod
    def get_content_preview_width(terminal_width):
        """Get responsive content preview width (50% of terminal or min 50)"""
        return max(ColumnWidths.CONTENT_PREVIEW_MIN, int(terminal_width * 0.5))


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
