"""Export functionality for TUI"""

import time
import datetime
from pathlib import Path
from typing import List, Tuple, Optional

from ...models import Note, Case, Evidence


class ExportHandler:
    """Handles exporting IOCs and notes to files"""

    @staticmethod
    def export_iocs_to_file(
        iocs_with_counts: List[Tuple[str, int, str]],
        active_case: Optional[Case],
        active_evidence: Optional[Evidence],
        get_iocs_func=None
    ) -> Tuple[bool, str]:
        """
        Export IOCs to a text file

        Args:
            iocs_with_counts: List of (ioc, count, type) tuples
            active_case: Active case context
            active_evidence: Active evidence context
            get_iocs_func: Function to get IOCs for a list of notes

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not iocs_with_counts:
            return False, "No IOCs to export."

        # Determine context for filename
        if active_evidence:
            context_name = f"{active_case.case_number}_{active_evidence.name}" if active_case else active_evidence.name
        elif active_case:
            context_name = active_case.case_number
        else:
            context_name = "unknown"

        # Clean filename
        context_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in context_name)

        # Create exports directory if it doesn't exist
        export_dir = Path.home() / ".trace" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"iocs_{context_name}_{timestamp}.txt"
        filepath = export_dir / filename

        # Build export content
        lines = []
        lines.append(f"# IOC Export - {context_name}")
        lines.append(f"# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        if active_evidence:
            # Evidence context - only evidence IOCs
            lines.append(f"## Evidence: {active_evidence.name}")
            lines.append("")
            for ioc, count, ioc_type in iocs_with_counts:
                lines.append(f"{ioc}\t[{ioc_type}]\t({count} occurrences)")
        elif active_case and get_iocs_func:
            # Case context - show case IOCs + evidence IOCs with separators
            # Get case notes IOCs
            case_iocs = get_iocs_func(active_case.notes)
            if case_iocs:
                lines.append("## Case Notes")
                lines.append("")
                for ioc, count, ioc_type in case_iocs:
                    lines.append(f"{ioc}\t[{ioc_type}]\t({count} occurrences)")
                lines.append("")

            # Get IOCs from each evidence
            for ev in active_case.evidence:
                ev_iocs = get_iocs_func(ev.notes)
                if ev_iocs:
                    lines.append(f"## Evidence: {ev.name}")
                    lines.append("")
                    for ioc, count, ioc_type in ev_iocs:
                        lines.append(f"{ioc}\t[{ioc_type}]\t({count} occurrences)")
                    lines.append("")

        # Write to file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            return True, f"IOCs exported to: {filepath}"
        except Exception as e:
            return False, f"Export failed: {str(e)}"

    @staticmethod
    def export_case_to_markdown(case: Case) -> Tuple[bool, str]:
        """
        Export case (and all its evidence) to markdown

        Args:
            case: The case to export

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Create exports directory if it doesn't exist
        export_dir = Path.home() / ".trace" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        case_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in case.case_number)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"case_{case_name}_{timestamp}.md"
        filepath = export_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("# Forensic Notes Export\n\n")
                f.write(f"Generated on: {time.ctime()}\n\n")

                # Write case info
                f.write(f"## Case: {case.case_number}\n")
                if case.name:
                    f.write(f"**Name:** {case.name}\n")
                if case.investigator:
                    f.write(f"**Investigator:** {case.investigator}\n")
                f.write(f"**Case ID:** {case.case_id}\n\n")

                # Case notes
                f.write("### Case Notes\n")
                if not case.notes:
                    f.write("_No notes._\n")
                for note in case.notes:
                    ExportHandler._write_note_markdown(f, note)

                # Evidence
                f.write("\n### Evidence\n")
                if not case.evidence:
                    f.write("_No evidence._\n")

                for ev in case.evidence:
                    f.write(f"#### Evidence: {ev.name}\n")
                    if ev.description:
                        f.write(f"_{ev.description}_\n")
                    f.write(f"**ID:** {ev.evidence_id}\n")

                    # Include source hash if available
                    source_hash = ev.metadata.get("source_hash")
                    if source_hash:
                        f.write(f"**Source Hash:** `{source_hash}`\n")
                    f.write("\n")

                    f.write("##### Evidence Notes\n")
                    if not ev.notes:
                        f.write("_No notes._\n")
                    for note in ev.notes:
                        ExportHandler._write_note_markdown(f, note)
                    f.write("\n")

            return True, f"Case exported to: {filepath}"
        except Exception as e:
            return False, f"Export failed: {str(e)}"

    @staticmethod
    def export_evidence_to_markdown(
        evidence: Evidence,
        case: Optional[Case]
    ) -> Tuple[bool, str]:
        """
        Export evidence to markdown

        Args:
            evidence: The evidence to export
            case: The parent case (for context)

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Create exports directory if it doesn't exist
        export_dir = Path.home() / ".trace" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        case_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in case.case_number) if case else "unknown"
        ev_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in evidence.name)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"evidence_{case_name}_{ev_name}_{timestamp}.md"
        filepath = export_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("# Forensic Evidence Export\n\n")
                f.write(f"Generated on: {time.ctime()}\n\n")

                # Case context
                if case:
                    f.write(f"**Case:** {case.case_number}\n")
                    if case.name:
                        f.write(f"**Case Name:** {case.name}\n")
                f.write("\n")

                # Evidence info
                f.write(f"## Evidence: {evidence.name}\n")
                if evidence.description:
                    f.write(f"**Description:** {evidence.description}\n")
                if evidence.metadata.get("source_hash"):
                    f.write(f"**Source Hash:** `{evidence.metadata['source_hash']}`\n")
                f.write(f"**Evidence ID:** {evidence.evidence_id}\n\n")

                # Notes
                f.write("### Notes\n")
                if not evidence.notes:
                    f.write("_No notes._\n")
                for note in evidence.notes:
                    ExportHandler._write_note_markdown(f, note)

            return True, f"Evidence exported to: {filepath}"
        except Exception as e:
            return False, f"Export failed: {str(e)}"

    @staticmethod
    def _write_note_markdown(f, note: Note):
        """Helper to write a note in markdown format"""
        f.write(f"- **{time.ctime(note.timestamp)}**\n")
        f.write(f"  - Content: {note.content}\n")
        if note.tags:
            tags_str = " ".join([f"#{tag}" for tag in note.tags])
            f.write(f"  - Tags: {tags_str}\n")
        f.write(f"  - Hash: `{note.content_hash}`\n")
        if note.signature:
            f.write("  - **Signature Verified:**\n")
            f.write("    ```\n")
            for line in note.signature.splitlines():
                f.write(f"    {line}\n")
            f.write("    ```\n")
        f.write("\n")
