import subprocess
import hashlib

class Crypto:
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
            stdout, stderr = proc.communicate()

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
                    current_key_id = None  # Reset after matching

            return keys

        except FileNotFoundError:
            return []  # GPG not installed

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
            stdout, stderr = proc.communicate(input=content)

            if proc.returncode != 0:
                # Fallback: maybe no key is found or gpg error
                # In a real app we might want to log this 'stderr'
                return ""

            return stdout
        except FileNotFoundError:
            return "" # GPG not installed

    @staticmethod
    def hash_content(content: str, timestamp: float) -> str:
        data = f"{timestamp}:{content}".encode('utf-8')
        return hashlib.sha256(data).hexdigest()
