"""Tk views for clubs / activities."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.academics.enrichment.clubs import (
    clubs as data,
)
from education_system.systems.primary.domain.academics.enrichment.clubs.clubs import (
    Club, DAYS_OF_WEEK, MEMBERSHIP_STATUSES,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel
from education_system.systems.primary.interfaces.gui import kit

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Clubs", str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


FORM_FIELDS: list[tuple[str, str]] = [
    ("name", "Name *"),
    ("description", "Description"),
    ("day_of_week", "Day of week"),
    ("start_time", "Start time"),
    ("end_time", "End time"),
    ("location", "Location"),
    ("lead_staff", "Lead staff"),
    ("year_groups", "Year groups (none = any)"),
    ("max_members", "Max members"),
    ("notes", "Notes"),
]


@_safe_view
def open_clubs(host) -> None:
    logger.debug("GUI: open_clubs")
    kit.show_page(host, "Clubs & Activities", lambda parent: _draw_clubs(parent, host))


def _draw_clubs(parent, host) -> None:
    kit.page_heading(parent, "Clubs & Activities",
                     "Clubs, when they meet, who leads them and who belongs.")
    win = parent.winfo_toplevel()

    top = ttk.Frame(parent, padding=(0, 0, 0, 6))
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(parent, padding=(0, 0, 0, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Day:").pack(side="left")
    day_var = tk.StringVar(value="All")
    kit.ChoiceField(filt, day_var, choices=["All", *DAYS_OF_WEEK],
                    width=12).pack(side="left", padx=(4, 12))
    active_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(filt, text="Active only",
                    variable=active_var).pack(side="left")

    cols = ("club_id", "name", "day", "time", "years", "lead",
            "active_members", "capacity", "active")
    tree_box = ttk.Frame(parent)
    tree_box.pack(fill="both", expand=True, pady=(0, 6))
    tree = ttk.Treeview(tree_box, columns=cols, show="headings", height=14)
    for col, label, width, anchor in [
        ("club_id", "ID", 50, "center"),
        ("name", "Name", 180, "w"),
        ("day", "Day", 90, "w"),
        ("time", "Time", 110, "center"),
        ("years", "Years", 110, "w"),
        ("lead", "Lead", 160, "w"),
        ("active_members", "Members", 80, "center"),
        ("capacity", "Cap", 60, "center"),
        ("active", "Active", 60, "center"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    sb = ttk.Scrollbar(tree_box, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    btns = ttk.Frame(parent, padding=(0, 4))
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            d = None if day_var.get() == "All" else day_var.get()
            rows = data.list_all(day_of_week=d, active_only=active_var.get())
        except ValidationError as e:
            messagebox.showerror("Clubs", str(e), parent=win)
            return
        except Exception:
            logger.exception("clubs refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for c in rows:
            try:
                members = data.list_members(c.club_id, active_only=True)
                act_n = len(members)
            except Exception:
                logger.exception("list_members(%s) failed", c.club_id)
                act_n = 0
            time = ""
            if c.start_time or c.end_time:
                time = f"{c.start_time or '?'}–{c.end_time or '?'}"
            tree.insert("", "end", iid=str(c.club_id), values=(
                c.club_id, c.name, c.day_of_week or "", time,
                c.year_groups or "any", c.lead_staff or "",
                act_n, c.max_members if c.max_members is not None else "",
                "yes" if c.is_active else "no",
            ))
        try:
            counts = data.counts()
        except Exception:
            counts = {"total": 0, "active": 0, "inactive": 0, "active_members": 0}
        summary_var.set(
            f"Clubs: {counts['total']}   Active: {counts['active']}   "
            f"Inactive: {counts['inactive']}   "
            f"Active memberships: {counts['active_members']}"
        )

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Clubs", "Select a club first.", parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, club_id=None, on_saved=_refresh)

    def _edit() -> None:
        cid = _selected_id()
        if cid is None:
            return
        _open_form_dialog(win, club_id=cid, on_saved=_refresh)

    def _members() -> None:
        cid = _selected_id()
        if cid is None:
            return
        _open_members_dialog(win, cid, on_changed=_refresh)

    def _toggle() -> None:
        cid = _selected_id()
        if cid is None:
            return
        try:
            data.toggle_active(cid)
        except Exception:
            logger.exception("toggle_active(%s) failed", cid)
            messagebox.showerror("Error", "Could not toggle — see logs.",
                                 parent=win)
            return
        _refresh()

    def _delete() -> None:
        cid = _selected_id()
        if cid is None:
            return
        if not messagebox.askyesno(
                "Delete club",
                f"Delete club #{cid}? All memberships will be removed.",
                parent=win):
            return
        try:
            data.delete(cid)
        except Exception:
            logger.exception("delete(%s) failed", cid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    ttk.Button(btns, text="Add club", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit", command=_edit).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="Manage members...", command=_members).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Toggle active", command=_toggle).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close",
               command=lambda: kit.close_page(host, parent)).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _members())
    day_var.trace_add("write", lambda *_: _refresh())
    active_var.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_form_dialog(parent, *, club_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: Club | None = None
    if club_id is not None:
        try:
            existing = data.get(club_id)
        except Exception:
            logger.exception("get(%s) failed", club_id)
            messagebox.showerror("Error", "Could not load club — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Clubs", f"No club #{club_id}", parent=parent)
            return

    dlg = make_toplevel(parent)
    dlg.title("Club" if existing else "New club")
    dlg.geometry("600x620")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm, footer = kit.scrolled_form(dlg)
    years_pick: kit.MultiPicker | None = None

    vars_: dict[str, tk.StringVar] = {}
    for i, (key, label) in enumerate(FORM_FIELDS):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=3)
        v = tk.StringVar()
        if existing is not None:
            val = getattr(existing, key, "")
            if key == "max_members":
                v.set("" if val in (None, "") else str(val))
            else:
                v.set(val or "")
        vars_[key] = v
        if key == "day_of_week":
            kit.ChoiceField(frm, v, choices=DAYS_OF_WEEK, blank=True,
                            width=28).grid(row=i, column=1, sticky="ew", pady=3)
        elif key in ("start_time", "end_time"):
            kit.TimeField(frm, v).grid(row=i, column=1, sticky="w", pady=3)
        elif key == "lead_staff":
            kit.StaffPicker(frm, v, by="name", width=34).grid(
                row=i, column=1, sticky="ew", pady=3)
        elif key == "year_groups":
            chosen = [y.strip() for y in v.get().split(",") if y.strip()]
            years_pick = kit.MultiPicker(
                frm, [(y, kit.YEAR_GROUP_LABELS.get(y, y)) for y in YEAR_GROUPS],
                selected=chosen, height=len(YEAR_GROUPS), width=20)
            years_pick.grid(row=i, column=1, sticky="w", pady=3)
        elif key == "max_members":
            kit.NumberField(frm, v, from_=1, to=200).grid(
                row=i, column=1, sticky="w", pady=3)
        else:
            ttk.Entry(frm, textvariable=v, width=30).grid(
                row=i, column=1, sticky="ew", pady=3)
    frm.columnconfigure(1, weight=1)

    active_var = tk.BooleanVar(value=existing.is_active if existing else True)
    ttk.Checkbutton(frm, text="Active", variable=active_var).grid(
        row=len(FORM_FIELDS), column=1, sticky="w", pady=(6, 0))

    def _save() -> None:
        if years_pick is not None:
            vars_["year_groups"].set(",".join(years_pick.get()))
        payload = {k: v.get() for k, v in vars_.items()}
        payload["is_active"] = active_var.get()
        try:
            if existing is None:
                data.create(payload)
            else:
                data.update(existing.club_id, payload)
        except ValidationError as e:
            messagebox.showerror("Clubs", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save club failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    ttk.Button(footer, text="Save", command=_save).pack(side="right")
    ttk.Button(footer, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_members_dialog(parent, club_id: int,
                         on_changed: Callable[[], None]) -> None:
    try:
        club = data.get(club_id)
    except Exception:
        logger.exception("get(%s) failed", club_id)
        messagebox.showerror("Error", "Could not load club — see logs.",
                             parent=parent)
        return
    if club is None:
        messagebox.showerror("Clubs", f"No club #{club_id}", parent=parent)
        return

    dlg = make_toplevel(parent)
    dlg.title(f"Members — {club.name}")
    dlg.geometry("900x560")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    header_var = tk.StringVar()
    ttk.Label(frm, textvariable=header_var,
              font=("Segoe UI", 11, "bold")).pack(anchor="w")

    cols = ("membership_id", "pupil_id", "name", "year", "joined", "status")
    tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
    for col, label, width, anchor in [
        ("membership_id", "M#", 50, "center"),
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 220, "w"),
        ("year", "Year", 60, "center"),
        ("joined", "Joined", 100, "center"),
        ("status", "Status", 90, "w"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, pady=(8, 6))

    add_row = ttk.LabelFrame(frm, text="Add member", padding=8)
    add_row.pack(fill="x", pady=(6, 6))
    ttk.Label(add_row, text="Pupil:").grid(row=0, column=0, sticky="w")
    pid_var = tk.StringVar()
    kit.PupilPicker(add_row, pid_var, width=40).grid(
        row=0, column=1, padx=(4, 12))
    ttk.Label(add_row, text="Joined:").grid(row=0, column=2, sticky="w")
    joined_var = tk.StringVar()
    kit.DateField(add_row, joined_var).grid(
        row=0, column=3, padx=(4, 12))

    def _refresh() -> None:
        try:
            members = data.list_members(club_id)
        except Exception:
            logger.exception("list_members(%s) failed", club_id)
            messagebox.showerror("Error",
                                 "Could not load members — see logs.",
                                 parent=dlg)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        active_n = 0
        for p, m in members:
            if m.status == "active":
                active_n += 1
            tree.insert("", "end", iid=str(m.membership_id), values=(
                m.membership_id, p.pupil_id, p.full_name, p.year_group,
                m.joined_on, m.status,
            ))
        cap = (f" / {club.max_members}" if club.max_members is not None else "")
        header_var.set(
            f"{club.name}  —  active: {active_n}{cap}   total: {len(members)}"
            + (f"   (years {club.year_groups})" if club.year_groups else "")
        )

    def _add() -> None:
        pid = pid_var.get().strip()
        if not pid:
            messagebox.showinfo("Clubs", "Choose a pupil.", parent=dlg)
            return
        try:
            data.add_member(club_id, pid,
                            joined_on=joined_var.get().strip() or None)
        except ValidationError as e:
            messagebox.showerror("Clubs", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("add_member(%s, %s) failed", club_id, pid)
            messagebox.showerror("Error",
                                 "Could not add member — see logs.",
                                 parent=dlg)
            return
        pid_var.set("")
        joined_var.set("")
        on_changed()
        _refresh()

    ttk.Button(add_row, text="Add", command=_add).grid(row=0, column=4)
    add_row.columnconfigure(5, weight=1)

    def _selected_mid() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Clubs", "Select a member first.", parent=dlg)
            return None
        return int(sel[0])

    def _toggle_status() -> None:
        mid = _selected_mid()
        if mid is None:
            return
        sel = tree.set(str(mid), "status")
        new_status = "withdrawn" if sel == "active" else "active"
        try:
            data.set_member_status(mid, new_status)
        except ValidationError as e:
            messagebox.showerror("Clubs", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("set_member_status(%s) failed", mid)
            messagebox.showerror("Error", "Could not update — see logs.",
                                 parent=dlg)
            return
        on_changed()
        _refresh()

    def _remove() -> None:
        mid = _selected_mid()
        if mid is None:
            return
        if not messagebox.askyesno(
                "Remove membership",
                f"Remove membership #{mid}?", parent=dlg):
            return
        try:
            data.remove_member(mid)
        except Exception:
            logger.exception("remove_member(%s) failed", mid)
            messagebox.showerror("Error", "Could not remove — see logs.",
                                 parent=dlg)
            return
        on_changed()
        _refresh()

    bottom = ttk.Frame(frm)
    bottom.pack(fill="x")
    ttk.Button(bottom, text="Toggle active/withdrawn",
               command=_toggle_status).pack(side="left")
    ttk.Button(bottom, text="Remove", command=_remove).pack(
        side="left", padx=(8, 0))
    ttk.Button(bottom, text="Close", command=dlg.destroy).pack(side="right")

    _refresh()
