"""Storage module - backward compatibility wrapper"""

# For backward compatibility, export all classes from storage_impl
from .storage_impl import Storage, StateManager, LockManager, create_demo_case

__all__ = ['Storage', 'StateManager', 'LockManager', 'create_demo_case']
