"""
Shared Extras Module

Tools, utilities, and applications available to all education systems
(university, college, secondary school, primary school).

Contents:
- calculator.py: Full-featured calculator with dark theme
- countdown.py: Countdown timer and clock
- decision-maker/: Multi-criteria decision analysis tool
- evidence-organizer/: Digital evidence and case management
- habit-tracker/: Daily habit tracking with streaks and points
- hash-generator/: Cryptographic hash generation and verification
- log-analyzer/: Log file analysis with visualization
- password-analyzer/: Password strength analysis and generation
- query-builder/: Visual SQL query builder for SQLite
- random-skill-generator/: Learning skill suggestions and tracking
- launcher.py: GUI launcher for all extras
"""

from pathlib import Path

EXTRAS_DIR = Path(__file__).parent


def get_extras_path():
    """Return the path to the shared extras directory."""
    return EXTRAS_DIR


def launch_extras_gui(parent_window=None):
    """Launch the shared extras launcher GUI.

    Args:
        parent_window: Optional parent Tk window. If provided, opens as
                       a Toplevel child window. Otherwise opens standalone.
    """
    from education_system.shared.extras.launcher import main, launch_as_toplevel

    if parent_window is not None:
        return launch_as_toplevel(parent_window)
    else:
        main()
