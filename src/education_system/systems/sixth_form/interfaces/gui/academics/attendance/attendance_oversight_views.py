"""GUI tabs for attendance oversight: safeguarding, cases and returns.

Six panels, mounted as extra tabs on the Attendance screen. Until now
each of these was only reachable from a CLI sub-menu:

* **CME alerts** — the safeguarding sweep, open alerts and children
  missing education referrals (:mod:`attendance_safeguarding`). Gated
  on the safeguarding capability and logged as sensitive access.
* **Escalation** — the intervention ladder, attendance contracts and
  the meetings log (:mod:`attendance_escalation`).
* **Thresholds** — every figure the rest of attendance branches on
  (:mod:`attendance_thresholds`).
* **Governor report** — the termly SLT/governor page and its trend
  (:mod:`attendance_governor_report`).
* **Census extract** — build and validate a census / ILR attendance
  return and export it (:mod:`attendance_census`).
* **Register nudges** — chasing registers nobody has taken
  (:mod:`attendance_nudges`).

Like :mod:`attendance_codes_views`, this module does not import
:mod:`attendance_views`; the import graph stays one-way.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date, timedelta as _timedelta
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_census as census,
    attendance_escalation as escalation,
    attendance_governor_report as governor,
    attendance_nudges as nudges,
    attendance_safeguarding as safeguarding,
    attendance_thresholds as thresholds,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel

logger = logging.getLogger(__name__)

_TERM_DAYS: int = 84


def _today() -> str:
    return _date.today().isoformat()


def _term_ago() -> str:
    return (_date.today() - _timedelta(days=_TERM_DAYS)).isoformat()


def _actor(gui) -> str | None:
    auth = getattr(gui, "auth", None)
    return ((getattr(auth, "current_user", None) or {}).get("username")
            if auth else None)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _note(parent, text: str) -> None:
    ttk.Label(parent, text=text, foreground="#666", wraplength=900,
              justify="left").pack(anchor="w", pady=(0, 8))


def _tree(parent, columns: list[tuple[str, str, int]],
          height: int = 12) -> ttk.Treeview:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=[c[0] for c in columns],
                        show="headings", height=height)
    for key, text, width in columns:
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


def _fill(tree: ttk.Treeview, rows: list[tuple]) -> None:
    tree.delete(*tree.get_children())
    for row in rows:
        tree.insert("", "end", values=[("" if v is None else v) for v in row])


def _selected_id(tree: ttk.Treeview, parent) -> int | None:
    selection = tree.selection()
    if not selection:
        messagebox.showinfo("Nothing selected", "Pick a row first.",
                            parent=parent)
        return None
    try:
        return int(tree.item(selection[0], "values")[0])
    except (ValueError, IndexError):
        return None


def _text_box(parent, height: int = 14) -> tk.Text:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    text = tk.Text(holder, height=height, wrap="word", font=("Courier", 10))
    scroll = ttk.Scrollbar(holder, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return text


def _set_text(widget: tk.Text, body: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", body)
    widget.configure(state="disabled")


def _form(gui, title: str,
          fields: list[tuple[str, str, str, tuple[str, ...] | None]],
          *, intro: str | None = None) -> dict[str, str] | None:
    """A small modal form. Each field is (key, label, default, choices).

    ``choices`` turns the field into a read-only combobox; a choices
    tuple containing a single ``"bool"`` entry gives a checkbox (the
    value comes back as ``"1"`` or ``""``). Returns stripped strings,
    or None when the user cancels.
    """
    win = tk.Toplevel(gui.root)
    win.title(title)
    win.transient(gui.root)
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    if intro:
        ttk.Label(body, text=intro, foreground="#666", wraplength=420,
                  justify="left").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 8))
    variables: dict[str, tk.Variable] = {}
    for i, (key, label, default, choices) in enumerate(fields, start=1):
        ttk.Label(body, text=label).grid(row=i, column=0, sticky="w",
                                         padx=(0, 8), pady=2)
        if choices == ("bool",):
            var: tk.Variable = tk.BooleanVar(value=bool(default))
            ttk.Checkbutton(body, variable=var).grid(row=i, column=1,
                                                     sticky="w", pady=2)
        elif choices:
            var = tk.StringVar(value=default)
            ttk.Combobox(body, textvariable=var, values=list(choices),
                         state="readonly", width=36).grid(
                row=i, column=1, sticky="w", pady=2)
        else:
            var = tk.StringVar(value=default)
            ttk.Entry(body, textvariable=var, width=40).grid(
                row=i, column=1, sticky="w", pady=2)
        variables[key] = var

    result: dict[str, dict[str, str] | None] = {"value": None}

    def ok() -> None:
        out: dict[str, str] = {}
        for key, var in variables.items():
            value = var.get()
            if isinstance(value, bool):
                out[key] = "1" if value else ""
            else:
                out[key] = str(value).strip()
        result["value"] = out
        win.destroy()

    buttons = ttk.Frame(body)
    buttons.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e",
                 pady=(10, 0))
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(
        side="right")
    ttk.Button(buttons, text="OK", command=ok).pack(side="right", padx=4)
    win.bind("<Return>", lambda _e: ok())
    win.bind("<Escape>", lambda _e: win.destroy())
    grab_when_viewable(win)
    win.wait_window()
    return result["value"]


def _safe(gui, action, *, success: str | None = None):
    """Run *action*; report ValidationError/OSError in a dialog."""
    try:
        out = action()
    except (ValidationError, ValueError, OSError) as e:
        messagebox.showerror("Not done", str(e), parent=gui.root)
        return None
    except Exception as e:  # noqa: BLE001 - a GUI must not die on one click
        logger.exception("Attendance oversight action failed")
        messagebox.showerror("Error", str(e), parent=gui.root)
        return None
    if success:
        messagebox.showinfo("Done", success, parent=gui.root)
    return out


# ── CME alerts (safeguarding) ───────────────────────────────────────

def _safeguarding_principal():
    """The signed-in principal and whether it may see safeguarding.

    Falls back to allowing when the access module is not available, so
    the tab behaves as it did before access control existed.
    """
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        p = access.current()
        return access, p, p.can(access.SAFEGUARDING)
    except (ImportError, AttributeError):
        return None, None, True


def build_safeguarding_tab(gui, parent: ttk.Frame) -> None:
    access, principal, allowed = _safeguarding_principal()
    if not allowed:
        if access is not None:
            access.log_sensitive_access(principal, "attendance_safeguarding",
                                        "view", allowed=False)
        ttk.Label(
            parent,
            text=("Safeguarding alerts and children missing education "
                  "referrals are restricted to staff with safeguarding "
                  "access. Ask the designated safeguarding lead or an "
                  "administrator if you need it."),
            foreground="#a33", wraplength=780, justify="left",
        ).pack(anchor="w")
        return
    if access is not None:
        access.log_sensitive_access(principal, "attendance_safeguarding",
                                    "view")

    def _log(action: str, *, student_id: str | None = None,
             ref: str | None = None) -> None:
        if access is not None:
            access.log_sensitive_access(principal, "attendance_safeguarding",
                                        action, student_id=student_id,
                                        record_ref=ref)

    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    alerts_tab = ttk.Frame(inner, padding=8)
    cme_tab = ttk.Frame(inner, padding=8)
    inner.add(alerts_tab, text="Alerts")
    inner.add(cme_tab, text="CME referrals")

    # ── Alerts ──
    _note(alerts_tab,
          "The sweep looks for consecutive unexplained absence with no "
          "contact — the pattern that matters — and raises flags for a "
          "person to read. Nothing is decided automatically.")
    bar = ttk.Frame(alerts_tab)
    bar.pack(anchor="w", fill="x", pady=(0, 6))
    state_var = tk.StringVar(value="Open (not closed)")
    ttk.Label(bar, text="Show:").pack(side="left")
    ttk.Combobox(bar, textvariable=state_var, state="readonly", width=18,
                 values=["Open (not closed)", *safeguarding.ALERT_STATES]
                 ).pack(side="left", padx=(4, 12))
    status = ttk.Label(alerts_tab, text="", foreground="#a33")

    actions = ttk.Frame(alerts_tab)
    actions.pack(anchor="w", fill="x", pady=(0, 6))
    status.pack(anchor="w", pady=(0, 4))
    tree = _tree(alerts_tab, [
        ("id", "#", 50), ("student", "Learner", 200), ("trigger", "Trigger", 220),
        ("level", "Level", 70), ("state", "State", 100), ("days", "Days", 50),
        ("raised", "Raised", 90), ("ack", "Acknowledged by", 120),
        ("detail", "Detail", 280)])

    def refresh_alerts() -> None:
        choice = state_var.get()
        rows = (safeguarding.open_alerts() if choice == "Open (not closed)"
                else safeguarding.list_alerts(state=choice, limit=500))
        _fill(tree, [(a.alert_id, a.student_name or a.student_id, a.trigger,
                      a.level, a.state, a.days, a.raised_on,
                      a.acknowledged_by, a.detail) for a in rows])
        unack = safeguarding.unacknowledged()
        status.configure(
            text=(f"{len(unack)} alert(s) nobody has looked at for over "
                  "24 hours." if unack else ""))

    def run_sweep() -> None:
        preview = _safe(gui, lambda: safeguarding.sweep(dry_run=True))
        if preview is None:
            return
        if not preview.raised:
            messagebox.showinfo(
                "Sweep", f"{preview.checked} learner(s) checked; nothing "
                "new to raise.", parent=gui.root)
            return
        if not messagebox.askyesno(
                "Sweep", f"{preview.checked} learner(s) checked; "
                f"{preview.raised} alert(s) would be raised.\n\nRaise them?",
                parent=gui.root):
            return
        result = _safe(gui, lambda: safeguarding.sweep(
            dry_run=False, raised_by=_actor(gui)))
        if result is not None:
            _log("sweep", ref=f"raised={result.raised}")
            messagebox.showinfo("Sweep", result.summary, parent=gui.root)
            refresh_alerts()

    def _alert_action(kind: str) -> None:
        alert_id = _selected_id(tree, gui.root)
        if alert_id is None:
            return
        fields = [("by", "Your name", _actor(gui) or "", None)]
        if kind == "action":
            fields.append(("note", "What was done", "", None))
        elif kind == "close":
            fields.append(("outcome", "Outcome", "", None))
        values = _form(gui, f"Alert #{alert_id}", fields)
        if values is None:
            return
        if kind == "ack":
            out = _safe(gui, lambda: safeguarding.acknowledge(
                alert_id, by=values["by"]))
        elif kind == "action":
            out = _safe(gui, lambda: safeguarding.mark_actioned(
                alert_id, by=values["by"], note=values["note"]))
        else:
            out = _safe(gui, lambda: safeguarding.close_alert(
                alert_id, by=values["by"], outcome=values["outcome"]))
        if out is not None:
            _log(f"alert_{kind}", student_id=out.student_id,
                 ref=f"alert:{alert_id}")
            refresh_alerts()

    def raise_manual() -> None:
        values = _form(gui, "Raise an alert", [
            ("student_id", "Student ID", "", None),
            ("trigger", "Trigger", safeguarding.TRIGGERS[0],
             safeguarding.TRIGGERS),
            ("level", "Level", safeguarding.MEDIUM, safeguarding.LEVELS),
            ("detail", "Detail", "", None),
            ("assigned_to", "Assign to", "", None),
        ])
        if values is None:
            return
        out = _safe(gui, lambda: safeguarding.raise_alert(
            values["student_id"], values["trigger"], level=values["level"],
            detail=values["detail"] or None, raised_by=_actor(gui),
            assigned_to=values["assigned_to"] or None))
        if out is not None:
            _log("alert_raise", student_id=out.student_id,
                 ref=f"alert:{out.alert_id}")
            refresh_alerts()

    ttk.Button(bar, text="Refresh", command=refresh_alerts).pack(side="left")
    ttk.Button(bar, text="Run sweep…", command=run_sweep).pack(
        side="left", padx=4)
    for label, kind in (("Acknowledge", "ack"),
                        ("Record what was done…", "action"),
                        ("Close…", "close")):
        ttk.Button(actions, text=label,
                   command=lambda k=kind: _alert_action(k)).pack(
            side="left", padx=(0, 4))
    ttk.Button(actions, text="Raise manually…", command=raise_manual).pack(
        side="left", padx=(12, 0))

    # ── CME referrals ──
    _note(cme_tab,
          "A referral to the local authority is a serious step and always "
          "a person's decision. The first list is who is at the referral "
          "threshold; the second is what is already on file.")
    ttk.Label(cme_tab, text="At the referral threshold",
              font=("", 11, "bold")).pack(anchor="w")
    cand_actions = ttk.Frame(cme_tab)
    cand_actions.pack(anchor="w", fill="x", pady=(2, 4))
    cand_holder = ttk.Frame(cme_tab)
    cand_holder.pack(fill="both", expand=True)
    cand_tree = _tree(cand_holder, [
        ("student", "Student ID", 110), ("name", "Name", 200),
        ("first", "First day", 100), ("last", "Last day", 100),
        ("days", "Days", 60), ("contacts", "Contact attempts", 120),
        ("made", "Contact made", 100)], height=6)

    ttk.Label(cme_tab, text="Referrals on file",
              font=("", 11, "bold")).pack(anchor="w", pady=(10, 0))
    ref_actions = ttk.Frame(cme_tab)
    ref_actions.pack(anchor="w", fill="x", pady=(2, 4))
    ref_holder = ttk.Frame(cme_tab)
    ref_holder.pack(fill="both", expand=True)
    ref_tree = _tree(ref_holder, [
        ("id", "#", 50), ("student", "Student ID", 110),
        ("state", "State", 130), ("days", "Days missing", 90),
        ("la", "Local authority", 140), ("reference", "Reference", 120),
        ("raised", "Raised", 90), ("submitted", "Submitted", 90),
        ("outcome", "Outcome", 200)], height=8)

    def refresh_cme() -> None:
        _fill(cand_tree, [(r.student_id, r.student_name, r.first_date,
                           r.last_date, r.days, r.contact_attempts,
                           "Yes" if r.contact_made else "No")
                          for r in safeguarding.referral_candidates()])
        _fill(ref_tree, [(r.referral_id, r.student_id, r.state,
                          r.days_missing, r.local_authority, r.reference,
                          r.raised_on, r.submitted_on, r.outcome)
                         for r in safeguarding.list_referrals(limit=500)])

    def raise_referral() -> None:
        selection = cand_tree.selection()
        default_sid = (cand_tree.item(selection[0], "values")[0]
                       if selection else "")
        values = _form(gui, "Raise a CME referral", [
            ("student_id", "Student ID", default_sid, None),
            ("raised_by", "Raised by", _actor(gui) or "", None),
            ("la", "Local authority", "", None),
            ("narrative", "Narrative", "", None),
        ], intro="This drafts the referral. Submitting it to the local "
                  "authority is a separate step.")
        if values is None:
            return
        out = _safe(gui, lambda: safeguarding.raise_cme_referral(
            values["student_id"], raised_by=values["raised_by"],
            local_authority=values["la"] or None,
            narrative=values["narrative"] or None))
        if out is not None:
            _log("cme_raise", student_id=out.student_id,
                 ref=f"cme:{out.referral_id}")
            messagebox.showinfo("Referral",
                                f"Referral #{out.referral_id} drafted.",
                                parent=gui.root)
            refresh_cme()

    def submit_referral() -> None:
        referral_id = _selected_id(ref_tree, gui.root)
        if referral_id is None:
            return
        values = _form(gui, f"Submit referral #{referral_id}", [
            ("reference", "LA reference", "", None),
            ("on", "Submitted on", _today(), None),
        ])
        if values is None:
            return
        out = _safe(gui, lambda: safeguarding.submit_referral(
            referral_id, reference=values["reference"] or None,
            on=values["on"] or None))
        if out is not None:
            _log("cme_submit", student_id=out.student_id,
                 ref=f"cme:{referral_id}")
            refresh_cme()

    def resolve_referral() -> None:
        referral_id = _selected_id(ref_tree, gui.root)
        if referral_id is None:
            return
        values = _form(gui, f"Resolve referral #{referral_id}",
                       [("outcome", "Outcome", "", None)])
        if values is None:
            return
        out = _safe(gui, lambda: safeguarding.resolve_referral(
            referral_id, outcome=values["outcome"]))
        if out is not None:
            _log("cme_resolve", student_id=out.student_id,
                 ref=f"cme:{referral_id}")
            refresh_cme()

    ttk.Button(cand_actions, text="Refresh", command=refresh_cme).pack(
        side="left")
    ttk.Button(cand_actions, text="Raise referral…",
               command=raise_referral).pack(side="left", padx=4)
    ttk.Button(ref_actions, text="Mark submitted…",
               command=submit_referral).pack(side="left")
    ttk.Button(ref_actions, text="Resolve…",
               command=resolve_referral).pack(side="left", padx=4)

    refresh_alerts()
    refresh_cme()


# ── Escalation ladder, contracts and meetings ───────────────────────

def build_escalation_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    cases_tab = ttk.Frame(inner, padding=8)
    contracts_tab = ttk.Frame(inner, padding=8)
    meetings_tab = ttk.Frame(inner, padding=8)
    inner.add(cases_tab, text="Cases")
    inner.add(contracts_tab, text="Contracts")
    inner.add(meetings_tab, text="Meetings")
    _build_cases(gui, cases_tab)
    _build_contracts(gui, contracts_tab)
    _build_meetings(gui, meetings_tab)


def _build_cases(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 6))
    filter_var = tk.StringVar(value="Open & monitoring")
    student_var = tk.StringVar()
    ttk.Label(bar, text="Show:").pack(side="left")
    ttk.Combobox(bar, textvariable=filter_var, state="readonly", width=20,
                 values=["Open & monitoring", "Overdue reviews",
                         *escalation.CASE_STATES, "All"]
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Student ID:").pack(side="left")
    ttk.Entry(bar, textvariable=student_var, width=12).pack(
        side="left", padx=(4, 12))

    counts_label = ttk.Label(parent, text="", foreground="#555")
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", fill="x", pady=(0, 6))
    counts_label.pack(anchor="w", pady=(0, 4))
    tree = _tree(parent, [
        ("id", "#", 50), ("student", "Learner", 200), ("stage", "Stage", 170),
        ("state", "State", 90), ("owner", "Owner", 120),
        ("opened", "Opened", 90), ("review", "Review by", 90),
        ("baseline", "Baseline", 70), ("summary", "Summary", 260)],
        height=10)
    ttk.Label(parent, text="Stage history (selected case)",
              font=("", 10, "bold")).pack(anchor="w", pady=(8, 0))
    history = _tree(parent, [
        ("on", "Entered", 90), ("stage", "Stage", 170),
        ("owner", "Owner", 120), ("by", "By", 120),
        ("review", "Review by", 90), ("note", "Note", 320)], height=5)

    def refresh() -> None:
        choice = filter_var.get()
        sid = student_var.get().strip() or None
        if choice == "Overdue reviews":
            rows = escalation.overdue_reviews()
            if sid:
                rows = [c for c in rows if c.student_id == sid]
        elif choice == "Open & monitoring":
            rows = escalation.list_cases(open_only=True, student_id=sid,
                                         limit=1000)
        elif choice == "All":
            rows = escalation.list_cases(student_id=sid, limit=1000)
        else:
            rows = escalation.list_cases(state=choice, student_id=sid,
                                         limit=1000)
        _fill(tree, [(c.case_id, c.student_name or c.student_id, c.stage,
                      c.state + (" (overdue)" if c.is_overdue() else ""),
                      c.owner, c.opened_on, c.review_on,
                      _pct(c.baseline_pct), c.summary) for c in rows])
        counts = escalation.stage_counts()
        counts_label.configure(text="Open cases by stage:  " + "   ".join(
            f"{stage}: {n}" for stage, n in counts.items()))
        history.delete(*history.get_children())

    def show_history(_event=None) -> None:
        selection = tree.selection()
        if not selection:
            return
        try:
            case_id = int(tree.item(selection[0], "values")[0])
        except (ValueError, IndexError):
            return
        _fill(history, [(e.entered_on, e.stage, e.owner, e.entered_by,
                         e.review_on, e.note)
                        for e in escalation.stage_history(case_id)])

    def open_case() -> None:
        sid = (student_var.get().strip() or "")
        first = _form(gui, "Open a case",
                      [("student_id", "Student ID", sid, None)])
        if first is None or not first["student_id"]:
            return
        suggested = _safe(gui, lambda: escalation.suggest_stage(
            first["student_id"]))
        values = _form(gui, "Open a case", [
            ("stage", "Stage", suggested or escalation.TUTOR_CONVERSATION,
             escalation.STAGES),
            ("owner", "Owner", "", None),
            ("opened_by", "Opened by", _actor(gui) or "", None),
            ("review_days", "Review after (days)",
             str(escalation.DEFAULT_REVIEW_DAYS), None),
            ("summary", "Summary", "", None),
        ], intro=(f"The ladder suggests: {suggested}" if suggested
                  else "The ladder suggests no action for this learner."))
        if values is None:
            return
        case = _safe(gui, lambda: escalation.open_case(
            first["student_id"], stage=values["stage"],
            owner=values["owner"] or None,
            opened_by=values["opened_by"] or None,
            review_days=int(values["review_days"] or
                            escalation.DEFAULT_REVIEW_DAYS),
            summary=values["summary"] or None))
        if case is not None:
            messagebox.showinfo(
                "Case opened", f"Case #{case.case_id}: {case.label}\n"
                f"Review by {case.review_on}.", parent=gui.root)
            refresh()

    def escalate() -> None:
        case_id = _selected_id(tree, gui.root)
        if case_id is None:
            return
        values = _form(gui, f"Escalate case #{case_id}", [
            ("owner", "New owner (optional)", "", None),
            ("actor", "Escalated by", _actor(gui) or "", None),
            ("note", "Note", "", None),
        ])
        if values is None:
            return
        case = _safe(gui, lambda: escalation.escalate(
            case_id, owner=values["owner"] or None,
            actor=values["actor"] or None, note=values["note"] or None))
        if case is not None:
            refresh()

    def set_stage() -> None:
        case_id = _selected_id(tree, gui.root)
        if case_id is None:
            return
        values = _form(gui, f"Move case #{case_id}", [
            ("stage", "Stage", escalation.TUTOR_CONVERSATION,
             escalation.STAGES),
            ("owner", "Owner (optional)", "", None),
            ("actor", "Changed by", _actor(gui) or "", None),
            ("note", "Note", "", None),
        ], intro="Moving down the ladder is a real event — use it when "
                 "attendance recovers.")
        if values is None:
            return
        if _safe(gui, lambda: escalation.set_stage(
                case_id, values["stage"], actor=values["actor"] or None,
                owner=values["owner"] or None,
                note=values["note"] or None)) is not None:
            refresh()

    def set_review() -> None:
        case_id = _selected_id(tree, gui.root)
        if case_id is None:
            return
        values = _form(gui, f"Review date for case #{case_id}",
                       [("review_on", "Review on (YYYY-MM-DD)", _today(),
                         None)])
        if values is None:
            return
        if _safe(gui, lambda: escalation.set_review(
                case_id, values["review_on"])) is not None:
            refresh()

    def close_case() -> None:
        case_id = _selected_id(tree, gui.root)
        if case_id is None:
            return
        values = _form(gui, f"Close case #{case_id}", [
            ("outcome", "Outcome", "", None),
            ("closed_by", "Closed by", _actor(gui) or "", None),
        ])
        if values is None:
            return
        if _safe(gui, lambda: escalation.close_case(
                case_id, outcome=values["outcome"],
                closed_by=values["closed_by"] or None)) is not None:
            refresh()

    def case_file() -> None:
        sid = student_var.get().strip()
        selection = tree.selection()
        if not sid and selection:
            case_id = int(tree.item(selection[0], "values")[0])
            case = escalation.get_case(case_id)
            sid = case.student_id if case else ""
        if not sid:
            messagebox.showinfo("Case file",
                                "Pick a case or type a student ID first.",
                                parent=gui.root)
            return
        file = _safe(gui, lambda: escalation.case_file(sid))
        if file is None:
            return
        lines = [f"{sid}: {_pct(file['current_percentage'])} "
                 f"(ladder suggests {file['suggested_stage'] or 'no action'})"]
        for case in file["cases"]:
            lines.append("")
            lines.append(f"Case #{case.case_id} — {case.stage} [{case.state}]")
            for entry in escalation.stage_history(case.case_id):
                lines.append(f"  {entry.entered_on}  {entry.stage} "
                             f"({entry.entered_by or '?'}) {entry.note or ''}")
        for contract in file["contracts"]:
            lines.append(f"Contract: {contract.label}")
        for meeting in file["meetings"][:20]:
            lines.append(f"Meeting {meeting.date} ({meeting.kind}): "
                         f"{meeting.outcome or meeting.notes or ''}")
        win = make_toplevel(gui.root)
        win.title(f"Case file — {sid}")
        win.geometry("760x520")
        box = _text_box(win)
        _set_text(box, "\n".join(lines))

    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    for label, command in (("Open a case…", open_case),
                           ("Escalate…", escalate),
                           ("Set stage…", set_stage),
                           ("Set review date…", set_review),
                           ("Close…", close_case),
                           ("Case file", case_file)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 4))
    tree.bind("<<TreeviewSelect>>", show_history)
    refresh()


def _build_contracts(gui, parent: ttk.Frame) -> None:
    _note(parent,
          "Record what the college will do as well as what the learner "
          "will — a contract without support is a warning with a "
          "signature line. Progress is measured from the contract's start.")
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 6))
    filter_var = tk.StringVar(value="All")
    ttk.Label(bar, text="Show:").pack(side="left")
    ttk.Combobox(bar, textvariable=filter_var, state="readonly", width=16,
                 values=["All", "Due review", *escalation.CONTRACT_STATES]
                 ).pack(side="left", padx=(4, 12))
    effect_label = ttk.Label(parent, text="", foreground="#555")
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", fill="x", pady=(0, 6))
    effect_label.pack(anchor="w", pady=(0, 4))
    tree = _tree(parent, [
        ("id", "#", 50), ("student", "Student ID", 100),
        ("target", "Target", 60), ("from", "From", 90), ("to", "To", 90),
        ("state", "State", 80), ("signed", "Signed (L/G/Staff)", 130),
        ("progress", "Progress", 280), ("track", "On track", 70),
        ("outcome", "Outcome", 70)])

    def refresh() -> None:
        choice = filter_var.get()
        if choice == "Due review":
            rows = escalation.contracts_due_review()
        elif choice == "All":
            rows = escalation.list_contracts(limit=1000)
        else:
            rows = escalation.list_contracts(state=choice, limit=1000)
        out = []
        for c in rows:
            progress_label, track = "", ""
            if c.is_active:
                try:
                    progress = escalation.contract_progress(c.contract_id)
                    progress_label = progress.label
                    track = {True: "Yes", False: "No"}.get(
                        progress.on_track, "—")
                except ValidationError:
                    pass
            signed = "/".join([
                "✓" if c.signed_by_student else "✗",
                "✓" if c.signed_by_guardian else "✗",
                c.signed_by_staff or "✗"])
            out.append((c.contract_id, c.student_id, f"{c.target_pct:g}%",
                        c.start_date, c.end_date, c.state, signed,
                        progress_label, track, _pct(c.outcome_pct)
                        if c.outcome_pct is not None else ""))
        _fill(tree, out)
        eff = escalation.contract_effectiveness()
        effect_label.configure(text=(
            f"Across {eff['contracts']} settled contract(s): "
            f"{eff.get('met_rate', 0)}% met, average change "
            f"{eff.get('average_change')} points, "
            f"{eff.get('improved', 0)} improved."
            if eff.get("contracts") else
            "No settled contracts yet to judge whether contracts work."))

    def create() -> None:
        values = _form(gui, "New attendance contract", [
            ("student_id", "Student ID", "", None),
            ("target", "Target attendance %", "90", None),
            ("start", "From (YYYY-MM-DD)", _today(), None),
            ("end", "To (YYYY-MM-DD)",
             (_date.today() + _timedelta(days=42)).isoformat(), None),
            ("review_on", "Review on (optional)", "", None),
            ("terms", "What the learner agrees to", "", None),
            ("support", "What the college will do", "", None),
            ("staff", "Staff signature", _actor(gui) or "", None),
        ])
        if values is None:
            return

        def _do():
            case = escalation.open_case_for(values["student_id"])
            return escalation.create_contract(
                values["student_id"], target_pct=float(values["target"]),
                start_date=values["start"], end_date=values["end"],
                case_id=case.case_id if case else None,
                terms=values["terms"] or None,
                support=values["support"] or None,
                review_on=values["review_on"] or None,
                signed_by_staff=values["staff"] or None)

        contract = _safe(gui, _do)
        if contract is not None:
            messagebox.showinfo("Contract", f"#{contract.contract_id}: "
                                f"{contract.label}", parent=gui.root)
            refresh()

    def sign() -> None:
        contract_id = _selected_id(tree, gui.root)
        if contract_id is None:
            return
        values = _form(gui, f"Sign contract #{contract_id}", [
            ("student", "Learner has signed", "", ("bool",)),
            ("guardian", "Parent/guardian has signed", "", ("bool",)),
            ("staff", "Staff signature", "", None),
        ])
        if values is None:
            return
        if _safe(gui, lambda: escalation.sign_contract(
                contract_id, by_student=bool(values["student"]),
                by_guardian=bool(values["guardian"]),
                by_staff=values["staff"] or None)) is not None:
            refresh()

    def close() -> None:
        contract_id = _selected_id(tree, gui.root)
        if contract_id is None:
            return
        values = _form(gui, f"Close contract #{contract_id}",
                       [("note", "Note (optional)", "", None)],
                       intro="The contract is settled as met or not met "
                             "from the actual figure.")
        if values is None:
            return
        out = _safe(gui, lambda: escalation.close_contract(
            contract_id, note=values["note"] or None))
        if out is not None:
            messagebox.showinfo("Contract", f"Closed as {out.state} "
                                f"({_pct(out.outcome_pct)}).",
                                parent=gui.root)
            refresh()

    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    for label, command in (("New contract…", create), ("Sign…", sign),
                           ("Close / settle…", close)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 4))
    refresh()


def _build_meetings(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 6))
    student_var = tk.StringVar()
    from_var = tk.StringVar(value=_term_ago())
    to_var = tk.StringVar(value=_today())
    ttk.Label(bar, text="Student ID:").pack(side="left")
    ttk.Entry(bar, textvariable=student_var, width=12).pack(
        side="left", padx=(4, 12))
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12).pack(
        side="left", padx=(4, 12))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12).pack(
        side="left", padx=(4, 12))
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", fill="x", pady=(0, 6))
    tree = _tree(parent, [
        ("id", "#", 50), ("date", "Date", 90), ("student", "Student ID", 100),
        ("kind", "Kind", 140), ("case", "Case", 50),
        ("attendees", "Attendees", 160), ("actions", "Actions", 200),
        ("outcome", "Outcome", 180), ("next", "Next review", 90),
        ("by", "Recorded by", 100)])

    def refresh() -> None:
        rows = _safe(gui, lambda: escalation.list_meetings(
            student_id=student_var.get().strip() or None,
            date_from=from_var.get().strip() or None,
            date_to=to_var.get().strip() or None, limit=1000))
        if rows is None:
            return
        _fill(tree, [(m.meeting_id, m.date, m.student_id, m.kind, m.case_id,
                      m.attendees, m.actions, m.outcome, m.next_review,
                      m.recorded_by) for m in rows])

    def log() -> None:
        values = _form(gui, "Log a meeting", [
            ("student_id", "Student ID", student_var.get().strip(), None),
            ("date", "Date", _today(), None),
            ("kind", "Kind", escalation.MEETING_KINDS[0],
             escalation.MEETING_KINDS),
            ("attendees", "Who was there", "", None),
            ("notes", "Notes", "", None),
            ("actions", "Actions agreed", "", None),
            ("outcome", "Outcome", "", None),
            ("next_review", "Next review (optional)", "", None),
            ("by", "Recorded by", _actor(gui) or "", None),
        ], intro="If the learner has an open case the meeting is filed "
                 "against it, and a next-review date moves the case review.")
        if values is None:
            return

        def _do():
            case = escalation.open_case_for(values["student_id"])
            return escalation.log_meeting(
                values["student_id"], values["date"], kind=values["kind"],
                case_id=case.case_id if case else None,
                attendees=values["attendees"] or None,
                notes=values["notes"] or None,
                actions=values["actions"] or None,
                outcome=values["outcome"] or None,
                next_review=values["next_review"] or None,
                recorded_by=values["by"] or None)

        if _safe(gui, _do) is not None:
            refresh()

    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(actions, text="Log a meeting…", command=log).pack(side="left")
    refresh()


# ── Thresholds ──────────────────────────────────────────────────────

def build_thresholds_tab(gui, parent: ttk.Frame) -> None:
    _note(parent,
          "Every figure the rest of attendance branches on — letter "
          "bands, persistent and severe absence, alert levels. College "
          "values are the fallback; year and cohort overrides win where "
          "they exist.")
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 6))
    scope_var = tk.StringVar(value="All scopes")
    ttk.Label(bar, text="Scope:").pack(side="left")
    ttk.Combobox(bar, textvariable=scope_var, state="readonly", width=14,
                 values=["All scopes", *thresholds.SCOPES]).pack(
        side="left", padx=(4, 12))
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", fill="x", pady=(0, 6))
    tree = _tree(parent, [
        ("id", "#", 50), ("key", "Key", 200), ("scope", "Scope", 80),
        ("scope_value", "Applies to", 90), ("value", "Value", 70),
        ("unit", "Unit", 50), ("direction", "Trips when", 80),
        ("description", "Description", 340), ("updated", "Updated", 140),
        ("by", "By", 90)])

    def refresh() -> None:
        scope = scope_var.get()
        rows = thresholds.list_thresholds(
            scope=None if scope == "All scopes" else scope)
        _fill(tree, [(t.threshold_id, t.key, t.scope, t.scope_value,
                      f"{t.value:g}", t.unit, t.direction, t.description,
                      t.updated_at, t.updated_by) for t in rows])

    def _selected() -> thresholds.Threshold | None:
        threshold_id = _selected_id(tree, gui.root)
        return (thresholds.get_threshold(threshold_id)
                if threshold_id is not None else None)

    def set_value(*, override: bool) -> None:
        current = None
        if tree.selection():
            current = _selected()
        values = _form(gui, "Set a threshold", [
            ("key", "Key", current.key if current else "", None),
            ("value", "Value", f"{current.value:g}" if current else "", None),
            ("scope", "Scope",
             (thresholds.SCOPE_YEAR if override else
              (current.scope if current else thresholds.SCOPE_COLLEGE)),
             thresholds.SCOPES),
            ("scope_value", "Year group / cohort (not for college)",
             (current.scope_value or "") if current and not override else "",
             None),
            ("direction", "Trips when (blank keeps)", "",
             ("", *thresholds.DIRECTIONS)),
            ("description", "Description (blank keeps)", "", None),
        ], intro=(thresholds.describe(current.key) if current else None))
        if values is None:
            return
        scope = values["scope"] or thresholds.SCOPE_COLLEGE
        out = _safe(gui, lambda: thresholds.set_threshold(
            values["key"], float(values["value"]), scope=scope,
            scope_value=(None if scope == thresholds.SCOPE_COLLEGE
                         else values["scope_value"]),
            direction=values["direction"] or None,
            description=values["description"] or None,
            actor=_actor(gui)))
        if out is not None:
            refresh()

    def clear() -> None:
        current = _selected()
        if current is None:
            return
        if current.scope == thresholds.SCOPE_COLLEGE:
            messagebox.showinfo(
                "Thresholds", "The college-wide setting is the fallback — "
                "it can be changed but not cleared.", parent=gui.root)
            return
        if not messagebox.askyesno(
                "Clear override", f"Drop the {current.scope} "
                f"{current.scope_value} override of {current.key}?",
                parent=gui.root):
            return
        if _safe(gui, lambda: thresholds.clear_override(
                current.key, scope=current.scope,
                scope_value=current.scope_value or "")) is not None:
            refresh()

    def reset() -> None:
        if not messagebox.askyesno(
                "Reset to shipped",
                "Put every shipped college-wide figure back to its shipped "
                "value? Custom keys and year/cohort overrides are left "
                "alone.", default="no", parent=gui.root):
            return
        n = _safe(gui, lambda: thresholds.reset_to_shipped(
            actor=_actor(gui)))
        if n is not None:
            messagebox.showinfo("Thresholds", f"{n} figure(s) reset.",
                                parent=gui.root)
            refresh()

    def seed() -> None:
        n = _safe(gui, thresholds.seed_defaults)
        if n is not None:
            messagebox.showinfo(
                "Thresholds", f"{n} shipped figure(s) added; any the "
                "college has edited were left alone.", parent=gui.root)
            refresh()

    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    for label, command in (
            ("Change selected…", lambda: set_value(override=False)),
            ("Add year/cohort override…", lambda: set_value(override=True)),
            ("Clear override", clear),
            ("Add missing defaults", seed),
            ("Reset to shipped…", reset)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 4))
    refresh()


# ── Governor report ─────────────────────────────────────────────────

def build_governor_tab(gui, parent: ttk.Frame) -> None:
    _note(parent,
          "The termly page for governors and SLT. Leave the dates blank "
          "for the current term.")
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 6))
    from_var = tk.StringVar()
    to_var = tk.StringVar()
    label_var = tk.StringVar()
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12).pack(
        side="left", padx=(4, 12))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12).pack(
        side="left", padx=(4, 12))
    ttk.Label(bar, text="Period label:").pack(side="left")
    ttk.Entry(bar, textvariable=label_var, width=18).pack(
        side="left", padx=(4, 12))

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", fill="x", pady=(0, 6))
    split = ttk.PanedWindow(parent, orient="vertical")
    split.pack(fill="both", expand=True)
    report_frame = ttk.Frame(split)
    trend_frame = ttk.Frame(split)
    split.add(report_frame, weight=3)
    split.add(trend_frame, weight=1)
    box = _text_box(report_frame, height=18)
    ttk.Label(trend_frame, text="Attendance over recent terms",
              font=("", 10, "bold")).pack(anchor="w", pady=(6, 2))
    trend = _tree(trend_frame, [("term", "Term", 260), ("pct", "Attendance", 90),
                                ("bar", "", 400)], height=6)

    state: dict[str, governor.GovernorReport | None] = {"report": None}

    def build() -> None:
        date_from = from_var.get().strip() or None
        date_to = to_var.get().strip() or None
        if date_from and not date_to:
            date_to = _today()
        report = _safe(gui, lambda: governor.build(
            date_from=date_from, date_to=date_to,
            period_label=label_var.get().strip() or None))
        if report is None:
            return
        state["report"] = report
        _set_text(box, governor.render_text(report))

    def refresh_trend() -> None:
        series = _safe(gui, governor.termly_series) or []
        _fill(trend, [(label, _pct(pct), "█" * int((pct or 0) / 4))
                      for label, pct in series])

    def save() -> None:
        report = state["report"]
        if report is None:
            messagebox.showinfo("Governor report", "Build the report first.",
                                parent=gui.root)
            return
        path = filedialog.asksaveasfilename(
            parent=gui.root, title="Save governor report",
            defaultextension=".md", initialfile="attendance_report.md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"),
                       ("JSON", "*.json")])
        if not path:
            return
        fmt = {"md": "markdown", "txt": "text", "json": "json"}.get(
            path.rsplit(".", 1)[-1].lower(), "text")
        saved = _safe(gui, lambda: governor.save(report, path, fmt=fmt))
        if saved:
            messagebox.showinfo("Governor report", f"Written to {saved}",
                                parent=gui.root)

    for label, command in (("Build report", build), ("Save…", save),
                           ("Refresh trend", refresh_trend)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 4))
    _set_text(box, "Press 'Build report' to assemble the page.")
    refresh_trend()


# ── Census extract ──────────────────────────────────────────────────

def build_census_tab(gui, parent: ttk.Frame) -> None:
    _note(parent,
          "Build a census or ILR attendance extract for a period and see "
          "what is wrong with it. Exporting writes a CSV — nothing is "
          "submitted from here; that is still a deliberate act by "
          "somebody who has read the findings.")
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 6))
    kind_var = tk.StringVar(value=census.CENSUS)
    from_var = tk.StringVar(value=_term_ago())
    to_var = tk.StringVar(value=_today())
    ttk.Label(bar, text="Return:").pack(side="left")
    ttk.Combobox(bar, textvariable=kind_var, values=list(census.RETURN_KINDS),
                 state="readonly", width=8).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12).pack(
        side="left", padx=(4, 12))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12).pack(
        side="left", padx=(4, 12))

    summary_label = ttk.Label(parent, text="", font=("", 10, "bold"))
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", fill="x", pady=(0, 6))
    summary_label.pack(anchor="w", pady=(0, 4))

    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    rows_tab = ttk.Frame(inner, padding=6)
    findings_tab = ttk.Frame(inner, padding=6)
    years_tab = ttk.Frame(inner, padding=6)
    mapping_tab = ttk.Frame(inner, padding=6)
    inner.add(rows_tab, text="Learner rows")
    inner.add(findings_tab, text="Findings")
    inner.add(years_tab, text="By year group")
    inner.add(mapping_tab, text="Code mapping & usage")

    rows_tree = _tree(rows_tab, [
        ("student", "Student ID", 100), ("name", "Name", 180),
        ("year", "Year", 50), ("possible", "Possible", 70),
        ("attended", "Attended", 70), ("pct", "Att %", 60),
        ("auth", "Auth", 50), ("unauth", "Unauth", 60),
        ("approved", "Approved", 70), ("unmarked", "Unmarked", 70),
        ("hours", "Hours att/poss", 110)])
    findings_tree = _tree(findings_tab, [
        ("severity", "Severity", 80), ("check", "Check", 200),
        ("student", "Student", 100), ("count", "Count", 60),
        ("detail", "Detail", 360), ("fix", "Fix", 260)])
    years_tree = _tree(years_tab, [("year", "Year group", 120),
                                   ("data", "Figures", 700)])

    map_tree = _tree(mapping_tab, [
        ("code", "Code", 70), ("label", "Meaning", 260),
        ("class", "National class", 200), ("attended", "Attended?", 80),
        ("possible", "Possible?", 80), ("usage", "Used in window", 110)])
    usage_note = ttk.Label(mapping_tab, text="", foreground="#a33")
    usage_note.pack(anchor="w", pady=(4, 0))

    state: dict[str, census.Return | None] = {"built": None}

    def build() -> None:
        kind = kind_var.get()
        builder = (census.ilr_extract if kind == census.ILR
                   else census.census_extract)
        built = _safe(gui, lambda: builder(
            date_from=from_var.get().strip(), date_to=to_var.get().strip()))
        if built is None:
            return
        state["built"] = built
        summary_label.configure(
            text=built.summary + ("" if built.submittable else
                                  "  — fix the errors, then build again."),
            foreground="#333" if built.submittable else "#a33")
        _fill(rows_tree, [(r.student_id, r.student_name, r.year_group,
                           r.sessions_possible, r.sessions_attended,
                           _pct(r.attendance_pct), r.authorised,
                           r.unauthorised, r.approved, r.unmarked,
                           f"{r.hours_attended:g}/{r.hours_possible:g}")
                          for r in built.rows])
        _fill(findings_tree, [(f.severity, f.check, f.student_id, f.count,
                               f.detail, f.fix) for f in built.findings])
        by_year = census.summary_by_year_group(built)
        _fill(years_tree, [(year, ", ".join(f"{k}: {v}" for k, v in
                                            figures.items()))
                           for year, figures in by_year.items()])
        refresh_mapping()

    def refresh_mapping() -> None:
        usage = _safe(gui, lambda: census.code_usage(
            date_from=from_var.get().strip(),
            date_to=to_var.get().strip())) or {}
        _fill(map_tree, [(m.code, m.label, m.national_class,
                          "Yes" if m.counts_as_attended else "No",
                          "Yes" if m.counts_as_possible else "No",
                          usage.get(m.code, 0)) for m in census.mapping()])
        usage_note.configure(text=(
            "No unauthorised absences coded at all in this window. A "
            "college with no truancy is usually coding everything as "
            "authorised." if usage and "O" not in usage else ""))

    def export() -> None:
        built = state["built"]
        if built is None:
            messagebox.showinfo("Census", "Build the return first.",
                                parent=gui.root)
            return
        if not built.submittable:
            messagebox.showerror(
                "Census", f"The return has {len(built.errors)} error(s). "
                "Fix them and build it again before exporting.",
                parent=gui.root)
            return
        path = filedialog.asksaveasfilename(
            parent=gui.root, title="Export return",
            defaultextension=".csv",
            initialfile=f"attendance_{built.kind}.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        saved = _safe(gui, lambda: census.save(built, path))
        if saved:
            messagebox.showinfo(
                "Census", f"Written to {saved}.\n\nNothing has been "
                "submitted.", parent=gui.root)

    def show_report() -> None:
        built = state["built"]
        if built is None:
            messagebox.showinfo("Census", "Build the return first.",
                                parent=gui.root)
            return
        win = make_toplevel(gui.root)
        win.title("Validation report")
        win.geometry("760x520")
        _set_text(_text_box(win), census.validation_report(built))

    for label, command in (("Build & validate", build),
                           ("Validation report", show_report),
                           ("Export CSV…", export),
                           ("Refresh code usage", refresh_mapping)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 4))
    refresh_mapping()


# ── Register nudges ─────────────────────────────────────────────────

def build_nudges_tab(gui, parent: ttk.Frame) -> None:
    _note(parent,
          "Chasing registers nobody has taken. The sweep raises nudges, "
          "escalates old ones (teacher → head of department → SLT) and "
          "clears any register that has since been taken. It is safe to "
          "run daily.")
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 6))
    state_var = tk.StringVar(value=nudges.OPEN)
    stage_var = tk.StringVar(value="All stages")
    ttk.Label(bar, text="State:").pack(side="left")
    ttk.Combobox(bar, textvariable=state_var, state="readonly", width=11,
                 values=list(nudges.NUDGE_STATES)).pack(
        side="left", padx=(4, 12))
    ttk.Label(bar, text="Stage:").pack(side="left")
    ttk.Combobox(bar, textvariable=stage_var, state="readonly", width=18,
                 values=["All stages", *nudges.STAGES]).pack(
        side="left", padx=(4, 12))
    counts_label = ttk.Label(parent, text="", foreground="#555")
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", fill="x", pady=(0, 6))
    counts_label.pack(anchor="w", pady=(0, 4))

    split = ttk.PanedWindow(parent, orient="vertical")
    split.pack(fill="both", expand=True)
    top = ttk.Frame(split)
    bottom = ttk.Frame(split)
    split.add(top, weight=3)
    split.add(bottom, weight=1)
    tree = _tree(top, [
        ("id", "#", 50), ("slot", "Slot", 60), ("date", "Date", 90),
        ("owner", "Owner", 150), ("stage", "Stage", 130),
        ("state", "State", 80), ("age", "Age (days)", 80),
        ("marked", "Marked", 80), ("sent", "Sent", 50),
        ("last", "Last sent", 140), ("note", "Note", 200)])
    ttk.Label(bottom, text="Who is missing registers",
              font=("", 10, "bold")).pack(anchor="w", pady=(6, 2))
    offenders = ttk.Frame(bottom)
    offenders.pack(fill="both", expand=True)
    people_frame = ttk.Frame(offenders)
    slots_frame = ttk.Frame(offenders)
    people_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
    slots_frame.pack(side="left", fill="both", expand=True)
    people = _tree(people_frame, [("owner", "Person", 260),
                                  ("n", "Missing", 80)], height=5)
    slots = _tree(slots_frame, [("slot", "Slot", 120),
                                ("n", "Missing", 80)], height=5)

    def refresh() -> None:
        stage = stage_var.get()
        rows = _safe(gui, lambda: nudges.list_nudges(
            state=state_var.get() or None,
            stage=None if stage == "All stages" else stage, limit=2000))
        if rows is None:
            return
        _fill(tree, [(n.nudge_id, n.slot_id, n.date, n.owner, n.stage,
                      n.state, n.age_days, f"{n.marked}/{n.expected}",
                      n.sent_count, n.last_sent_at, n.note) for n in rows])
        counts_label.configure(text="Open by stage:  " + "   ".join(
            f"{s}: {nudges.open_count(stage=s)}" for s in nudges.STAGES))
        _fill(people, nudges.worst_offenders())
        _fill(slots, [(f"#{slot_id}", n)
                      for slot_id, n in nudges.slot_offenders()])

    def sweep() -> None:
        notify = messagebox.askyesnocancel(
            "Chase sweep", "Run the chase sweep now.\n\nAlso queue digest "
            "messages to the people being chased?", parent=gui.root)
        if notify is None:
            return
        result = _safe(gui, lambda: nudges.sweep(notify=notify))
        if result is not None:
            messagebox.showinfo("Chase sweep", result.summary,
                                parent=gui.root)
            refresh()

    def resolve() -> None:
        nudge_id = _selected_id(tree, gui.root)
        if nudge_id is None:
            return
        values = _form(gui, f"Resolve nudge #{nudge_id}",
                       [("note", "Note (optional)", "", None)])
        if values is None:
            return
        if _safe(gui, lambda: nudges.resolve(
                nudge_id, note=values["note"] or None)) is not None:
            refresh()

    def dismiss() -> None:
        nudge_id = _selected_id(tree, gui.root)
        if nudge_id is None:
            return
        values = _form(gui, f"Dismiss nudge #{nudge_id}",
                       [("reason", "Why the lesson did not happen", "",
                         None)],
                       intro="Dismiss only when the lesson did not happen "
                             "and never will (cancelled, trip, dead slot).")
        if values is None:
            return
        if _safe(gui, lambda: nudges.dismiss(
                nudge_id, reason=values["reason"])) is not None:
            refresh()

    def chase_sheet() -> None:
        stage = stage_var.get()
        lines = _safe(gui, lambda: nudges.chase_sheet(
            stage=None if stage == "All stages" else stage))
        if lines is None:
            return
        win = make_toplevel(gui.root)
        win.title("Chase sheet")
        win.geometry("760x520")
        _set_text(_text_box(win), "\n".join(lines) or "Nothing outstanding.")

    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    for label, command in (("Run chase sweep…", sweep),
                           ("Resolve…", resolve),
                           ("Dismiss…", dismiss),
                           ("Chase sheet", chase_sheet)):
        ttk.Button(actions, text=label, command=command).pack(
            side="left", padx=(0, 4))
    refresh()
