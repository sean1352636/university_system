"""GUI tabs for safeguarding casework (referrals, plans, LADO, transfers).

Added to the Safeguarding window after its original tabs by
:func:`add_casework_tabs`:

* Referrals — the referral register with an overdue follow-up filter.
* Plans — CP / CIN / early help plans, meetings, reviews, step-down;
  overdue reviews highlighted.
* LADO — allegations against staff / volunteers (DSL / Principal).
* Transfers — files sent (transfer pack, receipt) and received.
* Chronology — a learner's whole file, Prevent included.
* Access Log — who opened which record.

:func:`open_lado_register` is the standalone screen for the Principal,
who has no safeguarding access but owns the LADO register with the DSL.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from typing import Any, Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.safeguarding import (
    safeguarding as sg,
)
from education_system.systems.sixth_form.domain.safeguarding import (
    safeguarding_casework as cw,
)
from education_system.systems.sixth_form.domain.safeguarding.safeguarding import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel

logger = logging.getLogger(__name__)

# Field spec: (key, label, kind, options). kind: entry / combo / text /
# check / readonly.
Field = tuple[str, str, str, Any]


def _today() -> str:
    return _date.today().isoformat()


def _form_dialog(gui, title: str, fields: list[Field],
                 initial: dict[str, Any] | None,
                 on_save: Callable[[dict[str, Any]], None],
                 *, note: str | None = None) -> None:
    """A small modal form. ``on_save`` raises ValidationError to refuse."""
    initial = initial or {}
    win = tk.Toplevel(gui.root)
    win.title(title)
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    if note:
        ttk.Label(frm, text=note, foreground="#a33", wraplength=560,
                  justify="left").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 6))
    getters: dict[str, Callable[[], Any]] = {}
    for i, (key, label, kind, options) in enumerate(fields, start=1):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="ne",
                                        padx=(0, 8), pady=2)
        val = initial.get(key)
        if kind == "text":
            w = tk.Text(frm, width=60, height=4)
            if val:
                w.insert("1.0", str(val))
            w.grid(row=i, column=1, sticky="w", pady=2)
            getters[key] = (lambda w=w: w.get("1.0", "end-1c").strip())
        elif kind == "check":
            var = tk.BooleanVar(value=bool(val))
            ttk.Checkbutton(frm, variable=var).grid(row=i, column=1,
                                                    sticky="w", pady=2)
            getters[key] = var.get
        elif kind == "combo":
            var = tk.StringVar(value=val if val is not None else "")
            ttk.Combobox(frm, textvariable=var, values=list(options),
                         state="readonly", width=44).grid(
                row=i, column=1, sticky="w", pady=2)
            getters[key] = (lambda v=var: v.get().strip())
        elif kind == "readonly":
            ttk.Label(frm, text=str(val or "—"), foreground="#555").grid(
                row=i, column=1, sticky="w", pady=2)
        else:
            var = tk.StringVar(value="" if val is None else str(val))
            ttk.Entry(frm, textvariable=var, width=46).grid(
                row=i, column=1, sticky="w", pady=2)
            getters[key] = (lambda v=var: v.get().strip())

    def save() -> None:
        payload = {k: g() for k, g in getters.items()}
        try:
            on_save(payload)
        except (ValidationError, sg.AccessDenied) as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("%s save crashed", title)
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()

    bar = ttk.Frame(frm)
    bar.grid(row=len(fields) + 2, column=0, columnspan=2, sticky="e",
             pady=(10, 0))
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=4)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def _table(parent, columns: list[tuple[str, str, int]], *,
           height: int = 14) -> ttk.Treeview:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=[c[0] for c in columns],
                        show="headings", height=height)
    for key, text, width in columns:
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    tree.tag_configure("overdue", foreground="#a33")
    tree.tag_configure("closed", foreground="#888")
    return tree


def _selected_id(tree: ttk.Treeview) -> int | None:
    sel = tree.selection()
    return int(sel[0]) if sel else None


def _students() -> tuple[list[str], dict[str, str]]:
    rows = student_data.list_students()
    labels = [f"{s.student_id} — {s.full_name}" for s in rows]
    return labels, dict(zip(labels, (s.student_id for s in rows)))


# ── Entry point ───────────────────────────────────────────────────

def add_casework_tabs(gui, nb: ttk.Notebook) -> None:
    builders = (
        ("Referrals", _build_referrals_tab),
        ("Plans", _build_plans_tab),
        ("LADO", _build_lado_tab),
        ("Transfers", _build_transfers_tab),
        ("Chronology", _build_chronology_tab),
        ("Access Log", _build_access_log_tab),
    )
    for label, builder in builders:
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text=label)
        try:
            builder(gui, tab)
        except sg.AccessDenied as e:
            ttk.Label(tab, text=str(e), foreground="#a33").pack(anchor="w")
        except Exception as e:
            logger.exception("Safeguarding %s tab failed", label)
            ttk.Label(tab, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
    # The DSL also owns the single central record.
    from education_system.systems.sixth_form.interfaces.gui.staff.staff_hr import (
        single_central_record_views as _scr_views,
    )
    _scr_views.SCRTab(nb)


# ── Referrals ─────────────────────────────────────────────────────

def referral_dialog(gui, *, concern=None, existing: cw.Referral | None = None,
                    on_saved: Callable[[], None]) -> None:
    concern_id = concern.concern_id if concern else existing.concern_id
    student_id = concern.student_id if concern else existing.student_id
    suggested = ", ".join(sg.suggested_agencies(student_id))
    age = sg.student_age(student_id)
    note = (f"Learner age {age}. Suggested agencies: {suggested}."
            if age is not None else None)
    fields: list[Field] = [
        ("concern", "Concern", "readonly", None),
        ("agency", "Agency *", "combo", cw.REFERRAL_AGENCIES),
        ("referral_date", "Referral date *", "entry", None),
        ("reference", "Reference", "entry", None),
        ("referred_by", "Referred by", "entry", None),
        ("reason", "Reason", "text", None),
        ("outcome", "Outcome", "combo", ("",) + cw.REFERRAL_OUTCOMES),
        ("outcome_date", "Outcome date", "entry", None),
        ("next_action", "Next action", "entry", None),
        ("follow_up_due", "Follow-up due", "entry", None),
    ]
    initial: dict[str, Any] = {"concern": f"#{concern_id} ({student_id})",
                               "referral_date": _today()}
    if existing:
        initial.update({k: getattr(existing, k) for k in (
            "agency", "referral_date", "reference", "referred_by", "reason",
            "outcome", "outcome_date", "next_action", "follow_up_due")})
    else:
        initial["agency"] = sg.suggested_agencies(student_id)[0]

    def save(p: dict[str, Any]) -> None:
        warning = sg.agency_warning(student_id, p.get("agency", ""),
                                    p.get("referral_date") or None)
        if warning and not messagebox.askyesno(
                "Check the agency", warning + "\n\nSave anyway?",
                parent=gui.root):
            raise ValidationError("Not saved — choose the right agency")
        if existing:
            cw.update_referral(existing.referral_id, p)
        else:
            cw.create_referral({**p, "concern_id": concern_id})
        on_saved()

    _form_dialog(gui, "Referral", fields, initial, save, note=note)


def _build_referrals_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    overdue_only = tk.BooleanVar(value=False)
    open_only = tk.BooleanVar(value=True)
    ttk.Checkbutton(bar, text="Open only", variable=open_only).pack(
        side="left")
    ttk.Checkbutton(bar, text="Overdue follow-ups only",
                    variable=overdue_only).pack(side="left", padx=8)
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    tree = _table(parent, [
        ("id", "#", 50), ("concern", "Concern", 70),
        ("student", "Learner", 100), ("agency", "Agency", 160),
        ("date", "Referred", 90), ("ref", "Reference", 110),
        ("outcome", "Outcome", 220), ("next", "Next action", 180),
        ("due", "Follow-up due", 100), ("status", "Status", 70)])

    def refresh() -> None:
        tree.delete(*tree.get_children())
        rows = (cw.overdue_referral_follow_ups() if overdue_only.get()
                else cw.list_referrals(open_only=open_only.get()))
        for r in rows:
            tag = ("overdue",) if r.follow_up_overdue() else \
                (("closed",) if not r.is_open else ())
            tree.insert("", "end", iid=str(r.referral_id), tags=tag, values=(
                r.referral_id, f"#{r.concern_id}", r.student_id, r.agency,
                r.referral_date, r.reference or "—", r.outcome or "—",
                r.next_action or "—", r.follow_up_due or "—", r.status))
        gui.status_var.set(f"Referrals: {len(rows)}")

    def _edit() -> None:
        rid = _selected_id(tree)
        if rid is None:
            return
        r = cw.get_referral(rid)
        if r:
            referral_dialog(gui, existing=r, on_saved=refresh)

    def _outcome() -> None:
        rid = _selected_id(tree)
        if rid is None:
            return
        _form_dialog(gui, "Referral outcome", [
            ("outcome", "Outcome *", "combo", cw.REFERRAL_OUTCOMES),
            ("outcome_date", "Outcome date", "entry", None),
            ("next_action", "Next action", "entry", None),
            ("follow_up_due", "Follow-up due", "entry", None),
        ], {"outcome_date": _today()}, lambda p: (
            cw.record_referral_outcome(rid, **p), refresh()))

    def _close() -> None:
        rid = _selected_id(tree)
        if rid is None:
            return
        reason = simpledialog.askstring("Close referral", "Reason:",
                                        parent=gui.root)
        if reason:
            try:
                cw.close_referral(rid, reason=reason)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=gui.root)
            refresh()

    def _new() -> None:
        cid = simpledialog.askinteger("New referral", "Concern #:",
                                      parent=gui.root)
        if not cid:
            return
        c = sg.get_concern(cid)
        if c is None:
            messagebox.showerror("Not found", f"No concern #{cid}",
                                 parent=gui.root)
            return
        referral_dialog(gui, concern=c, on_saved=refresh)

    for text, cmd in (("New referral", _new), ("Edit", _edit),
                      ("Record outcome", _outcome), ("Close", _close),
                      ("Refresh", refresh)):
        ttk.Button(actions, text=text, command=cmd).pack(side="left",
                                                         padx=(0, 6))
    ttk.Button(bar, text="Apply", command=refresh).pack(side="left", padx=8)
    tree.bind("<Double-1>", lambda _e: _edit())
    refresh()


# ── Plans ─────────────────────────────────────────────────────────

def _build_plans_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    active_only = tk.BooleanVar(value=True)
    overdue_only = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Active only", variable=active_only).pack(
        side="left")
    ttk.Checkbutton(bar, text="Reviews overdue only",
                    variable=overdue_only).pack(side="left", padx=8)
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    tree = _table(parent, [
        ("id", "#", 50), ("student", "Learner", 200),
        ("type", "Plan", 170), ("start", "Start", 90),
        ("lead", "Lead professional", 160), ("last", "Last review", 90),
        ("next", "Next review", 90), ("status", "Status", 100),
        ("end", "Ended", 90)], height=10)
    meetings = ttk.LabelFrame(parent, text="Meetings", padding=6)
    meetings.pack(fill="both", expand=False, pady=(6, 0))
    mtree = _table(meetings, [
        ("id", "#", 50), ("date", "Date", 90), ("type", "Type", 200),
        ("rep", "College rep", 140), ("summary", "Summary", 360),
        ("next", "Next", 90)], height=6)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        rows = (cw.overdue_plan_reviews() if overdue_only.get()
                else cw.list_plans(active_only=active_only.get()))
        for pl in rows:
            tag = ("overdue",) if pl.review_overdue() else \
                (("closed",) if not pl.is_active else ())
            tree.insert("", "end", iid=str(pl.plan_id), tags=tag, values=(
                pl.plan_id, f"{pl.student_id} {pl.student_name or ''}",
                pl.plan_type, pl.start_date, pl.lead_professional or "—",
                pl.last_review_date or "—", pl.next_review_date or "—",
                pl.status, pl.end_date or ""))
        mtree.delete(*mtree.get_children())

    def show_meetings(_e=None) -> None:
        pid = _selected_id(tree)
        mtree.delete(*mtree.get_children())
        if pid is None:
            return
        for m in cw.list_meetings(pid):
            mtree.insert("", "end", values=(
                m.meeting_id, m.meeting_date, m.meeting_type,
                m.college_rep or ("Yes" if m.college_attended else "—"),
                (m.summary or "").replace("\n", " ")[:120],
                m.next_meeting_date or ""))

    plan_fields: list[Field] = [
        ("plan_type", "Plan type *", "combo", cw.PLAN_TYPES),
        ("start_date", "Start date *", "entry", None),
        ("local_authority", "Local authority", "entry", None),
        ("lead_professional", "Lead professional", "entry", None),
        ("lead_agency", "Lead agency", "entry", None),
        ("college_contact", "College contact", "entry", None),
        ("next_review_date", "Next review (blank = default)", "entry", None),
        ("concern_id", "Linked concern #", "entry", None),
        ("notes", "Notes", "text", None),
    ]

    def _new() -> None:
        labels, by_label = _students()
        fields = [("student", "Learner *", "combo", labels)] + plan_fields
        _form_dialog(gui, "New plan", fields,
                     {"start_date": _today(),
                      "plan_type": cw.PLAN_TYPES[0]},
                     lambda p: (cw.create_plan({
                         **p, "student_id": by_label.get(p.pop("student"),
                                                         "")}), refresh()))

    def _edit() -> None:
        pid = _selected_id(tree)
        if pid is None:
            return
        pl = cw.get_plan(pid)
        fields = [f for f in plan_fields
                  if f[0] not in ("plan_type", "concern_id")]
        fields.insert(-1, ("last_review_date", "Last review", "entry", None))
        _form_dialog(gui, f"Edit plan #{pid}", fields,
                     {f[0]: getattr(pl, f[0], None) for f in fields},
                     lambda p: (cw.update_plan(pid, p), refresh()))

    def _meeting() -> None:
        pid = _selected_id(tree)
        if pid is None:
            return
        _form_dialog(gui, f"Meeting — plan #{pid}", [
            ("meeting_type", "Type *", "combo", cw.MEETING_TYPES),
            ("meeting_date", "Date *", "entry", None),
            ("attendees", "Attendees", "entry", None),
            ("college_attended", "College attended", "check", None),
            ("college_rep", "College representative", "entry", None),
            ("summary", "Summary", "text", None),
            ("actions", "Actions", "text", None),
            ("next_meeting_date", "Next meeting", "entry", None),
        ], {"meeting_date": _today(), "meeting_type": "Core Group",
            "college_attended": True},
            lambda p: (cw.add_meeting(pid, p), refresh()))

    def _review() -> None:
        pid = _selected_id(tree)
        if pid is None:
            return
        _form_dialog(gui, f"Record review — plan #{pid}", [
            ("review_date", "Review date *", "entry", None),
            ("next_review_date", "Next review (blank = default)", "entry",
             None),
            ("attendees", "Attendees", "entry", None),
            ("summary", "Summary", "text", None),
        ], {"review_date": _today()},
            lambda p: (cw.record_review(pid, **p), refresh()))

    def _step_down() -> None:
        pid = _selected_id(tree)
        if pid is None:
            return
        _form_dialog(gui, f"Step down — plan #{pid}", [
            ("to", "Step down to *", "combo", cw.STEP_DOWN_TARGETS),
            ("on", "Date *", "entry", None),
            ("reason", "Reason", "entry", None),
        ], {"on": _today()},
            lambda p: (cw.step_down_plan(pid, **p), refresh()))

    def _end() -> None:
        pid = _selected_id(tree)
        if pid is None:
            return
        _form_dialog(gui, f"End plan #{pid}", [
            ("reason", "Reason *", "combo", cw.PLAN_END_REASONS),
            ("on", "Date *", "entry", None),
        ], {"on": _today()}, lambda p: (cw.end_plan(pid, **p), refresh()))

    for text, cmd in (("New plan", _new), ("Edit", _edit),
                      ("Add meeting", _meeting), ("Record review", _review),
                      ("Step down", _step_down), ("End plan", _end),
                      ("Refresh", refresh)):
        ttk.Button(actions, text=text, command=cmd).pack(side="left",
                                                         padx=(0, 6))
    ttk.Button(bar, text="Apply", command=refresh).pack(side="left", padx=8)
    tree.bind("<<TreeviewSelect>>", show_meetings)
    refresh()


# ── LADO ──────────────────────────────────────────────────────────

_LADO_FIELDS: list[Field] = [
    ("staff_id", "Staff ID (if staff)", "entry", None),
    ("subject_name", "Name *", "entry", None),
    ("subject_role", "Role *", "combo", cw.LADO_SUBJECT_ROLES),
    ("allegation_date", "Allegation date *", "entry", None),
    ("allegation", "Allegation *", "text", None),
    ("reported_by", "Reported by", "entry", None),
    ("reported_to_lado_date", "Reported to LADO on", "entry", None),
    ("lado_reference", "LADO reference", "entry", None),
    ("lado_officer", "LADO officer", "entry", None),
    ("strategy_meeting_date", "Strategy meeting", "entry", None),
    ("police_involved", "Police involved", "check", None),
    ("suspended", "Suspended", "check", None),
    ("actions", "Actions", "text", None),
]


def _build_lado_tab(gui, parent: ttk.Frame) -> None:
    cw.require_lado_access(action="lado-open")
    ttk.Label(parent, foreground="#a33", wraplength=900, justify="left",
              text=("Allegations that an adult working with learners may "
                    "have harmed a child, committed an offence, or behaved in "
                    "a way that indicates they may pose a risk. Tell the LADO "
                    "within one working day. DSL / Principal only.")
              ).pack(anchor="w", pady=(0, 6))
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    open_only = tk.BooleanVar(value=True)
    ttk.Checkbutton(bar, text="Open only", variable=open_only).pack(
        side="left")
    tree = _table(parent, [
        ("id", "#", 50), ("name", "Name", 160), ("role", "Role", 120),
        ("date", "Date", 90), ("lado", "To LADO", 90),
        ("ref", "LADO ref", 100), ("outcome", "Outcome", 120),
        ("dbs", "DBS ref.", 70), ("tra", "TRA ref.", 70),
        ("status", "Status", 70)])

    def refresh() -> None:
        tree.delete(*tree.get_children())
        late = {a.allegation_id for a in cw.lado_not_reported()}
        for a in cw.list_allegations(open_only=open_only.get()):
            tag = ("overdue",) if a.allegation_id in late else \
                (("closed",) if not a.is_open else ())
            tree.insert("", "end", iid=str(a.allegation_id), tags=tag,
                        values=(a.allegation_id, a.subject_name,
                                a.subject_role, a.allegation_date,
                                a.reported_to_lado_date or "NOT YET",
                                a.lado_reference or "—", a.outcome or "—",
                                "Yes" if a.dbs_referral else "",
                                "Yes" if a.tra_referral else "", a.status))

    def _new() -> None:
        _form_dialog(gui, "New LADO allegation", _LADO_FIELDS,
                     {"allegation_date": _today(), "subject_role": "Other"},
                     lambda p: (cw.create_allegation(p), refresh()))

    def _edit() -> None:
        aid = _selected_id(tree)
        if aid is None:
            return
        a = cw.get_allegation(aid)
        _form_dialog(gui, f"LADO allegation #{aid}", _LADO_FIELDS,
                     {f[0]: getattr(a, f[0]) for f in _LADO_FIELDS},
                     lambda p: (cw.update_allegation(aid, p), refresh()))

    def _outcome() -> None:
        aid = _selected_id(tree)
        if aid is None:
            return
        _form_dialog(gui, f"LADO outcome #{aid}", [
            ("outcome", "Outcome *", "combo", cw.LADO_OUTCOMES),
            ("outcome_date", "Outcome date", "entry", None),
            ("dbs_referral", "Referred to DBS", "check", None),
            ("dbs_referral_date", "DBS referral date", "entry", None),
            ("tra_referral", "Referred to TRA", "check", None),
            ("tra_referral_date", "TRA referral date", "entry", None),
            ("actions", "Actions", "text", None),
        ], {"outcome_date": _today()},
            lambda p: (cw.record_lado_outcome(aid, **p), refresh()),
            note=("If the person was dismissed or would have been, the "
                  "college must refer to the DBS; teachers may also need a "
                  "TRA referral."))

    def _close() -> None:
        aid = _selected_id(tree)
        if aid is None:
            return
        reason = simpledialog.askstring("Close allegation", "Reason:",
                                        parent=gui.root)
        if reason:
            try:
                cw.close_allegation(aid, reason=reason)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=gui.root)
            refresh()

    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(6, 0))
    for text, cmd in (("New allegation", _new), ("Edit", _edit),
                      ("Record outcome", _outcome), ("Close", _close),
                      ("Refresh", refresh)):
        ttk.Button(actions, text=text, command=cmd).pack(side="left",
                                                         padx=(0, 6))
    ttk.Button(bar, text="Apply", command=refresh).pack(side="left", padx=8)
    tree.bind("<Double-1>", lambda _e: _edit())
    refresh()


def open_lado_register(gui) -> None:
    """Standalone LADO screen (top-level entry for the Principal / DSL)."""
    for w in gui.content_frame.winfo_children():
        w.destroy()
    frame = gui.content_frame
    ttk.Label(frame, text="LADO Allegations Register",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))
    try:
        _build_lado_tab(gui, frame)
    except sg.AccessDenied as e:
        ttk.Label(frame, text=str(e), foreground="#a33").pack(anchor="w")


# ── Transfers ─────────────────────────────────────────────────────

def _build_transfers_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    view = tk.StringVar(value="All")
    ttk.Combobox(bar, textvariable=view, state="readonly", width=34,
                 values=("All", "Out", "In", "Out — awaiting receipt",
                         "In — overdue")).pack(side="left")
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    tree = _table(parent, [
        ("id", "#", 50), ("dir", "Dir", 40), ("student", "Learner", 180),
        ("inst", "Institution", 180), ("due", "Due by", 90),
        ("sent", "Sent", 90), ("recv", "Received", 90),
        ("method", "Method", 180), ("receipt", "Receipt", 140),
        ("status", "Status", 110)])

    def refresh() -> None:
        tree.delete(*tree.get_children())
        v = view.get()
        if v == "Out — awaiting receipt":
            rows = cw.outgoing_awaiting_receipt()
        elif v == "In — overdue":
            rows = cw.incoming_overdue()
        else:
            rows = cw.list_transfers(direction=None if v == "All" else v)
        for t in rows:
            tree.insert("", "end", iid=str(t.transfer_id),
                        tags=(("overdue",) if t.overdue() else ()),
                        values=(t.transfer_id, t.direction,
                                f"{t.student_id} {t.student_name or ''}",
                                t.institution, t.due_by or "",
                                t.date_sent or "", t.date_received or "",
                                t.method or "",
                                (f"{t.receipt_confirmed_by} "
                                 f"{t.receipt_confirmed_on}"
                                 if t.receipt_confirmed else ""),
                                t.status))

    def _out() -> None:
        labels, by_label = _students()
        _form_dialog(gui, "Send safeguarding file", [
            ("student", "Learner *", "combo", labels),
            ("institution", "Receiving institution *", "entry", None),
            ("institution_contact", "Receiving DSL / contact", "entry", None),
            ("method", "Method *", "combo", cw.TRANSFER_METHODS),
            ("leaving_date", "Leaving / start date", "entry", None),
            ("date_sent", "Date sent (blank = not yet)", "entry", None),
            ("notes", "Notes", "text", None),
        ], {"leaving_date": _today(), "method": cw.TRANSFER_METHODS[0]},
            lambda p: _save_out(by_label.get(p.pop("student"), ""), p),
            note=("A transfer pack (full chronology) is generated. Send it "
                  "separately from the main file within 5 school days and "
                  "get confirmation of receipt."))

    def _save_out(sid: str, p: dict[str, Any]) -> None:
        if not sid:
            raise ValidationError("Pick the learner")
        t = cw.record_transfer_out(sid, **p)
        refresh()
        messagebox.showinfo("Transfer pack", f"Transfer pack written to:\n"
                            f"{t.file_path}", parent=gui.root)

    def _sent() -> None:
        tid = _selected_id(tree)
        if tid is None:
            return
        try:
            cw.mark_transfer_sent(tid)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=gui.root)
        refresh()

    def _receipt() -> None:
        tid = _selected_id(tree)
        if tid is None:
            return
        _form_dialog(gui, "Confirm receipt", [
            ("confirmed_by", "Confirmed by (receiving DSL) *", "entry", None),
            ("confirmed_on", "Confirmed on", "entry", None),
        ], {"confirmed_on": _today()},
            lambda p: (cw.confirm_receipt(tid, **p), refresh()))

    def _expect() -> None:
        labels, by_label = _students()
        _form_dialog(gui, "Expect file from previous setting", [
            ("student", "Learner *", "combo", labels),
            ("institution", "Previous institution *", "entry", None),
            ("institution_contact", "Contact", "entry", None),
            ("start_date", "Start date", "entry", None),
            ("notes", "Notes", "text", None),
        ], {"start_date": _today()}, lambda p: (cw.expect_incoming(
            by_label.get(p.pop("student"), ""), **p), refresh()))

    def _received() -> None:
        tid = _selected_id(tree)
        if tid is None:
            return
        _form_dialog(gui, "File received", [
            ("date_received", "Date received", "entry", None),
            ("method", "Method", "combo", ("",) + cw.TRANSFER_METHODS),
            ("file_ref", "Where it is kept (separate file ref)", "entry",
             None),
            ("notes", "Notes", "text", None),
        ], {"date_received": _today()},
            lambda p: (cw.record_received(tid, **{
                k: v for k, v in p.items() if v}), refresh()))

    def _pack() -> None:
        labels, by_label = _students()
        _form_dialog(gui, "Build transfer pack only", [
            ("student", "Learner *", "combo", labels),
        ], {}, lambda p: messagebox.showinfo(
            "Transfer pack", str(cw.build_transfer_pack(
                by_label.get(p["student"], ""))), parent=gui.root))

    for text, cmd in (("Send file…", _out), ("Mark sent", _sent),
                      ("Confirm receipt", _receipt),
                      ("Expect incoming…", _expect),
                      ("Record received", _received),
                      ("Build pack", _pack), ("Refresh", refresh)):
        ttk.Button(actions, text=text, command=cmd).pack(side="left",
                                                         padx=(0, 6))
    ttk.Button(bar, text="Apply", command=refresh).pack(side="left", padx=8)
    refresh()


# ── Chronology / access log ───────────────────────────────────────

def _fill_chronology(tree: ttk.Treeview, student_id: str) -> int:
    tree.delete(*tree.get_children())
    rows = cw.student_chronology(student_id)
    tree.tag_configure("retracted", foreground="#999")
    for i, e in enumerate(rows):
        tree.insert("", "end", iid=str(i),
                    tags=(("retracted",) if e.retracted else ()),
                    values=(e.date, e.kind, e.ref, e.title, e.by or "",
                            (e.detail or "").replace("\n", " · ")[:300]))
    return len(rows)


_CHRON_COLS = [("date", "Date", 90), ("kind", "Kind", 80),
               ("ref", "Ref", 90), ("title", "Entry", 320),
               ("by", "By", 130), ("detail", "Detail", 460)]


def _build_chronology_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    labels, by_label = _students()
    var = tk.StringVar()
    ttk.Label(bar, text="Learner:").pack(side="left")
    ttk.Combobox(bar, textvariable=var, values=labels, width=42,
                 state="readonly").pack(side="left", padx=4)
    sid_var = tk.StringVar()
    ttk.Label(bar, text="or ID (incl. leavers):").pack(side="left", padx=(8, 0))
    ttk.Entry(bar, textvariable=sid_var, width=12).pack(side="left", padx=4)
    tree = _table(parent, _CHRON_COLS)

    def show() -> None:
        sid = sid_var.get().strip() or by_label.get(var.get())
        if not sid:
            return
        n = _fill_chronology(tree, sid)
        gui.status_var.set(f"Chronology for {sid}: {n} entries")

    ttk.Button(bar, text="Show", command=show).pack(side="left", padx=4)
    ttk.Button(bar, text="Who viewed",
               command=lambda: who_viewed_window(
                   gui, student_id=sid_var.get().strip()
                   or by_label.get(var.get()))).pack(side="left")


def chronology_window(gui, student_id: str) -> None:
    win = make_toplevel(gui.root)
    win.title(f"Safeguarding chronology — {student_id}")
    window_sizing.fit(win, "1400x900", (1200, 800))
    frm = ttk.Frame(win, padding=8)
    frm.pack(fill="both", expand=True)
    tree = _table(frm, _CHRON_COLS, height=30)
    try:
        _fill_chronology(tree, student_id)
    except sg.AccessDenied as e:
        messagebox.showerror("Access denied", str(e), parent=win)
        win.destroy()


def _fill_access(tree: ttk.Treeview, rows: list[dict]) -> None:
    tree.delete(*tree.get_children())
    for r in rows:
        tree.insert("", "end", values=(
            r.get("at"), r.get("username"), r.get("action"),
            r.get("student_id") or "", r.get("record_ref") or "",
            "yes" if r.get("allowed") else "REFUSED"))


_ACCESS_COLS = [("at", "When", 150), ("user", "User", 140),
                ("action", "Action", 180), ("student", "Learner", 100),
                ("ref", "Record", 120), ("allowed", "Allowed", 80)]


def who_viewed_window(gui, *, concern_id: int | None = None,
                      student_id: str | None = None) -> None:
    try:
        rows = sg.who_viewed(concern_id=concern_id, student_id=student_id)
    except sg.AccessDenied as e:
        messagebox.showerror("Access denied", str(e), parent=gui.root)
        return
    win = tk.Toplevel(gui.root)
    what = f"concern #{concern_id}" if concern_id else (student_id or "all")
    win.title(f"Who viewed — {what}")
    win.transient(gui.root)
    frm = ttk.Frame(win, padding=8)
    frm.pack(fill="both", expand=True)
    tree = _table(frm, _ACCESS_COLS, height=20)
    _fill_access(tree, rows)


def _build_access_log_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    sid_var = tk.StringVar()
    cid_var = tk.StringVar()
    ttk.Label(bar, text="Learner ID:").pack(side="left")
    ttk.Entry(bar, textvariable=sid_var, width=12).pack(side="left", padx=4)
    ttk.Label(bar, text="Concern #:").pack(side="left", padx=(8, 0))
    ttk.Entry(bar, textvariable=cid_var, width=8).pack(side="left", padx=4)
    tree = _table(parent, _ACCESS_COLS)

    def refresh() -> None:
        cid = cid_var.get().strip()
        try:
            rows = sg.who_viewed(
                concern_id=int(cid) if cid.isdigit() else None,
                student_id=sid_var.get().strip() or None)
        except sg.AccessDenied as e:
            messagebox.showerror("Access denied", str(e), parent=gui.root)
            return
        _fill_access(tree, rows)
        gui.status_var.set(f"Access log: {len(rows)} entries")

    ttk.Button(bar, text="Show", command=refresh).pack(side="left", padx=4)
    refresh()
