"""GUI panels for Sixth Form Safeguarding.

Three tabs:

* Directory — filterable list of concerns (one row each). Sorted with
  Critical & open at the top so urgent items are visible immediately.
* Concern — full detail view: header + chronology of updates. Includes
  add-update / edit / delete actions.
* Summary — totals, breakdowns, and **red alerts** for high-risk-open,
  overdue, and upcoming follow-ups.

Further tabs (KCSIE gap build): Report a Concern (any staff), Unreviewed
Reports, Referrals, Plans, LADO, Transfers, Chronology and Access Log —
the casework tabs live in :mod:`safeguarding_casework_views`.

Access is enforced in the domain layer: staff without the safeguarding
capability only ever see the *Report a concern* screen. Concerns are
never deleted — the old Delete buttons now close a concern as
"Closed — Retained" with a reason.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from typing import Any, Callable
from education_system.systems.sixth_form.domain.safeguarding import safeguarding
from education_system.systems.sixth_form.domain.safeguarding import safeguarding as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.safeguarding.safeguarding import (
    ACCESS_LEVELS,
    AGENCIES,
    ARCHIVED_STATUS,
    CATEGORIES,
    LINK_ROLES,
    CONCERN_TYPES,
    Concern,
    DEFAULT_STATUS,
    OPEN_STATUSES,
    RISK_LEVELS,
    STATUSES,
    Update,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    ttk.Label(bar, text=text, font=("", 16, "bold")).pack(side="left")
    ttk.Label(
        bar,
        text="  Confidential — DSL team only. Every view is logged.",
        foreground="#a33",
    ).pack(side="left", padx=(8, 0))


def _risk_colour(level: str) -> str:
    return {"Low": "#2a8", "Medium": "#a82",
            "High": "#a33", "Critical": "#700"}.get(level, "#444")


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    if not data.can_read():
        # KCSIE: anyone can report, only the DSL team reads the record.
        open_report_concern(gui)
        return
    frame = _clear(gui)
    _heading(frame, "Safeguarding")

    nb = SidebarBook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    concern_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(concern_tab, text="Concern")
    nb.add(summary_tab, text="Summary")

    try:
        _build_directory_tab(gui, dir_tab)
        _build_concern_tab(gui, concern_tab)
        _build_summary_tab(gui, summary_tab)
    except data.AccessDenied as e:
        messagebox.showerror("Access denied", str(e), parent=gui.root)
        open_report_concern(gui)
        return

    # Casework tabs, added after the original three.
    from education_system.systems.sixth_form.interfaces.gui.safeguarding import (
        safeguarding_casework_views as _cw_views,
    )
    report_tab = ttk.Frame(nb, padding=8)
    nb.add(report_tab, text="Report a Concern")
    _build_report_form(gui, report_tab, embedded=True)
    unreviewed_tab = ttk.Frame(nb, padding=8)
    nb.add(unreviewed_tab, text="Unreviewed Reports")
    _build_unreviewed_tab(gui, unreviewed_tab)
    _cw_views.add_casework_tabs(gui, nb)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    risk_var = tk.StringVar()
    status_var = tk.StringVar()
    category_var = tk.StringVar()
    open_only_var = tk.BooleanVar(value=True)

    ttk.Label(filt, text="Student:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Risk:").pack(side="left")
    ttk.Combobox(filt, textvariable=risk_var,
                 values=["", *RISK_LEVELS], state="readonly", width=10
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *STATUSES], state="readonly", width=18
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Category:").pack(side="left")
    ttk.Combobox(filt, textvariable=category_var,
                 values=["", *CATEGORIES],
                 state="readonly", width=22
                 ).pack(side="left", padx=(4, 12))
    ttk.Checkbutton(filt, text="Open only",
                    variable=open_only_var).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(parent)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()
        try:
            rows = data.list_concerns_with_detail(
                student_id=sid_var.get().strip() or None,
                risk_level=risk_var.get().strip() or None,
                status=status_var.get().strip() or None,
                category=category_var.get().strip() or None,
                open_only=open_only_var.get(),
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_concerns failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("concern_id", "student", "name", "concern_date",
                "category", "risk", "status",
                "dsl", "ref", "follow_up", "updates")
        headings = {
            "concern_id":   ("#",         50),
            "student":      ("Student",  100),
            "name":         ("Name",     140),
            "concern_date": ("Date",     100),
            "category":     ("Category", 160),
            "risk":         ("Risk",      80),
            "status":       ("Status",   140),
            "dsl":          ("DSL?",      50),
            "ref":          ("Ref?",      50),
            "follow_up":    ("Follow-up",100),
            "updates":      ("Updates",   60),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                            show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        # Per-risk row tagging for visual priority.
        for level in RISK_LEVELS:
            tree.tag_configure(f"risk-{level}",
                                foreground=_risk_colour(level))

        for r in rows:
            c = r.concern
            tree.insert("", "end", iid=str(c.concern_id),
                         tags=(f"risk-{c.risk_level}",),
                         values=(
                c.concern_id, c.student_id,
                r.student_name + ("  [18+]" if c.adult_safeguarding else ""),
                c.concern_date, c.category, c.risk_level, c.status,
                "Yes" if c.dsl_notified else "No",
                "Yes" if c.referral_made else "No",
                c.follow_up_date or "—",
                r.update_count,
            ))
        summary.configure(text=f"{len(rows)} concern(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            cid = _selected()
            if cid is None:
                messagebox.showinfo("No selection",
                                    "Pick a concern first.",
                                    parent=gui.root)
            return cid

        def _open() -> None:
            cid = _require()
            if cid is None:
                return
            open_concern(gui, concern_id=cid)

        def _delete() -> None:
            # Concerns are never deleted (KCSIE retention): close as retained.
            cid = _require()
            if cid is None:
                return
            c = data.get_concern(cid)
            if c is None:
                return
            if _close_retained(gui, c):
                refresh()

        ttk.Button(actions_holder, text="Open",
                   command=_open).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Close (retain)",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_concern(gui, concern_id=None)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _open())
        gui.status_var.set(f"Safeguarding concerns: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), risk_var.set(""),
                                status_var.set(""), category_var.set(""),
                                open_only_var.set(True), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Concern tab ────────────────────────────────────────────────────

def _build_concern_tab(gui, parent: ttk.Frame) -> None:
    rows = data.list_concerns(open_only=True)
    if rows:
        _render_concern(gui, parent, rows[0].concern_id)
    else:
        ttk.Label(
            parent,
            text=("No open safeguarding concerns. Use Directory → New "
                  "to record one."),
            foreground="#555",
        ).pack(anchor="w", pady=8)


def open_concern(gui, *, concern_id: int | None) -> None:
    frame = _clear(gui)
    _heading(frame,
             f"Safeguarding Concern #{concern_id}"
             if concern_id else "New Safeguarding Concern")
    if concern_id:
        _render_concern(gui, frame, concern_id)
    else:
        _render_form(gui, frame, existing=None)
    ttk.Button(frame, text="Back to Safeguarding",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_concern(gui, parent: ttk.Frame, concern_id: int) -> None:
    c = data.get_concern(concern_id)
    if c is None:
        ttk.Label(parent, text="No such concern.",
                  foreground="#a33").pack(anchor="w")
        return

    # Action row at top so it's always visible while scrolling.
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 8))
    ttk.Button(actions, text="Edit concern",
               command=lambda: _open_form(gui, existing=c)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Add chronology entry",
               command=lambda: _add_update_dialog(
                   gui, c.concern_id,
                   on_saved=lambda: open_concern(gui, concern_id=c.concern_id))
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Close concern (retain)",
               command=lambda: _delete_concern_from_view(gui, c)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Link student",
               command=lambda: _link_student_dialog(gui, c)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Link Prevent concern",
               command=lambda: _link_prevent_dialog(gui, c)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Attachments",
               command=lambda: _attachments_dialog(gui, c)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Record referral",
               command=lambda: _record_referral(gui, c)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Learner chronology",
               command=lambda: _chronology_window(gui, c.student_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Who viewed this",
               command=lambda: _who_viewed_window(gui, concern_id=c.concern_id)
               ).pack(side="left", padx=(0, 6))
    if not c.dsl_notified:
        ttk.Button(actions, text="Acknowledge report",
                   command=lambda: (_acknowledge(gui, c.concern_id))
                   ).pack(side="left", padx=(0, 6))

    # Header summary
    head = ttk.Frame(parent)
    head.pack(anchor="w", fill="x", pady=(0, 8))

    def field(idx: int, label: str, value: str,
              foreground: str | None = None) -> None:
        ttk.Label(head, text=label + ":", foreground="#555",
                  width=18, anchor="e").grid(row=idx, column=0,
                                              sticky="e", pady=2, padx=(0, 8))
        ttk.Label(head, text=value or "—",
                  foreground=foreground or "#000",
                  wraplength=620, justify="left"
                  ).grid(row=idx, column=1, sticky="w", pady=2)

    student = student_data.get_student(c.student_id)
    age = c.age_at_concern
    field(0, "Student",
          f"{c.student_id} — "
          f"{student.full_name if student else (c.student_name or '(left)')}"
          + (f"  ·  age {age} at concern" if age is not None else "")
          + ("  ·  ADULT SAFEGUARDING (Care Act 2014)"
             if c.adult_safeguarding else ""),
          foreground=("#a33" if c.adult_safeguarding else None))
    field(1, "Concern date", c.concern_date)
    field(2, "Reported date", c.reported_date)
    field(3, "Type", c.concern_type)
    field(4, "Category", c.category)
    field(5, "Risk level", c.risk_level,
          foreground=_risk_colour(c.risk_level))
    field(6, "Status", c.status,
          foreground=("#a33" if c.status in OPEN_STATUSES else "#444"))
    field(7, "Reported by", c.reported_by)
    field(8, "DSL notified",
          ("Yes — " + (c.dsl_name or "")
           + (f" ({c.dsl_notified_at})" if c.dsl_notified_at else ""))
          if c.dsl_notified else "No")
    field(9, "Parents informed",
          ("Yes" + (f" ({c.parents_informed_at})"
                     if c.parents_informed_at else ""))
          if c.parents_informed else "No")
    field(10, "External agencies", c.external_agencies)
    field(11, "Referral made",
          ("Yes — " + (c.referral_ref or "—")
           + (f" ({c.referral_date})" if c.referral_date else ""))
          if c.referral_made else "No")
    field(12, "Follow-up date", c.follow_up_date)
    row_i = 17
    extra: list[tuple[str, str, str | None]] = [
        ("Suggested agencies", ", ".join(c.suggested_agencies), None),
    ]
    linked = data.linked_students(c.concern_id)
    if linked:
        extra.append(("Linked learners", "; ".join(
            f"{x.student_id} {x.student_name or ''} ({x.link_role})"
            for x in linked), None))
    prev = data.prevent_links(c.concern_id)
    if prev:
        extra.append(("Linked Prevent", "; ".join(
            f"#{pc.concern_id} {pc.concern_type} ({pc.status})"
            for pc in prev), None))
    if c.body_map_ref or c.body_map_notes:
        extra.append(("Body map", f"{c.body_map_ref or '—'}  "
                                  f"{c.body_map_notes or ''}", None))
    if c.access_level == "Restricted":
        extra.append(("Restricted notes", c.restricted_notes or "—", "#700"))
    if c.is_archived:
        extra.append(("Closed — retained",
                      f"{c.archived_reason or '—'} (by {c.archived_by or '—'}"
                      f", {c.archived_at or '—'})", "#444"))
    if c.description:
        ttk.Separator(head, orient="horizontal").grid(
            row=13, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(head, text="Description:", foreground="#555",
                  width=18, anchor="ne").grid(row=14, column=0, sticky="ne",
                                               padx=(0, 8))
        ttk.Label(head, text=c.description, wraplength=620,
                  justify="left").grid(row=14, column=1, sticky="w")
    if c.action_taken:
        ttk.Label(head, text="Action taken:", foreground="#555",
                  width=18, anchor="ne").grid(row=15, column=0, sticky="ne",
                                               padx=(0, 8), pady=(6, 0))
        ttk.Label(head, text=c.action_taken, wraplength=620,
                  justify="left").grid(row=15, column=1, sticky="w",
                                        pady=(6, 0))
    if c.notes:
        ttk.Label(head, text="Notes:", foreground="#555",
                  width=18, anchor="ne").grid(row=16, column=0, sticky="ne",
                                               padx=(0, 8), pady=(6, 0))
        ttk.Label(head, text=c.notes, wraplength=620,
                  justify="left").grid(row=16, column=1, sticky="w",
                                        pady=(6, 0))
    for label, value, colour in extra:
        field(row_i, label, value, foreground=colour)
        row_i += 1

    # Chronology
    updates = data.list_updates(c.concern_id)
    ch_frame = ttk.LabelFrame(parent,
                               text=f"Chronology ({len(updates)} entry/entries)",
                               padding=8)
    ch_frame.pack(fill="both", expand=True, pady=(8, 0))

    if not updates:
        ttk.Label(ch_frame,
                  text="(no chronology entries yet)",
                  foreground="#555").pack(anchor="w")
    else:
        cols = ("update_id", "update_date", "updated_by", "update_text")
        headings = {
            "update_id":   ("#",         50),
            "update_date": ("Date",     100),
            "updated_by":  ("By",       180),
            "update_text": ("Entry",    480),
        }
        tree = ttk.Treeview(ch_frame, columns=cols,
                            show="headings", height=8)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(ch_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        tree.tag_configure("retracted", foreground="#999")
        for u in updates:
            text = u.update_text
            if u.retracted:
                text = (f"[RETRACTED by {u.retracted_by}: "
                        f"{u.retracted_reason}] {text}")
            tree.insert("", "end", iid=str(u.update_id),
                        tags=(("retracted",) if u.retracted else ()),
                        values=(
                u.update_id, u.update_date,
                u.updated_by or "—",
                text,
            ))

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        update_actions = ttk.Frame(parent)
        update_actions.pack(anchor="w", pady=(8, 0))

        def _edit_update() -> None:
            uid = _selected()
            if uid is None:
                messagebox.showinfo("No selection",
                                    "Pick a chronology entry first.",
                                    parent=gui.root)
                return
            u = data.get_update(uid)
            if u is None:
                return
            _add_update_dialog(
                gui, c.concern_id, existing=u,
                on_saved=lambda: open_concern(gui, concern_id=c.concern_id))

        def _delete_update() -> None:
            uid = _selected()
            if uid is None:
                messagebox.showinfo("No selection",
                                    "Pick a chronology entry first.",
                                    parent=gui.root)
                return
            # Entries are struck through with a reason, never deleted.
            reason = simpledialog.askstring(
                "Retract chronology entry",
                f"Why is entry #{uid} being retracted?\n"
                "(The text stays on the file, marked as retracted.)",
                parent=gui.root)
            if not reason or not reason.strip():
                return
            try:
                data.retract_update(uid, reason=reason)
            except Exception as e:
                logger.exception("retract_update crashed")
                messagebox.showerror("Error", f"Could not retract: {e}",
                                     parent=gui.root)
                return
            open_concern(gui, concern_id=c.concern_id)

        ttk.Button(update_actions, text="Edit entry",
                   command=_edit_update).pack(side="left", padx=(0, 6))
        ttk.Button(update_actions, text="Retract entry",
                   command=_delete_update).pack(side="left", padx=(0, 6))

    gui.status_var.set(f"Concern #{concern_id} loaded "
                        f"({len(updates)} chronology entry/entries)")


def _delete_concern_from_view(gui, c: Concern) -> None:
    if _close_retained(gui, c):
        open_directory(gui)


def _close_retained(gui, c: Concern) -> bool:
    """Ask for a reason and close the concern as retained (never deleted)."""
    if c.is_archived:
        messagebox.showinfo("Already closed",
                            f"Concern #{c.concern_id} is already "
                            f"{ARCHIVED_STATUS}.", parent=gui.root)
        return False
    reason = simpledialog.askstring(
        "Close concern (retain)",
        f"Close concern #{c.concern_id} ({c.category}, {c.risk_level})?\n\n"
        "Safeguarding records are kept, not deleted. Give the reason for "
        "closing:", parent=gui.root)
    if not reason or not reason.strip():
        return False
    try:
        data.archive_concern(c.concern_id, reason=reason)
    except Exception as e:
        logger.exception("archive_concern crashed")
        messagebox.showerror("Error", f"Could not close: {e}",
                             parent=gui.root)
        return False
    gui.status_var.set(f"Concern #{c.concern_id} closed — retained")
    return True


def _acknowledge(gui, concern_id: int) -> None:
    try:
        data.acknowledge_report(concern_id)
    except Exception as e:
        messagebox.showerror("Error", str(e), parent=gui.root)
        return
    open_concern(gui, concern_id=concern_id)


def _student_choices() -> tuple[list[str], dict[str, str]]:
    students = student_data.list_students()
    labels = [f"{s.student_id} — {s.full_name}" for s in students]
    return labels, {f"{s.student_id} — {s.full_name}": s.student_id
                    for s in students}


def _link_student_dialog(gui, c: Concern) -> None:
    win = tk.Toplevel(gui.root)
    win.title(f"Link learner — concern #{c.concern_id}")
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    labels, by_label = _student_choices()
    s_var = tk.StringVar()
    r_var = tk.StringVar(value=LINK_ROLES[0])
    ttk.Label(frm, text="Learner:").grid(row=0, column=0, sticky="e")
    ttk.Combobox(frm, textvariable=s_var, values=labels, width=42,
                 state="readonly").grid(row=0, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Role:").grid(row=1, column=0, sticky="e")
    ttk.Combobox(frm, textvariable=r_var, values=list(LINK_ROLES),
                 state="readonly", width=24).grid(row=1, column=1,
                                                  sticky="w", pady=2)

    current = ttk.Frame(frm)
    current.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
    for link in data.linked_students(c.concern_id):
        row = ttk.Frame(current)
        row.pack(anchor="w")
        ttk.Label(row, text=f"{link.student_id} {link.student_name or ''} "
                            f"({link.link_role})").pack(side="left")

        def _remove(link_id=link.link_id) -> None:
            reason = simpledialog.askstring(
                "Remove link", "Reason for removing this link:", parent=win)
            if not reason:
                return
            data.unlink_student(link_id, reason=reason)
            win.destroy()
            open_concern(gui, concern_id=c.concern_id)

        ttk.Button(row, text="Remove", command=_remove).pack(side="left",
                                                             padx=6)

    def save() -> None:
        sid = by_label.get(s_var.get())
        if not sid:
            messagebox.showerror("Cannot link", "Pick a learner.", parent=win)
            return
        try:
            data.link_student(c.concern_id, sid, link_role=r_var.get())
        except (ValidationError, data.AccessDenied) as e:
            messagebox.showerror("Cannot link", str(e), parent=win)
            return
        win.destroy()
        open_concern(gui, concern_id=c.concern_id)

    bar = ttk.Frame(frm)
    bar.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Link", command=save).pack(side="left", padx=4)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="left")


def _link_prevent_dialog(gui, c: Concern) -> None:
    from education_system.systems.sixth_form.domain.safeguarding.prevent_duty import (
        prevent_duty as _pd,
    )
    try:
        rows = _pd.list_concerns(student_id=c.student_id)
    except Exception as e:
        messagebox.showerror("Prevent", str(e), parent=gui.root)
        return
    if not rows:
        messagebox.showinfo(
            "Prevent", "This learner has no Prevent concerns to link. "
            "Record one under Prevent Duty first.", parent=gui.root)
        return
    options = [f"#{p.concern_id} {p.report_date} {p.concern_type} "
               f"({p.status})" for p in rows]
    win = tk.Toplevel(gui.root)
    win.title(f"Link Prevent concern — concern #{c.concern_id}")
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    var = tk.StringVar(value=options[0])
    ttk.Combobox(frm, textvariable=var, values=options, width=60,
                 state="readonly").pack(anchor="w")
    note_var = tk.StringVar()
    ttk.Label(frm, text="Note (optional):").pack(anchor="w", pady=(6, 0))
    ttk.Entry(frm, textvariable=note_var, width=60).pack(anchor="w")

    def save() -> None:
        pid = rows[options.index(var.get())].concern_id
        try:
            data.link_prevent_concern(c.concern_id, pid, note=note_var.get())
        except Exception as e:
            messagebox.showerror("Cannot link", str(e), parent=win)
            return
        win.destroy()
        open_concern(gui, concern_id=c.concern_id)

    ttk.Button(frm, text="Link", command=save).pack(anchor="e", pady=(8, 0))


def _attachments_dialog(gui, c: Concern) -> None:
    win = tk.Toplevel(gui.root)
    win.title(f"Attachments — concern #{c.concern_id}")
    win.transient(gui.root)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(0, 6))
    tree = ttk.Treeview(frm, columns=("id", "title", "category", "file",
                                      "by", "on"),
                        show="headings", height=8)
    for col, text, w in (("id", "#", 50), ("title", "Title", 220),
                         ("category", "Category", 100),
                         ("file", "File reference", 240),
                         ("by", "By", 120), ("on", "On", 90)):
        tree.heading(col, text=text)
        tree.column(col, width=w, anchor="w")

    def refresh() -> None:
        tree.delete(*tree.get_children())
        for a in data.list_attachments(c.concern_id):
            tree.insert("", "end", values=(a.attachment_id, a.title,
                                           a.category, a.file_ref,
                                           a.uploaded_by or "—",
                                           a.uploaded_on))

    def add() -> None:
        title = simpledialog.askstring("Attachment", "Title:", parent=win)
        if not title:
            return
        ref = simpledialog.askstring(
            "Attachment", "File reference (path or document id):",
            parent=win)
        if not ref:
            return
        try:
            data.add_attachment(c.concern_id, title=title, file_ref=ref)
        except Exception as e:
            messagebox.showerror("Cannot attach", str(e), parent=win)
            return
        refresh()

    def body_map() -> None:
        ref = simpledialog.askstring(
            "Body map", "Body map reference (file / attachment id):",
            initialvalue=c.body_map_ref or "", parent=win)
        if ref is None:
            return
        notes = simpledialog.askstring(
            "Body map", "What it shows (location, size, colour of marks):",
            initialvalue=c.body_map_notes or "", parent=win)
        if notes is None:
            return
        try:
            data.set_body_map(c.concern_id, body_map_ref=ref,
                              body_map_notes=notes)
        except Exception as e:
            messagebox.showerror("Body map", str(e), parent=win)
            return
        win.destroy()
        open_concern(gui, concern_id=c.concern_id)

    ttk.Button(bar, text="Add attachment", command=add).pack(side="left")
    ttk.Button(bar, text="Body map…", command=body_map).pack(side="left",
                                                             padx=6)
    if data.can_see_restricted():
        def restricted() -> None:
            notes = simpledialog.askstring(
                "Restricted notes (DSL only)", "Restricted notes:",
                initialvalue=c.restricted_notes or "", parent=win)
            if notes is None:
                return
            try:
                data.set_restricted_notes(c.concern_id, notes)
            except Exception as e:
                messagebox.showerror("Restricted notes", str(e), parent=win)
                return
            win.destroy()
            open_concern(gui, concern_id=c.concern_id)
        ttk.Button(bar, text="Restricted notes…",
                   command=restricted).pack(side="left")
    tree.pack(fill="both", expand=True)
    refresh()


def _record_referral(gui, c: Concern) -> None:
    from education_system.systems.sixth_form.interfaces.gui.safeguarding import (
        safeguarding_casework_views as _cw_views,
    )
    _cw_views.referral_dialog(gui, concern=c, on_saved=lambda: open_concern(
        gui, concern_id=c.concern_id))


def _chronology_window(gui, student_id: str) -> None:
    from education_system.systems.sixth_form.interfaces.gui.safeguarding import (
        safeguarding_casework_views as _cw_views,
    )
    _cw_views.chronology_window(gui, student_id)


def _who_viewed_window(gui, *, concern_id: int | None = None,
                       student_id: str | None = None) -> None:
    from education_system.systems.sixth_form.interfaces.gui.safeguarding import (
        safeguarding_casework_views as _cw_views,
    )
    _cw_views.who_viewed_window(gui, concern_id=concern_id,
                                student_id=student_id)


# ─── Report a concern (any member of staff) ────────────────────────

def open_report_concern(gui) -> None:
    """Top-level screen for staff without safeguarding access."""
    frame = _clear(gui)
    bar = ttk.Frame(frame)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    ttk.Label(bar, text="Report a Safeguarding Concern",
              font=("", 16, "bold")).pack(side="left")
    _build_report_form(gui, frame, embedded=False)


def _build_report_form(gui, parent: ttk.Frame, *, embedded: bool) -> None:
    ttk.Label(
        parent, wraplength=900, justify="left", foreground="#a33",
        text=("If a learner is in immediate danger call 999, then tell the "
              "DSL in person. Record what you saw or were told, in the "
              "learner's words where you can. Do not investigate or promise "
              "to keep a secret. You will not be able to open the record "
              "after filing it — it goes straight to the DSL team."),
    ).pack(anchor="w", pady=(0, 8))
    form = ttk.Frame(parent)
    form.pack(anchor="w", fill="x")
    labels, by_label = _student_choices()
    s_var = tk.StringVar()
    cat_var = tk.StringVar(value="Other")
    type_var = tk.StringVar(value="Disclosure")
    risk_var = tk.StringVar(value="Medium")
    date_var = tk.StringVar(value=_date.today().isoformat())
    age_lbl = ttk.Label(form, text="", foreground="#a33")
    desc = tk.Text(form, height=8, width=80)
    action = tk.Text(form, height=3, width=80)

    def on_student(_e=None) -> None:
        sid = by_label.get(s_var.get())
        if not sid:
            age_lbl.configure(text="")
            return
        age = data.student_age(sid)
        if age is not None and age >= data.ADULT_AGE:
            age_lbl.configure(text=f"Age {age}: adult safeguarding — the DSL "
                                   "will consider adult social care "
                                   "(Care Act 2014).")
        else:
            age_lbl.configure(text=f"Age {age}" if age is not None else "")

    def row(i: int, label: str, w: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(row=i, column=0, sticky="ne",
                                         padx=(0, 8), pady=2)
        w.grid(row=i, column=1, sticky="w", pady=2)

    cb = ttk.Combobox(form, textvariable=s_var, values=labels, width=42,
                      state="readonly")
    cb.bind("<<ComboboxSelected>>", on_student)
    row(0, "Learner *", cb)
    age_lbl.grid(row=1, column=1, sticky="w")
    row(2, "When did it happen? *",
        ttk.Entry(form, textvariable=date_var, width=14))
    row(3, "What kind of concern",
        ttk.Combobox(form, textvariable=cat_var, values=list(CATEGORIES),
                     state="readonly", width=34))
    row(4, "How you know",
        ttk.Combobox(form, textvariable=type_var,
                     values=list(CONCERN_TYPES), state="readonly", width=24))
    row(5, "How worried are you",
        ttk.Combobox(form, textvariable=risk_var, values=list(RISK_LEVELS),
                     state="readonly", width=14))
    row(6, "What you saw / were told *", desc)
    row(7, "Anything you did", action)

    def submit() -> None:
        sid = by_label.get(s_var.get())
        if not sid:
            messagebox.showerror("Cannot file", "Pick the learner.",
                                 parent=gui.root)
            return
        try:
            receipt = data.report_concern(
                sid, desc.get("1.0", "end-1c"), category=cat_var.get(),
                concern_type=type_var.get(), risk_level=risk_var.get(),
                concern_date=date_var.get(),
                action_taken=action.get("1.0", "end-1c"))
        except ValidationError as e:
            messagebox.showerror("Cannot file", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("report_concern crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        messagebox.showinfo("Concern filed", receipt.message,
                            parent=gui.root)
        desc.delete("1.0", "end")
        action.delete("1.0", "end")
        gui.status_var.set(f"Safeguarding concern #{receipt.concern_id} "
                           "passed to the DSL")
        refresh_mine()

    ttk.Button(parent, text="Pass to the DSL",
               command=submit).pack(anchor="w", pady=(8, 8))
    mine = ttk.LabelFrame(parent, text="Concerns I have filed", padding=6)
    mine.pack(fill="x", anchor="w")
    mine_lbl = ttk.Label(mine, text="", foreground="#555", justify="left")
    mine_lbl.pack(anchor="w")

    def refresh_mine() -> None:
        rows = data.my_reports()
        mine_lbl.configure(text="\n".join(
            f"#{r.concern_id}  {r.student_id}  filed {r.reported_at}"
            for r in rows[:10]) or "(none)")

    refresh_mine()


def _build_unreviewed_tab(gui, parent: ttk.Frame) -> None:
    ttk.Label(parent, text="Reports filed by staff that the DSL has not "
                           "yet acknowledged.", foreground="#555"
              ).pack(anchor="w", pady=(0, 6))
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    tree = ttk.Treeview(parent, columns=("id", "student", "date", "category",
                                         "risk", "by", "age"),
                        show="headings", height=14)
    for col, text, w in (("id", "#", 50), ("student", "Learner", 200),
                         ("date", "Date", 100), ("category", "Category", 200),
                         ("risk", "Risk", 80), ("by", "Reported by", 160),
                         ("age", "18+?", 50)):
        tree.heading(col, text=text)
        tree.column(col, width=w, anchor="w")

    def refresh() -> None:
        tree.delete(*tree.get_children())
        for c in data.list_unreviewed():
            tree.insert("", "end", iid=str(c.concern_id), values=(
                c.concern_id, f"{c.student_id} {c.student_name or ''}",
                c.concern_date, c.category, c.risk_level, c.reported_by,
                "Yes" if c.adult_safeguarding else ""))

    def _open() -> None:
        sel = tree.selection()
        if sel:
            open_concern(gui, concern_id=int(sel[0]))

    def _ack() -> None:
        sel = tree.selection()
        if not sel:
            return
        try:
            data.acknowledge_report(int(sel[0]))
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=gui.root)
        refresh()

    ttk.Button(bar, text="Open", command=_open).pack(side="left")
    ttk.Button(bar, text="Acknowledge", command=_ack).pack(side="left",
                                                          padx=6)
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _open())
    refresh()


# ─── Concern form ───────────────────────────────────────────────────

def _open_form(gui, *, existing: Concern | None) -> None:
    frame = _clear(gui)
    _heading(frame,
             f"Edit Safeguarding Concern #{existing.concern_id}"
             if existing else "New Safeguarding Concern")
    _render_form(gui, frame, existing=existing)
    ttk.Button(frame, text="Cancel",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_form(gui, parent: ttk.Frame, *,
                 existing: Concern | None) -> None:
    today = _date.today().isoformat()

    form = ttk.Frame(parent)
    form.pack(anchor="w", fill="x", pady=(0, 8))
    form.columnconfigure(1, weight=1, minsize=320)

    if existing:
        ttk.Label(form, text="Student:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=2)
        ttk.Label(form, text=existing.student_id,
                  foreground="#555").grid(
            row=0, column=1, sticky="w", pady=2)
        student_var = tk.StringVar(value=existing.student_id)
        student_by_label = {}
    else:
        students = student_data.list_students()
        student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
        student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                            for s in students}
        student_var = tk.StringVar(
            value=student_labels[0] if student_labels else "")
        ttk.Label(form, text="Student *:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=2)
        ttk.Combobox(form, textvariable=student_var,
                     values=student_labels,
                     state="readonly", width=42
                     ).grid(row=0, column=1, sticky="w", pady=2)

    concern_date_var = tk.StringVar(
        value=existing.concern_date if existing else today)
    reported_date_var = tk.StringVar(
        value=existing.reported_date if existing else today)
    type_var = tk.StringVar(
        value=existing.concern_type if existing else CONCERN_TYPES[0])
    category_var = tk.StringVar(
        value=existing.category if existing else CATEGORIES[0])
    risk_var = tk.StringVar(
        value=existing.risk_level if existing else "Medium")
    status_var = tk.StringVar(
        value=existing.status if existing else DEFAULT_STATUS)
    reported_by_var = tk.StringVar(
        value=existing.reported_by if existing else "")
    description_text = tk.Text(form, height=4, width=60)
    action_text = tk.Text(form, height=3, width=60)
    if existing:
        if existing.description:
            description_text.insert("1.0", existing.description)
        if existing.action_taken:
            action_text.insert("1.0", existing.action_taken)

    dsl_var = tk.BooleanVar(
        value=bool(existing.dsl_notified) if existing else False)
    dsl_name_var = tk.StringVar(
        value=(existing.dsl_name or "") if existing else "")
    dsl_when_var = tk.StringVar(
        value=(existing.dsl_notified_at or "") if existing else "")
    parents_var = tk.BooleanVar(
        value=bool(existing.parents_informed) if existing else False)
    parents_when_var = tk.StringVar(
        value=(existing.parents_informed_at or "") if existing else "")
    agencies_var = tk.StringVar(
        value=(existing.external_agencies or "") if existing else "")
    referral_var = tk.BooleanVar(
        value=bool(existing.referral_made) if existing else False)
    referral_date_var = tk.StringVar(
        value=(existing.referral_date or "") if existing else "")
    referral_ref_var = tk.StringVar(
        value=(existing.referral_ref or "") if existing else "")
    follow_up_var = tk.StringVar(
        value=(existing.follow_up_date or "") if existing else "")
    notes_text = tk.Text(form, height=3, width=60)
    if existing and existing.notes:
        notes_text.insert("1.0", existing.notes)
    body_ref_var = tk.StringVar(
        value=(existing.body_map_ref or "") if existing else "")
    body_notes_var = tk.StringVar(
        value=(existing.body_map_notes or "") if existing else "")
    restricted_ok = data.can_see_restricted()
    restricted_text = tk.Text(form, height=3, width=60)
    if existing and existing.restricted_notes and restricted_ok:
        restricted_text.insert("1.0", existing.restricted_notes)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=2)
        widget.grid(row=idx, column=1, sticky="w", pady=2)

    row(1, "Concern date *",
        ttk.Entry(form, textvariable=concern_date_var, width=14))
    row(2, "Reported date *",
        ttk.Entry(form, textvariable=reported_date_var, width=14))
    row(3, "Concern type *",
        ttk.Combobox(form, textvariable=type_var, values=list(CONCERN_TYPES),
                     state="readonly", width=24))
    row(4, "Category *",
        ttk.Combobox(form, textvariable=category_var,
                     values=list(CATEGORIES),
                     state="readonly", width=30))
    row(5, "Risk level *",
        ttk.Combobox(form, textvariable=risk_var, values=list(RISK_LEVELS),
                     state="readonly", width=14))
    row(6, "Status",
        ttk.Combobox(form, textvariable=status_var, values=list(STATUSES),
                     state="readonly", width=22))
    row(7, "Reported by *",
        ttk.Entry(form, textvariable=reported_by_var, width=30))
    ttk.Label(form, text="Description *").grid(
        row=8, column=0, sticky="ne", padx=(0, 8), pady=2)
    description_text.grid(row=8, column=1, sticky="w", pady=2)
    ttk.Label(form, text="Action taken").grid(
        row=9, column=0, sticky="ne", padx=(0, 8), pady=2)
    action_text.grid(row=9, column=1, sticky="w", pady=2)

    row(10, "DSL notified",
        ttk.Checkbutton(form, variable=dsl_var))
    row(11, "DSL name",
        ttk.Entry(form, textvariable=dsl_name_var, width=24))
    row(12, "DSL notified date",
        ttk.Entry(form, textvariable=dsl_when_var, width=14))
    row(13, "Parents informed",
        ttk.Checkbutton(form, variable=parents_var))
    row(14, "Parents informed date",
        ttk.Entry(form, textvariable=parents_when_var, width=14))
    row(15, "External agencies",
        ttk.Entry(form, textvariable=agencies_var, width=42))
    row(16, "Referral made",
        ttk.Checkbutton(form, variable=referral_var))
    row(17, "Referral date",
        ttk.Entry(form, textvariable=referral_date_var, width=14))
    row(18, "Referral reference",
        ttk.Entry(form, textvariable=referral_ref_var, width=20))
    row(19, "Follow-up date",
        ttk.Entry(form, textvariable=follow_up_var, width=14))
    ttk.Label(form, text="Notes").grid(
        row=20, column=0, sticky="ne", padx=(0, 8), pady=2)
    notes_text.grid(row=20, column=1, sticky="w", pady=2)
    row(21, "Body map reference",
        ttk.Entry(form, textvariable=body_ref_var, width=30))
    row(22, "Body map notes",
        ttk.Entry(form, textvariable=body_notes_var, width=60))
    if restricted_ok:
        ttk.Label(form, text="Restricted notes (DSL only)").grid(
            row=23, column=0, sticky="ne", padx=(0, 8), pady=2)
        restricted_text.grid(row=23, column=1, sticky="w", pady=2)
    agency_hint = ttk.Label(form, text="", foreground="#a33")
    agency_hint.grid(row=24, column=1, sticky="w")

    def _hint(_e=None) -> None:
        sid = existing.student_id if existing else \
            student_by_label.get(student_var.get())
        if not sid:
            return
        age = data.student_age(sid, concern_date_var.get() or None)
        if age is None:
            agency_hint.configure(text="")
            return
        agency_hint.configure(
            text=f"Age {age}: refer to "
                 f"{', '.join(data.suggested_agencies(sid))}"
                 + (" (adult — Care Act 2014)" if age >= data.ADULT_AGE
                    else ""))
    _hint()
    if not existing:
        for w in form.grid_slaves(row=0, column=1):
            w.bind("<<ComboboxSelected>>", _hint)

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(12, 0))

    def save() -> None:
        if existing:
            sid = existing.student_id
        else:
            sid = student_by_label.get(student_var.get())
            if not sid:
                messagebox.showerror("Cannot save",
                                     "Pick a student.", parent=gui.root)
                return
        payload = {
            "student_id":          sid,
            "concern_date":        concern_date_var.get(),
            "reported_date":       reported_date_var.get(),
            "concern_type":        type_var.get(),
            "category":            category_var.get(),
            "risk_level":          risk_var.get(),
            "reported_by":         reported_by_var.get(),
            "description":         description_text.get("1.0", "end-1c").strip(),
            "action_taken":        action_text.get("1.0", "end-1c").strip(),
            "dsl_notified":        dsl_var.get(),
            "dsl_name":            dsl_name_var.get(),
            "dsl_notified_at":     dsl_when_var.get(),
            "parents_informed":    parents_var.get(),
            "parents_informed_at": parents_when_var.get(),
            "external_agencies":   agencies_var.get(),
            "referral_made":       referral_var.get(),
            "referral_date":       referral_date_var.get(),
            "referral_ref":        referral_ref_var.get(),
            "status":              status_var.get(),
            "follow_up_date":      follow_up_var.get(),
            "notes":               notes_text.get("1.0", "end-1c").strip(),
            "body_map_ref":        body_ref_var.get(),
            "body_map_notes":      body_notes_var.get(),
        }
        if restricted_ok:
            payload["restricted_notes"] = restricted_text.get(
                "1.0", "end-1c").strip()
        try:
            if existing:
                saved = data.update_concern(existing.concern_id, payload)
            else:
                saved = data.create_concern(payload)
        except (ValidationError, data.AccessDenied) as e:
            logger.warning("save safeguarding concern rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save safeguarding concern crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set(f"Saved concern #{saved.concern_id}")
        open_concern(gui, concern_id=saved.concern_id)

    ttk.Button(actions, text="Save", command=save).pack(side="left", padx=(0, 6))


# ─── Chronology dialog ──────────────────────────────────────────────

def _add_update_dialog(gui, concern_id: int, *,
                       existing: Update | None = None,
                       on_saved: Callable[[], None]) -> None:
    win = tk.Toplevel(gui.root)
    win.title(f"Chronology entry — concern #{concern_id}")
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    today = _date.today().isoformat()
    date_var = tk.StringVar(
        value=existing.update_date if existing else today)
    by_var = tk.StringVar(
        value=(existing.updated_by or "") if existing else "")
    text_widget = tk.Text(frm, width=60, height=8)
    if existing:
        text_widget.insert("1.0", existing.update_text)

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "Date *",
        ttk.Entry(frm, textvariable=date_var, width=14))
    row(1, "Updated by",
        ttk.Entry(frm, textvariable=by_var, width=28))
    ttk.Label(frm, text="Entry *:").grid(row=2, column=0, sticky="ne",
                                          padx=(0, 6), pady=2)
    text_widget.grid(row=2, column=1, sticky="w", pady=2)

    def save() -> None:
        payload = {
            "update_date": date_var.get(),
            "update_text": text_widget.get("1.0", "end-1c").strip(),
            "updated_by":  by_var.get(),
        }
        try:
            if existing:
                data.edit_update(existing.update_id, payload)
            else:
                data.add_update(concern_id, payload)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("save chronology update crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    upcoming_var = tk.StringVar(value="14")
    ttk.Label(bar, text="Follow-up window (days):").pack(side="left")
    ttk.Entry(bar, textvariable=upcoming_var, width=6
              ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            upcoming = int(upcoming_var.get())
        except ValueError:
            ttk.Label(holder, text="Window must be a number.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            summ = data.summary(upcoming_window_days=upcoming)
        except Exception as e:
            logger.exception("summary failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        ttk.Label(
            holder,
            text=f"Total concerns: {summ.total}  ·  "
                 f"Open: {summ.open_count}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(holder, text="Alerts:",
                  font=("", 11, "bold")).pack(anchor="w", pady=(8, 2))
        ttk.Label(
            holder,
            text=f"   High/Critical open : {summ.high_risk_open}",
            foreground=("#a33" if summ.high_risk_open else "#444"),
        ).pack(anchor="w")
        ttk.Label(
            holder,
            text=f"   Overdue follow-ups : {summ.overdue_follow_ups}",
            foreground=("#a33" if summ.overdue_follow_ups else "#444"),
        ).pack(anchor="w")
        ttk.Label(
            holder,
            text=f"   Upcoming ({upcoming}d)   : {summ.upcoming_follow_ups}",
            foreground=("#a33" if summ.upcoming_follow_ups else "#444"),
        ).pack(anchor="w")

        ttk.Label(
            holder,
            text=f"   Unreviewed reports : {summ.unreviewed_reports}",
            foreground=("#a33" if summ.unreviewed_reports else "#444"),
        ).pack(anchor="w")
        ttk.Label(
            holder,
            text=f"   Open — learner 18+ : {summ.adult_open}",
            foreground="#444",
        ).pack(anchor="w")
        ttk.Label(
            holder,
            text=f"   Closed — retained  : {summ.archived}",
            foreground="#444",
        ).pack(anchor="w")

        ttk.Label(holder, text="By risk:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for r in RISK_LEVELS:
            ttk.Label(holder, text=f"   {r:<10} : {summ.by_risk.get(r, 0)}",
                      foreground=_risk_colour(r)).pack(anchor="w")

        ttk.Label(holder, text="By status:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for s in STATUSES:
            ttk.Label(holder, text=f"   {s:<22} : {summ.by_status.get(s, 0)}",
                      foreground="#444").pack(anchor="w")

        if summ.by_category:
            ttk.Label(holder, text="Top categories:",
                      font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
            for cat, n in sorted(summ.by_category.items(),
                                  key=lambda kv: -kv[1])[:10]:
                ttk.Label(holder, text=f"   {cat[:30]:<30} : {n}",
                          foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="Notifications & referrals:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        ttk.Label(holder,
                  text=f"   DSL notified     : {summ.dsl_notified}",
                  foreground="#444").pack(anchor="w")
        ttk.Label(holder,
                  text=f"   Parents informed : {summ.parents_informed}",
                  foreground="#444").pack(anchor="w")
        ttk.Label(holder,
                  text=f"   Referrals made   : {summ.referrals}",
                  foreground="#444").pack(anchor="w")
        gui.status_var.set("Safeguarding summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    render()
