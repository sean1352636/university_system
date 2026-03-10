"""
University System Extras Module

This module contains additional tools, utilities, and games that can be launched
from the main University Management System GUI.

Contents:
- games/: Python games and game projects
- standalone-utilities/: Standalone utility applications
- python-utilities/: Python utility projects
- 91_Python_Mini_Projects-main/: Collection of mini Python projects
- launcher.py: GUI launcher for all extras
"""

from pathlib import Path

# Module paths
EXTRAS_DIR = Path(__file__).parent
GAMES_DIR = EXTRAS_DIR / "games"
STANDALONE_UTILITIES_DIR = EXTRAS_DIR / "standalone-utilities"
PYTHON_UTILITIES_DIR = EXTRAS_DIR / "python-utilities"
MINI_PROJECTS_DIR = EXTRAS_DIR / "91_Python_Mini_Projects-main"


def get_extras_path():
    """Return the path to the extras directory."""
    return EXTRAS_DIR


def launch_extras_gui():
    """Launch the extras program launcher GUI."""
    from education_system.university_system.extras.launcher import main
    main()
