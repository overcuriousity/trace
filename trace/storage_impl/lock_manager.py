"""File lock manager for preventing concurrent access"""

import os
import sys
import time
from pathlib import Path


class LockManager:
    """Cross-platform file lock manager to prevent concurrent access"""

    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.acquired = False

    def acquire(self, timeout: int = 5):
        """Acquire lock with timeout. Returns True if successful."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try to create lock file exclusively (fails if exists)
                # Use 'x' mode which fails if file exists (atomic on most systems)
                fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self.acquired = True
                return True
            except FileExistsError:
                # Lock file exists, check if process is still alive
                if self._is_stale_lock():
                    # Remove stale lock and retry
                    try:
                        self.lock_file.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                # Active lock, wait a bit
                time.sleep(0.1)
            except Exception:
                # Other errors, wait and retry
                time.sleep(0.1)
        return False

    def _is_stale_lock(self):
        """Check if lock file is stale (process no longer exists)"""
        try:
            if not self.lock_file.exists():
                return False
            with open(self.lock_file, 'r') as f:
                pid = int(f.read().strip())

            # Check if process exists (cross-platform)
            if sys.platform == 'win32':
                import ctypes
                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_INFORMATION = 0x0400
                handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return False
                return True
            else:
                # Unix/Linux - send signal 0 to check if process exists
                try:
                    os.kill(pid, 0)
                    return False  # Process exists
                except OSError:
                    return True  # Process doesn't exist
        except (ValueError, FileNotFoundError, PermissionError):
            return True

    def release(self):
        """Release the lock"""
        if self.acquired:
            try:
                self.lock_file.unlink()
            except FileNotFoundError:
                pass
            self.acquired = False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("Could not acquire lock: another instance is running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
