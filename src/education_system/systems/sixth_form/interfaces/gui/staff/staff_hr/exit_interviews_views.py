"""Tkinter window for staff exit interviews (HR)."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.sixth_form.domain.staff.staff_hr import (
    exit_interviews as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    make_window,
)
from education_system.systems.sixth_form.interfaces.gui.progression import (
    _record_tabs as rt,
)

logger = logging.getLogger(__name__)


def _key(label: str) -> str:
    return (label or "").split(" — ")[0].strip()


def _staff_choices(*, everyone: bool = True) -> list[str]:
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    rows = _staff.list_staff() if everyone else _staff.list_staff(
        active_only=True)
    return [f"{s.staff_id} — {s.full_name} ({s.employment_status})"
            for s in rows]


def _rating_key(area: str) -> str:
    return "rate_" + "".join(ch if ch.isalnum() else "_" for ch in area)


_FIELDS = (
    ("leaving_date", "Leaving date", "date"),
    ("status", "Status", "choice", data.STATUSES),
    ("primary_reason", "Main reason for leaving", "choice",
     ("",) + data.REASONS),
    ("other_reasons", "Other reasons (comma-separated)", "text"),
    ("destination", "Going to", "choice", ("",) + data.DESTINATIONS),
    ("destination_detail", "Destination detail", "text"),
    ("would_recommend", "Would recommend us as an employer", "choice",
     ("",) + data.ANSWERS),
    ("would_return", "Would consider returning", "choice",
     ("",) + data.ANSWERS),
    ("interviewer", "Interviewer", "choice", _staff_choices),
    ("interview_date", "Interview date", "date"),
    ("method", "Method", "choice", ("",) + data.METHODS),
    ("notes", "Notes", "multiline"),
)

#: Second dialog, so neither form is taller than a small screen.
_FEEDBACK_FIELDS = tuple(
    (_rating_key(a), f"{a} (1-5)", "choice", ("", "1", "2", "3", "4", "5"))
    for a in data.FEEDBACK_AREAS) + (
    ("went_well", "What we did well", "multiline"),
    ("could_improve", "What we should change", "multiline"),
)


def _to_payload(v: dict) -> dict:
    out = {k: val for k, val in v.items() if not k.startswith("rate_")
           and k not in ("interviewer", "staff")}
    if any(k.startswith("rate_") for k in v):
        out["ratings"] = {a: v.get(_rating_key(a))
                          for a in data.FEEDBACK_AREAS
                          if v.get(_rating_key(a))}
    if "interviewer" in v:
        out["interviewer_id"] = _key(v["interviewer"]) or None
    return out


def _initial(iv: data.ExitInterview) -> dict:
    out = dict(vars(iv))
    out["other_reasons"] = ", ".join(iv.other_reasons)
    for a in data.FEEDBACK_AREAS:
        out[_rating_key(a)] = str(iv.ratings.get(a, ""))
    out["interviewer"] = next((c for c in _staff_choices()
                               if _key(c) == iv.interviewer_id), "")
    return out


def _refuse(parent, title: str, message: str) -> None:
    from education_system.platform.delivery.gui.parented_dialogs import messagebox
    messagebox.showwarning(title, message,
                           parent=getattr(parent, "root", parent))


def open_exit_interviews_window(parent=None) -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    if not access.current().can(access.HR):
        _refuse(parent, "Exit Interviews", "Exit interviews are "
                "confidential HR records.")
        return
    data.init_db()
    win, nb = make_window(parent, "Staff Exit Interviews")
    tables: list[rt.RecordTable] = []

    def refresh_all() -> None:
        for t in tables:
            t.refresh()

    def new(table, staff_id: str | None = None,
            leaving: str | None = None) -> None:
        staff = _staff_choices()
        rt.form_dialog(
            table.parent, "Exit interview",
            (("staff", "Staff member", "choice", staff),) + _FIELDS,
            {"staff": next((s for s in staff if _key(s) == staff_id), ""),
             "leaving_date": leaving or "", "status": data.SCHEDULED},
            lambda v: data.create_interview(
                {**_to_payload(v), "staff_id": _key(v["staff"])}),
            refresh_all,
            intro="Leave the leaving date blank to use the date on their "
                  "staff record. A completed interview needs the main "
                  "reason and the interview date.")

    # ── Interviews ──
    def interviews_tab(parent: ttk.Frame) -> None:
        def load(f):
            return [{"id": i.interview_id, "staff": i.staff_name,
                     "role": i.job_role or "", "dept": i.department or "",
                     "leaving": i.leaving_date, "status": i.status,
                     "reason": i.primary_reason or "",
                     "dest": i.destination or "",
                     "avg": i.average_rating or "",
                     "rec": i.would_recommend or "",
                     "by": i.interviewer_name or ""}
                    for i in data.list_interviews(
                        status=f.get("status") or None,
                        academic_year=f.get("year") or None,
                        reason=f.get("reason") or None)]

        def edit(table):
            iv = data.get_interview(table.require()["id"])
            rt.form_dialog(table.parent,
                           f"Exit interview — {iv.staff_name}", _FIELDS,
                           _initial(iv),
                           lambda v: data.update_interview(
                               iv.interview_id, _to_payload(v)),
                           refresh_all)

        def feedback(table):
            iv = data.get_interview(table.require()["id"])
            rt.form_dialog(table.parent,
                           f"Ratings & feedback — {iv.staff_name}",
                           _FEEDBACK_FIELDS, _initial(iv),
                           lambda v: data.update_interview(
                               iv.interview_id, _to_payload(v)),
                           refresh_all,
                           intro="1 = very poor … 5 = very good. Leave an "
                                 "area blank if it was not discussed.")

        def view(table):
            iv = data.get_interview(table.require()["id"])
            lines = [f"{iv.staff_name} ({iv.job_role or '—'}, "
                     f"{iv.department or '—'})",
                     f"Started {iv.start_date or '—'}; leaving "
                     f"{iv.leaving_date} "
                     f"({iv.length_of_service_years or '—'} years)",
                     f"Status: {iv.status}", "",
                     f"Main reason:   {iv.primary_reason or '—'}",
                     f"Other reasons: {', '.join(iv.other_reasons) or '—'}",
                     f"Going to:      {iv.destination or '—'} "
                     f"{iv.destination_detail or ''}", "", "Ratings:"]
            lines += [f"  {a:<28} {iv.ratings[a]} "
                      f"({data.RATING_LABELS[iv.ratings[a]]})"
                      for a in data.FEEDBACK_AREAS if a in iv.ratings] \
                or ["  (none)"]
            lines += ["", f"Did well: {iv.went_well or '—'}",
                      f"Change:   {iv.could_improve or '—'}",
                      f"Would recommend: {iv.would_recommend or '—'};  "
                      f"would return: {iv.would_return or '—'}",
                      f"Interviewed by {iv.interviewer_name or '—'} on "
                      f"{iv.interview_date or '—'} ({iv.method or '—'})"]
            if iv.notes:
                lines += ["", iv.notes]
            rt.show_text(table.parent, "Exit interview", "\n".join(lines))

        tables.append(rt.RecordTable(
            parent,
            [("staff", "Staff", 170), ("role", "Role", 130),
             ("dept", "Department", 120), ("leaving", "Leaving", 95),
             ("status", "Status", 90), ("reason", "Main reason", 200),
             ("dest", "Going to", 200), ("avg", "Avg rating", 80),
             ("rec", "Recommend", 80), ("by", "Interviewer", 130)],
            load, key="id",
            filters=(("status", "Status", "choice", data.STATUSES),
                     ("year", "Academic year (2025/26)", "text"),
                     ("reason", "Reason", "choice", data.REASONS)),
            actions=(("New", new), ("Edit / complete", edit),
                     ("Ratings & feedback", feedback), ("View", view)),
            tags=lambda r: "muted" if r["status"] == data.DECLINED else (
                "warn" if r["status"] == data.SCHEDULED else None),
            on_open=view))

    # ── Leavers with no interview ──
    def leavers_tab(parent: ttk.Frame) -> None:
        def schedule(table):
            row = table.require()
            new(table, row["id"], row["leaving"] or None)

        tables.append(rt.RecordTable(
            parent,
            [("staff", "Staff", 200), ("role", "Role", 150),
             ("dept", "Department", 140), ("leaving", "Leaving", 100),
             ("source", "Known from", 200)],
            lambda f: [{"id": lv.staff_id, "staff": lv.staff_name,
                        "role": lv.job_role or "", "dept": lv.department or "",
                        "leaving": lv.leaving_date or "",
                        "source": lv.source}
                       for lv in data.leavers_without_interview(
                           since=f.get("since") or None)],
            key="id", filters=(("since", "Leaving since", "text"),),
            actions=(("Schedule / record interview", schedule),),
            on_open=schedule,
            note="Staff marked Left in the Staff Directory, or Left / on "
                 "notice on their HR record, with no exit interview yet."))

    # ── Report ──
    def report_tab(parent: ttk.Frame) -> None:
        def load(f):
            r = data.report(academic_year=f.get("year") or None,
                            department=f.get("dept") or None)
            rows = [{"id": "h", "what": "Interviews", "value":
                     f"{r.interviews} ({r.completed} completed, "
                     f"{r.declined} declined)"}]
            if r.average_service_years is not None:
                rows.append({"id": "svc", "what": "Average service",
                             "value": f"{r.average_service_years} years"})
            for k, v in r.primary_reasons.items():
                rows.append({"id": f"p{k}", "what": f"Main reason: {k}",
                             "value": v})
            for k, v in r.reasons.items():
                rows.append({"id": f"r{k}", "what": f"Any reason: {k}",
                             "value": v})
            for k, v in r.destinations.items():
                rows.append({"id": f"d{k}", "what": f"Going to: {k}",
                             "value": v})
            for a in data.FEEDBACK_AREAS:
                if a in r.area_averages:
                    rows.append({"id": f"a{a}", "what": f"Rating: {a}",
                                 "value": f"{r.area_averages[a]} / 5"})
            for k, v in r.would_recommend.items():
                rows.append({"id": f"w{k}", "what": f"Would recommend: {k}",
                             "value": v})
            for k, v in r.by_department.items():
                rows.append({"id": f"b{k}", "what": f"Department: {k}",
                             "value": v})
            return rows

        from education_system.systems.sixth_form.domain.staff import (
            staff as _staff,
        )
        tables.append(rt.RecordTable(
            parent, [("what", "Measure", 420), ("value", "Value", 260)],
            load, key="id",
            filters=(("year", "Academic year (2025/26)", "text"),
                     ("dept", "Department", "choice", _staff.DEPARTMENTS)),
            tags=lambda r: ("bad" if str(r["value"]).endswith("/ 5")
                            and float(str(r["value"]).split()[0]) < 3
                            else None),
            note="Reasons count completed interviews; ratings are averages "
                 "of the 1-5 scores given."))

    rt.notebook_tab(nb, "Interviews", interviews_tab)
    rt.notebook_tab(nb, "Leavers without interview", leavers_tab)
    rt.notebook_tab(nb, "Report", report_tab)
