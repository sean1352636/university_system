"""Tkinter views for Sixth Form Cover."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.academics.cover import (
    cover as data,
)
from education_system.sixthform_system.modules.domain.academics.cover.cover import (
    ABSENCE_REASONS,
    COVER_TYPES,
    CoverRequest,
    DEFAULT_COVER_TYPE,
    DEFAULT_REASON,
    DEFAULT_STATUS,
    STATUSES,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_cover_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Cover — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    CoverTab(nb, scope="today",   label="Today")
    CoverTab(nb, scope="open",    label="Open")
    CoverTab(nb, scope="all",     label="All")
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _agency_options() -> list[tuple[int, str]]:
    try:
        from education_system.sixthform_system.modules.domain.academics.cover_agency import (
            cover_agency as _ag,
        )
        rows = _ag.list_agencies(active_only=True)
        return [(a.agency_id,
                  f"#{a.agency_id} {a.name} {a.stars}") for a in rows]
    except Exception:
        return []


def _agency_name_lookup() -> dict[int, str]:
    try:
        from education_system.sixthform_system.modules.domain.academics.cover_agency import (
            cover_agency as _ag,
        )
        return {a.agency_id: a.name for a in _ag.list_agencies()}
    except Exception:
        return {}


# ══ Cover tab ═════════════════════════════════════════════════════

class CoverTab:
    def __init__(self, nb: ttk.Notebook, *, scope: str,
                 label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + COVER_TYPES,
                                     state="readonly", width=12)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Absent teacher:").pack(side="left")
        self.f_teacher = ttk.Entry(bar, width=16)
        self.f_teacher.pack(side="left", padx=(2, 8))

        if self.scope == "all":
            ttk.Label(bar, text="From:").pack(side="left")
            self.f_from = ttk.Entry(bar, width=12)
            self.f_from.pack(side="left", padx=(2, 8))
            ttk.Label(bar, text="To:").pack(side="left")
            self.f_to = ttk.Entry(bar, width=12)
            self.f_to.pack(side="left", padx=(2, 8))
        else:
            self.f_from = None
            self.f_to = None

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "periods", "absent", "subject",
                "year", "type", "cover", "status", "cost")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "date": 90, "periods": 90,
                  "absent": 140, "subject": 110,
                  "year": 70, "type": 100,
                  "cover": 200, "status": 100, "cost": 80}
        headings = {"id": "ID", "date": "Date",
                    "periods": "Periods",
                    "absent": "Absent teacher",
                    "subject": "Subject", "year": "Year",
                    "type": "Type", "cover": "Cover",
                    "status": "Status", "cost": "Cost"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "e" if c == "cost" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Open",        background="#ffd0d0")
        self.tree.tag_configure("Allocated",   background="#fff7d0")
        self.tree.tag_configure("Confirmed",   background="#eef7ff")
        self.tree.tag_configure("Completed",   background="#d8f4d8")
        self.tree.tag_configure("Cancelled",   background="#eeeeee")
        self.tree.tag_configure("Class Split", background="#eeeeee")
        self.tree.tag_configure("Self-Study",  background="#eeeeee")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Allocate",
                    command=self._allocate).pack(side="left", padx=4)
        ttk.Button(actions, text="Confirm",
                    command=lambda: self._quick_status(
                        "Confirmed")).pack(side="left", padx=2)
        ttk.Button(actions, text="Complete",
                    command=self._complete).pack(side="left", padx=2)
        ttk.Button(actions, text="Cancel",
                    command=lambda: self._quick_status(
                        "Cancelled")).pack(side="left", padx=2)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_status.current(0)
        self.f_type.current(0)
        self.f_teacher.delete(0, "end")
        if self.f_from is not None:
            self.f_from.delete(0, "end")
        if self.f_to is not None:
            self.f_to.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        kwargs: dict = {
            "status": self.f_status.get() or None,
            "cover_type": self.f_type.get() or None,
            "absent_teacher": self.f_teacher.get().strip() or None,
        }
        if self.scope == "today":
            kwargs["today_only"] = True
        elif self.scope == "open":
            kwargs["open_only"] = True
        else:
            if self.f_from is not None:
                kwargs["date_from"] = self.f_from.get().strip() or None
            if self.f_to is not None:
                kwargs["date_to"] = self.f_to.get().strip() or None
        try:
            rows = data.list_requests(**kwargs)
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _agency_name_lookup() if any(
            r.cover_type == "Agency" for r in rows) else {}
        for r in rows:
            cover_disp = r.cover_label
            if r.cover_type == "Agency" and r.agency_id in names:
                cover_disp = (f"{names[r.agency_id]}: "
                              f"{r.agency_teacher or '—'}")
            cost = (f"£{r.cost:.2f}" if r.cost is not None else "—")
            tags = (r.status,) if r.status in STATUSES else ()
            self.tree.insert("", "end", iid=str(r.cover_id), values=(
                r.cover_id, r.absent_date,
                r.periods or "—",
                r.absent_teacher, r.subject or "—",
                r.year_group or "—",
                r.cover_type, cover_disp,
                r.status, cost,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} request(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> CoverRequest | None:
        cid = self._selected_id()
        if cid is None:
            return None
        return data.get_request(cid)

    def _view_selected(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("View", "Select a cover first.")
            return
        agency_name = None
        if r.agency_id is not None:
            agency_name = _agency_name_lookup().get(r.agency_id)
        lines = [
            f"#{r.cover_id}  {r.absent_teacher}  on {r.absent_date}",
            f"Reason          : {r.absent_reason or '—'}",
            f"Periods         : {r.periods or '—'}",
            f"Subject         : {r.subject or '—'}",
            f"Year group      : {r.year_group or '—'}",
            f"Class group     : "
            f"#{r.class_group_id or '—'}  "
            f"{r.class_group_label or '—'}",
            f"Room            : {r.room or '—'}",
            f"Cover type      : {r.cover_type}",
        ]
        if r.cover_type == "Agency":
            lines.append(
                f"Agency          : #{r.agency_id} "
                f"{agency_name or '?'}")
            lines.append(
                f"Agency teacher  : {r.agency_teacher or '—'}")
        else:
            lines.append(f"Cover staff     : {r.cover_staff or '—'}")
        lines.extend([
            f"Status          : {r.status}",
            f"Requested on    : {r.requested_on or '—'}",
            f"Allocated on    : {r.allocated_on or '—'}",
            f"Confirmed on    : {r.confirmed_on or '—'}",
            f"Completed on    : {r.completed_on or '—'}",
            f"Cost            : "
            f"{('£' + format(r.cost, '.2f')) if r.cost is not None else '—'}",
        ])
        if r.notes:
            lines.append("")
            lines.append("Notes:")
            lines.append(r.notes)
        messagebox.showinfo(f"Cover #{r.cover_id}", "\n".join(lines))

    def _new(self) -> None:
        CoverDialog(self.frame.winfo_toplevel(),
                      existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Edit", "Select a cover first.")
            return
        CoverDialog(self.frame.winfo_toplevel(),
                      existing=r, on_save=self.refresh)

    def _allocate(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Allocate",
                                  "Select a cover first.")
            return
        AllocateDialog(self.frame.winfo_toplevel(), r,
                         on_save=self.refresh)

    def _status_selected(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Status",
                                  "Select a cover first.")
            return
        StatusDialog(self.frame.winfo_toplevel(), r,
                       on_save=self.refresh)

    def _complete(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Complete",
                                  "Select a cover first.")
            return
        CompleteDialog(self.frame.winfo_toplevel(), r,
                         on_save=self.refresh)

    def _quick_status(self, new_status: str) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo(new_status,
                                  "Select a cover first.")
            return
        if not messagebox.askyesno(
                new_status,
                f"Set #{r.cover_id} → {new_status}?"):
            return
        try:
            data.set_status(r.cover_id, new_status)
        except ValidationError as ex:
            messagebox.showerror(new_status, str(ex))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        r = self._selected()
        if r is None:
            messagebox.showinfo("Delete",
                                  "Select a cover first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete cover #{r.cover_id}?"):
            return
        try:
            data.delete_request(r.cover_id)
        except Exception as ex:
            messagebox.showerror("Delete failed", str(ex))
            return
        self.refresh()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Upcoming window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            win = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary",
                                    "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=win)
        lines = [
            f"Total cover       : {summ.total}",
            f"Open              : {summ.open_count}",
            f"Today             : {summ.today_count}",
            f"This week         : {summ.this_week_count}",
            f"Upcoming ({win}d)    : {summ.upcoming}",
            f"Total cost        : £{summ.total_cost:.2f}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("By type:")
        for t in COVER_TYPES:
            n = summ.by_type.get(t, 0)
            if n:
                lines.append(f"  {t:<14} : {n}")
        lines.append("")
        lines.append("By reason:")
        for r in ABSENCE_REASONS:
            n = summ.by_reason.get(r, 0)
            if n:
                lines.append(f"  {r:<22} : {n}")
        if summ.top_absent_teachers:
            lines.append("")
            lines.append("Most absent teachers:")
            for t, n in summ.top_absent_teachers.items():
                lines.append(f"  {t:<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: CoverRequest,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — cover #{existing.cover_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_status(self.existing.cover_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class CompleteDialog:
    def __init__(self, parent: tk.Misc, existing: CoverRequest,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Complete — cover #{existing.cover_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Cost (£):").grid(row=0, column=0,
                                                  sticky="e", pady=4)
        self.cost_e = ttk.Entry(form, width=12)
        if existing.cost is not None:
            self.cost_e.insert(0, f"{existing.cost:.2f}")
        self.cost_e.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Complete",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        v = self.cost_e.get().strip()
        try:
            data.complete(self.existing.cover_id,
                            cost=float(v) if v else None)
        except (ValueError, Exception) as e:
            messagebox.showerror("Complete", str(e))
            return
        self.win.destroy()
        self.on_save()


class AllocateDialog:
    def __init__(self, parent: tk.Misc, existing: CoverRequest,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Allocate — cover #{existing.cover_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"{self.existing.absent_teacher} · "
                         f"{self.existing.absent_date} · "
                         f"{self.existing.subject or '—'}",
                   font=("", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(form, text="Cover type:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=COVER_TYPES,
                                       state="readonly", width=14)
        self.type_cb.set(self.existing.cover_type
                            if self.existing.cover_type
                            else DEFAULT_COVER_TYPE)
        self.type_cb.bind("<<ComboboxSelected>>",
                             lambda _e: self._on_type_change())
        self.type_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Internal cover staff:").grid(
            row=2, column=0, sticky="e", pady=4)
        self.staff_e = ttk.Entry(form, width=30)
        if self.existing.cover_staff:
            self.staff_e.insert(0, self.existing.cover_staff)
        self.staff_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Agency:").grid(row=3, column=0,
                                                sticky="e", pady=4)
        opts = _agency_options()
        self._agency_ids = [aid for aid, _ in opts]
        self.agency_cb = ttk.Combobox(form,
                                         values=[lbl for _, lbl in opts],
                                         state="readonly", width=40)
        if self.existing.agency_id in self._agency_ids:
            self.agency_cb.current(
                self._agency_ids.index(self.existing.agency_id))
        self.agency_cb.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Agency teacher:").grid(row=4, column=0,
                                                       sticky="e", pady=4)
        self.agency_teacher_e = ttk.Entry(form, width=30)
        if self.existing.agency_teacher:
            self.agency_teacher_e.insert(0, self.existing.agency_teacher)
        self.agency_teacher_e.grid(row=4, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Allocate",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

        self._on_type_change()

    def _on_type_change(self) -> None:
        is_agency = self.type_cb.get() == "Agency"
        is_internal = self.type_cb.get() == "Internal"
        self.staff_e.configure(state="normal" if is_internal
                                  else "disabled")
        state = "readonly" if is_agency else "disabled"
        self.agency_cb.configure(state=state)
        self.agency_teacher_e.configure(
            state="normal" if is_agency else "disabled")

    def _save(self) -> None:
        ctype = self.type_cb.get()
        kwargs: dict = {"cover_type": ctype}
        if ctype == "Internal":
            kwargs["cover_staff"] = self.staff_e.get().strip() or None
        elif ctype == "Agency":
            idx = self.agency_cb.current()
            if idx < 0:
                messagebox.showerror("Allocate",
                                        "Pick an agency")
                return
            kwargs["agency_id"] = self._agency_ids[idx]
            kwargs["agency_teacher"] = (
                self.agency_teacher_e.get().strip() or None)
        try:
            data.allocate(self.existing.cover_id, **kwargs)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Allocate failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class CoverDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: CoverRequest | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Cover" if existing else "New Cover")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Absent teacher:").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.teacher_e = ttk.Entry(form, width=30)
        if self.existing:
            self.teacher_e.insert(0, self.existing.absent_teacher)
        self.teacher_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Reason:").grid(row=r, column=2,
                                                sticky="e", pady=4)
        self.reason_cb = ttk.Combobox(form, values=("",) + ABSENCE_REASONS,
                                         state="readonly", width=20)
        self.reason_cb.set((self.existing.absent_reason or "")
                              if self.existing else DEFAULT_REASON)
        self.reason_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Date:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, (self.existing.absent_date
                                  if self.existing else _today()))
        self.date_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Periods:").grid(row=r, column=2,
                                                 sticky="e", pady=4)
        self.periods_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.periods:
            self.periods_e.insert(0, self.existing.periods)
        self.periods_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Subject:").grid(row=r, column=0,
                                                 sticky="e", pady=4)
        self.subject_e = ttk.Entry(form, width=22)
        if self.existing and self.existing.subject:
            self.subject_e.insert(0, self.existing.subject)
        self.subject_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Year:").grid(row=r, column=2,
                                              sticky="e", pady=4)
        self.year_cb = ttk.Combobox(form, values=("",) + YEAR_GROUPS,
                                       state="readonly", width=10)
        self.year_cb.set((self.existing.year_group or "")
                            if self.existing else "")
        self.year_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Class group id:").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.cg_id_e = ttk.Entry(form, width=8)
        if self.existing and self.existing.class_group_id:
            self.cg_id_e.insert(0, str(self.existing.class_group_id))
        self.cg_id_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Class group label:").grid(row=r, column=2,
                                                          sticky="e",
                                                          pady=4)
        self.cg_label_e = ttk.Entry(form, width=22)
        if self.existing and self.existing.class_group_label:
            self.cg_label_e.insert(0, self.existing.class_group_label)
        self.cg_label_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Room:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.room_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.room:
            self.room_e.insert(0, self.existing.room)
        self.room_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Cover type:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=COVER_TYPES,
                                       state="readonly", width=14)
        self.type_cb.set(self.existing.cover_type if self.existing
                            else DEFAULT_COVER_TYPE)
        self.type_cb.bind("<<ComboboxSelected>>",
                             lambda _e: self._on_type_change())
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Status:").grid(row=r, column=2,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Cover staff:").grid(row=r, column=0,
                                                     sticky="e", pady=4)
        self.staff_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.cover_staff:
            self.staff_e.insert(0, self.existing.cover_staff)
        self.staff_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Agency:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        opts = _agency_options()
        self._agency_ids = [aid for aid, _ in opts]
        self.agency_cb = ttk.Combobox(form,
                                         values=[lbl for _, lbl in opts],
                                         state="readonly", width=40)
        if (self.existing and self.existing.agency_id
                and self.existing.agency_id in self._agency_ids):
            self.agency_cb.current(
                self._agency_ids.index(self.existing.agency_id))
        self.agency_cb.grid(row=r, column=1, columnspan=3,
                              sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Agency teacher:").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.agency_teacher_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.agency_teacher:
            self.agency_teacher_e.insert(0, self.existing.agency_teacher)
        self.agency_teacher_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Cost (£):").grid(row=r, column=2,
                                                  sticky="e", pady=4)
        self.cost_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.cost is not None:
            self.cost_e.insert(0, f"{self.existing.cost:.2f}")
        self.cost_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=60, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

        self._on_type_change()

    def _on_type_change(self) -> None:
        ctype = self.type_cb.get()
        is_agency = ctype == "Agency"
        is_internal = ctype == "Internal"
        self.staff_e.configure(
            state="normal" if is_internal else "disabled")
        self.agency_cb.configure(
            state="readonly" if is_agency else "disabled")
        self.agency_teacher_e.configure(
            state="normal" if is_agency else "disabled")

    def _collect(self) -> dict:
        ctype = self.type_cb.get()
        agency_id = None
        if ctype == "Agency":
            idx = self.agency_cb.current()
            if idx < 0:
                raise ValidationError("Pick an agency")
            agency_id = self._agency_ids[idx]
        return {
            "absent_teacher":    self.teacher_e.get().strip(),
            "absent_reason":     self.reason_cb.get().strip() or None,
            "absent_date":       self.date_e.get().strip(),
            "periods":           self.periods_e.get().strip() or None,
            "subject":           self.subject_e.get().strip() or None,
            "year_group":        self.year_cb.get().strip() or None,
            "class_group_id":    self.cg_id_e.get().strip() or None,
            "class_group_label": self.cg_label_e.get().strip() or None,
            "room":              self.room_e.get().strip() or None,
            "cover_type":        ctype,
            "cover_staff":       (self.staff_e.get().strip() or None
                                  if ctype == "Internal" else None),
            "agency_id":         agency_id,
            "agency_teacher":    (self.agency_teacher_e.get().strip()
                                  or None
                                  if ctype == "Agency" else None),
            "status":            self.status_cb.get(),
            "cost":              self.cost_e.get().strip() or None,
            "notes":             self.notes_t.get("1.0", "end").strip()
                                  or None,
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_request(self.existing.cover_id, payload)
            else:
                data.create_request(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
