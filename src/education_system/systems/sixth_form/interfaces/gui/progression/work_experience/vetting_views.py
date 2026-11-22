"""GUI tabs for employer vetting, placement visits and T Level sign-off.

Added to the Work Experience window after Placements / Employers /
Summary:

* **Vetting**        — every employer's insurance, risk assessment and
  safeguarding contact, with what is missing; record each from here.
* **Insurance**      — certificates on file, expired/expiring first.
* **Risk assessments** — the assessments, with hazards and review dates.
* **Visits**         — placement visits and checks.
* **Confirm & T Level** — confirm a placement (the H&S gate), link it to
  a T Level aim, check and sign off the 315-hour industry placement.
"""

from __future__ import annotations

import datetime as _dt
import logging
from tkinter import ttk

from education_system.systems.sixth_form.domain.progression.work_experience import (
    vetting as data,
    work_experience as we_data,
)
from education_system.systems.sixth_form.interfaces.gui.progression import _record_tabs as rt

logger = logging.getLogger(__name__)


def _placement_choices() -> list[str]:
    return [f"{r.placement.placement_id} — {r.student_name} @ {r.employer_name} "
            f"({r.placement.start_date})"
            for r in we_data.list_placements_with_detail()]


def _id_of(label: str) -> int | None:
    label = (label or "").strip()
    return int(label.split(" — ")[0]) if label else None


_INSURANCE_FIELDS = (
    ("insurer", "Insurer", "text"), ("policy_number", "Policy number", "text"),
    ("cover_amount", "Cover (e.g. £5m)", "text"), ("start_date", "Start", "date"),
    ("expiry_date", "Expiry", "date"), ("seen_by", "Certificate seen by", "text"),
    ("seen_on", "Seen on", "date"), ("notes", "Notes", "multiline"),
)
_RA_FIELDS = (
    ("placement", "Placement (blank = whole employer)", "choice", _placement_choices),
    ("assessed_on", "Assessed on", "date"), ("reviewer", "Reviewer", "text"),
    ("hazards", "Hazards identified", "multiline"), ("controls", "Controls", "multiline"),
    ("risk_level", "Risk level", "choice", data.RISK_LEVELS),
    ("outcome", "Outcome", "choice", data.RA_OUTCOMES),
    ("next_review_due", "Next review due", "date"), ("notes", "Notes", "multiline"),
)
_VISIT_FIELDS = (
    ("placement", "Placement", "choice", _placement_choices),
    ("visit_date", "Date", "date"), ("visit_type", "Type", "choice", data.VISIT_TYPES),
    ("visited_by", "Visited by", "text"), ("student_seen", "Student seen", "bool"),
    ("concerns", "Concerns", "multiline"), ("actions", "Actions", "multiline"),
)


def add_tabs(nb: ttk.Notebook) -> None:
    rt.notebook_tab(nb, "Vetting", _vetting)
    rt.notebook_tab(nb, "Insurance", _insurance)
    rt.notebook_tab(nb, "Risk assessments", _risk)
    rt.notebook_tab(nb, "Visits", _visits)
    rt.notebook_tab(nb, "Confirm & T Level", _confirm)


def _add_insurance(table, employer_id):
    rt.form_dialog(table.parent, "Record liability insurance", _INSURANCE_FIELDS, {},
                   lambda v: data.add_insurance(employer_id, v), table.refresh)


def _add_ra(table, employer_id):
    def save(v):
        v["placement_id"] = _id_of(v.pop("placement"))
        data.add_risk_assessment(employer_id, v)
    rt.form_dialog(table.parent, "Record risk assessment", _RA_FIELDS,
                   {"assessed_on": _dt.date.today().isoformat(), "risk_level": "Low",
                    "outcome": "Approved"}, save, table.refresh)


def _vetting(parent: ttk.Frame) -> None:
    def contact(table):
        row = table.require()
        current = data.get_safeguarding_contact(row["employer_id"])
        rt.form_dialog(table.parent, f"Safeguarding contact — {row['name']}",
                       (("name", "Name", "text"), ("phone", "Phone", "text"),
                        ("email", "Email", "text")), current,
                       lambda v: data.set_safeguarding_contact(row["employer_id"], **v),
                       table.refresh)

    rt.RecordTable(
        parent,
        (("name", "Employer", 200), ("insurance", "Insured to", 90),
         ("risk_assessment", "Risk assessment", 190), ("safeguarding", "Safeguarding", 140),
         ("state", "State", 520)),
        lambda f: [v.as_row() for v in data.employer_vetting_list()
                   if not f.get("show") or not v.ok],
        key="employer_id",
        filters=[("show", "Show", "choice", ("Not vetted only",))],
        note=("A placement can be confirmed — and can start — only at an employer "
              "with liability insurance in force on its start date; confirmation also "
              "needs a current approved risk assessment and a safeguarding contact."),
        tags=lambda r: "good" if r["state"] == "Vetted" else "bad",
        actions=[("Add insurance…", lambda t: _add_insurance(t, t.require()["employer_id"])),
                 ("Add risk assessment…", lambda t: _add_ra(t, t.require()["employer_id"])),
                 ("Safeguarding contact…", contact)])


def _insurance(parent: ttk.Frame) -> None:
    def load(f):
        if f.get("show") == "Expired / expiring with live placements":
            return [{"insurance_id": r["employer_id"], "employer_name": r["name"],
                     "expiry_date": r["expiry"], "insurer": r["state"],
                     "policy_number": f"{r['live_placements']} live placement(s)"}
                    for r in data.expiring_insurance()]
        return data.list_insurance()

    def delete(table):
        row = table.require()
        if table.filters().get("show"):
            raise ValueError("Switch the filter off to delete a certificate.")
        if rt.confirm(table.parent, "Delete", "Delete this insurance record?"):
            data.delete_insurance(row["insurance_id"])
            table.refresh()

    today = _dt.date.today().isoformat()
    rt.RecordTable(
        parent,
        (("employer_name", "Employer", 200), ("insurer", "Insurer", 160),
         ("policy_number", "Policy", 140), ("cover_amount", "Cover", 80),
         ("start_date", "Start", 90), ("expiry_date", "Expiry", 90),
         ("seen_by", "Seen by", 120), ("seen_on", "Seen on", 90)),
        load, key="insurance_id",
        filters=[("show", "Show", "choice", ("Expired / expiring with live placements",))],
        tags=lambda r: "bad" if (r.get("expiry_date") or "") < today else None,
        actions=[("Delete", delete)])


def _risk(parent: ttk.Frame) -> None:
    def delete(table):
        row = table.require()
        if rt.confirm(table.parent, "Delete", "Delete this risk assessment?"):
            data.delete_risk_assessment(row["ra_id"])
            table.refresh()

    def view(table):
        row = table.require()
        rt.show_text(table.parent, "Risk assessment", "\n".join(
            f"{k.replace('_', ' ').capitalize():<18} {v if v is not None else '—'}"
            for k, v in row.items()))

    today = _dt.date.today().isoformat()
    rt.RecordTable(
        parent,
        (("employer_name", "Employer", 200), ("placement_id", "Placement", 70),
         ("assessed_on", "Assessed", 90), ("reviewer", "Reviewer", 120),
         ("risk_level", "Risk", 70), ("outcome", "Outcome", 160),
         ("next_review_due", "Review due", 90), ("hazards", "Hazards", 320)),
        lambda f: data.list_risk_assessments(), key="ra_id",
        tags=lambda r: "bad" if r["outcome"] == "Not approved" or (
            r["next_review_due"] and r["next_review_due"] < today) else None,
        note="Record new assessments from the Vetting tab (select the employer).",
        actions=[("View", view), ("Delete", delete)], on_open=view)


def _visits(parent: ttk.Frame) -> None:
    def add(table):
        def save(v):
            pid = _id_of(v.pop("placement"))
            if pid is None:
                raise ValueError("Pick the placement visited")
            data.add_visit(pid, v)
        rt.form_dialog(table.parent, "Record placement visit", _VISIT_FIELDS,
                       {"visit_date": _dt.date.today().isoformat(), "student_seen": True,
                        "visit_type": "Monitoring"}, save, table.refresh)

    def delete(table):
        row = table.require()
        if rt.confirm(table.parent, "Delete", "Delete this visit record?"):
            data.delete_visit(row["visit_id"])
            table.refresh()

    rt.RecordTable(
        parent,
        (("visit_date", "Date", 90), ("placement_id", "Placement", 70),
         ("student_id", "Student", 90), ("employer_name", "Employer", 180),
         ("visit_type", "Type", 130), ("visited_by", "By", 120),
         ("student_seen", "Seen", 50), ("concerns", "Concerns", 260),
         ("actions", "Actions", 200)),
        lambda f: data.list_visits(), key="visit_id",
        tags=lambda r: "warn" if r["concerns"] else None,
        actions=[("Record visit…", add), ("Delete", delete)])


def _confirm(parent: ttk.Frame) -> None:
    def load(f):
        rows = []
        extras = data.placement_extras_map()
        for r in we_data.list_placements_with_detail():
            p = r.placement
            ex = extras.get(p.placement_id) or data.placement_extras(p.placement_id)
            if f.get("show") == "T Level only" and not ex["tlevel_aim_ref"]:
                continue
            rows.append({"placement_id": p.placement_id, "student_id": p.student_id,
                         "student_name": r.student_name, "employer": r.employer_name,
                         "employer_id": p.employer_id, "start": p.start_date,
                         "status": p.status, "hours": p.hours_completed,
                         "confirmed": ex["confirmed_on"] or "—",
                         "tlevel": ex["tlevel_aim_ref"] or "—",
                         "tlevel_done": ex["tlevel_completed_on"] or "—"})
        return rows

    def confirm(table):
        row = table.require()
        rt.form_dialog(table.parent, f"Confirm placement #{row['placement_id']}",
                       (("by", "Confirmed by", "text"),), {},
                       lambda v: data.confirm_placement(row["placement_id"],
                                                        confirmed_by=v["by"]),
                       table.refresh,
                       intro="Checks insurance, risk assessment and safeguarding contact.")

    def check(table):
        row = table.require()
        v = data.vetting(row["employer_id"], placement_id=row["placement_id"],
                         on_date=row["start"])
        lines = [f"Placement #{row['placement_id']} — {row['student_name']} @ {row['employer']}",
                 "", "Vetting: " + ("OK" if v.ok else "")]
        lines += [f"  ✗ {p}" for p in v.problems]
        if row["tlevel"] != "—":
            problems = data.tlevel_completion_check(row["placement_id"])
            lines += ["", "T Level completion: " + ("ready to sign off" if not problems else "")]
            lines += [f"  ✗ {p}" for p in problems]
        rt.show_text(table.parent, "Placement checks", "\n".join(lines))

    def link(table):
        row = table.require()
        aims = data.tlevel_aims_for(row["student_id"])
        if not aims:
            raise ValueError("No T Level learning aim is recorded for this student "
                             "(learning aims are kept in Qualifications).")
        labels = [f"{a['aim_ref']} — {a['title']}" for a in aims]
        rt.form_dialog(table.parent, "Link to T Level aim",
                       (("aim", "T Level aim (blank = unlink)", "choice", labels),), {},
                       lambda v: data.link_tlevel_aim(
                           row["placement_id"], v["aim"].split(" — ")[0] if v["aim"] else None),
                       table.refresh)

    def sign_off(table):
        row = table.require()
        rt.form_dialog(table.parent, "Sign off T Level industry placement",
                       (("by", "Signed off by", "text"),), {},
                       lambda v: data.sign_off_tlevel(row["placement_id"],
                                                      signed_off_by=v["by"]),
                       table.refresh,
                       intro=(f"Needs {data.TLEVEL_PLACEMENT_HOURS:g} hours across the "
                              "linked placements, all Completed and confirmed, and a final "
                              "review visit."))

    rt.RecordTable(
        parent,
        (("placement_id", "#", 50), ("student_name", "Student", 160),
         ("employer", "Employer", 180), ("start", "Start", 90), ("status", "Status", 90),
         ("hours", "Hours", 60), ("confirmed", "Confirmed", 90),
         ("tlevel", "T Level aim", 150), ("tlevel_done", "T Level signed off", 120)),
        load, key="placement_id",
        filters=[("show", "Show", "choice", ("T Level only",))],
        tags=lambda r: "good" if r["tlevel_done"] != "—" else (
            "warn" if r["confirmed"] == "—" and r["status"] == "Planned" else None),
        actions=[("Checks", check), ("Confirm…", confirm), ("Link T Level aim…", link),
                 ("Sign off T Level…", sign_off)],
        on_open=check)


__all__ = ["add_tabs"]
