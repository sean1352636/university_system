"""Tk views for enrichment / clubs."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.academics.enrichment import (
    enrichment as data,
)
from education_system.systems.secondary.domain.academics.enrichment.enrichment import (
    CLUB_CATEGORIES, DAYS_OF_WEEK, MEMBERSHIP_STATUSES,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Enrichment & Clubs", str(e),
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


def _club_dialog(host, title: str,
                 initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("500x540")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    name_var   = tk.StringVar(value=str(initial.get("name") or ""))
    cat_var    = tk.StringVar(value=str(initial.get("category") or "Other"))
    day_var    = tk.StringVar(value=str(initial.get("day_of_week") or ""))
    start_var  = tk.StringVar(value=str(initial.get("start_time") or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_time") or ""))
    room_var   = tk.StringVar(value=str(initial.get("room") or ""))
    leader_var = tk.StringVar(value=str(initial.get("leader") or ""))
    cap_var    = tk.StringVar(value=str(initial.get("max_capacity") or ""))
    years_var  = tk.StringVar(value=str(initial.get("eligible_years") or ""))
    active_var = tk.BooleanVar(
        value=True if initial.get("is_active") is None
        else bool(initial.get("is_active")))

    rows: list[tuple[str, tk.Widget]] = [
        ("Name:",       ttk.Entry(frm, textvariable=name_var, width=34)),
        ("Category:",   ttk.Combobox(frm, textvariable=cat_var,
                                      values=list(CLUB_CATEGORIES),
                                      state="readonly", width=14)),
        ("Day:",        ttk.Combobox(frm, textvariable=day_var,
                                      values=["", *DAYS_OF_WEEK],
                                      state="readonly", width=8)),
        ("Start time:", ttk.Entry(frm, textvariable=start_var, width=10)),
        ("End time:",   ttk.Entry(frm, textvariable=end_var, width=10)),
        ("Room:",       ttk.Entry(frm, textvariable=room_var, width=14)),
        ("Leader:",     ttk.Entry(frm, textvariable=leader_var, width=24)),
        ("Max capacity:", ttk.Entry(frm, textvariable=cap_var, width=8)),
        ("Eligible years\n(comma-sep, blank=all):",
                         ttk.Entry(frm, textvariable=years_var, width=18)),
        ("Active:",     ttk.Checkbutton(frm, variable=active_var)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Description:").grid(row=len(rows), column=0,
                                              sticky="nw", pady=2)
    desc_w = tk.Text(frm, width=40, height=3, wrap="word")
    desc_w.insert("1.0", str(initial.get("description") or ""))
    desc_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="Notes:").grid(row=len(rows) + 1, column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=40, height=2, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows) + 1, column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "name":           name_var.get().strip(),
            "category":       cat_var.get().strip(),
            "day_of_week":    day_var.get().strip(),
            "start_time":     start_var.get().strip(),
            "end_time":       end_var.get().strip(),
            "room":           room_var.get().strip(),
            "leader":         leader_var.get().strip(),
            "max_capacity":   cap_var.get().strip(),
            "eligible_years": years_var.get().strip(),
            "is_active":      bool(active_var.get()),
            "description":    desc_w.get("1.0", "end").strip(),
            "notes":          notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_enrichment(host) -> None:
    logger.debug("GUI: open_enrichment")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Enrichment & Clubs",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    only_active_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Active only",
                    variable=only_active_var,
                    command=lambda: _refresh()
                    ).pack(side="left", padx=(0, 8))
    ttk.Label(bar, text="Category:").pack(side="left", padx=(0, 4))
    cat_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=cat_var,
                 values=["", *CLUB_CATEGORIES], state="readonly",
                 width=12).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Toggle active",
               command=lambda: _toggle(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Members",
               command=lambda: _open_members(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "name", "cat", "day", "time", "room", "leader",
            "cap", "years", "active")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("name", "Name", 200),
        ("cat", "Category", 90), ("day", "Day", 50),
        ("time", "Time", 110), ("room", "Room", 80),
        ("leader", "Leader", 140),
        ("cap", "Cap", 50), ("years", "Years", 100),
        ("active", "Active", 60),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_clubs(
                active_only=bool(only_active_var.get()),
                category=cat_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Enrichment & Clubs", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("clubs refresh failed")
            messagebox.showerror("Enrichment & Clubs",
                                 f"Could not load clubs:\n\n{e}",
                                 parent=host.root)
            return
        for c in rows:
            timestr = ("-" if not c.start_time
                       else f"{c.start_time}–{c.end_time or '?'}")
            tree.insert("", "end", iid=str(c.club_id), values=(
                c.club_id, c.name, c.category,
                c.day_of_week or "-", timestr,
                c.room or "-", c.leader or "-",
                c.max_capacity if c.max_capacity is not None else "-",
                c.eligible_years or "all",
                "Yes" if c.is_active else "No",
            ))
        try:
            o = data.overview()
            summary_var.set(
                f"Clubs: {o['total']}    Active: {o['active']}    "
                f"Active memberships: {o['active_memberships']}")
        except Exception:
            summary_var.set("(summary unavailable)")
        host.status_var.set(f"Clubs: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _open_members(host, tree))
    cat_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Enrichment & Clubs",
                            "Select a club first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _club_dialog(host, "New club")
    if not fields:
        return
    c = data.create_club(fields)
    messagebox.showinfo("Enrichment & Clubs",
                        f"Created {c.name}",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    existing = data.get_club(cid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "name", "category", "description", "day_of_week",
        "start_time", "end_time", "room", "leader",
        "max_capacity", "eligible_years", "is_active", "notes")}
    fields = _club_dialog(host, f"Edit {existing.name}", initial=initial)
    if not fields:
        return
    data.update_club(cid, fields)
    if on_done:
        on_done()


@_safe_view
def _toggle(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    rec = data.toggle_active(cid)
    messagebox.showinfo(
        "Enrichment & Clubs",
        f"{rec.name} is now "
        f"{'active' if rec.is_active else 'inactive'}.",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    existing = data.get_club(cid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete club",
            f"Delete {existing.name} and all its memberships?",
            parent=host.root):
        return
    data.delete_club(cid)
    if on_done:
        on_done()


@_safe_view
def _open_members(host, tree: ttk.Treeview) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    c = data.get_club(cid)
    if c is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Members — {c.name}")
    dlg.transient(host.root)
    dlg.geometry("680x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    info_var = tk.StringVar()
    ttk.Label(frm, textvariable=info_var,
              font=("", 10, "bold")).pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Add pupil",
               command=lambda: _do_join()).pack(side="left", padx=2)
    ttk.Button(bar, text="Set status",
               command=lambda: _do_status()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    tree_m = ttk.Treeview(frm,
                           columns=("id", "pupil", "joined", "status",
                                     "notes"),
                           show="headings", height=14)
    for c_, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 100),
        ("joined", "Joined", 100), ("status", "Status", 100),
        ("notes", "Notes", 280),
    ]:
        tree_m.heading(c_, text=label)
        tree_m.column(c_, width=w, anchor="w")
    tree_m.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree_m.get_children():
            tree_m.delete(i)
        try:
            rows = data.list_memberships(cid)
            s = data.club_summary(cid)
        except Exception as e:
            logger.exception("members refresh failed")
            messagebox.showerror("Enrichment & Clubs",
                                 f"Could not load members:\n\n{e}",
                                 parent=dlg)
            return
        for m in rows:
            tree_m.insert("", "end", iid=str(m.membership_id), values=(
                m.membership_id, m.pupil_id, m.joined_date,
                m.status, m.notes or "-",
            ))
        info_var.set(
            f"{c.name}    Active: {s['active']}    "
            f"Capacity: {s['capacity'] if s['capacity'] is not None else '-'}    "
            f"Spaces: {s['spaces'] if s['spaces'] is not None else '-'}    "
            + "    ".join(f"{k}: {v}" for k, v in s["by_status"].items()))

    def _do_join() -> None:
        pid = simpledialog.askstring("Add pupil", "Pupil ID:",
                                      parent=dlg)
        if not pid:
            return
        try:
            data.join_club(cid, pid.strip())
        except ValidationError as e:
            messagebox.showerror("Enrichment & Clubs", str(e),
                                 parent=dlg)
            return
        _refresh()

    def _do_status() -> None:
        sel = tree_m.focus()
        if not sel:
            messagebox.showinfo("Enrichment & Clubs",
                                "Select a member first.", parent=dlg)
            return
        try:
            mid = int(sel)
        except ValueError:
            return
        m = data.get_membership(mid)
        if m is None:
            return
        sub = tk.Toplevel(dlg)
        sub.title(f"Status — #{mid}")
        sub.transient(dlg)
        sub.geometry("320x140")
        sub.update_idletasks()
        try:
            sub.wait_visibility()
            sub.grab_set()
        except tk.TclError:
            pass
        sf = ttk.Frame(sub, padding=12)
        sf.pack(fill="both", expand=True)
        ttk.Label(sf, text=f"{m.pupil_id} in {m.club_name}").pack(
            anchor="w")
        ttk.Label(sf, text=f"Current status: {m.status}",
                  foreground="#666").pack(anchor="w", pady=(0, 8))
        sv = tk.StringVar(value=m.status)
        ttk.Combobox(sf, textvariable=sv,
                     values=list(MEMBERSHIP_STATUSES),
                     state="readonly").pack(fill="x")

        def _save() -> None:
            try:
                data.set_membership_status(mid, sv.get())
            except ValidationError as e:
                messagebox.showerror("Enrichment & Clubs", str(e),
                                     parent=sub)
                return
            sub.destroy()
            _refresh()

        btns = ttk.Frame(sf)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="Cancel",
                   command=sub.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save", command=_save).pack(side="right")

    def _do_delete() -> None:
        sel = tree_m.focus()
        if not sel:
            messagebox.showinfo("Enrichment & Clubs",
                                "Select a member first.", parent=dlg)
            return
        try:
            mid = int(sel)
        except ValueError:
            return
        m = data.get_membership(mid)
        if m is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Remove {m.pupil_id} from {m.club_name}?",
                parent=dlg):
            return
        data.delete_membership(mid)
        _refresh()

    tree_m.bind("<Double-1>", lambda _e: _do_status())
    _refresh()
