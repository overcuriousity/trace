import argparse
import sys
import time
from typing import Optional, Tuple
from .models import Note, Case, Evidence
from .storage import Storage, StateManager
from .crypto import Crypto

def find_case(storage: Storage, identifier: str) -> Optional[Case]:
    """Find a case by case_id (UUID) or case_number."""
    for case in storage.cases:
        if case.case_id == identifier or case.case_number == identifier:
            return case
    return None

def find_evidence(case: Case, identifier: str) -> Optional[Evidence]:
    """Find evidence by evidence_id (UUID) or name within a case."""
    for evidence in case.evidence:
        if evidence.evidence_id == identifier or evidence.name == identifier:
            return evidence
    return None

def show_context():
    """Display the current active context."""
    state_manager = StateManager()
    storage = Storage()

    state = state_manager.get_active()
    case_id = state.get("case_id")
    evidence_id = state.get("evidence_id")

    if not case_id:
        print("No active context set.")
        print("Use --switch-case to set an active case, or open the TUI to select one.")
        return

    case = storage.get_case(case_id)
    if not case:
        print("Error: Active case not found in storage.")
        return

    print(f"Active context:")
    print(f"  Case: {case.case_number}", end="")
    if case.name:
        print(f" - {case.name}", end="")
    print(f" [{case.case_id[:8]}...]")

    if evidence_id:
        evidence = find_evidence(case, evidence_id)
        if evidence:
            print(f"  Evidence: {evidence.name}", end="")
            if evidence.description:
                print(f" - {evidence.description}", end="")
            print(f" [{evidence.evidence_id[:8]}...]")
        else:
            print(f"  Evidence: [not found - stale reference]")
    else:
        print(f"  Evidence: [none - notes will attach to case]")

def list_contexts():
    """List all cases and their evidence in a hierarchical format."""
    storage = Storage()

    if not storage.cases:
        print("No cases found.")
        print("Use --new-case to create one, or open the TUI.")
        return

    print("Cases and Evidence:")
    for case in storage.cases:
        # Show case
        print(f"  [{case.case_id[:8]}...] {case.case_number}", end="")
        if case.name:
            print(f" - {case.name}", end="")
        if case.investigator:
            print(f" (Investigator: {case.investigator})", end="")
        print()

        # Show evidence under this case
        for evidence in case.evidence:
            print(f"    [{evidence.evidence_id[:8]}...] {evidence.name}", end="")
            if evidence.description:
                print(f" - {evidence.description}", end="")
            print()

        # Add blank line between cases for readability
        if storage.cases[-1] != case:
            print()

def create_case(case_number: str, name: Optional[str] = None, investigator: Optional[str] = None):
    """Create a new case and set it as active."""
    storage = Storage()
    state_manager = StateManager()

    # Check if case number already exists
    existing = find_case(storage, case_number)
    if existing:
        print(f"Error: Case with number '{case_number}' already exists.", file=sys.stderr)
        sys.exit(1)

    # Create new case
    case = Case(case_number=case_number, name=name, investigator=investigator)
    storage.cases.append(case)
    storage.save_data()

    # Set as active case
    state_manager.set_active(case.case_id, None)

    print(f"✓ Created case '{case_number}' [{case.case_id[:8]}...]")
    if name:
        print(f"  Name: {name}")
    if investigator:
        print(f"  Investigator: {investigator}")
    print(f"✓ Set as active case")

def create_evidence(name: str, description: Optional[str] = None):
    """Create new evidence and attach to active case."""
    storage = Storage()
    state_manager = StateManager()

    state = state_manager.get_active()
    case_id = state.get("case_id")

    if not case_id:
        print("Error: No active case set. Use --switch-case or --new-case first.", file=sys.stderr)
        sys.exit(1)

    case = storage.get_case(case_id)
    if not case:
        print("Error: Active case not found in storage.", file=sys.stderr)
        sys.exit(1)

    # Check if evidence with this name already exists in the case
    existing = find_evidence(case, name)
    if existing:
        print(f"Error: Evidence named '{name}' already exists in case '{case.case_number}'.", file=sys.stderr)
        sys.exit(1)

    # Create new evidence
    evidence = Evidence(name=name, description=description)
    case.evidence.append(evidence)
    storage.save_data()

    # Set as active evidence
    state_manager.set_active(case.case_id, evidence.evidence_id)

    print(f"✓ Created evidence '{name}' [{evidence.evidence_id[:8]}...]")
    if description:
        print(f"  Description: {description}")
    print(f"✓ Added to case '{case.case_number}'")
    print(f"✓ Set as active evidence")

def switch_case(identifier: str):
    """Switch active case context."""
    storage = Storage()
    state_manager = StateManager()

    case = find_case(storage, identifier)
    if not case:
        print(f"Error: Case '{identifier}' not found.", file=sys.stderr)
        print("Use --list to see available cases.", file=sys.stderr)
        sys.exit(1)

    # Set as active case, clear evidence
    state_manager.set_active(case.case_id, None)

    print(f"✓ Switched to case '{case.case_number}' [{case.case_id[:8]}...]")
    if case.name:
        print(f"  {case.name}")

def switch_evidence(identifier: str):
    """Switch active evidence context within the active case."""
    storage = Storage()
    state_manager = StateManager()

    state = state_manager.get_active()
    case_id = state.get("case_id")

    if not case_id:
        print("Error: No active case set. Use --switch-case first.", file=sys.stderr)
        sys.exit(1)

    case = storage.get_case(case_id)
    if not case:
        print("Error: Active case not found in storage.", file=sys.stderr)
        sys.exit(1)

    evidence = find_evidence(case, identifier)
    if not evidence:
        print(f"Error: Evidence '{identifier}' not found in case '{case.case_number}'.", file=sys.stderr)
        print("Use --list to see available evidence.", file=sys.stderr)
        sys.exit(1)

    # Set as active evidence
    state_manager.set_active(case.case_id, evidence.evidence_id)

    print(f"✓ Switched to evidence '{evidence.name}' [{evidence.evidence_id[:8]}...]")
    if evidence.description:
        print(f"  {evidence.description}")

def quick_add_note(content: str, case_override: Optional[str] = None, evidence_override: Optional[str] = None):
    storage = Storage()
    state_manager = StateManager()

    # Validate and clear stale state
    warning = state_manager.validate_and_clear_stale(storage)
    if warning:
        print(f"Warning: {warning}", file=sys.stderr)

    state = state_manager.get_active()
    settings = state_manager.get_settings()

    # Handle case override or use active case
    if case_override:
        case = find_case(storage, case_override)
        if not case:
            print(f"Error: Case '{case_override}' not found.", file=sys.stderr)
            print("Use --list to see available cases.", file=sys.stderr)
            sys.exit(1)
    else:
        case_id = state.get("case_id")
        if not case_id:
            print("Error: No active case set. Use --switch-case, --new-case, or open the TUI to select a case.", file=sys.stderr)
            sys.exit(1)

        case = storage.get_case(case_id)
        if not case:
            print("Error: Active case not found in storage.", file=sys.stderr)
            sys.exit(1)

    # Handle evidence override or use active evidence
    target_evidence = None

    if evidence_override:
        target_evidence = find_evidence(case, evidence_override)
        if not target_evidence:
            print(f"Error: Evidence '{evidence_override}' not found in case '{case.case_number}'.", file=sys.stderr)
            print("Use --list to see available evidence.", file=sys.stderr)
            sys.exit(1)
    elif not case_override:  # Only use active evidence if not overriding case
        evidence_id = state.get("evidence_id")
        if evidence_id:
            # Find and validate evidence belongs to active case
            target_evidence = find_evidence(case, evidence_id)

            if not target_evidence:
                # Evidence ID is set but doesn't exist in case - clear it
                print(f"Warning: Active evidence not found in case. Clearing to case level.", file=sys.stderr)
                state_manager.set_active(case.case_id, None)

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
    """Format a single note for export (returns string instead of writing to file)

    Includes Unix timestamp for hash reproducibility - anyone can recompute the hash
    using the formula: SHA256("{unix_timestamp}:{content}")
    """
    lines = []
    lines.append(f"- **{time.ctime(note.timestamp)}**\n")
    lines.append(f"  - Unix Timestamp: `{note.timestamp}` (for hash verification)\n")
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
    parser = argparse.ArgumentParser(
        description="trace: Forensic Note Taking Tool",
        epilog="Examples:\n"
               "  trace 'Found suspicious process'     Add note to active context\n"
               "  trace --stdin < output.txt           Add file contents as note\n"
               "  trace --list                         List all cases and evidence\n"
               "  trace --new-case 2024-001            Create new case\n"
               "  trace --switch-case 2024-001         Switch active case\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Note content (positional or stdin)
    parser.add_argument("note", nargs="?", help="Quick note content to add to active context")
    parser.add_argument("--stdin", action="store_true", help="Read note content from stdin")

    # Context management
    parser.add_argument("--show-context", action="store_true", help="Show active case and evidence")
    parser.add_argument("--list", action="store_true", help="List all cases and evidence")
    parser.add_argument("--switch-case", metavar="IDENTIFIER", help="Switch active case (by ID or case number)")
    parser.add_argument("--switch-evidence", metavar="IDENTIFIER", help="Switch active evidence (by ID or name)")

    # Temporary overrides for note addition
    parser.add_argument("--case", metavar="IDENTIFIER", help="Use specific case for this note (doesn't change active)")
    parser.add_argument("--evidence", metavar="IDENTIFIER", help="Use specific evidence for this note (doesn't change active)")

    # Case and evidence creation
    parser.add_argument("--new-case", metavar="CASE_NUMBER", help="Create new case")
    parser.add_argument("--name", metavar="NAME", help="Name for new case")
    parser.add_argument("--investigator", metavar="INVESTIGATOR", help="Investigator name for new case")
    parser.add_argument("--new-evidence", metavar="EVIDENCE_NAME", help="Create new evidence in active case")
    parser.add_argument("--description", metavar="DESC", help="Description for new evidence")

    # Export
    parser.add_argument("--export", action="store_true", help="Export all data to Markdown file")
    parser.add_argument("--output", metavar="FILE", default="trace_export.md", help="Output file for export")

    # TUI
    parser.add_argument("--open", "-o", action="store_true", help="Open TUI directly at active case/evidence")

    args = parser.parse_args()

    # Handle context management commands
    if args.show_context:
        show_context()
        return

    if args.list:
        list_contexts()
        return

    if args.switch_case:
        switch_case(args.switch_case)
        return

    if args.switch_evidence:
        switch_evidence(args.switch_evidence)
        return

    # Handle case/evidence creation
    if args.new_case:
        create_case(args.new_case, name=args.name, investigator=args.investigator)
        return

    if args.new_evidence:
        create_evidence(args.new_evidence, description=args.description)
        return

    # Handle export
    if args.export:
        export_markdown(args.output)
        return

    # Handle note addition
    if args.stdin:
        # Read from stdin
        content = sys.stdin.read().strip()
        if not content:
            print("Error: No content provided from stdin.", file=sys.stderr)
            sys.exit(1)
        quick_add_note(content, case_override=args.case, evidence_override=args.evidence)
        return

    if args.note:
        quick_add_note(args.note, case_override=args.case, evidence_override=args.evidence)
        return

    # No arguments - check for first run and launch TUI
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
