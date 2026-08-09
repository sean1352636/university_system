"""Tkinter views for Sixth Form Accessibility (SEND + accommodations).

Notebook with 4 tabs:
* Profiles            — per-student SEND status, CRUD + mark-reviewed.
* Accommodations      — all individual arrangements (filterable).
* Exam Access (JCQ)   — exam-only listing ready to print.
* Summary             — counts / alerts.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.pastoral.accessibility import (
    accessibility as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.pastoral.accessibility.accessibility import (
    Accommodation,
    ACCOMMODATION_CATEGORIES,
    ACCOMMODATION_STATUSES,
    COMMON_ACCOMMODATIONS,
    DEFAULT_ACCOMMODATION_CATEGORY,
    DEFAULT_ACCOMMODATION_STATUS,
    DEFAULT_SEND_STATUS,
    PRIMARY_NEEDS,
    Profile,
    SEND_STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_accessibility_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Accessibility — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ProfilesTab(nb)
    AccommodationsTab(nb, exam_access_only=False, label="Accommodations")
    AccommodationsTab(nb, exam_access_only=True, label="Exam Access (JCQ)")
    SummaryTab(nb)


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _today() -> str:
    return _dt.date.today().isoformat()


# ══ Profiles tab ═══════════════════════════════════════════════════

class ProfilesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Profiles")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + SEND_STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Primary need:").pack(side="left")
        self.f_need = ttk.Combobox(bar, values=("",) + PRIMARY_NEEDS,
                                     state="readonly", width=30)
        self.f_need.current(0)
        self.f_need.pack(side="left", padx=(2, 10))

        self.ehcp_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="EHCP only",
                          variable=self.ehcp_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.overdue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Review overdue",
                          variable=self.overdue_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "status", "ehcp",
                "need", "review_due", "accs")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"id": "ID", "student": "Student", "name": "Name",
                    "status": "Status", "ehcp": "EHCP",
                    "need": "Primary need",
                    "review_due": "Review due",
                    "accs": "Accs (active)"}
        widths = {"id": 60, "student": 90, "name": 180,
                  "status": 110, "ehcp": 60,
                  "need": 200, "review_due": 110, "accs": 90}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c in ("ehcp", "accs") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("EHCP", background="#ffe6d0")
        self.tree.tag_configure("SEN Support", background="#fff7d0")
        self.tree.tag_configure("Monitoring", background="#eef7ff")
        self.tree.tag_configure("Overdue", background="#ffd0d0")
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
        ttk.Button(actions, text="Mark reviewed",
                    command=self._mark_reviewed).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_status.current(0)
        self.f_need.current(0)
        self.ehcp_var.set(False)
        self.overdue_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_profiles_with_detail(
                send_status=self.f_status.get() or None,
                primary_need=self.f_need.get() or None,
                ehcp_only=self.ehcp_var.get(),
                review_overdue=self.overdue_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        today = _today()
        for r in rows:
            p = r.profile
            tags: list[str] = []
            if p.send_status in ("EHCP", "SEN Support", "Monitoring"):
                tags.append(p.send_status)
            if p.next_review_due and p.next_review_due < today:
                tags.append("Overdue")
            self.tree.insert("", "end", iid=str(p.profile_id), values=(
                p.profile_id, p.student_id, r.student_name,
                p.send_status, "✓" if p.has_ehcp else "",
                p.primary_need or "—",
                p.next_review_due or "—",
                f"{r.accommodation_count} ({r.active_accommodation_count})",
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} profile(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _view_selected(self) -> None:
        pid = self._selected_id()
        if pid is None:
            messagebox.showinfo("View", "Select a profile first.")
            return
        p = data.get_profile(pid)
        if p is None:
            return
        names = _name_lookup()
        accs = data.accommodations_for_student(p.student_id)
        lines = [
            f"Profile      : #{p.profile_id}",
            f"Student      : {p.student_id} — "
            f"{names.get(p.student_id, '?')}",
            f"SEND status  : {p.send_status}",
            f"EHCP         : {'yes' if p.has_ehcp else 'no'}"
            f"{('  ' + p.ehcp_reference) if p.ehcp_reference else ''}",
            f"Primary need : {p.primary_need or '—'}",
            f"Secondary    : {p.secondary_needs or '—'}",
            f"Diagnoses    : {p.diagnoses or '—'}",
            f"Mobility     : {p.mobility_aids or '—'}",
            f"PEEP needed  : {'yes' if p.requires_pep else 'no'}",
            f"Fire/evac    : {p.fire_evac_notes or '—'}",
            f"Last review  : {p.last_reviewed or '—'}",
            f"Next review  : {p.next_review_due or '—'}",
            f"Reviewer     : {p.reviewer or '—'}",
            "",
            "Notes:",
            p.notes or "  —",
            "",
            f"Accommodations ({len(accs)}, "
            f"active: {sum(1 for a in accs if a.is_current)}):",
        ]
        for a in accs:
            mark = "●" if a.is_current else "○"
            lines.append(f"  {mark} [{a.category}] {a.name}  ({a.status})")
        messagebox.showinfo(f"Profile #{p.profile_id}", "\n".join(lines))

    def _new(self) -> None:
        ProfileDialog(self.frame.winfo_toplevel(),
                       existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        pid = self._selected_id()
        if pid is None:
            messagebox.showinfo("Edit", "Select a profile first.")
            return
        existing = data.get_profile(pid)
        if existing is None:
            return
        ProfileDialog(self.frame.winfo_toplevel(),
                       existing=existing, on_save=self.refresh)

    def _mark_reviewed(self) -> None:
        pid = self._selected_id()
        if pid is None:
            messagebox.showinfo("Reviewed", "Select a profile first.")
            return
        existing = data.get_profile(pid)
        if existing is None:
            return
        MarkReviewedDialog(self.frame.winfo_toplevel(), existing,
                            on_save=self.refresh)

    def _delete_selected(self) -> None:
        pid = self._selected_id()
        if pid is None:
            messagebox.showinfo("Delete", "Select a profile first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete profile #{pid}?\n"
                "Accommodations are kept (delete the student to wipe both)."):
            return
        try:
            data.delete_profile(pid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Accommodations tab ════════════════════════════════════════════

class AccommodationsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 exam_access_only: bool, label: str) -> None:
        self.exam_access_only = exam_access_only
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Student ID:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))

        if not self.exam_access_only:
            ttk.Label(bar, text="Category:").pack(side="left")
            self.f_category = ttk.Combobox(
                bar, values=("",) + ACCOMMODATION_CATEGORIES,
                state="readonly", width=20)
            self.f_category.current(0)
            self.f_category.pack(side="left", padx=(2, 10))
        else:
            self.f_category = None

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + ACCOMMODATION_STATUSES,
            state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Name contains:").pack(side="left")
        self.f_name = ttk.Entry(bar, width=18)
        self.f_name.pack(side="left", padx=(2, 10))

        self.active_var = tk.BooleanVar(value=self.exam_access_only)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.active_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "arrangement", "category",
                "status", "start", "end", "approved_by")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"id": "ID", "student": "Student", "name": "Name",
                    "arrangement": "Arrangement",
                    "category": "Category", "status": "Status",
                    "start": "From", "end": "To",
                    "approved_by": "Approved by"}
        widths = {"id": 60, "student": 90, "name": 160,
                  "arrangement": 220, "category": 160,
                  "status": 90, "start": 100, "end": 100,
                  "approved_by": 140}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Active",    background="#d8f4d8")
        self.tree.tag_configure("Pending",   background="#fff7d0")
        self.tree.tag_configure("Expired",   background="#eeeeee")
        self.tree.tag_configure("Withdrawn", background="#eeeeee")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        if self.f_category is not None:
            self.f_category.current(0)
        self.f_status.current(0)
        self.f_name.delete(0, "end")
        self.active_var.set(self.exam_access_only)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_accommodations_with_detail(
                student_id=self.f_student.get().strip() or None,
                category=("Exam Access" if self.exam_access_only
                           else (self.f_category.get() or None
                                  if self.f_category else None)),
                status=self.f_status.get() or None,
                name_like=self.f_name.get().strip() or None,
                active_only=self.active_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for r in rows:
            a = r.accommodation
            tags = (a.status,) if a.status in (
                "Active", "Pending", "Expired", "Withdrawn") else ()
            self.tree.insert("", "end", iid=str(a.accommodation_id), values=(
                a.accommodation_id, a.student_id, r.student_name,
                a.name, a.category, a.status,
                a.start_date or "—", a.end_date or "—",
                a.approved_by or "—",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} accommodation(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _new(self) -> None:
        AccommDialog(self.frame.winfo_toplevel(),
                      existing=None,
                      default_category=("Exam Access"
                                          if self.exam_access_only
                                          else DEFAULT_ACCOMMODATION_CATEGORY),
                      on_save=self.refresh)

    def _edit_selected(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Edit", "Select an accommodation first.")
            return
        existing = data.get_accommodation(aid)
        if existing is None:
            return
        AccommDialog(self.frame.winfo_toplevel(),
                      existing=existing,
                      default_category=existing.category,
                      on_save=self.refresh)

    def _status_selected(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Status", "Select an accommodation first.")
            return
        existing = data.get_accommodation(aid)
        if existing is None:
            return
        AccommStatusDialog(self.frame.winfo_toplevel(), existing,
                            on_save=self.refresh)

    def _delete_selected(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Delete", "Select an accommodation first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete accommodation #{aid}?"):
            return
        try:
            data.delete_accommodation(aid)
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
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Review window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "30")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            window = int(self.window_e.get().strip() or "30")
        except ValueError:
            messagebox.showerror("Summary", "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=window)
        lines: list[str] = []
        lines.append(f"Students with profile : {summ.student_count}")
        lines.append(f"EHCP                  : {summ.ehcp_count}")
        lines.append(f"PEEP required         : {summ.pep_count}")
        lines.append("")
        lines.append("Reviews:")
        lines.append(f"  Overdue             : {summ.review_overdue}")
        lines.append(f"  Upcoming ({window}d){' ' * (8 - len(str(window)))}: "
                       f"{summ.review_upcoming}")
        lines.append("")
        lines.append(f"Accommodations        : {summ.accommodation_count} "
                       f"(active: {summ.active_accommodation_count})")
        lines.append("")
        lines.append("By SEND status:")
        for s in SEND_STATUSES:
            lines.append(f"  {s:<14} : {summ.by_send_status.get(s, 0)}")
        lines.append("")
        lines.append("By primary need:")
        for n in PRIMARY_NEEDS:
            c = summ.by_primary_need.get(n, 0)
            if c:
                lines.append(f"  {n:<36} : {c}")
        lines.append("")
        lines.append("Accommodations by category:")
        for c in ACCOMMODATION_CATEGORIES:
            n = summ.by_category.get(c, 0)
            if n:
                lines.append(f"  {c:<24} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class MarkReviewedDialog:
    def __init__(self, parent: tk.Misc, existing: Profile,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Mark reviewed — #{existing.profile_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)

        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        names = _name_lookup()
        ttk.Label(form,
                   text=f"Student: {existing.student_id} — "
                         f"{names.get(existing.student_id, '?')}",
                   ).grid(row=0, column=0, columnspan=2,
                           sticky="w", pady=(0, 8))

        ttk.Label(form, text="Review date:").grid(row=1, column=0,
                                                     sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Reviewer:").grid(row=2, column=0,
                                                  sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.reviewer:
            self.by_e.insert(0, existing.reviewer)
        self.by_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Next review due:").grid(row=3, column=0,
                                                        sticky="e", pady=4)
        self.next_e = ttk.Entry(form, width=14)
        if existing.next_review_due:
            self.next_e.insert(0, existing.next_review_due)
        self.next_e.grid(row=3, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.mark_reviewed(
                self.existing.profile_id,
                reviewer=self.by_e.get().strip() or None,
                review_date=self.date_e.get().strip() or None,
                next_review_due=self.next_e.get().strip() or None,
            )
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ProfileDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Profile | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Profile" if existing else "New Profile")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                 sticky="e", pady=4)
        if self.existing:
            sid = self.existing.student_id
            self._student_id = sid
            self.student_cb = None
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{sid} — {names.get(sid, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                form, values=[l for _, l in opts],
                state="readonly", width=44)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="SEND status:").grid(row=r, column=0,
                                                     sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=SEND_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.send_status if self.existing
                              else DEFAULT_SEND_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        self.ehcp_var = tk.BooleanVar(
            value=(self.existing.has_ehcp if self.existing else False))
        ttk.Checkbutton(form, text="Has EHCP",
                          variable=self.ehcp_var).grid(
            row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="EHCP reference:").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.ehcp_ref_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.ehcp_reference:
            self.ehcp_ref_e.insert(0, self.existing.ehcp_reference)
        self.ehcp_ref_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Primary need:").grid(row=r, column=0,
                                                      sticky="e", pady=4)
        self.need_cb = ttk.Combobox(form, values=("",) + PRIMARY_NEEDS,
                                       state="readonly", width=30)
        self.need_cb.set((self.existing.primary_need or "")
                            if self.existing else "")
        self.need_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Secondary needs:").grid(row=r, column=0,
                                                        sticky="ne", pady=4)
        self.sec_t = tk.Text(form, width=44, height=2)
        if self.existing and self.existing.secondary_needs:
            self.sec_t.insert("1.0", self.existing.secondary_needs)
        self.sec_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Diagnoses:").grid(row=r, column=0,
                                                   sticky="ne", pady=4)
        self.diag_t = tk.Text(form, width=44, height=2)
        if self.existing and self.existing.diagnoses:
            self.diag_t.insert("1.0", self.existing.diagnoses)
        self.diag_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Mobility aids:").grid(row=r, column=0,
                                                      sticky="e", pady=4)
        self.mob_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.mobility_aids:
            self.mob_e.insert(0, self.existing.mobility_aids)
        self.mob_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        self.pep_var = tk.BooleanVar(
            value=(self.existing.requires_pep if self.existing else False))
        ttk.Checkbutton(form, text="Requires PEEP (evac plan)",
                          variable=self.pep_var).grid(
            row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Fire / evac notes:").grid(row=r, column=0,
                                                          sticky="ne", pady=4)
        self.evac_t = tk.Text(form, width=44, height=2)
        if self.existing and self.existing.fire_evac_notes:
            self.evac_t.insert("1.0", self.existing.fire_evac_notes)
        self.evac_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Last reviewed:").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.last_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.last_reviewed:
            self.last_e.insert(0, self.existing.last_reviewed)
        self.last_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Next review due:").grid(row=r, column=0,
                                                        sticky="e", pady=4)
        self.next_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.next_review_due:
            self.next_e.insert(0, self.existing.next_review_due)
        self.next_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Reviewer:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.rev_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.reviewer:
            self.rev_e.insert(0, self.existing.reviewer)
        self.rev_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=3)
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
        if self.existing:
            sid = self._student_id
        elif self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Select a student")
            sid = self._student_ids[idx]
        else:
            raise ValidationError("Select a student")
        return {
            "student_id":      sid,
            "send_status":     self.status_cb.get().strip(),
            "has_ehcp":        self.ehcp_var.get(),
            "ehcp_reference":  self.ehcp_ref_e.get().strip(),
            "primary_need":    self.need_cb.get().strip(),
            "secondary_needs": self.sec_t.get("1.0", "end").strip(),
            "diagnoses":       self.diag_t.get("1.0", "end").strip(),
            "mobility_aids":   self.mob_e.get().strip(),
            "requires_pep":    self.pep_var.get(),
            "fire_evac_notes": self.evac_t.get("1.0", "end").strip(),
            "last_reviewed":   self.last_e.get().strip(),
            "next_review_due": self.next_e.get().strip(),
            "reviewer":        self.rev_e.get().strip(),
            "notes":           self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_profile(self.existing.profile_id, payload)
            else:
                data.create_profile(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AccommStatusDialog:
    def __init__(self, parent: tk.Misc, existing: Accommodation,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — accommodation #{existing.accommodation_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=ACCOMMODATION_STATUSES,
                                  state="readonly", width=18)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_accommodation_status(
                self.existing.accommodation_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AccommDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Accommodation | None,
                 default_category: str = DEFAULT_ACCOMMODATION_CATEGORY,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.default_category = default_category
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Accommodation" if existing
                          else "New Accommodation")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                 sticky="e", pady=4)
        if self.existing:
            sid = self.existing.student_id
            self._student_id = sid
            self.student_cb = None
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{sid} — {names.get(sid, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                form, values=[l for _, l in opts],
                state="readonly", width=44)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Category:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.cat_cb = ttk.Combobox(form, values=ACCOMMODATION_CATEGORIES,
                                      state="readonly", width=22)
        self.cat_cb.set(self.existing.category if self.existing
                           else self.default_category)
        self.cat_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.name_cb = ttk.Combobox(form, values=COMMON_ACCOMMODATIONS,
                                       width=40)
        self.name_cb.set(self.existing.name if self.existing else "")
        self.name_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                    sticky="ne", pady=4)
        self.desc_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.description:
            self.desc_t.insert("1.0", self.existing.description)
        self.desc_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=ACCOMMODATION_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_ACCOMMODATION_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(
            0, self.existing.start_date if self.existing and
            self.existing.start_date else _today())
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.end_date:
            self.end_e.insert(0, self.existing.end_date)
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Approved by:").grid(row=r, column=0,
                                                     sticky="e", pady=4)
        self.appby_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.approved_by:
            self.appby_e.insert(0, self.existing.approved_by)
        self.appby_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Approved date:").grid(row=r, column=0,
                                                      sticky="e", pady=4)
        self.appdate_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.approved_date:
            self.appdate_e.insert(0, self.existing.approved_date)
        self.appdate_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Evidence:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.evidence_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.evidence:
            self.evidence_e.insert(0, self.existing.evidence)
        self.evidence_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=3)
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
        if self.existing:
            sid = self._student_id
        elif self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Select a student")
            sid = self._student_ids[idx]
        else:
            raise ValidationError("Select a student")
        return {
            "student_id":    sid,
            "category":      self.cat_cb.get().strip(),
            "name":          self.name_cb.get().strip(),
            "description":   self.desc_t.get("1.0", "end").strip(),
            "status":        self.status_cb.get().strip(),
            "start_date":    self.start_e.get().strip(),
            "end_date":      self.end_e.get().strip(),
            "approved_by":   self.appby_e.get().strip(),
            "approved_date": self.appdate_e.get().strip(),
            "evidence":      self.evidence_e.get().strip(),
            "notes":         self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_accommodation(
                    self.existing.accommodation_id, payload)
            else:
                data.create_accommodation(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
