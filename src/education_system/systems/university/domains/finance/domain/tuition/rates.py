"""Programme-level annual tuition rates by (programme, academic year, fee
basis, mode of study, FTE).

Lookup order for a student, most specific first:

1. a rate for exactly that mode and FTE;
2. a flat rate for the mode (FTE left blank);
3. the full-time rate (FTE blank or 1.0) pro rata to the student's FTE;
4. the programme's tuition in ``program_fees`` (what the Programme Record's
   Fees tab sets, home / international only), pro rata to the FTE.

Module fees are separate and unchanged: a module with its own
``program_fees`` row is still charged on enrolment by
``services/enrolment_fees``. A programme priced only by module simply has
no programme rate.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from education_system.systems.university.domains.finance.domain.tuition import access

MODES = ("full-time", "part-time", "distance", "sandwich")
BASES = ("home", "islands", "international")
#: 120 credits is one full-time year (the UK FTE convention).
CREDITS_PER_FTE = 120


def _fte(value):
    if value in (None, ""):
        return None
    try:
        fte = round(float(value), 3)
    except (TypeError, ValueError):
        raise ValueError("FTE must be a number between 0 and 1") from None
    if not 0 < fte <= 1:
        raise ValueError("FTE must be more than 0 and at most 1")
    return fte


def set_rate(conn, who, programme_code, academic_year, fee_basis, mode_of_study, fte,
             annual_fee, due_date=None) -> int:
    access.ensure(conn)
    access.require(conn, who, access.TUITION)
    code = access.text(programme_code, "Programme", True)
    if fee_basis not in BASES:
        raise ValueError("Fee basis is home, islands or international")
    if mode_of_study not in MODES:
        raise ValueError("Mode of study must be one of: " + ", ".join(MODES))
    year, fte, fee = access.year_label(academic_year), _fte(fte), access.money(annual_fee,
                                                                               "Annual fee")
    existing = conn.execute(
        "SELECT rate_id, annual_fee FROM programme_tuition_rates WHERE programme_code = ? AND "
        "academic_year = ? AND fee_basis = ? AND mode_of_study = ? AND fte IS ?",
        (code, year, fee_basis, mode_of_study, fte)).fetchone()
    if existing:
        conn.execute("UPDATE programme_tuition_rates SET annual_fee = ?, due_date = ?, "
                     "updated_by = ?, updated_at = datetime('now') WHERE rate_id = ?",
                     (fee, due_date or None, who.username, existing[0]))
        rate_id, before = existing[0], existing[1]
    else:
        rate_id = conn.execute(
            "INSERT INTO programme_tuition_rates (programme_code, academic_year, fee_basis, "
            "mode_of_study, fte, annual_fee, due_date, updated_by) VALUES (?, ?, ?, ?, ?, ?, "
            "?, ?)", (code, year, fee_basis, mode_of_study, fte, fee, due_date or None,
                      who.username)).lastrowid
        before = None
    access.audit(conn, who.username, "tuition_rate.set", "programme_tuition_rate", rate_id,
                 detail={"programme": code, "year": year, "basis": fee_basis,
                         "mode": mode_of_study, "fte": fte, "fee": fee, "was": before})
    return int(rate_id)


def delete_rate(conn, who, rate_id) -> None:
    access.ensure(conn)
    access.require(conn, who, access.TUITION)
    row = access.one(conn.execute("SELECT * FROM programme_tuition_rates WHERE rate_id = ?",
                                  (int(rate_id),)))
    if not row:
        raise ValueError(f"No tuition rate {rate_id}")
    conn.execute("DELETE FROM programme_tuition_rates WHERE rate_id = ?", (int(rate_id),))
    access.audit(conn, who.username, "tuition_rate.deleted", "programme_tuition_rate", rate_id,
                 detail=row)


def rates(conn, programme_code=None, academic_year=None) -> list[dict]:
    access.ensure(conn)
    sql, params = "SELECT * FROM programme_tuition_rates WHERE 1 = 1", []
    if programme_code:
        sql += " AND programme_code = ?"
        params.append(programme_code)
    if academic_year:
        sql += " AND substr(academic_year, 1, 4) = ?"
        params.append(str(access.year_start(academic_year)))
    return access.dicts(conn.execute(sql + " ORDER BY academic_year DESC, programme_code, "
                                     "fee_basis, mode_of_study, fte", params))


def _row(conn, code, start, basis, mode, fte_clause, params=()):
    return conn.execute(
        "SELECT annual_fee, due_date, rate_id FROM programme_tuition_rates WHERE "
        "programme_code = ? AND substr(academic_year, 1, 4) = ? AND fee_basis = ? AND "
        f"mode_of_study = ? AND {fte_clause} ORDER BY rate_id DESC LIMIT 1",  # nosec B608
        (code, str(start), basis, mode, *params)).fetchone()


def _program_fees(conn, code, start, basis):
    if basis == "islands" or not access.has_table(conn, "program_fees"):
        return None
    for amount, due, name in conn.execute(
            "SELECT p.amount, p.due_date, t.fee_name FROM program_fees p JOIN fee_types t ON "
            "t.fee_type_id = p.fee_type_id WHERE p.course = ? AND substr(COALESCE("
            "p.academic_year, ''), 1, 4) = ? ORDER BY p.program_fee_id DESC", (code, str(start))):
        lowered = str(name or "").lower()
        if "tuition" in lowered and (("international" in lowered) == (basis == "international")):
            return amount, due
    return None


def resolve(conn, programme_code, academic_year, fee_basis, mode_of_study, fte):
    """``(annual amount, due date, how it was found)`` or ``(None, None, why not)``."""
    access.ensure(conn)
    start = access.year_start(academic_year)
    mode = mode_of_study if mode_of_study in MODES else "full-time"
    if fte is not None:
        row = _row(conn, programme_code, start, fee_basis, mode, "abs(fte - ?) < 0.0005", (fte,))
        if row:
            return round(float(row[0]), 2), row[1], f"rate #{row[2]} ({mode}, {fte} FTE)"
    row = _row(conn, programme_code, start, fee_basis, mode, "fte IS NULL")
    if row:
        return round(float(row[0]), 2), row[1], f"rate #{row[2]} ({mode})"
    if fte is not None:
        row = _row(conn, programme_code, start, fee_basis, "full-time",
                   "(fte IS NULL OR fte = 1)")
        if row:
            return (round(float(row[0]) * fte, 2), row[1],
                    f"full-time rate #{row[2]} x {fte} FTE")
        fallback = _program_fees(conn, programme_code, start, fee_basis)
        if fallback:
            return (round(float(fallback[0]) * fte, 2), fallback[1],
                    f"Programme Record fee x {fte} FTE")
    return None, None, (f"no {fee_basis} {mode} tuition rate for {programme_code} in "
                        f"{access.year_label(start)}"
                        + ("" if fte is not None else " (and the FTE is not known)"))


def student_fte(conn, student_id, mode_of_study) -> float | None:
    """Full-time and sandwich students are 1.0 FTE; others by enrolled
    credits (120 = 1.0). None when no credits are recorded."""
    if (mode_of_study or "full-time") in ("full-time", "sandwich"):
        return 1.0
    if not (access.has_table(conn, "student_modules") and access.has_table(conn, "modules")):
        return None
    total = conn.execute(
        "SELECT COALESCE(SUM(NULLIF(m.credits, 0)), 0) FROM student_modules sm JOIN modules m "
        "ON m.module_code = sm.module_code WHERE sm.student_id = ? AND sm.status = 'Enrolled'",
        (str(student_id),)).fetchone()[0]
    if not total:
        return None
    return round(min(1.0, float(total) / CREDITS_PER_FTE), 3)
