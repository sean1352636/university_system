"""Which modules a member of staff can see in the Assignment System. Admins
see every module; everyone else sees the modules they teach, support or have
set an assignment on."""

from __future__ import annotations


def _has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def _columns(conn, table) -> set[str]:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def _user_ids(conn, username, user_id) -> list[str]:
    """auth.db and student_records.db number the same person differently."""
    ids = {str(user_id)} if user_id not in (None, "") else set()
    if username and _has_table(conn, "users"):
        row = conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE",
                           (username,)).fetchone()
        if row:
            ids.add(str(row[0]))
    return sorted(ids)


def _instructor_ids(conn, username, ids) -> list[str]:
    """``module_schedule`` and ``instructor_modules`` hold ``instructors.id``."""
    found = list(ids)
    if _has_table(conn, "instructors") and _has_table(conn, "users") and username:
        found += [str(r[0]) for r in conn.execute(
            "SELECT i.id FROM instructors i JOIN users u ON LOWER(u.email) = LOWER(i.email) "
            "WHERE u.username = ? COLLATE NOCASE AND COALESCE(u.email, '') <> ''", (username,))]
    return sorted(set(found))


def _in(values) -> str:
    return ",".join("?" * len(values))


def modules_for(conn, username, user_id, role) -> set[str] | None:
    """The module codes this person can see; ``None`` means every module."""
    if str(role or "").lower() == "admin":
        return None
    ids = _user_ids(conn, username, user_id)
    modules: set[str] = set()
    if username and _has_table(conn, "module_staff"):
        modules |= {r[0] for r in conn.execute(
            "SELECT module_code FROM module_staff WHERE username = ? COLLATE NOCASE", (username,))}
    if _has_table(conn, "modules"):
        cols = _columns(conn, "modules")
        if username and "instructor" in cols:
            modules |= {r[0] for r in conn.execute(
                "SELECT module_code FROM modules WHERE instructor = ? COLLATE NOCASE", (username,))}
        if ids and "instructor_id" in cols:
            modules |= {r[0] for r in conn.execute(
                f"SELECT module_code FROM modules WHERE CAST(instructor_id AS TEXT) "  # nosec B608
                f"IN ({_in(ids)})", ids)}
    teaching = _instructor_ids(conn, username, ids)
    for table in ("module_schedule", "instructor_modules"):
        if teaching and _has_table(conn, table):
            modules |= {r[0] for r in conn.execute(
                f"SELECT module_code FROM {table} WHERE CAST(instructor_id AS TEXT) "  # nosec B608
                f"IN ({_in(teaching)})", teaching)}
    if ids and _has_table(conn, "ta_assignments"):
        modules |= {r[0] for r in conn.execute(
            f"SELECT module_code FROM ta_assignments WHERE COALESCE(is_active, 1) = 1 "  # nosec B608
            f"AND CAST(COALESCE(ta_user_id, user_id) AS TEXT) IN ({_in(ids)})", ids)}
    if ids and _has_table(conn, "assignments"):
        modules |= {r[0] for r in conn.execute(
            f"SELECT module_code FROM assignments WHERE CAST(created_by AS TEXT) "  # nosec B608
            f"IN ({_in(ids)})", ids)}
    modules.discard(None)
    return modules


def sql_filter(modules, column="a.module_code") -> tuple[str, list]:
    """``(" AND …", params)`` limiting a query to ``modules``."""
    if modules is None:
        return "", []
    if not modules:
        return " AND 1 = 0", []
    ordered = sorted(modules)
    return f" AND {column} IN ({_in(ordered)})", ordered
