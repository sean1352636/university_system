"""Behaviour Log tabs: automatic escalation, learner agreement, and
dress code / ID badge breaches.

* Escalations — stages reached automatically from behaviour points;
  action / close them, open the linked disciplinary case number.
* Escalation Thresholds — points within rolling N days -> stage.
* Learner Agreement — versioned text; acceptances per student;
  outstanding (students / parents yet to accept the current version).
* Dress Code / ID Badges — each breach logs negative "Uniform" points.
"""

from __future__ import annotations

from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col
from education_system.systems.sixth_form.domain.pastoral.behaviour import behaviour as data
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form, show_record, spec_columns,
)

_RED = {"open": ("#fff0d6", "#7a5800"), "current": ("#e3f5e1", "#205c20")}


def add_behaviour_extra_tabs(nb: ttk.Notebook) -> None:
    data.init_db()
    EscalationsTab(nb)
    ThresholdsTab(nb)
    AgreementVersionsTab(nb)
    AcceptancesTab(nb)
    OutstandingTab(nb)
    BreachesTab(nb)


# ── Escalations ──────────────────────────────────────────────────

def _action(tab: RecordTab, e: Any) -> None:
    ask_form(tab.frame, f"Action escalation #{e.escalation_id} ({e.stage})",
             (Col("outcome", "What was done / agreed", "multiline",
                  required=True),
              Col("close", "Close the escalation", "bool")),
             initial={"outcome": e.outcome},
             on_save=lambda v: data.action_escalation(
                 e.escalation_id, outcome=v["outcome"], close=v["close"]))


def _check_all(tab: RecordTab, _row: Any) -> None:
    made = data.run_escalation_check()
    messagebox.showinfo("Escalations",
                        f"{len(made)} new escalation(s) created.",
                        parent=tab.frame)


class EscalationsTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(
            nb, "Escalations", data.ESCALATION_SPEC,
            load=lambda f: data.list_escalations(
                student_id=f.get("student_id") or None,
                status=f.get("status") or None,
                stage=f.get("stage") or None),
            update=data.update_escalation,
            delete=data.delete_escalation,
            columns=[*spec_columns(data.ESCALATION_SPEC, names=None)[:2],
                     ("Name", lambda e: self.names.get(e.student_id, "?"),
                      160),
                     *spec_columns(data.ESCALATION_SPEC, names=None)[2:],
                     ("Threshold", lambda e: e.threshold, 70),
                     ("Trigger entry", lambda e: e.trigger_entry_id, 90)],
            filters=(Col("student_id", "Student", "student"),
                     Col("stage", "Stage", "choice",
                         choices=data.ESCALATION_STAGES),
                     Col("status", "Status", "choice",
                         choices=data.ESCALATION_STATUSES)),
            actions=(("Action / Close", _action, True),
                     ("Check All Students Now", _check_all, False)),
            row_tag=lambda e: "open" if e.status == "Open" else None,
            tag_colours=_RED,
            intro=("Created automatically when a student's negative points "
                   "within a rolling window reach a threshold. Stages set "
                   "to refer also open a disciplinary case (column "
                   "'Disciplinary case #')."))


def _suggested(tab: RecordTab, _row: Any) -> None:
    if messagebox.askyesno(
            "Escalation thresholds",
            "Add the suggested thresholds for any stage without one?",
            parent=tab.frame):
        data.install_suggested_rules()


class ThresholdsTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(
            nb, "Escalation Thresholds", data.RULE_SPEC,
            load=lambda _f: data.list_rules(),
            create=data.create_rule, update=data.update_rule,
            delete=data.delete_rule,
            actions=(("Add Suggested Thresholds", _suggested, False),),
            intro=("Negative behaviour points (as a positive total) within "
                   "the rolling window that move a student to each stage. "
                   "Later stages need at least as many points as earlier "
                   "ones."))


# ── Learner agreement ────────────────────────────────────────────

def _make_current(tab: RecordTab, v: Any) -> None:
    data.set_current_agreement_version(v.version_id)


def _read(tab: RecordTab, v: Any) -> None:
    show_record(tab.frame, f"{v.title} — {v.version_label}", v,
                data.VERSION_SPEC)


class AgreementVersionsTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(
            nb, "Learner Agreement", data.VERSION_SPEC,
            load=lambda _f: data.list_agreement_versions(),
            create=data.create_agreement_version,
            update=data.update_agreement_version,
            delete=data.delete_agreement_version,
            actions=(("Make Current", _make_current, True),
                     ("Read Text", _read, True)),
            row_tag=lambda v: "current" if v.is_current else None,
            tag_colours=_RED,
            intro=("Once anyone has accepted a version its text is frozen — "
                   "add a new version for changes and make it current."))


def _accept_defaults(tab: RecordTab) -> dict[str, Any] | None:
    cur = data.current_agreement_version()
    if cur is None:
        messagebox.showinfo("Learner agreement",
                            "Add a learner agreement version first.",
                            parent=tab.frame)
        return None
    return {"version_id": cur.version_id}


class AcceptancesTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(
            nb, "Agreement Acceptances", data.SIGNATURE_SPEC,
            load=lambda f: data.list_agreement_acceptances(
                version_id=int(f["version_id"]) if f.get("version_id")
                else None,
                student_id=f.get("student_id") or None),
            create=data.record_agreement_acceptance,
            update=data.update_agreement_acceptance,
            delete=data.delete_agreement_acceptance,
            filters=(Col("student_id", "Student", "student"),
                     Col("version_id", "Version #", "int")),
            new_defaults=_accept_defaults,
            intro=("Recording again for the same student and version adds "
                   "to the existing acceptance (e.g. the parent signing "
                   "later)."))


def _record_for(tab: RecordTab, o: Any) -> None:
    cur = data.current_agreement_version()
    if cur is None:
        return
    ask_form(tab.frame, f"Record acceptance — {o.student_id}",
             [c for c in data.SIGNATURE_SPEC.cols],
             initial={"version_id": cur.version_id,
                      "student_id": o.student_id},
             on_save=data.record_agreement_acceptance)


class OutstandingTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(
            nb, "Agreements Outstanding", None,
            load=lambda _f: data.outstanding_agreements(),
            columns=(("Student", lambda o: o.student_id, 90),
                     ("Name", lambda o: o.student_name, 200),
                     ("Student accepted", lambda o: o.student_signed, 120),
                     ("Parent needed", lambda o: o.parent_needed, 110),
                     ("Parent accepted", lambda o: o.parent_signed, 120)),
            actions=(("Record Acceptance", _record_for, True),),
            row_id=lambda o: o.student_id,
            intro=("Current version only. Parent acceptance is not "
                   "required once a student is 18."))


# ── Dress code / ID badges ───────────────────────────────────────

def _points(tab: RecordTab, _row: Any) -> None:
    current = data.breach_points()
    cols = [Col(t, t, "int") for t in data.BREACH_TYPES]

    def save(v: dict[str, Any]) -> dict[str, int]:
        out = current
        for t in data.BREACH_TYPES:
            if str(v.get(t, "")).strip() not in ("", str(current[t])):
                out = data.set_breach_points(t, int(v[t]))
        return out
    ask_form(tab.frame, "Behaviour points per breach", cols,
             initial={t: current[t] for t in data.BREACH_TYPES},
             on_save=save,
             intro="Points are always negative (entering 3 means -3).")


class BreachesTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(
            nb, "Dress Code / ID Badges", data.BREACH_SPEC,
            load=lambda f: data.list_breaches(
                student_id=f.get("student_id") or None,
                breach_type=f.get("breach_type") or None,
                date_from=f.get("date_from") or None,
                date_to=f.get("date_to") or None),
            create=data.record_breach, update=data.update_breach,
            delete=data.delete_breach,
            columns=[*spec_columns(data.BREACH_SPEC, names=None)[:2],
                     ("Name", lambda b: self.names.get(b.student_id, "?"),
                      160),
                     *spec_columns(data.BREACH_SPEC, names=None)[2:],
                     ("Behaviour entry", lambda b: b.behaviour_entry_id, 100)],
            filters=(Col("student_id", "Student", "student"),
                     Col("breach_type", "Breach", "choice",
                         choices=data.BREACH_TYPES),
                     Col("date_from", "From"), Col("date_to", "To")),
            actions=(("Points per Breach…", _points, False),),
            intro=("Each breach adds a negative 'Uniform' behaviour entry "
                   "(and so counts towards escalation). Deleting a breach "
                   "removes its behaviour entry too."))
