"""Launcher orchestration for the Education System.

Splits the monolithic run.py into focused modules:

- auth: shared auth initialisation & MFA sync
- systems: per-system bootstrap & launcher functions + dispatch table
- menus: CLI interactive mode/system selection menus
- roles: superadmin role-picker dialogs (GUI & CLI)
- dispatch: GUI/CLI dispatch loops with system-switch handling
"""
