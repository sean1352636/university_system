"""Onboarding reports: dashboards, the outstanding-tasks list, exports.

* :func:`dashboard` — open and finished checklists grouped by tutor
  group, course (subject of the learner's learning aims; a learner counts
  once per subject) or year group: learners, checklists, completed, %
  of tasks done, overdue tasks and blocked tasks.
* :func:`outstanding_tasks` — every task still to do on open checklists,
  with who owns it and whether it is overdue / blocked.
* :func:`to_csv` / :func:`export_csv` and :func:`export_pdf` (reportlab,
  as the other sixth form exports use).

Reads only. Sensitive tasks are masked exactly as on the checklist
screens (:func:`onboarding.list_items`).
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)

logger = logging.getLogger(__name__)

GROUP_BY: tuple[str, ...] = ("tutor_group", "course", "year_group")
UNASSIGNED = "(none)"


@dataclass
class DashboardRow:
    group: str
    learners: int = 0
    checklists: int = 0
    completed: int = 0
    tasks: int = 0
    tasks_done: int = 0
    overdue: int = 0
    blocked: int = 0
    _students: set = field(default_factory=set, repr=False)

    @property
    def percent_complete(self) -> float:
        return round(100.0 * self.tasks_done / self.tasks, 1) \
            if self.tasks else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {"group": self.group, "learners": self.learners,
                "checklists": self.checklists, "completed": self.completed,
                "tasks": self.tasks, "tasks_done": self.tasks_done,
                "percent_complete": self.percent_complete,
                "overdue": self.overdue, "blocked": self.blocked}


@dataclass
class OutstandingTask:
    student_id: str
    student_name: str
    checklist_id: int
    checklist: str
    academic_year: str | None
    tutor_group: str | None
    year_group: int | None
    item_id: int
    task: str
    category: str
    required: bool
    status: str
    due_date: str | None
    overdue: bool
    blocked_reason: str | None
    owner_role: str | None
    assigned_to: str | None
    sensitive: bool = False


def _enrolment_map(year: str | None) -> dict[str, Any]:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enr,
    )
    out: dict[str, Any] = {}
    for e in _enr.list_enrolments(academic_year=year):
        cur = out.get(e.student_id)
        if cur is None or (e.is_live and not cur.is_live):
            out[e.student_id] = e
    return out


def _courses(e: Any) -> list[str]:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enr,
    )
    try:
        return sorted({a.subject for a in _enr.aims_for_enrolment(e)
                       if a.subject}) or [UNASSIGNED]
    except Exception:  # noqa: BLE001
        logger.debug("aims not read for %s", e.student_id, exc_info=True)
        return [UNASSIGNED]


def _checklists(academic_year: str | None, open_only: bool) -> list[Any]:
    return ob.list_checklists(academic_year=academic_year,
                              open_only=open_only)


def dashboard(group_by: str = "tutor_group", *,
              academic_year: str | None = None,
              open_only: bool = False) -> list[DashboardRow]:
    """Checklist progress per tutor group / course / year group for one
    academic year (default the current one). Cancelled checklists are
    left out."""
    if group_by not in GROUP_BY:
        raise ob.ValidationError(f"Group by one of: {', '.join(GROUP_BY)}")
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enr,
    )
    year = academic_year or _enr.current_academic_year()
    emap = _enrolment_map(year)
    today = _dt.date.today().isoformat()
    rows: dict[str, DashboardRow] = {}
    for c in _checklists(year, open_only):
        if c.status == "Cancelled":
            continue
        e = emap.get(c.student_id)
        if group_by == "tutor_group":
            groups = [(e.tutor_group if e and e.tutor_group else UNASSIGNED)]
        elif group_by == "year_group":
            groups = [f"Year {e.year_group}" if e else UNASSIGNED]
        else:
            groups = _courses(e) if e else [UNASSIGNED]
        items = ob.list_items(checklist_id=c.checklist_id)
        done = sum(1 for i in items if i.is_done)
        overdue = sum(1 for i in items if not i.is_done and i.due_date
                      and i.due_date < today)
        if not overdue and c.is_open and c.due_date and c.due_date < today:
            overdue = 1        # the checklist itself is past its due date
        blocked = sum(1 for i in items if i.status == "Blocked")
        for g in groups:
            r = rows.setdefault(g, DashboardRow(g))
            r._students.add(c.student_id)
            r.checklists += 1
            r.completed += c.status == "Completed"
            r.tasks += len(items)
            r.tasks_done += done
            r.overdue += overdue
            r.blocked += blocked
    for r in rows.values():
        r.learners = len(r._students)
    return sorted(rows.values(), key=lambda r: (r.group == UNASSIGNED,
                                                r.group))


def outstanding_tasks(*, academic_year: str | None = None,
                      overdue_only: bool = False,
                      blocked_only: bool = False,
                      required_only: bool = False,
                      category: str | None = None,
                      owner_role: str | None = None,
                      tutor_group: str | None = None,
                      student_id: str | None = None) -> list[OutstandingTask]:
    """Tasks not yet done on open checklists, overdue first."""
    year = academic_year
    emap = _enrolment_map(year)
    today = _dt.date.today().isoformat()
    out: list[OutstandingTask] = []
    for row in ob.list_checklists_with_detail(academic_year=year,
                                              open_only=True,
                                              student_id=student_id):
        c = row.checklist
        e = emap.get(c.student_id)
        tg = e.tutor_group if e else None
        if tutor_group and tg != tutor_group:
            continue
        for i in ob.list_items(checklist_id=c.checklist_id):
            if i.is_done:
                continue
            late = bool(i.due_date and i.due_date < today) or bool(
                not i.due_date and c.due_date and c.due_date < today)
            if overdue_only and not late:
                continue
            if blocked_only and i.status != "Blocked":
                continue
            if required_only and not i.required:
                continue
            if category and i.category != category:
                continue
            if owner_role and (i.owner_role or "") != owner_role:
                continue
            out.append(OutstandingTask(
                c.student_id, row.student_name, c.checklist_id, c.name,
                c.academic_year, tg, e.year_group if e else None,
                i.item_id, i.task_name, i.category, i.required, i.status,
                i.due_date or c.due_date, late, i.blocked_reason,
                i.owner_role, i.assigned_to or c.assigned_to, i.sensitive))
    return sorted(out, key=lambda t: (not t.overdue, t.due_date or "9999",
                                      t.student_name, t.item_id))


# ── Exports ─────────────────────────────────────────────────────────

def _dicts(rows: list[Any]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        if isinstance(r, DashboardRow):
            out.append(r.as_dict())
        elif isinstance(r, dict):
            out.append(r)
        else:
            out.append(asdict(r))
    return out


def to_csv(rows: list[Any]) -> str:
    data = _dicts(rows)
    if not data:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(data[0]))
    w.writeheader()
    for d in data:
        w.writerow({k: ("" if v is None else v) for k, v in d.items()})
    return buf.getvalue()


def _report_rows(kind: str, **kw: Any) -> tuple[str, list[Any]]:
    if kind == "outstanding":
        return "Onboarding — outstanding tasks", outstanding_tasks(**kw)
    if kind in GROUP_BY:
        label = kind.replace("_", " ")
        return f"Onboarding by {label}", dashboard(kind, **kw)
    raise ob.ValidationError("Report must be 'outstanding' or one of: "
                             + ", ".join(GROUP_BY))


def export_csv(kind: str, path: str | None = None, **kw: Any) -> str:
    """CSV text of a report (``outstanding`` or a :data:`GROUP_BY`
    dashboard); also written to *path* when given."""
    _title, rows = _report_rows(kind, **kw)
    text = to_csv(rows)
    if path:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            fh.write(text)
    return text


def export_pdf(kind: str, path: str, **kw: Any) -> str:
    """Write a report as a simple PDF (needs reportlab). Returns *path*."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas as _canvas
    except ImportError:
        raise ob.ValidationError("PDF export needs reportlab "
                                 "(pip install reportlab)") from None
    title, rows = _report_rows(kind, **kw)
    data = _dicts(rows)
    if kind == "outstanding":
        cols = ("student_name", "student_id", "tutor_group", "task",
                "status", "due_date", "overdue", "assigned_to")
    else:
        cols = ("group", "learners", "checklists", "completed",
                "percent_complete", "overdue", "blocked")
    size = landscape(A4)
    c = _canvas.Canvas(path, pagesize=size)
    width, height = size
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, title)
    c.setFont("Helvetica", 8)
    c.drawString(width - 200, y, f"Printed {_dt.date.today().isoformat()}")
    y -= 24
    col_w = (width - 80) / len(cols)

    def line(values, bold=False):
        nonlocal y
        if y < 40:
            c.showPage()
            y = height - 40
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 8)
        for n, v in enumerate(values):
            c.drawString(40 + n * col_w, y, str("" if v is None else v)
                         [: int(col_w / 4.2)])
        y -= 13

    line([k.replace("_", " ").title() for k in cols], bold=True)
    for d in data:
        line([d.get(k) for k in cols])
    if not data:
        line(["Nothing to report"])
    c.save()
    return path
