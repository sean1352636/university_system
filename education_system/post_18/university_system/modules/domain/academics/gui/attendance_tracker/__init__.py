# Re-exports AttendanceGUI and standalone functions for backward compatibility
from education_system.post_18.university_system.modules.domain.academics.gui.attendance_tracker.main import AttendanceGUI, run_gui, main, start_gui, start_cli

__all__ = ['AttendanceGUI', 'run_gui', 'main', 'start_gui', 'start_cli']
