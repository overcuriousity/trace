import curses
import time
from typing import Optional, List
from .models import Case, Evidence, Note
from .storage import Storage, StateManager

class TUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.storage = Storage()
        self.state_manager = StateManager()
        self.current_view = "case_list"  # case_list, case_detail, evidence_detail, tags_list, tag_notes_list, note_detail, ioc_list, ioc_notes_list, help
        self.selected_index = 0
        self.scroll_offset = 0 # Index of the first item to display
        self.cases = self.storage.cases

        # State for navigation
        self.active_case: Optional[Case] = None
        self.active_evidence: Optional[Evidence] = None

        # State for tags view
        self.current_tags = []  # List of (tag, count) tuples
        self.current_tag = None  # Currently selected tag
        self.tag_notes = []  # Notes with the current tag
        self.current_note = None  # Currently viewed note in detail

        # State for IOC view
        self.current_iocs = []  # List of (ioc, count, type) tuples
        self.current_ioc = None  # Currently selected IOC
        self.ioc_notes = []  # Notes with the current IOC

        # Filtering
        self.filter_mode = False
        self.filter_query = ""

        # Flash Message
        self.flash_message = ""
        self.flash_time = 0

        # UI Config
        curses.curs_set(0) # Hide cursor
        curses.start_color()
        if curses.has_colors():
            # Selection / Highlight
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
            # Success / Active indicators
            curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
            # Info / Warnings
            curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            # Errors / Critical / IOCs
            curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
            # Headers / Titles (bright cyan)
            curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)
            # Metadata / Secondary text (dim)
            curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLACK)
            # Borders / Separators (blue)
            curses.init_pair(7, curses.COLOR_BLUE, curses.COLOR_BLACK)
            # Tags (magenta)
            curses.init_pair(8, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
            # IOCs on selected background (red on cyan)
            curses.init_pair(9, curses.COLOR_RED, curses.COLOR_CYAN)
            # Tags on selected background (yellow on cyan)
            curses.init_pair(10, curses.COLOR_YELLOW, curses.COLOR_CYAN)

        self.height, self.width = stdscr.getmaxyx()

        # Load initial active state
        active_state = self.state_manager.get_active()
        self.global_active_case_id = active_state.get("case_id")
        self.global_active_evidence_id = active_state.get("evidence_id")

    def run(self):
        while True:
            self.height, self.width = self.stdscr.getmaxyx()
            self.stdscr.clear()

            self.draw_header()
            self.draw_status_bar()

            # Content area bounds
            self.content_y = 2
            self.content_h = self.height - 4 # Reserve top 2, bottom 2

            if self.current_view == "case_list":
                self.draw_case_list()
            elif self.current_view == "case_detail":
                self.draw_case_detail()
            elif self.current_view == "evidence_detail":
                self.draw_evidence_detail()
            elif self.current_view == "tags_list":
                self.draw_tags_list()
            elif self.current_view == "tag_notes_list":
                self.draw_tag_notes_list()
            elif self.current_view == "ioc_list":
                self.draw_ioc_list()
            elif self.current_view == "ioc_notes_list":
                self.draw_ioc_notes_list()
            elif self.current_view == "note_detail":
                self.draw_note_detail()
            elif self.current_view == "help":
                self.draw_help()

            self.stdscr.refresh()

            key = self.stdscr.getch()
            if not self.handle_input(key):
                break

    def show_message(self, msg):
        self.flash_message = msg
        self.flash_time = time.time()

    def _get_all_tags_with_counts(self, notes):
        """Get all tags from notes with their occurrence counts"""
        tag_counts = {}
        for note in notes:
            for tag in note.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        # Sort by count (descending), then alphabetically
        sorted_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
        return sorted_tags  # Returns list of (tag, count) tuples

    def _get_notes_with_tag(self, notes, tag):
        """Get all notes containing a specific tag (case-insensitive)"""
        tag_lower = tag.lower()
        return [note for note in notes if tag_lower in note.tags]

    def _get_all_iocs_with_counts(self, notes):
        """Get all IOCs from notes with their occurrence counts and types"""
        ioc_data = {}  # ioc -> (count, type)
        for note in notes:
            for ioc in note.iocs:
                if ioc not in ioc_data:
                    # Determine IOC type
                    ioc_type = self._classify_ioc(ioc)
                    ioc_data[ioc] = [1, ioc_type]
                else:
                    ioc_data[ioc][0] += 1
        # Sort by count (descending), then alphabetically
        sorted_iocs = sorted(ioc_data.items(), key=lambda x: (-x[1][0], x[0]))
        # Return list of (ioc, count, type) tuples
        return [(ioc, count, ioc_type) for ioc, (count, ioc_type) in sorted_iocs]

    def _classify_ioc(self, ioc):
        """Classify IOC type based on pattern"""
        import re
        if re.match(r'^[a-fA-F0-9]{32}$', ioc):
            return 'MD5'
        elif re.match(r'^[a-fA-F0-9]{40}$', ioc):
            return 'SHA1'
        elif re.match(r'^[a-fA-F0-9]{64}$', ioc):
            return 'SHA256'
        elif re.match(r'^https?://', ioc):
            return 'URL'
        elif '@' in ioc:
            return 'EMAIL'
        elif re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', ioc):
            return 'IPv4'
        elif ':' in ioc and any(c in '0123456789abcdefABCDEF' for c in ioc):
            return 'IPv6'
        else:
            return 'DOMAIN'

    def _get_notes_with_ioc(self, notes, ioc):
        """Get all notes containing a specific IOC"""
        return [note for note in notes if ioc in note.iocs]

    def _get_context_notes(self):
        """Get all notes from the current context (case or evidence)"""
        if self.active_evidence:
            # Evidence context - only evidence notes
            return list(self.active_evidence.notes)
        elif self.active_case:
            # Case context - case notes + all evidence notes
            all_notes = list(self.active_case.notes)
            for ev in self.active_case.evidence:
                all_notes.extend(ev.notes)
            return all_notes
        return []

    def handle_open_tags(self):
        """Open the tags list view for the current context"""
        if self.current_view not in ["case_detail", "evidence_detail"]:
            return

        # Get all notes from current context
        all_notes = self._get_context_notes()

        if not all_notes:
            self.show_message("No notes found in current context.")
            return

        # Get tags sorted by count
        self.current_tags = self._get_all_tags_with_counts(all_notes)

        if not self.current_tags:
            self.show_message("No tags found in notes.")
            return

        # Switch to tags list view
        self.current_view = "tags_list"
        self.selected_index = 0
        self.scroll_offset = 0

    def handle_open_iocs(self):
        """Open the IOCs list view for the current context"""
        if self.current_view not in ["case_detail", "evidence_detail"]:
            return

        # Get all notes from current context
        all_notes = self._get_context_notes()

        if not all_notes:
            self.show_message("No notes found in current context.")
            return

        # Get IOCs sorted by count
        self.current_iocs = self._get_all_iocs_with_counts(all_notes)

        if not self.current_iocs:
            self.show_message("No IOCs found in notes.")
            return

        # Switch to IOCs list view
        self.current_view = "ioc_list"
        self.selected_index = 0
        self.scroll_offset = 0

    def _safe_truncate(self, text, max_width, ellipsis="..."):
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

    def _display_line_with_highlights(self, y, x_start, line, is_selected=False, win=None):
        """
        Display a line with intelligent highlighting.
        - IOCs are highlighted with color_pair(4) (red)
        - Tags are highlighted with color_pair(3) (yellow)
        - Selection background is color_pair(1) (cyan) for non-IOC text
        - IOC highlighting takes priority over selection
        """
        import re
        from .models import Note
        
        # Use provided window or default to main screen
        screen = win if win is not None else self.stdscr
        
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
                screen.attron(curses.color_pair(1))
                screen.addstr(y, x_start, line)
                screen.attroff(curses.color_pair(1))
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
                    screen.attron(curses.color_pair(1))
                    screen.addstr(y, x_pos, text_before)
                    screen.attroff(curses.color_pair(1))
                else:
                    screen.addstr(y, x_pos, text_before)
                x_pos += len(text_before)
            
            # Add highlighted text
            if htype == 'ioc':
                # IOC highlighting: red on cyan if selected, red on black otherwise
                if is_selected:
                    screen.attron(curses.color_pair(9) | curses.A_BOLD)
                    screen.addstr(y, x_pos, text)
                    screen.attroff(curses.color_pair(9) | curses.A_BOLD)
                else:
                    screen.attron(curses.color_pair(4) | curses.A_BOLD)
                    screen.addstr(y, x_pos, text)
                    screen.attroff(curses.color_pair(4) | curses.A_BOLD)
            else:  # tag
                # Tag highlighting: yellow on cyan if selected, yellow on black otherwise
                if is_selected:
                    screen.attron(curses.color_pair(10))
                    screen.addstr(y, x_pos, text)
                    screen.attroff(curses.color_pair(10))
                else:
                    screen.attron(curses.color_pair(3))
                    screen.addstr(y, x_pos, text)
                    screen.attroff(curses.color_pair(3))
            
            x_pos += len(text)
            last_pos = end
        
        # Add remaining text
        if last_pos < len(line):
            text_after = line[last_pos:]
            if is_selected:
                screen.attron(curses.color_pair(1))
                screen.addstr(y, x_pos, text_after)
                screen.attroff(curses.color_pair(1))
            else:
                screen.addstr(y, x_pos, text_after)

    def draw_header(self):
        # Modern header with icon and better styling
        title = "◆ trace"
        subtitle = "Forensic Investigation Notes"

        # Top border line
        try:
            self.stdscr.attron(curses.color_pair(7))
            self.stdscr.addstr(0, 0, "─" * self.width)
            self.stdscr.attroff(curses.color_pair(7))
        except curses.error:
            pass

        # Title line with gradient effect
        try:
            # Icon and main title
            self.stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
            self.stdscr.addstr(0, 2, title)
            self.stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)

            # Subtitle
            self.stdscr.attron(curses.color_pair(6))
            self.stdscr.addstr(0, 2 + len(title) + 2, subtitle)
            self.stdscr.attroff(curses.color_pair(6))
        except curses.error:
            pass

    def draw_status_bar(self):
        # Determine status text
        status_text = ""
        attr = curses.color_pair(1)

        # Check for flash message (display for 3 seconds)
        icon = ""
        if self.flash_message and (time.time() - self.flash_time < 3):
            if "Failed" in self.flash_message or "Error" in self.flash_message:
                icon = "✗"
                attr = curses.color_pair(4)  # Red
            else:
                icon = "✓"
                attr = curses.color_pair(2)  # Green
            status_text = f"{icon} {self.flash_message}"
        elif self.filter_mode:
            icon = "◈"
            status_text = f"{icon} Filter: {self.filter_query}"
            attr = curses.color_pair(3)
        else:
            # Active context display
            if self.global_active_case_id:
                c = self.storage.get_case(self.global_active_case_id)
                if c:
                    icon = "●"
                    status_text = f"{icon} {c.case_number}"
                    attr = curses.color_pair(2)  # Green for active
                    if self.global_active_evidence_id:
                        _, ev = self.storage.find_evidence(self.global_active_evidence_id)
                        if ev:
                            status_text += f"  ▸  {ev.name}"
            else:
                icon = "○"
                status_text = f"{icon} No active context"
                attr = curses.color_pair(6) | curses.A_DIM

        # Truncate if too long
        max_status_len = self.width - 2
        if len(status_text) > max_status_len:
            status_text = status_text[:max_status_len-1] + "…"

        # Bottom line with border
        try:
            # Border line above status
            self.stdscr.attron(curses.color_pair(7))
            self.stdscr.addstr(self.height - 2, 0, "─" * self.width)
            self.stdscr.attroff(curses.color_pair(7))

            # Status text
            self.stdscr.attron(attr)
            self.stdscr.addstr(self.height - 1, 1, status_text)
            remaining = self.width - len(status_text) - 2
            if remaining > 0:
                self.stdscr.addstr(self.height - 1, len(status_text) + 1, " " * remaining)
            self.stdscr.attroff(attr)
        except curses.error:
            pass # Ignore bottom-right corner write errors

    def _update_scroll(self, total_items):
        # Viewport height calculation (approximate lines available for list)
        list_h = self.content_h - 2 # Title + padding
        if list_h < 1: list_h = 1

        # Ensure selected index is visible
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + list_h:
            self.scroll_offset = self.selected_index - list_h + 1

        return list_h

    def _get_filtered_list(self, items, key_attr=None, key_attr2=None):
        if not self.filter_query:
            return items
        q = self.filter_query.lower()
        filtered = []
        for item in items:
            # Check primary attribute
            val1 = getattr(item, key_attr, "") if key_attr else ""
            val2 = getattr(item, key_attr2, "") if key_attr2 else ""
            if q in str(val1).lower() or q in str(val2).lower():
                filtered.append(item)
        return filtered

    def draw_case_list(self):
        # Header with icon
        self.stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
        self.stdscr.addstr(2, 2, "■ Cases")
        self.stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)

        if not self.cases:
            self.stdscr.attron(curses.color_pair(3))
            self.stdscr.addstr(4, 4, "┌─ No cases found")
            self.stdscr.addstr(5, 4, "└─ Press 'N' to create your first case")
            self.stdscr.attroff(curses.color_pair(3))
            self.stdscr.addstr(self.height - 3, 2, "[N] New Case  [q] Quit", curses.color_pair(3))
            return

        display_cases = self._get_filtered_list(self.cases, "case_number", "name")

        # Show count
        self.stdscr.attron(curses.color_pair(6) | curses.A_DIM)
        self.stdscr.addstr(2, 12, f"({len(display_cases)} total)")
        self.stdscr.attroff(curses.color_pair(6) | curses.A_DIM)

        list_h = self._update_scroll(len(display_cases))

        for i in range(list_h):
            idx = self.scroll_offset + i
            if idx >= len(display_cases):
                break

            case = display_cases[idx]
            y = 4 + i

            # Calculate total note count and tags (case notes + all evidence notes)
            all_notes = list(case.notes)
            for ev in case.evidence:
                all_notes.extend(ev.notes)
            total_notes = len(all_notes)

            # Count unique tags
            all_tags = self._get_all_tags_with_counts(all_notes)
            tag_count = len(all_tags)

            # Active indicator with better icon
            is_active = case.case_id == self.global_active_case_id and not self.global_active_evidence_id
            prefix = "● " if is_active else "○ "

            # Build display string
            display_str = f"{prefix}{case.case_number}"
            if case.name:
                display_str += f"  │  {case.name}"

            # Metadata indicators with icons
            metadata = []
            if len(case.evidence) > 0:
                metadata.append(f"▪ {len(case.evidence)} ev")
            if total_notes > 0:
                metadata.append(f"◆ {total_notes}")
            if tag_count > 0:
                metadata.append(f"# {tag_count}")

            if metadata:
                display_str += "  │  " + "  ".join(metadata)

            # Truncate safely for Unicode
            display_str = self._safe_truncate(display_str, self.width - 6)

            if idx == self.selected_index:
                # Highlighted selection
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(y, 4, display_str)
                self.stdscr.attroff(curses.color_pair(1))
            else:
                # Normal item - color the active indicator if active
                if is_active:
                    self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                    self.stdscr.addstr(y, 4, prefix)
                    self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
                    # Rest of line in normal color
                    self.stdscr.addstr(display_str[len(prefix):])
                else:
                    self.stdscr.addstr(y, 4, display_str)

        if not display_cases and self.cases:
            self.stdscr.attron(curses.color_pair(3))
            self.stdscr.addstr(4, 4, "┌─ No cases match filter")
            self.stdscr.addstr(5, 4, "└─ Press ESC to clear filter")
            self.stdscr.attroff(curses.color_pair(3))

        self.stdscr.addstr(self.height - 3, 2, "[N] New Case  [n] Add Note  [Enter] Select  [a] Active  [d] Delete  [/] Filter  [s] Settings  [?] Help", curses.color_pair(3))

    def draw_case_detail(self):
        if not self.active_case: return

        case_note_count = len(self.active_case.notes)

        # Header with case info
        self.stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
        self.stdscr.addstr(2, 2, f"■ {self.active_case.case_number}")
        self.stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)

        if self.active_case.name:
            self.stdscr.attron(curses.color_pair(6))
            self.stdscr.addstr(f"  │  {self.active_case.name}")
            self.stdscr.attroff(curses.color_pair(6))

        # Metadata section
        y_pos = 3
        if self.active_case.investigator:
            self.stdscr.attron(curses.color_pair(6) | curses.A_DIM)
            self.stdscr.addstr(y_pos, 4, f"◆ Investigator:")
            self.stdscr.attroff(curses.color_pair(6) | curses.A_DIM)
            self.stdscr.addstr(f" {self.active_case.investigator}")
            y_pos += 1

        self.stdscr.attron(curses.color_pair(6) | curses.A_DIM)
        self.stdscr.addstr(y_pos, 4, f"◆ Case Notes:")
        self.stdscr.attroff(curses.color_pair(6) | curses.A_DIM)
        note_color = curses.color_pair(2) if case_note_count > 0 else curses.color_pair(6)
        self.stdscr.attron(note_color)
        self.stdscr.addstr(f" {case_note_count}")
        self.stdscr.attroff(note_color)
        y_pos += 1

        # Split screen between evidence and case notes
        # Allocate space: half for evidence, half for case notes (if both exist)
        available_space = self.content_h - 5
        case_notes = self.active_case.notes
        evidence_list = self._get_filtered_list(self.active_case.evidence, "name", "description")

        # Determine context: are we selecting evidence or notes?
        # Evidence items are indices 0 to len(evidence)-1
        # Case notes are indices len(evidence) to len(evidence)+len(notes)-1
        total_items = len(evidence_list) + len(case_notes)

        # Determine what's selected
        selecting_evidence = self.selected_index < len(evidence_list)

        # Evidence section header
        if y_pos < self.height - 3:
            self.stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
            self.stdscr.addstr(y_pos, 2, "▪ Evidence")
            self.stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)

            # Show count
            self.stdscr.attron(curses.color_pair(6) | curses.A_DIM)
            self.stdscr.addstr(y_pos, 14, f"({len(evidence_list)} items)")
            self.stdscr.attroff(curses.color_pair(6) | curses.A_DIM)

        y_pos += 1

        if not evidence_list:
            # Check if we have space to display the message
            if y_pos + 2 < self.height - 2:
                self.stdscr.attron(curses.color_pair(3))
                self.stdscr.addstr(y_pos + 1, 4, "┌─ No evidence items")
                self.stdscr.addstr(y_pos + 2, 4, "└─ Press 'N' to add evidence")
                self.stdscr.attroff(curses.color_pair(3))
        else:
            # Scrolling for evidence list
            # Calculate remaining space
            remaining_space = self.content_h - (y_pos - 2)
            list_h = max(1, remaining_space)

            self._update_scroll(total_items)

            # Calculate space for evidence
            evidence_space = min(len(evidence_list), available_space // 2) if case_notes else available_space

            self._update_scroll(total_items)

            # Calculate which evidence items to display
            # If selecting evidence, scroll just enough to keep it visible
            # If selecting a case note, show evidence from the beginning
            if selecting_evidence:
                # Keep selection visible: scroll up if needed, scroll down if needed
                if self.selected_index < 0:
                    evidence_scroll_offset = 0
                elif self.selected_index >= evidence_space:
                    # Scroll down only as much as needed to show the selected item at the bottom
                    evidence_scroll_offset = self.selected_index - evidence_space + 1
                else:
                    evidence_scroll_offset = 0
            else:
                evidence_scroll_offset = 0

            for i in range(evidence_space):
                evidence_idx = evidence_scroll_offset + i
                if evidence_idx < 0 or evidence_idx >= len(evidence_list):
                    continue

                ev = evidence_list[evidence_idx]
                y = y_pos + i
                if y >= self.height - 3:  # Don't overflow into status bar
                    break

                note_count = len(ev.notes)

                # Count tags
                ev_tags = self._get_all_tags_with_counts(ev.notes)
                tag_count = len(ev_tags)

                # Count IOCs
                ev_iocs = self._get_all_iocs_with_counts(ev.notes)
                ioc_count = len(ev_iocs)

                # Active indicator
                is_active = ev.evidence_id == self.global_active_evidence_id
                prefix = "● " if is_active else "○ "

                # Build display string
                display_str = f"{prefix}{ev.name}"

                # Metadata with icons
                metadata = []
                if note_count > 0:
                    metadata.append(f"◆ {note_count}")
                if tag_count > 0:
                    metadata.append(f"# {tag_count}")
                if ioc_count > 0:
                    metadata.append(f"⚠ {ioc_count}")

                # Add hash indicator if source hash exists
                source_hash = ev.metadata.get("source_hash")
                if source_hash:
                    hash_preview = source_hash[:6] + "…"
                    metadata.append(f"⌗ {hash_preview}")

                if metadata:
                    display_str += "  │  " + "  ".join(metadata)

                # Truncate safely
                base_display = self._safe_truncate(display_str, self.width - 6)

                # Check if this evidence item is selected
                if evidence_idx == self.selected_index:
                    # Highlighted selection
                    self.stdscr.attron(curses.color_pair(1))
                    self.stdscr.addstr(y, 4, base_display)
                    self.stdscr.attroff(curses.color_pair(1))
                else:
                    # Normal item - highlight active indicator if active
                    if is_active:
                        self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                        self.stdscr.addstr(y, 4, prefix)
                        self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
                        # Rest in normal, but highlight IOC warning in red
                        rest_of_line = base_display[len(prefix):]
                        if ioc_count > 0 and "⚠" in rest_of_line:
                            # Split and color the IOC part
                            parts = rest_of_line.split("⚠")
                            self.stdscr.addstr(parts[0])
                            self.stdscr.attron(curses.color_pair(4))
                            self.stdscr.addstr("⚠" + parts[1])
                            self.stdscr.attroff(curses.color_pair(4))
                        else:
                            self.stdscr.addstr(rest_of_line)
                    else:
                        # Not active - still highlight IOC warning
                        if ioc_count > 0 and "⚠" in base_display:
                            parts = base_display.split("⚠")
                            self.stdscr.addstr(y, 4, parts[0])
                            self.stdscr.attron(curses.color_pair(4))
                            self.stdscr.addstr("⚠" + parts[1])
                            self.stdscr.attroff(curses.color_pair(4))
                        else:
                            self.stdscr.addstr(y, 4, base_display)

            y_pos += evidence_space

        # Case Notes section
        if case_notes:
            y_pos += 2
            if y_pos < self.height - 3:
                self.stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
                self.stdscr.addstr(y_pos, 2, "▪ Case Notes")
                self.stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
                self.stdscr.attron(curses.color_pair(6) | curses.A_DIM)
                self.stdscr.addstr(y_pos, 16, f"({len(case_notes)} notes)")
                self.stdscr.attroff(curses.color_pair(6) | curses.A_DIM)
            y_pos += 1

            # Calculate remaining space for case notes
            remaining_space = self.content_h - (y_pos - 2)
            notes_space = max(1, remaining_space)

            # Calculate which notes to display
            if selecting_evidence:
                notes_scroll_offset = 0
            else:
                notes_scroll_offset = max(0, (self.selected_index - len(evidence_list)) - notes_space // 2)

            for i in range(notes_space):
                note_idx = notes_scroll_offset + i
                if note_idx >= len(case_notes):
                    break

                note = case_notes[note_idx]
                y = y_pos + i
                
                # Check if we're out of bounds
                if y >= self.height - 3:
                    break

                # Format note content
                note_content = note.content.replace('\n', ' ').replace('\r', ' ')
                display_str = f"- {note_content}"
                display_str = self._safe_truncate(display_str, self.width - 6)

                # Display with smart highlighting (IOCs take priority over selection)
                item_idx = len(evidence_list) + note_idx
                is_selected = (item_idx == self.selected_index)
                self._display_line_with_highlights(y, 4, display_str, is_selected)

        self.stdscr.addstr(self.height - 3, 2, "[N] New Evidence  [n] Add Note  [t] Tags  [i] IOCs  [v] View Notes  [a] Active  [d] Delete  [?] Help", curses.color_pair(3))

    def draw_evidence_detail(self):
        if not self.active_evidence: return

        current_y = 2
        self.stdscr.addstr(current_y, 2, f"Evidence: {self.active_evidence.name}", curses.A_BOLD)
        current_y += 1

        self.stdscr.addstr(current_y, 2, f"Desc: {self.active_evidence.description}")
        current_y += 1

        # Display source hash if available
        source_hash = self.active_evidence.metadata.get("source_hash")
        if source_hash:
            # Truncate hash if too long for display
            hash_display = self._safe_truncate(source_hash, self.width - 20)
            self.stdscr.addstr(current_y, 2, f"Source Hash: {hash_display}", curses.color_pair(3))
            current_y += 1

        # Count and display IOCs
        ev_iocs = self._get_all_iocs_with_counts(self.active_evidence.notes)
        ioc_count = len(ev_iocs)
        if ioc_count > 0:
            ioc_display = f"({ioc_count} IOCs detected)"
            self.stdscr.attron(curses.color_pair(4))  # Red
            self.stdscr.addstr(current_y, 2, ioc_display)
            self.stdscr.attroff(curses.color_pair(4))
            current_y += 1

        current_y += 1  # Blank line before notes
        self.stdscr.addstr(current_y, 2, f"Notes ({len(self.active_evidence.notes)}):", curses.A_UNDERLINE)
        current_y += 1

        # Just show last N notes that fit
        list_h = self.content_h - (current_y - 2)  # Adjust for dynamic header
        start_y = current_y

        notes = self.active_evidence.notes
        display_notes = notes[-list_h:] if len(notes) > list_h else notes

        # Update scroll for note selection
        if display_notes:
            self._update_scroll(len(display_notes))

        for i, note in enumerate(display_notes):
            idx = self.scroll_offset + i
            if idx >= len(display_notes):
                break
            note = display_notes[idx]
            # Replace newlines with spaces for single-line display
            note_content = note.content.replace('\n', ' ').replace('\r', ' ')
            display_str = f"- {note_content}"
            # Truncate safely for Unicode
            display_str = self._safe_truncate(display_str, self.width - 6)

            # Display with smart highlighting (IOCs take priority over selection)
            is_selected = (idx == self.selected_index)
            self._display_line_with_highlights(start_y + i, 4, display_str, is_selected)

        self.stdscr.addstr(self.height - 3, 2, "[n] Add Note  [t] Tags  [i] IOCs  [v] View Notes  [a] Active  [d] Delete Note  [?] Help", curses.color_pair(3))

    def draw_tags_list(self):
        """Draw the tags list view showing all tags sorted by occurrence count"""
        context = "Case" if self.current_view == "tags_list" and self.active_case else "Evidence"
        context_name = self.active_case.case_number if self.active_case else (self.active_evidence.name if self.active_evidence else "")

        self.stdscr.addstr(2, 2, f"Tags for {context}: {context_name}", curses.A_BOLD)
        self.stdscr.addstr(3, 2, "─" * (self.width - 4))

        if not self.current_tags:
            self.stdscr.addstr(5, 4, "No tags found.", curses.color_pair(3))
            self.stdscr.addstr(self.height - 3, 2, "[b] Back", curses.color_pair(3))
            return

        list_h = self._update_scroll(len(self.current_tags))

        for i in range(list_h):
            idx = self.scroll_offset + i
            if idx >= len(self.current_tags):
                break

            tag, count = self.current_tags[idx]
            y = 5 + i

            display_str = f"#{tag}".ljust(30) + f"({count} notes)"
            display_str = self._safe_truncate(display_str, self.width - 6)

            if idx == self.selected_index:
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(y, 4, display_str)
                self.stdscr.attroff(curses.color_pair(1))
            else:
                self.stdscr.addstr(y, 4, display_str)

        self.stdscr.addstr(self.height - 3, 2, "[Enter] View Notes  [b] Back", curses.color_pair(3))

    def draw_tag_notes_list(self):
        """Draw compact list of notes containing the selected tag"""
        self.stdscr.addstr(2, 2, f"Notes tagged with #{self.current_tag} ({len(self.tag_notes)})", curses.A_BOLD)
        self.stdscr.addstr(3, 2, "─" * (self.width - 4))

        if not self.tag_notes:
            self.stdscr.addstr(5, 4, "No notes found.", curses.color_pair(3))
            self.stdscr.addstr(self.height - 3, 2, "[b] Back", curses.color_pair(3))
            return

        list_h = self._update_scroll(len(self.tag_notes))

        for i in range(list_h):
            idx = self.scroll_offset + i
            if idx >= len(self.tag_notes):
                break

            note = self.tag_notes[idx]
            y = 5 + i

            timestamp_str = time.ctime(note.timestamp)
            # Replace newlines for compact display
            content_preview = note.content.replace('\n', ' ').replace('\r', ' ')
            if len(content_preview) > 50:
                content_preview = content_preview[:50] + "..."

            display_str = f"[{timestamp_str}] {content_preview}"
            display_str = self._safe_truncate(display_str, self.width - 6)

            if idx == self.selected_index:
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(y, 4, display_str)
                self.stdscr.attroff(curses.color_pair(1))
            else:
                self.stdscr.addstr(y, 4, display_str)

        self.stdscr.addstr(self.height - 3, 2, "[Enter] Expand  [b] Back", curses.color_pair(3))

    def draw_ioc_list(self):
        """Draw the IOC list view showing all IOCs sorted by occurrence count"""
        context = "Case" if self.current_view == "ioc_list" and self.active_case else "Evidence"
        context_name = self.active_case.case_number if self.active_case else (self.active_evidence.name if self.active_evidence else "")

        self.stdscr.addstr(2, 2, f"IOCs for {context}: {context_name}", curses.A_BOLD)
        self.stdscr.addstr(3, 2, "─" * (self.width - 4))

        if not self.current_iocs:
            self.stdscr.addstr(5, 4, "No IOCs found.", curses.color_pair(3))
            self.stdscr.addstr(self.height - 3, 2, "[b] Back  [e] Export", curses.color_pair(3))
            return

        list_h = self._update_scroll(len(self.current_iocs))

        for i in range(list_h):
            idx = self.scroll_offset + i
            if idx >= len(self.current_iocs):
                break

            ioc, count, ioc_type = self.current_iocs[idx]
            y = 5 + i

            # Show IOC with type indicator and count in red
            display_str = f"{ioc} [{ioc_type}]".ljust(50) + f"({count} notes)"
            display_str = self._safe_truncate(display_str, self.width - 6)

            if idx == self.selected_index:
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(y, 4, display_str)
                self.stdscr.attroff(curses.color_pair(1))
            else:
                # Use red color for IOCs
                self.stdscr.attron(curses.color_pair(4))
                self.stdscr.addstr(y, 4, display_str)
                self.stdscr.attroff(curses.color_pair(4))

        self.stdscr.addstr(self.height - 3, 2, "[Enter] View Notes  [e] Export  [b] Back", curses.color_pair(3))

    def draw_ioc_notes_list(self):
        """Draw compact list of notes containing the selected IOC"""
        self.stdscr.addstr(2, 2, f"Notes with IOC: {self.current_ioc} ({len(self.ioc_notes)})", curses.A_BOLD)
        self.stdscr.addstr(3, 2, "─" * (self.width - 4))

        if not self.ioc_notes:
            self.stdscr.addstr(5, 4, "No notes found.", curses.color_pair(3))
            self.stdscr.addstr(self.height - 3, 2, "[b] Back", curses.color_pair(3))
            return

        list_h = self._update_scroll(len(self.ioc_notes))

        for i in range(list_h):
            idx = self.scroll_offset + i
            if idx >= len(self.ioc_notes):
                break

            note = self.ioc_notes[idx]
            y = 5 + i

            timestamp_str = time.ctime(note.timestamp)
            content_preview = note.content[:60].replace('\n', ' ') + "..." if len(note.content) > 60 else note.content.replace('\n', ' ')

            display_str = f"[{timestamp_str}] {content_preview}"
            display_str = self._safe_truncate(display_str, self.width - 6)

            if idx == self.selected_index:
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(y, 4, display_str)
                self.stdscr.attroff(curses.color_pair(1))
            else:
                self.stdscr.addstr(y, 4, display_str)

        self.stdscr.addstr(self.height - 3, 2, "[Enter] Expand  [b] Back", curses.color_pair(3))

    def draw_note_detail(self):
        """Draw expanded view of a single note with all details"""
        if not self.current_note:
            return

        self.stdscr.addstr(2, 2, "Note Details", curses.A_BOLD)
        self.stdscr.addstr(3, 2, "─" * (self.width - 4))

        current_y = 5

        # Timestamp
        timestamp_str = time.ctime(self.current_note.timestamp)
        self.stdscr.addstr(current_y, 2, f"Timestamp: {timestamp_str}")
        current_y += 1

        # Tags
        if self.current_note.tags:
            tags_str = " ".join([f"#{tag}" for tag in self.current_note.tags])
            self.stdscr.addstr(current_y, 2, "Tags: ", curses.A_BOLD)
            self.stdscr.addstr(current_y, 8, tags_str, curses.color_pair(3))
            current_y += 1

        current_y += 1

        # Content with tag and IOC highlighting
        self.stdscr.addstr(current_y, 2, "Content:", curses.A_BOLD)
        current_y += 1

        # Display content with highlighted tags and IOCs
        content_lines = self.current_note.content.split('\n')
        max_content_lines = self.content_h - (current_y - 2) - 6  # Reserve space for hash/sig

        for line in content_lines[:max_content_lines]:
            if current_y >= self.height - 6:
                break

            # Highlight both tags and IOCs in the content
            display_line = self._safe_truncate(line, self.width - 6)
            
            # Display with highlighting (no selection in detail view)
            try:
                self._display_line_with_highlights(current_y, 4, display_line, is_selected=False)
            except curses.error:
                pass

            current_y += 1

        current_y += 1

        # Hash
        if self.current_note.content_hash:
            hash_display = self._safe_truncate(self.current_note.content_hash, self.width - 12)
            self.stdscr.addstr(current_y, 2, f"Hash: {hash_display}", curses.A_DIM)
            current_y += 1

        # Signature
        if self.current_note.signature:
            self.stdscr.addstr(current_y, 2, "Signature: [GPG signed]", curses.color_pair(2))
            current_y += 1

        self.stdscr.addstr(self.height - 3, 2, "[b] Back", curses.color_pair(3))

    def draw_help(self):
        """Draw the help screen with keyboard shortcuts and features"""
        self.stdscr.addstr(2, 2, "trace - Help & Keyboard Shortcuts", curses.A_BOLD)
        self.stdscr.addstr(3, 2, "═" * (self.width - 4))

        # Build help content as a list of lines
        help_lines = []

        # General Navigation
        help_lines.append(("GENERAL NAVIGATION", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  Arrow Keys       Navigate lists and menus", curses.A_NORMAL))
        help_lines.append(("  Enter            Select item / Open", curses.A_NORMAL))
        help_lines.append(("  b                Go back to previous view", curses.A_NORMAL))
        help_lines.append(("  q                Quit application", curses.A_NORMAL))
        help_lines.append(("  ?  or  h         Show this help screen", curses.A_NORMAL))
        help_lines.append(("", curses.A_NORMAL))

        # Case List View
        help_lines.append(("CASE LIST VIEW", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  N                Create new case", curses.A_NORMAL))
        help_lines.append(("  n                Add note to active context", curses.A_NORMAL))
        help_lines.append(("  a                Set selected case as active", curses.A_NORMAL))
        help_lines.append(("  d                Delete selected case (with confirmation)", curses.A_NORMAL))
        help_lines.append(("  /                Filter cases by case number or name", curses.A_NORMAL))
        help_lines.append(("  s                Open settings menu", curses.A_NORMAL))
        help_lines.append(("  Enter            Open case details", curses.A_NORMAL))
        help_lines.append(("", curses.A_NORMAL))

        # Case Detail View
        help_lines.append(("CASE DETAIL VIEW", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  N                Create new evidence item", curses.A_NORMAL))
        help_lines.append(("  n                Add note to case", curses.A_NORMAL))
        help_lines.append(("  t                View tags across case and all evidence", curses.A_NORMAL))
        help_lines.append(("  i                View IOCs across case and all evidence", curses.A_NORMAL))
        help_lines.append(("  v                View all case notes with IOC highlighting", curses.A_NORMAL))
        help_lines.append(("  a                Set case (or selected evidence) as active", curses.A_NORMAL))
        help_lines.append(("  d                Delete selected evidence item or note", curses.A_NORMAL))
        help_lines.append(("  /                Filter evidence by name or description", curses.A_NORMAL))
        help_lines.append(("  Enter            Open evidence details or jump to note", curses.A_NORMAL))
        help_lines.append(("", curses.A_NORMAL))

        # Evidence Detail View
        help_lines.append(("EVIDENCE DETAIL VIEW", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  n                Add note to evidence", curses.A_NORMAL))
        help_lines.append(("  t                View tags for this evidence", curses.A_NORMAL))
        help_lines.append(("  i                View IOCs for this evidence", curses.A_NORMAL))
        help_lines.append(("  v                View all evidence notes with IOC highlighting", curses.A_NORMAL))
        help_lines.append(("  a                Set evidence as active context", curses.A_NORMAL))
        help_lines.append(("  d                Delete selected note", curses.A_NORMAL))
        help_lines.append(("  Enter            Jump to selected note in full view", curses.A_NORMAL))
        help_lines.append(("", curses.A_NORMAL))

        # Tags View
        help_lines.append(("TAGS VIEW", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  Enter            View all notes with selected tag", curses.A_NORMAL))
        help_lines.append(("  b                Return to previous view", curses.A_NORMAL))
        help_lines.append(("", curses.A_NORMAL))

        # IOCs View
        help_lines.append(("IOCs VIEW", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  Enter            View all notes containing selected IOC", curses.A_NORMAL))
        help_lines.append(("  e                Export IOCs to text file", curses.A_NORMAL))
        help_lines.append(("  b                Return to previous view", curses.A_NORMAL))
        help_lines.append(("", curses.A_NORMAL))

        # Note Editor
        help_lines.append(("NOTE EDITOR", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  Arrow Keys       Navigate within text", curses.A_NORMAL))
        help_lines.append(("  Enter            New line (multi-line notes supported)", curses.A_NORMAL))
        help_lines.append(("  Backspace        Delete character", curses.A_NORMAL))
        help_lines.append(("  Ctrl+G           Submit note", curses.A_NORMAL))
        help_lines.append(("  Esc              Cancel note creation", curses.A_NORMAL))
        help_lines.append(("", curses.A_NORMAL))

        # Features
        help_lines.append(("FEATURES", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  Active Context   Set with 'a' key - enables CLI quick notes", curses.A_NORMAL))
        help_lines.append(("                   Run: trace \"your note text\"", curses.A_DIM))
        help_lines.append(("  Tags             Use #hashtag in notes for auto-tagging", curses.A_NORMAL))
        help_lines.append(("                   Highlighted in cyan throughout the interface", curses.A_DIM))
        help_lines.append(("  IOCs             Auto-extracts IPs, domains, URLs, hashes, emails", curses.A_NORMAL))
        help_lines.append(("                   Highlighted in red in full note views", curses.A_DIM))
        help_lines.append(("  Note Navigation  Press Enter on any note to view with highlighting", curses.A_NORMAL))
        help_lines.append(("                   Selected note auto-centered and highlighted", curses.A_DIM))
        help_lines.append(("  Integrity        All notes SHA256 hashed + optional GPG signing", curses.A_NORMAL))
        help_lines.append(("  GPG Settings     Press 's' to toggle signing & select GPG key", curses.A_NORMAL))
        help_lines.append(("  Source Hash      Store evidence file hashes for chain of custody", curses.A_NORMAL))
        help_lines.append(("  Export           Run: trace --export --output report.md", curses.A_DIM))
        help_lines.append(("", curses.A_NORMAL))

        # Data Location
        help_lines.append(("DATA STORAGE", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  All data:        ~/.trace/data.json", curses.A_NORMAL))
        help_lines.append(("  Active context:  ~/.trace/state", curses.A_NORMAL))
        help_lines.append(("  Settings:        ~/.trace/settings.json", curses.A_NORMAL))
        help_lines.append(("  IOC exports:     ~/.trace/exports/", curses.A_NORMAL))
        help_lines.append(("", curses.A_NORMAL))

        # Demo Case Note
        help_lines.append(("GETTING STARTED", curses.A_BOLD | curses.color_pair(2)))
        help_lines.append(("  Demo Case        A sample case (DEMO-2024-001) showcases all features", curses.A_NORMAL))
        help_lines.append(("                   Explore evidence, notes, tags, and IOCs", curses.A_DIM))
        help_lines.append(("                   Delete it when ready: select and press 'd'", curses.A_DIM))

        # Calculate scrolling
        total_lines = len(help_lines)
        list_h = self.content_h - 2  # Account for header

        # Update scroll based on selection (treat as line navigation)
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + list_h:
            self.scroll_offset = self.selected_index - list_h + 1

        # Ensure scroll_offset is within bounds
        max_scroll = max(0, total_lines - list_h)
        if self.scroll_offset > max_scroll:
            self.scroll_offset = max_scroll
        if self.scroll_offset < 0:
            self.scroll_offset = 0

        # Draw visible help lines
        y_offset = 5
        for i in range(list_h):
            line_idx = self.scroll_offset + i
            if line_idx >= total_lines:
                break

            text, attr = help_lines[line_idx]
            y = y_offset + i

            if y >= self.height - 3:
                break

            # Truncate if needed
            display_text = self._safe_truncate(text, self.width - 4)

            try:
                self.stdscr.addstr(y, 2, display_text, attr)
            except curses.error:
                pass  # Ignore display errors at screen boundaries

        # Show scroll indicator if content doesn't fit
        if total_lines > list_h:
            scroll_info = f"[{self.scroll_offset + 1}-{min(self.scroll_offset + list_h, total_lines)} of {total_lines}]"
            try:
                self.stdscr.addstr(self.height - 3, self.width - len(scroll_info) - 2, scroll_info, curses.color_pair(3))
            except curses.error:
                pass

        self.stdscr.addstr(self.height - 3, 2, "[Arrow Keys] Scroll  [b/q/?] Close", curses.color_pair(3))

    def handle_input(self, key):
        if self.filter_mode:
            return self.handle_filter_input(key)

        # Help screen - accessible from anywhere
        if key == ord('?') or key == ord('h'):
            # Save previous view to return to it
            if not hasattr(self, 'previous_view'):
                self.previous_view = self.current_view
            else:
                # If already in help, don't update previous_view
                if self.current_view != "help":
                    self.previous_view = self.current_view

            self.current_view = "help"
            self.selected_index = 0
            self.scroll_offset = 0
            return True

        if key == ord('q'):
            # If in help view, just close help instead of quitting
            if self.current_view == "help":
                self.current_view = getattr(self, 'previous_view', 'case_list')
                self.selected_index = 0
                self.scroll_offset = 0
                return True
            return False

        # Filter toggle
        if key == ord('/'):
            # Filter works on list views: case_list and case_detail (evidence list)
            if self.current_view in ["case_list", "case_detail"]:
                self.filter_mode = True
                return True

        # Navigation
        if key == curses.KEY_UP:
            if self.current_view == "help":
                # Scrolling help content
                if self.selected_index > 0:
                    self.selected_index -= 1
                return True
            if self.selected_index > 0:
                self.selected_index -= 1
        elif key == curses.KEY_DOWN:
            # Calculate max_idx based on current filtered view
            max_idx = 0
            if self.current_view == "case_list":
                filtered = self._get_filtered_list(self.cases, "case_number", "name")
                max_idx = len(filtered) - 1
            elif self.current_view == "case_detail" and self.active_case:
                # Total items = evidence + case notes
                case_notes = self.active_case.notes
                filtered = self._get_filtered_list(self.active_case.evidence, "name", "description")
                max_idx = len(filtered) + len(case_notes) - 1
            elif self.current_view == "evidence_detail" and self.active_evidence:
                # Navigate through notes in evidence detail view
                max_idx = len(self.active_evidence.notes) - 1
            elif self.current_view == "tags_list":
                max_idx = len(self.current_tags) - 1
            elif self.current_view == "tag_notes_list":
                max_idx = len(self.tag_notes) - 1
            elif self.current_view == "ioc_list":
                max_idx = len(self.current_iocs) - 1
            elif self.current_view == "ioc_notes_list":
                max_idx = len(self.ioc_notes) - 1
            elif self.current_view == "help":
                # Scrolling help content - just increment scroll_offset directly
                # Help view uses scroll_offset for scrolling, not selected_index
                list_h = self.content_h - 2
                # We'll increment selected_index but it's just used for scroll calculation
                max_idx = 100  # Arbitrary large number for help content
                self.selected_index += 1
                return True

            if max_idx < 0: max_idx = 0 # Handle empty list
            if self.selected_index < max_idx:
                self.selected_index += 1

        # Enter / Select
        elif key == curses.KEY_ENTER or key in [10, 13]:
            if self.current_view == "case_list":
                filtered = self._get_filtered_list(self.cases, "case_number", "name")
                if filtered:
                    self.active_case = filtered[self.selected_index]
                    self.current_view = "case_detail"
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.filter_query = ""
            elif self.current_view == "evidence_detail" and self.active_evidence:
                # Check if a note is selected
                notes = self.active_evidence.notes
                list_h = self.content_h - 5
                display_notes = notes[-list_h:] if len(notes) > list_h else notes
                
                if display_notes and self.selected_index < len(display_notes):
                    # Calculate the actual note index in the full list
                    note_offset = len(notes) - len(display_notes)
                    actual_note_index = note_offset + self.selected_index
                    # Open notes view and jump to selected note
                    self._highlight_note_idx = actual_note_index
                    self.view_evidence_notes(highlight_note_index=actual_note_index)
                    delattr(self, '_highlight_note_idx') # Reset filter on view change
            elif self.current_view == "case_detail":
                if self.active_case:
                    case_notes = self.active_case.notes
                    filtered = self._get_filtered_list(self.active_case.evidence, "name", "description")

                    # Check if selecting evidence or note
                    # Evidence items come first (indices 0 to len(filtered)-1)
                    # Case notes come second (indices len(filtered) to len(filtered)+len(case_notes)-1)
                    if self.selected_index < len(filtered):
                        # Selected evidence - navigate to evidence detail
                        self.active_evidence = filtered[self.selected_index]
                        self.current_view = "evidence_detail"
                        self.selected_index = 0
                        self.filter_query = ""
                    elif case_notes and self.selected_index - len(filtered) < len(case_notes):
                        # Selected a note - show note detail view
                        note_idx = self.selected_index - len(filtered)
                        self.current_note = case_notes[note_idx]
                        self.previous_view = "case_detail"
                        self.current_view = "note_detail"
                        self.filter_query = ""
            elif self.current_view == "tags_list":
                # Enter tag -> show notes with that tag
                if self.current_tags and self.selected_index < len(self.current_tags):
                    tag, _ = self.current_tags[self.selected_index]
                    self.current_tag = tag
                    # Get all notes (case + evidence if in case view, or just evidence if in evidence view)
                    all_notes = self._get_context_notes()
                    self.tag_notes = self._get_notes_with_tag(all_notes, tag)
                    # Sort by timestamp descending
                    self.tag_notes.sort(key=lambda n: n.timestamp, reverse=True)
                    self.current_view = "tag_notes_list"
                    self.selected_index = 0
                    self.scroll_offset = 0
            elif self.current_view == "tag_notes_list":
                # Enter note -> show expanded view
                if self.tag_notes and self.selected_index < len(self.tag_notes):
                    self.current_note = self.tag_notes[self.selected_index]
                    self.previous_view = "tag_notes_list"
                    self.current_view = "note_detail"
                    self.selected_index = 0
                    self.scroll_offset = 0
            elif self.current_view == "ioc_list":
                # Enter IOC -> show notes with that IOC
                if self.current_iocs and self.selected_index < len(self.current_iocs):
                    ioc, _, _ = self.current_iocs[self.selected_index]
                    self.current_ioc = ioc
                    # Get all notes from current context
                    all_notes = self._get_context_notes()
                    self.ioc_notes = self._get_notes_with_ioc(all_notes, ioc)
                    # Sort by timestamp descending
                    self.ioc_notes.sort(key=lambda n: n.timestamp, reverse=True)
                    self.current_view = "ioc_notes_list"
                    self.selected_index = 0
                    self.scroll_offset = 0
            elif self.current_view == "ioc_notes_list":
                # Enter note -> show expanded view
                if self.ioc_notes and self.selected_index < len(self.ioc_notes):
                    self.current_note = self.ioc_notes[self.selected_index]
                    self.previous_view = "ioc_notes_list"
                    self.current_view = "note_detail"
                    self.selected_index = 0
                    self.scroll_offset = 0

        # Back
        elif key == ord('b'):
            if self.current_view == "help":
                # Return to previous view
                self.current_view = getattr(self, 'previous_view', 'case_list')
                self.selected_index = 0
                self.scroll_offset = 0
            elif self.current_view == "note_detail":
                # Return to the view we came from
                self.current_view = getattr(self, 'previous_view', 'case_detail')
                self.current_note = None
                self.selected_index = 0
                self.scroll_offset = 0
            elif self.current_view == "tag_notes_list":
                self.current_view = "tags_list"
                self.tag_notes = []
                self.current_tag = None
                self.selected_index = 0
                self.scroll_offset = 0
            elif self.current_view == "ioc_notes_list":
                self.current_view = "ioc_list"
                self.ioc_notes = []
                self.current_ioc = None
                self.selected_index = 0
                self.scroll_offset = 0
            elif self.current_view == "ioc_list":
                # Go back to the view we came from (case_detail or evidence_detail)
                if self.active_evidence:
                    self.current_view = "evidence_detail"
                elif self.active_case:
                    self.current_view = "case_detail"
                self.current_iocs = []
                self.selected_index = 0
                self.scroll_offset = 0
            elif self.current_view == "tags_list":
                # Go back to the view we came from (case_detail or evidence_detail)
                if self.active_evidence:
                    self.current_view = "evidence_detail"
                elif self.active_case:
                    self.current_view = "case_detail"
                self.current_tags = []
                self.selected_index = 0
                self.scroll_offset = 0
            elif self.current_view == "evidence_detail":
                self.current_view = "case_detail"
                self.active_evidence = None
                self.selected_index = 0
                self.scroll_offset = 0
                self.filter_query = ""
            elif self.current_view == "case_detail":
                self.current_view = "case_list"
                self.active_case = None
                self.selected_index = 0
                self.scroll_offset = 0
                self.filter_query = ""

        # Export IOCs
        elif key == ord('e'):
            if self.current_view in ["ioc_list", "ioc_notes_list"]:
                self.export_iocs()

        # Set Active
        elif key == ord('a'):
            self._handle_set_active()

        # Settings
        elif key == ord('s') and self.current_view == "case_list":
             self.dialog_settings()

        # Actions
        elif key == ord('N') and self.current_view == "case_list":
            self.dialog_new_case()
        elif key == ord('N') and self.current_view == "case_detail":
            self.dialog_new_evidence()
        elif key == ord('n'):
            self.dialog_add_note()
        elif key == ord('t'):
            self.handle_open_tags()
        elif key == ord('i'):
            self.handle_open_iocs()
        elif key == ord('v'):
            if self.current_view == "case_detail":
                self.view_case_notes()
            elif self.current_view == "evidence_detail":
                self.view_evidence_notes()

        # Delete
        elif key == ord('d'):
            self.handle_delete()

        return True

    def handle_filter_input(self, key):
        if key == 27: # ESC
            self.filter_mode = False
            self.filter_query = ""
            self.selected_index = 0
            self.scroll_offset = 0
            return True
        elif key == curses.KEY_ENTER or key in [10, 13]:
            self.filter_mode = False
            self.selected_index = 0
            self.scroll_offset = 0
            return True
        elif key == curses.KEY_BACKSPACE or key == 127:
            if len(self.filter_query) > 0:
                self.filter_query = self.filter_query[:-1]
                self.selected_index = 0
        elif 32 <= key <= 126:
            self.filter_query += chr(key)
            self.selected_index = 0

        return True

    def _handle_set_active(self):
        if self.current_view == "case_list":
            filtered = self._get_filtered_list(self.cases, "case_number", "name")
            if filtered:
                case = filtered[self.selected_index]
                self.state_manager.set_active(case_id=case.case_id, evidence_id=None)
                self.global_active_case_id = case.case_id
                self.global_active_evidence_id = None
                self.show_message(f"Active Case: {case.case_number}")

        elif self.current_view == "case_detail" and self.active_case:
            case_notes = self.active_case.notes
            filtered = self._get_filtered_list(self.active_case.evidence, "name", "description")

            # Evidence is displayed first (indices 0 to len(evidence)-1)
            # Case notes are displayed second (indices len(evidence) to len(evidence)+len(notes)-1)
            if self.selected_index < len(filtered):
                # Selected evidence - set it as active
                ev = filtered[self.selected_index]
                self.state_manager.set_active(case_id=self.active_case.case_id, evidence_id=ev.evidence_id)
                self.global_active_case_id = self.active_case.case_id
                self.global_active_evidence_id = ev.evidence_id
                self.show_message(f"Active: {ev.name}")
            elif case_notes and self.selected_index - len(filtered) < len(case_notes):
                # Selected a note - set case as active (not evidence)
                self.state_manager.set_active(case_id=self.active_case.case_id, evidence_id=None)
                self.global_active_case_id = self.active_case.case_id
                self.global_active_evidence_id = None
                self.show_message(f"Active: Case {self.active_case.case_number}")
            else:
                # Nothing selected - set case as active
                self.state_manager.set_active(case_id=self.active_case.case_id, evidence_id=None)
                self.global_active_case_id = self.active_case.case_id
                self.global_active_evidence_id = None
                self.show_message(f"Active Case: {self.active_case.case_number}")

        elif self.current_view == "evidence_detail" and self.active_evidence and self.active_case:
            self.state_manager.set_active(case_id=self.active_case.case_id, evidence_id=self.active_evidence.evidence_id)
            self.global_active_case_id = self.active_case.case_id
            self.global_active_evidence_id = self.active_evidence.evidence_id
            self.show_message(f"Active: {self.active_evidence.name}")

    def _input_dialog(self, title, prompt=""):
        """
        Single-line text input dialog with full Unicode/UTF-8 support.
        Handles umlauts and other special characters properly.
        """
        curses.noecho()
        curses.curs_set(1)

        # Calculate dimensions - taller to show prompt and footer
        h = 6 if prompt else 4
        w = min(60, self.width - 4)
        y = self.height // 2 - 3
        x = (self.width - w) // 2

        win = curses.newwin(h, w, y, x)
        win.box()
        win.attron(curses.A_BOLD | curses.color_pair(1))
        win.addstr(0, 2, f" {title} ", curses.A_BOLD)
        win.attroff(curses.A_BOLD | curses.color_pair(1))

        # Show prompt if provided
        input_y = 1
        if prompt:
            win.addstr(1, 2, prompt, curses.color_pair(3))
            input_y = 3

        # Footer with cancel instruction
        win.addstr(h - 2, 2, "[ESC] Cancel", curses.A_DIM)

        win.refresh()

        # Text input state
        text = ""
        cursor_pos = 0  # Cursor position in characters (not bytes)
        max_width = w - 6  # Leave space for borders and padding

        def redraw_input():
            """Redraw the input line"""
            # Clear the input area
            win.addstr(input_y, 2, " " * (w - 4))

            # Display text (handle scrolling if too long)
            display_text = text
            display_offset = 0

            # If text is too long, scroll to show cursor position
            if len(display_text) > max_width:
                # Calculate offset to keep cursor visible
                if cursor_pos > max_width - 5:
                    display_offset = cursor_pos - max_width + 5
                display_text = display_text[display_offset:display_offset + max_width]

            try:
                win.addstr(input_y, 2, display_text)
            except curses.error:
                pass  # Ignore if text is too wide

            # Position cursor
            cursor_x = min(cursor_pos - display_offset + 2, w - 3)
            try:
                win.move(input_y, cursor_x)
            except curses.error:
                pass

            win.refresh()

        # Main input loop
        while True:
            redraw_input()

            try:
                ch = win.getch()
            except KeyboardInterrupt:
                curses.curs_set(0)
                del win
                return None

            # Handle special keys
            if ch == 27:  # ESC
                curses.curs_set(0)
                del win
                return None

            elif ch == 10 or ch == 13:  # Enter
                curses.curs_set(0)
                del win
                return text.strip() if text.strip() else None

            elif ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
                # Backspace
                if cursor_pos > 0:
                    text = text[:cursor_pos-1] + text[cursor_pos:]
                    cursor_pos -= 1

            elif ch == curses.KEY_DC:  # Delete key
                if cursor_pos < len(text):
                    text = text[:cursor_pos] + text[cursor_pos+1:]

            elif ch == curses.KEY_LEFT:
                if cursor_pos > 0:
                    cursor_pos -= 1

            elif ch == curses.KEY_RIGHT:
                if cursor_pos < len(text):
                    cursor_pos += 1

            elif ch == curses.KEY_HOME or ch == 1:  # Home or Ctrl+A
                cursor_pos = 0

            elif ch == curses.KEY_END or ch == 5:  # End or Ctrl+E
                cursor_pos = len(text)

            elif 32 <= ch <= 126:
                # Regular ASCII printable characters
                text = text[:cursor_pos] + chr(ch) + text[cursor_pos:]
                cursor_pos += 1

            elif ch > 127:
                # UTF-8 multi-byte character (umlauts, etc.)
                # curses returns the first byte, we need to read the rest
                try:
                    # Try to decode as UTF-8
                    # For multibyte UTF-8, we need to collect all bytes
                    bytes_collected = [ch]

                    # Determine how many bytes we need based on the first byte
                    if ch >= 0xF0:  # 4-byte character
                        num_bytes = 4
                    elif ch >= 0xE0:  # 3-byte character
                        num_bytes = 3
                    elif ch >= 0xC0:  # 2-byte character
                        num_bytes = 2
                    else:
                        num_bytes = 1

                    # Read remaining bytes
                    for _ in range(num_bytes - 1):
                        next_ch = win.getch()
                        bytes_collected.append(next_ch)

                    # Convert to character
                    char_bytes = bytes([b & 0xFF for b in bytes_collected])
                    char = char_bytes.decode('utf-8')

                    # Insert character
                    text = text[:cursor_pos] + char + text[cursor_pos:]
                    cursor_pos += 1

                except (UnicodeDecodeError, ValueError):
                    # If decode fails, ignore the character
                    pass

    def _multiline_input_dialog(self, title, prompt="", recent_notes=None, max_lines=10):
        """
        Multi-line text input dialog with optional recent notes preview.

        Args:
            title: Dialog title
            prompt: Prompt text to show above input
            recent_notes: List of recent Note objects to display inline
            max_lines: Maximum lines for input area

        Returns:
            String content or None if cancelled
        """
        curses.curs_set(1)
        curses.noecho()

        # Calculate dimensions
        # Need space for: title, prompt, recent notes, input area, footer
        recent_note_lines = 0
        if recent_notes:
            # Show up to 3 recent notes, 2 lines each
            recent_note_lines = min(len(recent_notes), 3) * 2 + 1  # +1 for header

        prompt_lines = prompt.count('\n') + 1 if prompt else 0

        # Dialog height: title(1) + prompt + recent notes + input area + footer(2) + borders
        dialog_h = min(self.height - 4, 4 + prompt_lines + recent_note_lines + max_lines + 2)
        dialog_w = min(70, self.width - 4)
        dialog_y = max(2, (self.height - dialog_h) // 2)
        dialog_x = (self.width - dialog_w) // 2

        win = curses.newwin(dialog_h, dialog_w, dialog_y, dialog_x)
        win.box()

        # Title
        win.attron(curses.A_BOLD | curses.color_pair(1))
        title_text = f" {title} "
        win.addstr(0, 2, title_text[:dialog_w-4])
        win.attroff(curses.A_BOLD | curses.color_pair(1))

        current_y = 1

        # Show prompt if provided
        if prompt:
            for line in prompt.split('\n'):
                if current_y < dialog_h - 2:
                    win.addstr(current_y, 2, line[:dialog_w-4], curses.color_pair(3))
                    current_y += 1

        # Show recent notes inline (non-blocking!)
        if recent_notes and current_y < dialog_h - max_lines - 2:
            win.addstr(current_y, 2, "Recent notes:", curses.A_DIM)
            current_y += 1

            for note in recent_notes[-3:]:  # Last 3 notes
                if current_y >= dialog_h - max_lines - 2:
                    break
                timestamp_str = time.ctime(note.timestamp)[-13:-5]  # Just time HH:MM:SS
                # Replace newlines with spaces to keep on one line
                note_content_single_line = note.content.replace('\n', ' ').replace('\r', ' ')
                # Truncate safely for Unicode
                max_preview_len = dialog_w - 18  # Account for timestamp and padding
                note_preview = self._safe_truncate(note_content_single_line, max_preview_len)
                try:
                    win.addstr(current_y, 2, f"[{timestamp_str}] {note_preview}", curses.color_pair(2))
                except curses.error:
                    # Silently handle curses errors (e.g., string too wide)
                    pass
                current_y += 1

        # Calculate input area position and size
        input_start_y = current_y + 1 if current_y > 1 else current_y
        input_height = min(max_lines, dialog_h - input_start_y - 3)  # -3 for footer + border
        input_width = dialog_w - 4

        # Footer
        footer_y = dialog_h - 2
        win.addstr(footer_y, 2, "[Ctrl+G] Submit  [ESC] Cancel", curses.A_DIM)

        win.refresh()

        # Text storage
        lines = [""]
        cursor_line = 0
        cursor_col = 0
        scroll_offset = 0

        def redraw_input():
            """Redraw the input area with current text"""
            for i in range(input_height):
                line_idx = scroll_offset + i
                y = input_start_y + i

                # Clear the line
                win.addstr(y, 2, " " * input_width)

                if line_idx < len(lines):
                    # Show line content (truncated if too long)
                    display_text = lines[line_idx][:input_width]
                    win.addstr(y, 2, display_text)

            # Position cursor
            display_cursor_line = cursor_line - scroll_offset
            if 0 <= display_cursor_line < input_height:
                cursor_y = input_start_y + display_cursor_line
                cursor_x = min(cursor_col + 2, input_width + 1)
                try:
                    win.move(cursor_y, cursor_x)
                except curses.error:
                    pass

            win.refresh()

        # Main input loop
        while True:
            redraw_input()

            try:
                ch = win.getch()
            except KeyboardInterrupt:
                curses.curs_set(0)
                del win
                return None

            # Handle special keys
            if ch == 27:  # ESC
                curses.curs_set(0)
                del win
                return None

            elif ch == 7:  # Ctrl+G - Submit
                curses.curs_set(0)
                del win
                result = '\n'.join(lines).strip()
                return result if result else None

            elif ch == curses.KEY_UP:
                if cursor_line > 0:
                    cursor_line -= 1
                    cursor_col = min(cursor_col, len(lines[cursor_line]))
                    # Adjust scroll if needed
                    if cursor_line < scroll_offset:
                        scroll_offset = cursor_line

            elif ch == curses.KEY_DOWN:
                if cursor_line < len(lines) - 1:
                    cursor_line += 1
                    cursor_col = min(cursor_col, len(lines[cursor_line]))
                    # Adjust scroll if needed
                    if cursor_line >= scroll_offset + input_height:
                        scroll_offset = cursor_line - input_height + 1

            elif ch == curses.KEY_LEFT:
                if cursor_col > 0:
                    cursor_col -= 1
                elif cursor_line > 0:
                    # Move to end of previous line
                    cursor_line -= 1
                    cursor_col = len(lines[cursor_line])
                    if cursor_line < scroll_offset:
                        scroll_offset = cursor_line

            elif ch == curses.KEY_RIGHT:
                if cursor_col < len(lines[cursor_line]):
                    cursor_col += 1
                elif cursor_line < len(lines) - 1:
                    # Move to start of next line
                    cursor_line += 1
                    cursor_col = 0
                    if cursor_line >= scroll_offset + input_height:
                        scroll_offset = cursor_line - input_height + 1

            elif ch == curses.KEY_HOME or ch == 1:  # Home or Ctrl+A
                cursor_col = 0

            elif ch == curses.KEY_END or ch == 5:  # End or Ctrl+E
                cursor_col = len(lines[cursor_line])

            elif ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
                if cursor_col > 0:
                    # Delete character before cursor
                    line = lines[cursor_line]
                    lines[cursor_line] = line[:cursor_col-1] + line[cursor_col:]
                    cursor_col -= 1
                elif cursor_line > 0:
                    # Merge with previous line
                    cursor_col = len(lines[cursor_line - 1])
                    lines[cursor_line - 1] += lines[cursor_line]
                    del lines[cursor_line]
                    cursor_line -= 1
                    if cursor_line < scroll_offset:
                        scroll_offset = cursor_line

            elif ch == curses.KEY_DC:  # Delete key
                line = lines[cursor_line]
                if cursor_col < len(line):
                    lines[cursor_line] = line[:cursor_col] + line[cursor_col+1:]
                elif cursor_line < len(lines) - 1:
                    # Merge with next line
                    lines[cursor_line] += lines[cursor_line + 1]
                    del lines[cursor_line + 1]

            elif ch == 10 or ch == 13:  # Enter - new line
                # Split current line at cursor
                line = lines[cursor_line]
                lines[cursor_line] = line[:cursor_col]
                lines.insert(cursor_line + 1, line[cursor_col:])
                cursor_line += 1
                cursor_col = 0

                # Adjust scroll if needed
                if cursor_line >= scroll_offset + input_height:
                    scroll_offset = cursor_line - input_height + 1

            elif 32 <= ch <= 126:  # Printable characters
                # Insert character at cursor
                line = lines[cursor_line]
                lines[cursor_line] = line[:cursor_col] + chr(ch) + line[cursor_col:]
                cursor_col += 1
                
                # Auto-wrap to next line if cursor exceeds visible width
                if cursor_col >= input_width:
                    # Always ensure there's a next line to move to
                    if cursor_line >= len(lines) - 1:
                        # We're on the last line, add a new line
                        lines.append("")
                    cursor_line += 1
                    cursor_col = 0
                    # Adjust scroll if needed
                    if cursor_line >= scroll_offset + input_height:
                        scroll_offset = cursor_line - input_height + 1

    def dialog_confirm(self, message):
        curses.curs_set(0)
        h = 5
        w = len(message) + 10
        y = self.height // 2 - 2
        x = (self.width - w) // 2

        win = curses.newwin(h, w, y, x)
        win.box()
        win.addstr(1, 2, message)
        win.addstr(3, 2, " [y] Yes   [n] No ")
        win.refresh()

        while True:
            ch = win.getch()
            if ch == ord('y') or ch == ord('Y'):
                del win
                return True
            elif ch == ord('n') or ch == ord('N') or ch == 27:
                del win
                return False

    def dialog_settings(self):
        """Settings menu with GPG signing toggle and key selection"""
        from .crypto import Crypto

        # Load current settings
        settings = self.state_manager.get_settings()
        pgp_enabled = settings.get("pgp_enabled", True)
        current_key = settings.get("gpg_key_id", None)

        # Menu state
        selected_option = 0
        options = ["GPG Signing", "Select GPG Key", "Save", "Cancel"]

        curses.curs_set(0)
        h = 12
        w = 60
        y = self.height // 2 - 6
        x = (self.width - w) // 2

        win = curses.newwin(h, w, y, x)
        win.keypad(True)  # Enable keypad mode for arrow keys

        while True:
            win.clear()
            win.box()
            win.addstr(0, 2, " Settings ", curses.A_BOLD)

            # Display current settings
            win.addstr(2, 2, "Current Configuration:", curses.A_UNDERLINE)

            # GPG Signing status
            status = "ENABLED" if pgp_enabled else "DISABLED"
            color = curses.color_pair(2) if pgp_enabled else curses.color_pair(3)
            win.addstr(4, 4, "GPG Signing: ")
            win.addstr(4, 18, f"{status}", color)

            # Current GPG Key
            if current_key:
                key_display = current_key[:16] + "..." if len(current_key) > 16 else current_key
                win.addstr(5, 4, f"GPG Key:     {key_display}")
            else:
                win.addstr(5, 4, "GPG Key:     [Default]", curses.A_DIM)

            win.addstr(7, 2, "Options:", curses.A_UNDERLINE)

            # Menu options
            for i, option in enumerate(options):
                y_pos = 8 + i
                if i == selected_option:
                    win.addstr(y_pos, 4, f"> {option}", curses.color_pair(1))
                else:
                    win.addstr(y_pos, 4, f"  {option}")

            # Footer
            win.addstr(h - 2, 2, "[Arrow Keys] Navigate  [Enter] Select  [Esc] Cancel", curses.A_DIM)
            win.refresh()

            ch = win.getch()

            if ch == curses.KEY_UP:
                if selected_option > 0:
                    selected_option -= 1
            elif ch == curses.KEY_DOWN:
                if selected_option < len(options) - 1:
                    selected_option += 1
            elif ch == 10 or ch == 13:  # Enter
                if selected_option == 0:  # Toggle GPG Signing
                    pgp_enabled = not pgp_enabled
                elif selected_option == 1:  # Select GPG Key
                    # Open key selection dialog
                    selected_key = self._dialog_select_gpg_key(current_key)
                    if selected_key is not None:
                        current_key = selected_key
                elif selected_option == 2:  # Save
                    self.state_manager.set_setting("pgp_enabled", pgp_enabled)
                    self.state_manager.set_setting("gpg_key_id", current_key)
                    self.show_message("Settings saved.")
                    break
                elif selected_option == 3:  # Cancel
                    break
            elif ch == 27:  # Esc
                break

        del win

    def _dialog_select_gpg_key(self, current_key):
        """Dialog to select a GPG key from available keys"""
        from .crypto import Crypto

        # Get available keys
        available_keys = Crypto.list_gpg_keys()

        if not available_keys:
            # Show error message
            self._show_error_dialog("No GPG Keys Found",
                                   "No GPG secret keys found on this system.\n"
                                   "Please generate a key using 'gpg --gen-key'.")
            return None

        # Add option for default key
        key_options = [("default", "[Use GPG Default Key]")] + available_keys
        selected_idx = 0

        # Find currently selected key in list
        if current_key:
            for i, (key_id, _) in enumerate(key_options):
                if key_id == current_key:
                    selected_idx = i
                    break

        curses.curs_set(0)
        h = min(len(key_options) + 6, self.height - 4)
        w = min(70, self.width - 4)
        y = (self.height - h) // 2
        x = (self.width - w) // 2

        win = curses.newwin(h, w, y, x)
        win.keypad(True)  # Enable keypad mode for arrow keys
        scroll_offset = 0

        while True:
            win.clear()
            win.box()
            win.addstr(0, 2, " Select GPG Key ", curses.A_BOLD)

            list_h = h - 5

            # Update scroll
            if selected_idx < scroll_offset:
                scroll_offset = selected_idx
            elif selected_idx >= scroll_offset + list_h:
                scroll_offset = selected_idx - list_h + 1

            # Display keys
            for i in range(list_h):
                idx = scroll_offset + i
                if idx >= len(key_options):
                    break

                key_id, user_id = key_options[idx]
                y_pos = 2 + i

                # Truncate if needed
                display_text = f"{key_id[:12]}... - {user_id[:40]}" if len(user_id) > 40 else f"{key_id[:12]}... - {user_id}"
                if key_id == "default":
                    display_text = user_id

                display_text = self._safe_truncate(display_text, w - 6)

                if idx == selected_idx:
                    win.addstr(y_pos, 2, f"> {display_text}", curses.color_pair(1))
                else:
                    win.addstr(y_pos, 2, f"  {display_text}")

            # Footer
            win.addstr(h - 2, 2, "[Arrow Keys] Navigate  [Enter] Select  [Esc] Cancel", curses.A_DIM)
            win.refresh()

            ch = win.getch()

            if ch == curses.KEY_UP:
                if selected_idx > 0:
                    selected_idx -= 1
            elif ch == curses.KEY_DOWN:
                if selected_idx < len(key_options) - 1:
                    selected_idx += 1
            elif ch == 10 or ch == 13:  # Enter
                selected_key_id, _ = key_options[selected_idx]
                del win
                # Return None for default, otherwise return the key ID
                return None if selected_key_id == "default" else selected_key_id
            elif ch == 27:  # Esc
                del win
                return None

        del win
        return None

    def _show_error_dialog(self, title, message):
        """Show a simple error dialog"""
        curses.curs_set(0)

        # Calculate size based on message
        lines = message.split('\n')
        h = len(lines) + 5
        w = min(max(len(line) for line in lines) + 6, self.width - 4)
        y = (self.height - h) // 2
        x = (self.width - w) // 2

        win = curses.newwin(h, w, y, x)
        win.box()
        win.addstr(0, 2, f" {title} ", curses.A_BOLD | curses.color_pair(4))

        for i, line in enumerate(lines):
            win.addstr(2 + i, 2, self._safe_truncate(line, w - 4))

        win.addstr(h - 2, 2, "Press any key to continue...", curses.A_DIM)
        win.refresh()
        win.getch()
        del win

    def dialog_new_case(self):
        case_num = self._input_dialog("New Case - Step 1/3", "Enter Case ID (required):")
        if case_num is None:
            self.show_message("Case creation cancelled.")
            return
        if not case_num:
            self.show_message("Case ID is required.")
            return

        name = self._input_dialog("New Case - Step 2/3", "Enter descriptive name (optional):")
        # For optional fields, treat None as empty string (user pressed Enter on empty field)

        investigator = self._input_dialog("New Case - Step 3/3", "Enter investigator name (optional):")
        # For optional fields, treat None as empty string (user pressed Enter on empty field)

        case = Case(case_number=case_num, name=name or "", investigator=investigator or "")
        self.storage.add_case(case)
        # After add_case, the case is already in self.storage.cases, no need to reload
        # Reload would create new object instances from disk, breaking any existing references
        self.show_message(f"Case {case_num} created.")

    def dialog_new_evidence(self):
        if not self.active_case: return

        name = self._input_dialog("New Evidence - Step 1/3", "Enter evidence name (required):")
        if name is None:
            self.show_message("Evidence creation cancelled.")
            return
        if not name:
            self.show_message("Evidence name is required.")
            return

        desc = self._input_dialog("New Evidence - Step 2/3", "Enter description (optional):")
        # For optional fields, treat None as empty string (user pressed Enter on empty field)
        
        source_hash = self._input_dialog("New Evidence - Step 3/3", "Enter source hash (optional, e.g. SHA256):")
        # For optional fields, treat None as empty string (user pressed Enter on empty field)

        ev = Evidence(name=name, description=desc or "")
        if source_hash:
            ev.metadata["source_hash"] = source_hash
        self.active_case.evidence.append(ev)
        self.storage.save_data()
        self.show_message(f"Evidence '{name}' added.")

    def dialog_add_note(self):
        # Determine context for the note
        context_title = "Add Note"
        context_prompt = "Enter note content:"
        recent_notes = []
        target_case = None
        target_evidence = None

        if self.current_view == "evidence_detail" and self.active_evidence:
            context_title = f"Add Note → Evidence: {self.active_evidence.name}"
            context_prompt = f"Case: {self.active_case.case_number if self.active_case else '?'}\nEvidence: {self.active_evidence.name}\n"
            recent_notes = self.active_evidence.notes[-5:] if len(self.active_evidence.notes) > 0 else []
            target_evidence = self.active_evidence
        elif self.current_view == "case_detail" and self.active_case:
            context_title = f"Add Note → Case: {self.active_case.case_number}"
            context_prompt = f"Case: {self.active_case.case_number}\n{self.active_case.name if self.active_case.name else ''}\nNote will be added to case notes."
            recent_notes = self.active_case.notes[-5:] if len(self.active_case.notes) > 0 else []
            target_case = self.active_case
        elif self.current_view == "case_list":
            # If in case list, try to use global active context
            if self.global_active_case_id:
                active_case = self.storage.get_case(self.global_active_case_id)
                if active_case:
                    if self.global_active_evidence_id:
                        # Find evidence
                        for ev in active_case.evidence:
                            if ev.evidence_id == self.global_active_evidence_id:
                                context_title = f"Add Note → Evidence: {ev.name}"
                                context_prompt = f"Case: {active_case.case_number}\nEvidence: {ev.name}\n"
                                recent_notes = ev.notes[-5:] if len(ev.notes) > 0 else []
                                target_case = active_case
                                target_evidence = ev
                                break
                    else:
                        context_title = f"Add Note → Case: {active_case.case_number}"
                        context_prompt = f"Case: {active_case.case_number}\nNote will be added to case notes."
                        recent_notes = active_case.notes[-5:] if len(active_case.notes) > 0 else []
                        target_case = active_case

            if not target_case:
                self.show_message("No active case/evidence. Set active context first.")
                return

        # Use multi-line input dialog with inline recent notes (non-blocking!)
        content = self._multiline_input_dialog(context_title, context_prompt, recent_notes=recent_notes, max_lines=10)

        if content is None:
            self.show_message("Note creation cancelled.")
            return
        if not content:
            self.show_message("Note content cannot be empty.")
            return

        # Create and save the note
        from .crypto import Crypto

        # Check settings
        settings = self.state_manager.get_settings()
        pgp_enabled = settings.get("pgp_enabled", True)
        gpg_key_id = settings.get("gpg_key_id", None)

        note = Note(content=content)
        note.calculate_hash()
        note.extract_tags()  # Extract hashtags from content
        note.extract_iocs()  # Extract IOCs from content

        signed = False
        if pgp_enabled:
            sig = Crypto.sign_content(f"Hash: {note.content_hash}\nContent: {note.content}", key_id=gpg_key_id or "")
            if sig:
                note.signature = sig
                signed = True
            else:
                self.show_message("Note Saved. GPG Signing Failed!")

        # Add note to the appropriate target
        if target_evidence:
            target_evidence.notes.append(note)
        elif target_case:
            target_case.notes.append(note)
        elif self.current_view == "evidence_detail" and self.active_evidence:
            self.active_evidence.notes.append(note)
        elif self.current_view == "case_detail" and self.active_case:
            self.active_case.notes.append(note)

        self.storage.save_data()
        if not (pgp_enabled and not signed):
            self.show_message("Note added successfully.")

    def handle_delete(self):
        if self.current_view == "case_list":
            filtered = self._get_filtered_list(self.cases, "case_number", "name")
            if filtered:
                case_to_del = filtered[self.selected_index]
                if self.dialog_confirm(f"Delete Case {case_to_del.case_number}?"):
                    self.storage.delete_case(case_to_del.case_id)
                    # Check active state
                    if self.global_active_case_id == case_to_del.case_id:
                        self.state_manager.set_active(None, None)
                        self.global_active_case_id = None
                        self.global_active_evidence_id = None
                    # Refresh
                    self.cases = self.storage.cases
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.show_message(f"Case {case_to_del.case_number} deleted.")

        elif self.current_view == "case_detail" and self.active_case:
            # Determine if we're deleting a note or evidence based on selected index
            case_notes = self.active_case.notes
            filtered = self._get_filtered_list(self.active_case.evidence, "name", "description")

            # Check if selecting a note (indices 0 to len(notes)-1)
            if self.selected_index < len(case_notes):
                # Delete case note
                note_to_del = case_notes[self.selected_index]
                preview = note_to_del.content[:50] + "..." if len(note_to_del.content) > 50 else note_to_del.content
                if self.dialog_confirm(f"Delete note: '{preview}'?"):
                    self.active_case.notes.remove(note_to_del)
                    self.storage.save_data()
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.show_message("Note deleted.")
            elif filtered and self.selected_index - len(case_notes) < len(filtered):
                # Delete evidence (adjust index by subtracting case notes count)
                evidence_idx = self.selected_index - len(case_notes)
                ev_to_del = filtered[evidence_idx]
                if self.dialog_confirm(f"Delete Evidence {ev_to_del.name}?"):
                    self.storage.delete_evidence(self.active_case.case_id, ev_to_del.evidence_id)
                    # Check active state
                    if self.global_active_evidence_id == ev_to_del.evidence_id:
                        # Fallback to case active
                        self.state_manager.set_active(self.active_case.case_id, None)
                        self.global_active_evidence_id = None
                    # Refresh
                    updated_case = self.storage.get_case(self.active_case.case_id)
                    if updated_case:
                        self.active_case = updated_case
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.show_message(f"Evidence '{ev_to_del.name}' deleted.")

        elif self.current_view == "evidence_detail" and self.active_evidence:
            # Delete individual notes from evidence
            if not self.active_evidence.notes:
                self.show_message("No notes to delete.")
                return

            # Calculate which note to delete based on display (showing last N notes)
            notes = self.active_evidence.notes
            list_h = self.content_h - 5  # Adjust for header
            display_notes = notes[-list_h:] if len(notes) > list_h else notes

            if display_notes:
                # User selection is in context of displayed notes
                # We need to delete from the full list
                if self.selected_index < len(display_notes):
                    note_to_del = display_notes[self.selected_index]
                    # Show preview of note content in confirmation
                    preview = note_to_del.content[:50] + "..." if len(note_to_del.content) > 50 else note_to_del.content
                    if self.dialog_confirm(f"Delete note: '{preview}'?"):
                        self.active_evidence.notes.remove(note_to_del)
                        self.storage.save_data()
                        self.selected_index = 0
                        self.scroll_offset = 0
                        self.show_message("Note deleted.")

    def view_case_notes(self, highlight_note_index=None):
        if not self.active_case: return

        h = int(self.height * 0.8)
        w = int(self.width * 0.8)
        y = int(self.height * 0.1)
        x = int(self.width * 0.1)

        scroll_offset = 0
        highlight_idx = highlight_note_index  # Store for persistent highlighting

        while True:
            win = curses.newwin(h, w, y, x)
            win.keypad(True)
            win.timeout(25)  # 25ms timeout makes ESC responsive
            win.box()
            win.addstr(1, 2, f"Notes: {self.active_case.case_number} ({len(self.active_case.notes)} total)", curses.A_BOLD)

            notes = self.active_case.notes
            content_lines = []
            note_line_ranges = []  # Track which lines belong to which note
            
            # Build all content lines with separators between notes
            for note_idx, note in enumerate(notes):
                start_line = len(content_lines)
                timestamp_str = time.ctime(note.timestamp)
                content_lines.append(f"[{timestamp_str}]")
                # Split multi-line notes and wrap long lines
                for line in note.content.split('\n'):
                    # Wrap long lines
                    while len(line) > w - 6:
                        content_lines.append("  " + line[:w-6])
                        line = line[w-6:]
                    content_lines.append("  " + line)
                content_lines.append("")  # Blank line between notes
                end_line = len(content_lines) - 1
                note_line_ranges.append((start_line, end_line, note_idx))

            max_display_lines = h - 5
            total_lines = len(content_lines)

            # Jump to highlighted note on first render
            if highlight_note_index is not None and note_line_ranges:
                for start, end, idx in note_line_ranges:
                    if idx == highlight_note_index:
                        # Center the note in the view
                        note_middle = (start + end) // 2
                        scroll_offset = max(0, note_middle - max_display_lines // 2)
                        highlight_note_index = None  # Only jump once
                        break

            # Adjust scroll bounds
            max_scroll = max(0, total_lines - max_display_lines)
            scroll_offset = max(0, min(scroll_offset, max_scroll))

            # Display lines with highlighting
            for i in range(max_display_lines):
                line_idx = scroll_offset + i
                if line_idx >= total_lines:
                    break
                display_line = self._safe_truncate(content_lines[line_idx], w - 4)
                
                # Check if this line belongs to the highlighted note
                is_highlighted = False
                if highlight_idx is not None:
                    for start, end, idx in note_line_ranges:
                        if start <= line_idx <= end and idx == highlight_idx:
                            is_highlighted = True
                            break
                
                try:
                    y_pos = 3 + i
                    # Use unified highlighting function
                    self._display_line_with_highlights(y_pos, 2, display_line, is_highlighted, win)
                except curses.error:
                    pass

            # Show scroll indicator
            if total_lines > max_display_lines:
                scroll_info = f"[{scroll_offset + 1}-{min(scroll_offset + max_display_lines, total_lines)}/{total_lines}]"
                try:
                    win.addstr(2, w - len(scroll_info) - 3, scroll_info, curses.A_DIM)
                except curses.error:
                    pass

            win.addstr(h-2, 2, "[↑↓] Scroll  [n] Add Note  [b/q/Esc] Close", curses.color_pair(3))
            win.refresh()
            key = win.getch()
            if key == -1:  # timeout, redraw
                del win
                continue
            del win

            # Handle key presses
            if key == curses.KEY_UP:
                scroll_offset = max(0, scroll_offset - 1)
            elif key == curses.KEY_DOWN:
                scroll_offset = min(max_scroll, scroll_offset + 1)
            elif key == curses.KEY_PPAGE:  # Page Up
                scroll_offset = max(0, scroll_offset - max_display_lines)
            elif key == curses.KEY_NPAGE:  # Page Down
                scroll_offset = min(max_scroll, scroll_offset + max_display_lines)
            elif key == curses.KEY_HOME:
                scroll_offset = 0
            elif key == curses.KEY_END:
                scroll_offset = max_scroll
            elif key == ord('n') or key == ord('N'):
                # Save current view and switch to case_detail temporarily for context
                saved_view = self.current_view
                self.current_view = "case_detail"
                self.dialog_add_note()
                self.current_view = saved_view
                scroll_offset = max_scroll  # Jump to bottom to show new note
            elif key == ord('b') or key == ord('B') or key == ord('q') or key == ord('Q') or key == 27:  # 27 is Esc
                break

    def view_evidence_notes(self, highlight_note_index=None):
        if not self.active_evidence: return

        h = int(self.height * 0.8)
        w = int(self.width * 0.8)
        y = int(self.height * 0.1)
        x = int(self.width * 0.1)

        scroll_offset = 0
        highlight_idx = highlight_note_index  # Store for persistent highlighting

        while True:
            win = curses.newwin(h, w, y, x)
            win.keypad(True)
            win.timeout(25)  # 25ms timeout makes ESC responsive
            win.box()
            win.addstr(1, 2, f"Notes: {self.active_evidence.name} ({len(self.active_evidence.notes)} total)", curses.A_BOLD)

            notes = self.active_evidence.notes
            content_lines = []
            note_line_ranges = []  # Track which lines belong to which note
            
            # Build all content lines with separators between notes
            for note_idx, note in enumerate(notes):
                start_line = len(content_lines)
                timestamp_str = time.ctime(note.timestamp)
                content_lines.append(f"[{timestamp_str}]")
                # Split multi-line notes and wrap long lines
                for line in note.content.split('\n'):
                    # Wrap long lines
                    while len(line) > w - 6:
                        content_lines.append("  " + line[:w-6])
                        line = line[w-6:]
                    content_lines.append("  " + line)
                content_lines.append("")  # Blank line between notes
                end_line = len(content_lines) - 1
                note_line_ranges.append((start_line, end_line, note_idx))

            max_display_lines = h - 5
            total_lines = len(content_lines)

            # Jump to highlighted note on first render
            if highlight_note_index is not None and note_line_ranges:
                for start, end, idx in note_line_ranges:
                    if idx == highlight_note_index:
                        # Center the note in the view
                        note_middle = (start + end) // 2
                        scroll_offset = max(0, note_middle - max_display_lines // 2)
                        highlight_note_index = None  # Only jump once
                        break

            # Adjust scroll bounds
            max_scroll = max(0, total_lines - max_display_lines)
            scroll_offset = max(0, min(scroll_offset, max_scroll))

            # Display lines with highlighting
            for i in range(max_display_lines):
                line_idx = scroll_offset + i
                if line_idx >= total_lines:
                    break
                display_line = self._safe_truncate(content_lines[line_idx], w - 4)
                
                # Check if this line belongs to the highlighted note
                is_highlighted = False
                if highlight_idx is not None:
                    for start, end, idx in note_line_ranges:
                        if start <= line_idx <= end and idx == highlight_idx:
                            is_highlighted = True
                            break
                
                try:
                    y_pos = 3 + i
                    # Use unified highlighting function
                    self._display_line_with_highlights(y_pos, 2, display_line, is_highlighted, win)
                except curses.error:
                    pass

            # Show scroll indicator
            if total_lines > max_display_lines:
                scroll_info = f"[{scroll_offset + 1}-{min(scroll_offset + max_display_lines, total_lines)}/{total_lines}]"
                try:
                    win.addstr(2, w - len(scroll_info) - 3, scroll_info, curses.A_DIM)
                except curses.error:
                    pass

            win.addstr(h-2, 2, "[↑↓] Scroll  [n] Add Note  [b/q/Esc] Close", curses.color_pair(3))
            win.refresh()
            key = win.getch()
            if key == -1:  # timeout, redraw
                del win
                continue
            del win

            # Handle key presses
            if key == curses.KEY_UP:
                scroll_offset = max(0, scroll_offset - 1)
            elif key == curses.KEY_DOWN:
                scroll_offset = min(max_scroll, scroll_offset + 1)
            elif key == curses.KEY_PPAGE:  # Page Up
                scroll_offset = max(0, scroll_offset - max_display_lines)
            elif key == curses.KEY_NPAGE:  # Page Down
                scroll_offset = min(max_scroll, scroll_offset + max_display_lines)
            elif key == curses.KEY_HOME:
                scroll_offset = 0
            elif key == curses.KEY_END:
                scroll_offset = max_scroll
            elif key == ord('n') or key == ord('N'):
                # Save current view and switch to evidence_detail temporarily for context
                saved_view = self.current_view
                self.current_view = "evidence_detail"
                self.dialog_add_note()
                self.current_view = saved_view
                scroll_offset = max_scroll  # Jump to bottom to show new note
            elif key == ord('b') or key == ord('B') or key == ord('q') or key == ord('Q') or key == 27:  # 27 is Esc
                break

    def export_iocs(self):
        """Export IOCs from current context to a text file"""
        import os
        from pathlib import Path

        if not self.current_iocs:
            self.show_message("No IOCs to export.")
            return

        # Determine context for filename
        if self.active_evidence:
            context_name = f"{self.active_case.case_number}_{self.active_evidence.name}" if self.active_case else self.active_evidence.name
        elif self.active_case:
            context_name = self.active_case.case_number
        else:
            context_name = "unknown"

        # Clean filename
        context_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in context_name)

        # Create exports directory if it doesn't exist
        export_dir = Path.home() / ".trace" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"iocs_{context_name}_{timestamp}.txt"
        filepath = export_dir / filename

        # Build export content
        lines = []
        lines.append(f"# IOC Export - {context_name}")
        lines.append(f"# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        if self.active_evidence:
            # Evidence context - only evidence IOCs
            lines.append(f"## Evidence: {self.active_evidence.name}")
            lines.append("")
            for ioc, count, ioc_type in self.current_iocs:
                lines.append(f"{ioc}\t[{ioc_type}]\t({count} occurrences)")
        elif self.active_case:
            # Case context - show case IOCs + evidence IOCs with separators
            # Get case notes IOCs
            case_iocs = self._get_all_iocs_with_counts(self.active_case.notes)
            if case_iocs:
                lines.append("## Case Notes")
                lines.append("")
                for ioc, count, ioc_type in case_iocs:
                    lines.append(f"{ioc}\t[{ioc_type}]\t({count} occurrences)")
                lines.append("")

            # Get IOCs from each evidence
            for ev in self.active_case.evidence:
                ev_iocs = self._get_all_iocs_with_counts(ev.notes)
                if ev_iocs:
                    lines.append(f"## Evidence: {ev.name}")
                    lines.append("")
                    for ioc, count, ioc_type in ev_iocs:
                        lines.append(f"{ioc}\t[{ioc_type}]\t({count} occurrences)")
                    lines.append("")

        # Write to file
        try:
            with open(filepath, 'w') as f:
                f.write('\n'.join(lines))
            self.show_message(f"IOCs exported to: {filepath}")
        except Exception as e:
            self.show_message(f"Export failed: {str(e)}")

def run_tui(open_active=False):
    """
    Run the TUI application.

    Args:
        open_active: If True, navigate directly to the active case/evidence view
    """
    def tui_wrapper(stdscr):
        tui = TUI(stdscr)

        # If requested, navigate to active case/evidence
        if open_active:
            if tui.global_active_case_id:
                # Find the active case
                case = tui.storage.get_case(tui.global_active_case_id)
                if case:
                    tui.active_case = case

                    if tui.global_active_evidence_id:
                        # Navigate to evidence detail
                        for ev in case.evidence:
                            if ev.evidence_id == tui.global_active_evidence_id:
                                tui.active_evidence = ev
                                tui.current_view = "evidence_detail"
                                break
                        else:
                            # Evidence not found, just go to case detail
                            tui.current_view = "case_detail"
                    else:
                        # Navigate to case detail
                        tui.current_view = "case_detail"

        tui.run()

    curses.wrapper(tui_wrapper)
