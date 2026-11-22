"""CLI flows for employer vetting, placement visits and T Level sign-off.

Listed in the Work Experience menu after its original entries.
"""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.sixth_form.domain.progression.work_experience import (
    vetting as data,
    work_experience as we_data,
)
from education_system.systems.sixth_form.interfaces.cli.progression import _record_menus as rm

logger = logging.getLogger(__name__)


def _pick_employer() -> int | None:
    emps = we_data.list_employers()
    if not emps:
        print("  No employers yet.")
        return None
    label = rm.choose("Employer", [f"{e.employer_id} — {e.name}" for e in emps])
    return int(label.split(" — ")[0])


def _pick_placement() -> int | None:
    rows = [{"placement_id": r.placement.placement_id, "student": r.student_name,
             "employer": r.employer_name, "start": r.placement.start_date,
             "status": r.placement.status}
            for r in we_data.list_placements_with_detail()]
    rm.print_table(rows, (("placement_id", "#", 5), ("student", "Student", 22),
                          ("employer", "Employer", 24), ("start", "Start", 10),
                          ("status", "Status", 12)))
    row = rm.pick_row(rows, "placement_id", "Placement #")
    return row["placement_id"] if row else None


def vetting_list() -> None:
    rm.print_table([v.as_row() for v in data.employer_vetting_list()],
                   (("employer_id", "#", 4), ("name", "Employer", 24),
                    ("insurance", "Insured to", 10), ("safeguarding", "Safeguarding", 16),
                    ("state", "State", 60)))
    rm.pause()


def add_insurance() -> None:
    emp = _pick_employer()
    if emp is None:
        return
    values = rm.form((("insurer", "Insurer", "text"), ("policy_number", "Policy number", "text"),
                      ("cover_amount", "Cover", "text"), ("start_date", "Start", "date"),
                      ("expiry_date", "Expiry", "date"), ("seen_by", "Certificate seen by", "text"),
                      ("seen_on", "Seen on", "date"), ("notes", "Notes", "text")))
    data.add_insurance(emp, values)
    print("  ✓ Insurance recorded.")
    rm.pause()


def expiring() -> None:
    rm.print_table(data.expiring_insurance(),
                   (("name", "Employer", 26), ("expiry", "Expiry", 14),
                    ("live_placements", "Live", 4), ("state", "State", 20)))
    rm.pause()


def add_risk_assessment() -> None:
    emp = _pick_employer()
    if emp is None:
        return
    pid = None
    if rm.ask_yes("For one specific placement?"):
        pid = _pick_placement()
    values = rm.form((("assessed_on", "Assessed on", "date"), ("reviewer", "Reviewer", "text"),
                      ("hazards", "Hazards identified", "text"), ("controls", "Controls", "text"),
                      ("risk_level", "Risk level", "choice", data.RISK_LEVELS),
                      ("outcome", "Outcome", "choice", data.RA_OUTCOMES),
                      ("next_review_due", "Next review due", "date"),
                      ("notes", "Notes", "text")),
                     {"assessed_on": _dt.date.today().isoformat()})
    data.add_risk_assessment(emp, {**values, "placement_id": pid})
    print("  ✓ Risk assessment recorded.")
    rm.pause()


def list_risk_assessments() -> None:
    rm.print_table(data.list_risk_assessments(),
                   (("ra_id", "#", 4), ("employer_name", "Employer", 22),
                    ("placement_id", "Pl.", 4), ("assessed_on", "Assessed", 10),
                    ("reviewer", "Reviewer", 14), ("risk_level", "Risk", 6),
                    ("outcome", "Outcome", 22), ("next_review_due", "Review", 10)))
    rm.pause()


def safeguarding_contact() -> None:
    emp = _pick_employer()
    if emp is None:
        return
    current = data.get_safeguarding_contact(emp)
    values = rm.form((("name", "Name", "text"), ("phone", "Phone", "text"),
                      ("email", "Email", "text")), current)
    data.set_safeguarding_contact(emp, **values)
    print("  ✓ Saved.")
    rm.pause()


def record_visit() -> None:
    pid = _pick_placement()
    if pid is None:
        return
    values = rm.form((("visit_date", "Date", "date"),
                      ("visit_type", "Type", "choice", data.VISIT_TYPES),
                      ("visited_by", "Visited by", "text"), ("student_seen", "Student seen", "bool"),
                      ("concerns", "Concerns", "text"), ("actions", "Actions", "text")),
                     {"visit_date": _dt.date.today().isoformat(), "student_seen": True})
    data.add_visit(pid, values)
    print("  ✓ Visit recorded.")
    rm.pause()


def list_visits() -> None:
    rm.print_table(data.list_visits(),
                   (("visit_date", "Date", 10), ("placement_id", "Pl.", 4),
                    ("employer_name", "Employer", 22), ("visit_type", "Type", 18),
                    ("visited_by", "By", 14), ("concerns", "Concerns", 30)))
    rm.pause()


def confirm() -> None:
    pid = _pick_placement()
    if pid is None:
        return
    data.confirm_placement(pid, confirmed_by=rm.ask("Confirmed by", required=True))
    print("  ✓ Placement confirmed.")
    rm.pause()


def link_tlevel() -> None:
    pid = _pick_placement()
    if pid is None:
        return
    p = we_data.get_placement(pid)
    aims = data.tlevel_aims_for(p.student_id)
    if not aims:
        print("  No T Level learning aim is recorded for this student.")
        rm.pause()
        return
    label = rm.choose("T Level aim", [f"{a['aim_ref']} — {a['title']}" for a in aims],
                      allow_blank=True)
    data.link_tlevel_aim(pid, label.split(" — ")[0] if label else None)
    print("  ✓ Saved.")
    rm.pause()


def tlevel_status() -> None:
    rows = data.tlevel_overview()
    rm.print_table(rows, (("placement_id", "#", 4), ("student_name", "Student", 20),
                          ("employer", "Employer", 20), ("status", "Status", 11),
                          ("aim_hours", "Hours", 9), ("completed_on", "Signed off", 10)))
    if rows and rm.ask_yes("Check / sign off one?"):
        row = rm.pick_row(rows, "placement_id", "Placement #")
        if row:
            problems = data.tlevel_completion_check(row["placement_id"])
            for problem in problems:
                print(f"  ✗ {problem}")
            if not problems and rm.ask_yes("Ready — sign off now?"):
                data.sign_off_tlevel(row["placement_id"],
                                     signed_off_by=rm.ask("Signed off by", required=True))
                print("  ✓ Signed off.")
    rm.pause()


MENU = (
    ("Employer vetting status", vetting_list),
    ("Record employer's liability insurance", add_insurance),
    ("Insurance expired / expiring", expiring),
    ("Record risk assessment", add_risk_assessment),
    ("List risk assessments", list_risk_assessments),
    ("Employer safeguarding contact", safeguarding_contact),
    ("Record placement visit", record_visit),
    ("List placement visits", list_visits),
    ("Confirm placement (H&S gate)", confirm),
    ("Link placement to T Level aim", link_tlevel),
    ("T Level placements — hours and sign-off", tlevel_status),
)

__all__ = ["MENU"]
