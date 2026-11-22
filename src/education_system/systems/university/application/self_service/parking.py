"""My Parking: the signed-in student's own permits, vehicles and fines.

The Parking Management window lists every permit, vehicle and violation on
campus, which is right for the parking office and wrong for a student. This
reads only the student's rows: permits and vehicles keyed on their student
number or their university ``users.id``, and violations on those vehicles.
Applying for a permit or paying a fine stays with the parking office.

Functions take an open connection and only read.
"""

from __future__ import annotations

from education_system.systems.university.application.self_service.identity import (
    Student,
    table_columns,
)

UNPAID = ("unpaid", "pending", "outstanding", "overdue", "")


def _owner_clause(columns: set[str], student: Student, *, id_column: str) -> tuple[str, list]:
    """``(sql, params)`` matching rows owned by *student*, or ``("", [])``."""
    parts, params = [], []
    if "student_id" in columns:
        parts.append("student_id = ?")
        params.append(student.student_id)
    if id_column in columns and student.user_pk is not None:
        parts.append(f"{id_column} = ?")
        params.append(student.user_pk)
    return (" OR ".join(parts), params) if parts else ("", [])


def _rows(conn, sql: str, params) -> list[dict]:
    cur = conn.execute(sql, tuple(params))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def own_permits(conn, student: Student) -> list[dict]:
    columns = table_columns(conn, "parking_permits")
    where, params = _owner_clause(columns, student, id_column="user_id")
    if not where:
        return []
    # db-audit: ignore[DBW001] - where is built from fixed column names only
    return _rows(conn, f"SELECT * FROM parking_permits WHERE {where} "  # nosec B608
                       "ORDER BY COALESCE(end_date, '') DESC", params)


def own_vehicles(conn, student: Student) -> list[dict]:
    columns = table_columns(conn, "vehicles")
    where, params = _owner_clause(columns, student, id_column="owner_id")
    if not where:
        return []
    # db-audit: ignore[DBW001] - where is built from fixed column names only
    return _rows(conn, f"SELECT * FROM vehicles WHERE {where} ORDER BY license_plate",  # nosec B608
                 params)


def own_violations(conn, vehicles: list[dict]) -> list[dict]:
    """Violations recorded against the student's vehicles (by id or plate)."""
    if not vehicles or not table_columns(conn, "parking_violations"):
        return []
    ids = [v["vehicle_id"] for v in vehicles if v.get("vehicle_id")]
    plates = [v["license_plate"] for v in vehicles if v.get("license_plate")]
    clauses, params = [], []
    if ids:
        clauses.append(f"vehicle_id IN ({', '.join('?' for _ in ids)})")
        params.extend(ids)
    if plates:
        clauses.append(f"license_plate IN ({', '.join('?' for _ in plates)})")
        params.extend(plates)
    if not clauses:
        return []
    # db-audit: ignore[DBW001] - clauses are placeholder joins over fixed columns
    return _rows(conn, f"SELECT * FROM parking_violations WHERE {' OR '.join(clauses)} "  # nosec B608
                       "ORDER BY violation_date DESC", params)


def outstanding_fines(violations: list[dict]) -> float:
    total = 0.0
    for v in violations:
        status = str(v.get("payment_status") or v.get("status") or "").lower()
        if status in UNPAID:
            total += float(v.get("fine_amount") or 0)
    return round(total, 2)


def my_parking(conn, student: Student) -> dict:
    """Everything the My Parking page shows, for *student* only."""
    vehicles = own_vehicles(conn, student)
    violations = own_violations(conn, vehicles)
    return {
        "permits": own_permits(conn, student),
        "vehicles": vehicles,
        "violations": violations,
        "outstanding": outstanding_fines(violations),
    }
