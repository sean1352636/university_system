"""
CLI System Package

This package provides the command-line interface for the University Management System.
Submodules are imported directly by consumers (e.g.
``from ...cli.utils import safe_auth_check``).

This __init__ intentionally avoids eagerly re-exporting everything to keep
startup fast.  For the main entry point use:

    from education_system.university_system.modules.shared.cli.cli_main import main
"""

__version__ = '5.0.0'
__author__ = 'University Management System Team'
__description__ = 'Modular CLI system for university management'
