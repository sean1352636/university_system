"""Tkinter "My area" window: the signed-in member of staff's own
timetable, absences, appraisal, CPD and training, DBS status, helpdesk
tickets and (when available) directed time. Open to every staff login.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.sixth_form.domain.staff.my_area import (
    my_area as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    make_window,
)
from education_system.systems.sixth_form.interfaces.gui.progression import (
    _record_tabs as rt,
)

logger = logging.getLogger(__name__)

_TRAINING_TAG = {"Overdue": "bad", "Missing": "bad", "Due soon": "warn",
                 "Done": "good"}


def open_my_area_window(parent=None) -> None:
    try:
        s = data.my_staff_record()
    except (ValueError, PermissionError) as exc:
        master = getattr(parent, "root", parent)
        from education_system.platform.delivery.gui.parented_dialogs import messagebox
        messagebox.showwarning("My area", str(exc), parent=master)
        return
    win, nb = make_window(parent, f"My area — {s.full_name}")
    rt.notebook_tab(nb, "Overview", _overview_tab)
    rt.notebook_tab(nb, "Timetable", _timetable_tab)
    rt.notebook_tab(nb, "Absences", _absences_tab)
    rt.notebook_tab(nb, "Appraisal", _appraisal_tab)
    rt.notebook_tab(nb, "CPD & training", _training_tab)
    rt.notebook_tab(nb, "DBS", _dbs_tab)
    rt.notebook_tab(nb, "Helpdesk", lambda p: _tickets_tab(p, win))
    rt.notebook_tab(nb, "Directed time", _directed_tab)


def _text_box(parent: ttk.Frame, lines_fn) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    box = tk.Text(parent, wrap="word", font=("TkFixedFont", 10))

    def render() -> None:
        try:
            lines = lines_fn()
        except (ValueError, PermissionError) as exc:
            lines = [str(exc)]
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")

    ttk.Button(bar, text="Refresh", command=render).pack(side="left")
    box.pack(fill="both", expand=True)
    render()


def _overview_tab(parent: ttk.Frame) -> None:
    def lines():
        o = data.overview()
        tr = o["training"]
        training = (", ".join(f"{k}: {v}" for k, v in tr.items())
                    if isinstance(tr, dict) else tr) or "nothing required"
        return [
            f"{o['name']}  ({o['staff_id']})",
            f"{o['role']}, {o['department']}"
            + (f" — line manager {o['line_manager']}"
               if o.get("line_manager") else ""), "",
            f"  Lessons a week:            {o['lessons_per_week']}",
            f"  Absence days this year:    {o['absence_days_this_year']}",
            f"  CPD hours this year:       {o['cpd_hours_this_year']}",
            f"  Mandatory training:        {training}",
            f"  DBS:                       {o['dbs']}",
            f"  Open helpdesk tickets:     {o['open_tickets']}",
            f"  Appraisal:                 {o['appraisal']}", "",
            "Only your own records are shown here. Speak to HR if "
            "anything is wrong."]
    _text_box(parent, lines)


def _timetable_tab(parent: ttk.Frame) -> None:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    status = ttk.Label(parent, text="", foreground="#555")
    status.pack(side="bottom", anchor="w")
    cols = ["period"] + list(_tt.DAYS)
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=8)
    tree.heading("period", text="Period")
    tree.column("period", width=110, anchor="w")
    for d in _tt.DAYS:
        tree.heading(d, text=d)
        tree.column(d, width=220, anchor="w")
    style = ttk.Style(parent)
    style.configure("MyArea.Treeview", rowheight=48)
    tree.configure(style="MyArea.Treeview")

    def render() -> None:
        tree.delete(*tree.get_children())
        try:
            rows = data.my_timetable()
        except (ValueError, PermissionError) as exc:
            status.configure(text=str(exc), foreground="#a33")
            return
        grid: dict[tuple[int, int], list[str]] = {}
        for e in rows:
            grid.setdefault((e.day, e.period), []).append(
                f"{e.group_name} {e.room or ''}".strip())
        for p in _tt.PERIODS:
            start, end = _tt.DEFAULT_PERIOD_TIMES.get(p, ("", ""))
            tree.insert("", "end", values=[f"P{p} {start}-{end}"] + [
                " / ".join(grid.get((d, p), [])) for d in _tt.DAY_NUMBERS])
        status.configure(text=f"{len(rows)} lesson(s) a week. Groups are "
                              "matched on the teacher named on the class "
                              "group or course.", foreground="#555")

    ttk.Button(bar, text="Refresh", command=render).pack(side="left")
    tree.pack(fill="both", expand=True)
    render()


def _absences_tab(parent: ttk.Frame) -> None:
    rt.RecordTable(
        parent,
        [("date", "Date", 95), ("type", "Type", 160),
         ("expected", "Expected back", 110), ("returned", "Returned", 95),
         ("days", "Days", 60), ("status", "Status", 90),
         ("rtw", "Return-to-work", 140), ("reason", "Reason", 260)],
        lambda _f: [{"id": a.absence_id, "date": a.absence_date,
                     "type": a.absence_type,
                     "expected": a.expected_return or "",
                     "returned": a.actual_return or "",
                     "days": a.days_lost if a.days_lost is not None else "",
                     "status": a.status,
                     "rtw": (f"done {a.rtw_meeting_on}" if a.rtw_meeting_on
                             else "due" if a.rtw_required else ""),
                     "reason": a.reason or ""} for a in data.my_absences()],
        key="id", note="Absences recorded for you. To report a new absence "
                       "follow the college's absence procedure.")


def _appraisal_tab(parent: ttk.Frame) -> None:
    def load(_f):
        out = []
        for a in data.my_appraisals():
            so = data.signoff_for(a.appraisal_id)
            out.append({"id": a.appraisal_id, "cycle": a.cycle,
                        "appraiser": a.appraiser_name or a.appraiser_id or "",
                        "status": a.status, "grade": a.grade_label,
                        "mid": a.mid_year_review_on or "",
                        "end": a.end_year_review_on or "",
                        "self": "Yes" if a.self_review_completed else "No",
                        "signed": (f"{so.response} {so.signed_at[:10]}"
                                   if so else "")})
        return out

    def view(table):
        aid = table.require()["id"]
        a = next(x for x in data.my_appraisals() if x.appraisal_id == aid)
        lines = [f"Appraisal {a.cycle} — {a.status}",
                 f"Appraiser: {a.appraiser_name or a.appraiser_id or '—'}",
                 f"Objectives set {a.objectives_set_on or '—'}; mid-year "
                 f"{a.mid_year_review_on or '—'}; end-year "
                 f"{a.end_year_review_on or '—'}",
                 f"Overall: {a.grade_label}; pay progression: "
                 f"{a.pay_progression}", "",
                 f"Strengths: {a.strengths or '—'}",
                 f"To develop: {a.areas_to_develop or '—'}",
                 f"CPD needs: {a.cpd_needs or '—'}", "",
                 f"Appraiser comments: {a.appraiser_comments or '—'}",
                 f"Your comments: {a.appraisee_comments or '—'}", "",
                 "Objectives:"]
        for o in data.my_objectives(aid):
            lines.append(f"  {o.objective_number}. [{o.status}] {o.title}"
                         f" ({o.objective_type})")
            for label, v in (("Success criteria", o.success_criteria),
                             ("Progress", o.progress_notes),
                             ("Mid-year", o.mid_year_progress),
                             ("Evidence", o.end_year_evidence)):
                if v:
                    lines.append(f"       {label}: {v}")
        so = data.signoff_for(aid)
        if so:
            lines += ["", f"Signed off {so.signed_at.replace('T', ' ')} — "
                          f"{so.response}"]
        rt.show_text(table.parent, f"Appraisal {a.cycle}", "\n".join(lines))

    def comments(table):
        aid = table.require()["id"]
        a = next(x for x in data.my_appraisals() if x.appraisal_id == aid)
        rt.form_dialog(table.parent, f"My comments — {a.cycle}",
                       (("comments", "Your comments", "longtext"),),
                       {"comments": a.appraisee_comments or ""},
                       lambda v: data.add_my_comments(aid, v["comments"]),
                       table.refresh)

    def self_review(table):
        row = table.require()
        done = row["self"] != "Yes"
        data.mark_self_review_done(row["id"], done)
        table.refresh()

    def sign(table):
        aid = table.require()["id"]
        rt.form_dialog(table.parent, "Sign off appraisal",
                       (("response", "Your response", "choice",
                         data.SIGNOFF_RESPONSES),
                        ("comments", "Comments (needed unless you agree)",
                         "multiline")),
                       {"response": data.AGREE},
                       lambda v: data.sign_off(aid, v["response"],
                                               v["comments"]),
                       table.refresh,
                       intro="Signing confirms you have read the appraisal "
                             "record. Your comments are locked once signed.")

    rt.RecordTable(
        parent,
        [("cycle", "Cycle", 90), ("appraiser", "Appraiser", 160),
         ("status", "Status", 130), ("grade", "Overall", 150),
         ("mid", "Mid-year", 95), ("end", "End-year", 95),
         ("self", "Self-review done", 110), ("signed", "Signed off", 180)],
        load, key="id",
        actions=(("View", view), ("My comments", comments),
                 ("Self-review done / not done", self_review),
                 ("Sign off", sign)),
        on_open=view,
        tags=lambda r: "good" if r["signed"] else None)


def _training_tab(parent: ttk.Frame) -> None:
    top = ttk.LabelFrame(parent, text="Mandatory training", padding=6)
    top.pack(fill="both", expand=True)
    rt.RecordTable(
        top,
        [("training", "Training", 320), ("state", "State", 90),
         ("done", "Last done", 100), ("expires", "Expires", 100),
         ("source", "Recorded in", 140), ("required", "Required", 80)],
        lambda _f: [{"id": c.type_id, "training": c.type_name,
                     "state": c.state or "—", "done": c.completed_on or "",
                     "expires": c.expires_on or "",
                     "source": c.latest.source if c.latest else "",
                     "required": "Yes" if c.required else "No"}
                    for c in data.my_training()],
        key="id", tags=lambda r: _TRAINING_TAG.get(r["state"]),
        note="If something you have done is missing, send HR the "
             "certificate.")
    bottom = ttk.LabelFrame(parent, text="CPD", padding=6)
    bottom.pack(fill="both", expand=True, pady=(6, 0))
    from education_system.systems.sixth_form.domain.staff.cpd import cpd

    def cpd_rows(_f):
        acts = {}
        out = []
        for r in data.my_cpd():
            if r.activity_id and r.activity_id not in acts:
                acts[r.activity_id] = cpd.get_activity(r.activity_id)
            a = acts.get(r.activity_id)
            out.append({"id": r.record_id,
                        "title": a.title if a else (r.activity_title_cache
                                                    or ""),
                        "date": r.attended_on or (a.activity_date if a
                                                  else r.booked_on),
                        "status": r.status,
                        "hours": r.hours_completed or "",
                        "cert": "filed" if r.certificate_filed else (
                            "received" if r.certificate_received else "")})
        return out

    rt.RecordTable(
        bottom,
        [("title", "Activity", 320), ("date", "Date", 100),
         ("status", "Status", 100), ("hours", "Hours", 70),
         ("cert", "Certificate", 100)],
        cpd_rows, key="id")


def _dbs_tab(parent: ttk.Frame) -> None:
    def lines():
        c = data.my_dbs()
        out = [f"Status: {data.dbs_state(c)}", ""]
        if c is not None:
            out += [f"  Level:            {c.level}",
                    f"  Certificate no.:  {c.dbs_number or '—'}",
                    f"  Issued:           {c.issued_on or '—'}",
                    f"  Expires / renew:  {c.expires_on or '—'}",
                    f"  Update Service:   "
                    f"{'subscribed' if c.update_service_subscribed else 'no'}",
                    f"  Last update check: {c.last_update_check_on or '—'}"]
        return out
    _text_box(parent, lines)


def _tickets_tab(parent: ttk.Frame, win) -> None:
    def open_helpdesk(_table):
        from education_system.systems.sixth_form.domains.operations.interfaces.gui.helpdesk import (
            helpdesk_views,
        )
        helpdesk_views.open_helpdesk_window(win)

    rt.RecordTable(
        parent,
        [("ref", "Ref", 80), ("kind", "Type", 50),
         ("title", "Summary", 300), ("location", "Location", 170),
         ("status", "Status", 90), ("assignee", "With", 140),
         ("raised", "Raised", 120)],
        lambda f: [{"id": t.ticket_id, "ref": t.reference, "kind": t.kind,
                    "title": t.title, "location": t.location or "",
                    "status": t.status, "assignee": t.assignee_name or "",
                    "raised": t.raised_at.replace("T", " ")[:16]}
                   for t in data.my_tickets(open_only=f.get("open") == "Yes")],
        key="id", filters=(("open", "Open only", "choice", ("Yes",)),),
        actions=(("Open the helpdesk (report / comment)", open_helpdesk),),
        tags=lambda r: "muted" if r["status"] in ("Resolved", "Closed")
        else None)


def _directed_tab(parent: ttk.Frame) -> None:
    def lines():
        d = data.my_directed_time()
        if not d.available:
            return [d.message]
        out = [d.message, ""]
        for row in d.rows:
            out.append("  " + "   ".join(f"{k}: {v}" for k, v in row.items()))
        return out
    _text_box(parent, lines)
