"""Tk views for house points."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.house_points import (
    house_points as data,
)
from education_system.primarysch_system.modules.domain.house_points.house_points import (
    Award, House, POINTS_MAX, POINTS_MIN,
)
from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError,
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
                messagebox.showerror("House Points", str(e),
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


def _house_choices() -> tuple[list[str], dict[str, int]]:
    try:
        houses = data.list_houses()
    except Exception:
        logger.exception("list_houses failed")
        return [], {}
    labels: list[str] = []
    mapping: dict[str, int] = {}
    for h in houses:
        lbl = f"#{h.house_id}  {h.name}" + (" (inactive)" if not h.is_active else "")
        labels.append(lbl)
        mapping[lbl] = h.house_id
    return labels, mapping


@_safe_view
def open_house_points(host) -> None:
    logger.debug("GUI: open_house_points")

    win = tk.Toplevel(host.root)
    win.title("House Points")
    win.transient(host.root)
    win.geometry("1100x640")

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    leaderboard_tab = ttk.Frame(nb, padding=10)
    houses_tab = ttk.Frame(nb, padding=10)
    awards_tab = ttk.Frame(nb, padding=10)
    nb.add(leaderboard_tab, text="Leaderboard")
    nb.add(houses_tab, text="Houses")
    nb.add(awards_tab, text="Awards")

    # --- Leaderboard ----------------------------------------------------
    summary_var = tk.StringVar()
    ttk.Label(leaderboard_tab, textvariable=summary_var,
              font=("Segoe UI", 11, "bold")).pack(anchor="w")

    filt = ttk.Frame(leaderboard_tab)
    filt.pack(fill="x", pady=(6, 6))
    ttk.Label(filt, text="From (YYYY-MM-DD):").pack(side="left")
    from_var = tk.StringVar()
    ttk.Entry(filt, textvariable=from_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(filt, text="To (YYYY-MM-DD):").pack(side="left")
    to_var = tk.StringVar()
    ttk.Entry(filt, textvariable=to_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(filt, text="Top N pupils:").pack(side="left")
    topn_var = tk.StringVar(value="20")
    ttk.Entry(filt, textvariable=topn_var, width=6).pack(
        side="left", padx=(4, 10))

    cols_lb = ("rank", "house", "total")
    house_tree = ttk.Treeview(leaderboard_tab, columns=cols_lb,
                              show="headings", height=6)
    for col, label, width, anchor in [
        ("rank", "Rank", 60, "center"),
        ("house", "House", 240, "w"),
        ("total", "Total points", 120, "center"),
    ]:
        house_tree.heading(col, text=label)
        house_tree.column(col, width=width, anchor=anchor)
    house_tree.pack(fill="x", pady=(0, 10))

    ttk.Label(leaderboard_tab, text="Pupil leaderboard",
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    cols_pl = ("rank", "pupil_id", "total", "awards")
    pupil_tree = ttk.Treeview(leaderboard_tab, columns=cols_pl,
                              show="headings", height=14)
    for col, label, width, anchor in [
        ("rank", "Rank", 60, "center"),
        ("pupil_id", "Pupil ID", 100, "w"),
        ("total", "Total", 100, "center"),
        ("awards", "Awards", 100, "center"),
    ]:
        pupil_tree.heading(col, text=label)
        pupil_tree.column(col, width=width, anchor=anchor)
    pupil_tree.pack(fill="both", expand=True)

    def _refresh_leaderboard() -> None:
        fr = from_var.get().strip() or None
        to = to_var.get().strip() or None
        try:
            totals = data.house_totals(from_date=fr, to_date=to)
        except ValidationError as e:
            messagebox.showerror("House Points", str(e), parent=win)
            return
        except Exception:
            logger.exception("house_totals failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in house_tree.get_children():
            house_tree.delete(iid)
        for rank, (h, total) in enumerate(totals, 1):
            house_tree.insert("", "end",
                              iid=f"h{h.house_id}",
                              values=(rank, h.name, total))
        try:
            limit = int(topn_var.get())
        except ValueError:
            limit = 20
        try:
            rows = data.pupil_totals(limit=limit)
        except Exception:
            logger.exception("pupil_totals failed")
            rows = []
        for iid in pupil_tree.get_children():
            pupil_tree.delete(iid)
        for rank, (pid, total, n) in enumerate(rows, 1):
            pupil_tree.insert("", "end", values=(rank, pid, total, n))
        n_houses = len(totals)
        total_all = sum(t for _h, t in totals)
        summary_var.set(
            f"Houses: {n_houses}   Combined points awarded: {total_all:+d}"
            + (f"   {fr} to {to or 'now'}" if fr or to else "")
        )

    ttk.Button(filt, text="Refresh",
               command=_refresh_leaderboard).pack(side="left", padx=(4, 0))

    # --- Houses tab -----------------------------------------------------
    cols_h = ("house_id", "name", "colour", "motto", "active")
    htree = ttk.Treeview(houses_tab, columns=cols_h, show="headings", height=14)
    for col, label, width, anchor in [
        ("house_id", "ID", 50, "center"),
        ("name", "Name", 180, "w"),
        ("colour", "Colour", 100, "w"),
        ("motto", "Motto", 360, "w"),
        ("active", "Active", 80, "center"),
    ]:
        htree.heading(col, text=label)
        htree.column(col, width=width, anchor=anchor)
    htree.pack(fill="both", expand=True, pady=(0, 6))

    h_btns = ttk.Frame(houses_tab)
    h_btns.pack(fill="x")

    def _refresh_houses() -> None:
        try:
            rows = data.list_houses()
        except Exception:
            logger.exception("list_houses failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in htree.get_children():
            htree.delete(iid)
        for h in rows:
            htree.insert("", "end", iid=str(h.house_id), values=(
                h.house_id, h.name, h.colour or "", h.motto or "",
                "yes" if h.is_active else "no",
            ))

    def _h_selected() -> int | None:
        sel = htree.selection()
        if not sel:
            messagebox.showinfo("House Points",
                                "Select a house first.", parent=win)
            return None
        return int(sel[0])

    def _h_add() -> None:
        _open_house_dialog(win, house_id=None, on_saved=_refresh_all)

    def _h_edit() -> None:
        hid = _h_selected()
        if hid is None:
            return
        _open_house_dialog(win, house_id=hid, on_saved=_refresh_all)

    def _h_toggle() -> None:
        hid = _h_selected()
        if hid is None:
            return
        try:
            data.toggle_house_active(hid)
        except Exception:
            logger.exception("toggle_house(%s) failed", hid)
            messagebox.showerror("Error", "Could not toggle — see logs.",
                                 parent=win)
            return
        _refresh_all()

    def _h_delete() -> None:
        hid = _h_selected()
        if hid is None:
            return
        if not messagebox.askyesno("Delete house",
                                   f"Delete house #{hid}?", parent=win):
            return
        try:
            data.delete_house(hid)
        except ValidationError as e:
            messagebox.showerror("House Points", str(e), parent=win)
            return
        except Exception:
            logger.exception("delete_house(%s) failed", hid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh_all()

    ttk.Button(h_btns, text="New house", command=_h_add).pack(side="left")
    ttk.Button(h_btns, text="Edit", command=_h_edit).pack(
        side="left", padx=(8, 0))
    ttk.Button(h_btns, text="Toggle active", command=_h_toggle).pack(
        side="left", padx=(8, 0))
    ttk.Button(h_btns, text="Delete", command=_h_delete).pack(
        side="left", padx=(8, 0))
    htree.bind("<Double-Button-1>", lambda _e: _h_edit())

    # --- Awards tab -----------------------------------------------------
    a_filt = ttk.Frame(awards_tab)
    a_filt.pack(fill="x", pady=(0, 6))
    ttk.Label(a_filt, text="House:").pack(side="left")
    house_filter_var = tk.StringVar(value="All")
    house_filter_box = ttk.Combobox(a_filt, textvariable=house_filter_var,
                                    values=["All"], state="readonly", width=22)
    house_filter_box.pack(side="left", padx=(4, 10))
    ttk.Label(a_filt, text="Pupil ID:").pack(side="left")
    pupil_filter_var = tk.StringVar()
    ttk.Entry(a_filt, textvariable=pupil_filter_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(a_filt, text="From:").pack(side="left")
    from2_var = tk.StringVar()
    ttk.Entry(a_filt, textvariable=from2_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(a_filt, text="To:").pack(side="left")
    to2_var = tk.StringVar()
    ttk.Entry(a_filt, textvariable=to2_var, width=12).pack(
        side="left", padx=(4, 10))

    cols_a = ("award_id", "date", "house", "pupil", "points", "by", "reason")
    atree = ttk.Treeview(awards_tab, columns=cols_a, show="headings", height=18)
    for col, label, width, anchor in [
        ("award_id", "#", 60, "center"),
        ("date", "Date", 100, "center"),
        ("house", "House", 140, "w"),
        ("pupil", "Pupil ID", 100, "w"),
        ("points", "Pts", 60, "center"),
        ("by", "Awarded by", 160, "w"),
        ("reason", "Reason", 360, "w"),
    ]:
        atree.heading(col, text=label)
        atree.column(col, width=width, anchor=anchor)
    atree.pack(fill="both", expand=True, pady=(0, 6))

    a_btns = ttk.Frame(awards_tab)
    a_btns.pack(fill="x")

    def _house_filter_map() -> tuple[dict[str, int], list[str]]:
        try:
            houses = data.list_houses()
        except Exception:
            return {}, ["All"]
        mapping: dict[str, int] = {}
        labels = ["All"]
        for h in houses:
            lbl = f"#{h.house_id} {h.name}"
            labels.append(lbl)
            mapping[lbl] = h.house_id
        return mapping, labels

    def _refresh_awards() -> None:
        mapping, labels = _house_filter_map()
        house_filter_box["values"] = labels
        sel = house_filter_var.get()
        hid: int | None = None
        if sel != "All" and sel in mapping:
            hid = mapping[sel]
        try:
            rows = data.list_awards(
                house_id=hid,
                pupil_id=pupil_filter_var.get().strip() or None,
                from_date=from2_var.get().strip() or None,
                to_date=to2_var.get().strip() or None,
                limit=500,
            )
        except ValidationError as e:
            messagebox.showerror("House Points", str(e), parent=win)
            return
        except Exception:
            logger.exception("list_awards failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in atree.get_children():
            atree.delete(iid)
        for a, house, _p in rows:
            atree.insert("", "end", iid=str(a.award_id), values=(
                a.award_id, a.awarded_on,
                house.name if house else f"#{a.house_id}",
                a.pupil_id or "", a.points,
                a.awarded_by or "", a.reason or "",
            ))

    def _a_selected() -> int | None:
        sel = atree.selection()
        if not sel:
            messagebox.showinfo("House Points",
                                "Select an award first.", parent=win)
            return None
        return int(sel[0])

    def _a_add() -> None:
        _open_award_dialog(win, award_id=None, on_saved=_refresh_all)

    def _a_edit() -> None:
        aid = _a_selected()
        if aid is None:
            return
        _open_award_dialog(win, award_id=aid, on_saved=_refresh_all)

    def _a_delete() -> None:
        aid = _a_selected()
        if aid is None:
            return
        if not messagebox.askyesno("Delete award",
                                   f"Delete award #{aid}?", parent=win):
            return
        try:
            data.delete_award(aid)
        except Exception:
            logger.exception("delete_award(%s) failed", aid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh_all()

    ttk.Button(a_btns, text="Award points", command=_a_add).pack(side="left")
    ttk.Button(a_btns, text="Edit", command=_a_edit).pack(
        side="left", padx=(8, 0))
    ttk.Button(a_btns, text="Delete", command=_a_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(a_btns, text="Refresh", command=_refresh_awards).pack(
        side="left", padx=(8, 0))
    atree.bind("<Double-Button-1>", lambda _e: _a_edit())

    ttk.Button(win, text="Close", command=win.destroy).pack(
        anchor="e", padx=12, pady=(0, 10))

    def _refresh_all() -> None:
        _refresh_leaderboard()
        _refresh_houses()
        _refresh_awards()

    for v in (from_var, to_var, topn_var):
        v.trace_add("write", lambda *_: _refresh_leaderboard())
    for v in (house_filter_var, pupil_filter_var, from2_var, to2_var):
        v.trace_add("write", lambda *_: _refresh_awards())

    _refresh_all()


def _open_house_dialog(parent, *, house_id: int | None,
                       on_saved: Callable[[], None]) -> None:
    existing: House | None = None
    if house_id is not None:
        try:
            existing = data.get_house(house_id)
        except Exception:
            logger.exception("get_house(%s) failed", house_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("House Points",
                                 f"No house #{house_id}", parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("House" if existing else "New house")
    dlg.transient(parent)
    dlg.geometry("440x320")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Name *").grid(row=0, column=0, sticky="w", pady=3)
    name_var = tk.StringVar(value=existing.name if existing else "")
    ttk.Entry(frm, textvariable=name_var, width=24).grid(
        row=0, column=1, sticky="ew", pady=3)
    ttk.Label(frm, text="Colour").grid(row=1, column=0, sticky="w", pady=3)
    col_var = tk.StringVar(value=existing.colour or "" if existing else "")
    ttk.Entry(frm, textvariable=col_var, width=18).grid(
        row=1, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="Motto").grid(row=2, column=0, sticky="w", pady=3)
    motto_var = tk.StringVar(value=existing.motto or "" if existing else "")
    ttk.Entry(frm, textvariable=motto_var, width=36).grid(
        row=2, column=1, sticky="ew", pady=3)
    active_var = tk.BooleanVar(value=existing.is_active if existing else True)
    ttk.Checkbutton(frm, text="Active",
                    variable=active_var).grid(
        row=3, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="Notes").grid(row=4, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=36).grid(
        row=4, column=1, sticky="ew", pady=3)
    frm.columnconfigure(1, weight=1)

    def _save() -> None:
        payload = {
            "name": name_var.get(),
            "colour": col_var.get(),
            "motto": motto_var.get(),
            "is_active": active_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                data.create_house(payload)
            else:
                data.update_house(existing.house_id, payload)
        except ValidationError as e:
            messagebox.showerror("House Points", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save house failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_award_dialog(parent, *, award_id: int | None,
                       on_saved: Callable[[], None]) -> None:
    existing: Award | None = None
    if award_id is not None:
        try:
            existing = data.get_award(award_id)
        except Exception:
            logger.exception("get_award(%s) failed", award_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("House Points",
                                 f"No award #{award_id}", parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Award" if existing else "Award points")
    dlg.transient(parent)
    dlg.geometry("500x400")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    labels, mapping = _house_choices()
    initial_label = ""
    if existing is not None:
        for lbl, hid in mapping.items():
            if hid == existing.house_id:
                initial_label = lbl
                break

    ttk.Label(frm, text="House *").grid(row=0, column=0, sticky="w", pady=3)
    house_var = tk.StringVar(value=initial_label)
    ttk.Combobox(frm, textvariable=house_var, values=labels,
                 state="readonly", width=36).grid(
        row=0, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Pupil ID (optional)").grid(
        row=1, column=0, sticky="w", pady=3)
    pupil_var = tk.StringVar(value=existing.pupil_id or "" if existing else "")
    ttk.Entry(frm, textvariable=pupil_var, width=14).grid(
        row=1, column=1, sticky="w", pady=3)
    pupil_label = tk.StringVar()
    ttk.Label(frm, textvariable=pupil_label, foreground="#666").grid(
        row=1, column=2, sticky="w", padx=(8, 0))

    def _lookup_pupil(*_a) -> None:
        pid = pupil_var.get().strip()
        if not pid:
            pupil_label.set("")
            return
        try:
            p = pupils_data.get_pupil(pid)
        except Exception:
            pupil_label.set("(error)")
            return
        pupil_label.set(
            f"{p.full_name} (year {p.year_group})" if p else "(unknown)")
    pupil_var.trace_add("write", _lookup_pupil)
    _lookup_pupil()

    ttk.Label(frm, text=f"Points ({POINTS_MIN} to {POINTS_MAX}, non-zero) *").grid(
        row=2, column=0, sticky="w", pady=3)
    pts_var = tk.StringVar(value=str(existing.points) if existing else "")
    ttk.Entry(frm, textvariable=pts_var, width=8).grid(
        row=2, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Awarded on (YYYY-MM-DD)").grid(
        row=3, column=0, sticky="w", pady=3)
    date_var = tk.StringVar(value=existing.awarded_on if existing else "")
    ttk.Entry(frm, textvariable=date_var, width=14).grid(
        row=3, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="(blank = today)",
              foreground="#888").grid(row=3, column=2, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Awarded by").grid(row=4, column=0, sticky="w", pady=3)
    by_var = tk.StringVar(value=existing.awarded_by or "" if existing else "")
    ttk.Entry(frm, textvariable=by_var, width=30).grid(
        row=4, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Reason").grid(row=5, column=0, sticky="w", pady=3)
    reason_var = tk.StringVar(value=existing.reason or "" if existing else "")
    ttk.Entry(frm, textvariable=reason_var, width=42).grid(
        row=5, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Notes").grid(row=6, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=42).grid(
        row=6, column=1, columnspan=2, sticky="ew", pady=3)
    frm.columnconfigure(1, weight=1)
    frm.columnconfigure(2, weight=1)

    def _save() -> None:
        chosen = house_var.get()
        if chosen not in mapping:
            messagebox.showerror("House Points",
                                 "Please choose a house.", parent=dlg)
            return
        payload = {
            "house_id": mapping[chosen],
            "pupil_id": pupil_var.get(),
            "points": pts_var.get(),
            "awarded_on": date_var.get(),
            "awarded_by": by_var.get(),
            "reason": reason_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                data.award_points(payload)
            else:
                data.update_award(existing.award_id, payload)
        except ValidationError as e:
            messagebox.showerror("House Points", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save award failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
