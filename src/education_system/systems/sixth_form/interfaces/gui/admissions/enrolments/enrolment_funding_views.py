"""Funding screens: an enrolment's condition-of-funding position (with
Apply) and fees (due, raise, charges, cancel), the year's condition-of-
funding report, and the way into finance's Fee Rules (finance / funding).
Fees come from finance's one fee schedule; charges are finance's tuition
invoices."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import (
    messagebox,
    simpledialog,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import funding

from . import enrolment_page_kit as kit
from .enrolment_common import _default_academic_year, describe_error, show_error

logger = logging.getLogger(__name__)

GAP_COLS = [("area", "Area", 80), ("grade", "Best grade", 80),
            ("req", "Requirement", 180), ("suggest", "Suggested", 130),
            ("allowed", "Allowed", 220), ("status", "Status", 300)]
CHARGE_COLS = [("id", "#", 50), ("number", "Invoice", 120), ("year", "Year", 70),
               ("fee", "Fee status", 130), ("gross", "Gross", 80),
               ("rem", "Remission", 80), ("net", "Net", 80),
               ("raised", "Issued", 150), ("state", "State", 300)]


def can_fees() -> bool:
    return kit.can("finance", "funding")


def can_raise() -> bool:
    return kit.can("finance", "admissions", "students.manage")


def _money(x) -> str:
    return f"£{(x or 0):,.2f}"


# ── One enrolment ───────────────────────────────────────────────────

def open_funding_and_fees(gui, enrolment_id: int) -> None:
    from .enrolment_views import open_profile
    frame, bar = kit.page(gui, f"Funding & Fees — Enrolment #{enrolment_id}",
                          back=lambda: open_profile(gui, enrolment_id),
                          back_text="Back to Enrolment")
    _cof_section(gui, frame, bar, enrolment_id)
    _fee_section(gui, frame, bar, enrolment_id)
    gui.status_var.set(f"Funding and fees for #{enrolment_id}")


def _cof_section(gui, frame, bar, enrolment_id: int) -> None:
    kit.section(frame, "Condition of funding (English and maths)")
    try:
        pos = funding.cof_position(enrolment_id)
        gaps = funding.condition_of_funding_gaps(enrolment_id)
    except Exception as exc:  # noqa: BLE001 — shown in place
        logger.exception("CoF for %s not read", enrolment_id)
        kit.note(frame, f"Not read: {describe_error(exc)}", colour="#a33")
        return
    if not pos.applies:
        kit.note(frame, f"Does not apply: {pos.reason}")
    else:
        kit.note(frame, pos.reason)
        for a in pos.areas:
            mark = "✓" if a.met else "✗"
            extra = " (exempt)" if a.exempt else ""
            aim = f"; aim: {a.aim_label}" if a.aim_label else ""
            kit.note(frame, f"{mark} {a.area}: best grade {a.best_grade or '—'}; "
                     f"needs {a.requirement}; {a.status}{extra}{aim}",
                     colour="#2e7d32" if a.met else "#a33")
    if gaps:
        kit.table(frame, GAP_COLS, [(g.area, g.best_grade, g.requirement, g.suggested_type,
                                     ", ".join(g.allowed_types), g.status) for g in gaps],
                  height=min(3, len(gaps)), expand=False)
    kit.button(bar, "Apply Condition of Funding…",
               lambda: apply_cof(gui, enrolment_id, gaps),
               enabled=bool(gaps) and kit.can_write())


def apply_cof(gui, enrolment_id: int, gaps, *, types: dict[str, str] | None = None) -> None:
    """Ask the qualification type per gap (default: the suggestion), then
    add the aims and report what was created and any problems."""
    if types is None:
        initial = {g.area: g.suggested_type for g in gaps}
        fields = [(g.area, f"{g.area} — add (grade {g.best_grade or 'none'})", "readonly",
                   list(g.allowed_types)) for g in gaps]
        chosen = kit.ask_form(gui.root, "Apply condition of funding", fields, initial)
        if not chosen:
            return
        types = {k: v for k, v in chosen.items() if v}
    res = kit.attempt(gui, "Condition of funding", lambda: funding.apply_condition_of_funding(
        enrolment_id, qualification_types=types))
    if res is None:
        return
    lines = ([f"Added: {getattr(a, 'label', a)}" for a in res.created]
             or ["No aims were added."])
    kit.show_lines(gui, "Condition of funding", lines, res.problems)
    open_funding_and_fees(gui, enrolment_id)


def _fee_section(gui, frame, bar, enrolment_id: int) -> None:
    kit.section(frame, "Fees")
    try:
        due = funding.fee_due(enrolment_id)
        charges = funding.list_charges(enrolment_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fees for %s not read", enrolment_id)
        kit.note(frame, f"Not read: {describe_error(exc)}", colour="#a33")
        return
    rule = (f"#{due.rule.rule_id} {_money(due.rule.annual_fee)} "
            f"({due.age_band}, {due.residency_category})" if due.rule
            else "no rule applies" if due.fee_paying else "—")
    kit.fields_grid(frame, [
        ("Fee status", due.fee_status), ("Fee paying", "Yes" if due.fee_paying else "No"),
        ("Fee rule", rule), ("Gross fee", _money(due.gross_fee)),
        ("Remission", _money(due.remission_amount)), ("Net fee", _money(due.net_fee)),
        ("Already raised", _money(due.already_raised)), ("To raise", _money(due.to_raise)),
    ])
    for line in due.explanation:
        kit.note(frame, f"• {line}")
    for p in due.problems:
        kit.note(frame, f"⚠ {p}", colour="#a33")
    tree = kit.table(frame, CHARGE_COLS, [
        (c.invoice_id, c.invoice_number, c.academic_year, c.fee_status or "",
         _money(c.gross_fee), _money(c.remission_amount), _money(c.net_fee),
         " by ".join(x for x in (c.issued_on, c.issued_by) if x),
         "Live" if c.status == "Issued" else f"Cancelled: {c.cancelled_reason or ''}")
        for c in charges],
        iids=[str(c.invoice_id) for c in charges], height=4)
    if not charges:
        kit.note(frame, "No charges raised.", colour="#777")

    def raise_it() -> None:
        day = simpledialog.askstring(
            "Raise fee", f"Raise {_money(due.to_raise)} as a tuition invoice.\n\n"
            "Due date (YYYY-MM-DD, blank = in one month):", parent=gui.root)
        if day is None:
            return
        c = kit.attempt(gui, "Raise fee", lambda: funding.raise_fee(
            enrolment_id, due_date=day.strip() or None))
        if c is not None:
            kit.show_lines(gui, "Fee raised", [
                f"Invoice {c.invoice_number}: {_money(c.net_fee)} ({c.fee_status})."])
            open_funding_and_fees(gui, enrolment_id)

    def cancel_it() -> None:
        iid = kit.selected(tree, "Cancel charge", "a charge")
        if not iid:
            return
        number = next((c.invoice_number for c in charges if str(c.invoice_id) == iid), iid)
        reason = simpledialog.askstring("Cancel charge",
                                        f"Cancel invoice {number}?\n\nReason:", parent=gui.root)
        if not reason:
            return
        c = kit.attempt(gui, "Cancel charge", lambda: funding.cancel_fee_charge(
            int(iid), reason=reason))
        if c is not None:
            kit.show_lines(gui, "Charge cancelled", [
                f"Invoice {c.invoice_number} ({_money(c.net_fee)}) cancelled; its finance "
                "item is now Cancelled."])
            open_funding_and_fees(gui, enrolment_id)

    ok = can_raise()
    kit.button(bar, "Raise Fee…", raise_it, enabled=ok and due.to_raise > 0 and not due.problems)
    kit.button(bar, "Cancel Charge…", cancel_it,
               enabled=ok and any(c.status == "Issued" for c in charges))


# ── Year report ─────────────────────────────────────────────────────

COF_COLS = [("eid", "#", 50), ("sid", "Student", 90), ("name", "Name", 170),
            ("yg", "YG", 40), ("tutor", "Tutor", 70), ("status", "Status", 80),
            ("applies", "Applies", 60), ("english", "English", 220),
            ("maths", "Maths", 220), ("gaps", "Gaps", 110)]


def open_cof_report(gui, academic_year: str | None = None, *, only_gaps: bool = True,
                    live_only: bool = True) -> None:
    year = academic_year or _default_academic_year()
    frame, bar = kit.page(gui, "Condition of Funding Report")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    gaps_var = tk.BooleanVar(value=only_gaps)
    live_var = tk.BooleanVar(value=live_only)
    year_var = kit.year_picker(top, year)

    def reload(*_a) -> None:
        open_cof_report(gui, year_var.get(), only_gaps=gaps_var.get(),
                        live_only=live_var.get())

    ttk.Checkbutton(top, text="Only learners with gaps", variable=gaps_var,
                    command=reload).pack(side="left", padx=4)
    ttk.Checkbutton(top, text="Live enrolments only", variable=live_var,
                    command=reload).pack(side="left", padx=4)
    ttk.Button(top, text="Apply", command=reload).pack(side="left", padx=4)
    try:
        rows = funding.cof_report(year, only_gaps=only_gaps, live_only=live_only)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Condition of funding", exc)
        rows = []
    flat = [r.csv_row() for r in rows]
    tree = kit.table(frame, COF_COLS, [
        (f["enrolment_id"], f["student_id"], f["student_name"], f["year_group"],
         f["tutor_group"], f["status"], f["applies"], f["english"], f["maths"], f["gaps"])
        for f in flat], iids=[str(r.enrolment_id) for r in rows])
    kit.note(frame, f"{len(rows)} enrolment(s); "
             f"{sum(1 for r in rows if r.gaps)} with a gap.")

    def open_sel() -> None:
        iid = kit.selected(tree, "Condition of funding", "an enrolment")
        if iid:
            open_funding_and_fees(gui, int(iid))

    tree.bind("<Double-1>", lambda _e: tree.selection() and open_sel())
    kit.button(bar, "Open Funding & Fees", open_sel)
    kit.csv_button(bar, gui, lambda: rows, f"condition_of_funding_{year.replace('/', '-')}.csv")
    gui.status_var.set(f"Condition of funding {year}: {len(rows)} row(s)")


# ── Fee rates (finance / funding) ───────────────────────────────────

def open_fee_rates(gui, academic_year: str | None = None) -> None:
    """Fee rates are finance's fee rules: open Finance's Fees window on
    its Fee Rules tab (finance or funding staff only). *academic_year* is
    accepted for the caller's year picker; the rules list shows every
    year."""
    if not can_fees():
        messagebox.showinfo("Fee Rates", "Fee rules are kept by finance or funding staff "
                            "— you need the finance or funding permission.",
                            parent=gui.root)
        return
    from education_system.systems.sixth_form.domains.finance.interfaces.gui.fees import (
        fees_views,
    )
    try:
        fees_views.open_fees_window(gui, tab=fees_views.FEE_RULES_TAB)
    except Exception as exc:  # noqa: BLE001 — window failed to build
        logger.exception("Fee rules window not opened")
        show_error(gui.root, "Fee Rates", exc)
        return
    gui.status_var.set("Fee rules opened in Finance > Fees")
