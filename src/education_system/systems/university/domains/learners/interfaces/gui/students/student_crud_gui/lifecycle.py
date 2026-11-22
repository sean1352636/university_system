"""Student registration-status lifecycle dialog.

Surfaces ``domains.learners.domain.student_lifecycle`` in the records GUI.
Before this existed the lifecycle service had no caller at all: status was
set once at creation and never changed again from any interface, which is
how the live database ended up with both ``'Graduated'`` and
``'graduated'``.

Beyond the status transitions it also surfaces ``change_study()`` (mode,
campus, programme, repeat year) and ``reverse_change()``, which had no
caller either. Reversal is dual-control in the domain, so the dialog asks
for an approver distinct from the signed-in user.

The dialog deliberately owns no rules. Which transitions are legal comes
from ``student_lifecycle.available_actions()``, and the write itself goes
through ``change_status()`` so the history row, the downstream
reconciliation work and the enrolment event all still happen.
"""

import logging
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.tk_callback_filter import (
    install_clean_close as _install_clean_close,
)
from education_system.platform.delivery.gui.window_sizing import fit as _fit_window
from education_system.systems.university.domains.learners.domain import (
    student_lifecycle,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t

from .authorization import require_student_permission

logger = logging.getLogger(__name__)

# Actions that park a student with an intent to come back, so a return
# date is meaningful. change_status() stores it on the student row.
_RETURN_DATE_ACTIONS = frozenset({"interrupt", "defer", "suspend"})

_ACTION_LABELS = {
    "interrupt": "Interrupt studies",
    "withdraw": "Withdraw",
    "defer": "Defer",
    "suspend": "Suspend",
    "resume": "Resume studies",
    "reinstate": "Reinstate (undo withdrawal)",
    "complete": "Complete",
    "close": "Close record",
}

_DATE_HINT = "YYYY-MM-DD"

# change_study() accepts exactly one of these per call, and only while the
# student is Active, Interrupted or Suspended.
_STUDY_FIELDS = (
    ("programme_code", "Programme / course"),
    ("mode_of_study", "Mode of study"),
    ("campus_code", "Campus"),
    ("repeat_year", "Repeat year"),
)
_STUDY_ALLOWED_STATUSES = ("Active", "Interrupted", "Suspended")
_MODE_CHOICES = ("full-time", "part-time", "distance", "sandwich")


def _active_course_codes() -> list[str]:
    """Course codes from the catalogue.

    Read straight from the database rather than importing the academics
    slice: learners must not reach into another domain (the boundary
    ratchet in tests/unit/systems/university/domains/).
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT course_code FROM courses "
                "WHERE LOWER(COALESCE(status, '')) = 'active' "
                "AND course_code IS NOT NULL AND course_code <> '' "
                "ORDER BY course_code"
            ).fetchall()
        return [str(r[0]) for r in rows]
    except Exception:
        logger.debug("Could not load course catalogue", exc_info=True)
        return []


def _parse_date(value: str, field: str) -> str | None:
    """Return an ISO date string, or raise ValueError naming *field*."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError(f"{field} must be {_DATE_HINT}") from None


def _actor_id(owner) -> str:
    """Who to attribute the change to in the immutable history row.

    Username, not a numeric id: auth.db ids and student_records.db ids are
    different spaces for the same person, so a bare integer here would be
    ambiguous when the history is read back.
    """
    user = getattr(getattr(owner, "auth", None), "current_user", None) or {}
    return str(user.get("username") or user.get("id") or "unknown")


def _load_student(student_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT student_id, first_name, last_name, status, course,
                      mode_of_study, campus_code, academic_year,
                      expected_return_date, is_active
                 FROM students WHERE student_id = ?""",
            (student_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        return dict(row)
    except (TypeError, ValueError):
        # Connection handed back tuples rather than Row objects.
        keys = ("student_id", "first_name", "last_name", "status", "course",
                "mode_of_study", "campus_code", "academic_year",
                "expected_return_date", "is_active")
        return dict(zip(keys, row))


def _sync_sign_in(student_id, status):
    """Withdrawn or closed students lose their sign-in; reinstated or
    resumed students get it back. Completed students keep theirs."""
    from education_system.systems.university.services.student_provisioning import (
        sync_sign_in_for_status,
    )
    sync_sign_in_for_status(student_id, status)


def manage_student_lifecycle(self, student_id, first_name=None, last_name=None):
    """Open the registration-status dialog for one student."""
    if not require_student_permission(
            self, "update_any_student", "change the registration status of"):
        return

    student = _load_student(student_id)
    if student is None:
        messagebox.showerror(
            _t("common.error", default="Error"),
            f"Student {student_id} was not found.",
            parent=getattr(self, "root", None))
        return

    name = " ".join(
        p for p in (first_name or student.get("first_name"),
                    last_name or student.get("last_name")) if p
    ).strip() or student_id
    current_status = student.get("status")

    dialog = tk.Toplevel(self.root)
    _install_clean_close(dialog)
    dialog.title(f"Registration Status — {name} ({student_id})")
    _fit_window(dialog, "760x720", minsize=(620, 520))
    dialog.transient(self.root)
    dialog.update_idletasks()
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        logger.debug("Could not grab lifecycle dialog", exc_info=True)

    outer = ttk.Frame(dialog, padding=12)
    outer.pack(fill=tk.BOTH, expand=True)

    # ── Current state ────────────────────────────────────────────────
    summary = ttk.LabelFrame(outer, text="Current record", padding=10)
    summary.pack(fill=tk.X)

    for label, value in (
        ("Student", f"{name} ({student_id})"),
        ("Status", current_status or "—"),
        ("Course", student.get("course") or "—"),
        ("Mode of study", student.get("mode_of_study") or "—"),
        ("Academic year", student.get("academic_year") or "—"),
        ("Expected return", student.get("expected_return_date") or "—"),
    ):
        line = ttk.Frame(summary)
        line.pack(fill=tk.X, pady=1)
        ttk.Label(line, text=f"{label}:", width=16,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(line, text=str(value)).pack(side=tk.LEFT)

    # change_status() now keeps is_active in step, but records changed
    # before that still carry the old value. Say so rather than hiding it.
    if student.get("is_active") and current_status not in (None, "Active"):
        ttk.Label(
            summary,
            text=("Note: is_active is still 1 while status is "
                  f"'{current_status}' — a stale value from before these "
                  "columns were kept in step. The next lifecycle change on "
                  "this record corrects it."),
            foreground="#a05000", wraplength=680, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(6, 0))

    actions = student_lifecycle.available_actions(current_status)

    # ── Tabs: status change and study details ────────────────────────
    tabs = ttk.Notebook(outer)
    tabs.pack(fill=tk.X, pady=(10, 0))

    form = ttk.Frame(tabs, padding=10)
    study_tab = ttk.Frame(tabs, padding=10)
    tabs.add(form, text="Change status")
    tabs.add(study_tab, text="Study details")

    # ── Status tab ───────────────────────────────────────────────────
    if not actions:
        ttk.Label(
            form,
            text=(
                f"'{current_status}' is not part of the registration "
                "lifecycle, so no transition can be applied. The lifecycle "
                "statuses are: Active, Registration Pending, Interrupted, "
                "Withdrawn, Deferred, Suspended, Completed, Closed.\n\n"
                "A record in a legacy status needs correcting to a "
                "lifecycle status before it can be managed here."
            ),
            wraplength=680, justify=tk.LEFT, foreground="#a05000",
        ).pack(anchor=tk.W)
    else:
        action_var = tk.StringVar(value=actions[0])
        row = ttk.Frame(form)
        row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(row, text="Action:", width=16,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        action_box = ttk.Combobox(
            row, state="readonly", width=28, textvariable=action_var,
            values=[f"{_ACTION_LABELS.get(a, a)}  ({a})" for a in actions],
        )
        action_box.current(0)
        action_box.pack(side=tk.LEFT)

        becomes_var = tk.StringVar()
        ttk.Label(row, textvariable=becomes_var,
                  foreground="#005a9e").pack(side=tk.LEFT, padx=(10, 0))

        reason_row = ttk.Frame(form)
        reason_row.pack(fill=tk.X, pady=4)
        ttk.Label(reason_row, text="Reason:", width=16,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        reason_var = tk.StringVar()
        ttk.Entry(reason_row, textvariable=reason_var, width=48).pack(
            side=tk.LEFT, fill=tk.X, expand=True)

        eff_row = ttk.Frame(form)
        eff_row.pack(fill=tk.X, pady=4)
        ttk.Label(eff_row, text="Effective date:", width=16,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        effective_var = tk.StringVar(value=datetime.now().date().isoformat())
        ttk.Entry(eff_row, textvariable=effective_var, width=14).pack(side=tk.LEFT)
        ttk.Label(eff_row, text=f"  ({_DATE_HINT})",
                  foreground="#666666").pack(side=tk.LEFT)

        ret_row = ttk.Frame(form)
        ret_row.pack(fill=tk.X, pady=4)
        ttk.Label(ret_row, text="Expected return:", width=16,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        return_var = tk.StringVar(value=student.get("expected_return_date") or "")
        return_entry = ttk.Entry(ret_row, textvariable=return_var, width=14)
        return_entry.pack(side=tk.LEFT)
        return_hint = ttk.Label(ret_row, text=f"  ({_DATE_HINT})",
                                foreground="#666666")
        return_hint.pack(side=tk.LEFT)

        def _selected_action() -> str:
            idx = action_box.current()
            return actions[idx if idx >= 0 else 0]

        def _on_action_change(*_a):
            action = _selected_action()
            target = student_lifecycle.target_status(action)
            becomes_var.set(f"\u2192 {target}" if target else "")
            if action in _RETURN_DATE_ACTIONS:
                return_entry.state(["!disabled"])
                return_hint.configure(text=f"  ({_DATE_HINT})")
            else:
                return_var.set("")
                return_entry.state(["disabled"])
                return_hint.configure(text="  (not used for this action)")

        action_box.bind("<<ComboboxSelected>>", _on_action_change)
        _on_action_change()

        ttk.Button(form, text="Apply status change",
                   command=lambda: _apply_status()).pack(anchor=tk.W, pady=(10, 0))

    # ── Study-details tab ────────────────────────────────────────────
    study_ok = current_status in _STUDY_ALLOWED_STATUSES
    if not study_ok:
        ttk.Label(
            study_tab,
            text=("Study details can only be changed while the student is "
                  f"{', '.join(_STUDY_ALLOWED_STATUSES)} — this record is "
                  f"'{current_status}'."),
            wraplength=680, justify=tk.LEFT, foreground="#a05000",
        ).pack(anchor=tk.W)
    else:
        ttk.Label(
            study_tab,
            text=("Exactly one change per submission — the domain records each "
                  "as its own history entry."),
            foreground="#666666", wraplength=680, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 8))

        study_kind = tk.StringVar(value=_STUDY_FIELDS[0][0])
        kind_row = ttk.Frame(study_tab)
        kind_row.pack(fill=tk.X, pady=4)
        ttk.Label(kind_row, text="Change:", width=16,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        kind_box = ttk.Combobox(
            kind_row, state="readonly", width=28,
            values=[label for _k, label in _STUDY_FIELDS])
        kind_box.current(0)
        kind_box.pack(side=tk.LEFT)

        value_row = ttk.Frame(study_tab)
        value_row.pack(fill=tk.X, pady=4)
        ttk.Label(value_row, text="New value:", width=16,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        study_value = tk.StringVar()
        value_box = ttk.Combobox(value_row, width=28, textvariable=study_value)
        value_box.pack(side=tk.LEFT)
        value_hint = ttk.Label(value_row, text="", foreground="#666666")
        value_hint.pack(side=tk.LEFT, padx=(8, 0))

        year_row = ttk.Frame(study_tab)
        year_row.pack(fill=tk.X, pady=4)
        ttk.Label(year_row, text="Academic year:", width=16,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        study_year = tk.StringVar(value=student.get("academic_year") or "")
        ttk.Entry(year_row, textvariable=study_year, width=14).pack(side=tk.LEFT)
        ttk.Label(year_row, text="  (optional)",
                  foreground="#666666").pack(side=tk.LEFT)

        sreason_row = ttk.Frame(study_tab)
        sreason_row.pack(fill=tk.X, pady=4)
        ttk.Label(sreason_row, text="Reason:", width=16,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        study_reason = tk.StringVar()
        ttk.Entry(sreason_row, textvariable=study_reason, width=48).pack(
            side=tk.LEFT, fill=tk.X, expand=True)

        def _selected_study_kind() -> str:
            i = kind_box.current()
            return _STUDY_FIELDS[i if i >= 0 else 0][0]

        def _on_kind_change(*_a):
            kind = _selected_study_kind()
            study_value.set("")
            if kind == "programme_code":
                codes = _active_course_codes()
                value_box.configure(values=codes, state="readonly")
                value_hint.configure(
                    text=f"current: {student.get('course') or '—'}")
            elif kind == "mode_of_study":
                value_box.configure(values=_MODE_CHOICES, state="normal")
                value_hint.configure(
                    text=f"current: {student.get('mode_of_study') or '—'}")
            elif kind == "campus_code":
                value_box.configure(values=(), state="normal")
                value_hint.configure(
                    text=f"current: {student.get('campus_code') or '—'}")
            else:
                value_box.configure(values=("1", "2", "3", "4"), state="normal")
                value_hint.configure(text="whole number")

        kind_box.bind("<<ComboboxSelected>>", _on_kind_change)
        _on_kind_change()

        ttk.Button(study_tab, text="Apply study change",
                   command=lambda: _apply_study()).pack(anchor=tk.W, pady=(10, 0))

    # ── History ──────────────────────────────────────────────────────
    hist_frame = ttk.LabelFrame(outer, text="Lifecycle history", padding=10)
    hist_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    hist_cols = ("id", "when", "action", "from", "to", "actor", "reason")
    hist_tree = ttk.Treeview(hist_frame, columns=hist_cols,
                             show="headings", height=8)
    for col, title, width in (
        ("id", "#", 46), ("when", "Effective", 90), ("action", "Action", 110),
        ("from", "From", 95), ("to", "To", 95),
        ("actor", "By", 90), ("reason", "Reason", 200),
    ):
        hist_tree.heading(col, text=title)
        hist_tree.column(col, width=width, minwidth=40, anchor="w")

    hist_vsb = ttk.Scrollbar(hist_frame, orient=tk.VERTICAL,
                             command=hist_tree.yview)
    hist_tree.configure(yscrollcommand=hist_vsb.set)
    hist_tree.grid(row=0, column=0, sticky="nsew")
    hist_vsb.grid(row=0, column=1, sticky="ns")
    ttk.Button(hist_frame, text="Reverse selected change\u2026",
               command=lambda: _reverse_selected()).grid(
        row=1, column=0, sticky="w", pady=(8, 0))
    hist_frame.rowconfigure(0, weight=1)
    hist_frame.columnconfigure(0, weight=1)

    def _refresh_history():
        for item in hist_tree.get_children():
            hist_tree.delete(item)
        try:
            rows = student_lifecycle.history(student_id)
        except Exception as exc:
            logger.exception("Could not load lifecycle history")
            hist_tree.insert("", tk.END,
                             values=("", "\u2014", "history unavailable", "", "",
                                     "", str(exc)[:120]))
            return
        if not rows:
            hist_tree.insert("", tk.END,
                             values=("", "\u2014", "no changes recorded",
                                     "", "", "", ""))
            return
        for r in rows:
            hist_tree.insert("", tk.END, values=(
                r.get("history_id") or "",
                r.get("effective_date") or "",
                r.get("action") or "",
                r.get("from_status") or "",
                r.get("to_status") or "",
                r.get("actor_id") or "",
                r.get("reason") or "",
            ))

    _refresh_history()

    # ── Shared helpers ───────────────────────────────────────────────
    def _finish(message):
        messagebox.showinfo("Lifecycle updated", message, parent=dialog)
        dialog.destroy()
        for attr in ("student_tree", "records_tree"):
            tree = getattr(self, attr, None)
            if tree is not None:
                try:
                    self.view_students_in_window(tree)
                except Exception:
                    logger.debug("Could not refresh %s", attr, exc_info=True)

    def _apply_status():
        action = _selected_action()
        reason = reason_var.get().strip()
        if not reason:
            messagebox.showwarning(
                "Reason required",
                "Enter a reason \u2014 it is written to the immutable "
                "lifecycle history.", parent=dialog)
            return
        try:
            effective = _parse_date(effective_var.get(), "Effective date")
            expected_return = (
                _parse_date(return_var.get(), "Expected return date")
                if action in _RETURN_DATE_ACTIONS else None
            )
        except ValueError as exc:
            messagebox.showerror("Invalid date", str(exc), parent=dialog)
            return

        target = student_lifecycle.target_status(action)
        if not messagebox.askyesno(
                "Confirm status change",
                f"{_ACTION_LABELS.get(action, action)} {name} ({student_id})?\n\n"
                f"Status: {current_status} \u2192 {target}\n"
                f"Effective: {effective or 'today'}\n\n"
                "This writes an immutable history record and notifies "
                f"{len(student_lifecycle.DOWNSTREAM_SYSTEMS)} downstream systems.",
                parent=dialog):
            return
        try:
            student_lifecycle.change_status(
                student_id, action, actor_id=_actor_id(self), reason=reason,
                effective_date=effective, expected_return_date=expected_return)
        except Exception as exc:
            logger.exception("Lifecycle change failed for %s", student_id)
            messagebox.showerror(
                "Status change failed",
                f"Could not {action} this student:\n\n{exc}", parent=dialog)
            return
        _sync_sign_in(student_id, target)
        _finish(f"{name} is now '{target}'.")

    def _apply_study():
        kind = _selected_study_kind()
        raw = study_value.get().strip()
        reason = study_reason.get().strip()
        if not raw:
            messagebox.showwarning("Value required",
                                   "Enter the new value.", parent=dialog)
            return
        if not reason:
            messagebox.showwarning(
                "Reason required",
                "Enter a reason \u2014 it is written to the immutable "
                "lifecycle history.", parent=dialog)
            return
        kwargs = {}
        if kind == "repeat_year":
            try:
                kwargs["repeat_year"] = int(raw)
            except ValueError:
                messagebox.showerror("Invalid value",
                                     "Repeat year must be a whole number.",
                                     parent=dialog)
                return
        else:
            kwargs[kind] = raw
        year = study_year.get().strip()
        if year:
            kwargs["academic_year"] = year
        label = dict(_STUDY_FIELDS)[kind]
        if not messagebox.askyesno(
                "Confirm study change",
                f"Change {label.lower()} for {name} ({student_id}) to "
                f"'{raw}'?\n\nThis writes an immutable history record.",
                parent=dialog):
            return
        try:
            if kind == "programme_code":
                # A programme change is a transfer: the curriculum moves too.
                from education_system.systems.university.application.students.lifecycle import (
                    StudentLifecycleService,
                )
                StudentLifecycleService().transfer_course(
                    student_id, raw, actor_id=_actor_id(self), reason=reason,
                    idempotency_key=f"gui:transfer:{student_id}:{datetime.now().isoformat()}")
            else:
                student_lifecycle.change_study(
                    student_id, actor_id=_actor_id(self), reason=reason, **kwargs)
        except Exception as exc:
            logger.exception("Study change failed for %s", student_id)
            messagebox.showerror(
                "Study change failed",
                f"Could not apply that change:\n\n{exc}", parent=dialog)
            return
        _finish(f"{label} updated to '{raw}' for {name}.")

    def _reverse_selected():
        """Reverse one history entry. The domain requires dual control, so
        the approver must be someone other than the signed-in user."""
        selection = hist_tree.selection()
        if not selection:
            messagebox.showwarning("Nothing selected",
                                   "Select the history row to reverse.",
                                   parent=dialog)
            return
        values = hist_tree.item(selection[0]).get("values") or []
        try:
            history_id = int(values[0])
        except (IndexError, TypeError, ValueError):
            messagebox.showwarning("Not reversible",
                                   "That row is not a recorded change.",
                                   parent=dialog)
            return

        win = tk.Toplevel(dialog)
        _install_clean_close(win)
        win.title(f"Reverse change #{history_id}")
        _fit_window(win, "520x280", minsize=(460, 240))
        win.transient(dialog)
        win.update_idletasks()
        win.deiconify()
        try:
            win.grab_set()
        except tk.TclError:
            logger.debug("Could not grab reversal dialog", exc_info=True)

        body = ttk.Frame(win, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        requester = _actor_id(self)
        ttk.Label(
            body,
            text=(f"Reversing history entry #{history_id} "
                  f"({values[2] if len(values) > 2 else ''}).\n\n"
                  "This is a dual-control action: the approver must be a "
                  f"different person from the requester ({requester})."),
            wraplength=470, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 10))

        appr_row = ttk.Frame(body)
        appr_row.pack(fill=tk.X, pady=4)
        ttk.Label(appr_row, text="Approver:", width=14,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        approver_var = tk.StringVar()
        ttk.Entry(appr_row, textvariable=approver_var, width=28).pack(side=tk.LEFT)

        rr_row = ttk.Frame(body)
        rr_row.pack(fill=tk.X, pady=4)
        ttk.Label(rr_row, text="Reason:", width=14,
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        rev_reason = tk.StringVar()
        ttk.Entry(rr_row, textvariable=rev_reason, width=36).pack(
            side=tk.LEFT, fill=tk.X, expand=True)

        def _do_reverse():
            approver = approver_var.get().strip()
            reason = rev_reason.get().strip()
            if not approver or not reason:
                messagebox.showwarning(
                    "Approver and reason required",
                    "Both an independent approver and a reason are required.",
                    parent=win)
                return
            if approver == requester:
                messagebox.showerror(
                    "Independent approval required",
                    "The approver must be someone other than the requester.",
                    parent=win)
                return
            try:
                student_lifecycle.reverse_change(
                    history_id, reason=reason,
                    requested_by=requester, approved_by=approver)
            except Exception as exc:
                logger.exception("Reversal failed for history %s", history_id)
                messagebox.showerror("Reversal failed",
                                     f"Could not reverse:\n\n{exc}", parent=win)
                return
            win.destroy()
            _finish(f"Change #{history_id} reversed.")

        btns = ttk.Frame(body)
        btns.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(btns, text="Reverse change",
                   command=_do_reverse).pack(side=tk.LEFT)
        ttk.Button(btns, text=_t("gui.close", default="Close"),
                   command=win.destroy).pack(side=tk.RIGHT)

    ttk.Button(outer, text=_t("gui.close", default="Close"),
               command=dialog.destroy).pack(anchor=tk.E, pady=(10, 0))
