"""Learner agreements and parent/guardian acknowledgements for an
enrolment (record, withdraw, correct, history) and the year's
outstanding list."""

from __future__ import annotations

import datetime as _dt
import logging
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import simpledialog
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    agreements as agr,
)

from . import enrolment_page_kit as kit
from .enrolment_common import _default_academic_year, _student_name_map, describe_error, show_error

logger = logging.getLogger(__name__)

OTHER = "(someone not on file — type the name)"

AGR_COLS = [("id", "#", 50), ("kind", "Kind", 120), ("name", "Signed by", 180),
            ("rel", "Relationship", 110), ("on", "Signed on", 90), ("method", "Method", 70),
            ("status", "Status", 90), ("by", "Recorded by", 110),
            ("ended", "Ended", 300)]
HIST_COLS = [("at", "When", 150), ("id", "Agreement", 80), ("action", "Action", 100),
             ("by", "By", 110), ("detail", "Detail", 540)]


def contact_label(c) -> str:
    flags = []
    if getattr(c, "has_parental_responsibility", False):
        flags.append("PR")
    if getattr(c, "is_primary", False):
        flags.append("primary")
    extra = f" [{', '.join(flags)}]" if flags else ""
    return f"{c.contact_id} — {c.full_name} ({c.relationship or '?'}){extra}"


def open_agreements(gui, enrolment_id: int) -> None:
    from .enrolment_views import open_profile
    frame, bar = kit.page(gui, f"Agreements — Enrolment #{enrolment_id}",
                          back=lambda: open_profile(gui, enrolment_id),
                          back_text="Back to Enrolment")
    try:
        st = agr.state(enrolment_id)
        rows = agr.for_enrolment(enrolment_id)
        hist = agr.history(enrolment_id)
    except Exception as exc:  # noqa: BLE001
        kit.note(frame, f"Not read: {describe_error(exc)}", colour="#a33")
        return
    if st.complete:
        kit.note(frame, "✓ Complete.", colour="#2e7d32")
    for m in st.missing:
        kit.note(frame, f"✗ {m}", colour="#a33")
    kit.note(frame, "A parent/guardian acknowledgement is needed: "
             + ("yes (under 18 at the start)" if st.parent_needed else "no"))
    tree = kit.table(frame, AGR_COLS, [
        (a.agreement_id, a.kind, a.signed_name, a.relationship, a.signed_on, a.method,
         a.status, a.recorded_by,
         " — ".join(x for x in (a.ended_at, a.ended_by, a.ended_reason) if x))
        for a in rows], iids=[str(a.agreement_id) for a in rows], height=6, expand=False)
    kit.section(frame, "History")
    kit.table(frame, HIST_COLS, [(h.get("changed_at"), h.get("agreement_id"),
                                  h.get("action"), h.get("changed_by"), h.get("detail"))
                                 for h in hist], height=8)
    w = kit.can_write()
    by_id = {str(a.agreement_id): a for a in rows}

    def pick_current() -> object | None:
        iid = kit.selected(tree, "Agreements", "a signature")
        a = by_id.get(iid or "")
        if a is not None and a.status != agr.CURRENT:
            show_error(gui.root, "Agreements", ValueError(f"#{a.agreement_id} is {a.status}"))
            return None
        return a

    def withdraw() -> None:
        a = pick_current()
        if a is None:
            return
        reason = simpledialog.askstring("Withdraw signature", f"Withdraw {a.kind} "
                                        f"#{a.agreement_id} ({a.signed_name})?\n\nReason:",
                                        parent=gui.root)
        if reason and kit.attempt(gui, "Withdraw", lambda: agr.withdraw(
                a.agreement_id, reason=reason)) is not None:
            open_agreements(gui, enrolment_id)

    kit.button(bar, "Record Learner Agreement…",
               lambda: ask_record(gui, enrolment_id, agr.LEARNER),
               enabled=w and st.learner is None)
    kit.button(bar, "Record Parent Acknowledgement…",
               lambda: ask_record(gui, enrolment_id, agr.PARENT),
               enabled=w and st.parent is None)
    kit.button(bar, "Withdraw…", withdraw, enabled=w and bool(rows))
    kit.button(bar, "Correct…", lambda: (lambda a: a and ask_correct(gui, enrolment_id, a))(
        pick_current()), enabled=w and bool(rows))
    gui.status_var.set(f"Agreements for #{enrolment_id}")


def _parent_fields(student_id: str) -> tuple[list, list]:
    try:
        contacts = agr.parent_contacts(student_id)
    except Exception:  # noqa: BLE001 — a name can still be typed
        logger.exception("Parent contacts for %s not read", student_id)
        contacts = []
    labels = [contact_label(c) for c in contacts] + [OTHER]
    return [("contact", "Parent / guardian", "readonly", labels),
            ("signed_name", "Name as signed (if not on file)", "entry", None),
            ("relationship", "Relationship (if not on file)", "entry", None)], contacts


def record_values(kind: str, v: dict) -> dict:
    """Form values → keyword arguments for ``agreements.record``."""
    out = {"method": v.get("method") or "", "signed_on": kit.blank_none(v.get("signed_on")),
           "signed_name": kit.blank_none(v.get("signed_name")),
           "notes": kit.blank_none(v.get("notes"))}
    if kind == agr.PARENT:
        contact = v.get("contact") or ""
        if contact and contact != OTHER:
            out["contact_id"] = int(kit.code_of(contact))
        out["relationship"] = kit.blank_none(v.get("relationship"))
    return out


def ask_record(gui, enrolment_id: int, kind: str) -> None:
    from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments
    e = enrolments.get_enrolment(enrolment_id)
    if e is None:
        return
    fields = [("method", "Method", "readonly", list(agr.METHODS)),
              ("signed_on", "Signed on (YYYY-MM-DD)", "entry", None)]
    initial = {"method": agr.METHODS[0], "signed_on": _dt.date.today().isoformat()}
    if kind == agr.PARENT:
        extra, contacts = _parent_fields(e.student_id)
        fields += extra
        initial["contact"] = contact_label(contacts[0]) if contacts else OTHER
    else:
        fields.append(("signed_name", "Name as signed (blank = learner's name)", "entry", None))
    fields.append(("notes", "Notes", "text", None))
    if kit.ask_form(gui.root, f"Record {kind.lower()} signature — #{enrolment_id}",
                    fields, initial, on_submit=lambda v: agr.record(
                        enrolment_id, kind, **record_values(kind, v))):
        open_agreements(gui, enrolment_id)


def ask_correct(gui, enrolment_id: int, a) -> None:
    fields = [("reason", "Reason for the correction", "entry", None),
              ("method", "Method", "readonly", list(agr.METHODS)),
              ("signed_on", "Signed on (YYYY-MM-DD)", "entry", None),
              ("signed_name", "Name as signed", "entry", None)]
    if a.kind == agr.PARENT:
        fields.append(("relationship", "Relationship", "entry", None))
    initial = {"method": a.method, "signed_on": a.signed_on, "signed_name": a.signed_name,
               "relationship": a.relationship}

    def save(v: dict) -> None:
        if not (v.get("reason") or "").strip():
            raise ValueError("Give the reason for the correction")
        agr.correct(a.agreement_id, reason=v["reason"], method=v.get("method") or None,
                    signed_on=kit.blank_none(v.get("signed_on")),
                    signed_name=kit.blank_none(v.get("signed_name")),
                    relationship=kit.blank_none(v.get("relationship")))

    if kit.ask_form(gui.root, f"Correct #{a.agreement_id}", fields, initial, on_submit=save):
        open_agreements(gui, enrolment_id)


OUT_COLS = [("eid", "#", 50), ("sid", "Student", 90), ("name", "Name", 200),
            ("yg", "YG", 40), ("missing", "Missing", 520)]


def open_agreements_outstanding(gui, academic_year: str | None = None) -> None:
    year = academic_year or _default_academic_year()
    frame, bar = kit.page(gui, "Agreements Outstanding")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    kit.year_picker(top, year, on_change=lambda y: open_agreements_outstanding(gui, y))
    try:
        rows = agr.outstanding(year)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Agreements", exc)
        rows = []
    names = _student_name_map()
    tree = kit.table(frame, OUT_COLS, [(r.enrolment_id, r.student_id,
                                        names.get(r.student_id, ""), r.year_group,
                                        "; ".join(r.missing)) for r in rows],
                     iids=[str(r.enrolment_id) for r in rows])
    kit.note(frame, f"{len(rows)} live enrolment(s) still missing a signature.")

    def open_sel() -> None:
        iid = kit.selected(tree, "Agreements", "an enrolment")
        if iid:
            open_agreements(gui, int(iid))

    tree.bind("<Double-1>", lambda _e: tree.selection() and open_sel())
    kit.button(bar, "Open Agreements", open_sel)
    kit.csv_button(bar, gui, lambda: rows, f"agreements_outstanding_{year.replace('/', '-')}.csv")
    gui.status_var.set(f"Agreements outstanding {year}: {len(rows)}")
