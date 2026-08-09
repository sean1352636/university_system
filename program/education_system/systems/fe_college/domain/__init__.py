"""Domain layer: pure models and rules for the FE College system.

Nothing in this package performs I/O. Every module here is importable without a
database, which is what lets the rules be unit-tested and reused unchanged by
the GUI, the CLI and the API.
"""
