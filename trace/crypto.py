import subprocess
import hashlib

class Crypto:
    @staticmethod
    def sign_content(content: str) -> str:
        """
        Signs the content using GPG.
        Returns the clearsigned content or None if GPG fails.
        """
        try:
            # We use --clearsign so the signature is attached to the text in a readable format
            # We assume a default key is available or configured.
            proc = subprocess.Popen(
                ['gpg', '--clearsign', '--output', '-'],
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
