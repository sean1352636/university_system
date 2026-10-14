"""Launcher orchestration for the Education System.

Splits the original monolithic launcher into focused modules:

- main: ``main()`` and command-line argument parsing — the entry point itself
- environment: launch-time ``APP_ENV`` default (dependency-free; safe to import)
- auth: shared auth initialisation & MFA sync
- systems: per-system bootstrap & launcher functions + dispatch table
- menus: CLI interactive mode/system selection menus
- roles: superadmin role-picker dialogs (GUI & CLI)
- dispatch: GUI/CLI dispatch loops with system-switch handling

``main`` is deliberately *not* re-exported here. Importing it has module-level
side effects (loading the root ``.env``, configuring logging), so it should be
paid for only by callers that actually launch the application — importing a
sibling such as ``education_system.launcher.systems`` must stay cheap.
"""
