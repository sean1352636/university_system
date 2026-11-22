"""CLI flows for Gatsby coverage, evidence and the employer directory.

Listed in the Careers Guidance menu after its original entries.
"""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.progression.careers import (
    careers as careers_data,
    gatsby as data,
)
from education_system.systems.sixth_form.domain.progression.work_experience import (
    work_experience as we_data,
)
from education_system.systems.sixth_form.interfaces.cli.progression import _record_menus as rm

logger = logging.getLogger(__name__)


def _period() -> tuple[str | None, str | None]:
    if rm.ask_yes("This academic year only?", default=True):
        return data.current_academic_year()
    return (rm.ask("From (YYYY-MM-DD, blank = start)") or None,
            rm.ask("To (YYYY-MM-DD, blank = today)") or None)


def _pick_employer(allow_blank: bool = True) -> int | None:
    emps = we_data.list_employers()
    if not emps:
        print("  No employers in the directory yet.")
        return None
    label = rm.choose("Employer", [f"{e.employer_id} — {e.name}" for e in emps],
                      allow_blank=allow_blank)
    return int(label.split(" — ")[0]) if label else None


def cohort_report() -> None:
    cohort = rm.choose("Cohort", data.COHORTS, default="All active")
    lo, hi = _period()
    print()
    print(data.cohort_coverage(cohort, date_from=lo, date_to=hi).text())
    rm.pause()


def student_detail() -> None:
    sid = rm.pick_student()
    lo, hi = _period()
    cov = data.student_coverage(sid, date_from=lo, date_to=hi)
    print(f"\n  {cov.student_name} — {len(cov.met)}/8 benchmarks met")
    for b, c in cov.benchmarks.items():
        print(f"\n  BM{b} {careers_data.GATSBY_BENCHMARKS[b]} — "
              f"{'MET' if c.met else 'not met'} ({c.count}/{c.needed})")
        for item in c.items:
            print(f"     • {item}")
        for item in c.not_counted:
            print(f"     ✗ {item}")
    rm.pause()


def add_evidence() -> None:
    sid = rm.pick_student()
    kind = rm.choose("Kind", data.EVIDENCE_KINDS)
    bm = rm.ask_int("Benchmark 1-8", default=data.KIND_BENCHMARK.get(kind))
    values = {
        "student_id": sid, "kind": kind, "benchmark": bm,
        "evidence_date": rm.ask("Date (YYYY-MM-DD)", required=True),
        "description": rm.ask("Description", required=True),
        "employer_id": _pick_employer() if kind in ("Employer encounter",
                                                    "Workplace experience") else None,
        "provider": rm.ask("FE/HE provider") if kind == "FE/HE encounter" else None,
        "adviser_level6": rm.ask_yes("Delivered by a level 6 adviser?",
                                     default=kind == "Personal guidance"),
    }
    e = data.add_evidence(values)
    print(f"  ✓ Evidence #{e['evidence_id']} recorded against BM{e['benchmark']}.")
    rm.pause()


def list_evidence() -> None:
    sid = rm.ask("Student id (blank = all)")
    rm.print_table(data.list_evidence(student_id=sid or None),
                   (("evidence_id", "#", 4), ("evidence_date", "Date", 10),
                    ("student_name", "Student", 20), ("benchmark", "BM", 3),
                    ("kind", "Kind", 20), ("description", "Description", 36),
                    ("employer_name", "Employer", 18)))
    if rm.ask_yes("Delete one?"):
        eid = rm.ask_int("Evidence #")
        if eid and data.delete_evidence(eid):
            print("  ✓ Deleted.")
    rm.pause()


def link_session() -> None:
    sid = rm.pick_student()
    sessions = careers_data.list_sessions(student_id=sid)
    links = data.session_links_map(sid)
    rows = [{"session_id": s.session_id, "date": s.session_date, "type": s.session_type,
             "bm": s.gatsby_benchmark or "", "employer": links.get(s.session_id, {}).get(
                 "employer_name") or "", "l6": bool(links.get(s.session_id, {}).get(
                     "adviser_level6"))} for s in sessions]
    rm.print_table(rows, (("session_id", "#", 5), ("date", "Date", 10), ("type", "Type", 20),
                          ("bm", "BM", 3), ("employer", "Employer", 24), ("l6", "L6", 3)))
    row = rm.pick_row(rows, "session_id", "Session #")
    if row is None:
        return
    current = data.get_session_links(row["session_id"])
    data.set_session_links(
        row["session_id"], employer_id=_pick_employer(),
        provider=rm.ask("FE/HE provider", default=current["provider"] or ""),
        adviser_level6=rm.ask_yes("Delivered by a level 6 adviser?",
                                  default=bool(current["adviser_level6"])),
        evidence=rm.ask("Evidence (where it is kept)", default=current["evidence"] or ""))
    print("  ✓ Linked.")
    rm.pause()


def employer_directory() -> None:
    rows = data.employer_directory()
    rm.print_table(rows, (("employer_id", "#", 4), ("name", "Employer", 28),
                          ("sector", "Sector", 16), ("sessions", "Sess", 4),
                          ("evidence", "Evid", 4), ("placements", "Plac", 4)))
    if rows and rm.ask_yes("Show one employer's encounters?"):
        row = rm.pick_row(rows, "employer_id", "Employer #")
        if row:
            rm.print_table(data.encounters_for_employer(row["employer_id"]),
                           (("date", "Date", 10), ("student_id", "Student", 10),
                            ("what", "What", 22), ("detail", "Detail", 40)))
    rm.pause()


MENU = (
    ("Gatsby Coverage — Cohort Report", cohort_report),
    ("Gatsby Coverage — One Learner", student_detail),
    ("Add Gatsby Evidence", add_evidence),
    ("List / Delete Gatsby Evidence", list_evidence),
    ("Link Session to Employer / Provider", link_session),
    ("Employer Directory", employer_directory),
)

__all__ = ["MENU"] + [fn.__name__ for _l, fn in MENU]
