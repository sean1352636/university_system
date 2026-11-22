"""What a student (or staff looking at one student) sees about tuition: fee
status, this year's tuition and who pays it, finance holds and what they
block, the fee-liability position if they left today, and any liability
adjustments already made. Read-only.
"""

from __future__ import annotations

from education_system.systems.university.domains.finance.domain.tuition import (
    access,
    charging,
    fee_status,
    liability,
    sponsors,
)


def _holds(conn, student_id) -> list[dict]:
    if not access.has_table(conn, "finance_holds"):
        return []
    return access.dicts(conn.execute(
        "SELECT hold_id, amount, reason, source, placed_at FROM finance_holds WHERE "
        "student_id = ? AND is_active = 1 ORDER BY placed_at DESC", (str(student_id),)))


def summary(conn, who, student_id) -> dict:
    access.ensure(conn)
    access.require_self_or(conn, who, student_id, access.FEE_STATUS)
    year = access.year_of(access.today())
    charge = charging.charge_row(conn, student_id, year) or charging.charge_for(conn, student_id)
    status = fee_status.current(conn, student_id, year)
    pending = fee_status.listing(conn, who, status="submitted", student_id=student_id)
    return {
        "academic_year": year,
        "fee_status": status,
        "assessment_pending": bool(pending),
        "charge": charge,
        "sponsorship": sponsors.active_agreement(conn, student_id, year),
        "holds": _holds(conn, student_id),
        "liability_if_leaving_today": liability.preview(
            conn, student_id, access.today(), charge["academic_year"] if charge else year),
        "adjustments": liability.adjustments(conn, student_id=student_id),
    }


def lines(data: dict) -> list[str]:
    """The summary as plain lines (CLI and the account card share them)."""
    out = [f"Fee status: {data['fee_status']['label']} ({data['fee_status']['source']})"]
    if data["assessment_pending"]:
        out.append("A fee-status questionnaire is waiting for Student Finance's decision.")
    charge = data["charge"]
    if charge and charge["status"] in charging.DONE:
        out.append(f"Tuition {charge['academic_year']}: £{charge['gross_amount']:,.2f} "
                   f"({charge['programme_code']}, {charge['mode_of_study']})")
        if charge["sponsor_amount"]:
            out.append(f"  Your sponsor pays £{charge['sponsor_amount']:,.2f}; you pay "
                       f"£{charge['student_amount']:,.2f}")
    elif charge:
        out.append(f"Tuition {charge['academic_year']}: not charged yet - {charge['note']}")
    else:
        out.append("No tuition charged yet.")
    if data["sponsorship"]:
        sp = data["sponsorship"]
        share = f"{sp['value']:g}%" if sp["basis"] == "percent" else f"£{sp['value']:,.2f}/yr"
        out.append(f"Sponsor: {sp['sponsor']} ({share})")
    for hold in data["holds"]:
        out.append(f"HOLD: {hold['reason']} (£{float(hold['amount'] or 0):,.2f}, placed "
                   f"{str(hold['placed_at'])[:10]}) - this blocks registration until it is "
                   "cleared; contact Student Finance")
    preview = data["liability_if_leaving_today"]
    if preview.get("liable_amount") is not None:
        out.append(f"If you withdrew today you would be liable for {preview['liable_percent']:g}%"
                   f" ({preview['explanation']}): £{preview['student_liable']:,.2f} of your "
                   "share")
    elif charge:
        out.append(f"Liability if leaving today: {preview['explanation']}")
    for adj in data["adjustments"]:
        out.append(f"Adjustment ({adj['status']}): {adj['note'] or adj['action']}")
    return out
