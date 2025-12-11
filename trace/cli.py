import argparse
import sys
import time
from .models import Note, Case
from .storage import Storage, StateManager
from .crypto import Crypto

def quick_add_note(content: str):
    storage = Storage()
    state_manager = StateManager()
    state = state_manager.get_active()
    settings = state_manager.get_settings()

    case_id = state.get("case_id")
    evidence_id = state.get("evidence_id")

    if not case_id:
        print("Error: No active case set. Open the TUI to select a case first.")
        sys.exit(1)

    case = storage.get_case(case_id)
    if not case:
        print("Error: Active case not found in storage. Ensure you have set an active case in the TUI.")
        sys.exit(1)

    target_evidence = None

    if evidence_id:
        # Find evidence
        for ev in case.evidence:
            if ev.evidence_id == evidence_id:
                target_evidence = ev
                break

    # Create note
    note = Note(content=content)
    note.calculate_hash()
    note.extract_tags()  # Extract hashtags from content
    note.extract_iocs()  # Extract IOCs from content

    # Try signing if enabled
    if settings.get("pgp_enabled", True):
        gpg_key_id = settings.get("gpg_key_id", None)
        signature = Crypto.sign_content(f"Hash: {note.content_hash}\nContent: {note.content}", key_id=gpg_key_id)
        if signature:
            note.signature = signature
        else:
            print("Warning: GPG signature failed (GPG not found or no key). Note saved without signature.")

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
    storage = Storage()

    with open(output_file, "w") as f:
        f.write("# Forensic Notes Export\n\n")
        f.write(f"Generated on: {time.ctime()}\n\n")

        for case in storage.cases:
            f.write(f"## Case: {case.case_number}\n")
            if case.name:
                f.write(f"**Name:** {case.name}\n")
            if case.investigator:
                f.write(f"**Investigator:** {case.investigator}\n")
            f.write(f"**Case ID:** {case.case_id}\n\n")

            f.write("### Case Notes\n")
            if not case.notes:
                f.write("_No notes._\n")
            for note in case.notes:
                write_note(f, note)

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
                    write_note(f, note)
                f.write("\n")
            f.write("---\n\n")
    print(f"Exported to {output_file}")

def write_note(f, note: Note):
    f.write(f"- **{time.ctime(note.timestamp)}**\n")
    f.write(f"  - Content: {note.content}\n")
    f.write(f"  - Hash: `{note.content_hash}`\n")
    if note.signature:
        f.write("  - **Signature Verified:**\n")
        f.write("    ```\n")
        # Indent signature for markdown block
        for line in note.signature.splitlines():
             f.write(f"    {line}\n")
        f.write("    ```\n")
    f.write("\n")

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

    # Launch TUI (with optional direct navigation to active context)
    try:
        from .tui import run_tui
        run_tui(open_active=args.open)
    except ImportError as e:
        print(f"Error launching TUI: {e}")
        # For development debugging, it might be useful to see full traceback
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
