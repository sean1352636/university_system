"""Timetable GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.academics.timetable.services.timetable_service import (
    TimetableService, DAYS, PERIODS,
)
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.core.exceptions import TimetableError


class TimetableFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._svc = TimetableService(db_path)
        self._subj_svc = SubjectService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Timetable", font=("Helvetica", 15, "bold"),
                 bg="#1a5276", fg="white").pack(side="left", padx=20, pady=10)

        controls = tk.Frame(self, bg="#ecf0f1", pady=8)
        controls.pack(fill="x", padx=15)

        tk.Label(controls, text="Year:", bg="#ecf0f1").pack(side="left", padx=4)
        self._year_var = tk.StringVar(value="7")
        ttk.Combobox(controls, textvariable=self._year_var,
                     values=["7", "8", "9", "10", "11"],
                     state="readonly", width=5).pack(side="left", padx=4)

        tk.Label(controls, text="Form:", bg="#ecf0f1").pack(side="left", padx=(15, 4))
        self._form_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self._form_var, width=6).pack(side="left", padx=4)

        ttk.Button(controls, text="Load", command=self._load_timetable).pack(side="left", padx=15)
        ttk.Button(controls, text="Add Slot", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(controls, text="Delete Slot", command=self._on_delete).pack(side="left", padx=4)

        # Separator
        ttk.Separator(controls, orient="vertical").pack(side="left", fill="y", padx=10)

        # Auto-generate buttons
        ttk.Button(controls, text="Generate Year", command=self._on_generate_year).pack(side="left", padx=4)
        ttk.Button(controls, text="Generate All Years", command=self._on_generate_all).pack(side="left", padx=4)

        # Grid-style timetable display
        self._grid_frame = tk.Frame(self, bg="white", bd=1, relief="solid")
        self._grid_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self._status_var = tk.StringVar(value="Select year/form and load")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        pass

    def _load_timetable(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()

        year = self._year_var.get()
        form = self._form_var.get().strip() or None

        # Header row
        tk.Label(self._grid_frame, text="Period", font=("Helvetica", 10, "bold"),
                 bg="#1a5276", fg="white", width=8, relief="ridge").grid(row=0, column=0, sticky="nsew")
        for col, day in enumerate(DAYS, 1):
            tk.Label(self._grid_frame, text=day, font=("Helvetica", 10, "bold"),
                     bg="#1a5276", fg="white", width=15, relief="ridge").grid(
                row=0, column=col, sticky="nsew")

        try:
            slots = self._svc.get_timetable(year_group=year, form_group=form)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        # Build lookup
        lookup: dict[tuple, dict] = {}
        for s in slots:
            key = (s["day_of_week"], s["period"])
            lookup[key] = s

        self._slot_ids = {}
        for row, period in enumerate(PERIODS, 1):
            tk.Label(self._grid_frame, text=str(period), font=("Helvetica", 10),
                     bg="#d5dbdb", width=8, relief="ridge").grid(row=row, column=0, sticky="nsew")
            for col, day in enumerate(DAYS, 1):
                slot = lookup.get((day, period))
                if slot:
                    text = f"{slot.get('subject_code', '')}\n{slot.get('teacher', '') or ''}\n{slot.get('room', '') or ''}"
                    bg_color = "#d4efdf"
                    self._slot_ids[(row, col)] = slot["id"]
                else:
                    text = ""
                    bg_color = "#fdfefe"
                    self._slot_ids[(row, col)] = None

                lbl = tk.Label(self._grid_frame, text=text, font=("Helvetica", 9),
                               bg=bg_color, width=15, height=3, relief="ridge", wraplength=110)
                lbl.grid(row=row, column=col, sticky="nsew")

        self._status_var.set(f"{len(slots)} slot(s) for Year {year}")

    def _on_add(self):
        subjects = self._subj_svc.list_subjects(status="active")
        if not subjects:
            messagebox.showwarning("Warning", "No subjects available.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Add Timetable Slot")
        dlg.resizable(False, False)
        dlg.grab_set()

        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()

        subj_names = [f"{s['subject_code']} - {s['title']}" for s in subjects]
        vars_ = {}

        row = 0
        tk.Label(c, text="Subject", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["subject"] = tk.StringVar()
        ttk.Combobox(c, textvariable=vars_["subject"], values=subj_names,
                     state="readonly", width=30).grid(row=row, column=1, **pad)

        row += 1
        tk.Label(c, text="Day", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["day"] = tk.StringVar(value="Monday")
        ttk.Combobox(c, textvariable=vars_["day"], values=list(DAYS),
                     state="readonly", width=30).grid(row=row, column=1, **pad)

        row += 1
        tk.Label(c, text="Period", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["period"] = tk.StringVar(value="1")
        ttk.Combobox(c, textvariable=vars_["period"], values=[str(p) for p in PERIODS],
                     state="readonly", width=30).grid(row=row, column=1, **pad)

        for label, key in [("Room", "room"), ("Teacher", "teacher")]:
            row += 1
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar()
            ttk.Entry(c, textvariable=vars_[key], width=32).grid(row=row, column=1, **pad)

        result = [None]

        def save():
            subj_val = vars_["subject"].get()
            if not subj_val:
                messagebox.showwarning("Validation", "Select a subject.")
                return
            code = subj_val.split(" - ")[0]
            subj_pk = None
            for s in subjects:
                if s["subject_code"] == code:
                    subj_pk = s["id"]
                    break

            result[0] = {
                "subject_id": subj_pk,
                "day": vars_["day"].get(),
                "period": int(vars_["period"].get()),
                "room": vars_["room"].get().strip() or None,
                "teacher": vars_["teacher"].get().strip() or None,
            }
            dlg.destroy()

        row += 1
        btn = tk.Frame(c)
        btn.grid(row=row, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

        self.wait_window(dlg)
        if result[0] is None:
            return

        d = result[0]
        try:
            self._svc.add_slot(
                subject_id=d["subject_id"],
                day_of_week=d["day"],
                period=d["period"],
                room=d["room"],
                teacher=d["teacher"],
                year_group=self._year_var.get(),
                form_group=self._form_var.get().strip() or None,
            )
            messagebox.showinfo("Success", "Timetable slot added.")
            self._load_timetable()
        except TimetableError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        messagebox.showinfo("Delete", "Click on a slot in the timetable grid to select, then delete.\n"
                            "Feature: select a filled slot and confirm deletion.")

    def _on_generate_year(self):
        year = self._year_var.get()
        if not messagebox.askyesno(
            "Generate Timetable",
            f"This will clear and regenerate the entire timetable for Year {year}.\n\n"
            "Core subjects (Maths, English, Science, etc.) will be allocated fixed periods.\n"
            "Remaining slots will be filled with option subjects.\n\n"
            "Continue?"
        ):
            return

        try:
            result = self._svc.generate_timetable(year)
            lines = [
                f"Timetable generated for Year {year}!\n",
                f"Total slots: {result['total_slots']}",
                f"Core: {result['core_slots']}  |  Options: {result['option_slots']}\n",
                "Subjects:",
            ]
            for subj, count in sorted(result["subjects"].items()):
                lines.append(f"  {subj}: {count} period(s)")

            messagebox.showinfo("Timetable Generated", "\n".join(lines))
            self._load_timetable()
        except TimetableError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_generate_all(self):
        if not messagebox.askyesno(
            "Generate All Timetables",
            "This will clear and regenerate timetables for ALL year groups (7-11).\n\n"
            "Continue?"
        ):
            return

        try:
            results = self._svc.generate_all_timetables()
            lines = ["Timetables generated for all year groups!\n"]
            for r in results:
                lines.append(f"Year {r['year_group']}: {r['total_slots']} slots "
                             f"({r['core_slots']} core + {r['option_slots']} options)")
            total = sum(r["total_slots"] for r in results)
            lines.append(f"\nTotal: {total} slots across 5 year groups")

            messagebox.showinfo("All Timetables Generated", "\n".join(lines))
            self._load_timetable()
        except TimetableError as exc:
            messagebox.showerror("Error", str(exc))
