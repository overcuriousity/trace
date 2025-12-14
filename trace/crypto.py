import subprocess
import hashlib

class Crypto:
    @staticmethod
    def is_gpg_available() -> bool:
        """
        Check if GPG is available on the system.

        Returns:
            True if GPG is available, False otherwise.
        """
        try:
            proc = subprocess.Popen(
                ['gpg', '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = proc.communicate(timeout=5)
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def verify_signature(signed_content: str) -> tuple[bool, str]:
        """
        Verify a GPG clearsigned message.

        Args:
            signed_content: The clearsigned content to verify

        Returns:
            A tuple of (verified: bool, signer_info: str)
            - verified: True if signature is valid, False otherwise
            - signer_info: Information about the signer (key ID, name) or error message
        """
        if not signed_content or not signed_content.strip():
            return False, "No signature present"

        # Check if content looks like a GPG signed message
        if "-----BEGIN PGP SIGNED MESSAGE-----" not in signed_content:
            return False, "Not a GPG signed message"

        try:
            # Force English output for consistent parsing across locales
            # Linux/macOS: LC_ALL/LANG variables control GPG's output language
            # Windows: GPG may ignore these, but encoding='utf-8' + errors='replace' provides robustness
            import os
            env = os.environ.copy()
            # Use C.UTF-8 for English messages with UTF-8 encoding support
            # Falls back gracefully via errors='replace' if locale not available
            env['LC_ALL'] = 'C.UTF-8'
            env['LANG'] = 'C.UTF-8'

            proc = subprocess.Popen(
                ['gpg', '--verify'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',  # Handle encoding issues on any platform
                env=env
            )
            stdout, stderr = proc.communicate(input=signed_content, timeout=10)

            if proc.returncode == 0:
                # Parse signer info from stderr (GPG outputs verification info to stderr)
                signer_info = "Unknown signer"
                for line in stderr.split('\n'):
                    if "Good signature from" in line:
                        # Extract the signer name/email
                        parts = line.split('"')
                        if len(parts) >= 2:
                            signer_info = parts[1]
                            break  # Only break after successfully extracting signer info
                    elif "using" in line:
                        # Try to get key ID as fallback
                        if "key" in line.lower():
                            signer_info = line.strip()

                return True, signer_info
            else:
                # Signature verification failed
                error_msg = "Verification failed"
                for line in stderr.split('\n'):
                    if "BAD signature" in line:
                        error_msg = "BAD signature"
                        break
                    elif "no public key" in line or "public key not found" in line:
                        error_msg = "Public key not found in keyring"
                        break
                    elif "Can't check signature" in line:
                        error_msg = "Cannot check signature"
                        break

                return False, error_msg

        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, "GPG not available or timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"

    @staticmethod
    def list_gpg_keys():
        """
        List available GPG secret keys.
        Returns a list of tuples: (key_id, user_id)
        """
        try:
            proc = subprocess.Popen(
                ['gpg', '--list-secret-keys', '--with-colons'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = proc.communicate(timeout=10)

            if proc.returncode != 0:
                return []

            keys = []
            current_key_id = None

            for line in stdout.split('\n'):
                fields = line.split(':')
                if len(fields) < 2:
                    continue

                # sec = secret key
                if fields[0] == 'sec':
                    # Key ID is in field 4 (short) or we can extract from field 5 (fingerprint)
                    current_key_id = fields[4] if len(fields) > 4 else None

                # uid = user ID
                elif fields[0] == 'uid' and current_key_id:
                    user_id = fields[9] if len(fields) > 9 else "Unknown"
                    keys.append((current_key_id, user_id))
                    # Don't reset current_key_id - allow multiple UIDs per key

            return keys

        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []  # GPG not installed or timed out

    @staticmethod
    def sign_content(content: str, key_id: str = None) -> str:
        """
        Signs the content using GPG.

        Args:
            content: The content to sign
            key_id: Optional GPG key ID to use. If None, uses default key.

        Returns:
            The clearsigned content or empty string if GPG fails.
        """
        try:
            # Build command
            cmd = ['gpg', '--clearsign', '--output', '-']

            # Add specific key if provided
            if key_id:
                cmd.extend(['--local-user', key_id])

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = proc.communicate(input=content, timeout=10)

            if proc.returncode != 0:
                # Fallback: maybe no key is found or gpg error
                # In a real app we might want to log this 'stderr'
                return ""

            return stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "" # GPG not installed or timed out

    @staticmethod
    def hash_content(content: str, timestamp: float) -> str:
        """Calculate SHA256 hash of timestamp:content.

        Hash input format: "{timestamp}:{content}"
        - timestamp: Unix epoch timestamp as float (seconds since 1970-01-01 00:00:00 UTC)
          Example: 1702345678.123456
        - The float is converted to string using Python's default str() conversion
        - Colon (':') separator between timestamp and content
        - Ensures integrity of both WHAT was said and WHEN it was said

        Args:
            content: The note content to hash
            timestamp: Unix epoch timestamp as float

        Returns:
            SHA256 hash as hexadecimal string (64 characters)

        Example:
            >>> hash_content("Suspicious process detected", 1702345678.123456)
            Computes SHA256 of: "1702345678.123456:Suspicious process detected"
        """
        data = f"{timestamp}:{content}".encode('utf-8')
        return hashlib.sha256(data).hexdigest()
