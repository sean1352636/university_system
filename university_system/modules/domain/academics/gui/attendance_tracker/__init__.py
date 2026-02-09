# Re-exports AttendanceGUI and standalone functions for backward compatibility
from .main import AttendanceGUI, run_gui, main, start_gui, start_cli

__all__ = ['AttendanceGUI', 'run_gui', 'main', 'start_gui', 'start_cli']
