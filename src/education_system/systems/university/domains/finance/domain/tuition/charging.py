"""Charge a year's programme tuition when a student registers.

One ``tuition_charges`` row per student and academic year. The charge uses
the student's fee basis (``fee_status.current``), their programme, mode of
study and FTE, and the rate found by ``rates.resolve``. An active
sponsorship agreement splits it: the sponsor's share goes on the sponsor's
invoice (``billing.add_line``) and only the remainder is charged to the
student as an unpaid ``student_fees`` row, which is what every Finance fee
screen, statement and the ledger already read.

Charging is idempotent: a year already charged is left alone. When the
charge cannot be made (no fee status, no rate, no tuition fee type) the row
records why and the next attempt - another registration, the outbox
backstop or "Charge now" in Finance - tries again.

Functions take an open connection and do not commit; after committing,
the caller runs :func:`post_to_ledger` with the result.
"""

from __future__ import annotations

from education_system.systems.university.domains.finance.domain.tuition import (
    access,
    billing,
    fee_status,
    rates,
    sponsors,
)

DONE = ("charged", "adjusted")


def tuition_fee_type(conn, basis) -> int | None:
    """An active tuition fee type for the basis (International ... for
    international, any other tuition type for home / islands)."""
    if not access.has_table(conn, "fee_types"):
        return None
    cols = {r[1] for r in conn.execute("PRAGMA table_info(fee_types)")}
    active = "COALESCE(is_active, 1) = 1" if "is_active" in cols else "1 = 1"
    rows = conn.execute(f"SELECT fee_type_id, fee_name FROM fee_types WHERE {active} "  # nosec B608
                        "ORDER BY fee_type_id").fetchall()
    wanted_international = basis == "international"
    preferred = None
    for fid, name in rows:
        lowered = str(name or "").lower()
        if "tuition" not in lowered or ("international" in lowered) != wanted_international:
            continue
        if wanted_international or "undergraduate" in lowered or lowered == "tuition fee":
            return int(fid)
        preferred = preferred or int(fid)
    return preferred


def _programme(conn, course) -> str | None:
    if not course:
        return None
    if access.has_table(conn, "courses"):
        row = conn.execute("SELECT COALESCE(NULLIF(course_code, ''), code) FROM courses WHERE "
                           "? IN (course_code, code, course_name, name) LIMIT 1",
                           (course,)).fetchone()
        if row and row[0]:
            return str(row[0])
    return str(course)


def charge_for(conn, student_id) -> dict | None:
    return access.one(conn.execute("SELECT * FROM tuition_charges WHERE student_id = ? ORDER BY "
                                   "academic_year DESC LIMIT 1", (str(student_id),)))


def charge_row(conn, student_id, academic_year) -> dict | None:
    return access.one(conn.execute(
        "SELECT * FROM tuition_charges WHERE student_id = ? AND substr(academic_year, 1, 4) = ?",
        (str(student_id), str(access.year_start(academic_year)))))


def _save(conn, existing, values: dict) -> int:
    if existing:
        sets = ", ".join(f"{k} = ?" for k in values)  # keys are this module's own
        conn.execute(f"UPDATE tuition_charges SET {sets}, charged_at = datetime('now') "  # nosec B608
                     "WHERE charge_id = ?", (*values.values(), existing["charge_id"]))
        return int(existing["charge_id"])
    cols = list(values)
    return int(conn.execute(
        f"INSERT INTO tuition_charges ({', '.join(cols)}) VALUES "  # nosec B608
        f"({', '.join('?' for _ in cols)})", tuple(values.values())).lastrowid)


def _student_fee(conn, student_id, fee_type_id, amount, due_date, description) -> int:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(student_fees)")}
    values = {"student_id": str(student_id), "fee_type_id": fee_type_id, "amount": amount,
              "currency": "GBP", "status": "unpaid", "due_date": due_date,
              "created_at": access.now(), "updated_at": access.now()}
    if "description" in cols:
        values["description"] = description
    if "fee_type" in cols:
        values["fee_type"] = "tuition"
    names = list(values)
    return int(conn.execute(
        f"INSERT INTO student_fees ({', '.join(names)}) VALUES "  # nosec B608
        f"({', '.join('?' for _ in names)})", tuple(values.values())).lastrowid)


def _publish(conn, fee_id, student_id, amount, year) -> None:
    if not access.has_table(conn, "university_event_outbox"):
        return
    from education_system.systems.university.infrastructure.events import (
        transactional_publisher,
    )
    transactional_publisher.publish(
        conn, "fee.assessed",
        {"student_fee_id": fee_id, "student_id": str(student_id), "module_code": None,
         "amount": amount, "currency": "GBP", "academic_year": year, "kind": "tuition"},
        aggregate_id=str(student_id), idempotency_key=f"fee:{fee_id}:assessed")


def _context(conn, student_id, academic_year, mode, fte):
    st = access.student_row(conn, student_id)
    programme = _programme(conn, st.get("course"))
    mode = mode or st.get("mode_of_study") or "full-time"
    fte = rates._fte(fte) if fte not in (None, "") else rates.student_fte(conn, student_id, mode)
    basis = fee_status.current(conn, student_id, academic_year)
    return st, programme, mode, fte, basis


def charge_for_registration(conn, student_id, academic_year, *, actor, mode=None,
                            fte=None) -> dict:
    """Charge the year's tuition (idempotent). Returns the charge row plus
    ``created`` (a new fee was raised) and ``message``."""
    access.ensure(conn)
    year = access.year_label(academic_year)
    existing = charge_row(conn, student_id, year)
    if existing and existing["status"] in DONE:
        return {**existing, "created": False, "message": f"{year} tuition already charged"}
    st, programme, mode, fte, basis = _context(conn, student_id, year, mode, fte)
    base = {"student_id": str(student_id), "academic_year": year, "programme_code": programme,
            "fee_basis": basis["basis"], "basis_source": basis["source"],
            "mode_of_study": mode, "fte": fte, "charged_by": str(actor)}
    if not basis["basis"]:
        return _not_charged(conn, existing, base, "no_fee_status",
                            "Fee status not assessed - assess it, then charge")
    gross, due, source = rates.resolve(conn, programme, year, basis["basis"], mode, fte)
    if gross is None:
        return _not_charged(conn, existing, base, "no_rate", source)
    fee_type_id = tuition_fee_type(conn, basis["basis"])
    if fee_type_id is None:
        return _not_charged(conn, existing, base, "no_fee_type",
                            "No active tuition fee type in Finance - add one in Fees")
    return _charge(conn, existing, base, st, gross, due, source, fee_type_id)


def _not_charged(conn, existing, base, status, why) -> dict:
    charge_id = _save(conn, existing, {**base, "status": status, "note": why,
                                       "gross_amount": 0, "sponsor_amount": 0,
                                       "student_amount": 0})
    access.audit(conn, base["charged_by"], f"tuition.{status}", "tuition_charge", charge_id,
                 student_id=base["student_id"], detail={"why": why, **base})
    return {**base, "charge_id": charge_id, "status": status, "note": why, "created": False,
            "message": why}


def _charge(conn, existing, base, st, gross, due, source, fee_type_id) -> dict:
    year, sid = base["academic_year"], base["student_id"]
    agreement = sponsors.active_agreement(conn, sid, year)
    sponsor_amount = sponsors.sponsor_share(conn, agreement, gross)
    student_amount = round(gross - sponsor_amount, 2)
    label = (f"Tuition {year} - {base['programme_code']} ({base['fee_basis']}, "
             f"{base['mode_of_study']}" + (f", {base['fte']:g} FTE" if base["fte"] else "") + ")")
    fee_id = None
    if student_amount > 0:
        fee_id = _student_fee(conn, sid, fee_type_id, student_amount, due, label)
        _publish(conn, fee_id, sid, student_amount, year)
    values = {**base, "status": "charged", "rate_source": source, "gross_amount": gross,
              "sponsor_amount": sponsor_amount, "student_amount": student_amount,
              "student_fee_id": fee_id,
              "agreement_id": agreement["agreement_id"] if sponsor_amount else None,
              "note": None}
    charge_id = _save(conn, existing, values)
    if sponsor_amount:
        line_id = billing.add_line(conn, base["charged_by"], agreement, sid, year,
                                   sponsor_amount, f"{label} - {st['name']} - sponsor share",
                                   charge_id)
        conn.execute("UPDATE tuition_charges SET sponsor_line_id = ? WHERE charge_id = ?",
                     (line_id, charge_id))
    access.audit(conn, base["charged_by"], "tuition.charged", "tuition_charge", charge_id,
                 student_id=sid, detail={**values, "sponsor": (agreement or {}).get("sponsor")})
    message = f"{year} tuition £{gross:,.2f} charged"
    if sponsor_amount:
        message += (f" (£{sponsor_amount:,.2f} invoiced to {agreement['sponsor']}, "
                    f"£{student_amount:,.2f} to the student)")
    return {**values, "charge_id": charge_id, "created": True, "message": message}


def post_to_ledger(result: dict | None) -> None:
    """After the caller commits: post a new student tuition fee to the GL
    (never raises; a no-op when the ledger is not set up)."""
    if not result or not result.get("created") or not result.get("student_fee_id"):
        return
    try:
        from education_system.systems.university.domains.finance.domain.ledger import (
            notify_ledger,
        )
        notify_ledger("fee_assignment", result["student_fee_id"], posted_by="tuition")
    except Exception:  # pragma: no cover - the hook itself never raises
        pass


def charges(conn, *, status=None, academic_year=None) -> list[dict]:
    access.ensure(conn)
    sql = ("SELECT c.*, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
           "AS name FROM tuition_charges c LEFT JOIN students s ON s.student_id = c.student_id "
           "WHERE 1 = 1")
    params: list = []
    if status == "awaiting":
        sql += " AND c.status NOT IN ('charged', 'adjusted')"
    elif status:
        sql += " AND c.status = ?"
        params.append(status)
    if academic_year:
        sql += " AND substr(c.academic_year, 1, 4) = ?"
        params.append(str(access.year_start(academic_year)))
    return access.dicts(conn.execute(sql + " ORDER BY c.charge_id DESC", params))


def charge_now(conn, who, student_id, academic_year, *, mode=None, fte=None) -> dict:
    """Finance's "Charge now" / retry (needs the tuition capability)."""
    access.require(conn, who, access.TUITION)
    return charge_for_registration(conn, student_id, academic_year, actor=who.username,
                                   mode=mode, fte=fte)
