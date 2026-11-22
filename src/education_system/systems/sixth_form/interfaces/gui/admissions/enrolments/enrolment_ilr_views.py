"""ILR screens: one enrolment's ILR record (recorded vs derived values,
aims with completion status and outcome), the year's ILR export with
its problems, and the early-leavers report."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import ilr

from . import enrolment_page_kit as kit
from .enrolment_common import (
    _default_academic_year,
    _student_name_map,
    describe_error,
    show_error,
)

logger = logging.getLogger(__name__)

AIM_COLS = [("label", "Aim", 220), ("start", "Start", 90), ("planned", "Planned end", 90),
            ("actual", "Actual end", 90), ("comp", "Completion", 90),
            ("wreason", "Withdraw reason", 110), ("outcome", "Outcome", 200),
            ("grade", "Grade", 60), ("ach", "Achieved on", 90), ("hours", "Hours", 60),
            ("counted", "Funded hours", 85), ("qual", "Qualifying", 80)]


def _yes(flag: bool) -> str:
    return "Yes" if flag else "No"


def _src(value, source: str) -> str:
    shown = "—" if value in (None, "") else str(value)
    return f"{shown}  ({source})" if source and source != "none" else shown


def _fund_label(code) -> str:
    return f"{code} — {ilr.FUND_MODELS.get(code, '?')}" if code else ""


def _outcome_label(a) -> str:
    if a.outcome is None:
        return "—"
    return f"{a.outcome} {ilr.OUTCOMES.get(a.outcome, '')} ({a.outcome_source})"


# ── One enrolment ───────────────────────────────────────────────────

def open_ilr_record(gui, enrolment_id: int) -> None:
    from .enrolment_views import open_profile
    back = lambda: open_profile(gui, enrolment_id)  # noqa: E731
    frame, bar = kit.page(gui, f"ILR — Enrolment #{enrolment_id}", back=back,
                          back_text="Back to Enrolment")
    try:
        rec = ilr.get_ilr(enrolment_id)
    except Exception as exc:  # noqa: BLE001 — shown in place
        logger.exception("ILR for %s not read", enrolment_id)
        kit.note(frame, f"ILR record not read: {describe_error(exc)}", colour="#a33")
        return
    names = _student_name_map()
    kit.note(frame, f"{rec.student_id} — {names.get(rec.student_id, '')} · "
             f"{rec.academic_year} · {rec.status} · started {rec.start_date}. "
             "Values marked (recorded) were entered here; (derived) ones are "
             "worked out from the learner's record.")
    days_note = (f"{rec.days_in_learning} day(s); qualifying period "
                 f"{'met' if rec.qualifying_met else 'not met'}")
    kit.fields_grid(frame, [
        ("Fee status", _src(rec.fee_status, rec.fee_status_source)),
        ("Funding model", _fund_label(rec.fund_model)),
        ("FFI", rec.ffi),
        ("Mode", _src(rec.mode, rec.mode_source)),
        ("Planned learning hours", _src(rec.plan_learn_hours, rec.plan_learn_hours_source)),
        ("Planned EEP hours", _src(rec.plan_eep_hours, rec.plan_eep_hours_source)),
        ("Total hours", rec.total_hours),
        ("Funding band", rec.funding_band),
        ("Funded", _yes(rec.funded)),
        ("Fee paying", _yes(rec.fee_paying)),
        ("High needs", _yes(rec.high_needs)),
        ("Age on 31 August", rec.age_on_31_august),
        ("Days in learning", days_note),
        ("Early leaver", _yes(rec.early_leaver)),
        ("Destination", rec.destination_label),
        ("Destination start", rec.destination_start),
        ("Destination collected", rec.destination_collected),
        ("Notes", rec.notes),
        ("Last updated", " by ".join(x for x in (rec.updated_at, rec.updated_by) if x)),
    ])
    write = kit.can_write()
    kit.button(bar, "Edit ILR…", lambda: edit_ilr(gui, enrolment_id), enabled=write)

    kit.section(frame, "Learning aims")
    tree = kit.table(frame, AIM_COLS, [
        (a.label, a.start_date, a.planned_end_date, a.actual_end_date,
         ilr.COMP_STATUS_LABELS.get(a.comp_status, a.comp_status), a.withdraw_reason,
         _outcome_label(a), a.grade, a.achievement_date, a.planned_hours,
         _yes(a.counted), "Met" if a.qualifying_met else
         ("Early" if a.withdrawn_before_qualifying else "Not yet"))
        for a in rec.aims], iids=[str(a.aim_id) for a in rec.aims], height=6)
    if not rec.aims:
        kit.note(frame, "No learning aims in this enrolment's year.", colour="#777")

    def aim_id() -> int | None:
        iid = kit.selected(tree, "Aim outcome", "an aim")
        return int(iid) if iid else None

    def set_outcome() -> None:
        aid = aim_id()
        if aid is not None:
            ask_aim_outcome(gui, enrolment_id, aid)

    def clear_outcome() -> None:
        aid = aim_id()
        if aid is None or not messagebox.askyesno(
                "Clear outcome", "Clear the recorded outcome? The derived one "
                "applies again.", parent=gui.root):
            return
        if kit.attempt(gui, "Clear outcome", lambda: ilr.clear_aim_outcome(aid)) is not None:
            open_ilr_record(gui, enrolment_id)

    kit.button(bar, "Set Outcome…", set_outcome, enabled=write)
    kit.button(bar, "Clear Outcome", clear_outcome, enabled=write)
    gui.status_var.set(f"ILR for enrolment #{enrolment_id}")


def ilr_form_fields(rec) -> tuple[list, dict]:
    """ask_form fields and initial values: only *recorded* values are
    filled in, so leaving a field blank keeps it derived."""
    def rec_val(name: str):
        if getattr(rec, f"{name}_source", "recorded") == "recorded":
            return getattr(rec, name)
        return None

    initial = {
        "fee_status": rec_val("fee_status") or "",
        "fund_model": "",
        "mode": rec_val("mode") or "",
        "plan_learn_hours": rec_val("plan_learn_hours"),
        "plan_eep_hours": rec_val("plan_eep_hours"),
        "destination_type": rec.destination_type or "",
        "destination_code": rec.destination_code,
        "destination_start": rec.destination_start,
        "destination_collected": rec.destination_collected,
        "notes": rec.notes,
    }
    if rec.fee_status_source == "recorded" and rec.fund_model:
        initial["fund_model"] = _fund_label(rec.fund_model)
    dest_codes = "; ".join(f"{t}: " + ", ".join(f"{c} {lbl}" for c, lbl in codes.items())
                           for t, codes in ilr.DESTINATIONS.items() if t == rec.destination_type)
    fields = [
        ("fee_status", f"Fee status (blank = derived: {rec.fee_status or '—'})", "readonly",
         ["", *ilr.FEE_STATUSES]),
        ("fund_model", "Funding model (blank = follows fee status)", "readonly",
         ["", *(_fund_label(k) for k in ilr.FUND_MODELS)]),
        ("mode", f"Mode (blank = derived: {rec.mode or '—'})", "readonly", ["", *ilr.MODES]),
        ("plan_learn_hours", "Planned learning hours (blank = derived)", "entry", None),
        ("plan_eep_hours", "Planned EEP hours (blank = derived)", "entry", None),
        ("destination_type", "Destination type", "readonly", ["", *ilr.DESTINATIONS]),
        ("destination_code", "Destination code" + (f" ({dest_codes})" if dest_codes else ""),
         "entry", None),
        ("destination_start", "Destination start (YYYY-MM-DD)", "entry", None),
        ("destination_collected", "Destination collected (YYYY-MM-DD)", "entry", None),
        ("notes", "Notes", "text", None),
    ]
    return fields, initial


def ilr_payload(values: dict) -> dict:
    out = {k: kit.blank_none(v) for k, v in values.items() if k in ilr.ILR_FIELDS}
    if out.get("fund_model"):
        out["fund_model"] = kit.code_of(out["fund_model"])
    elif out.get("fee_status"):
        out.pop("fund_model", None)       # follows the fee status
    if not out.get("destination_type"):
        out.pop("destination_code", None)
    return out


def edit_ilr(gui, enrolment_id: int) -> None:
    try:
        rec = ilr.get_ilr(enrolment_id)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "ILR", exc)
        return
    fields, initial = ilr_form_fields(rec)
    if kit.ask_form(gui.root, f"ILR — enrolment #{enrolment_id}", fields, initial,
                    on_submit=lambda v: ilr.set_ilr(enrolment_id, ilr_payload(v))):
        gui.status_var.set(f"ILR saved for #{enrolment_id}")
        open_ilr_record(gui, enrolment_id)


def ask_aim_outcome(gui, enrolment_id: int, aim_id: int) -> None:
    cur = None
    try:
        cur = ilr.get_aim_outcome(aim_id)
    except Exception:  # noqa: BLE001 — the form still opens
        logger.exception("Outcome for aim %s not read", aim_id)
    initial = {}
    if cur is not None:
        initial = {"outcome": f"{cur.outcome} — {ilr.OUTCOMES.get(cur.outcome, '')}",
                   "achievement_date": cur.achievement_date, "grade": cur.grade,
                   "notes": cur.notes}

    def save(v: dict) -> None:
        if not v.get("outcome"):
            raise ValueError("Choose the outcome")
        ilr.set_aim_outcome(aim_id, int(kit.code_of(v["outcome"])),
                            achievement_date=kit.blank_none(v.get("achievement_date")),
                            grade=kit.blank_none(v.get("grade")),
                            notes=kit.blank_none(v.get("notes")))

    if kit.ask_form(gui.root, f"Outcome — aim #{aim_id}", [
            ("outcome", "Outcome (withdrawn aims: 2 or 3)", "readonly",
             [f"{k} — {v}" for k, v in ilr.OUTCOMES.items()]),
            ("achievement_date", "Achievement date (YYYY-MM-DD)", "entry", None),
            ("grade", "Grade", "entry", None),
            ("notes", "Notes", "text", None)], initial, on_submit=save):
        open_ilr_record(gui, enrolment_id)


# ── Export ──────────────────────────────────────────────────────────

PROBLEM_COLS = [("sid", "Student", 90), ("eid", "Enrolment", 70), ("aim", "Aim", 60),
                ("sev", "Severity", 70), ("field", "Field", 140), ("message", "Problem", 640)]


def open_ilr_export(gui, academic_year: str | None = None) -> None:
    year = academic_year or _default_academic_year()
    frame, bar = kit.page(gui, "ILR Export")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    year_var = kit.year_picker(top, year, on_change=lambda y: open_ilr_export(gui, y))
    allowed = kit.can("funding", "admissions", "students.manage")
    kit.note(frame, "Learner and LearningDelivery rows for every learner in the "
             "year — the same file as Finance & Bursaries → Census ILR → ILR "
             "Export, built from these enrolments' ILR details and aim outcomes "
             "(Pending and archived enrolments are left out). Problems are "
             "listed below — fix them before sending the return.")
    if not allowed:
        kit.note(frame, "Exporting the ILR needs the funding, admissions or "
                 "students.manage permission.", colour="#a33")
        return
    try:
        res = ilr.export_csv(year_var.get())
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "ILR export", exc)
        return
    kit.note(frame, f"{res.learners} learner(s), {res.deliveries} learning "
             f"deliver(ies), {len(res.problems)} problem(s).",
             colour="#a33" if res.problems else "#2e7d32")
    kit.table(frame, PROBLEM_COLS, [(p.student_id, p.enrolment_id, p.aim_id, p.severity,
                                     p.field, p.message) for p in res.problems], height=14)

    def save_as() -> None:
        path = filedialog.asksaveasfilename(
            parent=gui.root, defaultextension=".csv",
            initialfile=f"ilr_{year_var.get().replace('/', '-')}.csv",
            filetypes=[("CSV files", "*.csv")], title="Save ILR export")
        if not path:
            return
        out = kit.attempt(gui, "ILR export", lambda: ilr.export_csv(year_var.get(), path=path))
        if out is not None:
            kit.show_lines(gui, "ILR export saved", [
                f"Saved to: {out.path or path}",
                f"{out.learners} learner(s), {out.deliveries} deliver(ies)."],
                [f"{p.student_id} #{p.enrolment_id} {p.field}: {p.message}"
                 for p in out.problems[:20]]
                + ([f"…and {len(out.problems) - 20} more"] if len(out.problems) > 20 else []))
            gui.status_var.set(f"ILR saved to {out.path or path}")

    kit.button(bar, "Save As…", save_as)
    kit.csv_button(bar, gui, lambda: res.problems, "ilr_problems.csv", "Export Problems")
    gui.status_var.set(f"ILR export {year_var.get()}: {len(res.problems)} problem(s)")


# ── Early leavers ───────────────────────────────────────────────────

LEAVER_COLS = [("eid", "#", 50), ("sid", "Student", 90), ("name", "Name", 180),
               ("yg", "YG", 40), ("tutor", "Tutor", 70), ("start", "Start", 90),
               ("wd", "Withdrawn", 90), ("reason", "Reason", 60), ("days", "Days", 50),
               ("aims", "Aims before qualifying", 360)]


def open_early_leavers(gui, academic_year: str | None = None) -> None:
    year = academic_year or _default_academic_year()
    frame, bar = kit.page(gui, "Early Leavers")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    kit.year_picker(top, year, on_change=lambda y: open_early_leavers(gui, y))
    kit.note(frame, f"Withdrawn inside the {ilr.QUALIFYING_DAYS}-day qualifying "
             "period: not counted as starts and not funded.")
    try:
        rows = ilr.early_leavers(year)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Early leavers", exc)
        rows = []
    tree = kit.table(frame, LEAVER_COLS, [
        (r.enrolment_id, r.student_id, r.student_name, r.year_group, r.tutor_group,
         r.start_date, r.withdrawal_date, r.withdrawal_reason, r.days_in_learning,
         "; ".join(r.aims_before_qualifying)) for r in rows],
        iids=[str(r.enrolment_id) for r in rows])
    if not rows:
        kit.note(frame, "No early leavers this year.", colour="#777")

    def open_sel() -> None:
        iid = kit.selected(tree, "Early leavers", "a learner")
        if iid:
            open_ilr_record(gui, int(iid))

    tree.bind("<Double-1>", lambda _e: tree.selection() and open_sel())
    kit.button(bar, "Open ILR", open_sel)
    kit.csv_button(bar, gui, lambda: rows, f"early_leavers_{year.replace('/', '-')}.csv")
    gui.status_var.set(f"Early leavers {year}: {len(rows)}")
