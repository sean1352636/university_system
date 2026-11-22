"""GUI panels for Sixth Form Enrolment CRUD.

Rendered into ``SixthFormMainGUI.content_frame``. Mirrors the layout of
``student_views``: a directory with filters + actions, plus an
add/edit form. Error handling: all DB calls live inside try/except
blocks that log via the module logger and surface user-friendly
messages through ``messagebox``.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
    simpledialog,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    DEFAULT_STATUS,
    Enrolment,
    STATUSES,
    YEAR_GROUPS,
)

from education_system.systems.sixth_form.interfaces.gui import popout
from .enrolment_bulk_actions import (
    open_bulk_return_intention,
    open_bulk_status_change,
    open_bulk_tutor_reassign,
)
from .enrolment_common import (
    _UNDO_STACK,
    _clear,
    _count_badge_per_status,
    _default_academic_year,
    _heading,
    _next_academic_year,
    _student_name_map,
    _year_choices,
    show_error,
)
from .enrolment_cohort_views import (
    open_bulk_enrol,
    open_end_of_year_rollover,
    open_progression_wizard,
)
from .enrolment_history_views import audit_table, open_student_enrolment_history
from .enrolment_integrity_views import (
    _highlight_duplicate_conflicts,
    _highlight_students_without_enrolment,
    open_transfer_enrolment,
)
from .enrolment_io_views import (
    copy_enrolment_to_clipboard,
    export_directory_csv,
    export_enrolment_pdf,
    export_progression_list,
    export_tutor_group_pdf,
    import_enrolments_csv,
)
from .enrolment_pickers import StudentPicker, TutorGroupPicker, students_for_picker
from .enrolment_record_actions import (
    archive_toggle,
    restore_enrolments,
    reinstate_with_reason,
    reopen_with_reason,
    _confirm_and_withdraw,
    _confirm_bulk_delete,
    _delete_with_confirm,
    _soft_delete_toggle,
    open_undo_last_action,
)
from .enrolment_report_views import (
    open_capacity_utilisation,
    open_cohort_report,
    open_enrolment_dashboard,
    open_retention_report,
    open_tutor_group_roster_picker,
    open_withdrawal_analysis,
    open_year_on_year_comparison,
)
from .enrolment_checks_views import warnings_for, warnings_section
from .enrolment_rollover_views import open_return_intentions, open_rollover_history

__all__ = ["export_tutor_group_pdf", "open_student_enrolment_history"]

logger = logging.getLogger(__name__)


# ── Saved filter presets (persisted as JSON in the data dir) ─────────

from education_system import paths as _paths

_PRESETS_PATH = _paths.SIXTH_FORM_DATA_DIR / "enrolment_filter_presets.json"


def _load_presets() -> dict[str, dict[str, str]]:
    try:
        with open(_PRESETS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        logger.exception("Could not read enrolment filter presets")
        return {}


def _save_presets(presets: dict[str, dict[str, str]]) -> None:
    try:
        _paths.ensure_sixth_form_directories()
        with open(_PRESETS_PATH, "w", encoding="utf-8") as fh:
            json.dump(presets, fh, indent=2)
    except Exception:
        logger.exception("Could not write enrolment filter presets")


# ── Form (add + edit) ───────────────────────────────────────────────

# Picker entries in the edit form's status box that open a lifecycle
# action instead of setting a status.
_WITHDRAW_ACTION = "Withdraw…"
_REINSTATE_ACTION = "Reinstate…"
_REOPEN_ACTION = "Reopen…"


def _status_options(existing: Enrolment | None) -> list[str]:
    """What the status box offers: ``allowed_statuses`` for an edit (plus
    the action that leaves the status: withdraw / reinstate / reopen), the
    create statuses for a new enrolment."""
    if existing is None:
        return list(data.CREATE_STATUSES)
    opts = list(data.allowed_statuses(existing))
    if existing.is_live:
        opts.append(_WITHDRAW_ACTION)
    elif existing.status == "Withdrawn":
        opts.append(_REINSTATE_ACTION)
    elif existing.status == "Completed":
        opts.append(_REOPEN_ACTION)
    return opts


def _enrolment_form(
    gui,
    *,
    title: str,
    existing: Enrolment | None,
    preselect_student_id: str | None,
    on_save: Callable[[dict[str, Any]], Enrolment],
    preset_year: str | None = None,
    preset_year_group: int | None = None,
) -> dict[str, Any]:
    """Render the add / edit form. Returns its widgets and variables (for
    callers that drive it, e.g. checks)."""
    frame = _clear(gui)
    _heading(frame, title)

    is_edit = existing is not None
    parts: dict[str, Any] = {}

    if not data.can_write():
        ttk.Label(frame, foreground="#a33", text=(
            "Your account can view enrolments but not change them.")).pack(anchor="w")
        ttk.Button(frame, text="Back to Enrolments",
                   command=lambda: open_directory(gui)).pack(anchor="w", pady=(8, 0))
        return parts

    # Only learners on roll can be enrolled (create_enrolment refuses others).
    student_picker: StudentPicker | None = None
    if not is_edit and not students_for_picker():
        ttk.Label(
            frame,
            text="No students on roll — add a student (or reinstate a leaver) first.",
            foreground="#a33",
        ).pack(anchor="w")
        ttk.Button(
            frame, text="Back to Enrolments",
            command=lambda: open_directory(gui),
        ).pack(anchor="w", pady=(8, 0))
        return parts

    year_var = tk.StringVar(
        value=existing.academic_year if is_edit
        else (preset_year or _default_academic_year()))
    yg_var = tk.StringVar(
        value=str(existing.year_group) if is_edit
        else str(preset_year_group or YEAR_GROUPS[0]))
    tg_var = tk.StringVar(value=(existing.tutor_group or "") if is_edit else "")
    sd_var = tk.StringVar(
        value=(existing.start_date or "") if is_edit else date.today().isoformat())
    status_var = tk.StringVar(
        value=existing.status if is_edit else DEFAULT_STATUS)
    withdrawn = is_edit and existing.status == "Withdrawn"
    wd_var = tk.StringVar(value=(existing.withdrawal_date or "") if withdrawn else "")
    wr_var = tk.StringVar(value=(existing.withdrawal_reason_label or "") if withdrawn else "")
    wdet_var = tk.StringVar(value=(existing.withdrawal_detail or "") if withdrawn else "")
    # ── Layout ──
    form = ttk.Frame(frame, padding=(0, 4))
    form.pack(anchor="w", fill="x")
    form.columnconfigure(1, weight=1, minsize=320)

    # `notes_text` must be parented on the grid-managed `form`, not on
    # the pack-managed `frame` — Tk refuses to grid a widget whose
    # parent already has pack-managed children.
    notes_text = tk.Text(form, height=4, width=60)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    if is_edit:
        row(0, "Student *", ttk.Label(
            form, text=f"{existing.student_id} — "
            f"{_student_name_map().get(existing.student_id, '')}  (use Transfer "
            "to move it to another learner)"))
    else:
        student_picker = StudentPicker(form, leavers_toggle=False,
                                       preselect=preselect_student_id)
        row(0, "Student * (on roll)", student_picker)

    year_box = ttk.Combobox(form, textvariable=year_var, state="readonly",
                            values=_year_choices(year_var.get()), width=10)
    row(1, "Academic year *", year_box)
    row(2, "Year group *", ttk.Combobox(
        form, textvariable=yg_var, values=[str(y) for y in YEAR_GROUPS],
        state="readonly", width=8))
    tg_picker = TutorGroupPicker(form, tg_var, int(yg_var.get()))
    row(3, "Tutor group", tg_picker)
    sd_entry = tk.Entry(form, textvariable=sd_var)
    row(4, "Start date (YYYY-MM-DD)", sd_entry)
    _live_validate_start_date(sd_entry, sd_var)  # feature #37
    # Feature #38 — bump the tutor group prefix when the year group changes,
    # then offer that year's real tutor groups.
    yg_var._prev_yg = int(yg_var.get() or YEAR_GROUPS[0])  # type: ignore[attr-defined]

    def _yg_changed(*_a) -> None:
        _autofill_tutor_group_from_year(yg_var, tg_var)
        tg_picker.set_year_group(int(yg_var.get()) if yg_var.get() else None)
        if not tg_picker.free_text and tg_var.get() not in tg_picker.cget("values"):
            tg_var.set("")
    yg_var.trace_add("write", _yg_changed)

    status_box = ttk.Combobox(form, textvariable=status_var,
                              values=_status_options(existing),
                              state="readonly", width=16)
    row(5, "Status *", status_box)

    def _status_action(_e=None) -> None:
        choice = status_var.get()
        if choice not in (_WITHDRAW_ACTION, _REINSTATE_ACTION, _REOPEN_ACTION):
            return
        status_var.set(existing.status)
        if _snapshot() != _initial and not messagebox.askyesno(
                "Unsaved changes", "Other changes on this form are not saved "
                "yet and will be discarded. Continue?", parent=gui.root):
            return
        back = lambda: open_profile(gui, existing.enrolment_id)  # noqa: E731
        if choice == _WITHDRAW_ACTION:
            parts["dialog"] = _confirm_and_withdraw(gui, existing.enrolment_id, back)
        elif choice == _REINSTATE_ACTION:
            reinstate_with_reason(gui, existing.enrolment_id, back)
        else:
            reopen_with_reason(gui, existing.enrolment_id, back)
    status_box.bind("<<ComboboxSelected>>", _status_action)
    parts["status_action"] = _status_action
    next_row = 6
    if withdrawn:
        ttk.Label(form, text="Correct the withdrawal (Reinstate undoes it):",
                  foreground="#555").grid(row=next_row, column=0, columnspan=2,
                                          sticky="w", pady=(8, 0))
        row(next_row + 1, "Last day in learning", ttk.Entry(form, textvariable=wd_var))
        from .enrolment_withdraw_dialog import reason_choices
        row(next_row + 2, "ILR withdrawal reason", ttk.Combobox(
            form, textvariable=wr_var, values=reason_choices(), state="readonly"))
        row(next_row + 3, "Withdrawal detail", ttk.Entry(form, textvariable=wdet_var))
        next_row += 4
    ttk.Label(form, text="Notes").grid(row=next_row, column=0, sticky="ne",
                                       padx=(0, 8), pady=4)
    notes_text.grid(row=next_row, column=1, sticky="ew", pady=4)
    if is_edit and existing.notes:
        notes_text.insert("1.0", existing.notes)

    # ── Buttons ──
    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))

    # Feature #39 — track edits so we can warn before discarding them.
    def _snapshot() -> tuple:
        return (student_picker.get() if student_picker else None, year_var.get(),
                yg_var.get(), tg_var.get(), sd_var.get(), status_var.get(),
                wd_var.get(), wr_var.get(), wdet_var.get(),
                notes_text.get("1.0", "end"))

    _initial = _snapshot()

    def _leave() -> None:
        if _warn_on_unsaved_changes(gui, _snapshot() != _initial):
            open_directory(gui)

    def submit() -> None:
        if is_edit:
            sid = existing.student_id
        else:
            sid = student_picker.get()
            if not sid:
                messagebox.showerror(
                    "Cannot save", "Please choose a student.", parent=gui.root)
                return
        payload = {
            "student_id":    sid,
            "academic_year": year_var.get(),
            "year_group":    yg_var.get(),
            "tutor_group":   tg_var.get(),
            "start_date":    sd_var.get(),
            "status":        status_var.get(),
            "notes":         notes_text.get("1.0", "end").strip(),
        }
        if withdrawn:
            detail = wdet_var.get().strip()
            payload.update({
                "withdrawal_date": wd_var.get().strip() or None,
                "withdrawal_reason": wr_var.get().split(" — ", 1)[0].strip() or None,
            })
            if detail != data.RESTRICTED:
                payload["withdrawal_detail"] = detail or None
        try:
            saved = on_save(payload)
        except Exception as e:  # ValidationError / AccessDenied / DB
            logger.warning("Enrolment form rejected: %s", e)
            show_error(gui.root, "Cannot save", e)
            return
        logger.info("GUI saved enrolment #%d via %s", saved.enrolment_id, title)
        warnings = warnings_for(saved.student_id, saved.academic_year)
        (messagebox.showwarning if warnings else messagebox.showinfo)(
            "Saved",
            f"Enrolment #{saved.enrolment_id} saved\n"
            f"  Student : {saved.student_id}\n"
            f"  Year    : {saved.academic_year} · Year {saved.year_group}\n"
            f"  Tutor   : {saved.tutor_group or '—'}\n"
            f"  Status  : {saved.status}"
            + ("\n\nPlease check (the enrolment is saved):\n"
               + "\n".join(f"  • {w}" for w in warnings) if warnings else ""),
            parent=gui.root,
        )
        gui.status_var.set(f"Saved enrolment #{saved.enrolment_id}")
        open_directory(gui)

    ttk.Button(bar, text="Save", command=submit).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel", command=_leave).pack(side="left")
    parts.update(student=student_picker, year=year_var, year_group=yg_var,
                 tutor=tg_var, tutor_picker=tg_picker, start=sd_var,
                 status=status_var, status_box=status_box, notes=notes_text,
                 submit=submit)
    return parts


def open_add_enrolment(
    gui,
    preselect_student_id: str | None = None,
    *,
    preset_year: str | None = None,
    preset_year_group: int | None = None,
) -> dict[str, Any]:
    def on_save(payload: dict[str, Any]) -> Enrolment:
        return data.create_enrolment(payload)
    parts = _enrolment_form(
        gui, title="New Enrolment", existing=None,
        preselect_student_id=preselect_student_id, on_save=on_save,
        preset_year=preset_year, preset_year_group=preset_year_group,
    )
    gui.status_var.set("New enrolment")
    return parts


def open_edit_enrolment(gui, enrolment_id: int) -> dict[str, Any] | None:
    try:
        existing = data.get_enrolment(enrolment_id)
    except Exception as e:
        logger.exception("Failed to load enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not load enrolment: {e}",
                             parent=gui.root)
        return None
    if existing is None:
        messagebox.showerror(
            "Not found", f"No enrolment #{enrolment_id}", parent=gui.root)
        return None

    def on_save(payload: dict[str, Any]) -> Enrolment:
        return data.update_enrolment(enrolment_id, payload)

    parts = _enrolment_form(
        gui, title=f"Edit Enrolment #{enrolment_id}",
        existing=existing, preselect_student_id=existing.student_id,
        on_save=on_save,
    )
    gui.status_var.set(f"Editing enrolment #{enrolment_id}")
    return parts


# ── Directory (list + filters + actions) ────────────────────────────


def _sort_by_column(tree: ttk.Treeview, col: str, descending: bool) -> None:
    """Sort the tree rows by a column (numeric where possible), then flip the
    heading so the next click reverses direction."""
    items = [(tree.set(iid, col), iid) for iid in tree.get_children("")]

    def key(item: tuple[str, str]):
        val = item[0]
        try:
            return (0, float(val))
        except ValueError:
            return (1, val.lower())

    items.sort(key=key, reverse=descending)
    for index, (_v, iid) in enumerate(items):
        tree.move(iid, "", index)
    tree.heading(col, command=lambda: _sort_by_column(tree, col, not descending))


def _apply_status_row_colours(tree: ttk.Treeview) -> None:
    """Configure per-status foreground tags. Rows are tagged with their status
    at insert time; ``Enrolled`` keeps the default colour."""
    tree.tag_configure("Withdrawn", foreground="#888888")
    tree.tag_configure("Pending", foreground="#b8860b")
    tree.tag_configure("Completed", foreground="#2a7aa1")


def _quick_filter_current_year(fvars: dict[str, tk.StringVar],
                               refresh: Callable[[], None]) -> None:
    """One-click filter to the current academic year (feature #15)."""
    fvars["academic_year"].set(_default_academic_year())
    refresh()


def _add_tutor_group_filter(parent, fvars: dict[str, tk.StringVar],
                            refresh: Callable[[], None]) -> None:
    ttk.Label(parent, text="Tutor:").pack(side="left")
    e = ttk.Entry(parent, textvariable=fvars["tutor_group"], width=8)
    e.pack(side="left", padx=(4, 12))
    e.bind("<Return>", lambda _e: refresh())


def _add_student_search_box(parent, fvars: dict[str, tk.StringVar],
                            refresh: Callable[[], None]) -> None:
    ttk.Label(parent, text="Search:").pack(side="left")
    e = ttk.Entry(parent, textvariable=fvars["search"], width=18)
    e.pack(side="left", padx=(4, 12))
    e.bind("<Return>", lambda _e: refresh())


def _add_date_range_filter(parent, fvars: dict[str, tk.StringVar],
                           refresh: Callable[[], None]) -> None:
    ttk.Label(parent, text="Start ≥").pack(side="left")
    f = ttk.Entry(parent, textvariable=fvars["start_from"], width=11)
    f.pack(side="left", padx=(4, 6))
    ttk.Label(parent, text="≤").pack(side="left")
    t = ttk.Entry(parent, textvariable=fvars["start_to"], width=11)
    t.pack(side="left", padx=(4, 12))
    for entry in (f, t):
        entry.bind("<Return>", lambda _e: refresh())


def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Enrolment Directory")

    fvars: dict[str, tk.StringVar] = {
        "academic_year": tk.StringVar(value=_default_academic_year()),
        "year_group":    tk.StringVar(),
        "status":        tk.StringVar(),
        "tutor_group":   tk.StringVar(),
        "search":        tk.StringVar(),
        "start_from":    tk.StringVar(),
        "start_to":      tk.StringVar(),
        "archived":      tk.StringVar(),
    }

    # ── Layout scaffolding (packed top-to-bottom in call order) ──
    filt = ttk.Frame(frame)
    filt.pack(anchor="w", fill="x", pady=(0, 8))
    badge_holder = ttk.Frame(frame)
    badge_holder.pack(anchor="w", fill="x", pady=(0, 4))
    # Bottom bars are packed before the expanding table so a short window
    # squeezes the table, never the action buttons.
    actions_holder = ttk.Frame(frame)
    actions_holder.pack(side="bottom", anchor="w", pady=(0, 4))
    summary = ttk.Label(frame, text="", foreground="#555")
    summary.pack(side="bottom", anchor="w", pady=(4, 8))
    pager_holder = ttk.Frame(frame)
    pager_holder.pack(side="bottom", anchor="w", pady=(2, 0))
    table_holder = ttk.Frame(frame)
    table_holder.pack(fill="both", expand=True)

    # Pagination state (feature #45) — persists across refreshes.
    page = {"idx": 0, "size": 50}

    def refresh() -> None:
        for holder in (badge_holder, table_holder, pager_holder, actions_holder):
            for w in holder.winfo_children():
                w.destroy()

        try:
            rows = data.list_enrolments(
                academic_year=fvars["academic_year"].get().strip() or None,
                year_group=int(fvars["year_group"].get()) if fvars["year_group"].get() else None,
                status=fvars["status"].get().strip() or None,
                include_archived=fvars["archived"].get() == "Include",
                archived_only=fvars["archived"].get() == "Only",
            )
        except Exception as e:
            logger.exception("Failed to load enrolments")
            ttk.Label(
                table_holder, text=f"Error loading enrolments: {e}",
                foreground="#a33",
            ).pack(anchor="w")
            return

        names = _student_name_map()

        # ── Python-side filters the data layer doesn't cover ──
        tg = fvars["tutor_group"].get().strip().lower()
        if tg:
            rows = [r for r in rows if tg in (r.tutor_group or "").lower()]
        q = fvars["search"].get().strip().lower()
        if q:
            rows = [
                r for r in rows
                if q in r.student_id.lower() or q in names.get(r.student_id, "").lower()
            ]
        sf = fvars["start_from"].get().strip()
        if sf:
            rows = [r for r in rows if (r.start_date or "") >= sf]
        st_to = fvars["start_to"].get().strip()
        if st_to:
            rows = [r for r in rows if r.start_date and r.start_date <= st_to]

        _count_badge_per_status(badge_holder, rows)  # feature #16

        # ── Pagination (feature #45) ──
        total = len(rows)
        pages = max(1, (total + page["size"] - 1) // page["size"])
        page["idx"] = max(0, min(page["idx"], pages - 1))
        start = page["idx"] * page["size"]
        page_rows = rows[start:start + page["size"]]

        cols = ("enrolment_id", "student_id", "name",
                "academic_year", "year_group", "tutor_group",
                "start_date", "status")
        headings = {
            "enrolment_id":  ("#",         50),
            "student_id":    ("Student ID", 100),
            "name":          ("Name",       200),
            "academic_year": ("Year",        80),
            "year_group":    ("YG",          40),
            "tutor_group":   ("Tutor",       70),
            "start_date":    ("Start",      100),
            "status":        ("Status",     100),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings",
                            height=14, selectmode="extended")
        for col in cols:
            text, width = headings[col]
            # Click a heading to sort by that column (feature #12).
            tree.heading(col, text=text,
                         command=lambda c=col: _sort_by_column(tree, c, False))
            tree.column(col, width=width, anchor="w")
        _apply_status_row_colours(tree)  # feature #13
        tree.tag_configure("archived", foreground="#999")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for e in page_rows:
            tree.insert("", "end", iid=str(e.enrolment_id),
                        tags=("archived",) if e.is_archived else (e.status,),
                        values=(
                e.enrolment_id, e.student_id,
                names.get(e.student_id, "—"),
                e.academic_year, e.year_group, e.tutor_group or "—",
                e.start_date or "—",
                f"{e.status} (archived)" if e.is_archived else e.status,
            ))

        # ── Pager controls (only when more than one page) ──
        if pages > 1:
            def _go(delta: int) -> None:
                page["idx"] += delta
                refresh()

            ttk.Button(pager_holder, text="‹ Prev", command=lambda: _go(-1),
                       state=("disabled" if page["idx"] == 0 else "normal")
                       ).pack(side="left", padx=(0, 6))
            ttk.Label(pager_holder,
                      text=f"Page {page['idx'] + 1} / {pages}").pack(side="left")
            ttk.Button(pager_holder, text="Next ›", command=lambda: _go(1),
                       state=("disabled" if page["idx"] >= pages - 1 else "normal")
                       ).pack(side="left", padx=(6, 0))

        shown = f"{len(page_rows)} of {total}" if pages > 1 else str(total)
        summary.configure(text=f"Showing {shown} enrolment(s).")

        def _selected_ids() -> list[int]:
            return [int(i) for i in tree.selection()]

        def _selected() -> int | None:
            ids = _selected_ids()
            return ids[0] if ids else None

        def _selected_student() -> str | None:
            eid = _selected()
            e = data.get_enrolment(eid) if eid is not None else None
            return e.student_id if e else None

        def _require() -> int | None:
            eid = _selected()
            if eid is None:
                messagebox.showinfo("No selection",
                                    "Pick an enrolment row first.",
                                    parent=gui.root)
            return eid

        def _require_many() -> list[int]:
            ids = _selected_ids()
            if not ids:
                messagebox.showinfo("No selection",
                                    "Pick one or more enrolment rows first.",
                                    parent=gui.root)
            return ids

        def _on_selected_student(fn: Callable[[str], None]) -> None:
            eid = _require()
            if eid is None:
                return
            e = data.get_enrolment(eid)
            if e is not None:
                fn(e.student_id)

        def _reenrol() -> None:
            _on_selected_student(lambda sid: open_reenrol_student(gui, sid))

        def _history() -> None:
            _on_selected_student(lambda sid: open_student_enrolment_history(gui, sid))

        # Feature #43 — keyboard shortcuts on the directory tree.
        _add_keyboard_shortcuts(gui, tree, {
            "view":   lambda: _selected() is not None and open_profile(gui, _selected()),
            "edit":   lambda: _selected() is not None and open_edit_enrolment(gui, _selected()),
            "delete": lambda: _require() is not None and _delete_with_confirm(gui, _selected()),
            "new":    lambda: open_add_enrolment(gui),
            "refresh": refresh,
        })
        can_write = data.can_write()
        w_state = "normal" if can_write else "disabled"

        def _one(fn: Callable[[Any, int], Any]) -> Callable[[], Any]:
            return lambda: _require() is not None and fn(gui, _selected())

        # Feature #44 — right-click context menu (write items greyed out
        # for an account that can only view enrolments).
        _add_context_menu(gui, tree, {
            "View":            lambda: _selected() is not None and open_profile(gui, _selected()),
            "Edit":            lambda: _selected() is not None and open_edit_enrolment(gui, _selected()),
            "Withdraw":        lambda: _selected() is not None and _confirm_and_withdraw(gui, _selected()),
            "Reinstate":       _one(reinstate_with_reason),
            "Reopen":          _one(reopen_with_reason),
            "Withdraw / Reinstate (toggle)":
                lambda: _selected() is not None and _soft_delete_toggle(gui, _selected()),
            "Archive / Restore (toggle)": _one(archive_toggle),
            "Duplicate":       lambda: _selected() is not None and _duplicate_enrolment(gui, _selected()),
            "Transfer to…":    lambda: _selected() is not None and open_transfer_enrolment(gui, _selected()),
            "Return intention…": lambda: open_bulk_return_intention(gui, _require_many()),
            "History":         _one(lambda g, eid: open_profile(g, eid)),
            "Copy to clipboard": lambda: _selected() is not None and copy_enrolment_to_clipboard(gui, _selected()),
            "Print PDF":       lambda: _selected() is not None and export_enrolment_pdf(gui, _selected()),
            "Delete":          lambda: _require() is not None and _delete_with_confirm(gui, _selected()),
            "Restore":         lambda: restore_enrolments(gui, _require_many()),
        }, disabled=set() if can_write else {
            "Edit", "Withdraw", "Reinstate", "Reopen",
            "Withdraw / Reinstate (toggle)", "Archive / Restore (toggle)",
            "Duplicate", "Transfer to…", "Return intention…", "Delete",
            "Restore"})

        def btn(bar, text: str, command, *, write: bool = False) -> None:
            ttk.Button(bar, text=text, command=command,
                       state=w_state if write else "normal"
                       ).pack(side="left", padx=(0, 6))

        # ── Record actions (single selection) ──
        a1 = ttk.Frame(actions_holder)
        a1.pack(anchor="w")
        btn(a1, "View", lambda: (_require() is not None and open_profile(gui, _selected())))
        btn(a1, "Edit", lambda: (_require() is not None
                                 and open_edit_enrolment(gui, _selected())), write=True)
        btn(a1, "Delete", lambda: (_require() is not None
                                   and _delete_with_confirm(gui, _selected())), write=True)
        btn(a1, "Withdraw", lambda: (_require() is not None
                                     and _confirm_and_withdraw(gui, _selected())), write=True)
        btn(a1, "Reinstate", _one(reinstate_with_reason), write=True)
        btn(a1, "Reopen", _one(reopen_with_reason), write=True)
        btn(a1, "Duplicate", lambda: (_require() is not None
                                      and _duplicate_enrolment(gui, _selected())), write=True)
        btn(a1, "Re-enrol", _reenrol, write=True)
        btn(a1, "Transfer…", _one(open_transfer_enrolment), write=True)
        btn(a1, "Restore", lambda: restore_enrolments(gui, _require_many()), write=True)
        btn(a1, "Print PDF", _one(export_enrolment_pdf))
        btn(a1, "Copy", _one(copy_enrolment_to_clipboard))

        # ── Bulk / workflow actions (multi-selection) ──
        a2 = ttk.Frame(actions_holder)
        a2.pack(anchor="w", pady=(4, 0))
        btn(a2, "New Enrolment", lambda: open_add_enrolment(gui), write=True)
        btn(a2, "Bulk Enrol", lambda: open_bulk_enrol(gui), write=True)
        btn(a2, "Progression Wizard", lambda: open_progression_wizard(gui))
        btn(a2, "End-of-Year Rollover", lambda: open_end_of_year_rollover(gui))
        btn(a2, "Rollover History", lambda: open_rollover_history(gui))
        btn(a2, "Return Intentions", lambda: open_return_intentions(
            gui, fvars["academic_year"].get().strip() or None))
        btn(a2, "Set Status…", lambda: open_bulk_status_change(gui, _require_many()),
            write=True)
        btn(a2, "Reassign Tutor…", lambda: open_bulk_tutor_reassign(gui, _require_many()),
            write=True)
        btn(a2, "Delete Selected", lambda: _confirm_bulk_delete(gui, _require_many()),
            write=True)
        btn(a2, "Refresh", refresh)

        # ── Reports & analytics ──
        a3 = ttk.Frame(actions_holder)
        a3.pack(anchor="w", pady=(4, 0))
        def _report(label, draw):
            # Drawn here; "Open in new window" (above the page) re-opens it.
            return lambda: popout.show_page(gui, label, draw)

        def _year():
            return fvars["academic_year"].get().strip() or None

        btn(a3, "Dashboard", _report("Enrolment Dashboard",
                                     open_enrolment_dashboard))
        btn(a3, "Cohort Report", lambda: popout.show_page(
            gui, "Cohort Report",
            lambda g, y=_year(): open_cohort_report(g, y)))
        btn(a3, "Retention", _report("Retention", open_retention_report))
        btn(a3, "Withdrawals", _report("Withdrawals",
                                       open_withdrawal_analysis))
        btn(a3, "Year-on-Year", _report("Year-on-Year",
                                        open_year_on_year_comparison))
        btn(a3, "Tutor Group Roster", lambda: open_tutor_group_roster_picker(
            gui, _year()))
        btn(a3, "Capacity", lambda: popout.show_page(
            gui, "Capacity",
            lambda g, y=_year(): open_capacity_utilisation(g, y)))
        btn(a3, "Student History", _history)
        btn(a3, "Advanced Query", lambda: open_advanced_query(gui))

        # ── Data tools ──
        a4 = ttk.Frame(actions_holder)
        a4.pack(anchor="w", pady=(4, 0))
        btn(a4, "Export CSV", lambda: export_directory_csv(gui, rows, names))
        btn(a4, "Import CSV", lambda: import_enrolments_csv(gui), write=True)
        btn(a4, "Export Progression", lambda: export_progression_list(gui))
        btn(a4, "No Enrolment", lambda: _highlight_students_without_enrolment(gui))
        btn(a4, "Conflicts", lambda: _highlight_duplicate_conflicts(gui))
        btn(a4, "Academic Years", lambda: open_academic_year_manager(gui))
        btn(a4, f"Undo ({len(_UNDO_STACK)})", lambda: open_undo_last_action(gui),
            write=True)
        btn(a4, "Photo & ID checks", lambda: _open_identity_checks(gui, _selected_student()))
        _directory_wave2_rows(gui, actions_holder, btn,
                              lambda: fvars["academic_year"].get().strip() or None,
                              _selected, _selected_student)

        tree.bind("<Double-1>",
                  lambda _e: (_selected() is not None and open_profile(gui, _selected())))

        gui.status_var.set(f"Enrolments: {total} match(es)")

    # ── Filter bar (two rows) ──
    r1 = ttk.Frame(filt)
    r1.pack(anchor="w", fill="x")
    ttk.Label(r1, text="Academic year:").pack(side="left")
    year_box = ttk.Combobox(r1, textvariable=fvars["academic_year"],
                            values=["", *_year_choices()], state="readonly", width=10)
    year_box.pack(side="left", padx=(4, 12))
    year_box.bind("<<ComboboxSelected>>", lambda _e: refresh())
    ttk.Label(r1, text="Year group:").pack(side="left")
    ttk.Combobox(
        r1, textvariable=fvars["year_group"],
        values=["", *[str(y) for y in YEAR_GROUPS]],
        state="readonly", width=6,
    ).pack(side="left", padx=(4, 12))
    ttk.Label(r1, text="Status:").pack(side="left")
    ttk.Combobox(
        r1, textvariable=fvars["status"],
        values=["", *STATUSES], state="readonly", width=12,
    ).pack(side="left", padx=(4, 12))
    ttk.Label(r1, text="Archived:").pack(side="left")
    arch_box = ttk.Combobox(r1, textvariable=fvars["archived"],
                            values=["Hide", "Include", "Only"],
                            state="readonly", width=8)
    arch_box.pack(side="left", padx=(4, 12))
    arch_box.bind("<<ComboboxSelected>>", lambda _e: refresh())
    ttk.Button(r1, text="This Year",
               command=lambda: _quick_filter_current_year(fvars, refresh)
               ).pack(side="left", padx=(4, 0))

    r2 = ttk.Frame(filt)
    r2.pack(anchor="w", fill="x", pady=(4, 0))
    _add_tutor_group_filter(r2, fvars, refresh)   # feature #10
    _add_student_search_box(r2, fvars, refresh)   # feature #9
    _add_date_range_filter(r2, fvars, refresh)    # feature #11

    def _current_filter() -> dict[str, str]:
        return {k: v.get() for k, v in fvars.items()}

    def _apply_preset(values: dict[str, str]) -> None:
        for k, v in fvars.items():
            v.set(values.get(k, ""))
        refresh()

    def _clear_filters() -> None:
        for v in fvars.values():
            v.set("")
        refresh()

    ttk.Button(r2, text="Apply", command=refresh).pack(side="left", padx=(8, 0))
    ttk.Button(r2, text="Clear", command=_clear_filters).pack(side="left", padx=(4, 0))
    ttk.Button(r2, text="Presets…",
               command=lambda: open_saved_filter_manager(
                   gui, current=_current_filter, on_apply=_apply_preset)
               ).pack(side="left", padx=(4, 0))

    refresh()


def _directory_wave2_rows(gui, holder, btn, year: Callable[[], str | None],
                          selected: Callable[[], int | None],
                          selected_student: Callable[[], str | None]) -> None:
    """Funding / ILR / reports and enrolment-day / checks rows."""
    from . import enrolment_agreements_views as agreements_v
    from . import enrolment_checks_views as checks_v
    from . import enrolment_course_change_views as course_v
    from . import enrolment_day_views as day_v
    from . import enrolment_funding_views as funding_v
    from . import enrolment_ilr_views as ilr_v
    from . import enrolment_targets_views as targets_v

    def one(fn: Callable[[int], Any]) -> Callable[[], Any]:
        def go() -> None:
            eid = selected()
            if eid is None:
                messagebox.showinfo("Enrolments", "Select an enrolment first.",
                                    parent=gui.root)
                return
            fn(eid)
        return go

    a5 = ttk.Frame(holder)
    a5.pack(anchor="w", pady=(4, 0))
    btn(a5, "ILR Record", one(lambda eid: ilr_v.open_ilr_record(gui, eid)))
    btn(a5, "ILR Export", lambda: ilr_v.open_ilr_export(gui, year()))
    btn(a5, "Early Leavers", lambda: ilr_v.open_early_leavers(gui, year()))
    btn(a5, "Funding & Fees", one(lambda eid: funding_v.open_funding_and_fees(gui, eid)))
    btn(a5, "Condition of Funding", lambda: funding_v.open_cof_report(gui, year()))
    ttk.Button(a5, text="Fee Rates", command=lambda: funding_v.open_fee_rates(gui, year()),
               state="normal" if funding_v.can_fees() else "disabled"
               ).pack(side="left", padx=(0, 6))
    btn(a5, "Targets", lambda: targets_v.open_targets(gui, year()))
    btn(a5, "Withdrawal Analytics", lambda: targets_v.open_withdrawal_breakdown(gui, year()))
    btn(a5, "Status Counts", lambda: targets_v.open_status_counts(gui, year()))

    a6 = ttk.Frame(holder)
    a6.pack(anchor="w", pady=(4, 0))
    btn(a6, "Enrolment Day", lambda: day_v.open_enrolment_day_board(gui, year()))
    btn(a6, "Agreements", one(lambda eid: agreements_v.open_agreements(gui, eid)))
    btn(a6, "Agreements Outstanding",
        lambda: agreements_v.open_agreements_outstanding(gui, year()))
    btn(a6, "Change Course…", one(lambda eid: course_v.open_change_course(gui, eid)),
        write=True)
    btn(a6, "Course Changes", lambda: course_v.open_course_change_log(gui, year()))
    btn(a6, "Settings", lambda: course_v.open_enrolment_settings(gui))
    btn(a6, "Confirmation Wording", lambda: day_v.open_confirmation_template(gui))
    btn(a6, "Class Sizes", lambda: checks_v.open_class_sizes(gui, year()))
    btn(a6, "Tutor Group Sizes", lambda: checks_v.open_tutor_group_sizes(gui))
    btn(a6, "Timetable", lambda: checks_v.open_learner_timetable(gui, selected_student()))
    btn(a6, "Data Check", lambda: checks_v.open_data_check(gui))


def _open_identity_checks(gui, student_id: str | None) -> None:
    """Photo / ID-document check window (identity_checks_views)."""
    from education_system.systems.sixth_form.interfaces.gui.admissions.enrolments.identity_checks_views import (
        open_identity_checks_window,
    )
    open_identity_checks_window(getattr(gui, "root", gui), student_id=student_id)


# ── Profile / delete ────────────────────────────────────────────────

def open_profile(gui, enrolment_id: int) -> None:
    frame = _clear(gui)
    _heading(frame, f"Enrolment #{enrolment_id}")

    try:
        e = data.get_enrolment(enrolment_id)
    except Exception as exc:
        logger.exception("Failed to load enrolment %d", enrolment_id)
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    if e is None:
        ttk.Label(frame, text="No such enrolment.", foreground="#a33").pack(anchor="w")
        return

    student = student_data.get_student(e.student_id)

    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(8, 0))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(grid, text=label + ":", foreground="#555",
                  width=20, anchor="e").grid(row=row, column=0, sticky="e",
                                              pady=2, padx=(0, 8))
        ttk.Label(grid, text=value or "—").grid(row=row, column=1, sticky="w", pady=2)

    field(0, "Student", f"{e.student_id} — {student.full_name if student else '(deleted)'}")
    field(1, "Academic year", e.academic_year)
    field(2, "Year group", f"Year {e.year_group}")
    field(3, "Tutor group", e.tutor_group or "—")
    field(4, "Start date", e.start_date or "—")
    field(5, "Status", e.status)
    field(6, "Created", e.created_at
          + (f" by {e.recorded_by}" if e.recorded_by else ""))
    nxt = 7
    if e.status == "Withdrawn":
        field(nxt, "Withdrawn", " — ".join(x for x in (
            e.withdrawal_date, e.withdrawal_reason_label, e.withdrawal_detail,
            f"by {e.withdrawn_by}" if e.withdrawn_by else None) if x))
        nxt += 1
    if e.is_archived:
        field(nxt, "Archived", " — ".join(x for x in (
            e.archived_at, e.archived_reason,
            f"by {e.archived_by}" if e.archived_by else None) if x))
        nxt += 1
    if e.completed_at:
        field(nxt, "Completed", e.completed_at)
        nxt += 1
    if e.year_group == 12 or e.return_intention:
        field(nxt, "Return for Year 13", (e.return_intention or "Not answered")
              + (f" — {e.return_intention_note}" if e.return_intention_note else ""))
        nxt += 1
    if e.notes:
        ttk.Separator(grid, orient="horizontal").grid(
            row=nxt, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(grid, text="Notes:", foreground="#555",
                  width=20, anchor="e").grid(row=nxt + 1, column=0, sticky="ne", padx=(0, 8))
        ttk.Label(grid, text=e.notes, wraplength=520, justify="left").grid(
            row=nxt + 1, column=1, sticky="w")

    w = data.can_write()

    def state(ok: bool) -> str:
        return "normal" if w and ok else "disabled"

    back = lambda: open_profile(gui, e.enrolment_id)  # noqa: E731
    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Edit", state=state(not e.is_archived),
               command=lambda: open_edit_enrolment(gui, e.enrolment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete", state=state(not e.is_archived),
               command=lambda: _delete_with_confirm(gui, e.enrolment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Withdraw…",
               command=lambda: _confirm_and_withdraw(gui, e.enrolment_id, back),
               state=state(e.is_live)).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Reinstate…",
               command=lambda: reinstate_with_reason(gui, e.enrolment_id, back),
               state=state(e.status == "Withdrawn" and not e.is_archived)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Reopen…",
               command=lambda: reopen_with_reason(gui, e.enrolment_id, back),
               state=state(e.status == "Completed" and not e.is_archived)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Restore",
               command=lambda: restore_enrolments(gui, [e.enrolment_id]),
               state=state(e.is_archived)
               ).pack(side="left", padx=(0, 6))
    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(4, 0))
    ttk.Button(actions, text="Transfer…",
               command=lambda: open_transfer_enrolment(gui, e.enrolment_id),
               state=state(not e.is_archived)).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Return Intention…",
               command=lambda: open_bulk_return_intention(gui, [e.enrolment_id], back),
               state=state(not e.is_archived)).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Print PDF",
               command=lambda: export_enrolment_pdf(gui, e.enrolment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Copy",
               command=lambda: copy_enrolment_to_clipboard(gui, e.enrolment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Student History",
               command=lambda: open_student_enrolment_history(gui, e.student_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")
    _profile_wave2_actions(gui, frame, e, state)
    warnings_section(frame, e.student_id, e.academic_year)

    ttk.Label(frame, text="History of this enrolment", font=("", 11, "bold")
              ).pack(anchor="w", pady=(14, 2))
    try:
        trail = data.enrolment_history(enrolment_id=e.enrolment_id)
    except Exception as exc:  # noqa: BLE001 — shown in place
        logger.exception("History of enrolment %d not read", e.enrolment_id)
        trail = []
        ttk.Label(frame, text=f"History not read: {exc}", foreground="#a33").pack(anchor="w")
    if trail:
        audit_table(frame, trail, height=8, show_enrolment=False)
    else:
        ttk.Label(frame, text="No changes recorded yet.", foreground="#777").pack(anchor="w")
    gui.status_var.set(f"Viewing enrolment #{enrolment_id}")


def _profile_wave2_actions(gui, frame, e: Enrolment, state: Callable[[bool], str]) -> None:
    """ILR, funding and fees, course change, agreements and enrolment-day
    actions for one enrolment."""
    from . import enrolment_agreements_views as agreements_v
    from . import enrolment_checks_views as checks_v
    from . import enrolment_day_views as day_v
    from . import enrolment_funding_views as funding_v
    from . import enrolment_ilr_views as ilr_v
    from .enrolment_course_change_views import open_change_course
    eid, sid = e.enrolment_id, e.student_id
    row = ttk.Frame(frame)
    row.pack(anchor="w", pady=(4, 0))
    for text, command, st in (
            ("ILR Record", lambda: ilr_v.open_ilr_record(gui, eid), "normal"),
            ("Funding & Fees", lambda: funding_v.open_funding_and_fees(gui, eid), "normal"),
            ("Change Course…", lambda: open_change_course(
                gui, eid, lambda: open_profile(gui, eid)), state(e.is_live)),
            ("Agreements", lambda: agreements_v.open_agreements(gui, eid), "normal"),
            ("Enrolment Day Status", lambda: day_v.open_learner_status(
                gui, sid, e.academic_year), "normal"),
            ("Confirmation…", lambda: day_v.show_confirmation(gui, eid), "normal"),
            ("ID Card…", lambda: day_v.open_id_card(gui, sid), "normal"),
            ("Timetable", lambda: checks_v.open_learner_timetable(gui, sid), "normal"),
            ("Data Check", lambda: checks_v.open_data_check(gui, sid), "normal")):
        ttk.Button(row, text=text, command=command, state=st).pack(side="left", padx=(0, 6))


# ── Record-level workflow actions ───────────────────────────────────


def _duplicate_enrolment(gui, enrolment_id: int) -> None:
    """Feature #7 — open the add form pre-filled from an existing enrolment,
    rolled forward one academic year (and Year 12 → 13)."""
    e = data.get_enrolment(enrolment_id)
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    yg = 13 if e.year_group == 12 else e.year_group
    open_add_enrolment(
        gui, preselect_student_id=e.student_id,
        preset_year=_next_academic_year(e.academic_year), preset_year_group=yg)


def open_reenrol_student(gui, student_id: str) -> None:
    """Feature #6 — quick re-enrol: add form pre-filled with the student's
    next academic year (and next year group where sensible)."""
    latest = data.current_enrolment(student_id)
    if latest is not None:
        year = _next_academic_year(latest.academic_year)
        yg = 13 if latest.year_group == 12 else latest.year_group
    else:
        year, yg = _default_academic_year(), YEAR_GROUPS[0]
    open_add_enrolment(
        gui, preselect_student_id=student_id,
        preset_year=year, preset_year_group=yg)


# ── Saved filter presets UI ─────────────────────────────────────────

def open_saved_filter_manager(
    gui,
    *,
    current: Callable[[], dict[str, str]] | None = None,
    on_apply: Callable[[dict[str, str]], None] | None = None,
) -> None:
    """Feature #14 — manage named filter presets. ``current`` supplies the
    live filter values to save; ``on_apply`` applies a chosen preset."""
    dlg = make_toplevel(gui.root)
    dlg.title("Filter Presets")
    dlg.transient(gui.root)
    dlg.grab_set()

    presets = _load_presets()
    ttk.Label(dlg, text="Saved filter presets",
              font=("", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 6))
    lb = tk.Listbox(dlg, height=8, width=32)
    lb.pack(padx=12, fill="x")

    def reload() -> None:
        lb.delete(0, "end")
        for name in sorted(presets):
            lb.insert("end", name)

    reload()

    def selected_name() -> str | None:
        sel = lb.curselection()
        return lb.get(sel[0]) if sel else None

    def apply() -> None:
        name = selected_name()
        if name and on_apply:
            on_apply(presets[name])
            dlg.destroy()

    def delete() -> None:
        name = selected_name()
        if name and messagebox.askyesno(
                "Delete preset", f"Delete preset '{name}'?", parent=dlg):
            presets.pop(name, None)
            _save_presets(presets)
            reload()

    def save_current() -> None:
        if current is None:
            return
        name = simpledialog.askstring(
            "Save preset", "Name for this filter preset:", parent=dlg)
        if not name or not name.strip():
            return
        presets[name.strip()] = current()
        _save_presets(presets)
        reload()

    bar = ttk.Frame(dlg)
    bar.pack(anchor="w", padx=12, pady=12)
    if on_apply:
        ttk.Button(bar, text="Apply", command=apply).pack(side="left", padx=(0, 6))
    if current is not None:
        ttk.Button(bar, text="Save current…",
                   command=save_current).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Delete", command=delete).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Close", command=dlg.destroy).pack(side="left")


# ════════════════════════════════════════════════════════════════════
# Features 16–50
# ════════════════════════════════════════════════════════════════════

# ── Small reusable UI helpers ───────────────────────────────────────


def _add_keyboard_shortcuts(gui, tree, actions: dict[str, Callable[[], None]]) -> None:
    """Feature #43 — Return=view, Ctrl-E=edit, Delete=delete, Ctrl-N=new,
    F5=refresh. Bound to the directory tree so they fire when it has focus."""
    binds = {
        "<Return>": actions.get("view"),
        "<Control-e>": actions.get("edit"),
        "<Delete>": actions.get("delete"),
        "<Control-n>": actions.get("new"),
        "<F5>": actions.get("refresh"),
    }
    for seq, fn in binds.items():
        if fn is not None:
            tree.bind(seq, lambda _e, f=fn: f())


def _add_context_menu(gui, tree, items: dict[str, Callable[[], None]],
                      disabled: set[str] | None = None) -> tk.Menu:
    """Feature #44 — right-click menu on the directory tree; labels in
    ``disabled`` stay listed but greyed out."""
    menu = tk.Menu(tree, tearoff=0)
    for label, fn in items.items():
        if label.startswith("—"):
            menu.add_separator()
        else:
            menu.add_command(label=label, command=fn,
                             state="disabled" if label in (disabled or ()) else "normal")

    def popup(event) -> None:
        row = tree.identify_row(event.y)
        if row:
            tree.selection_set(row)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    tree.bind("<Button-3>", popup)       # right-click (Win/Linux)
    tree.bind("<Button-2>", popup)       # middle/right (macOS trackpad)
    tree._context_menu = menu            # type: ignore[attr-defined]  # for checks
    return menu


# ── Live form validation & autofill (features 36–38) ────────────────

def _colour_entry(entry, var, matcher) -> None:
    def check(*_a) -> None:
        val = var.get().strip()
        if not val:
            entry.configure(foreground="black")
        elif matcher(val):
            entry.configure(foreground="#1a7a1a")
        else:
            entry.configure(foreground="#a33333")
    var.trace_add("write", check)
    check()


def _live_validate_start_date(entry, var) -> None:
    """Feature #37 — green when the date matches ``YYYY-MM-DD``, red otherwise."""
    _colour_entry(entry, var, lambda v: bool(enrolments._DATE_RE.match(v)))


def _autofill_tutor_group_from_year(yg_var, tg_var) -> None:
    """Feature #38 — when the year group changes, bump the tutor-group prefix
    (e.g. 12A → 13A) so it follows the student. No-op if the tutor field is
    empty or has no leading-digit prefix."""
    prev = getattr(yg_var, "_prev_yg", None)
    try:
        new = int(yg_var.get())
    except (ValueError, TypeError):
        return
    cur = (tg_var.get() or "").strip()
    if cur and prev is not None and prev != new:
        bumped = enrolments._bump_tutor_group(prev, new, cur)
        if bumped and bumped != cur:
            tg_var.set(bumped)
    yg_var._prev_yg = new  # type: ignore[attr-defined]


# ── Unsaved-changes guard & delete safety (features 39–41) ──────────

def _warn_on_unsaved_changes(gui, dirty: bool) -> bool:
    """Feature #39 — returns True if it's safe to leave the form."""
    if not dirty:
        return True
    return messagebox.askyesno(
        "Unsaved changes",
        "You have unsaved changes. Discard them?",
        parent=gui.root)


# ── Student-centric deep link (feature 46) ──────────────────────────

def open_enrolment_from_student_profile(gui, student_id: str) -> None:
    """Feature #46 — deep-link used by the student profile's 'Enrol' button."""
    open_add_enrolment(gui, preselect_student_id=student_id)


def open_advanced_query(gui) -> None:
    """Feature #20 — combine several conditions with AND / OR logic."""
    frame = _clear(gui)
    _heading(frame, "Advanced Enrolment Query")

    mode_var = tk.StringVar(value="AND")
    y_var = tk.StringVar()
    yg_var = tk.StringVar()
    st_var = tk.StringVar()
    tg_var = tk.StringVar()

    ctrl = ttk.Frame(frame)
    ctrl.pack(anchor="w", pady=(0, 6))
    ttk.Label(ctrl, text="Match").pack(side="left")
    ttk.Combobox(ctrl, textvariable=mode_var, values=["AND", "OR"],
                 state="readonly", width=5).pack(side="left", padx=(4, 12))
    ttk.Label(ctrl, text="of these conditions:").pack(side="left")

    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(0, 6))

    def crow(r: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(grid, text=label).grid(row=r, column=0, sticky="e", padx=(0, 6), pady=3)
        widget.grid(row=r, column=1, sticky="w", pady=3)

    crow(0, "Academic year =", ttk.Combobox(grid, textvariable=y_var, state="readonly",
                                           values=["", *_year_choices()], width=10))
    crow(1, "Year group =", ttk.Combobox(
        grid, textvariable=yg_var, values=["", *[str(y) for y in YEAR_GROUPS]],
        state="readonly", width=6))
    crow(2, "Status =", ttk.Combobox(
        grid, textvariable=st_var, values=["", *STATUSES], state="readonly", width=12))
    crow(3, "Tutor contains", ttk.Entry(grid, textvariable=tg_var, width=12))

    result_holder = ttk.Frame(frame)
    result_holder.pack(anchor="w", fill="both", expand=True, pady=(6, 0))

    def run() -> None:
        for w in result_holder.winfo_children():
            w.destroy()
        conds: list[Callable[[Enrolment], bool]] = []
        if y_var.get().strip():
            conds.append(lambda e, v=y_var.get().strip(): e.academic_year == v)
        if yg_var.get():
            conds.append(lambda e, v=int(yg_var.get()): e.year_group == v)
        if st_var.get():
            conds.append(lambda e, v=st_var.get(): e.status == v)
        if tg_var.get().strip():
            conds.append(lambda e, v=tg_var.get().strip().lower():
                         v in (e.tutor_group or "").lower())
        rows = data.list_enrolments()
        if conds:
            combine = all if mode_var.get() == "AND" else any
            rows = [e for e in rows if combine(c(e) for c in conds)]
        names = _student_name_map()
        cols = ("id", "sid", "name", "year", "yg", "status")
        tree = ttk.Treeview(result_holder, columns=cols, show="headings", height=12)
        for col, (text, w) in {
            "id": ("#", 50), "sid": ("Student", 90), "name": ("Name", 180),
            "year": ("Year", 80), "yg": ("YG", 50), "status": ("Status", 100),
        }.items():
            tree.heading(col, text=text)
            tree.column(col, width=w)
        _apply_status_row_colours(tree)
        tree.pack(anchor="w", fill="x")
        for e in rows:
            tree.insert("", "end", tags=(e.status,), values=(
                e.enrolment_id, e.student_id, names.get(e.student_id, "—"),
                e.academic_year, e.year_group, e.status))
        gui.status_var.set(f"Advanced query: {len(rows)} match(es)")

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(6, 0))
    ttk.Button(bar, text="Run Query", command=run).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")


# ── Academic years (feature 50) ─────────────────────────────────────

def _open_year_register(gui) -> None:
    """The academic year register (Academic Year & Calendar window), which
    is where years are set up — the enrolment pickers read it."""
    from education_system.systems.sixth_form.interfaces.gui.academics.academic_year import (
        academic_year_window,
    )
    academic_year_window.open_academic_year_window(gui)


def open_academic_year_manager(gui) -> None:
    """Feature #50 — the academic years the enrolment form and filters
    offer: those set up in the academic year register plus any already in
    use. Years are added in the register, not here."""
    frame = _clear(gui)
    _heading(frame, "Academic Years")
    ttk.Label(
        frame, foreground="#555", wraplength=900, justify="left",
        text="The enrolment form, filters and rollover offer these years: "
             "the academic year register's years plus any already used by an "
             "enrolment. Set up or change a year (its dates, terms and which "
             "one is current) in the academic year register.").pack(
        anchor="w", pady=(0, 6))
    try:
        years = _year_choices()
        current = _default_academic_year()
        rows = data.list_enrolments(include_archived=True)
    except Exception as exc:  # noqa: BLE001 — shown
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        years, current, rows = [], "", []
    in_use: dict[str, int] = {}
    for e in rows:
        in_use[e.academic_year] = in_use.get(e.academic_year, 0) + 1

    bar = ttk.Frame(frame)
    bar.pack(side="bottom", anchor="w", pady=(10, 0))
    tree = ttk.Treeview(frame, columns=("year", "dates", "current", "count"),
                        show="headings", height=12)
    for col, text, width in (("year", "Academic year", 110), ("dates", "Dates", 220),
                             ("current", "Current", 80), ("count", "Enrolments", 90)):
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="w")
    tree.pack(anchor="w", fill="y", expand=True)
    for y in years:
        try:
            first, last = data.academic_year_dates(y)
            dates = f"{first} – {last}"
        except ValueError:
            dates = "—"
        tree.insert("", "end", values=(y, dates, "Yes" if y == current else "",
                                       in_use.get(y, 0)))
    ttk.Button(bar, text="Open Academic Year Register…",
               command=lambda: _open_year_register(gui)).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Refresh",
               command=lambda: open_academic_year_manager(gui)).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set("Academic years")
