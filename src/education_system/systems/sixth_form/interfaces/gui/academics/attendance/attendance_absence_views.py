"""GUI tabs for absence intake, planned leave, and signing in/out of site.

Two panels, mounted as extra tabs on the Attendance screen:

* **Leave & absence** — the one absence store (:mod:`attendance_leave`),
  which holds planned leave, the pastoral team's absence requests and
  inbound absence reports together:

  - *Leave requests*: the queue awaiting a decision, with clashes and the
    learner's discretionary allowance, approve / decline / withdraw /
    cancel, and a new request.
  - *Study leave*: grant exam-season study leave to a group at once.
  - *Awaiting marks*: approved absence that has not reached the
    register (pastoral approvals record the decision only), and "Write
    marks" for it.
  - *Reports*: the absence-report queue (:mod:`attendance_absence_reports`)
    — accept with a code, reject with a reason, take a report, and
    self-certify on a learner's behalf.
  - *All absence*: every row of the store, filterable by source, with
    the migration check.

* **Sign in / out** — :mod:`attendance_signout`: sign a learner out of
  site (reason, parent permission, due-back time), the currently
  off-site list the fire roll call reads, late returns and their alerts,
  and the day's log.

Shares the small widget helpers in :mod:`attendance_capture_views`.
Nothing here touches a database until a tab is built.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_absence_reports as reports,
    attendance_codes as codes,
    attendance_leave as leave,
    attendance_signout as signout,
    attendance_signout_requests as signout_requests,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.gui.academics.attendance import (
    attendance_capture_views as cap,
)

logger = logging.getLogger(__name__)

_ORIGIN_LABEL: dict[str, str] = {
    leave.ORIGIN_LEAVE: "Leave",
    leave.ORIGIN_PASTORAL: "Pastoral request",
    leave.ORIGIN_REPORT: "Report",
}


def _yes(gui, title: str, text: str) -> bool:
    return messagebox.askyesno(title, text, parent=gui.root)


# ═══ Leave & absence ═════════════════════════════════════════════════

def build_leave_tab(gui, parent: ttk.Frame) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    pages: list[tuple[str, Callable[[Any, ttk.Frame], Any]]] = [
        ("Leave requests", _build_leave_requests),
        ("Study leave", _build_study_leave),
        ("Awaiting marks", _build_awaiting_marks),
        ("Reports", _build_reports),
        ("All absence", _build_all_absence),
    ]
    for title, builder in pages:
        page = ttk.Frame(nb, padding=8)
        nb.add(page, text=title)
        builder(gui, page)


def _build_leave_requests(gui, parent: ttk.Frame) -> None:
    cap._hint(parent, "Planned absence asked for here or logged by the "
              "pastoral team. Approving codes every timetabled lesson in "
              f"the span; the college asks for {leave.NOTICE_DAYS} days' "
              "notice and allows "
              f"{leave.ANNUAL_ALLOWANCE_DAYS} discretionary day(s) a year.")
    bar = cap._bar(parent)
    view_var = tk.StringVar(value="Awaiting decision")
    ttk.Label(bar, text="Show:").pack(side="left")
    ttk.Combobox(bar, textvariable=view_var, state="readonly", width=20,
                 values=["Awaiting decision", "Upcoming (14 days)",
                         "Short notice", *leave.STATES]).pack(
        side="left", padx=(4, 12))
    student_var = tk.StringVar()
    cap._labelled_entry(bar, "Student ID:", student_var, 12)

    actions = cap._bar(parent)
    detail = ttk.Label(parent, text="", foreground="#555", wraplength=900,
                       justify="left")
    detail.pack(anchor="w", pady=(0, 6))
    tree = cap._tree(parent, [
        ("id", "#", 50), ("source", "Source", 110), ("dates", "Dates", 170),
        ("student", "Learner", 170), ("kind", "Kind", 150),
        ("notice", "Notice", 60), ("state", "State", 90),
        ("marks", "Marks", 60)])

    def rows() -> list[leave.LeaveRequest]:
        view = view_var.get()
        sid = student_var.get().strip() or None
        if view == "Awaiting decision":
            out = leave.pending()
            return [r for r in out if not sid or r.student_id == sid]
        if view == "Upcoming (14 days)":
            out = leave.upcoming(days=14)
        elif view == "Short notice":
            out = leave.short_notice_report()
        else:
            out = leave.list_requests(state=view, student_id=sid, limit=500)
        return [r for r in out if not sid or r.student_id == sid]

    def refresh() -> None:
        data = cap._run(gui, rows) or []
        cap._fill(tree, [
            (r.request_id, _ORIGIN_LABEL.get(r.origin, r.origin), r.span,
             r.student_name or r.student_id, r.kind,
             "—" if r.notice_days is None else
             f"{r.notice_days}d" + (" ⚠" if r.short_notice else ""),
             r.state, r.marks_written)
            for r in data])
        detail.configure(text=f"{len(data)} request(s).")

    def selected() -> leave.LeaveRequest | None:
        rid = cap._selected_id(tree, gui.root)
        return leave.get_request(rid) if rid is not None else None

    def show_detail(_event=None) -> None:
        sel = tree.selection()
        if not sel:
            return
        try:
            request = leave.get_request(int(tree.item(sel[0], "values")[0]))
        except (ValueError, IndexError):
            return
        if request is None:
            return
        bits = [f"{request.kind}: {leave.describe_kind(request.kind)}"]
        if request.detail:
            bits.append(f"Detail: {request.detail}")
        if request.destination:
            bits.append(f"Where: {request.destination}")
        try:
            clashes = leave.clashes(request.request_id)
            if clashes:
                bits.append("⚠ Clashes: " + "; ".join(c.label for c in clashes))
            allowance = leave.leave_used(request.student_id)
            bits.append(f"Discretionary leave used this year: "
                        f"{allowance.used_days}/{allowance.allowance} day(s)")
        except ValidationError as e:
            bits.append(str(e))
        if request.decision_note:
            bits.append(f"Decision note: {request.decision_note}")
        detail.configure(text="   ·   ".join(bits))

    def new_request() -> None:
        values = cap._form(gui, "Request leave", [
            ("student_id", "Student ID", student_var.get()),
            ("kind", "Kind", list(leave.KINDS)),
            ("date_from", "From (YYYY-MM-DD)", cap._today()),
            ("date_to", "To (blank = same day)", ""),
            ("detail", "Detail", ""),
            ("destination", "Where", ""),
            ("requested_by", "Requested by", cap._actor(gui) or ""),
        ])
        if not values:
            return
        request = cap._run(gui, lambda: leave.request_leave(
            values["student_id"], values["date_from"],
            date_to=values["date_to"] or None, kind=values["kind"],
            detail=values["detail"] or None,
            destination=values["destination"] or None,
            requested_by=values["requested_by"] or None))
        if request is not None:
            note = (f"\n\n⚠ {request.notice_days} day(s) notice — the college "
                    f"asks for {leave.NOTICE_DAYS}." if request.short_notice
                    else "")
            messagebox.showinfo("Leave requested",
                                f"#{request.request_id}: {request.label}{note}",
                                parent=gui.root)
            refresh()

    def approve() -> None:
        request = selected()
        if request is None:
            return
        clashes = cap._run(gui, lambda: leave.clashes(request.request_id)) or []
        ignore = False
        if clashes:
            ignore = _yes(gui, "Clashes",
                          "Already in the diary:\n\n"
                          + "\n".join(c.label for c in clashes)
                          + "\n\nApprove over the clash?")
            if not ignore:
                return
        values = cap._form(gui, f"Approve #{request.request_id}", [
            ("decided_by", "Approved by", cap._actor(gui) or ""),
            ("code", "Code (blank = from kind)", ""),
            ("note", "Note", ""),
        ])
        if not values:
            return
        result = cap._run(gui, lambda: leave.approve(
            request.request_id, decided_by=values["decided_by"],
            code=values["code"] or None, note=values["note"] or None,
            ignore_clashes=ignore))
        if result is not None:
            messagebox.showinfo(
                "Approved", f"{result.marks_written} mark(s) written"
                + (f"; {len(result.skipped)} day(s) skipped (closed or "
                   "submitted)." if result.skipped else "."),
                parent=gui.root)
            refresh()

    def decline() -> None:
        request = selected()
        if request is None:
            return
        values = cap._form(gui, f"Decline #{request.request_id}", [
            ("reason", "Reason (required)", ""),
            ("decided_by", "Decided by", cap._actor(gui) or ""),
        ])
        if values and cap._run(gui, lambda: leave.decline(
                request.request_id, reason=values["reason"],
                decided_by=values["decided_by"] or None)) is not None:
            refresh()

    def withdraw() -> None:
        request = selected()
        if request is None:
            return
        values = cap._form(gui, f"Withdraw #{request.request_id}",
                           [("reason", "Reason", "")])
        if values is not None and cap._run(gui, lambda: leave.withdraw(
                request.request_id,
                reason=values.get("reason") or None)) is not None:
            refresh()

    def cancel() -> None:
        request = selected()
        if request is None:
            return
        values = cap._form(gui, f"Cancel approved leave #{request.request_id}", [
            ("reason", "Reason (required)", ""),
            ("actor", "Cancelled by", cap._actor(gui) or ""),
        ])
        if values and cap._run(gui, lambda: leave.cancel(
                request.request_id, reason=values["reason"],
                actor=values["actor"] or None)) is not None:
            messagebox.showinfo("Cancelled",
                                "Leave cancelled and its marks voided.",
                                parent=gui.root)
            refresh()

    def breakdown() -> None:
        data = cap._run(gui, leave.kind_breakdown) or {}
        text = "\n".join(f"{kind:<28}{days:>5} day(s)"
                         for kind, days in sorted(data.items(),
                                                  key=lambda kv: -kv[1]))
        cap._show_text(gui, "Approved leave by kind",
                       text or "No approved leave yet.")

    for label, command in (("Refresh", refresh), ("New request…", new_request),
                           ("Approve…", approve), ("Decline…", decline),
                           ("Withdraw…", withdraw),
                           ("Cancel approved…", cancel),
                           ("Days by kind", breakdown)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 6))
    tree.bind("<<TreeviewSelect>>", show_detail)
    view_var.trace_add("write", lambda *_a: refresh())
    refresh()


def _build_study_leave(gui, parent: ttk.Frame) -> None:
    cap._hint(parent, "Study leave is granted by the college to a cohort, "
              "not asked for one learner at a time. Each learner gets leave "
              "approved at once and coded S; exam sittings inside the span "
              "are expected. Anyone already on leave over those dates is "
              "skipped and listed.")
    form = ttk.Frame(parent)
    form.pack(anchor="w", fill="x", pady=(0, 8))
    labels, group_ids = cap._group_choices()
    group_var = tk.StringVar(value=labels[0] if labels else "")
    ids_var = tk.StringVar()
    from_var = tk.StringVar(value=cap._today())
    to_var = tk.StringVar(value=cap._today())
    detail_var = tk.StringVar(value="Exam-season study leave")
    by_var = tk.StringVar(value=cap._actor(gui) or "")
    use_group = tk.BooleanVar(value=bool(labels))
    rows = [
        ("Use a class group", None),
        ("Class group", ttk.Combobox(form, textvariable=group_var,
                                     values=labels, state="readonly",
                                     width=40)),
        ("…or student IDs (comma-separated)",
         ttk.Entry(form, textvariable=ids_var, width=42)),
        ("From (YYYY-MM-DD)", ttk.Entry(form, textvariable=from_var, width=14)),
        ("To (YYYY-MM-DD)", ttk.Entry(form, textvariable=to_var, width=14)),
        ("Detail", ttk.Entry(form, textvariable=detail_var, width=42)),
        ("Granted by", ttk.Entry(form, textvariable=by_var, width=24)),
    ]
    for row, (label, widget) in enumerate(rows):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w",
                                         pady=3, padx=(0, 8))
        if widget is None:
            widget = ttk.Checkbutton(form, variable=use_group)
        widget.grid(row=row, column=1, sticky="w")

    out = cap._tree(parent, [("student", "Learner", 140),
                             ("result", "Result", 600)], height=10)

    def grant() -> None:
        ids = [s.strip() for s in ids_var.get().split(",") if s.strip()]
        group_id = group_ids.get(group_var.get()) if use_group.get() else None
        if group_id is None and not ids:
            messagebox.showinfo("Study leave",
                                "Choose a class group or list student IDs.",
                                parent=gui.root)
            return
        if not _yes(gui, "Grant study leave",
                    f"Grant study leave {from_var.get()} → {to_var.get()} "
                    "and write the marks now?"):
            return
        result = cap._run(gui, lambda: leave.grant_study_leave(
            from_var.get().strip(), to_var.get().strip(),
            decided_by=by_var.get().strip(), student_ids=ids,
            group_id=group_id, detail=detail_var.get().strip() or None))
        if result is None:
            return
        granted = [leave.get_request(r.request_id) for r in result.granted]
        cap._fill(out, [(r.student_id, f"Granted ({a.marks_written} mark(s))")
                        for r, a in zip(granted, result.granted) if r]
                  + [(sid, f"Skipped: {why}")
                     for sid, why in result.skipped.items()])
        messagebox.showinfo("Study leave", result.summary, parent=gui.root)

    ttk.Button(form, text="Grant study leave", command=grant).grid(
        row=len(rows), column=1, sticky="w", pady=(8, 0))


def _build_awaiting_marks(gui, parent: ttk.Frame) -> None:
    cap._hint(parent, "Approved absence that has not been written to the "
              "register. Approvals in the pastoral absence log record the "
              "decision only; Write marks codes every timetabled lesson in "
              "the span with the code the leave kind implies.")
    actions = cap._bar(parent)
    tree = cap._tree(parent, [
        ("id", "#", 50), ("source", "Source", 120), ("dates", "Dates", 170),
        ("student", "Learner", 120), ("kind", "Kind", 160),
        ("decided", "Decided by", 140)])

    def refresh() -> None:
        data = cap._run(gui, leave.awaiting_marks) or []
        cap._fill(tree, [(r.request_id, _ORIGIN_LABEL.get(r.origin, r.origin),
                          r.span, r.student_id, r.kind, r.decided_by or "—")
                         for r in data])

    def write() -> None:
        rid = cap._selected_id(tree, gui.root)
        if rid is None:
            return
        actor = cap._actor(gui) or ""
        values = cap._form(gui, f"Write marks for #{rid}", [
            ("actor", "Written by", actor),
            ("code", "Code (blank = from kind)", ""),
        ])
        if not values:
            return
        try:
            result = leave.apply_marks(rid, actor=values["actor"],
                                       code=values["code"] or None)
        except ValidationError as e:
            # Only the exam-clash refusal can be overridden.
            if "sitting" not in str(e):
                messagebox.showerror("Not done", str(e), parent=gui.root)
                return
            if not _yes(gui, "Exam clash", f"{e}\n\nWrite the marks anyway?"):
                return
            result = cap._run(gui, lambda: leave.apply_marks(
                rid, actor=values["actor"], code=values["code"] or None,
                ignore_clashes=True))
            if result is None:
                return
        messagebox.showinfo("Marks written",
                            f"{result.marks_written} mark(s) written.",
                            parent=gui.root)
        refresh()

    ttk.Button(actions, text="Refresh", command=refresh).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Write marks…", command=write).pack(side="left")
    refresh()


def _build_reports(gui, parent: ttk.Frame) -> None:
    cap._hint(parent, "Somebody told the college a learner is absent. A "
              "report writes no mark until it is accepted with a code; "
              "self-certification codes it at once, up to the term's cap.")
    bar = cap._bar(parent)
    state_var = tk.StringVar(value=reports.PENDING)
    ttk.Label(bar, text="State:").pack(side="left")
    ttk.Combobox(bar, textvariable=state_var, state="readonly", width=14,
                 values=["All", *reports.STATES]).pack(side="left",
                                                       padx=(4, 12))
    count = ttk.Label(bar, text="", foreground="#555")
    count.pack(side="left")
    actions = cap._bar(parent)
    tree = cap._tree(parent, [
        ("id", "#", 50), ("dates", "Dates", 170), ("student", "Learner", 160),
        ("reason", "Reason", 180), ("by", "Reported by", 140),
        ("state", "State", 90), ("code", "Code", 50), ("self", "Self-cert", 70)])

    def refresh() -> None:
        state = state_var.get()

        def load() -> list[reports.AbsenceReport]:
            if state == reports.PENDING:
                return reports.queue()
            return reports.list_reports(
                state=None if state == "All" else state, limit=500)

        data = cap._run(gui, load) or []
        cap._fill(tree, [
            (r.report_id, r.span, r.student_name or r.student_id,
             r.reason_text or "—",
             f"{r.reported_by} ({r.channel.lower()})"
             + (f" {r.reporter_name}" if r.reporter_name else ""),
             r.state, r.code or "", "yes" if r.self_certified else "")
            for r in data])
        pending = cap._run(gui, reports.queue_count)
        count.configure(text=f"{pending or 0} waiting")

    def take() -> None:
        values = cap._form(gui, "Take an absence report", [
            ("student_id", "Student ID", ""),
            ("date_from", "From (YYYY-MM-DD)", cap._today()),
            ("date_to", "To (blank = same day)", ""),
            ("channel", "How", list(reports.CHANNELS)),
            ("reported_by", "Who", list(reports.REPORTERS)),
            ("reporter_name", "Their name", ""),
            ("reason_text", "Reason", ""),
            ("message", "Message", ""),
        ])
        if values and cap._run(gui, lambda: reports.report_absence(
                values["student_id"], values["date_from"],
                date_to=values["date_to"] or None, channel=values["channel"],
                reported_by=values["reported_by"],
                reporter_name=values["reporter_name"] or None,
                reason_text=values["reason_text"] or None,
                message=values["message"] or None)) is not None:
            refresh()

    def self_cert() -> None:
        values = cap._form(gui, "Self-certify (on the learner's behalf)", [
            ("student_id", "Student ID", ""),
            ("date_from", "From (YYYY-MM-DD)", cap._today()),
            ("date_to", "To (blank = same day)", ""),
            ("reason_text", "Reason", "Illness"),
        ])
        if not values:
            return
        report = cap._run(gui, lambda: reports.self_certify(
            values["student_id"], values["date_from"],
            date_to=values["date_to"] or None,
            reason_text=values["reason_text"] or None,
            channel=reports.IN_PERSON))
        if report is not None:
            status = cap._run(gui, lambda: reports.self_cert_status(
                report.student_id))
            messagebox.showinfo("Self-certified",
                                f"Coded {reports.SELF_CERT_CODE}. "
                                + (status.label if status else ""),
                                parent=gui.root)
            refresh()

    def accept() -> None:
        rid = cap._selected_id(tree, gui.root)
        if rid is None:
            return
        values = cap._form(gui, f"Accept report #{rid}", [
            ("code", "Code", [reports.DEFAULT_ACCEPT_CODE,
                              *[c for c in codes.CODES
                                if c != reports.DEFAULT_ACCEPT_CODE]]),
            ("decided_by", "Decided by", cap._actor(gui) or ""),
            ("note", "Note", ""),
        ])
        if not values:
            return
        result = cap._run(gui, lambda: reports.accept(
            rid, code=values["code"], decided_by=values["decided_by"] or None,
            note=values["note"] or None))
        if result is not None:
            messagebox.showinfo("Accepted",
                                f"{result.marks_written} mark(s) written.",
                                parent=gui.root)
            refresh()

    def reject() -> None:
        rid = cap._selected_id(tree, gui.root)
        if rid is None:
            return
        values = cap._form(gui, f"Reject report #{rid}", [
            ("reason", "Reason (required)", ""),
            ("decided_by", "Decided by", cap._actor(gui) or ""),
        ])
        if values and cap._run(gui, lambda: reports.reject(
                rid, reason=values["reason"],
                decided_by=values["decided_by"] or None)) is not None:
            refresh()

    def channels() -> None:
        data = cap._run(gui, reports.channel_breakdown) or {}
        caps = cap._run(gui, reports.self_certification_report) or []
        text = "How reports arrive\n" + "\n".join(
            f"  {k:<14}{v:>5}" for k, v in data.items())
        if caps:
            text += "\n\nSelf-certification use this term\n" + "\n".join(
                f"  {s.student_id:<12}{s.label}" for s in caps)
        cap._show_text(gui, "Absence reports", text)

    for label, command in (("Refresh", refresh), ("Take a report…", take),
                           ("Self-certify…", self_cert),
                           ("Accept…", accept), ("Reject…", reject),
                           ("Channels & caps", channels)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 6))
    state_var.trace_add("write", lambda *_a: refresh())
    refresh()


def _build_all_absence(gui, parent: ttk.Frame) -> None:
    cap._hint(parent, "Leave, pastoral absence requests and absence "
              "reports are one store. This is every row of it — the list "
              "the pastoral team and the attendance office now share.")
    bar = cap._bar(parent)
    student_var = tk.StringVar()
    from_var = tk.StringVar(value=cap._days_ago(30))
    to_var = tk.StringVar(value=cap._today())
    origin_var = tk.StringVar(value="All")
    cap._labelled_entry(bar, "Student ID:", student_var, 12)
    cap._labelled_entry(bar, "From:", from_var, 11)
    cap._labelled_entry(bar, "To:", to_var, 11)
    ttk.Label(bar, text="Source:").pack(side="left")
    ttk.Combobox(bar, textvariable=origin_var, state="readonly", width=10,
                 values=["All", *leave.ORIGINS]).pack(side="left",
                                                      padx=(4, 12))
    actions = cap._bar(parent)
    status = ttk.Label(parent, text="", foreground="#555")
    status.pack(anchor="w", pady=(0, 6))
    tree = cap._tree(parent, [
        ("id", "#", 50), ("source", "Source", 120), ("dates", "Dates", 170),
        ("student", "Learner", 170), ("kind", "Kind", 140),
        ("reason", "Reason", 160), ("state", "State", 90),
        ("code", "Code", 50), ("marks", "Marks", 60)])

    def refresh() -> None:
        data = cap._run(gui, lambda: leave.all_absence(
            student_id=student_var.get().strip() or None,
            date_from=from_var.get().strip() or None,
            date_to=to_var.get().strip() or None,
            origin=None if origin_var.get() == "All" else origin_var.get())
        ) or []
        cap._fill(tree, [
            (r.request_id, _ORIGIN_LABEL.get(r.origin, r.origin), r.span,
             r.student_name or r.student_id, r.kind, r.reason_text or "",
             r.state, r.code or "", r.marks_written) for r in data])
        counts = cap._run(gui, leave.origin_counts) or {}
        status.configure(text=f"{len(data)} row(s) shown.  Store: " + ", ".join(
            f"{_ORIGIN_LABEL.get(k, k)} {v}" for k, v in sorted(counts.items())))

    def migrate() -> None:
        result = cap._run(gui, leave.migrate_legacy_stores)
        if result is not None:
            messagebox.showinfo("Absence store", result.summary,
                                parent=gui.root)
            refresh()

    def delete() -> None:
        rid = cap._selected_id(tree, gui.root)
        if rid is None:
            return
        if not _yes(gui, "Delete",
                    f"Delete absence record #{rid}? Marks already written "
                    "to the register are not touched (cancel approved "
                    "leave instead to void them)."):
            return
        if cap._run(gui, lambda: leave.store_delete(rid)):
            refresh()

    for label, command in (("Refresh", refresh),
                           ("Check migration", migrate),
                           ("Delete…", delete)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 6))
    origin_var.trace_add("write", lambda *_a: refresh())
    refresh()


# ═══ Sign in / out of site ══════════════════════════════════════════

def build_signout_tab(gui, parent: ttk.Frame) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    off_page = ttk.Frame(nb, padding=8)
    late_page = ttk.Frame(nb, padding=8)
    log_page = ttk.Frame(nb, padding=8)
    nb.add(off_page, text="Off site now")
    nb.add(late_page, text="Late returns")
    nb.add(log_page, text="Day's log")
    requests_page = ttk.Frame(nb, padding=8)
    nb.add(requests_page, text="Requests")
    refresh_late = _build_late_returns(gui, late_page)
    refresh_log = _build_signout_log(gui, log_page)
    _build_off_site(gui, off_page, also=(refresh_late, refresh_log))
    _build_signout_requests(gui, requests_page)


def _build_signout_requests(gui, parent: ttk.Frame) -> None:
    cap._hint(parent, "Learners ask ahead from the student portal. Approving "
              "does not take anybody off site — when they leave, select the "
              "approved request and sign it out here; the approver is "
              "recorded as authorising it. A decline needs a reason, which "
              "the learner sees.")
    actions = cap._bar(parent)
    show = tk.StringVar(value="Waiting")
    ttk.Label(actions, text="Show:").pack(side="left")
    ttk.Combobox(actions, textvariable=show, state="readonly", width=16,
                 values=("Waiting", "Approved today", "All open")).pack(
        side="left", padx=(4, 12))
    tree = cap._tree(parent, [
        ("id", "#", 50), ("student_id", "Student", 90),
        ("student", "Name", 160), ("date", "Date", 95),
        ("leave", "Leaving", 65), ("back", "Back by", 65),
        ("reason", "Reason", 220), ("parent", "Parent aware", 95),
        ("state", "State", 85), ("by", "Decided by", 110)])

    def refresh() -> None:
        def load() -> list[signout_requests.SignOutRequest]:
            mode = show.get()
            if mode == "Approved today":
                return signout_requests.approved_for_today()
            if mode == "All open":
                return signout_requests.list_requests(open_only=True,
                                                      with_names=True)
            return signout_requests.pending()

        rows = cap._run(gui, load) or []
        cap._fill(tree, [
            (r.request_id, r.student_id, r.student_name or "", r.date,
             r.leave_time, r.expected_back or "—",
             r.reason + (f" ({r.detail})" if r.detail else ""),
             "yes" if r.parent_aware else "no", r.state, r.decided_by or "")
            for r in rows])

    def _selected() -> int | None:
        rid = cap._selected_value(tree, gui.root, column=0)
        return int(rid) if rid else None

    def _by() -> str | None:
        by = cap._actor(gui)
        if not by:
            values = cap._form(gui, "Who is deciding", [("by", "Your name", "")])
            by = (values or {}).get("by") or None
        return by

    def approve() -> None:
        rid = _selected()
        by = _by() if rid else None
        if rid and by:
            values = cap._form(gui, "Approve request", [("note", "Note (optional)", "")])
            if values is not None and cap._run(gui, lambda: signout_requests.approve(
                    rid, by=by, note=values["note"] or None)) is not None:
                refresh()

    def decline() -> None:
        rid = _selected()
        by = _by() if rid else None
        if rid and by:
            values = cap._form(gui, "Decline request",
                               [("note", "Why (the learner sees this)", "")])
            if values is not None and cap._run(gui, lambda: signout_requests.decline(
                    rid, by=by, note=values["note"])) is not None:
                refresh()

    def use() -> None:
        rid = _selected()
        by = _by() if rid else None
        if not (rid and by):
            return
        values = cap._form(gui, "Sign out approved request", [
            ("parent_permission", "Parent permission given", False),
            ("permission_from", "Permission from (name)", "")])
        if values is None:
            return
        trip = cap._run(gui, lambda: signout_requests.use_request(
            rid, recorded_by=by,
            parent_permission=bool(values["parent_permission"]),
            permission_from=values["permission_from"] or None))
        if trip is not None:
            messagebox.showinfo("Signed out", trip.label, parent=gui.root)
            refresh()

    def cancel() -> None:
        rid = _selected()
        by = _by() if rid else None
        if rid and by and _yes(gui, "Cancel request", f"Cancel request #{rid}?"):
            if cap._run(gui, lambda: signout_requests.cancel_request(
                    rid, by=by)) is not None:
                refresh()

    for label, command in (("Refresh", refresh), ("Approve…", approve),
                           ("Decline…", decline),
                           ("Sign out approved request…", use),
                           ("Cancel request", cancel)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 6))
    show.trace_add("write", lambda *_a: refresh())
    refresh()


def _sign_out_form(gui) -> dict[str, Any] | None:
    return cap._form(gui, "Sign out of site", [
        ("student_id", "Student ID", ""),
        ("reason", "Reason", list(signout.REASONS)),
        ("detail", "Detail (appointment / early leave / other)", ""),
        ("expected_back", "Expected back (HH:MM)", ""),
        ("parent_permission", "Parent permission given", False),
        ("permission_from", "Permission from (name)", ""),
        ("authorised_by", "Authorised by (staff, early leave)", ""),
        ("notes", "Notes", ""),
    ])


def _build_off_site(gui, parent: ttk.Frame,
                    also: tuple[Callable[[], None], ...] = ()) -> None:
    cap._hint(parent, "Signed out and not back — the list a fire marshal "
              "needs. A roll call does not expect these learners at the "
              "assembly point and counts them as Confirmed off site. "
              "Early leave without a parent's permission needs a member of "
              "staff named as authorising it.")
    actions = cap._bar(parent)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))
    tree = cap._tree(parent, [
        ("id", "#", 50), ("student_id", "Student", 90),
        ("student", "Name", 160), ("out", "Out", 60),
        ("reason", "Reason", 200), ("back", "Due back", 70),
        ("permission", "Parent permission", 130), ("state", "State", 110),
        ("overdue", "Overdue", 70)])

    def refresh() -> None:
        rows = cap._run(gui, signout.currently_off_site) or []
        cap._fill(tree, [
            (r.signout_id, r.student_id, r.student_name or "", r.out_time,
             r.reason + (f" ({r.detail})" if r.detail else ""),
             r.expected_back or ("—" if r.returning else "not returning"),
             (r.permission_from or "yes") if r.parent_permission else
             (f"no — auth. {r.authorised_by}" if r.authorised_by else "no"),
             r.state,
             f"{r.minutes_overdue()} min" if r.minutes_overdue() else "")
            for r in rows])
        counts = cap._run(gui, signout.day_summary) or {}
        summary.configure(text="Today: " + ", ".join(
            f"{k} {v}" for k, v in counts.items()) if counts else "")
        for fn in also:
            fn()

    def sign_out() -> None:
        values = _sign_out_form(gui)
        if not values:
            return
        trip = cap._run(gui, lambda: signout.sign_out(
            values["student_id"], values["reason"],
            detail=values["detail"] or None,
            expected_back=values["expected_back"] or None,
            parent_permission=bool(values["parent_permission"]),
            permission_from=values["permission_from"] or None,
            authorised_by=values["authorised_by"] or None,
            via="Desk", recorded_by=cap._actor(gui),
            notes=values["notes"] or None))
        if trip is not None:
            refresh()

    def sign_in() -> None:
        sid = cap._selected_value(tree, gui.root, column=1)
        if sid is None:
            return
        trip = cap._run(gui, lambda: signout.sign_in(sid, via="Desk"))
        if trip is not None:
            refresh()

    def sign_in_by_id() -> None:
        values = cap._form(gui, "Sign back in", [("student_id", "Student ID", "")])
        if values and cap._run(gui, lambda: signout.sign_in(
                values["student_id"], via="Desk")) is not None:
            refresh()

    for label, command in (("Refresh", refresh), ("Sign out…", sign_out),
                           ("Sign selected back in", sign_in),
                           ("Sign in by ID…", sign_in_by_id)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 6))
    refresh()


def _build_late_returns(gui, parent: ttk.Frame) -> Callable[[], None]:
    cap._hint(parent, f"Learners more than {signout.LATE_GRACE_MINUTES} "
              "minutes past the time they said they would be back. Raising "
              "an alert stamps the sign-out so the list shows who has been "
              "chased; a message home is queued only if you ask.")
    actions = cap._bar(parent)
    tree = cap._tree(parent, [
        ("id", "#", 50), ("student_id", "Student", 90),
        ("student", "Name", 160), ("out", "Out", 60),
        ("reason", "Reason", 180), ("back", "Due back", 70),
        ("overdue", "Overdue", 80), ("alert", "Alert raised", 140)])

    def refresh() -> None:
        rows = cap._run(gui, signout.late_returns) or []
        cap._fill(tree, [
            (r.signout_id, r.student_id, r.student_name or "", r.out_time,
             r.reason, r.expected_back, f"{r.minutes_overdue()} min",
             r.late_alert_at or "") for r in rows])

    def raise_alerts() -> None:
        notify = _yes(gui, "Late returns",
                      "Also queue a message home for each new alert?")
        result = cap._run(gui, lambda: signout.raise_late_alerts(
            raised_by=cap._actor(gui), notify_guardian=notify))
        if result is not None:
            messagebox.showinfo("Late returns", result.summary,
                                parent=gui.root)
            refresh()

    def sign_in() -> None:
        sid = cap._selected_value(tree, gui.root, column=1)
        if sid and cap._run(gui, lambda: signout.sign_in(
                sid, via="Desk")) is not None:
            refresh()

    for label, command in (("Refresh", refresh),
                           ("Raise alerts", raise_alerts),
                           ("Sign selected back in", sign_in)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 6))
    refresh()
    return refresh


def _build_signout_log(gui, parent: ttk.Frame) -> Callable[[], None]:
    bar = cap._bar(parent)
    date_var = tk.StringVar(value=cap._today())
    cap._labelled_entry(bar, "Date:", date_var, 11)
    perm_only = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Only without parent permission",
                    variable=perm_only).pack(side="left", padx=(0, 12))
    actions = cap._bar(parent)
    tree = cap._tree(parent, [
        ("id", "#", 50), ("student", "Learner", 170), ("out", "Out", 60),
        ("in", "In", 60), ("reason", "Reason", 200),
        ("permission", "Parent permission", 120), ("via", "Via", 90),
        ("state", "State", 110), ("alert", "Late alert", 120)])

    def refresh() -> None:
        def load() -> list[signout.SignOut]:
            rows = signout.list_signouts(date=date_var.get().strip() or None)
            return [r for r in rows if not perm_only.get()
                    or not r.parent_permission]

        rows = cap._run(gui, load) or []
        cap._fill(tree, [
            (r.signout_id, r.student_name or r.student_id, r.out_time,
             r.in_time or ("—" if r.returning else "left"),
             r.reason + (f" ({r.detail})" if r.detail else ""),
             "yes" if r.parent_permission else "no",
             r.signed_out_via or "", r.state, r.late_alert_at or "")
            for r in rows])

    ttk.Button(actions, text="Refresh", command=refresh).pack(side="left")
    refresh()
    return refresh
