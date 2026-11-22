"""GUI tabs for Gatsby coverage, evidence and the employer directory.

Added to the Careers Guidance window beside its original four tabs:

* **Gatsby coverage** — per-student benchmarks met for a cohort and
  period, the cohort report, and one learner's evidence in detail.
* **Evidence**        — manual evidence rows (add / delete).
* **Session links**   — link careers sessions to an employer or FE/HE
  provider and flag level 6 guidance.
* **Employers**       — the shared employer directory with encounter
  counts; add/edit goes through the work-experience employer records.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.sixth_form.domain.progression.careers import (
    careers as careers_data,
    gatsby as data,
)
from education_system.systems.sixth_form.domain.progression.work_experience import (
    work_experience as we_data,
)
from education_system.systems.sixth_form.interfaces.gui.progression import _record_tabs as rt

logger = logging.getLogger(__name__)


def _employer_choices() -> list[str]:
    return [f"{e.employer_id} — {e.name}" for e in we_data.list_employers()]


def _employer_id(label: str) -> int | None:
    label = (label or "").strip()
    return int(label.split(" — ")[0]) if label else None


def _period(f: dict[str, str]) -> tuple[str | None, str | None]:
    if f.get("period") == "This academic year":
        return data.current_academic_year()
    return (f.get("from") or None, f.get("to") or None)


_PERIOD_FILTERS = [
    ("period", "Period", "choice", ("This academic year",), "This academic year"),
    ("from", "or from", "text"), ("to", "to", "text"),
]


def build_coverage_tab(gui, parent: ttk.Frame) -> None:
    def load(f):
        lo, hi = _period(f)
        report = data.cohort_coverage(f.get("cohort") or "All active", date_from=lo, date_to=hi)
        return [s.as_row() for s in report.students]

    def detail(table):
        row = table.require()
        lo, hi = _period(table.filters())
        cov = data.student_coverage(row["student_id"], date_from=lo, date_to=hi)
        lines = [f"{cov.student_name} ({cov.student_id}) — {len(cov.met)}/8 benchmarks met", ""]
        for b, c in cov.benchmarks.items():
            lines.append(f"BM{b} {careers_data.GATSBY_BENCHMARKS[b]} — "
                         f"{'MET' if c.met else 'not met'} ({c.count}/{c.needed})")
            lines += [f"    • {i}" for i in c.items]
            lines += [f"    ✗ {i}" for i in c.not_counted]
        rt.show_text(table.parent, "Gatsby evidence", "\n".join(lines))

    def report(table):
        f = table.filters()
        lo, hi = _period(f)
        rt.show_text(table.parent, "Gatsby cohort coverage",
                     data.cohort_coverage(f.get("cohort") or "All active",
                                          date_from=lo, date_to=hi).text())

    cols = [("student_name", "Student", 180), ("student_id", "ID", 80), ("met", "Met", 50)]
    cols += [(f"bm{b}", f"BM{b}", 50) for b in range(1, 9)]
    rt.RecordTable(
        parent, cols, load, key="student_id",
        filters=[("cohort", "Cohort", "choice", data.COHORTS, "All active")] + _PERIOD_FILTERS,
        note=("Built from completed careers sessions, work placements, university "
              "visits attended and manual evidence. ✓ = met; n/m = evidence so far. "
              "BM8 counts only guidance from a level 6 qualified adviser."),
        tags=lambda r: "good" if r["met"] == "8/8" else None,
        actions=[("Evidence for learner", detail), ("Cohort report", report)],
        on_open=detail)


_EVIDENCE_FIELDS = (
    ("student", "Student", "choice", rt.student_choices),
    ("kind", "Kind", "choice", data.EVIDENCE_KINDS),
    ("benchmark", "Benchmark (blank = from kind)", "choice",
     lambda: [f"{k} — {v}" for k, v in careers_data.GATSBY_BENCHMARKS.items()]),
    ("evidence_date", "Date", "date"),
    ("description", "Description", "multiline"),
    ("employer", "Employer", "choice", _employer_choices),
    ("provider", "FE/HE provider", "text"),
    ("adviser_level6", "Delivered by a level 6 adviser", "bool"),
)


def build_evidence_tab(gui, parent: ttk.Frame) -> None:
    def load(f):
        bm = f.get("benchmark") or ""
        return data.list_evidence(student_id=f.get("student") or None,
                                  benchmark=int(bm.split()[0]) if bm else None)

    def add(table):
        def save(v):
            v["student_id"] = rt.student_id_of(v.pop("student"))
            v["employer_id"] = _employer_id(v.pop("employer"))
            v["benchmark"] = (v.get("benchmark") or "").split(" — ")[0] or None
            data.add_evidence(v)
        rt.form_dialog(table.parent, "Add Gatsby evidence", _EVIDENCE_FIELDS, {}, save,
                       table.refresh)

    def delete(table):
        row = table.require()
        if rt.confirm(table.parent, "Delete", "Delete this evidence row?"):
            data.delete_evidence(row["evidence_id"])
            table.refresh()

    rt.RecordTable(
        parent,
        (("evidence_date", "Date", 90), ("student_name", "Student", 160),
         ("benchmark", "BM", 40), ("kind", "Kind", 160), ("description", "Description", 300),
         ("employer_name", "Employer", 160), ("provider", "Provider", 140),
         ("adviser_level6", "L6", 40)),
        load, key="evidence_id",
        filters=[("student", "Student id", "text"),
                 ("benchmark", "Benchmark", "choice", [str(b) for b in range(1, 9)])],
        actions=[("Add…", add), ("Delete", delete)])


def build_session_links_tab(gui, parent: ttk.Frame) -> None:
    def load(f):
        rows = []
        links_by_id = data.session_links_map(f.get("student") or None)
        for s in careers_data.list_sessions(student_id=f.get("student") or None):
            links = links_by_id.get(s.session_id, {})
            rows.append({"session_id": s.session_id, "date": s.session_date,
                         "student_id": s.student_id, "type": s.session_type,
                         "benchmark": s.gatsby_benchmark or "", "status": s.status,
                         "employer": links.get("employer_name") or "",
                         "provider": links.get("provider") or "",
                         "level6": bool(links.get("adviser_level6")),
                         "evidence": links.get("evidence") or ""})
        return rows

    def link(table):
        row = table.require()
        links = data.get_session_links(row["session_id"])
        emp = we_data.get_employer(links["employer_id"]) if links["employer_id"] else None
        rt.form_dialog(
            table.parent, f"Session #{row['session_id']} links",
            (("employer", "Employer", "choice", _employer_choices),
             ("provider", "FE/HE provider", "text"),
             ("adviser_level6", "Delivered by a level 6 adviser", "bool"),
             ("evidence", "Evidence (where it is kept)", "multiline")),
            {"employer": f"{emp.employer_id} — {emp.name}" if emp else "",
             "provider": links["provider"], "adviser_level6": links["adviser_level6"],
             "evidence": links["evidence"]},
            lambda v: data.set_session_links(
                row["session_id"], employer_id=_employer_id(v["employer"]),
                provider=v["provider"], adviser_level6=v["adviser_level6"],
                evidence=v["evidence"]),
            table.refresh)

    rt.RecordTable(
        parent,
        (("date", "Date", 90), ("student_id", "Student", 80), ("type", "Type", 140),
         ("benchmark", "BM", 40), ("status", "Status", 90), ("employer", "Employer", 170),
         ("provider", "Provider", 150), ("level6", "L6", 40), ("evidence", "Evidence", 200)),
        load, key="session_id", filters=[("student", "Student id", "text")],
        note="Link employer encounters to the employer directory and mark level 6 guidance.",
        actions=[("Link…", link)], on_open=link)


_EMPLOYER_FIELDS = (
    ("name", "Name", "text"), ("sector", "Sector", "choice", we_data.SECTORS),
    ("contact_name", "Contact", "text"), ("contact_email", "Email", "text"),
    ("contact_phone", "Phone", "text"), ("address", "Address", "multiline"),
    ("notes", "Notes", "multiline"),
)


def build_employers_tab(gui, parent: ttk.Frame) -> None:
    def add(table):
        rt.form_dialog(table.parent, "New employer", _EMPLOYER_FIELDS, {"sector": "Other"},
                       we_data.create_employer, table.refresh)

    def edit(table):
        row = table.require()
        rt.form_dialog(table.parent, row["name"], _EMPLOYER_FIELDS, row,
                       lambda v: we_data.update_employer(row["employer_id"], v),
                       table.refresh)

    def encounters(table):
        row = table.require()
        rows = data.encounters_for_employer(row["employer_id"])
        lines = [f"{row['name']} — {len(rows)} encounter(s)", ""]
        lines += [f"{r['date'] or '':<10} {r['student_id']:<10} {r['what']:<22} {r['detail']}"
                  for r in rows]
        rt.show_text(table.parent, "Employer encounters", "\n".join(lines))

    rt.RecordTable(
        parent,
        (("name", "Employer", 220), ("sector", "Sector", 140), ("contact_name", "Contact", 140),
         ("sessions", "Sessions", 70), ("evidence", "Evidence", 70),
         ("placements", "Placements", 80)),
        lambda f: data.employer_directory(name_like=f.get("name") or None),
        key="employer_id", filters=[("name", "Name", "text")],
        note=("One directory shared with Work Experience: employers giving talks, "
              "mock interviews or placements."),
        actions=[("New…", add), ("Edit…", edit), ("Encounters", encounters)],
        on_open=encounters)


__all__ = ["build_coverage_tab", "build_evidence_tab", "build_session_links_tab",
           "build_employers_tab"]
