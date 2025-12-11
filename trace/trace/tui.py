import curses
import curses.textpad
import time
from typing import Optional, List
from .models import Case, Evidence, Note
from .storage import Storage, StateManager

class TUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.storage = Storage()
        self.state_manager = StateManager()
        self.current_view = "case_list"  # case_list, case_detail, evidence_detail, tags_list, tag_notes_list, note_detail, ioc_list, ioc_notes_list
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
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN) # Highlight
            curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK) # Success / Active
            curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK) # Warning / Info
            curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK) # Error

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

    def draw_header(self):
        title = " trace - Forensic Notes "
        self.stdscr.attron(curses.color_pair(1))
        self.stdscr.addstr(0, 0, title)
        if self.width > len(title):
            self.stdscr.addstr(0, len(title), " " * (self.width - len(title)))
        self.stdscr.attroff(curses.color_pair(1))

    def draw_status_bar(self):
        # Determine status text
        status_text = ""
        attr = curses.color_pair(1)

        # Check for flash message (display for 3 seconds)
        if self.flash_message and (time.time() - self.flash_time < 3):
            status_text = f" {self.flash_message} "
            if "Failed" in self.flash_message or "Error" in self.flash_message:
                attr = curses.color_pair(4) # Red
            else:
                attr = curses.color_pair(2) # Green
        elif self.filter_mode:
            status_text = f"FILTER: {self.filter_query}"
            attr = curses.color_pair(3)
        else:
            status_text = "Active Context: None"
            if self.global_active_case_id:
                c = self.storage.get_case(self.global_active_case_id)
                if c:
                    status_text = f"Active Case: {c.case_number}"
                    if self.global_active_evidence_id:
                        # Find evidence name
                        _, ev = self.storage.find_evidence(self.global_active_evidence_id)
                        if ev:
                            status_text += f" | Ev: {ev.name}"

        # Truncate if too long
        if len(status_text) > self.width:
            status_text = status_text[:self.width-1]

        # Bottom line
        try:
            self.stdscr.attron(attr)
            self.stdscr.addstr(self.height - 1, 0, status_text)
            remaining = self.width - len(status_text) - 1
            if remaining > 0:
                self.stdscr.addstr(self.height - 1, len(status_text), " " * remaining)
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
        self.stdscr.addstr(2, 2, "Cases:", curses.A_BOLD)

        if not self.cases:
            self.stdscr.addstr(4, 4, "No cases found. Press 'N' to create one.", curses.color_pair(3))
            self.stdscr.addstr(self.height - 3, 2, "[N] New Case  [q] Quit", curses.color_pair(3))
            return

        display_cases = self._get_filtered_list(self.cases, "case_number", "name")

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

            prefix = "[x] " if case.case_id == self.global_active_case_id and not self.global_active_evidence_id else "[ ] "
            note_indicator = f" ({total_notes} notes" if total_notes > 0 else ""
            tag_indicator = f", {tag_count} tags)" if tag_count > 0 and total_notes > 0 else ")" if total_notes > 0 else ""
            display_str = f"{prefix}{case.case_number} - {case.name}{note_indicator}{tag_indicator}"
            # Truncate safely for Unicode
            display_str = self._safe_truncate(display_str, self.width - 6)

            if idx == self.selected_index:
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(y, 4, display_str)
                self.stdscr.attroff(curses.color_pair(1))
            else:
                self.stdscr.addstr(y, 4, display_str)

        if not display_cases and self.cases:
            self.stdscr.addstr(4, 4, "No cases match filter.")

        self.stdscr.addstr(self.height - 3, 2, "[N] New Case  [n] Add Note  [Enter] Select  [a] Active  [d] Delete  [/] Filter  [s] Settings", curses.color_pair(3))

    def draw_case_detail(self):
        if not self.active_case: return

        case_note_count = len(self.active_case.notes)
        case_note_info = f" ({case_note_count} case notes)" if case_note_count > 0 else " (no case notes)"

        self.stdscr.addstr(2, 2, f"Case: {self.active_case.case_number}{case_note_info}", curses.A_BOLD)
        self.stdscr.addstr(3, 2, f"Inv: {self.active_case.investigator}")
        self.stdscr.addstr(4, 2, f"ID: {self.active_case.case_id}")

        self.stdscr.addstr(6, 2, "Evidence:", curses.A_UNDERLINE)

        evidence_list = self._get_filtered_list(self.active_case.evidence, "name", "description")

        if not evidence_list:
             self.stdscr.addstr(7, 4, "No evidence.")
             # Continue to draw navigation footer
        else:
            # Scrolling for evidence list
            # List starts at y=7
            list_h = self.content_h - 5 # 7 is header offset
            if list_h < 1: list_h = 1

            self._update_scroll(len(evidence_list))

            for i in range(list_h):
                idx = self.scroll_offset + i
                if idx >= len(evidence_list): break

                ev = evidence_list[idx]
                y = 7 + i

                note_count = len(ev.notes)

                # Count tags
                ev_tags = self._get_all_tags_with_counts(ev.notes)
                tag_count = len(ev_tags)

                # Count IOCs
                ev_iocs = self._get_all_iocs_with_counts(ev.notes)
                ioc_count = len(ev_iocs)

                prefix = "[x] " if ev.evidence_id == self.global_active_evidence_id else "[ ] "
                note_indicator = f" ({note_count} notes" if note_count > 0 else ""
                tag_indicator = f", {tag_count} tags" if tag_count > 0 and note_count > 0 else ""
                ioc_indicator = f", {ioc_count} IOCs)" if ioc_count > 0 and note_count > 0 else ")" if note_count > 0 else ""

                # Add hash indicator if source hash exists
                hash_indicator = ""
                source_hash = ev.metadata.get("source_hash")
                if source_hash:
                    # Show first 8 chars of hash for quick reference
                    hash_preview = source_hash[:8] + "..." if len(source_hash) > 8 else source_hash
                    hash_indicator = f" [H:{hash_preview}]"

                # Build display with IOC indicator in red if present
                if ioc_count > 0:
                    base_display = f"{prefix}{ev.name}{note_indicator}{tag_indicator}"
                    # Truncate base_display to leave room for IOC indicator
                    ioc_text = f", {ioc_count} IOCs)"
                    max_base_len = self.width - 6 - len(ioc_text)
                    base_display = self._safe_truncate(base_display, max_base_len)
                else:
                    base_display = f"{prefix}{ev.name}{note_indicator}{tag_indicator}{ioc_indicator}{hash_indicator}"
                    base_display = self._safe_truncate(base_display, self.width - 6)

                if idx == self.selected_index:
                    self.stdscr.attron(curses.color_pair(1))
                    self.stdscr.addstr(y, 4, base_display)
                    if ioc_count > 0:
                        # Add IOC indicator in red
                        self.stdscr.attroff(curses.color_pair(1))
                        self.stdscr.attron(curses.color_pair(4))
                        self.stdscr.addstr(ioc_text)
                        self.stdscr.attroff(curses.color_pair(4))
                    else:
                        self.stdscr.attroff(curses.color_pair(1))
                else:
                    self.stdscr.addstr(y, 4, base_display)
                    if ioc_count > 0:
                        # Add IOC indicator in red
                        self.stdscr.attron(curses.color_pair(4))
                        self.stdscr.addstr(ioc_text)
                        self.stdscr.attroff(curses.color_pair(4))

        self.stdscr.addstr(self.height - 3, 2, "[N] New Evidence  [n] Add Note  [t] Tags  [i] IOCs  [v] View Notes  [b] Back  [a] Active  [d] Delete  [/] Filter", curses.color_pair(3))

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

            # Highlight selected note
            if idx == self.selected_index:
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(start_y + i, 4, display_str)
                self.stdscr.attroff(curses.color_pair(1))
            else:
                self.stdscr.addstr(start_y + i, 4, display_str)

        self.stdscr.addstr(self.height - 3, 2, "[n] Add Note  [t] Tags  [i] IOCs  [v] View Notes  [b] Back  [a] Active  [d] Delete Note", curses.color_pair(3))

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

        # Content with tag highlighting
        self.stdscr.addstr(current_y, 2, "Content:", curses.A_BOLD)
        current_y += 1

        # Display content with highlighted tags
        content_lines = self.current_note.content.split('\n')
        max_content_lines = self.content_h - (current_y - 2) - 6  # Reserve space for hash/sig

        for line in content_lines[:max_content_lines]:
            if current_y >= self.height - 6:
                break

            # Highlight tags in the content
            display_line = self._safe_truncate(line, self.width - 6)
            x_pos = 4

            # Simple tag highlighting - split by words and color tags
            import re
            parts = re.split(r'(#\w+)', display_line)
            for part in parts:
                if part.startswith('#'):
                    try:
                        self.stdscr.addstr(current_y, x_pos, part, curses.color_pair(3))
                    except curses.error:
                        pass
                    x_pos += len(part)
                else:
                    if x_pos < self.width - 2:
                        try:
                            self.stdscr.addstr(current_y, x_pos, part[:self.width - x_pos - 2])
                        except curses.error:
                            pass
                        x_pos += len(part)

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

    def handle_input(self, key):
        if self.filter_mode:
            return self.handle_filter_input(key)

        if key == ord('q'): return False

        # Filter toggle
        if key == ord('/'):
            # Filter works on list views: case_list and case_detail (evidence list)
            if self.current_view in ["case_list", "case_detail"]:
                self.filter_mode = True
                return True

        # Navigation
        if key == curses.KEY_UP:
            if self.selected_index > 0:
                self.selected_index -= 1
        elif key == curses.KEY_DOWN:
            # Calculate max_idx based on current filtered view
            max_idx = 0
            if self.current_view == "case_list":
                filtered = self._get_filtered_list(self.cases, "case_number", "name")
                max_idx = len(filtered) - 1
            elif self.current_view == "case_detail" and self.active_case:
                filtered = self._get_filtered_list(self.active_case.evidence, "name", "description")
                max_idx = len(filtered) - 1
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
                    self.filter_query = "" # Reset filter on view change
            elif self.current_view == "case_detail":
                if self.active_case:
                    filtered = self._get_filtered_list(self.active_case.evidence, "name", "description")
                    if filtered:
                        self.active_evidence = filtered[self.selected_index]
                        self.current_view = "evidence_detail"
                        self.selected_index = 0
                        self.filter_query = "" # Reset filter
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
                    self.current_view = "note_detail"
                    self.selected_index = 0
                    self.scroll_offset = 0

        # Back
        elif key == ord('b'):
            if self.current_view == "note_detail":
                self.current_view = "tag_notes_list"
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
            filtered = self._get_filtered_list(self.active_case.evidence, "name", "description")
            if filtered:
                ev = filtered[self.selected_index]
                self.state_manager.set_active(case_id=self.active_case.case_id, evidence_id=ev.evidence_id)
                self.global_active_case_id = self.active_case.case_id
                self.global_active_evidence_id = ev.evidence_id
                self.show_message(f"Active: {ev.name}")
            else:
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
        curses.noecho() # Fix: Ensure echo is off before using Textbox, as Textbox handles its own echoing
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

        # Inner window for editing
        inner = win.derwin(1, w-4, input_y, 2)
        box = curses.textpad.Textbox(inner)

        win.refresh()
        self.stdscr.refresh()

        # Flag to detect ESC
        cancelled = [False]

        # Validator to handle Enter (10/13) and ESC (27)
        def validator(ch):
            if ch == 27:  # ESC
                cancelled[0] = True
                return 7  # Ctrl-G (terminate)
            if ch == 10 or ch == 13:
                return 7 # Ctrl-G (terminate)
            return ch

        result = box.edit(validator).strip()

        curses.noecho()
        curses.curs_set(0)
        del win

        # Return None if cancelled
        if cancelled[0]:
            return None

        return result

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
                    # Show line content
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
        # Simple Toggle
        current = self.state_manager.get_settings().get("pgp_enabled", True)

        curses.curs_set(0)
        h = 6
        w = 40
        y = self.height // 2 - 2
        x = (self.width - w) // 2

        win = curses.newwin(h, w, y, x)
        win.box()
        win.addstr(0, 2, " Settings ")

        while True:
            status = "ENABLED" if current else "DISABLED"
            color = curses.color_pair(2) if current else curses.color_pair(3)

            win.addstr(2, 4, "GPG Signing: ")
            win.addstr(2, 17, f"[{status}]", color)
            win.addstr(4, 2, "[Space] Toggle  [Enter] Save", curses.A_DIM)
            win.refresh()

            ch = win.getch()
            if ch == 32: # Space
                current = not current
            elif ch == 10 or ch == 13: # Enter
                self.state_manager.set_setting("pgp_enabled", current)
                self.show_message("Settings saved.")
                break
            elif ch == 27: # Esc
                break

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
        if name is None:
            self.show_message("Case creation cancelled.")
            return

        investigator = self._input_dialog("New Case - Step 3/3", "Enter investigator name (optional):")
        if investigator is None:
            self.show_message("Case creation cancelled.")
            return

        case = Case(case_number=case_num, name=name or "", investigator=investigator or "")
        self.storage.add_case(case)
        # After add_case, the case is already in self.storage.cases, no need to reload
        # Reload would create new object instances from disk, breaking any existing references
        self.show_message(f"Case {case_num} created.")

    def _show_recent_notes_preview(self, notes, context_title):
        """Show a preview window with recent notes before adding a new note"""
        h = int(self.height * 0.7)
        w = int(self.width * 0.8)
        y = int(self.height * 0.15)
        x = int(self.width * 0.1)

        win = curses.newwin(h, w, y, x)
        win.box()
        win.attron(curses.A_BOLD | curses.color_pair(1))
        win.addstr(0, 2, f" {context_title} - Recent Notes ", curses.A_BOLD)
        win.attroff(curses.A_BOLD | curses.color_pair(1))

        max_lines = h - 5

        if not notes:
            win.addstr(2, 2, "No existing notes.", curses.color_pair(3))
        else:
            win.addstr(1, 2, f"Showing last {len(notes)} note(s):", curses.A_DIM)

            line_y = 3
            for i, note in enumerate(notes):
                if line_y >= max_lines:
                    break

                timestamp_str = time.ctime(note.timestamp)
                # Header for each note
                win.addstr(line_y, 2, f"[{timestamp_str}]", curses.color_pair(2))
                line_y += 1

                # Content - may wrap or truncate
                content_lines = note.content.split('\n')
                for content_line in content_lines:
                    if line_y >= max_lines:
                        break
                    # Truncate safely for Unicode
                    content_line = self._safe_truncate(content_line, w - 6)
                    win.addstr(line_y, 4, content_line)
                    line_y += 1

                line_y += 1  # Blank line between notes

        win.addstr(h - 2, 2, "Press any key to continue...", curses.A_DIM)
        win.refresh()
        win.getch()
        del win
        # Redraw the main screen
        self.stdscr.clear()
        self.stdscr.refresh()

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
        if desc is None:
            self.show_message("Evidence creation cancelled.")
            return

        source_hash = self._input_dialog("New Evidence - Step 3/3", "Enter source hash (optional, e.g. SHA256):")
        if source_hash is None:
            self.show_message("Evidence creation cancelled.")
            return

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
            context_prompt = f"Case: {self.active_case.case_number if self.active_case else '?'}\nEvidence: {self.active_evidence.name}\n\nNote will be added to this evidence."
            recent_notes = self.active_evidence.notes[-5:] if len(self.active_evidence.notes) > 0 else []
            target_evidence = self.active_evidence
        elif self.current_view == "case_detail" and self.active_case:
            context_title = f"Add Note → Case: {self.active_case.case_number}"
            context_prompt = f"Case: {self.active_case.case_number}\n{self.active_case.name if self.active_case.name else ''}\n\nNote will be added to case notes."
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
                                context_prompt = f"Case: {active_case.case_number}\nEvidence: {ev.name}\n\nNote will be added to this evidence."
                                recent_notes = ev.notes[-5:] if len(ev.notes) > 0 else []
                                target_case = active_case
                                target_evidence = ev
                                break
                    else:
                        context_title = f"Add Note → Case: {active_case.case_number}"
                        context_prompt = f"Case: {active_case.case_number}\n\nNote will be added to case notes."
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
        pgp_enabled = self.state_manager.get_settings().get("pgp_enabled", True)

        note = Note(content=content)
        note.calculate_hash()
        note.extract_tags()  # Extract hashtags from content
        note.extract_iocs()  # Extract IOCs from content

        signed = False
        if pgp_enabled:
            sig = Crypto.sign_content(f"Hash: {note.content_hash}\nContent: {note.content}")
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
            filtered = self._get_filtered_list(self.active_case.evidence, "name", "description")
            if filtered:
                ev_to_del = filtered[self.selected_index]
                if self.dialog_confirm(f"Delete Evidence {ev_to_del.name}?"):
                    self.storage.delete_evidence(self.active_case.case_id, ev_to_del.evidence_id)
                    # Check active state
                    if self.global_active_evidence_id == ev_to_del.evidence_id:
                        # Fallback to case active
                        self.state_manager.set_active(self.active_case.case_id, None)
                        self.global_active_evidence_id = None
                    # Refresh (in-memory update was done by storage usually? No, storage reloads or we reload)
                    # We need to reload active_case evidence list or trust storage.cases
                    # It's better to reload from storage to be safe
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

    def view_case_notes(self):
        if not self.active_case: return

        h = int(self.height * 0.8)
        w = int(self.width * 0.8)
        y = int(self.height * 0.1)
        x = int(self.width * 0.1)

        win = curses.newwin(h, w, y, x)
        win.box()
        win.addstr(1, 2, f"Notes: {self.active_case.case_number}", curses.A_BOLD)

        notes = self.active_case.notes
        max_lines = h - 4

        # Scroll last notes
        display_notes = notes[-max_lines:] if len(notes) > max_lines else notes

        for i, note in enumerate(display_notes):
            # Replace newlines with spaces for single-line display
            note_content = note.content.replace('\n', ' ').replace('\r', ' ')
            display_str = f"- [{time.ctime(note.timestamp)}] {note_content}"
            # Truncate safely for Unicode
            display_str = self._safe_truncate(display_str, w - 4)
            win.addstr(3 + i, 2, display_str)

        win.addstr(h-2, 2, "Press any key to close")
        win.refresh()
        win.getch()
        del win

    def view_evidence_notes(self):
        if not self.active_evidence: return

        h = int(self.height * 0.8)
        w = int(self.width * 0.8)
        y = int(self.height * 0.1)
        x = int(self.width * 0.1)

        win = curses.newwin(h, w, y, x)
        win.box()
        win.addstr(1, 2, f"Notes: {self.active_evidence.name}", curses.A_BOLD)

        notes = self.active_evidence.notes
        max_lines = h - 4

        # Scroll last notes
        display_notes = notes[-max_lines:] if len(notes) > max_lines else notes

        for i, note in enumerate(display_notes):
            # Replace newlines with spaces for single-line display
            note_content = note.content.replace('\n', ' ').replace('\r', ' ')
            display_str = f"- [{time.ctime(note.timestamp)}] {note_content}"
            # Truncate safely for Unicode
            display_str = self._safe_truncate(display_str, w - 4)
            win.addstr(3 + i, 2, display_str)

        win.addstr(h-2, 2, "Press any key to close")
        win.refresh()
        win.getch()
        del win

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
