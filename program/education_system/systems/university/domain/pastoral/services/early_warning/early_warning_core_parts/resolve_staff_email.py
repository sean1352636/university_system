"""Extracted function implementation."""

from .. import early_warning_core_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _resolve_staff_email(cursor, identifier: str) -> Optional[str]:
    """Resolve a staff/user email from an identifier that may be a username,
    a numeric user/staff id, or already an email address."""
    if not identifier:
        return None
    ident = str(identifier).strip()
    if "@" in ident:
        return ident
    # Try the users table (username or id), then the staff table.
    for table, col in (("users", "username"), ("users", "id"),
                       ("staff", "username"), ("staff", "id")):
        try:
            cursor.execute(
                f"SELECT email FROM {table} WHERE {col} = ? "  # nosec B608 - literals only
                f"AND email IS NOT NULL AND TRIM(email) <> '' LIMIT 1",
                (ident,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            continue
    return None
