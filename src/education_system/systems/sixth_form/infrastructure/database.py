"""SQLite access for the Sixth Form domain layer.

``domain/`` may not import the database driver (tools/check_layout.py,
``domain-forbidden-import``), so domain modules reach SQLite through
this module instead, the same way the nursery domain uses
``nursery.infrastructure.database``. The names below are the driver's
own, so a domain module uses ``db.connect`` / ``db.Row`` /
``db.IntegrityError`` exactly as it would ``sqlite3.*``.
"""

from __future__ import annotations

import sqlite3

Connection = sqlite3.Connection
Row = sqlite3.Row
Error = sqlite3.Error
DatabaseError = sqlite3.DatabaseError
IntegrityError = sqlite3.IntegrityError
OperationalError = sqlite3.OperationalError
connect = sqlite3.connect

__all__ = [
    "Connection", "Row", "Error", "DatabaseError", "IntegrityError",
    "OperationalError", "connect",
]
