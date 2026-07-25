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
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    DEFAULT_STATUS,
    Enrolment,
    STATUSES,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


# ── Internal helpers ────────────────────────────────────────────────

def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _default_academic_year() -> str:
    """Compute the current sixth-form academic year (e.g. '2025/26').

    Rolls over on 1 August (a sensible UK academic-year start).
    """
    today = date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def _next_academic_year(academic_year: str) -> str:
    """'2025/26' -> '2026/27'. Falls back to next year after the computed
    current year if the input isn't in the expected ``YYYY/YY`` form."""
    try:
        start = int((academic_year or "").split("/")[0]) + 1
    except (ValueError, IndexError):
        start = int(_default_academic_year().split("/")[0]) + 1
    return f"{start}/{str(start + 1)[-2:]}"


def _enrolment_to_payload(e: Enrolment, **overrides: Any) -> dict[str, Any]:
    """Build an ``update_enrolment`` payload from an existing record, with
    optional field overrides. ``student_id`` is immutable so it's omitted."""
    payload: dict[str, Any] = {
        "academic_year": e.academic_year,
        "year_group": e.year_group,
        "tutor_group": e.tutor_group,
        "start_date": e.start_date,
        "status": e.status,
        "notes": e.notes,
    }
    payload.update(overrides)
    return payload


# ── Saved filter presets (persisted as JSON in the data dir) ─────────

from education_system.systems.sixth_form.infrastructure import paths as _paths

_PRESETS_PATH = _paths.DATA_DIR / "enrolment_filter_presets.json"


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
        _paths.ensure_directories()
        with open(_PRESETS_PATH, "w", encoding="utf-8") as fh:
            json.dump(presets, fh, indent=2)
    except Exception:
        logger.exception("Could not write enrolment filter presets")


def _report_bulk(gui, title: str, ok: list[str], fail: list[str]) -> None:
    """Summarise a bulk operation's outcome, then return to the directory."""
    lines = [f"{len(ok)} succeeded, {len(fail)} failed."]
    if fail:
        lines.append("")
        lines.extend(fail[:15])
        if len(fail) > 15:
            lines.append(f"…and {len(fail) - 15} more.")
    show = messagebox.showinfo if not fail else messagebox.showwarning
    show(title, "\n".join(lines), parent=gui.root)
    gui.status_var.set(f"{title}: {len(ok)} ok, {len(fail)} failed")
    open_directory(gui)


def _choose_from(gui, title: str, prompt: str,
                 options: list[str], default: str | None = None) -> str | None:
    """Modal combobox picker. Returns the chosen value, or None if cancelled."""
    dlg = tk.Toplevel(gui.root)
    dlg.title(title)
    dlg.transient(gui.root)
    dlg.grab_set()
    ttk.Label(dlg, text=prompt).pack(anchor="w", padx=12, pady=(12, 6))
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(dlg, textvariable=var, values=options,
                 state="readonly", width=24).pack(padx=12)
    result: dict[str, str | None] = {"val": None}

    def ok() -> None:
        result["val"] = var.get()
        dlg.destroy()

    bar = ttk.Frame(dlg)
    bar.pack(anchor="e", padx=12, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="left")
    dlg.wait_window()
    return result["val"]


# ── Form (add + edit) ───────────────────────────────────────────────

def _enrolment_form(
    gui,
    *,
    title: str,
    existing: Enrolment | None,
    preselect_student_id: str | None,
    on_save: Callable[[dict[str, Any]], Enrolment],
    preset_year: str | None = None,
    preset_year_group: int | None = None,
) -> None:
    frame = _clear(gui)
    _heading(frame, title)

    is_edit = existing is not None

    try:
        students = student_data.list_students()
    except Exception:
        logger.exception("Could not load student list for enrolment form")
        students = []
    if not students and not is_edit:
        ttk.Label(
            frame,
            text="No students on the roll yet — add a student first.",
            foreground="#a33",
        ).pack(anchor="w")
        ttk.Button(
            frame, text="Back to Enrolments",
            command=lambda: open_directory(gui),
        ).pack(anchor="w", pady=(8, 0))
        return

    # ── Variables ──
    student_choices = [f"{s.student_id} — {s.full_name}" for s in students]
    student_lookup = {f"{s.student_id} — {s.full_name}": s.student_id for s in students}

    if is_edit:
        student_disp = next(
            (lbl for lbl, sid in student_lookup.items() if sid == existing.student_id),
            existing.student_id,
        )
    elif preselect_student_id:
        student_disp = next(
            (lbl for lbl, sid in student_lookup.items() if sid == preselect_student_id),
            "",
        )
    else:
        student_disp = ""

    student_var = tk.StringVar(value=student_disp)
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

    student_combo = ttk.Combobox(
        form, textvariable=student_var, values=student_choices,
        state=("readonly" if not is_edit else "disabled"), width=42,
    )
    row(0, "Student *", student_combo)

    year_entry = tk.Entry(form, textvariable=year_var)
    row(1, "Academic year * (YYYY/YY)", year_entry)
    _live_validate_academic_year(year_entry, year_var)  # feature #36
    row(2, "Year group *", ttk.Combobox(
        form, textvariable=yg_var, values=[str(y) for y in YEAR_GROUPS],
        state="readonly", width=8))
    row(3, "Tutor group (auto-bumps with year, e.g. 12A → 13A)",
        ttk.Entry(form, textvariable=tg_var))
    sd_entry = tk.Entry(form, textvariable=sd_var)
    row(4, "Start date (YYYY-MM-DD)", sd_entry)
    _live_validate_start_date(sd_entry, sd_var)  # feature #37
    # Feature #38 — bump the tutor group prefix when the year group changes.
    yg_var._prev_yg = int(yg_var.get() or YEAR_GROUPS[0])  # type: ignore[attr-defined]
    yg_var.trace_add(
        "write", lambda *_: _autofill_tutor_group_from_year(yg_var, tg_var))
    row(5, "Status *", ttk.Combobox(
        form, textvariable=status_var, values=list(STATUSES),
        state="readonly", width=16))
    ttk.Label(form, text="Notes").grid(row=6, column=0, sticky="ne", padx=(0, 8), pady=4)
    notes_text.grid(row=6, column=1, sticky="ew", pady=4)
    if is_edit and existing.notes:
        notes_text.insert("1.0", existing.notes)

    # ── Buttons ──
    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))

    # Feature #39 — track edits so we can warn before discarding them.
    def _snapshot() -> tuple:
        return (student_var.get(), year_var.get(), yg_var.get(), tg_var.get(),
                sd_var.get(), status_var.get(), notes_text.get("1.0", "end"))

    _initial = _snapshot()

    def _leave() -> None:
        if _warn_on_unsaved_changes(gui, _snapshot() != _initial):
            open_directory(gui)

    def submit() -> None:
        if is_edit:
            sid = existing.student_id
        else:
            sid = student_lookup.get(student_var.get().strip())
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
        try:
            saved = on_save(payload)
        except ValidationError as e:
            logger.warning("Enrolment form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Unexpected error saving enrolment form")
            messagebox.showerror("Error", f"Unexpected error: {e}", parent=gui.root)
            return
        logger.info("GUI saved enrolment #%d via %s", saved.enrolment_id, title)
        messagebox.showinfo(
            "Saved",
            f"Enrolment #{saved.enrolment_id} saved\n"
            f"  Student : {saved.student_id}\n"
            f"  Year    : {saved.academic_year} · Year {saved.year_group}\n"
            f"  Status  : {saved.status}",
            parent=gui.root,
        )
        gui.status_var.set(f"Saved enrolment #{saved.enrolment_id}")
        open_directory(gui)

    ttk.Button(bar, text="Save", command=submit).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel", command=_leave).pack(side="left")


def open_add_enrolment(
    gui,
    preselect_student_id: str | None = None,
    *,
    preset_year: str | None = None,
    preset_year_group: int | None = None,
) -> None:
    def on_save(payload: dict[str, Any]) -> Enrolment:
        return data.create_enrolment(payload)
    _enrolment_form(
        gui, title="New Enrolment", existing=None,
        preselect_student_id=preselect_student_id, on_save=on_save,
        preset_year=preset_year, preset_year_group=preset_year_group,
    )
    gui.status_var.set("New enrolment")


def open_edit_enrolment(gui, enrolment_id: int) -> None:
    try:
        existing = data.get_enrolment(enrolment_id)
    except Exception as e:
        logger.exception("Failed to load enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not load enrolment: {e}",
                             parent=gui.root)
        return
    if existing is None:
        messagebox.showerror(
            "Not found", f"No enrolment #{enrolment_id}", parent=gui.root)
        return

    def on_save(payload: dict[str, Any]) -> Enrolment:
        return data.update_enrolment(enrolment_id, payload)

    _enrolment_form(
        gui, title=f"Edit Enrolment #{enrolment_id}",
        existing=existing, preselect_student_id=existing.student_id,
        on_save=on_save,
    )
    gui.status_var.set(f"Editing enrolment #{enrolment_id}")


# ── Directory (list + filters + actions) ────────────────────────────

def _student_name_map() -> dict[str, str]:
    try:
        return {s.student_id: s.full_name for s in student_data.list_students()}
    except Exception:
        logger.exception("Could not build student name map")
        return {}


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
        "academic_year": tk.StringVar(),
        "year_group":    tk.StringVar(),
        "status":        tk.StringVar(),
        "tutor_group":   tk.StringVar(),
        "search":        tk.StringVar(),
        "start_from":    tk.StringVar(),
        "start_to":      tk.StringVar(),
    }

    # ── Layout scaffolding (packed top-to-bottom in call order) ──
    filt = ttk.Frame(frame)
    filt.pack(anchor="w", fill="x", pady=(0, 8))
    badge_holder = ttk.Frame(frame)
    badge_holder.pack(anchor="w", fill="x", pady=(0, 4))
    table_holder = ttk.Frame(frame)
    table_holder.pack(fill="both", expand=True)
    pager_holder = ttk.Frame(frame)
    pager_holder.pack(anchor="w", pady=(2, 0))
    summary = ttk.Label(frame, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(frame)
    actions_holder.pack(anchor="w", pady=(0, 4))

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
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for e in page_rows:
            tree.insert("", "end", iid=str(e.enrolment_id), tags=(e.status,), values=(
                e.enrolment_id, e.student_id,
                names.get(e.student_id, "—"),
                e.academic_year, e.year_group, e.tutor_group or "—",
                e.start_date or "—", e.status,
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
        # Feature #44 — right-click context menu.
        _add_context_menu(gui, tree, {
            "View":            lambda: _selected() is not None and open_profile(gui, _selected()),
            "Edit":            lambda: _selected() is not None and open_edit_enrolment(gui, _selected()),
            "Withdraw":        lambda: _selected() is not None and _confirm_and_withdraw(gui, _selected()),
            "Soft-delete toggle": lambda: _selected() is not None and _soft_delete_toggle(gui, _selected()),
            "Duplicate":       lambda: _selected() is not None and _duplicate_enrolment(gui, _selected()),
            "Transfer to…":    lambda: _selected() is not None and open_transfer_enrolment(gui, _selected()),
            "Copy to clipboard": lambda: _selected() is not None and copy_enrolment_to_clipboard(gui, _selected()),
            "Print PDF":       lambda: _selected() is not None and export_enrolment_pdf(gui, _selected()),
            "Delete":          lambda: _require() is not None and _delete_with_confirm(gui, _selected()),
        })

        # ── Record actions (single selection) ──
        a1 = ttk.Frame(actions_holder)
        a1.pack(anchor="w")
        ttk.Button(a1, text="View",
                   command=lambda: (_require() is not None and open_profile(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a1, text="Edit",
                   command=lambda: (_require() is not None and open_edit_enrolment(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a1, text="Delete",
                   command=lambda: (_require() is not None and _delete_with_confirm(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a1, text="Withdraw",
                   command=lambda: (_require() is not None and _confirm_and_withdraw(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a1, text="Duplicate",
                   command=lambda: (_require() is not None and _duplicate_enrolment(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a1, text="Re-enrol", command=_reenrol
                   ).pack(side="left", padx=(0, 6))

        # ── Bulk / workflow actions (multi-selection) ──
        a2 = ttk.Frame(actions_holder)
        a2.pack(anchor="w", pady=(4, 0))
        ttk.Button(a2, text="New Enrolment",
                   command=lambda: open_add_enrolment(gui)
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a2, text="Bulk Enrol",
                   command=lambda: open_bulk_enrol(gui)
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a2, text="Progression Wizard",
                   command=lambda: open_progression_wizard(gui)
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a2, text="End-of-Year Rollover",
                   command=lambda: open_end_of_year_rollover(gui)
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a2, text="Set Status…",
                   command=lambda: open_bulk_status_change(gui, _require_many())
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a2, text="Reassign Tutor…",
                   command=lambda: open_bulk_tutor_reassign(gui, _require_many())
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a2, text="Delete Selected",
                   command=lambda: _confirm_bulk_delete(gui, _require_many())
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a2, text="Refresh", command=refresh
                   ).pack(side="left", padx=(0, 6))

        # ── Reports & analytics ──
        a3 = ttk.Frame(actions_holder)
        a3.pack(anchor="w", pady=(4, 0))
        ttk.Button(a3, text="Dashboard",
                   command=lambda: open_enrolment_dashboard(gui)).pack(side="left", padx=(0, 6))
        ttk.Button(a3, text="Cohort Report",
                   command=lambda: open_cohort_report(gui, fvars["academic_year"].get().strip() or None)
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a3, text="Retention",
                   command=lambda: open_retention_report(gui)).pack(side="left", padx=(0, 6))
        ttk.Button(a3, text="Withdrawals",
                   command=lambda: open_withdrawal_analysis(gui)).pack(side="left", padx=(0, 6))
        ttk.Button(a3, text="Year-on-Year",
                   command=lambda: open_year_on_year_comparison(gui)).pack(side="left", padx=(0, 6))
        ttk.Button(a3, text="Student History", command=_history
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a3, text="Advanced Query",
                   command=lambda: open_advanced_query(gui)).pack(side="left", padx=(0, 6))

        # ── Data tools ──
        a4 = ttk.Frame(actions_holder)
        a4.pack(anchor="w", pady=(4, 0))
        ttk.Button(a4, text="Export CSV",
                   command=lambda: export_directory_csv(gui, rows, names)
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a4, text="Import CSV",
                   command=lambda: import_enrolments_csv(gui)).pack(side="left", padx=(0, 6))
        ttk.Button(a4, text="Export Progression",
                   command=lambda: export_progression_list(gui)).pack(side="left", padx=(0, 6))
        ttk.Button(a4, text="No Enrolment",
                   command=lambda: _highlight_students_without_enrolment(gui)
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(a4, text="Conflicts",
                   command=lambda: _highlight_duplicate_conflicts(gui)).pack(side="left", padx=(0, 6))
        ttk.Button(a4, text="Academic Years",
                   command=lambda: open_academic_year_manager(gui)).pack(side="left", padx=(0, 6))
        ttk.Button(a4, text=f"Undo ({len(_UNDO_STACK)})",
                   command=lambda: open_undo_last_action(gui)).pack(side="left", padx=(0, 6))

        tree.bind("<Double-1>",
                  lambda _e: (_selected() is not None and open_profile(gui, _selected())))

        gui.status_var.set(f"Enrolments: {total} match(es)")

    # ── Filter bar (two rows) ──
    r1 = ttk.Frame(filt)
    r1.pack(anchor="w", fill="x")
    ttk.Label(r1, text="Academic year:").pack(side="left")
    ttk.Entry(r1, textvariable=fvars["academic_year"], width=10).pack(side="left", padx=(4, 12))
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
    field(6, "Created", e.created_at)
    if e.notes:
        ttk.Separator(grid, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(grid, text="Notes:", foreground="#555",
                  width=20, anchor="e").grid(row=8, column=0, sticky="ne", padx=(0, 8))
        ttk.Label(grid, text=e.notes, wraplength=520, justify="left").grid(
            row=8, column=1, sticky="w")

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Edit",
               command=lambda: open_edit_enrolment(gui, e.enrolment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete",
               command=lambda: _delete_with_confirm(gui, e.enrolment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Viewing enrolment #{enrolment_id}")


def _delete_with_confirm(gui, enrolment_id: int) -> None:
    try:
        e = data.get_enrolment(enrolment_id)
    except Exception as exc:
        logger.exception("Failed to load enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not load enrolment: {exc}",
                             parent=gui.root)
        return
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    ok = messagebox.askyesno(
        "Delete enrolment",
        f"Delete enrolment #{e.enrolment_id} for {e.student_id} "
        f"({e.academic_year}, Year {e.year_group})?",
        parent=gui.root,
    )
    if not ok:
        logger.debug("GUI delete cancelled for enrolment #%d", enrolment_id)
        return
    try:
        deleted = data.delete_enrolment(enrolment_id)
    except Exception as exc:
        logger.exception("GUI delete failed for enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not delete: {exc}",
                             parent=gui.root)
        return
    if deleted:
        # Feature #42 — allow undo by re-creating the deleted row.
        _record_undo(
            f"delete of #{enrolment_id} ({e.student_id})",
            lambda: data.create_enrolment({"student_id": e.student_id,
                                           **_enrolment_to_payload(e)}))
        gui.status_var.set(f"Deleted enrolment #{enrolment_id}")
        open_directory(gui)
    else:
        messagebox.showerror("Error", "Could not delete enrolment.",
                             parent=gui.root)


# ── Record-level workflow actions ───────────────────────────────────

def _confirm_and_withdraw(gui, enrolment_id: int) -> None:
    """Feature #5 — set status to Withdrawn and capture a reason into notes."""
    try:
        e = data.get_enrolment(enrolment_id)
    except Exception as exc:
        logger.exception("Withdraw: failed to load enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not load enrolment: {exc}",
                             parent=gui.root)
        return
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    if e.status == "Withdrawn":
        messagebox.showinfo("Already withdrawn",
                            f"Enrolment #{enrolment_id} is already withdrawn.",
                            parent=gui.root)
        return
    reason = simpledialog.askstring(
        "Withdraw enrolment",
        f"Reason for withdrawing {e.student_id} "
        f"({e.academic_year}, Year {e.year_group}):",
        parent=gui.root,
    )
    if reason is None:  # cancelled
        return
    stamp = f"[Withdrawn {date.today().isoformat()}]"
    tail = f"{stamp} {reason.strip()}".strip()
    new_notes = f"{e.notes}\n{tail}".strip() if e.notes else tail
    try:
        data.update_enrolment(
            enrolment_id, _enrolment_to_payload(e, status="Withdrawn", notes=new_notes))
    except Exception as exc:
        logger.exception("Withdraw failed for enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not withdraw: {exc}", parent=gui.root)
        return
    # Feature #42 — undo restores the prior status and notes.
    _record_undo(
        f"withdrawal of #{enrolment_id}",
        lambda: data.update_enrolment(enrolment_id, _enrolment_to_payload(e)))
    gui.status_var.set(f"Withdrew enrolment #{enrolment_id}")
    open_directory(gui)


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


# ── Bulk / cohort operations ────────────────────────────────────────

def open_bulk_enrol(gui) -> None:
    """Feature #1 — enrol several students into one shared year/status."""
    frame = _clear(gui)
    _heading(frame, "Bulk Enrol Students")

    try:
        students = student_data.list_students()
    except Exception:
        logger.exception("Bulk enrol: could not load students")
        students = []
    if not students:
        ttk.Label(frame, text="No students on the roll yet — add a student first.",
                  foreground="#a33").pack(anchor="w")
        ttk.Button(frame, text="Back to Enrolments",
                   command=lambda: open_directory(gui)).pack(anchor="w", pady=(8, 0))
        return

    ttk.Label(
        frame,
        text="Select students (Ctrl/Shift-click), set the shared details, then Enrol.",
        foreground="#555",
    ).pack(anchor="w", pady=(0, 6))

    body = ttk.Frame(frame)
    body.pack(anchor="w", fill="x")

    left = ttk.Frame(body)
    left.pack(side="left", padx=(0, 16))
    lb = tk.Listbox(left, selectmode="extended", height=14, width=40,
                    exportselection=False)
    lbs = ttk.Scrollbar(left, orient="vertical", command=lb.yview)
    lb.configure(yscrollcommand=lbs.set)
    lb.pack(side="left")
    lbs.pack(side="left", fill="y")
    idx_to_sid: dict[int, str] = {}
    for i, s in enumerate(students):
        lb.insert("end", f"{s.student_id} — {s.full_name}")
        idx_to_sid[i] = s.student_id

    form = ttk.Frame(body)
    form.pack(side="left", anchor="n")
    year_var = tk.StringVar(value=_default_academic_year())
    yg_var = tk.StringVar(value=str(YEAR_GROUPS[0]))
    tg_var = tk.StringVar()
    sd_var = tk.StringVar(value=date.today().isoformat())
    status_var = tk.StringVar(value=DEFAULT_STATUS)

    def frow(r: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=r, column=1, sticky="ew", pady=4)

    frow(0, "Academic year *", ttk.Entry(form, textvariable=year_var))
    frow(1, "Year group *", ttk.Combobox(
        form, textvariable=yg_var, values=[str(y) for y in YEAR_GROUPS],
        state="readonly", width=8))
    frow(2, "Tutor group", ttk.Entry(form, textvariable=tg_var))
    frow(3, "Start date", ttk.Entry(form, textvariable=sd_var))
    frow(4, "Status *", ttk.Combobox(
        form, textvariable=status_var, values=list(STATUSES),
        state="readonly", width=16))

    def run() -> None:
        sel = lb.curselection()
        if not sel:
            messagebox.showinfo("No students", "Select at least one student.",
                                parent=gui.root)
            return
        ok: list[str] = []
        fail: list[str] = []
        for i in sel:
            sid = idx_to_sid[i]
            payload = {
                "student_id": sid,
                "academic_year": year_var.get(),
                "year_group": yg_var.get(),
                "tutor_group": tg_var.get(),
                "start_date": sd_var.get(),
                "status": status_var.get(),
                "notes": None,
            }
            try:
                data.create_enrolment(payload)
                ok.append(sid)
            except Exception as exc:
                fail.append(f"{sid}: {exc}")
        _report_bulk(gui, "Bulk enrol", ok, fail)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))
    ttk.Button(bar, text="Enrol Selected", command=run).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set("Bulk enrol")


def open_progression_wizard(gui) -> None:
    """Feature #2 — roll enrolled Year 12s forward into Year 13 next year."""
    frame = _clear(gui)
    _heading(frame, "Year 12 → 13 Progression Wizard")

    src_var = tk.StringVar(value=_default_academic_year())
    info = ttk.Label(frame, text="", foreground="#555")

    row = ttk.Frame(frame)
    row.pack(anchor="w", pady=(0, 6))
    ttk.Label(row, text="Source academic year:").pack(side="left")
    ttk.Entry(row, textvariable=src_var, width=10).pack(side="left", padx=(4, 8))

    def _y12() -> list[Enrolment]:
        return data.list_enrolments(
            academic_year=src_var.get().strip(), year_group=12, status="Enrolled")

    def preview() -> None:
        src = src_var.get().strip()
        tgt = _next_academic_year(src)
        try:
            count = len(_y12())
        except Exception as exc:
            info.configure(text=f"Error: {exc}", foreground="#a33")
            return
        info.configure(
            text=f"{count} enrolled Year 12 student(s) in {src} "
                 f"will roll into Year 13 for {tgt}.",
            foreground="#555")

    ttk.Button(row, text="Preview", command=preview).pack(side="left")
    info.pack(anchor="w", pady=(0, 8))

    def run() -> None:
        src = src_var.get().strip()
        tgt = _next_academic_year(src)
        try:
            y12 = _y12()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=gui.root)
            return
        if not y12:
            messagebox.showinfo("Nothing to do",
                                f"No enrolled Year 12 students in {src}.",
                                parent=gui.root)
            return
        if not messagebox.askyesno(
                "Confirm progression",
                f"Create {len(y12)} Year 13 enrolment(s) for {tgt}?",
                parent=gui.root):
            return
        ok: list[str] = []
        fail: list[str] = []
        for e in y12:
            new_tg = enrolments._bump_tutor_group(12, 13, e.tutor_group)
            try:
                data.create_enrolment({
                    "student_id": e.student_id,
                    "academic_year": tgt,
                    "year_group": 13,
                    "tutor_group": new_tg,
                    "start_date": None,
                    "status": "Enrolled",
                    "notes": None,
                })
                ok.append(e.student_id)
            except Exception as exc:
                fail.append(f"{e.student_id}: {exc}")
        _report_bulk(gui, "Progression", ok, fail)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))
    ttk.Button(bar, text="Run Progression", command=run).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")
    preview()
    gui.status_var.set("Progression wizard")


def open_end_of_year_rollover(gui) -> None:
    """Feature #8 — complete Year 13 leavers and progress Year 12 into 13."""
    frame = _clear(gui)
    _heading(frame, "End-of-Year Rollover")
    ttk.Label(
        frame,
        text="Marks Year 13 leavers as Completed and progresses Year 12 into "
             "Year 13 for the next academic year.",
        foreground="#555",
    ).pack(anchor="w", pady=(0, 6))

    src_var = tk.StringVar(value=_default_academic_year())
    info = ttk.Label(frame, text="", foreground="#555")

    row = ttk.Frame(frame)
    row.pack(anchor="w", pady=(0, 6))
    ttk.Label(row, text="Academic year ending:").pack(side="left")
    ttk.Entry(row, textvariable=src_var, width=10).pack(side="left", padx=(4, 8))

    def _cohorts() -> tuple[str, list[Enrolment], list[Enrolment]]:
        src = src_var.get().strip()
        tgt = _next_academic_year(src)
        y13 = data.list_enrolments(academic_year=src, year_group=13, status="Enrolled")
        y12 = data.list_enrolments(academic_year=src, year_group=12, status="Enrolled")
        return tgt, y13, y12

    def preview() -> None:
        try:
            tgt, y13, y12 = _cohorts()
        except Exception as exc:
            info.configure(text=f"Error: {exc}", foreground="#a33")
            return
        info.configure(
            text=f"{len(y13)} Year 13 leaver(s) → Completed. "
                 f"{len(y12)} Year 12 → Year 13 in {tgt}.",
            foreground="#555")

    ttk.Button(row, text="Preview", command=preview).pack(side="left")
    info.pack(anchor="w", pady=(0, 8))

    def run() -> None:
        try:
            tgt, y13, y12 = _cohorts()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=gui.root)
            return
        if not y13 and not y12:
            messagebox.showinfo("Nothing to do",
                                f"No enrolled students in {src_var.get().strip()}.",
                                parent=gui.root)
            return
        if not messagebox.askyesno(
                "Confirm rollover",
                f"Complete {len(y13)} leaver(s) and progress {len(y12)} "
                f"student(s) to {tgt}?",
                parent=gui.root):
            return
        ok: list[str] = []
        fail: list[str] = []
        for e in y13:
            try:
                data.update_enrolment(
                    e.enrolment_id, _enrolment_to_payload(e, status="Completed"))
                ok.append(f"{e.student_id} (completed)")
            except Exception as exc:
                fail.append(f"{e.student_id}: {exc}")
        for e in y12:
            new_tg = enrolments._bump_tutor_group(12, 13, e.tutor_group)
            try:
                data.create_enrolment({
                    "student_id": e.student_id,
                    "academic_year": tgt,
                    "year_group": 13,
                    "tutor_group": new_tg,
                    "start_date": None,
                    "status": "Enrolled",
                    "notes": None,
                })
                ok.append(f"{e.student_id} (progressed)")
            except Exception as exc:
                fail.append(f"{e.student_id}: {exc}")
        _report_bulk(gui, "Rollover", ok, fail)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))
    ttk.Button(bar, text="Run Rollover", command=run).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")
    preview()
    gui.status_var.set("End-of-year rollover")


def open_bulk_status_change(gui, enrolment_ids: list[int]) -> None:
    """Feature #3 — set one status on many selected enrolments."""
    if not enrolment_ids:
        return
    new_status = _choose_from(
        gui, "Set Status",
        f"New status for {len(enrolment_ids)} enrolment(s):",
        list(STATUSES), DEFAULT_STATUS)
    if new_status is None:
        return
    ok: list[str] = []
    fail: list[str] = []
    priors: list[Enrolment] = []
    for eid in enrolment_ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                fail.append(f"#{eid}: not found")
                continue
            priors.append(e)
            data.update_enrolment(eid, _enrolment_to_payload(e, status=new_status))
            ok.append(f"#{eid}")
        except Exception as exc:
            fail.append(f"#{eid}: {exc}")
    if priors:
        # Feature #42 — undo restores each row's previous status.
        def _restore(snapshot: list[Enrolment] = priors) -> None:
            for e in snapshot:
                data.update_enrolment(e.enrolment_id, _enrolment_to_payload(e))
        _record_undo(f"status change of {len(priors)} enrolment(s)", _restore)
    _report_bulk(gui, "Bulk status change", ok, fail)


def open_bulk_tutor_reassign(gui, enrolment_ids: list[int]) -> None:
    """Feature #4 — move many selected enrolments to a new tutor group."""
    if not enrolment_ids:
        return
    new_tg = simpledialog.askstring(
        "Reassign Tutor Group",
        f"New tutor group for {len(enrolment_ids)} enrolment(s):",
        parent=gui.root)
    if new_tg is None:
        return
    tutor = new_tg.strip() or None
    ok: list[str] = []
    fail: list[str] = []
    for eid in enrolment_ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                fail.append(f"#{eid}: not found")
                continue
            data.update_enrolment(eid, _enrolment_to_payload(e, tutor_group=tutor))
            ok.append(f"#{eid}")
        except Exception as exc:
            fail.append(f"#{eid}: {exc}")
    _report_bulk(gui, "Bulk tutor reassign", ok, fail)


# ── Saved filter presets UI ─────────────────────────────────────────

def open_saved_filter_manager(
    gui,
    *,
    current: Callable[[], dict[str, str]] | None = None,
    on_apply: Callable[[dict[str, str]], None] | None = None,
) -> None:
    """Feature #14 — manage named filter presets. ``current`` supplies the
    live filter values to save; ``on_apply`` applies a chosen preset."""
    dlg = tk.Toplevel(gui.root)
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

def _status_counts(rows: list[Enrolment]) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for e in rows:
        counts[e.status] = counts.get(e.status, 0) + 1
    return counts


_STATUS_COLOURS = {
    "Enrolled":  "#2a7d2a",
    "Pending":   "#b8860b",
    "Withdrawn": "#888888",
    "Completed": "#2a7aa1",
}


def _count_badge_per_status(frame, rows: list[Enrolment]) -> None:
    """Feature #16 — coloured chips showing the count for each status."""
    counts = _status_counts(rows)
    ttk.Label(frame, text=f"Total {len(rows)}",
              font=("", 10, "bold")).pack(side="left", padx=(0, 10))
    for status in STATUSES:
        chip = tk.Label(frame, text=f"{status}: {counts.get(status, 0)}",
                        fg="white", bg=_STATUS_COLOURS.get(status, "#666"),
                        padx=8, pady=1)
        chip.pack(side="left", padx=(0, 6))


def _render_status_bar_chart(frame, counts: dict[str, int]) -> None:
    """Feature #25 — a simple horizontal bar chart drawn on a Canvas."""
    peak = max(counts.values()) if counts and max(counts.values()) else 1
    canvas = tk.Canvas(frame, width=420, height=len(counts) * 30 + 10,
                       highlightthickness=0)
    canvas.pack(anchor="w")
    for i, status in enumerate(STATUSES):
        n = counts.get(status, 0)
        y = 10 + i * 30
        width = int(300 * n / peak)
        canvas.create_rectangle(90, y, 90 + width, y + 20,
                                fill=_STATUS_COLOURS.get(status, "#666"), width=0)
        canvas.create_text(85, y + 10, text=status, anchor="e", font=("", 9))
        canvas.create_text(90 + width + 6, y + 10, text=str(n), anchor="w",
                           font=("", 9, "bold"))


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


def _add_context_menu(gui, tree, items: dict[str, Callable[[], None]]) -> None:
    """Feature #44 — right-click menu on the directory tree."""
    menu = tk.Menu(tree, tearoff=0)
    for label, fn in items.items():
        if label.startswith("—"):
            menu.add_separator()
        else:
            menu.add_command(label=label, command=fn)

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


def _live_validate_academic_year(entry, var) -> None:
    """Feature #36 — green when the year matches ``YYYY/YY``, red otherwise."""
    _colour_entry(entry, var, lambda v: bool(enrolments._ACADEMIC_YEAR_RE.match(v)))


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


def _confirm_bulk_delete(gui, enrolment_ids: list[int]) -> None:
    """Feature #40 — guarded multi-delete requiring a typed confirmation."""
    if not enrolment_ids:
        return
    n = len(enrolment_ids)
    typed = simpledialog.askstring(
        "Delete selected enrolments",
        f"This will permanently delete {n} enrolment(s).\n"
        f"Type DELETE to confirm:",
        parent=gui.root)
    if (typed or "").strip().upper() != "DELETE":
        gui.status_var.set("Bulk delete cancelled")
        return
    snapshots = [data.get_enrolment(eid) for eid in enrolment_ids]
    ok: list[str] = []
    fail: list[str] = []
    for eid in enrolment_ids:
        try:
            if data.delete_enrolment(eid):
                ok.append(f"#{eid}")
            else:
                fail.append(f"#{eid}: not found")
        except Exception as exc:
            fail.append(f"#{eid}: {exc}")
    restorable = [e for e in snapshots if e is not None]
    if restorable:
        def _restore(snapshot: list[Enrolment] = restorable) -> None:
            for e in snapshot:
                data.create_enrolment({"student_id": e.student_id,
                                       **_enrolment_to_payload(e)})
        _record_undo(f"bulk delete of {len(restorable)} enrolment(s)", _restore)
    _report_bulk(gui, "Bulk delete", ok, fail)


def _soft_delete_toggle(gui, enrolment_id: int) -> None:
    """Feature #41 — flip between Withdrawn and Enrolled instead of hard
    deleting, so the record is preserved."""
    e = data.get_enrolment(enrolment_id)
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    new_status = "Enrolled" if e.status == "Withdrawn" else "Withdrawn"
    try:
        data.update_enrolment(enrolment_id, _enrolment_to_payload(e, status=new_status))
    except Exception as exc:
        messagebox.showerror("Error", f"Could not update: {exc}", parent=gui.root)
        return
    _record_undo(
        f"soft-delete toggle of #{enrolment_id}",
        lambda: data.update_enrolment(enrolment_id, _enrolment_to_payload(e)))
    gui.status_var.set(f"#{enrolment_id} → {new_status}")
    open_directory(gui)


# ── Undo stack (feature 42) ─────────────────────────────────────────

_UNDO_STACK: list[tuple[str, Callable[[], None]]] = []


def _record_undo(label: str, restore: Callable[[], None]) -> None:
    _UNDO_STACK.append((label, restore))
    if len(_UNDO_STACK) > 20:
        _UNDO_STACK.pop(0)


def open_undo_last_action(gui) -> None:
    """Feature #42 — undo the most recent delete / status change this session."""
    if not _UNDO_STACK:
        messagebox.showinfo("Nothing to undo",
                            "No recent action to undo.", parent=gui.root)
        return
    label, restore = _UNDO_STACK[-1]
    if not messagebox.askyesno("Undo", f"Undo {label}?", parent=gui.root):
        return
    _UNDO_STACK.pop()
    try:
        restore()
    except Exception as exc:
        logger.exception("Undo failed for: %s", label)
        messagebox.showerror("Undo failed", f"Could not undo: {exc}", parent=gui.root)
        return
    gui.status_var.set(f"Undid {label}")
    open_directory(gui)


# ── Student-centric views (features 17, 46, 47, 49) ─────────────────

def open_student_enrolment_history(gui, student_id: str) -> None:
    """Feature #17 — every enrolment for one student, newest first."""
    frame = _clear(gui)
    student = student_data.get_student(student_id)
    name = student.full_name if student else "(unknown)"
    _heading(frame, f"Enrolment History — {student_id} · {name}")

    _show_current_year_group_chip(frame, student_id)  # feature #47

    rows = data.list_for_student(student_id)
    if not rows:
        ttk.Label(frame, text="No enrolments on record for this student.",
                  foreground="#555").pack(anchor="w", pady=(8, 0))
    else:
        cols = ("enrolment_id", "academic_year", "year_group",
                "tutor_group", "start_date", "status")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
        for col, (text, w) in {
            "enrolment_id": ("#", 50), "academic_year": ("Year", 90),
            "year_group": ("YG", 50), "tutor_group": ("Tutor", 80),
            "start_date": ("Start", 110), "status": ("Status", 110),
        }.items():
            tree.heading(col, text=text)
            tree.column(col, width=w, anchor="w")
        _apply_status_row_colours(tree)
        tree.pack(anchor="w", pady=(8, 0), fill="x")
        for e in rows:
            tree.insert("", "end", tags=(e.status,), values=(
                e.enrolment_id, e.academic_year, e.year_group,
                e.tutor_group or "—", e.start_date or "—", e.status))

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))
    ttk.Button(bar, text="Re-enrol",
               command=lambda: open_reenrol_student(gui, student_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"History for {student_id}")


def _show_current_year_group_chip(parent, student_id: str) -> None:
    """Feature #47 — surface the student's current year-group label."""
    label = data.current_year_group_label(student_id)
    text = label or "Not currently enrolled"
    tk.Label(parent, text=text, fg="white",
             bg="#2a7aa1" if label else "#888888",
             padx=8, pady=2).pack(anchor="w", pady=(4, 0))


def open_enrolment_from_student_profile(gui, student_id: str) -> None:
    """Feature #46 — deep-link used by the student profile's 'Enrol' button."""
    open_add_enrolment(gui, preselect_student_id=student_id)


def _sync_status_to_student_record(gui, student_id: str) -> str | None:
    """Feature #49 — reconcile the student's displayed year group with their
    live enrolment. The enrolment is the source of truth (year group is never
    stored on the student row), so this is a non-destructive read that returns
    the authoritative label for callers to display."""
    return data.current_year_group_label(student_id)


# ── Discovery / integrity views (features 18, 19) ───────────────────

def open_transfer_enrolment(gui, enrolment_id: int) -> None:
    """Feature #48 — move an enrolment to a different student (delete + re-create
    under the new student, since ``student_id`` is immutable)."""
    e = data.get_enrolment(enrolment_id)
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    try:
        students = [s for s in student_data.list_students() if s.student_id != e.student_id]
    except Exception:
        logger.exception("Transfer: could not load students")
        students = []
    if not students:
        messagebox.showinfo("No target", "No other students to transfer to.",
                            parent=gui.root)
        return
    choices = [f"{s.student_id} — {s.full_name}" for s in students]
    lookup = {c: s.student_id for c, s in zip(choices, students)}
    picked = _choose_from(
        gui, "Transfer enrolment",
        f"Move enrolment #{enrolment_id} ({e.academic_year}, Year {e.year_group}) to:",
        choices, choices[0])
    if picked is None:
        return
    target = lookup[picked]
    note = f"{e.notes or ''}\n[Transferred from {e.student_id} " \
           f"{date.today().isoformat()}]".strip()
    try:
        data.delete_enrolment(enrolment_id)
        new = data.create_enrolment({"student_id": target,
                                     **_enrolment_to_payload(e, notes=note)})
    except Exception as exc:
        logger.exception("Transfer failed for enrolment %d", enrolment_id)
        messagebox.showerror("Transfer failed", str(exc), parent=gui.root)
        return
    gui.status_var.set(f"Transferred to {target} (#{new.enrolment_id})")
    open_directory(gui)


def _highlight_students_without_enrolment(gui) -> None:
    """Feature #18 — students on the roll who have no enrolment record."""
    frame = _clear(gui)
    _heading(frame, "Students Without an Enrolment")
    try:
        students = student_data.list_students()
        enrolled = {e.student_id for e in data.list_enrolments()}
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    missing = [s for s in students if s.student_id not in enrolled]

    ttk.Label(frame, text=f"{len(missing)} student(s) have no enrolment.",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    tree = ttk.Treeview(frame, columns=("sid", "name"), show="headings", height=12)
    tree.heading("sid", text="Student ID")
    tree.heading("name", text="Name")
    tree.column("sid", width=110)
    tree.column("name", width=240)
    tree.pack(anchor="w", fill="x")
    for s in missing:
        tree.insert("", "end", iid=s.student_id, values=(s.student_id, s.full_name))

    def enrol_selected() -> None:
        sel = tree.selection()
        if sel:
            open_enrolment_from_student_profile(gui, sel[0])

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))
    ttk.Button(bar, text="Enrol Selected", command=enrol_selected
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"{len(missing)} student(s) without enrolment")


def _highlight_duplicate_conflicts(gui) -> None:
    """Feature #19 — surface (student, academic_year) pairs that appear more
    than once. The DB's UNIQUE constraint should prevent these, so any hit
    indicates data imported around the constraint or a legacy row."""
    frame = _clear(gui)
    _heading(frame, "Duplicate Enrolment Conflicts")
    seen: dict[tuple[str, str], int] = {}
    dupes: list[Enrolment] = []
    try:
        rows = data.list_enrolments()
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    for e in rows:
        key = (e.student_id, e.academic_year)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            dupes.append(e)

    if not dupes:
        ttk.Label(frame,
                  text="No conflicts — every (student, year) pair is unique. ✔",
                  foreground="#2a7d2a").pack(anchor="w", pady=(8, 0))
    else:
        ttk.Label(frame, text=f"{len(dupes)} conflicting row(s) found.",
                  foreground="#a33").pack(anchor="w", pady=(0, 6))
        tree = ttk.Treeview(frame, columns=("id", "sid", "year", "yg", "status"),
                            show="headings", height=10)
        for col, (text, w) in {
            "id": ("#", 50), "sid": ("Student", 110), "year": ("Year", 90),
            "yg": ("YG", 50), "status": ("Status", 100),
        }.items():
            tree.heading(col, text=text)
            tree.column(col, width=w)
        tree.pack(anchor="w", fill="x")
        for e in dupes:
            tree.insert("", "end", values=(
                e.enrolment_id, e.student_id, e.academic_year, e.year_group, e.status))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set(f"{len(dupes)} conflict(s)")


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

    crow(0, "Academic year =", ttk.Entry(grid, textvariable=y_var, width=12))
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


# ── Reports & analytics (features 21–28) ────────────────────────────

def open_enrolment_dashboard(gui) -> None:
    """Feature #21 — summary cards plus a status bar chart."""
    frame = _clear(gui)
    _heading(frame, "Enrolment Dashboard")
    try:
        rows = data.list_enrolments()
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return

    counts = _status_counts(rows)
    by_year: dict[str, int] = {}
    by_yg: dict[int, int] = {}
    for e in rows:
        by_year[e.academic_year] = by_year.get(e.academic_year, 0) + 1
        by_yg[e.year_group] = by_yg.get(e.year_group, 0) + 1

    cards = ttk.Frame(frame)
    cards.pack(anchor="w", pady=(4, 10))

    def card(parent, title: str, value: str, colour: str) -> None:
        box = tk.Frame(parent, bg=colour, padx=14, pady=10)
        box.pack(side="left", padx=(0, 10))
        tk.Label(box, text=value, fg="white", bg=colour,
                 font=("", 18, "bold")).pack()
        tk.Label(box, text=title, fg="white", bg=colour).pack()

    card(cards, "Total", str(len(rows)), "#34495e")
    card(cards, "Enrolled", str(counts.get("Enrolled", 0)), _STATUS_COLOURS["Enrolled"])
    card(cards, "Pending", str(counts.get("Pending", 0)), _STATUS_COLOURS["Pending"])
    card(cards, "Withdrawn", str(counts.get("Withdrawn", 0)), _STATUS_COLOURS["Withdrawn"])
    card(cards, "Completed", str(counts.get("Completed", 0)), _STATUS_COLOURS["Completed"])

    ttk.Label(frame, text="By status", font=("", 11, "bold")).pack(anchor="w")
    chart = ttk.Frame(frame)
    chart.pack(anchor="w", pady=(2, 8))
    _render_status_bar_chart(chart, counts)  # feature #25

    breakdown = "  ·  ".join(f"Year {yg}: {n}" for yg, n in sorted(by_yg.items()))
    ttk.Label(frame, text=f"By year group — {breakdown or '—'}").pack(anchor="w")
    years = "  ·  ".join(f"{y}: {n}" for y, n in sorted(by_year.items(), reverse=True))
    ttk.Label(frame, text=f"By academic year — {years or '—'}").pack(anchor="w", pady=(2, 0))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set("Enrolment dashboard")


def open_cohort_report(gui, academic_year: str | None = None) -> None:
    """Feature #22 — headcount breakdown for a single academic year."""
    frame = _clear(gui)
    year = academic_year or _default_academic_year()
    _heading(frame, f"Cohort Report — {year}")
    try:
        rows = data.list_enrolments(academic_year=year)
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    counts = _status_counts(rows)
    by_yg: dict[int, dict[str, int]] = {}
    for e in rows:
        by_yg.setdefault(e.year_group, {s: 0 for s in STATUSES})[e.status] += 1

    ttk.Label(frame, text=f"{len(rows)} enrolment(s) in {year}.",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    tree = ttk.Treeview(frame, columns=("yg", *STATUSES, "total"),
                        show="headings", height=6)
    tree.heading("yg", text="Year group")
    tree.column("yg", width=90)
    for s in STATUSES:
        tree.heading(s, text=s)
        tree.column(s, width=90, anchor="center")
    tree.heading("total", text="Total")
    tree.column("total", width=70, anchor="center")
    tree.pack(anchor="w", fill="x")
    for yg in sorted(by_yg):
        c = by_yg[yg]
        tree.insert("", "end", values=(
            f"Year {yg}", *[c.get(s, 0) for s in STATUSES], sum(c.values())))
    tree.insert("", "end", values=(
        "All", *[counts.get(s, 0) for s in STATUSES], len(rows)))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set(f"Cohort report {year}")


def open_retention_report(gui) -> None:
    """Feature #23 — Year 12 → 13 progression / dropout rate per academic year."""
    frame = _clear(gui)
    _heading(frame, "Retention (Year 12 → 13)")
    try:
        rows = data.list_enrolments()
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return

    # Map each student's set of (year, year_group).
    by_student: dict[str, set[tuple[str, int]]] = {}
    y12_years: set[str] = set()
    for e in rows:
        by_student.setdefault(e.student_id, set()).add((e.academic_year, e.year_group))
        if e.year_group == 12:
            y12_years.add(e.academic_year)

    tree = ttk.Treeview(frame, columns=("year", "y12", "progressed", "rate"),
                        show="headings", height=8)
    for col, (text, w) in {
        "year": ("Y12 cohort year", 130), "y12": ("Y12 count", 90),
        "progressed": ("Progressed to Y13", 140), "rate": ("Rate", 80),
    }.items():
        tree.heading(col, text=text)
        tree.column(col, width=w, anchor="center")
    tree.pack(anchor="w", fill="x", pady=(6, 0))

    for y12_year in sorted(y12_years, reverse=True):
        next_year = _next_academic_year(y12_year)
        cohort = [sid for sid, pairs in by_student.items()
                  if (y12_year, 12) in pairs]
        progressed = [sid for sid in cohort
                      if (next_year, 13) in by_student.get(sid, set())]
        rate = (100 * len(progressed) / len(cohort)) if cohort else 0
        tree.insert("", "end", values=(
            y12_year, len(cohort), len(progressed), f"{rate:.0f}%"))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set("Retention report")


def open_tutor_group_roster(gui, tutor_group: str) -> None:
    """Feature #24 — class list for one tutor group (printable via PDF)."""
    frame = _clear(gui)
    _heading(frame, f"Tutor Group Roster — {tutor_group}")
    names = _student_name_map()
    rows = [e for e in data.list_enrolments()
            if (e.tutor_group or "").lower() == tutor_group.lower()]
    ttk.Label(frame, text=f"{len(rows)} student(s) in {tutor_group}.",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    tree = ttk.Treeview(frame, columns=("sid", "name", "year", "status"),
                        show="headings", height=12)
    for col, (text, w) in {
        "sid": ("Student ID", 110), "name": ("Name", 220),
        "year": ("Year", 90), "status": ("Status", 100),
    }.items():
        tree.heading(col, text=text)
        tree.column(col, width=w)
    tree.pack(anchor="w", fill="x")
    for e in sorted(rows, key=lambda r: names.get(r.student_id, "")):
        tree.insert("", "end", values=(
            e.student_id, names.get(e.student_id, "—"), e.academic_year, e.status))

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))
    ttk.Button(bar, text="Export PDF",
               command=lambda: export_tutor_group_pdf(gui, tutor_group)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Roster {tutor_group}")


def open_withdrawal_analysis(gui) -> None:
    """Feature #26 — all withdrawn enrolments with their captured reasons."""
    frame = _clear(gui)
    _heading(frame, "Withdrawal Analysis")
    names = _student_name_map()
    try:
        rows = data.list_enrolments(status="Withdrawn")
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    ttk.Label(frame, text=f"{len(rows)} withdrawn enrolment(s).",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    tree = ttk.Treeview(frame, columns=("sid", "name", "year", "reason"),
                        show="headings", height=12)
    for col, (text, w) in {
        "sid": ("Student", 90), "name": ("Name", 160),
        "year": ("Year", 80), "reason": ("Notes / reason", 320),
    }.items():
        tree.heading(col, text=text)
        tree.column(col, width=w)
    tree.pack(anchor="w", fill="x")
    for e in rows:
        reason = (e.notes or "").replace("\n", " ⏎ ")
        tree.insert("", "end", values=(
            e.student_id, names.get(e.student_id, "—"), e.academic_year, reason or "—"))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set(f"{len(rows)} withdrawal(s)")


def open_year_on_year_comparison(gui) -> None:
    """Feature #27 — headcounts side by side across academic years."""
    frame = _clear(gui)
    _heading(frame, "Year-on-Year Comparison")
    try:
        rows = data.list_enrolments()
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    per_year: dict[str, dict[str, int]] = {}
    for e in rows:
        bucket = per_year.setdefault(e.academic_year, {s: 0 for s in STATUSES})
        bucket[e.status] += 1

    tree = ttk.Treeview(frame, columns=("year", *STATUSES, "total"),
                        show="headings", height=12)
    tree.heading("year", text="Academic year")
    tree.column("year", width=120)
    for s in STATUSES:
        tree.heading(s, text=s)
        tree.column(s, width=90, anchor="center")
    tree.heading("total", text="Total")
    tree.column("total", width=70, anchor="center")
    tree.pack(anchor="w", fill="x", pady=(6, 0))
    for year in sorted(per_year, reverse=True):
        c = per_year[year]
        tree.insert("", "end", values=(
            year, *[c.get(s, 0) for s in STATUSES], sum(c.values())))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set("Year-on-year comparison")


def _compute_capacity_utilisation(rows: list[Enrolment], capacity: int) -> dict[str, Any]:
    """Feature #28 — active headcount vs a configured cohort capacity."""
    active = sum(1 for e in rows if e.status in ("Enrolled", "Pending"))
    pct = (100 * active / capacity) if capacity else 0.0
    return {
        "active": active,
        "capacity": capacity,
        "free": max(0, capacity - active),
        "utilisation_pct": round(pct, 1),
        "over_capacity": active > capacity,
    }


# ── Import / export / print (features 29–35) ────────────────────────

_CSV_HEADERS = ("enrolment_id", "student_id", "name", "academic_year",
                "year_group", "tutor_group", "start_date", "status", "notes")


def export_directory_csv(gui, rows: list[Enrolment], names: dict[str, str]) -> None:
    """Feature #29 — export the current (filtered) view to CSV."""
    import csv
    from tkinter import filedialog
    path = filedialog.asksaveasfilename(
        parent=gui.root, defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialfile="enrolments.csv", title="Export enrolments to CSV")
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(_CSV_HEADERS)
            for e in rows:
                w.writerow([
                    e.enrolment_id, e.student_id, names.get(e.student_id, ""),
                    e.academic_year, e.year_group, e.tutor_group or "",
                    e.start_date or "", e.status, (e.notes or "").replace("\n", " ")])
    except Exception as exc:
        logger.exception("CSV export failed")
        messagebox.showerror("Export failed", str(exc), parent=gui.root)
        return
    messagebox.showinfo("Exported", f"Wrote {len(rows)} row(s) to:\n{path}",
                        parent=gui.root)
    gui.status_var.set(f"Exported {len(rows)} enrolment(s)")


def export_progression_list(gui) -> None:
    """Feature #35 — CSV of who is progressing (Y12 Enrolled) vs leaving
    (Y13 Enrolled) for the current academic year."""
    import csv
    from tkinter import filedialog
    year = _default_academic_year()
    try:
        rows = data.list_enrolments(academic_year=year, status="Enrolled")
    except Exception as exc:
        messagebox.showerror("Error", str(exc), parent=gui.root)
        return
    names = _student_name_map()
    path = filedialog.asksaveasfilename(
        parent=gui.root, defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile=f"progression_{year.replace('/', '-')}.csv",
        title="Export progression list")
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(("student_id", "name", "year_group", "outcome"))
            for e in rows:
                outcome = "Progressing to Y13" if e.year_group == 12 else \
                          ("Leaving (Y13)" if e.year_group == 13 else "—")
                w.writerow((e.student_id, names.get(e.student_id, ""),
                            e.year_group, outcome))
    except Exception as exc:
        logger.exception("Progression export failed")
        messagebox.showerror("Export failed", str(exc), parent=gui.root)
        return
    messagebox.showinfo("Exported", f"Wrote {len(rows)} row(s) to:\n{path}",
                        parent=gui.root)
    gui.status_var.set("Exported progression list")


def _write_simple_pdf(path: str, title: str, lines: list[str]) -> None:
    """Render a plain, one-column text PDF via reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _canvas
    c = _canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, title)
    y -= 30
    c.setFont("Helvetica", 10)
    for line in lines:
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 50
        c.drawString(50, y, line[:110])
        y -= 16
    c.save()


def export_enrolment_pdf(gui, enrolment_id: int) -> None:
    """Feature #30 — printable one-enrolment PDF summary."""
    from tkinter import filedialog
    e = data.get_enrolment(enrolment_id)
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    student = student_data.get_student(e.student_id)
    path = filedialog.asksaveasfilename(
        parent=gui.root, defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")],
        initialfile=f"enrolment_{enrolment_id}.pdf",
        title="Export enrolment PDF")
    if not path:
        return
    lines = [
        f"Enrolment #{e.enrolment_id}",
        "",
        f"Student        : {e.student_id} — {student.full_name if student else '(deleted)'}",
        f"Academic year  : {e.academic_year}",
        f"Year group     : Year {e.year_group}",
        f"Tutor group    : {e.tutor_group or '—'}",
        f"Start date     : {e.start_date or '—'}",
        f"Status         : {e.status}",
        f"Created        : {e.created_at}",
        "",
        "Notes:",
        *(e.notes or "—").splitlines(),
    ]
    try:
        _write_simple_pdf(path, "Sixth Form Enrolment", lines)
    except Exception as exc:
        logger.exception("PDF export failed")
        messagebox.showerror("Export failed", str(exc), parent=gui.root)
        return
    messagebox.showinfo("Exported", f"Saved PDF to:\n{path}", parent=gui.root)
    gui.status_var.set(f"Exported PDF for #{enrolment_id}")


def export_tutor_group_pdf(gui, tutor_group: str) -> None:
    """Feature #33 — printable tutor-group roster PDF."""
    from tkinter import filedialog
    names = _student_name_map()
    rows = sorted(
        (e for e in data.list_enrolments()
         if (e.tutor_group or "").lower() == tutor_group.lower()),
        key=lambda r: names.get(r.student_id, ""))
    path = filedialog.asksaveasfilename(
        parent=gui.root, defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")],
        initialfile=f"roster_{tutor_group}.pdf",
        title="Export roster PDF")
    if not path:
        return
    lines = [f"Tutor group: {tutor_group}    ({len(rows)} students)", ""]
    lines += [f"{i + 1:>2}. {e.student_id:<10} {names.get(e.student_id, '—'):<28} "
              f"{e.academic_year}  {e.status}"
              for i, e in enumerate(rows)]
    try:
        _write_simple_pdf(path, "Tutor Group Roster", lines)
    except Exception as exc:
        logger.exception("Roster PDF export failed")
        messagebox.showerror("Export failed", str(exc), parent=gui.root)
        return
    messagebox.showinfo("Exported", f"Saved roster to:\n{path}", parent=gui.root)
    gui.status_var.set(f"Exported roster {tutor_group}")


def copy_enrolment_to_clipboard(gui, enrolment_id: int) -> None:
    """Feature #34 — copy a formatted enrolment summary to the clipboard."""
    e = data.get_enrolment(enrolment_id)
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    student = student_data.get_student(e.student_id)
    text = (
        f"Enrolment #{e.enrolment_id}\n"
        f"Student: {e.student_id} — {student.full_name if student else '(deleted)'}\n"
        f"Year: {e.academic_year} · Year {e.year_group}\n"
        f"Tutor: {e.tutor_group or '—'} · Start: {e.start_date or '—'}\n"
        f"Status: {e.status}")
    try:
        gui.root.clipboard_clear()
        gui.root.clipboard_append(text)
    except Exception as exc:
        messagebox.showerror("Copy failed", str(exc), parent=gui.root)
        return
    gui.status_var.set(f"Copied enrolment #{enrolment_id} to clipboard")


def _preview_import_diff(gui, parent, records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Feature #32 — classify parsed CSV rows as new / duplicate / invalid and
    render the preview. Returns the subset that is safe to import (new)."""
    existing = {(e.student_id, e.academic_year) for e in data.list_enrolments()}
    valid_students = {s.student_id for s in student_data.list_students()}
    importable: list[dict[str, str]] = []

    tree = ttk.Treeview(parent, columns=("sid", "year", "yg", "verdict"),
                        show="headings", height=10)
    for col, (text, w) in {
        "sid": ("Student", 100), "year": ("Year", 90),
        "yg": ("YG", 50), "verdict": ("Verdict", 220),
    }.items():
        tree.heading(col, text=text)
        tree.column(col, width=w)
    tree.tag_configure("new", foreground="#2a7d2a")
    tree.tag_configure("dupe", foreground="#b8860b")
    tree.tag_configure("bad", foreground="#a33333")
    tree.pack(anchor="w", fill="x")

    for rec in records:
        sid = (rec.get("student_id") or "").strip()
        year = (rec.get("academic_year") or "").strip()
        yg = (rec.get("year_group") or "").strip()
        if sid not in valid_students:
            verdict, tag = "unknown student — skipped", "bad"
        elif not enrolments._ACADEMIC_YEAR_RE.match(year):
            verdict, tag = "bad academic year — skipped", "bad"
        elif (sid, year) in existing:
            verdict, tag = "duplicate (student+year) — skipped", "dupe"
        else:
            verdict, tag = "new — will import", "new"
            importable.append(rec)
        tree.insert("", "end", tags=(tag,), values=(sid, year, yg, verdict))
    return importable


def import_enrolments_csv(gui) -> None:
    """Feature #31 — bulk-import enrolments from CSV with a validated preview."""
    import csv
    from tkinter import filedialog
    path = filedialog.askopenfilename(
        parent=gui.root, filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        title="Import enrolments from CSV")
    if not path:
        return
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            records = list(csv.DictReader(fh))
    except Exception as exc:
        logger.exception("CSV import read failed")
        messagebox.showerror("Import failed", f"Could not read file: {exc}",
                             parent=gui.root)
        return

    frame = _clear(gui)
    _heading(frame, "Import Enrolments — Preview")
    ttk.Label(frame, text=f"{len(records)} row(s) read from {path}",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    preview_holder = ttk.Frame(frame)
    preview_holder.pack(anchor="w", fill="x")
    importable = _preview_import_diff(gui, preview_holder, records)

    def do_import() -> None:
        ok: list[str] = []
        fail: list[str] = []
        for rec in importable:
            try:
                data.create_enrolment({
                    "student_id": rec.get("student_id", "").strip(),
                    "academic_year": rec.get("academic_year", "").strip(),
                    "year_group": rec.get("year_group", "").strip(),
                    "tutor_group": (rec.get("tutor_group") or "").strip() or None,
                    "start_date": (rec.get("start_date") or "").strip() or None,
                    "status": (rec.get("status") or DEFAULT_STATUS).strip(),
                    "notes": (rec.get("notes") or "").strip() or None,
                })
                ok.append(rec.get("student_id", "?"))
            except Exception as exc:
                fail.append(f"{rec.get('student_id', '?')}: {exc}")
        _report_bulk(gui, "CSV import", ok, fail)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))
    ttk.Button(bar, text=f"Import {len(importable)} new row(s)",
               command=do_import,
               state=("normal" if importable else "disabled")
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Import preview: {len(importable)} importable")


# ── Academic-year list manager (feature 50) ─────────────────────────

_YEARS_PATH = _paths.DATA_DIR / "enrolment_academic_years.json"


def _load_academic_years() -> list[str]:
    try:
        with open(_YEARS_PATH, encoding="utf-8") as fh:
            data_ = json.load(fh)
        return [str(y) for y in data_] if isinstance(data_, list) else []
    except FileNotFoundError:
        return []
    except Exception:
        logger.exception("Could not read academic-year list")
        return []


def _save_academic_years(years: list[str]) -> None:
    try:
        _paths.ensure_directories()
        with open(_YEARS_PATH, "w", encoding="utf-8") as fh:
            json.dump(sorted(set(years)), fh, indent=2)
    except Exception:
        logger.exception("Could not write academic-year list")


def open_academic_year_manager(gui) -> None:
    """Feature #50 — CRUD the list of valid academic years used to seed the
    enrolment form and filters."""
    frame = _clear(gui)
    _heading(frame, "Academic Years")
    ttk.Label(
        frame,
        text="Manage the academic years offered in enrolment dropdowns "
             "(format YYYY/YY, e.g. 2025/26).",
        foreground="#555").pack(anchor="w", pady=(0, 6))

    years = _load_academic_years()
    if not years:
        years = [_default_academic_year()]

    lb = tk.Listbox(frame, height=8, width=18)
    lb.pack(anchor="w")

    def reload() -> None:
        lb.delete(0, "end")
        for y in sorted(set(years), reverse=True):
            lb.insert("end", y)

    reload()

    def add() -> None:
        val = simpledialog.askstring("Add academic year",
                                     "New academic year (YYYY/YY):", parent=gui.root)
        if not val:
            return
        val = val.strip()
        if not enrolments._ACADEMIC_YEAR_RE.match(val):
            messagebox.showerror("Invalid", "Must look like '2025/26'.", parent=gui.root)
            return
        years.append(val)
        _save_academic_years(years)
        reload()

    def remove() -> None:
        sel = lb.curselection()
        if not sel:
            return
        val = lb.get(sel[0])
        if val in years:
            years.remove(val)
            _save_academic_years(years)
            reload()

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(10, 0))
    ttk.Button(bar, text="Add…", command=add).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Remove", command=remove).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set("Academic year manager")
