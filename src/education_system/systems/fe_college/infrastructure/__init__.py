"""Infrastructure layer: SQLite persistence for the FE College system.

The only layer that knows SQL. Services depend on the repositories under
``persistence.repositories``; nothing above this package imports ``sqlite3``.
"""
