"""Tk views for EYFS Profile."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.assessment.eyfs_profile import (
    eyfs_profile as data,
)
from education_system.systems.primary.domain.assessment.eyfs_profile.eyfs_profile import (
    AREAS, ELG_AREAS, ELG_CODES, ELG_GLD, ELG_LABELS, STATUSES,
)
from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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
                messagebox.showerror("EYFS Profile", str(e),
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


@_safe_view
def open_eyfs_profile(host) -> None:
    logger.debug("GUI: open_eyfs_profile")

    win = tk.Toplevel(host.root)
    win.title("EYFS Profile")
    win.transient(host.root)
    win.geometry("960x580")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Academic year:").pack(side="left")
    year_var = tk.StringVar(value="")
    year_box = ttk.Combobox(filt, textvariable=year_var,
                            values=[], width=12)
    year_box.pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Pupil year:").pack(side="left")
    py_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=py_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 12))

    cols = ("pupil_id", "name", "year", "elgs", "expected", "gld")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 260, "w"),
        ("year", "Year", 60, "center"),
        ("elgs", "ELGs", 80, "center"),
        ("expected", "Expected", 90, "center"),
        ("gld", "GLD", 60, "center"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            known = data.known_years()
        except Exception:
            known = []
        year_box["values"] = known
        ay = year_var.get().strip()
        if not ay:
            for iid in tree.get_children():
                tree.delete(iid)
            summary_var.set("Choose an academic year to load profiles.")
            return
        try:
            py = None if py_var.get() == "All" else py_var.get()
            rows = data.list_pupils_with_profiles(ay, year_group=py)
        except ValidationError as e:
            messagebox.showerror("EYFS Profile", str(e), parent=win)
            return
        except Exception:
            logger.exception("EYFS refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for pupil, pr in rows:
            tree.insert("", "end", iid=pupil.pupil_id, values=(
                pupil.pupil_id, pupil.full_name, pupil.year_group,
                f"{pr.elgs_recorded}/{pr.elgs_total}",
                pr.expected_count,
                "yes" if pr.has_gld else "no",
            ))
        try:
            s = data.cohort_summary(ay, year_group=py)
            summary_var.set(
                f"{s['academic_year']}: pupils {s['pupils']}   "
                f"complete profiles {s['complete_profiles']}   "
                f"GLD {s['gld_count']} ({s['gld_pct']:.1f}%)"
            )
        except Exception:
            summary_var.set(f"{ay}: showing {len(rows)} pupil(s)")

    def _selected_pid() -> str | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("EYFS Profile", "Select a pupil first.",
                                parent=win)
            return None
        return sel[0]

    def _open_pupil() -> None:
        pid = _selected_pid()
        if pid is None:
            return
        ay = year_var.get().strip()
        if not ay:
            messagebox.showinfo("EYFS Profile", "Choose an academic year.",
                                parent=win)
            return
        _open_pupil_dialog(win, pid, ay, on_changed=_refresh)

    def _new_pupil() -> None:
        ay = year_var.get().strip()
        if not ay:
            messagebox.showinfo("EYFS Profile",
                                "Choose an academic year first.", parent=win)
            return
        pid = _prompt_for_pid(win)
        if not pid:
            return
        _open_pupil_dialog(win, pid, ay, on_changed=_refresh)

    def _clear() -> None:
        pid = _selected_pid()
        if pid is None:
            return
        ay = year_var.get().strip()
        if not ay:
            return
        if not messagebox.askyesno(
                "Clear profile",
                f"Remove ALL EYFS ELG entries for pupil {pid} in {ay}?",
                parent=win):
            return
        try:
            data.clear_pupil_year(pid, ay)
        except Exception:
            logger.exception("clear_pupil_year failed for %s/%s", pid, ay)
            messagebox.showerror("Error", "Could not clear — see logs.",
                                 parent=win)
            return
        _refresh()

    ttk.Button(btns, text="Open / edit profile", command=_open_pupil).pack(
        side="left")
    ttk.Button(btns, text="Open by pupil ID...", command=_new_pupil).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Clear pupil year", command=_clear).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _open_pupil())
    year_var.trace_add("write", lambda *_: _refresh())
    py_var.trace_add("write", lambda *_: _refresh())

    _refresh()


def _prompt_for_pid(parent) -> str | None:
    dlg = tk.Toplevel(parent)
    dlg.title("Open pupil profile")
    dlg.transient(parent)
    dlg.geometry("360x150")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="Pupil ID:").pack(anchor="w")
    pid_var = tk.StringVar()
    ttk.Entry(frm, textvariable=pid_var, width=20).pack(anchor="w", pady=(4, 6))
    label_var = tk.StringVar()
    ttk.Label(frm, textvariable=label_var, foreground="#666").pack(anchor="w")

    def _lookup(*_a) -> None:
        v = pid_var.get().strip()
        if not v:
            label_var.set("")
            return
        try:
            p = pupils_data.get_pupil(v)
        except Exception:
            label_var.set("(error)")
            return
        label_var.set(
            f"{p.full_name} (year {p.year_group})" if p else "(unknown)")
    pid_var.trace_add("write", _lookup)

    result: dict[str, str] = {}

    def _ok() -> None:
        v = pid_var.get().strip()
        if not v:
            return
        try:
            if pupils_data.get_pupil(v) is None:
                messagebox.showerror("EYFS Profile",
                                     f"No pupil with id {v}", parent=dlg)
                return
        except Exception:
            logger.exception("get_pupil(%s) failed", v)
            return
        result["pid"] = v
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.pack(fill="x", pady=(10, 0))
    ttk.Button(btn_row, text="Open", command=_ok).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 6))
    dlg.wait_window()
    return result.get("pid")


def _open_pupil_dialog(parent, pupil_id: str, academic_year: str,
                       on_changed: Callable[[], None]) -> None:
    try:
        pupil = pupils_data.get_pupil(pupil_id)
    except Exception:
        logger.exception("get_pupil(%s) failed", pupil_id)
        messagebox.showerror("Error", "Could not load pupil — see logs.",
                             parent=parent)
        return
    if pupil is None:
        messagebox.showerror("EYFS Profile",
                             f"No pupil with id {pupil_id}", parent=parent)
        return
    try:
        profile = data.get_profile(pupil_id, academic_year)
    except ValidationError as e:
        messagebox.showerror("EYFS Profile", str(e), parent=parent)
        return
    except Exception:
        logger.exception("get_profile failed for %s/%s", pupil_id, academic_year)
        messagebox.showerror("Error", "Could not load profile — see logs.",
                             parent=parent)
        return

    dlg = tk.Toplevel(parent)
    dlg.title(f"EYFS — {pupil.full_name}  ({academic_year})")
    dlg.transient(parent)
    dlg.geometry("720x640")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm,
              text=f"{pupil.full_name}  ({pupil.pupil_id}, year {pupil.year_group})",
              font=("Segoe UI", 11, "bold")).pack(anchor="w")
    header_var = tk.StringVar()
    ttk.Label(frm, textvariable=header_var,
              foreground="#444").pack(anchor="w", pady=(2, 8))

    canvas = tk.Canvas(frm, highlightthickness=0)
    scrollbar = ttk.Scrollbar(frm, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    list_frame = ttk.Frame(canvas)
    canvas.create_window((0, 0), window=list_frame, anchor="nw")

    def _on_configure(_e=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
    list_frame.bind("<Configure>", _on_configure)

    elg_vars: dict[str, tk.StringVar] = {}
    for area in AREAS:
        area_frm = ttk.LabelFrame(list_frame, text=area, padding=8)
        area_frm.pack(fill="x", pady=4)
        for code in ELG_CODES:
            if ELG_AREAS[code] != area:
                continue
            row = ttk.Frame(area_frm)
            row.pack(fill="x", pady=1)
            tag = "*" if ELG_GLD[code] else " "
            ttk.Label(row, text=f"{tag} {code}  {ELG_LABELS[code]}",
                      width=46, anchor="w").pack(side="left")
            current = profile.by_code.get(code)
            v = tk.StringVar(value=current.status if current else "")
            elg_vars[code] = v
            ttk.Combobox(row, textvariable=v,
                         values=["", *STATUSES],
                         state="readonly", width=10).pack(side="left")

    def _update_header() -> None:
        try:
            updated = data.get_profile(pupil_id, academic_year)
        except Exception:
            updated = profile
        header_var.set(
            f"ELGs {updated.elgs_recorded}/{updated.elgs_total}   "
            f"Expected: {updated.expected_count}   "
            f"GLD: {'YES' if updated.has_gld else 'no'}"
            + (f"   missing: {', '.join(updated.gld_missing)}"
               if not updated.has_gld and updated.gld_missing else "")
        )
    _update_header()

    def _save() -> None:
        # Apply each row, only writing changed values.
        try:
            current = data.get_profile(pupil_id, academic_year)
        except Exception:
            logger.exception("get_profile failed for %s/%s",
                             pupil_id, academic_year)
            messagebox.showerror("Error", "Could not refresh — see logs.",
                                 parent=dlg)
            return
        errors: list[str] = []
        for code in ELG_CODES:
            desired = elg_vars[code].get().strip()
            cur = current.by_code.get(code)
            cur_status = cur.status if cur else ""
            if desired == cur_status:
                continue
            if desired == "":
                # Cleared: delete the row if it exists.
                if cur is not None:
                    try:
                        data.delete(cur.result_id)
                    except Exception as e:
                        logger.exception("delete %s failed", code)
                        errors.append(f"{code}: {e}")
                continue
            try:
                data.set_elg(pupil_id, academic_year, code, desired)
            except ValidationError as e:
                errors.append(f"{code}: {e}")
            except Exception as e:
                logger.exception("set_elg %s failed", code)
                errors.append(f"{code}: {e}")
        if errors:
            messagebox.showwarning(
                "EYFS Profile",
                "Some entries could not be saved:\n\n" + "\n".join(errors),
                parent=dlg)
        _update_header()
        on_changed()

    btn_row = ttk.Frame(dlg, padding=(12, 0, 12, 12))
    btn_row.pack(fill="x")
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Close", command=dlg.destroy).pack(
        side="right", padx=(0, 8))
    ttk.Label(btn_row,
              text="* = contributes to GLD. Blank = unrecorded.",
              foreground="#666").pack(side="left")
