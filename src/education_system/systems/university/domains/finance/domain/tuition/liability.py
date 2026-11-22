"""Tuition fee liability when a student withdraws or interrupts.

A configurable schedule says what share of the year's tuition the student
is liable for by the term the change takes effect in, counted against the
academic calendar's terms (``academic_terms``). Default: nothing before the
first term starts, 25% in term 1, 50% in term 2 and 100% from term 3 (or
once the last term has ended). A schedule saved for a specific year wins
over the general one.

Applying it to a withdrawal / interruption credits back the unliable part
of the year's tuition: an unpaid fee is reduced or cancelled, money already
paid beyond the liability becomes a *refund request* through the existing
Refunds flow (never paid automatically), and the sponsor's share is credited
on the sponsor's invoice (with a sponsor refund request if they overpaid).
One adjustment per lifecycle change (``history_id``), so a re-run is
harmless; a reversed change restores what can be restored.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from education_system.systems.university.domains.finance.domain.tuition import (
    access,
    billing,
    charging,
    sponsors,
)

DEFAULT_SCHEDULE = {0: 0.0, 1: 25.0, 2: 50.0, 3: 100.0}
ACTIONS = ("withdraw", "interrupt")
_GONE = ("superseded", "cancelled")


# ── the schedule ────────────────────────────────────────────────────────


def schedule(conn, academic_year=None) -> dict[int, float]:
    access.ensure(conn)
    for key in ([access.year_label(academic_year)] if academic_year else []) + ["*"]:
        rows = conn.execute("SELECT term_number, liable_percent FROM fee_liability_schedule "
                            "WHERE academic_year = ? ORDER BY term_number", (key,)).fetchall()
        if rows:
            return {int(t): float(p) for t, p in rows}
    return dict(DEFAULT_SCHEDULE)


def set_schedule(conn, who, percents: dict, academic_year=None) -> None:
    """Save ``{term number: liable %}`` (term 0 = before the first term)
    for one academic year, or for every year when ``academic_year`` is
    blank. Percentages may not go down from one term to the next."""
    access.ensure(conn)
    access.require(conn, who, access.TUITION)
    clean = {}
    for term, pct in percents.items():
        term = int(term)
        pct = float(pct)
        if not 0 <= term <= 6 or not 0 <= pct <= 100:
            raise ValueError("Terms are 0-6 and percentages 0-100")
        clean[term] = pct
    ordered = [clean[t] for t in sorted(clean)]
    if ordered != sorted(ordered):
        raise ValueError("Liability cannot fall in a later term")
    key = access.year_label(academic_year) if academic_year else "*"
    before = schedule(conn, academic_year)
    conn.execute("DELETE FROM fee_liability_schedule WHERE academic_year = ?", (key,))
    conn.executemany("INSERT INTO fee_liability_schedule (academic_year, term_number, "
                     "liable_percent, updated_by) VALUES (?, ?, ?, ?)",
                     [(key, t, p, who.username) for t, p in sorted(clean.items())])
    access.audit(conn, who.username, "liability_schedule.set", "fee_liability_schedule", key,
                 detail={"schedule": clean, "was": before})


def terms(conn, academic_year) -> list[dict]:
    if not access.has_table(conn, "academic_terms"):
        return []
    rows = access.dicts(conn.execute(
        "SELECT name, start_date, end_date, status FROM academic_terms WHERE "
        "substr(academic_year, 1, 4) = ? AND COALESCE(start_date, '') != '' ORDER BY "
        "start_date", (str(access.year_start(academic_year)),)))
    return [r for r in rows if str(r.get("status") or "").lower() not in _GONE]


def liable_percent(conn, academic_year, effective_date):
    """``(percent, term number, explanation)``; percent is None when the
    year has no terms in the calendar."""
    found = terms(conn, academic_year)
    if not found:
        return None, None, (f"{access.year_label(academic_year)} has no terms in the academic "
                            "calendar - set the liability by hand")
    day = str(effective_date or access.today())[:10]
    rules = schedule(conn, academic_year)
    started = [t for t in found if str(t["start_date"])[:10] <= day]
    last_end = max(str(t["end_date"] or "")[:10] for t in found)
    if last_end and day > last_end:
        return 100.0, len(found), f"after the last term ended ({last_end})"
    number = len(started)
    if number == 0:
        return rules.get(0, 0.0), 0, f"before {found[0]['name']} started"
    eligible = [t for t in rules if t <= number]
    pct = rules[max(eligible)] if eligible else 0.0
    return pct, number, f"in term {number} ({started[-1]['name']})"


# ── applying it ─────────────────────────────────────────────────────────


def _paid(conn, fee) -> float:
    if access.has_table(conn, "payment_allocations"):
        paid = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payment_allocations WHERE "
                            "student_fee_id = ?", (fee["student_fee_id"],)).fetchone()[0]
        if paid:
            return round(float(paid), 2)
    return round(float(fee["amount"] or 0), 2) if fee["status"] == "paid" else 0.0


def _status(amount, paid) -> str:
    if amount <= 0:
        return "paid" if paid > 0 else "cancelled"
    if paid >= amount:
        return "paid"
    return "partial" if paid > 0 else "unpaid"


def _credit_student(conn, actor, charge, credit, note) -> tuple[float, int | None]:
    """Reduce the student's fee by ``credit``; a refund request for money
    paid beyond the new amount. Returns ``(reduced by, refund id)``."""
    if credit <= 0 or not charge.get("student_fee_id"):
        return 0.0, None
    fee = access.one(conn.execute("SELECT * FROM student_fees WHERE student_fee_id = ?",
                                  (charge["student_fee_id"],)))
    if not fee or fee["status"] == "cancelled":
        return 0.0, None
    current = round(float(fee["amount"] or 0), 2)
    new_amount = round(max(current - credit, 0.0), 2)
    paid = _paid(conn, fee)
    conn.execute("UPDATE student_fees SET amount = ?, status = ?, updated_at = ? WHERE "
                 "student_fee_id = ?", (new_amount, _status(new_amount, paid), access.now(),
                                        fee["student_fee_id"]))
    refund_id = None
    if paid > new_amount:
        refund_id = billing.request_refund(
            conn, actor, amount=round(paid - new_amount, 2), reason=note,
            source_type="tuition_liability", reference_type="student_fee",
            reference_id=fee["student_fee_id"], student_id=charge["student_id"])
    return round(current - new_amount, 2), refund_id


def _record(conn, values: dict) -> dict:
    cols = list(values)
    values["adjustment_id"] = int(conn.execute(
        f"INSERT INTO fee_liability_adjustments ({', '.join(cols)}) VALUES "  # nosec B608
        f"({', '.join('?' for _ in cols)})", tuple(values.values())).lastrowid)
    access.audit(conn, values.get("applied_by"), f"liability.{values['status']}",
                 "fee_liability_adjustment", values["adjustment_id"],
                 student_id=values["student_id"], detail=values)
    return values


def preview(conn, student_id, effective_date=None, academic_year=None) -> dict:
    """What withdrawing on ``effective_date`` would leave the student liable
    for, without changing anything."""
    access.ensure(conn)
    day = str(effective_date or access.today())[:10]
    year = access.year_label(academic_year) if academic_year else access.year_of(day)
    charge = charging.charge_row(conn, student_id, year)
    pct, term, why = liable_percent(conn, year, day)
    out = {"academic_year": year, "effective_date": day, "liable_percent": pct, "term": term,
           "explanation": why, "schedule": schedule(conn, year), "charge": charge}
    if charge and charge["status"] in charging.DONE and pct is not None:
        gross = float(charge["gross_amount"] or 0)
        out["liable_amount"] = round(gross * pct / 100, 2)
        out["student_liable"] = round(float(charge["student_amount"] or 0) * pct / 100, 2)
    return out


def apply(conn, actor, *, student_id, history_id, action, effective_date, academic_year=None,
          percent=None) -> dict:
    """Apply the schedule to one withdrawal / interruption (idempotent on
    ``history_id``). ``percent`` overrides the schedule (staff, by hand)."""
    access.ensure(conn)
    if history_id is not None:
        done = access.one(conn.execute("SELECT * FROM fee_liability_adjustments WHERE "
                                       "history_id = ?", (int(history_id),)))
        if done:
            return done
    day = str(effective_date or access.today())[:10]
    year = access.year_label(academic_year) if academic_year else access.year_of(day)
    base = {"student_id": str(student_id), "history_id": history_id, "action": action,
            "academic_year": year, "effective_date": day, "applied_by": str(actor)}
    charge = charging.charge_row(conn, student_id, year)
    if not charge or charge["status"] not in charging.DONE:
        return _record(conn, {**base, "status": "no_tuition",
                              "note": f"No {year} tuition charge to adjust"})
    if percent is None:
        pct, term, why = liable_percent(conn, year, day)
    else:
        pct, term, why = float(percent), None, "set by hand"
    if pct is None:
        return _record(conn, {**base, "status": "needs_review", "charge_id": charge["charge_id"],
                              "gross_amount": charge["gross_amount"], "note": why})
    return _credit(conn, actor, base, charge, pct, term, why)


def _credit(conn, actor, base, charge, pct, term, why) -> dict:
    unliable = 1 - pct / 100
    student_credit = round(float(charge["student_amount"] or 0) * unliable, 2)
    sponsor_credit = round(float(charge["sponsor_amount"] or 0) * unliable, 2)
    note = (f"{base['action'].title()} effective {base['effective_date']}, {why}: liable for "
            f"{pct:g}% of {base['academic_year']} tuition")
    reduced, refund_id = _credit_student(conn, actor, charge, student_credit, note)
    line_id = sponsor_refund = None
    if sponsor_credit > 0 and charge.get("sponsor_line_id"):
        line_id, sponsor_refund = billing.credit_line(conn, actor, charge["sponsor_line_id"],
                                                      sponsor_credit, note)
    conn.execute("UPDATE tuition_charges SET status = 'adjusted', note = ? WHERE charge_id = ?",
                 (note, charge["charge_id"]))
    return _record(conn, {**base, "status": "applied", "charge_id": charge["charge_id"],
                          "term_number": term, "liable_percent": pct,
                          "gross_amount": charge["gross_amount"],
                          "student_credit": student_credit, "sponsor_credit": sponsor_credit,
                          "fee_reduced_by": reduced, "student_refund_id": refund_id,
                          "sponsor_refund_id": sponsor_refund, "sponsor_line_id": line_id,
                          "note": note})


def resolve_review(conn, who, adjustment_id, percent, note) -> dict:
    """Finance sets the liability for an adjustment the calendar could not
    work out (``needs_review``)."""
    access.ensure(conn)
    access.require(conn, who, access.TUITION)
    note = access.text(note, "Reason", True)
    row = access.one(conn.execute("SELECT * FROM fee_liability_adjustments WHERE "
                                  "adjustment_id = ?", (int(adjustment_id),)))
    if not row or row["status"] != "needs_review":
        raise ValueError("That adjustment is not waiting for review")
    pct = float(percent)
    if not 0 <= pct <= 100:
        raise ValueError("The liable percentage is 0-100")
    charge = access.one(conn.execute("SELECT * FROM tuition_charges WHERE charge_id = ?",
                                     (row["charge_id"],)))
    conn.execute("DELETE FROM fee_liability_adjustments WHERE adjustment_id = ?",
                 (int(adjustment_id),))
    base = {k: row[k] for k in ("student_id", "history_id", "action", "academic_year",
                                "effective_date")}
    return _credit(conn, who.username, {**base, "applied_by": who.username}, charge, pct, None,
                   f"set by {who.username}: {note}")


def _cancel_refund(conn, refund_id) -> bool:
    if not refund_id:
        return True
    return bool(conn.execute("UPDATE unified_refunds SET status = 'cancelled', notes = "
                             "COALESCE(notes, '') || ' [cancelled: lifecycle change reversed]' "
                             "WHERE refund_id = ? AND status = 'pending'",
                             (int(refund_id),)).rowcount)


def reverse(conn, actor, original_history_id) -> dict | None:
    """Undo an applied adjustment when its withdrawal / interruption is
    reversed: the fee goes back up, still-pending refund requests are
    cancelled and the sponsor is re-billed. A refund already approved or paid
    is left alone and noted for Finance."""
    access.ensure(conn)
    row = access.one(conn.execute("SELECT * FROM fee_liability_adjustments WHERE history_id = ? "
                                  "AND status = 'applied'", (int(original_history_id),)))
    if not row:
        return None
    notes = []
    if row["fee_reduced_by"]:
        charge = access.one(conn.execute("SELECT * FROM tuition_charges WHERE charge_id = ?",
                                         (row["charge_id"],)))
        fee = access.one(conn.execute("SELECT * FROM student_fees WHERE student_fee_id = ?",
                                      (charge["student_fee_id"],)))
        if fee:
            amount = round(float(fee["amount"] or 0) + float(row["fee_reduced_by"]), 2)
            conn.execute("UPDATE student_fees SET amount = ?, status = ?, updated_at = ? WHERE "
                         "student_fee_id = ?", (amount, _status(amount, _paid(conn, fee)),
                                                access.now(), fee["student_fee_id"]))
    for key in ("student_refund_id", "sponsor_refund_id"):
        if not _cancel_refund(conn, row[key]):
            notes.append(f"refund #{row[key]} was already approved or paid - review it")
    if row["sponsor_credit"] and row["sponsor_line_id"]:
        _rebill_sponsor(conn, actor, row)
    conn.execute("UPDATE tuition_charges SET status = 'charged', note = ? WHERE charge_id = ?",
                 ("liability adjustment reversed", row["charge_id"]))
    note = "; ".join(notes) or None
    conn.execute("UPDATE fee_liability_adjustments SET status = 'reversed', reversed_at = ?, "
                 "note = COALESCE(note, '') || ? WHERE adjustment_id = ?",
                 (access.now(), f" [reversed{': ' + note if note else ''}]",
                  row["adjustment_id"]))
    access.audit(conn, actor, "liability.reversed", "fee_liability_adjustment",
                 row["adjustment_id"], student_id=row["student_id"], detail={"notes": notes})
    return {**row, "status": "reversed", "notes": notes}


def _rebill_sponsor(conn, actor, row) -> None:
    line = access.one(conn.execute("SELECT * FROM sponsor_invoice_lines WHERE line_id = ?",
                                   (row["sponsor_line_id"],)))
    if not line or not line.get("agreement_id"):
        return
    agreement = sponsors.get_agreement(conn, line["agreement_id"])
    billing.add_line(conn, actor, agreement, row["student_id"], row["academic_year"],
                     row["sponsor_credit"], "Re-billed: withdrawal / interruption reversed",
                     row["charge_id"])


def adjustments(conn, *, status=None, student_id=None) -> list[dict]:
    access.ensure(conn)
    sql = ("SELECT a.*, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
           "AS name FROM fee_liability_adjustments a LEFT JOIN students s ON s.student_id = "
           "a.student_id WHERE 1 = 1")
    params: list = []
    if status:
        sql += " AND a.status = ?"
        params.append(status)
    if student_id:
        sql += " AND a.student_id = ?"
        params.append(str(student_id))
    return access.dicts(conn.execute(sql + " ORDER BY a.adjustment_id DESC", params))
