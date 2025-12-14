"""First-run GPG setup wizard for trace application"""

import sys
from .crypto import Crypto
from .storage import StateManager


def run_gpg_wizard():
    """
    Run the first-time GPG setup wizard.

    Returns:
        dict: Settings to save (gpg_enabled, gpg_key_id)
    """
    print("\n" + "="*60)
    print("Welcome to trace - Forensic Note Taking Tool")
    print("="*60)
    print("\nFirst-time setup: GPG Signature Configuration\n")
    print("trace can digitally sign all notes using GPG for authenticity")
    print("and integrity verification. This is useful for legal evidence")
    print("and chain-of-custody documentation.\n")

    # Check if GPG is available
    gpg_available = Crypto.is_gpg_available()

    if not gpg_available:
        print("⚠ GPG is not installed or not available on your system.")
        print("\nTo use GPG signing, please install GPG:")
        print("  - Linux: apt install gnupg / yum install gnupg")
        print("  - macOS: brew install gnupg")
        print("  - Windows: Install Gpg4win (https://gpg4win.org)")
        print("\nYou can enable GPG signing later by editing ~/.trace/settings.json")
        print("\nPress Enter to continue without GPG signing...")
        input()
        return {"pgp_enabled": False, "gpg_key_id": None}

    # GPG is available - ask if user wants to enable it
    print("✓ GPG is available on your system.\n")

    while True:
        response = input("Do you want to enable GPG signing for notes? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            enable_gpg = True
            break
        elif response in ['n', 'no']:
            enable_gpg = False
            break
        else:
            print("Please enter 'y' or 'n'")

    if not enable_gpg:
        print("\nGPG signing disabled. You can enable it later in settings.")
        return {"pgp_enabled": False, "gpg_key_id": None}

    # List available GPG keys
    print("\nSearching for GPG secret keys...\n")
    keys = Crypto.list_gpg_keys()

    if not keys:
        print("⚠ No GPG secret keys found in your keyring.")
        print("\nTo use GPG signing, you need to generate a GPG key first:")
        print("  - Use 'gpg --gen-key' (Linux/macOS)")
        print("  - Use Kleopatra (Windows)")
        print("\nAfter generating a key, you can enable GPG signing by editing")
        print("~/.trace/settings.json and setting 'gpg_enabled': true")
        print("\nPress Enter to continue without GPG signing...")
        input()
        return {"pgp_enabled": False, "gpg_key_id": None}

    # Display available keys
    print("Available GPG keys:\n")
    for i, (key_id, user_id) in enumerate(keys, 1):
        print(f"  {i}. {user_id}")
        print(f"     Key ID: {key_id}\n")

    # Let user select a key
    selected_key = None

    if len(keys) == 1:
        print(f"Only one key found. Using: {keys[0][1]}")
        selected_key = keys[0][0]
    else:
        while True:
            try:
                choice = input(f"Select a key (1-{len(keys)}, or 0 to use default key): ").strip()
                choice_num = int(choice)

                if choice_num == 0:
                    print("Using GPG default key (no specific key ID)")
                    selected_key = None
                    break
                elif 1 <= choice_num <= len(keys):
                    selected_key = keys[choice_num - 1][0]
                    print(f"Selected: {keys[choice_num - 1][1]}")
                    break
                else:
                    print(f"Please enter a number between 0 and {len(keys)}")
            except ValueError:
                print("Please enter a valid number")

    print("\n✓ GPG signing enabled!")
    if selected_key:
        print(f"  Using key: {selected_key}")
    else:
        print("  Using default GPG key")

    print("\nSetup complete. Starting trace...\n")

    return {"pgp_enabled": True, "gpg_key_id": selected_key}


def check_and_run_wizard():
    """
    Check if this is first run and run wizard if needed.
    Returns True if wizard was run, False otherwise.
    """
    state_manager = StateManager()
    settings = state_manager.get_settings()

    # Check if wizard has already been run (presence of any GPG setting indicates setup was done)
    if "pgp_enabled" in settings:
        return False

    # First run - run wizard
    wizard_settings = run_gpg_wizard()

    # Save settings
    for key, value in wizard_settings.items():
        state_manager.set_setting(key, value)

    return True
