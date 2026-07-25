# Re-exports AttendanceGUI and standalone functions for backward compatibility
from education_system.systems.university.interfaces.gui.academics.attendance_tracker.main import AttendanceGUI, run_gui, main, start_gui, start_cli

__all__ = ['AttendanceGUI', 'run_gui', 'main', 'start_gui', 'start_cli']
