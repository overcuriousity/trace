"""TUI (Text User Interface) package for trace application"""

# Import from the main tui_app module for backward compatibility
# The tui_app.py file contains the main TUI class and run_tui function
from ..tui_app import run_tui, TUI

__all__ = ['run_tui', 'TUI']
