"""Exams GUI for managing exam entries, timetables, access arrangements, and results."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.exams.services.exams_service import ExamsService
from education_system.college_system.core.i18n import t


class ExamsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ExamsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("exams.title"), font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Entries tab
        self._entries_tab = tk.Frame(self._nb)
        self._nb.add(self._entries_tab, text=t("exams.exam_entries"))
        self._build_entries_tab()

        # Timetable tab
        self._tt_tab = tk.Frame(self._nb)
        self._nb.add(self._tt_tab, text=t("exams.exam_timetable"))
        self._build_timetable_tab()

        # Access tab
        self._access_tab = tk.Frame(self._nb)
        self._nb.add(self._access_tab, text=t("exams.access_arrangements"))
        self._build_access_tab()

        # Results tab
        self._results_tab = tk.Frame(self._nb)
        self._nb.add(self._results_tab, text=t("exams.results"))
        self._build_results_tab()

    def _build_entries_tab(self):
        toolbar = tk.Frame(self._entries_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_entries).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("exams.new_entry"), command=self._new_entry).pack(side="right", padx=5)

        cols = ("id", "student", "board", "subject", "level", "series", "status")
        self._entry_tree = ttk.Treeview(self._entries_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 80, 120, 80, 80, 80)):
            self._entry_tree.heading(c, text=c.title())
            self._entry_tree.column(c, width=w)
        self._entry_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_timetable_tab(self):
        toolbar = tk.Frame(self._tt_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        tk.Label(toolbar, text=t("common.date_colon")).pack(side="left", padx=5)
        self._tt_date = tk.Entry(toolbar, width=12)
        self._tt_date.pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.search"), command=self._load_timetable).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("exams.add_slot"), command=self._new_tt_slot).pack(side="right", padx=5)

        cols = ("id", "board", "subject", "component", "date", "time", "duration", "room")
        self._tt_tree = ttk.Treeview(self._tt_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 80, 120, 100, 100, 80, 70, 80)):
            self._tt_tree.heading(c, text=c.title())
            self._tt_tree.column(c, width=w)
        self._tt_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_access_tab(self):
        toolbar = tk.Frame(self._access_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_access).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("exams.new_arrangement"), command=self._new_access).pack(side="right", padx=5)

        cols = ("id", "student", "type", "extra_time", "approved_by", "jcq_form")
        self._access_tree = ttk.Treeview(self._access_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 150, 80, 100, 100)):
            self._access_tree.heading(c, text=c.replace("_", " ").title())
            self._access_tree.column(c, width=w)
        self._access_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_results_tab(self):
        toolbar = tk.Frame(self._results_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        tk.Label(toolbar, text=t("common.student_id_colon")).pack(side="left", padx=5)
        self._res_sid = tk.Entry(toolbar, width=10)
        self._res_sid.pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.search"), command=self._load_results).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("exams.record_result"), command=self._new_result).pack(side="right", padx=5)

        cols = ("id", "student", "board", "subject", "level", "grade", "ums", "date")
        self._res_tree = ttk.Treeview(self._results_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 80, 120, 80, 60, 60, 100)):
            self._res_tree.heading(c, text=c.title())
            self._res_tree.column(c, width=w)
        self._res_tree.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Data loading ---

    def _load_entries(self):
        for item in self._entry_tree.get_children():
            self._entry_tree.delete(item)
        try:
            entries = self._svc.list_entries()
            for e in entries:
                name = f"{e.get('first_name', '')} {e.get('last_name', '')}".strip() or str(e.get("student_id", ""))
                self._entry_tree.insert("", "end", values=(
                    e["id"], name, e.get("exam_board", ""), e.get("subject", ""),
                    e.get("qualification_level", ""), e.get("series", ""), e.get("status", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_timetable(self):
        for item in self._tt_tree.get_children():
            self._tt_tree.delete(item)
        try:
            date_val = self._tt_date.get().strip()
            slots = self._svc.list_timetable(exam_date=date_val if date_val else None)
            for s in slots:
                self._tt_tree.insert("", "end", values=(
                    s["id"], s.get("exam_board", ""), s.get("subject", ""),
                    s.get("component_code", ""), s.get("exam_date", ""),
                    s.get("start_time", ""), s.get("duration_mins", ""),
                    s.get("room", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_access(self):
        for item in self._access_tree.get_children():
            self._access_tree.delete(item)
        try:
            arrangements = self._svc.list_access_arrangements()
            for a in arrangements:
                name = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() or str(a.get("student_id", ""))
                self._access_tree.insert("", "end", values=(
                    a["id"], name, a.get("arrangement_type", ""),
                    f"{a.get('extra_time_percent', 0)}%" if a.get("extra_time_percent") else "",
                    a.get("approved_by", ""), a.get("jcq_form", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_results(self):
        for item in self._res_tree.get_children():
            self._res_tree.delete(item)
        try:
            sid = self._res_sid.get().strip()
            results = self._svc.list_results(student_id=int(sid) if sid else None)
            for r in results:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._res_tree.insert("", "end", values=(
                    r["id"], name, r.get("exam_board", ""), r.get("subject", ""),
                    r.get("qualification_level", ""), r.get("grade", ""),
                    r.get("ums_mark", ""), r.get("result_date", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # --- New entry dialogs ---

    def _new_entry(self):
        win = tk.Toplevel(self)
        win.title(t("exams.new_exam_entry"))
        win.geometry("400x350")
        fields = {}
        row = 0
        for label, key in [(t("common.student_id_required"), "student_id"), (t("exams.exam_board_required"), "exam_board"),
                           (t("exams.subject_required"), "subject"), (t("exams.level_required"), "qualification_level"),
                           (t("exams.component_code_colon"), "component_code"), (t("exams.series_colon"), "series")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                self._svc.create_entry(
                    student_id=int(fields["student_id"].get().strip()),
                    exam_board=fields["exam_board"].get().strip(),
                    subject=fields["subject"].get().strip(),
                    qualification_level=fields["qualification_level"].get().strip(),
                    component_code=fields["component_code"].get().strip() or None,
                    series=fields["series"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("exams.entry_created"))
                win.destroy()
                self._load_entries()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_tt_slot(self):
        win = tk.Toplevel(self)
        win.title(t("exams.new_timetable_slot"))
        win.geometry("400x400")
        fields = {}
        row = 0
        for label, key in [(t("exams.exam_board_required"), "exam_board"), (t("exams.subject_required"), "subject"),
                           (t("exams.component_required"), "component_code"), (t("exams.date_required"), "exam_date"),
                           (t("exams.start_time_required"), "start_time"), (t("exams.duration_required"), "duration_mins"),
                           (t("exams.room_colon"), "room"), (t("exams.invigilator_colon"), "invigilator")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                self._svc.create_timetable_slot(
                    exam_board=fields["exam_board"].get().strip(),
                    subject=fields["subject"].get().strip(),
                    component_code=fields["component_code"].get().strip(),
                    exam_date=fields["exam_date"].get().strip(),
                    start_time=fields["start_time"].get().strip(),
                    duration_mins=int(fields["duration_mins"].get().strip()),
                    room=fields["room"].get().strip() or None,
                    invigilator=fields["invigilator"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("exams.slot_created"))
                win.destroy()
                self._load_timetable()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_access(self):
        win = tk.Toplevel(self)
        win.title(t("exams.new_access_arrangement"))
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [(t("common.student_id_required"), "student_id"), (t("exams.type_required"), "arrangement_type"),
                           (t("exams.approved_by_colon"), "approved_by"), (t("exams.jcq_form_colon"), "jcq_form"),
                           (t("exams.extra_time_pct_colon"), "extra_time_percent"), (t("exams.details_colon"), "details")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                et = fields["extra_time_percent"].get().strip()
                self._svc.create_access_arrangement(
                    student_id=int(fields["student_id"].get().strip()),
                    arrangement_type=fields["arrangement_type"].get().strip(),
                    approved_by=fields["approved_by"].get().strip() or None,
                    jcq_form=fields["jcq_form"].get().strip() or None,
                    extra_time_percent=int(et) if et else None,
                    details=fields["details"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("exams.arrangement_created"))
                win.destroy()
                self._load_access()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_result(self):
        win = tk.Toplevel(self)
        win.title(t("exams.record_result"))
        win.geometry("400x350")
        fields = {}
        row = 0
        for label, key in [(t("common.student_id_required"), "student_id"), (t("exams.exam_board_required"), "exam_board"),
                           (t("exams.subject_required"), "subject"), (t("exams.level_required"), "qualification_level"),
                           (t("exams.grade_required"), "grade"), (t("exams.ums_mark_colon"), "ums_mark"),
                           (t("exams.raw_mark_colon"), "raw_mark"), (t("exams.series_colon"), "series")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                ums = fields["ums_mark"].get().strip()
                raw = fields["raw_mark"].get().strip()
                self._svc.record_result(
                    student_id=int(fields["student_id"].get().strip()),
                    exam_board=fields["exam_board"].get().strip(),
                    subject=fields["subject"].get().strip(),
                    qualification_level=fields["qualification_level"].get().strip(),
                    grade=fields["grade"].get().strip(),
                    ums_mark=int(ums) if ums else None,
                    raw_mark=int(raw) if raw else None,
                    series=fields["series"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("exams.result_recorded"))
                win.destroy()
                self._load_results()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _export_csv(self):
        """Export the currently visible exams tab's treeview to CSV."""
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        current_tab = self._nb.index(self._nb.select())
        trees = [self._entry_tree, self._tt_tree, self._access_tree, self._res_tree]
        names = ["exam_entries.csv", "exam_timetable.csv", "access_arrangements.csv", "exam_results.csv"]
        export_treeview_to_csv(trees[current_tab], default_filename=names[current_tab])

    def refresh(self):
        self._load_entries()
        self._load_timetable()
        self._load_access()
