import argparse
import sys
import time
from .models import Note, Case
from .storage import Storage, StateManager
from .crypto import Crypto

def quick_add_note(content: str):
    storage = Storage()
    state_manager = StateManager()

    # Validate and clear stale state
    warning = state_manager.validate_and_clear_stale(storage)
    if warning:
        print(f"Warning: {warning}", file=sys.stderr)

    state = state_manager.get_active()
    settings = state_manager.get_settings()

    case_id = state.get("case_id")
    evidence_id = state.get("evidence_id")

    if not case_id:
        print("Error: No active case set. Open the TUI to select a case first.", file=sys.stderr)
        sys.exit(1)

    case = storage.get_case(case_id)
    if not case:
        print("Error: Active case not found in storage. Ensure you have set an active case in the TUI.", file=sys.stderr)
        sys.exit(1)

    target_evidence = None

    if evidence_id:
        # Find and validate evidence belongs to active case
        for ev in case.evidence:
            if ev.evidence_id == evidence_id:
                target_evidence = ev
                break

        if not target_evidence:
            # Evidence ID is set but doesn't exist in case - clear it
            print(f"Warning: Active evidence not found in case. Clearing to case level.", file=sys.stderr)
            state_manager.set_active(case_id, None)

    # Create note
    note = Note(content=content)
    note.calculate_hash()
    note.extract_tags()  # Extract hashtags from content
    note.extract_iocs()  # Extract IOCs from content

    # Try signing the hash if enabled
    signature = None
    if settings.get("pgp_enabled", True):
        gpg_key_id = settings.get("gpg_key_id", None)
        if gpg_key_id:
            # Sign only the hash (hash already includes timestamp:content for integrity)
            signature = Crypto.sign_content(note.content_hash, key_id=gpg_key_id)
            if signature:
                note.signature = signature
            else:
                print("Warning: GPG signature failed (GPG not found or no key). Note saved without signature.", file=sys.stderr)
        else:
            print("Warning: No GPG key ID configured. Note saved without signature.", file=sys.stderr)

    # Attach to evidence or case
    if target_evidence:
        target_evidence.notes.append(note)
        print(f"✓ Note added to evidence '{target_evidence.name}'")
    elif evidence_id:
        print("Warning: Active evidence not found. Adding to case instead.")
        case.notes.append(note)
        print(f"✓ Note added to case '{case.case_number}'")
    else:
        case.notes.append(note)
        print(f"✓ Note added to case '{case.case_number}'")

    storage.save_data()

def export_markdown(output_file: str = "export.md"):
    try:
        storage = Storage()
        state_manager = StateManager()
        settings = state_manager.get_settings()

        # Build the export content in memory first
        content_lines = []
        content_lines.append("# Forensic Notes Export\n\n")
        content_lines.append(f"Generated on: {time.ctime()}\n\n")

        for case in storage.cases:
            content_lines.append(f"## Case: {case.case_number}\n")
            if case.name:
                content_lines.append(f"**Name:** {case.name}\n")
            if case.investigator:
                content_lines.append(f"**Investigator:** {case.investigator}\n")
            content_lines.append(f"**Case ID:** {case.case_id}\n\n")

            content_lines.append("### Case Notes\n")
            if not case.notes:
                content_lines.append("_No notes._\n")
            for note in case.notes:
                note_content = format_note_for_export(note)
                content_lines.append(note_content)

            content_lines.append("\n### Evidence\n")
            if not case.evidence:
                content_lines.append("_No evidence._\n")

            for ev in case.evidence:
                content_lines.append(f"#### Evidence: {ev.name}\n")
                if ev.description:
                    content_lines.append(f"_{ev.description}_\n")
                content_lines.append(f"**ID:** {ev.evidence_id}\n")

                # Include source hash if available
                source_hash = ev.metadata.get("source_hash")
                if source_hash:
                    content_lines.append(f"**Source Hash:** `{source_hash}`\n")
                content_lines.append("\n")

                content_lines.append("##### Evidence Notes\n")
                if not ev.notes:
                    content_lines.append("_No notes._\n")
                for note in ev.notes:
                    note_content = format_note_for_export(note)
                    content_lines.append(note_content)
                content_lines.append("\n")
            content_lines.append("---\n\n")

        # Join all content
        export_content = "".join(content_lines)

        # Sign the entire export if GPG is enabled
        if settings.get("pgp_enabled", False):
            gpg_key_id = settings.get("gpg_key_id", None)
            signed_export = Crypto.sign_content(export_content, key_id=gpg_key_id)

            if signed_export:
                # Write the signed version
                final_content = signed_export
                print(f"✓ Export signed with GPG")
            else:
                # Signing failed - write unsigned
                final_content = export_content
                print("⚠ Warning: GPG signing failed. Export saved unsigned.", file=sys.stderr)
        else:
            final_content = export_content

        # Write to file
        with open(output_file, "w", encoding='utf-8') as f:
            f.write(final_content)

        print(f"✓ Exported to {output_file}")

        # Show verification instructions
        if settings.get("pgp_enabled", False) and signed_export:
            print(f"\nTo verify the export:")
            print(f"  gpg --verify {output_file}")

    except (IOError, OSError, PermissionError) as e:
        print(f"Error: Failed to export to {output_file}: {e}")
        sys.exit(1)

def format_note_for_export(note: Note) -> str:
    """Format a single note for export (returns string instead of writing to file)"""
    lines = []
    lines.append(f"- **{time.ctime(note.timestamp)}**\n")
    lines.append(f"  - Content:\n")
    # Properly indent multi-line content
    for line in note.content.splitlines():
        lines.append(f"    {line}\n")
    lines.append(f"  - SHA256 Hash (timestamp:content): `{note.content_hash}`\n")
    if note.signature:
        lines.append("  - **GPG Signature of Hash:**\n")
        lines.append("    ```\n")
        # Indent signature for markdown block
        for line in note.signature.splitlines():
            lines.append(f"    {line}\n")
        lines.append("    ```\n")
    lines.append("\n")
    return "".join(lines)

def main():
    parser = argparse.ArgumentParser(description="trace: Forensic Note Taking Tool")
    parser.add_argument("note", nargs="?", help="Quick note content to add to active context")
    parser.add_argument("--export", help="Export all data to Markdown file", action="store_true")
    parser.add_argument("--output", help="Output file for export", default="trace_export.md")
    parser.add_argument("--open", "-o", help="Open TUI directly at active case/evidence", action="store_true")

    # We will import TUI only if needed to keep start time fast

    args = parser.parse_args()

    if args.export:
        export_markdown(args.output)
        return

    if args.note:
        quick_add_note(args.note)
        return

    # Check for first run and run GPG wizard if needed
    from .gpg_wizard import check_and_run_wizard
    check_and_run_wizard()

    # Launch TUI (with optional direct navigation to active context)
    try:
        from .tui_app import run_tui
        run_tui(open_active=args.open)
    except ImportError as e:
        print(f"Error launching TUI: {e}")
        # For development debugging, it might be useful to see full traceback
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
