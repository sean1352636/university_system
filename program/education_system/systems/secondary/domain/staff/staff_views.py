"""Tkinter views for the Secondary School Staff Directory.

Single directory window with a filter bar, treeview list, action
buttons, and a modal editor dialog.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.systems.secondary.domain.staff import staff as data
from education_system.platform import branding
from education_system.systems.secondary.domain.staff.staff import (
    DEFAULT_DEPARTMENT,
    DEFAULT_EMPLOYMENT_STATUS,
    DEFAULT_ROLE,
    DEPARTMENTS,
    EMPLOYMENT_STATUSES,
    ROLES,
    Staff,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_directory(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Staff Directory — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    StaffDirectory(win)


class StaffDirectory:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.q_e = ttk.Entry(bar, width=24)
        self.q_e.pack(side="left", padx=(2, 10))
        self.q_e.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Role:").pack(side="left")
        self.f_role = ttk.Combobox(bar, values=("",) + ROLES,
                                      state="readonly", width=22)
        self.f_role.current(0)
        self.f_role.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Dept:").pack(side="left")
        self.f_dept = ttk.Combobox(bar, values=("",) + DEPARTMENTS,
                                      state="readonly", width=22)
        self.f_dept.current(0)
        self.f_dept.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + EMPLOYMENT_STATUSES,
                                        state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        self.f_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.f_active,
                          command=self.refresh).pack(side="left")
        self.f_tutor = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Tutors", variable=self.f_tutor,
                          command=self.refresh).pack(side="left", padx=(8, 0))
        self.f_dsl = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="DSL", variable=self.f_dsl,
                          command=self.refresh).pack(side="left")

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill="both", expand=True, padx=10, pady=4)
        cols = ("id", "name", "role", "department", "status",
                "email", "phone", "room", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 90, "name": 220, "role": 180, "department": 180,
                  "status": 110, "email": 220, "phone": 130, "room": 80,
                  "flags": 80}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())
        self.tree.tag_configure("Left", foreground="#888888")
        self.tree.tag_configure("DSL", background="#fff4d0")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=10)

        self.actions_holder = ttk.Frame(self.root)
        self.actions_holder.pack(fill="x", padx=10, pady=(4, 10))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Mark Left",
                    command=self._mark_left).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.q_e.delete(0, "end")
        self.f_role.current(0)
        self.f_dept.current(0)
        self.f_status.current(0)
        self.f_active.set(True)
        self.f_tutor.set(False)
        self.f_dsl.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.q_e.get().strip()
        try:
            if q:
                rows = data.search_staff(q)
            else:
                rows = data.list_staff(
                    role=self.f_role.get() or None,
                    department=self.f_dept.get() or None,
                    employment_status=self.f_status.get() or None,
                    is_tutor=True if self.f_tutor.get() else None,
                    is_dsl=True if self.f_dsl.get() else None,
                    active_only=self.f_active.get(),
                )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for s in rows:
            flags = "".join([
                "T" if s.is_tutor else "-",
                "D" if s.is_dsl else "-",
                "E" if s.is_examiner else "-",
            ])
            tags = []
            if s.employment_status == "Left":
                tags.append("Left")
            if s.is_dsl:
                tags.append("DSL")
            self.tree.insert("", "end", iid=s.staff_id, values=(
                s.staff_id, s.full_name, s.role, s.department,
                s.employment_status, s.email, s.work_phone or "—",
                s.room or "—", flags,
            ), tags=tuple(tags))
        self.count_var.set(
            f"{len(rows)} staff. (Flags column: T=Tutor D=DSL E=Examiner)")
        self._build_actions()

    def _selected_id(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _view_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("View", "Select a staff member first.")
            return
        s = data.get_staff(sid)
        if s is None:
            return
        reports = data.reports_to(s.staff_id)
        lines = [
            f"Staff ID    : {s.staff_id}",
            f"Name        : {s.full_name}",
            f"Role        : {s.role}",
            f"Department  : {s.department}",
            f"Employment  : {s.employment_status}",
            f"Email       : {s.email}",
            f"Work phone  : {s.work_phone or '—'}",
            f"Pers. phone : {s.personal_phone or '—'}",
            f"Room        : {s.room or '—'}",
            f"Line mgr    : {s.line_manager or '—'}",
            f"Start / End : "
            f"{s.start_date or '—'}  /  {s.end_date or '—'}",
            f"Flags       : "
            f"{'Tutor ' if s.is_tutor else ''}"
            f"{'DSL ' if s.is_dsl else ''}"
            f"{'Examiner' if s.is_examiner else ''}".strip() or "—",
            "",
            "Qualifications:",
            s.qualifications or "  —",
            "",
            "Notes:",
            s.notes or "  —",
        ]
        if reports:
            lines.append("")
            lines.append(f"Direct reports ({len(reports)}):")
            for r in reports:
                lines.append(f"  {r.staff_id}  {r.full_name}  ({r.role})")
        messagebox.showinfo(f"Staff — {s.staff_id}", "\n".join(lines))

    def _new(self) -> None:
        StaffDialog(self.root, existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Edit", "Select a staff member first.")
            return
        existing = data.get_staff(sid)
        if existing is None:
            return
        StaffDialog(self.root, existing=existing, on_save=self.refresh)

    def _mark_left(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Mark Left", "Select a staff member first.")
            return
        s = data.get_staff(sid)
        if s is None:
            return
        if not messagebox.askyesno(
                "Mark Left",
                f"Mark {s.staff_id} ({s.full_name}) as Left "
                f"on {_date.today().isoformat()}?"):
            return
        try:
            data.mark_left(s.staff_id)
        except Exception as e:
            messagebox.showerror("Mark Left failed", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Delete", "Select a staff member first.")
            return
        s = data.get_staff(sid)
        if s is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Permanently delete {s.staff_id} ({s.full_name})?\n\n"
                f"This will clear line-manager links pointing to them."):
            return
        try:
            data.delete_staff(s.staff_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class StaffDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Staff | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Staff" if existing else "New Staff")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        def label(text: str):
            nonlocal r
            ttk.Label(form, text=text).grid(row=r, column=0,
                                              sticky="e", pady=3)

        def entry(width: int = 30) -> ttk.Entry:
            e = ttk.Entry(form, width=width)
            e.grid(row=r, column=1, sticky="w", padx=6)
            return e

        if self.existing:
            label("Staff ID:")
            ttk.Label(form, text=self.existing.staff_id).grid(
                row=r, column=1, sticky="w", padx=6)
            r += 1

        label("Title:")
        self.title_e = entry(10)
        if self.existing and self.existing.title:
            self.title_e.insert(0, self.existing.title)
        r += 1

        label("First name:")
        self.fn_e = entry()
        if self.existing:
            self.fn_e.insert(0, self.existing.first_name)
        r += 1

        label("Last name:")
        self.ln_e = entry()
        if self.existing:
            self.ln_e.insert(0, self.existing.last_name)
        r += 1

        label("Role:")
        self.role_cb = ttk.Combobox(form, values=ROLES,
                                       state="readonly", width=30)
        self.role_cb.set(self.existing.role if self.existing
                            else DEFAULT_ROLE)
        self.role_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Department:")
        self.dept_cb = ttk.Combobox(form, values=DEPARTMENTS,
                                       state="readonly", width=30)
        self.dept_cb.set(self.existing.department if self.existing
                            else DEFAULT_DEPARTMENT)
        self.dept_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Employment status:")
        self.status_cb = ttk.Combobox(form, values=EMPLOYMENT_STATUSES,
                                         state="readonly", width=18)
        self.status_cb.set(self.existing.employment_status
                              if self.existing
                              else DEFAULT_EMPLOYMENT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Email:")
        self.email_e = entry(40)
        if self.existing:
            self.email_e.insert(0, self.existing.email)
        else:
            ttk.Label(form, text="(auto-generated if blank)",
                       foreground="#666").grid(row=r, column=2,
                                                  sticky="w", padx=4)
        r += 1

        label("Work phone:")
        self.wphone_e = entry()
        if self.existing and self.existing.work_phone:
            self.wphone_e.insert(0, self.existing.work_phone)
        r += 1

        label("Personal phone:")
        self.pphone_e = entry()
        if self.existing and self.existing.personal_phone:
            self.pphone_e.insert(0, self.existing.personal_phone)
        r += 1

        label("Room / office:")
        self.room_e = entry()
        if self.existing and self.existing.room:
            self.room_e.insert(0, self.existing.room)
        r += 1

        label("Line manager (staff ID):")
        self.lm_e = entry()
        if self.existing and self.existing.line_manager:
            self.lm_e.insert(0, self.existing.line_manager)
        r += 1

        label("Start date:")
        self.start_e = entry(14)
        self.start_e.insert(0, (self.existing.start_date
                                  if self.existing
                                  else _date.today().isoformat()) or "")
        r += 1

        label("End date:")
        self.end_e = entry(14)
        if self.existing and self.existing.end_date:
            self.end_e.insert(0, self.existing.end_date)
        r += 1

        # Flag checkboxes
        ttk.Label(form, text="Flags:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        fl = ttk.Frame(form)
        fl.grid(row=r, column=1, sticky="w", padx=6)
        self.tutor_var = tk.BooleanVar(
            value=self.existing.is_tutor if self.existing else False)
        self.dsl_var = tk.BooleanVar(
            value=self.existing.is_dsl if self.existing else False)
        self.exam_var = tk.BooleanVar(
            value=self.existing.is_examiner if self.existing else False)
        ttk.Checkbutton(fl, text="Tutor",
                          variable=self.tutor_var).pack(side="left")
        ttk.Checkbutton(fl, text="DSL",
                          variable=self.dsl_var).pack(side="left", padx=8)
        ttk.Checkbutton(fl, text="Examiner",
                          variable=self.exam_var).pack(side="left")
        r += 1

        label("Qualifications:")
        self.quals_text = tk.Text(form, width=50, height=3, wrap="word")
        if self.existing and self.existing.qualifications:
            self.quals_text.insert("1.0", self.existing.qualifications)
        self.quals_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Notes:")
        self.notes_text = tk.Text(form, width=50, height=4, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "title":             self.title_e.get().strip(),
            "first_name":        self.fn_e.get().strip(),
            "last_name":         self.ln_e.get().strip(),
            "role":              self.role_cb.get(),
            "department":        self.dept_cb.get(),
            "employment_status": self.status_cb.get(),
            "work_phone":        self.wphone_e.get().strip(),
            "personal_phone":    self.pphone_e.get().strip(),
            "room":              self.room_e.get().strip(),
            "line_manager":      self.lm_e.get().strip(),
            "start_date":        self.start_e.get().strip(),
            "end_date":          self.end_e.get().strip(),
            "is_tutor":          self.tutor_var.get(),
            "is_dsl":            self.dsl_var.get(),
            "is_examiner":       self.exam_var.get(),
            "qualifications":    self.quals_text.get("1.0", "end").strip(),
            "notes":             self.notes_text.get("1.0", "end").strip(),
        }
        email = self.email_e.get().strip()
        if email or self.existing:
            payload["email"] = email or (
                self.existing.email if self.existing else "")
        try:
            if self.existing:
                data.update_staff(self.existing.staff_id, payload)
            else:
                data.create_staff(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save staff failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
