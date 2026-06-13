"""Tkinter views for Medical Records.

Single window with four tabs:

* **Students** — overview table with counts per student (conditions,
  severe conditions, current meds, emergency meds, allergies, severe
  allergies). Double-click to open the student detail window.
* **Flagged** — students with at least one severe condition / severe
  or life-threatening allergy / emergency medication.
* **EpiPen holders** — quick list of allergies marked as EpiPen-held.
* **Summary** — overall counts.

The detail window shows the student's profile + lists of conditions
/ medications / allergies with per-row add/edit/delete buttons.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.shared import branding
from education_system.sixthform_system.modules.domain.pastoral.medical_records import (
    medical_records as data,
)
from education_system.sixthform_system.modules.domain.pastoral.medical_records.medical_records import (
    ALLERGY_SEVERITIES,
    Allergy,
    BLOOD_GROUPS,
    CONDITION_SEVERITIES,
    Condition,
    DEFAULT_ALLERGY_SEVERITY,
    DEFAULT_CONDITION_SEVERITY,
    DEFAULT_MEDICATION_ROUTE,
    MEDICATION_ROUTES,
    Medication,
    MedicalProfile,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_SEVERE_TAG_COLOURS = ("#ffd1d1", "#8c0d0d")
_FLAG_TAG_COLOURS = ("#fff0d6", "#7a5800")


def open_directory(parent=None) -> None:
    try:
        data.init_db()
    except Exception:
        logger.exception("Medical-records init_db failed")
        messagebox.showerror(
            "Medical Records",
            "Could not initialise the database. Check logs.")
        return

    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Medical Records — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    StudentsTab(nb, win, flagged_only=False)
    StudentsTab(nb, win, flagged_only=True)
    EpiPenTab(nb, win)
    SummaryTab(nb)


# ─────────────────────────────────────────────────────────────────
# Students tab (re-used for "All" and "Flagged")
# ─────────────────────────────────────────────────────────────────

class StudentsTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc,
                  *, flagged_only: bool) -> None:
        self.root = root
        self.flagged_only = flagged_only
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=("Flagged" if flagged_only
                                   else "Students"))
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_id = ttk.Entry(bar, width=12)
        self.f_id.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="Open selected",
                    command=self._open).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("student_id", "name", "profile",
                 "cond_active", "cond_severe",
                 "meds_curr", "meds_emerg",
                 "alg_total", "alg_severe")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"student_id": 100, "name": 220, "profile": 80,
                   "cond_active": 90, "cond_severe": 100,
                   "meds_curr": 100, "meds_emerg": 100,
                   "alg_total": 90, "alg_severe": 110}
        labels = {"student_id": "Student", "name": "Name",
                   "profile": "Profile",
                   "cond_active": "Conditions",
                   "cond_severe": "Severe cond.",
                   "meds_curr": "Current meds",
                   "meds_emerg": "Emergency",
                   "alg_total": "Allergies",
                   "alg_severe": "Severe/Life-t"}
        for c in cols:
            self.tree.heading(c, text=labels[c])
            self.tree.column(c, width=widths[c],
                              anchor=("w" if c in ("student_id", "name")
                                       else "center"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("severe",
                                  background=_SEVERE_TAG_COLOURS[0],
                                  foreground=_SEVERE_TAG_COLOURS[1])
        self.tree.tag_configure("flag",
                                  background=_FLAG_TAG_COLOURS[0],
                                  foreground=_FLAG_TAG_COLOURS[1])
        self.tree.bind("<Double-Button-1>", lambda _e: self._open())

        self.count = ttk.Label(self.frame, text="")
        self.count.pack(anchor="e", padx=8, pady=(0, 8))

    def _clear(self) -> None:
        self.f_id.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.all_student_summaries()
        except Exception as e:
            logger.exception("Students refresh failed")
            messagebox.showerror("Medical Records",
                                   f"Could not load: {e}")
            return
        sid_filter = self.f_id.get().strip().lower()
        for s in rows:
            if sid_filter and sid_filter not in s.student_id.lower():
                continue
            is_flagged = (s.severe_conditions
                            or s.severe_allergies
                            or s.emergency_medications)
            if self.flagged_only and not is_flagged:
                continue
            tags = []
            if s.severe_conditions or s.severe_allergies:
                tags.append("severe")
            elif s.emergency_medications:
                tags.append("flag")
            self.tree.insert(
                "", "end", iid=s.student_id,
                values=(s.student_id, s.student_name,
                          "yes" if s.profile else "—",
                          s.active_conditions, s.severe_conditions,
                          s.current_medications,
                          s.emergency_medications,
                          s.allergies, s.severe_allergies),
                tags=tuple(tags),
            )
        n = len(self.tree.get_children())
        self.count.configure(text=f"{n} student(s)")

    def _open(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Medical Records",
                                 "Select a student first.")
            return
        StudentDetailWindow(self.root, student_id=sel[0],
                              on_change=self.refresh)


# ─────────────────────────────────────────────────────────────────
# Student detail window
# ─────────────────────────────────────────────────────────────────

class StudentDetailWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc, *, student_id: str,
                  on_change=None) -> None:
        super().__init__(master)
        self.student_id = student_id
        self.on_change = on_change
        s = student_data.get_student(student_id)
        name = getattr(s, "full_name", None) or "(unknown)"
        self.title(f"Medical Record — {student_id} ({name})")
        self.geometry("1200x800")
        self.minsize(1000, 700)
        self.transient(master)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.profile_tab = ProfileSubTab(nb, self)
        self.conditions_tab = ConditionsSubTab(nb, self)
        self.medications_tab = MedicationsSubTab(nb, self)
        self.allergies_tab = AllergiesSubTab(nb, self)

    def notify_change(self) -> None:
        self.profile_tab.refresh()
        self.conditions_tab.refresh()
        self.medications_tab.refresh()
        self.allergies_tab.refresh()
        if self.on_change is not None:
            self.on_change()


# ── Profile sub-tab ──────────────────────────────────────────────

class ProfileSubTab:
    def __init__(self, nb: ttk.Notebook,
                  parent: StudentDetailWindow) -> None:
        self.parent = parent
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Profile")
        self._build()
        self.refresh()

    def _build(self) -> None:
        frm = ttk.Frame(self.frame, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        row = 0
        for label, attr in (
                ("NHS number:",                    "e_nhs"),
                ("Blood group:",                   "cb_bg"),
                ("GP name:",                       "e_gp_name"),
                ("GP practice:",                   "e_gp_practice"),
                ("GP phone:",                      "e_gp_phone"),
                ("Emergency contact name:",        "e_ec_name"),
                ("Emergency contact phone:",       "e_ec_phone"),
                ("Relationship:",                  "e_ec_rel"),
                ("Last reviewed (YYYY-MM-DD):",    "e_reviewed"),
        ):
            ttk.Label(frm, text=label).grid(
                row=row, column=0, sticky="w", pady=3)
            if attr == "cb_bg":
                cb = ttk.Combobox(frm,
                                    values=("",) + BLOOD_GROUPS,
                                    state="readonly")
                cb.grid(row=row, column=1, sticky="ew", pady=3)
                setattr(self, attr, cb)
            else:
                e = ttk.Entry(frm)
                e.grid(row=row, column=1, sticky="ew", pady=3)
                setattr(self, attr, e)
            row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=3)
        self.t_notes = tk.Text(frm, height=6, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=3)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Reset",
                    command=self.refresh).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def refresh(self) -> None:
        p = data.get_profile(self.parent.student_id)
        self._set(self.e_nhs,         p.nhs_number if p else "")
        self.cb_bg.set(p.blood_group if p and p.blood_group else "")
        self._set(self.e_gp_name,     p.gp_name if p else "")
        self._set(self.e_gp_practice, p.gp_practice if p else "")
        self._set(self.e_gp_phone,    p.gp_phone if p else "")
        self._set(self.e_ec_name,
                   p.emergency_contact_name if p else "")
        self._set(self.e_ec_phone,
                   p.emergency_contact_phone if p else "")
        self._set(self.e_ec_rel,
                   p.emergency_contact_rel if p else "")
        self._set(self.e_reviewed,    p.last_reviewed if p else "")
        self.t_notes.delete("1.0", "end")
        if p and p.notes:
            self.t_notes.insert("1.0", p.notes)

    @staticmethod
    def _set(entry: ttk.Entry, value: str | None) -> None:
        entry.delete(0, "end")
        if value:
            entry.insert(0, value)

    def _save(self) -> None:
        payload = {
            "student_id":              self.parent.student_id,
            "nhs_number":              self.e_nhs.get(),
            "blood_group":             self.cb_bg.get(),
            "gp_name":                 self.e_gp_name.get(),
            "gp_practice":             self.e_gp_practice.get(),
            "gp_phone":                self.e_gp_phone.get(),
            "emergency_contact_name":  self.e_ec_name.get(),
            "emergency_contact_phone": self.e_ec_phone.get(),
            "emergency_contact_rel":   self.e_ec_rel.get(),
            "last_reviewed":           self.e_reviewed.get(),
            "notes":                   self.t_notes.get(
                "1.0", "end").strip(),
        }
        try:
            data.save_profile(payload)
        except ValidationError as e:
            messagebox.showwarning("Medical Records", str(e),
                                     parent=self.frame)
            return
        except Exception as e:
            logger.exception("Profile save failed")
            messagebox.showerror("Medical Records",
                                   f"Save failed: {e}",
                                   parent=self.frame)
            return
        self.parent.notify_change()
        messagebox.showinfo("Medical Records",
                              "Profile saved.",
                              parent=self.frame)


# ── Conditions sub-tab ───────────────────────────────────────────

class ConditionsSubTab:
    def __init__(self, nb: ttk.Notebook,
                  parent: StudentDetailWindow) -> None:
        self.parent = parent
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Conditions")
        self._build()
        self.refresh()

    def _build(self) -> None:
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(actions, text="Add condition",
                    command=self._add).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "severity", "diagnosed",
                "care_plan", "active")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "name": 280, "severity": 100,
                   "diagnosed": 110, "care_plan": 180, "active": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "active")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("Severe",
                                  background=_SEVERE_TAG_COLOURS[0],
                                  foreground=_SEVERE_TAG_COLOURS[1])
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for c in data.list_conditions(
                student_id=self.parent.student_id):
            self.tree.insert(
                "", "end", iid=str(c.condition_id),
                values=(c.condition_id, c.name, c.severity,
                          c.diagnosed_date or "—",
                          c.care_plan_ref or "—",
                          "yes" if c.active else "no"),
                tags=(c.severity,),
            )

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Medical Records",
                                 "Select a condition first.")
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _add(self) -> None:
        ConditionDialog(self.parent,
                          student_id=self.parent.student_id)

    def _edit(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        c = data.get_condition(cid)
        if c is None:
            self.refresh()
            return
        ConditionDialog(self.parent,
                          student_id=self.parent.student_id,
                          condition=c)

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        if not messagebox.askyesno("Medical Records",
                                       f"Delete condition #{cid}?"):
            return
        try:
            data.delete_condition(cid)
        except Exception as e:
            logger.exception("delete_condition failed")
            messagebox.showerror("Medical Records",
                                   f"Delete failed: {e}")
            return
        self.parent.notify_change()


class ConditionDialog(tk.Toplevel):
    def __init__(self, parent: StudentDetailWindow, *,
                 student_id: str,
                 condition: Condition | None = None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.student_id = student_id
        self.condition = condition
        self.title("Edit Condition" if condition else "New Condition")
        self.geometry("600x540")
        self.transient(parent)
        # Defer grab until the window is actually viewable — Tk
        # raises "grab failed: window not viewable" if grab_set runs
        # before the window mapping has been processed. after_idle
        # queues the grab for the next idle slice of the event loop.
        self.after_idle(self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(frm, text="Name:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_name = ttk.Entry(frm)
        self.e_name.grid(row=row, column=1, sticky="ew", pady=4)
        if condition:
            self.e_name.insert(0, condition.name)
        row += 1

        ttk.Label(frm, text="Severity:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_severity = ttk.Combobox(
            frm, values=CONDITION_SEVERITIES, state="readonly")
        self.cb_severity.set(condition.severity if condition
                                else DEFAULT_CONDITION_SEVERITY)
        self.cb_severity.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Diagnosed (YYYY-MM-DD):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_diag = ttk.Entry(frm)
        self.e_diag.grid(row=row, column=1, sticky="ew", pady=4)
        if condition and condition.diagnosed_date:
            self.e_diag.insert(0, condition.diagnosed_date)
        row += 1

        ttk.Label(frm, text="Care plan reference:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_plan = ttk.Entry(frm)
        self.e_plan.grid(row=row, column=1, sticky="ew", pady=4)
        if condition and condition.care_plan_ref:
            self.e_plan.insert(0, condition.care_plan_ref)
        row += 1

        self.v_active = tk.BooleanVar(
            value=(condition.active if condition else True))
        ttk.Checkbutton(frm, text="Active",
                         variable=self.v_active).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=8, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if condition and condition.notes:
            self.t_notes.insert("1.0", condition.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _save(self) -> None:
        payload = {
            "student_id":     self.student_id,
            "name":           self.e_name.get(),
            "severity":       self.cb_severity.get(),
            "diagnosed_date": self.e_diag.get(),
            "care_plan_ref":  self.e_plan.get(),
            "active":         self.v_active.get(),
            "notes":          self.t_notes.get("1.0", "end").strip(),
        }
        try:
            if self.condition is None:
                data.create_condition(payload)
            else:
                data.update_condition(self.condition.condition_id,
                                        payload)
        except ValidationError as e:
            messagebox.showwarning("Medical Records", str(e),
                                     parent=self)
            return
        except Exception as e:
            logger.exception("Condition save failed")
            messagebox.showerror("Medical Records",
                                   f"Save failed: {e}", parent=self)
            return
        self.parent.notify_change()
        self.destroy()


# ── Medications sub-tab ──────────────────────────────────────────

class MedicationsSubTab:
    def __init__(self, nb: ttk.Notebook,
                  parent: StudentDetailWindow) -> None:
        self.parent = parent
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Medications")
        self._build()
        self.refresh()

    def _build(self) -> None:
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(actions, text="Add medication",
                    command=self._add).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "dose", "frequency", "route",
                "start", "end", "prescribed_by", "emergency")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "name": 200, "dose": 100,
                   "frequency": 130, "route": 90, "start": 100,
                   "end": 100, "prescribed_by": 150,
                   "emergency": 90}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "emergency")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("emergency",
                                  background=_FLAG_TAG_COLOURS[0],
                                  foreground=_FLAG_TAG_COLOURS[1])
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for m in data.list_medications(
                student_id=self.parent.student_id):
            self.tree.insert(
                "", "end", iid=str(m.medication_id),
                values=(m.medication_id, m.name, m.dose or "—",
                          m.frequency or "—", m.route,
                          m.start_date or "—", m.end_date or "—",
                          m.prescribed_by or "—",
                          "yes" if m.is_emergency else "no"),
                tags=("emergency",) if m.is_emergency else (),
            )

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Medical Records",
                                 "Select a medication first.")
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _add(self) -> None:
        MedicationDialog(self.parent,
                            student_id=self.parent.student_id)

    def _edit(self) -> None:
        mid = self._selected_id()
        if mid is None:
            return
        m = data.get_medication(mid)
        if m is None:
            self.refresh()
            return
        MedicationDialog(self.parent,
                            student_id=self.parent.student_id,
                            medication=m)

    def _delete(self) -> None:
        mid = self._selected_id()
        if mid is None:
            return
        if not messagebox.askyesno("Medical Records",
                                       f"Delete medication #{mid}?"):
            return
        try:
            data.delete_medication(mid)
        except Exception as e:
            logger.exception("delete_medication failed")
            messagebox.showerror("Medical Records",
                                   f"Delete failed: {e}")
            return
        self.parent.notify_change()


class MedicationDialog(tk.Toplevel):
    def __init__(self, parent: StudentDetailWindow, *,
                 student_id: str,
                 medication: Medication | None = None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.student_id = student_id
        self.medication = medication
        self.title("Edit Medication" if medication else "New Medication")
        self.geometry("640x680")
        self.transient(parent)
        # Defer grab until the window is actually viewable — Tk
        # raises "grab failed: window not viewable" if grab_set runs
        # before the window mapping has been processed. after_idle
        # queues the grab for the next idle slice of the event loop.
        self.after_idle(self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(frm, text="Name:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_name = ttk.Entry(frm)
        self.e_name.grid(row=row, column=1, sticky="ew", pady=4)
        if medication:
            self.e_name.insert(0, medication.name)
        row += 1

        ttk.Label(frm, text="Dose:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_dose = ttk.Entry(frm)
        self.e_dose.grid(row=row, column=1, sticky="ew", pady=4)
        if medication and medication.dose:
            self.e_dose.insert(0, medication.dose)
        row += 1

        ttk.Label(frm, text="Frequency:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_freq = ttk.Entry(frm)
        self.e_freq.grid(row=row, column=1, sticky="ew", pady=4)
        if medication and medication.frequency:
            self.e_freq.insert(0, medication.frequency)
        row += 1

        ttk.Label(frm, text="Route:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_route = ttk.Combobox(
            frm, values=MEDICATION_ROUTES, state="readonly")
        self.cb_route.set(medication.route if medication
                            else DEFAULT_MEDICATION_ROUTE)
        self.cb_route.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Start date (YYYY-MM-DD):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_start = ttk.Entry(frm)
        self.e_start.grid(row=row, column=1, sticky="ew", pady=4)
        if medication and medication.start_date:
            self.e_start.insert(0, medication.start_date)
        row += 1

        ttk.Label(frm, text="End date (YYYY-MM-DD):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_end = ttk.Entry(frm)
        self.e_end.grid(row=row, column=1, sticky="ew", pady=4)
        if medication and medication.end_date:
            self.e_end.insert(0, medication.end_date)
        row += 1

        ttk.Label(frm, text="Prescribed by:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_pres = ttk.Entry(frm)
        self.e_pres.grid(row=row, column=1, sticky="ew", pady=4)
        if medication and medication.prescribed_by:
            self.e_pres.insert(0, medication.prescribed_by)
        row += 1

        self.v_emergency = tk.BooleanVar(
            value=(medication.is_emergency if medication else False))
        ttk.Checkbutton(frm, text="Emergency medication",
                         variable=self.v_emergency).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=6, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if medication and medication.notes:
            self.t_notes.insert("1.0", medication.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _save(self) -> None:
        payload = {
            "student_id":    self.student_id,
            "name":          self.e_name.get(),
            "dose":          self.e_dose.get(),
            "frequency":     self.e_freq.get(),
            "route":         self.cb_route.get(),
            "start_date":    self.e_start.get(),
            "end_date":      self.e_end.get(),
            "prescribed_by": self.e_pres.get(),
            "is_emergency":  self.v_emergency.get(),
            "notes":         self.t_notes.get("1.0", "end").strip(),
        }
        try:
            if self.medication is None:
                data.create_medication(payload)
            else:
                data.update_medication(self.medication.medication_id,
                                          payload)
        except ValidationError as e:
            messagebox.showwarning("Medical Records", str(e),
                                     parent=self)
            return
        except Exception as e:
            logger.exception("Medication save failed")
            messagebox.showerror("Medical Records",
                                   f"Save failed: {e}", parent=self)
            return
        self.parent.notify_change()
        self.destroy()


# ── Allergies sub-tab ────────────────────────────────────────────

class AllergiesSubTab:
    def __init__(self, nb: ttk.Notebook,
                  parent: StudentDetailWindow) -> None:
        self.parent = parent
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Allergies")
        self._build()
        self.refresh()

    def _build(self) -> None:
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(actions, text="Add allergy",
                    command=self._add).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "allergen", "severity", "reaction",
                "epipen")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "allergen": 240, "severity": 130,
                   "reaction": 320, "epipen": 90}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "epipen")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("Severe",
                                  background=_FLAG_TAG_COLOURS[0],
                                  foreground=_FLAG_TAG_COLOURS[1])
        self.tree.tag_configure("Life-threatening",
                                  background=_SEVERE_TAG_COLOURS[0],
                                  foreground=_SEVERE_TAG_COLOURS[1])
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for a in data.list_allergies(
                student_id=self.parent.student_id):
            self.tree.insert(
                "", "end", iid=str(a.allergy_id),
                values=(a.allergy_id, a.allergen, a.severity,
                          a.reaction or "—",
                          "yes" if a.has_epipen else "no"),
                tags=(a.severity,),
            )

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Medical Records",
                                 "Select an allergy first.")
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _add(self) -> None:
        AllergyDialog(self.parent,
                         student_id=self.parent.student_id)

    def _edit(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        a = data.get_allergy(aid)
        if a is None:
            self.refresh()
            return
        AllergyDialog(self.parent,
                         student_id=self.parent.student_id,
                         allergy=a)

    def _delete(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        if not messagebox.askyesno("Medical Records",
                                       f"Delete allergy #{aid}?"):
            return
        try:
            data.delete_allergy(aid)
        except Exception as e:
            logger.exception("delete_allergy failed")
            messagebox.showerror("Medical Records",
                                   f"Delete failed: {e}")
            return
        self.parent.notify_change()


class AllergyDialog(tk.Toplevel):
    def __init__(self, parent: StudentDetailWindow, *,
                 student_id: str,
                 allergy: Allergy | None = None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.student_id = student_id
        self.allergy = allergy
        self.title("Edit Allergy" if allergy else "New Allergy")
        self.geometry("600x500")
        self.transient(parent)
        # Defer grab until the window is actually viewable — Tk
        # raises "grab failed: window not viewable" if grab_set runs
        # before the window mapping has been processed. after_idle
        # queues the grab for the next idle slice of the event loop.
        self.after_idle(self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(frm, text="Allergen:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_allergen = ttk.Entry(frm)
        self.e_allergen.grid(row=row, column=1, sticky="ew", pady=4)
        if allergy:
            self.e_allergen.insert(0, allergy.allergen)
        row += 1

        ttk.Label(frm, text="Severity:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_severity = ttk.Combobox(
            frm, values=ALLERGY_SEVERITIES, state="readonly")
        self.cb_severity.set(allergy.severity if allergy
                                else DEFAULT_ALLERGY_SEVERITY)
        self.cb_severity.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Reaction:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_reaction = ttk.Entry(frm)
        self.e_reaction.grid(row=row, column=1, sticky="ew", pady=4)
        if allergy and allergy.reaction:
            self.e_reaction.insert(0, allergy.reaction)
        row += 1

        self.v_epipen = tk.BooleanVar(
            value=(allergy.has_epipen if allergy else False))
        ttk.Checkbutton(frm, text="EpiPen / auto-injector held",
                         variable=self.v_epipen).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=8, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if allergy and allergy.notes:
            self.t_notes.insert("1.0", allergy.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _save(self) -> None:
        payload = {
            "student_id": self.student_id,
            "allergen":   self.e_allergen.get(),
            "severity":   self.cb_severity.get(),
            "reaction":   self.e_reaction.get(),
            "has_epipen": self.v_epipen.get(),
            "notes":      self.t_notes.get("1.0", "end").strip(),
        }
        try:
            if self.allergy is None:
                data.create_allergy(payload)
            else:
                data.update_allergy(self.allergy.allergy_id, payload)
        except ValidationError as e:
            messagebox.showwarning("Medical Records", str(e),
                                     parent=self)
            return
        except Exception as e:
            logger.exception("Allergy save failed")
            messagebox.showerror("Medical Records",
                                   f"Save failed: {e}", parent=self)
            return
        self.parent.notify_change()
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# EpiPen tab
# ─────────────────────────────────────────────────────────────────

class EpiPenTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="EpiPen holders")
        self._build()
        self.refresh()

    def _build(self) -> None:
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(actions, text="Open student",
                    command=self._open).pack(side="left", padx=4)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student_id", "name", "allergen",
                "severity", "reaction")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "student_id": 100, "name": 200,
                   "allergen": 240, "severity": 140,
                   "reaction": 360}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center" if c == "id" else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-Button-1>", lambda _e: self._open())

        self.count = ttk.Label(self.frame, text="")
        self.count.pack(anchor="e", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_allergies(epipen_only=True)
        except Exception as e:
            logger.exception("EpiPen tab refresh failed")
            messagebox.showerror("Medical Records",
                                   f"Could not load: {e}")
            return
        names = {s.student_id: s.full_name
                  for s in student_data.list_students()}
        for a in rows:
            self.tree.insert(
                "", "end", iid=f"{a.allergy_id}",
                values=(a.allergy_id, a.student_id,
                          names.get(a.student_id, "(unknown)"),
                          a.allergen, a.severity,
                          a.reaction or "—"),
            )
        self.count.configure(
            text=f"{len(rows)} EpiPen-held allergie(s)")

    def _open(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        a = data.get_allergy(int(sel[0]))
        if a is None:
            return
        StudentDetailWindow(self.root, student_id=a.student_id,
                              on_change=self.refresh)


# ─────────────────────────────────────────────────────────────────
# Summary tab
# ─────────────────────────────────────────────────────────────────

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        top = ttk.Frame(self.frame, padding=12)
        top.pack(fill="both", expand=True)
        ttk.Button(top, text="Refresh",
                    command=self.refresh).pack(anchor="e")
        self.body = tk.Text(top, wrap="word", font=("Courier", 10),
                             height=30, state="disabled")
        self.body.pack(fill="both", expand=True, pady=(8, 0))

    def refresh(self) -> None:
        try:
            s = data.summary()
        except Exception as e:
            logger.exception("Medical-records summary failed")
            messagebox.showerror("Medical Records",
                                   f"Summary failed: {e}")
            return
        lines = [
            f"Profiles                 : {s.total_profiles}",
            f"Conditions (total)       : {s.total_conditions}",
            f"  Severe active          : {s.severe_conditions}",
            f"Medications (total)      : {s.total_medications}",
            f"  Emergency              : {s.emergency_medications}",
            f"Allergies (total)        : {s.total_allergies}",
            f"  Severe / life-threat   : {s.severe_allergies}",
            f"Students with EpiPen     : {s.epipen_holders}",
            f"Students flagged overall : {s.students_with_flag}",
        ]
        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        self.body.insert("1.0", "\n".join(lines))
        self.body.configure(state="disabled")
