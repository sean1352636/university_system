"""The My Day boxes fed by the linked areas: safeguarding (leads), my
absence (with Report sickness / Request absence), expense claims and budgets,
announcements, parents' evenings, attendance cases and wellbeing follow-ups,
and the SEND / medical needs of the pupils I teach.

Each box only appears when there is something for this person (or, for
absence and announcements, always - those apply to all staff). The data is
read once by :func:`modules.portals.domain.my_day.day`.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.secondary.modules.portals.gui.my_day_views import (
    _box,
    _date,
    _line,
    _open,
)
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.ui.gui.components import widgets as W


def draw_linked(grid: ttk.Frame, place: Callable[[ttk.LabelFrame], None], d: dict[str, Any],
                *, principal: Principal, app: Any, refresh: Callable[[], None]) -> None:
    _safeguarding(grid, place, d, app)
    _absence(grid, place, d, principal, app, refresh)
    _announcements(grid, place, d, principal, app, refresh)
    _expenses(grid, place, d, app)
    _parents_evenings(grid, place, d, app)
    _pastoral(grid, place, d, app)
    _needs(grid, place, d, app)
    _leads_due(grid, place, d, app)


def _safeguarding(grid, place, d, app) -> None:
    sg = d.get("safeguarding")
    if not sg:
        return
    total = sg["new"] + sg["overdue"]
    box = _box(grid, "Safeguarding (DSL)", total)
    if not total:
        _line(box, "No new concerns and nothing overdue.", "#060")
    if sg["new"]:
        _line(box, f"{sg['new']} new concern(s) to triage"
              + (f" - {sg['urgent']} URGENT" if sg["urgent"] else ""),
              "#a00" if sg["urgent"] else "#a60")
    if sg["overdue"]:
        _line(box, f"{sg['overdue']} overdue action(s) / review(s)", "#a00")
    _open(box, app, "safeguarding", "Safeguarding")
    place(box)


def _absence(grid, place, d, principal, app, refresh) -> None:
    from education_system.systems.secondary.modules.staff.domain import staff_absence as SA
    ab = d.get("absence") or {"off_now": [], "requests": [], "rtw_due": []}
    box = _box(grid, "My absence", len(ab["off_now"]) + len(ab["requests"]))
    for r in ab["off_now"]:
        _line(box, f"{r.absence_type}: {r.dates_label} ({r.status})"
              + (f" · back {_date(r.expected_return)}" if r.expected_return else ""))
    for q in ab["requests"]:
        _line(box, f"Request: {q.absence_type} {q.dates_label} - {q.status}",
              "#a60" if q.status == "Requested" else "")
    for r in ab["rtw_due"]:
        _line(box, f"Return-to-work meeting still to hold ({r.dates_label})", "#a60")
    if not any(ab.values()):
        _line(box, "Nothing recorded.", "#777")

    def sick() -> None:
        def save(v: dict[str, Any]) -> None:
            rec, covers = SA.report_sickness(actor=principal, start_date=v["start_date"] or None,
                                             expected_return=v["expected_return"] or None,
                                             reason=v["reason"] or None)
            messagebox.showinfo("Report sickness",
                                f"Recorded {rec.dates_label}. {covers} lesson(s) need cover - "
                                "the cover team can see them.", parent=grid)
            refresh()
        W.form_dialog(grid, "Report sickness",
                      [("start_date", "First day off", "", None),
                       ("expected_return", "Expected back (date)", "", None),
                       ("reason", "Reason (optional)", "", None)], save,
                      "Leave the first day blank for today. Your lessons go to cover.")

    def request() -> None:
        types = [t for t in SA.ABSENCE_TYPES if t not in SA.SICKNESS_TYPES]

        def save(v: dict[str, Any]) -> None:
            q = SA.request_absence(v, actor=principal)
            messagebox.showinfo("Request absence",
                                f"Request sent: {q.absence_type} {q.dates_label}.", parent=grid)
            refresh()
        W.form_dialog(grid, "Request absence",
                      [("absence_type", "Type", types[0], types),
                       ("start_date", "First day", "", None),
                       ("end_date", "Last day", "", None),
                       ("reason", "Reason", "", "text")], save,
                      "Nothing is covered until the request is approved.")
    bar = ttk.Frame(box)
    bar.pack(anchor="w", pady=(6, 0))
    ttk.Button(bar, text="Report sickness", command=sick).pack(side="left", padx=(0, 4))
    ttk.Button(bar, text="Request absence", command=request).pack(side="left", padx=(0, 4))
    ttk.Button(bar, text="Staff Absence", command=app._handler("staff_absence", "Staff Absence")
               ).pack(side="left")
    place(box)


def _announcements(grid, place, d, principal, app, refresh) -> None:
    from education_system.systems.secondary.modules.communication.domain import announcements as AN
    an = d.get("announcements") or {}
    active = an.get("active") or []
    if not active:
        return
    unread = {a.announcement_id for a in an.get("unread") or []}
    ack = {a.announcement_id for a in an.get("to_acknowledge") or []}
    box = _box(grid, "Announcements", len(unread))
    for a in active[:6]:
        mark = "● " if a.announcement_id in unread else ""
        _line(box, f"{mark}{a.title}" + (f" - {a.summary}" if a.summary else ""),
              "#a00" if a.announcement_id in ack else "")

        def show(a=a) -> None:
            AN.mark_read(a.announcement_id, principal)
            if a.announcement_id in ack and messagebox.askyesno(
                    a.title, a.body + "\n\nI have read and understood this.", parent=grid):
                AN.acknowledge(a.announcement_id, principal)
            elif a.announcement_id not in ack:
                messagebox.showinfo(a.title, a.body, parent=grid)
            refresh()
        ttk.Button(box, text="Acknowledge" if a.announcement_id in ack else "Read",
                   command=show).pack(anchor="w")
    _open(box, app, "announcements", "Announcements")
    place(box)


def _expenses(grid, place, d, app) -> None:
    ex = d.get("expenses") or {}
    queue, fix, over = ex.get("to_approve") or [], ex.get("to_fix") or [], \
        ex.get("overspends") or []
    if not (queue or fix or over):
        return
    box = _box(grid, "Expenses and budgets", len(queue) + len(fix))
    for c in queue[:5]:
        _line(box, f"To approve: {c.claim_ref} {c.claimant_name or c.claimant_id} - "
                   f"{c.title} {c.total}", "#a60")
    for c in fix[:5]:
        _line(box, f"My claim {c.claim_ref} {c.title}: {c.status.lower()}"
              + (f" - {c.rejection_reason}" if c.rejection_reason else ""),
              "#a00" if c.status == "Rejected" else "")
    for p, state in over[:5]:
        _line(box, f"Budget {p.code} {p.description}: {state}",
              "#a00" if state == "over" else "#a60")
    bar = ttk.Frame(box)
    bar.pack(anchor="w", pady=(6, 0))
    ttk.Button(bar, text="Expense Claims",
               command=app._handler("expense_claims", "Expense Claims")).pack(side="left")
    if over:
        ttk.Button(bar, text="Budgets", command=app._handler("budgets", "Budgets")).pack(
            side="left", padx=4)
    place(box)


def _parents_evenings(grid, place, d, app) -> None:
    rows = d.get("parents_evenings") or []
    if not rows:
        return
    box = _box(grid, "Parents' evenings", len(rows))
    for e, t in rows:
        _line(box, f"{_date(e.event_date)} {e.name} {e.start_time}-{e.end_time}"
              + (f" · room {t.room}" if t.room else "") + f" ({e.status})")
    _open(box, app, "parents_evenings", "Parents' Evenings", "My appointments")
    place(box)


def _pastoral(grid, place, d, app) -> None:
    ps = d.get("pastoral") or {}
    cases, fups = ps.get("attendance_cases") or [], ps.get("wellbeing_follow_ups") or []
    if not (cases or fups):
        return
    box = _box(grid, "Attendance and wellbeing", len(cases) + len(fups))
    for c in cases[:6]:
        pct = f" {c.attendance_pct:.1f}%" if c.attendance_pct is not None else ""
        _line(box, f"Attendance: {c.pupil_name}{pct} - {c.stage}"
              + (f" · review {_date(c.next_review_date)}" if c.next_review_date else ""))
    for w in fups[:6]:
        _line(box, f"Wellbeing follow-up: {w.pupil_name} (due {_date(w.follow_up_date)})",
              "#a00")
    bar = ttk.Frame(box)
    bar.pack(anchor="w", pady=(6, 0))
    if cases:
        ttk.Button(bar, text="Attendance Concerns",
                   command=app._handler("attendance_concerns", "Attendance Concerns")).pack(
            side="left", padx=(0, 4))
    if fups:
        ttk.Button(bar, text="Wellbeing", command=app._handler("wellbeing", "Wellbeing")).pack(
            side="left")
    place(box)


def _needs(grid, place, d, app) -> None:
    nd = d.get("needs") or {}
    send, med = nd.get("send") or [], nd.get("medical") or []
    if not (send or med):
        return
    box = _box(grid, "My pupils' needs (SEND and medical)", len(send) + len(med))
    for m in med[:8]:
        _line(box, f"{m['pupil_name']}: " + ", ".join(m["conditions"] + m["allergies"])
              + (f" · {m['what_to_do'][0]}" if m["what_to_do"] else ""),
              "#a00" if m["anaphylaxis"] or m["worst"] in ("Severe", "Life-threatening")
              else "")
    for s in send[:8]:
        first = (s["strategies"] or "").splitlines()[0] if s["strategies"] else ""
        _line(box, f"{s['pupil_name']} ({s['stage']}) {s['needs']}"
              + (f" - {first}" if first else ""))
    bar = ttk.Frame(box)
    bar.pack(anchor="w", pady=(6, 0))
    ttk.Button(bar, text="SEND", command=app._handler("send", "SEND")).pack(side="left")
    ttk.Button(bar, text="Medical", command=app._handler("medical", "Medical")).pack(
        side="left", padx=4)
    place(box)


def _leads_due(grid, place, d, app) -> None:
    ld = d.get("leads_due") or {}
    send, med, pp = ld.get("send"), ld.get("medical"), ld.get("pp_without_activities")
    rows = [*(("SEND", x) for x in send or []), *(("Medical", x) for x in med or [])]
    if not rows and not pp:
        return
    box = _box(grid, "SEND, medical and pupil premium to do", len(rows))
    for area, x in rows[:10]:
        who = x.get("pupil_name") or x.get("who") or ""
        _line(box, f"{area}: {_date(x['due'])} {x['item']}" + (f" - {who}" if who else ""),
              "#a00" if x["overdue"] else "")
    if len(rows) > 10:
        _line(box, f"... and {len(rows) - 10} more", "#777")
    if pp:
        _line(box, f"Pupil premium: {pp} eligible pupil(s) with no activity recorded", "#a60")
    bar = ttk.Frame(box)
    bar.pack(anchor="w", pady=(6, 0))
    for key, label, show in (("send", "SEND", send is not None),
                             ("medical", "Medical", med is not None),
                             ("pupil_premium", "Pupil Premium", pp is not None)):
        if show:
            ttk.Button(bar, text=label, command=app._handler(key, label)).pack(
                side="left", padx=(0, 4))
    place(box)


__all__ = ["draw_linked"]
