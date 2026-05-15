"""Tkinter views for Sixth Form Cover Agencies."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.academics.cover_agency import (
    cover_agency as data,
)
from education_system.sixthform_system.modules.domain.academics.cover_agency.cover_agency import (
    Agency,
    DEFAULT_STATUS,
    SPECIALISMS,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_cover_agency_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Cover Agencies — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    AgenciesTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


# ══ Agencies tab ══════════════════════════════════════════════════

class AgenciesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Agencies")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=18)
        self.f_search.pack(side="left", padx=(2, 10))
        self.f_search.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Min rating:").pack(side="left")
        self.f_rating = ttk.Combobox(bar,
                                       values=("", "1", "2", "3", "4", "5"),
                                       state="readonly", width=4)
        self.f_rating.current(0)
        self.f_rating.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Specialism:").pack(side="left")
        self.f_spec = ttk.Entry(bar, width=14)
        self.f_spec.pack(side="left", padx=(2, 10))

        self.active_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.active_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "status", "rating", "rate",
                "contact", "email", "last_used", "specialisms")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "name": 220, "status": 90,
                  "rating": 80, "rate": 150,
                  "contact": 140, "email": 200,
                  "last_used": 100, "specialisms": 200}
        headings = {"id": "ID", "name": "Name", "status": "Status",
                    "rating": "Rating", "rate": "Rate",
                    "contact": "Contact", "email": "Email",
                    "last_used": "Last used",
                    "specialisms": "Specialisms"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "rating" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Active",    background="#d8f4d8")
        self.tree.tag_configure("Prospect",  background="#eef7ff")
        self.tree.tag_configure("Suspended", background="#fff7d0")
        self.tree.tag_configure("Inactive",  background="#eeeeee")
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
        ttk.Button(actions, text="Rating",
                    command=self._rate_selected).pack(side="left",
                                                        padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Record use",
                    command=self._record_use).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_search.delete(0, "end")
        self.f_status.current(0)
        self.f_rating.current(0)
        self.f_spec.delete(0, "end")
        self.active_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rating = self.f_rating.get().strip()
        try:
            rows = data.list_agencies(
                search=self.f_search.get().strip() or None,
                status=self.f_status.get() or None,
                min_rating=int(rating) if rating else None,
                specialism_like=self.f_spec.get().strip() or None,
                active_only=self.active_var.get(),
            )
        except (ValueError, ValidationError) as e:
            messagebox.showerror("Filter error", str(e))
            return
        for a in rows:
            tags = (a.status,) if a.status in STATUSES else ()
            self.tree.insert("", "end", iid=str(a.agency_id), values=(
                a.agency_id, a.name, a.status, a.stars,
                a.rate_label, a.contact_name or "—",
                a.email or "—", a.last_used_on or "—",
                a.specialisms or "—",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} agency/agencies.")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> Agency | None:
        aid = self._selected_id()
        if aid is None:
            return None
        return data.get_agency(aid)

    def _view_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("View", "Select an agency first.")
            return
        lines = [
            f"#{a.agency_id}  {a.name}",
            f"Status        : {a.status}",
            f"Rating        : {a.stars}  "
            f"({a.rating if a.rating else '—'}/5)",
            f"Contact       : {a.contact_name or '—'}",
            f"Email         : {a.email or '—'}",
            f"Phone         : {a.phone or '—'}",
            f"Website       : {a.website or '—'}",
            f"Address       : {a.address or '—'}",
            f"Specialisms   : {a.specialisms or '—'}",
            f"Hourly rate   : "
            f"{('£' + format(a.hourly_rate, '.2f')) if a.hourly_rate is not None else '—'}",
            f"Daily rate    : "
            f"{('£' + format(a.daily_rate, '.2f')) if a.daily_rate is not None else '—'}",
            f"Onboarded on  : {a.onboarded_on or '—'}",
            f"Last used on  : {a.last_used_on or '—'}",
        ]
        if a.notes:
            lines.append("")
            lines.append("Notes:")
            lines.append(a.notes)
        messagebox.showinfo(f"Agency #{a.agency_id}",
                              "\n".join(lines))

    def _new(self) -> None:
        AgencyDialog(self.frame.winfo_toplevel(),
                       existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Edit", "Select an agency first.")
            return
        AgencyDialog(self.frame.winfo_toplevel(),
                       existing=a, on_save=self.refresh)

    def _rate_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Rating", "Select an agency first.")
            return
        RatingDialog(self.frame.winfo_toplevel(), a,
                       on_save=self.refresh)

    def _status_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Status", "Select an agency first.")
            return
        StatusDialog(self.frame.winfo_toplevel(), a,
                       on_save=self.refresh)

    def _record_use(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Record use",
                                  "Select an agency first.")
            return
        try:
            data.record_use(a.agency_id)
        except Exception as e:
            messagebox.showerror("Record use", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Delete",
                                  "Select an agency first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete agency #{a.agency_id} ({a.name})?\n"
                "Cover requests referencing it keep their "
                "agency_id (broken FK)."):
            return
        try:
            data.delete_agency(a.agency_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
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
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(side="top", anchor="w",
                                                 padx=8, pady=(8, 4))
        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = data.summary()
        lines = [
            f"Total agencies    : {summ.total}",
            f"Active            : {summ.active_count}",
            f"Used in last 30d  : {summ.used_recently}",
            f"Avg rating        : "
            f"{summ.average_rating if summ.average_rating is not None else '—'}",
            f"Avg daily rate    : "
            f"{('£' + format(summ.rate_average_daily, '.2f')) if summ.rate_average_daily is not None else '—'}",
            f"Avg hourly rate   : "
            f"{('£' + format(summ.rate_average_hourly, '.2f')) if summ.rate_average_hourly is not None else '—'}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Agency,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — agency #{existing.agency_id}")
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
            data.set_status(self.existing.agency_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class RatingDialog:
    def __init__(self, parent: tk.Misc, existing: Agency,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Rating — agency #{existing.agency_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Current: {existing.stars} "
                         f"({existing.rating if existing.rating else '—'})"
                   ).grid(row=0, column=0, columnspan=2,
                           sticky="w", pady=(0, 8))
        ttk.Label(form, text="New rating:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form,
                                  values=("", "1", "2", "3", "4", "5"),
                                  state="readonly", width=6)
        self.cb.set(str(existing.rating) if existing.rating else "")
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        v = self.cb.get().strip()
        try:
            data.set_rating(self.existing.agency_id,
                              int(v) if v else None)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AgencyDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Agency | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Agency" if existing else "New Agency")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def add_row(label: str, widget: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            widget.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.name_e = ttk.Entry(form, width=40)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        add_row("Name:", self.name_e)

        self.contact_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.contact_name:
            self.contact_e.insert(0, self.existing.contact_name)
        add_row("Contact:", self.contact_e)

        self.email_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.email:
            self.email_e.insert(0, self.existing.email)
        add_row("Email:", self.email_e)

        self.phone_e = ttk.Entry(form, width=20)
        if self.existing and self.existing.phone:
            self.phone_e.insert(0, self.existing.phone)
        add_row("Phone:", self.phone_e)

        self.website_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.website:
            self.website_e.insert(0, self.existing.website)
        add_row("Website:", self.website_e)

        self.address_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.address:
            self.address_e.insert(0, self.existing.address)
        add_row("Address:", self.address_e)

        self.specs_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.specialisms:
            self.specs_e.insert(0, self.existing.specialisms)
        ttk.Label(form, text="Specialisms:").grid(row=r, column=0,
                                                     sticky="e", pady=3)
        self.specs_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form,
                   text=f"e.g. {', '.join(SPECIALISMS[:3])}",
                   foreground="#888"
                   ).grid(row=r, column=2, sticky="w")
        r += 1

        self.hourly_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.hourly_rate is not None:
            self.hourly_e.insert(0, f"{self.existing.hourly_rate:.2f}")
        add_row("Hourly rate:", self.hourly_e)

        self.daily_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.daily_rate is not None:
            self.daily_e.insert(0, f"{self.existing.daily_rate:.2f}")
        add_row("Daily rate:", self.daily_e)

        self.rating_cb = ttk.Combobox(form,
                                         values=("", "1", "2", "3", "4", "5"),
                                         state="readonly", width=6)
        self.rating_cb.set(str(self.existing.rating)
                              if self.existing and self.existing.rating
                              else "")
        add_row("Rating:", self.rating_cb)

        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status
                              if self.existing else DEFAULT_STATUS)
        add_row("Status:", self.status_cb)

        self.onboarded_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.onboarded_on:
            self.onboarded_e.insert(0, self.existing.onboarded_on)
        add_row("Onboarded on:", self.onboarded_e)

        self.lastused_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.last_used_on:
            self.lastused_e.insert(0, self.existing.last_used_on)
        add_row("Last used on:", self.lastused_e)

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        return {
            "name":         self.name_e.get().strip(),
            "contact_name": self.contact_e.get().strip(),
            "email":        self.email_e.get().strip(),
            "phone":        self.phone_e.get().strip(),
            "website":      self.website_e.get().strip(),
            "address":      self.address_e.get().strip(),
            "specialisms":  self.specs_e.get().strip(),
            "hourly_rate":  self.hourly_e.get().strip() or None,
            "daily_rate":   self.daily_e.get().strip() or None,
            "rating":       self.rating_cb.get().strip() or None,
            "status":       self.status_cb.get().strip(),
            "onboarded_on": self.onboarded_e.get().strip(),
            "last_used_on": self.lastused_e.get().strip(),
            "notes":        self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_agency(self.existing.agency_id, payload)
            else:
                data.create_agency(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
