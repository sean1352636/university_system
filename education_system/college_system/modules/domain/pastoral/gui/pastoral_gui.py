"""Pastoral GUI for managing tutor notes, wellbeing, and LAC records."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.pastoral.services.pastoral_service import PastoralService
from education_system.college_system.core.i18n import t


class PastoralFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = PastoralService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("pastoral.title"), font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Notes tab
        self._notes_tab = tk.Frame(self._nb)
        self._nb.add(self._notes_tab, text=t("pastoral.pastoral_notes"))
        self._build_notes_tab()

        # Wellbeing tab
        self._wb_tab = tk.Frame(self._nb)
        self._nb.add(self._wb_tab, text=t("pastoral.wellbeing"))
        self._build_wellbeing_tab()

        # LAC tab
        self._lac_tab = tk.Frame(self._nb)
        self._nb.add(self._lac_tab, text=t("pastoral.lac_records"))
        self._build_lac_tab()

    def _build_notes_tab(self):
        toolbar = tk.Frame(self._notes_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        tk.Label(toolbar, text=t("common.student_id_colon")).pack(side="left", padx=5)
        self._note_sid = tk.Entry(toolbar, width=10)
        self._note_sid.pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.search"), command=self._load_notes).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("pastoral.add_note"), command=self._add_note).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_notes_csv).pack(side="right", padx=5)

        cols = ("id", "student", "category", "confidential", "date")
        self._notes_tree = ttk.Treeview(self._notes_tab, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (50, 120, 100, 80, 120)):
            self._notes_tree.heading(c, text=c.title())
            self._notes_tree.column(c, width=w)
        self._notes_tree.pack(fill="both", expand=True, padx=5, pady=5)

        self._note_detail = tk.Text(self._notes_tab, height=4, state="disabled")
        self._note_detail.pack(fill="x", padx=5, pady=5)
        self._notes_tree.bind("<<TreeviewSelect>>", self._on_note_select)

    def _build_wellbeing_tab(self):
        toolbar = tk.Frame(self._wb_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        tk.Label(toolbar, text=t("common.student_id_colon")).pack(side="left", padx=5)
        self._wb_sid = tk.Entry(toolbar, width=10)
        self._wb_sid.pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.search"), command=self._load_wellbeing).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("pastoral.record_check"), command=self._record_wellbeing).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_wellbeing_csv).pack(side="right", padx=5)

        cols = ("id", "student", "score", "concerns", "date")
        self._wb_tree = ttk.Treeview(self._wb_tab, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (50, 120, 60, 200, 120)):
            self._wb_tree.heading(c, text=c.title())
            self._wb_tree.column(c, width=w)
        self._wb_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_lac_tab(self):
        toolbar = tk.Frame(self._lac_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_lac).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("pastoral.add_lac_record"), command=self._add_lac).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_lac_csv).pack(side="right", padx=5)

        cols = ("id", "student", "local_authority", "care_status", "pep_date")
        self._lac_tree = ttk.Treeview(self._lac_tab, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (50, 120, 150, 100, 100)):
            self._lac_tree.heading(c, text=c.replace("_", " ").title())
            self._lac_tree.column(c, width=w)
        self._lac_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_notes(self):
        for item in self._notes_tree.get_children():
            self._notes_tree.delete(item)
        try:
            sid = self._note_sid.get().strip()
            notes = self._svc.list_notes(student_id=int(sid) if sid else None)
            for n in notes:
                name = f"{n.get('first_name', '')} {n.get('last_name', '')}".strip() or str(n.get("student_id", ""))
                self._notes_tree.insert("", "end", iid=str(n["id"]), values=(
                    n["id"], name, n.get("category", ""),
                    "Yes" if n.get("is_confidential") else "No",
                    n.get("created_at", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_note_select(self, _event=None):
        sel = self._notes_tree.selection()
        if not sel:
            return
        try:
            note = self._svc.get_note(int(sel[0]))
            self._note_detail.configure(state="normal")
            self._note_detail.delete("1.0", "end")
            self._note_detail.insert("end", note.get("content", ""))
            self._note_detail.configure(state="disabled")
        except Exception:
            pass

    def _add_note(self):
        win = tk.Toplevel(self)
        win.title(t("pastoral.add_pastoral_note"))
        win.geometry("400x350")
        fields = {}
        row = 0
        for label, key in [(t("common.student_id_required"), "student_id")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text=t("common.category_colon")).grid(row=row, column=0, padx=10, pady=5, sticky="e")
        cat_var = tk.StringVar(value="general")
        ttk.Combobox(win, textvariable=cat_var,
                      values=["general", "academic", "personal", "attendance", "safeguarding"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        tk.Label(win, text=t("pastoral.content_required")).grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        content = tk.Text(win, width=30, height=6)
        content.grid(row=row, column=1, padx=10, pady=5)
        row += 1
        conf_var = tk.BooleanVar()
        ttk.Checkbutton(win, text=t("pastoral.confidential"), variable=conf_var).grid(row=row, column=1, sticky="w", padx=10)
        row += 1

        def save():
            try:
                user_id = self._auth.current_user["user_id"] if self._auth and self._auth.current_user else 1
                self._svc.add_note(
                    student_id=int(fields["student_id"].get().strip()),
                    author_id=user_id,
                    category=cat_var.get(),
                    content=content.get("1.0", "end").strip(),
                    is_confidential=1 if conf_var.get() else 0)
                messagebox.showinfo(t("common.success"), t("pastoral.note_added"))
                win.destroy()
                self._load_notes()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _load_wellbeing(self):
        for item in self._wb_tree.get_children():
            self._wb_tree.delete(item)
        try:
            sid = self._wb_sid.get().strip()
            records = self._svc.list_wellbeing(student_id=int(sid) if sid else None)
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._wb_tree.insert("", "end", values=(
                    r["id"], name, r.get("mood_score", ""),
                    r.get("concerns", ""), r.get("check_date", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _record_wellbeing(self):
        win = tk.Toplevel(self)
        win.title(t("pastoral.record_wellbeing_check"))
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [(t("common.student_id_required"), "student_id")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text=t("pastoral.mood_score")).grid(row=row, column=0, padx=10, pady=5, sticky="e")
        score = tk.Spinbox(win, from_=1, to=10, width=5)
        score.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1
        tk.Label(win, text=t("pastoral.concerns_colon")).grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        concerns = tk.Text(win, width=30, height=3)
        concerns.grid(row=row, column=1, padx=10, pady=5)
        row += 1
        tk.Label(win, text=t("pastoral.support_offered_colon")).grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        support = tk.Text(win, width=30, height=3)
        support.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                user_id = self._auth.current_user["user_id"] if self._auth and self._auth.current_user else 1
                self._svc.record_wellbeing(
                    student_id=int(fields["student_id"].get().strip()),
                    recorded_by=user_id,
                    mood_score=int(score.get()),
                    concerns=concerns.get("1.0", "end").strip() or None,
                    support_offered=support.get("1.0", "end").strip() or None)
                messagebox.showinfo(t("common.success"), t("pastoral.wellbeing_recorded"))
                win.destroy()
                self._load_wellbeing()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _load_lac(self):
        for item in self._lac_tree.get_children():
            self._lac_tree.delete(item)
        try:
            records = self._svc.list_lac_records()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._lac_tree.insert("", "end", values=(
                    r["id"], name, r.get("local_authority", ""),
                    r.get("care_status", ""), r.get("pep_date", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _add_lac(self):
        win = tk.Toplevel(self)
        win.title(t("pastoral.add_lac_record"))
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [(t("common.student_id_required"), "student_id"), (t("pastoral.local_authority_required"), "local_authority"),
                           (t("pastoral.social_worker_colon"), "social_worker_name"), (t("pastoral.contact_colon"), "social_worker_contact"),
                           (t("pastoral.pep_date_colon"), "pep_date")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                self._svc.create_lac_record(
                    student_id=int(fields["student_id"].get().strip()),
                    local_authority=fields["local_authority"].get().strip(),
                    social_worker_name=fields["social_worker_name"].get().strip() or None,
                    social_worker_contact=fields["social_worker_contact"].get().strip() or None,
                    pep_date=fields["pep_date"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("pastoral.lac_record_created"))
                win.destroy()
                self._load_lac()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _export_notes_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._notes_tree, "pastoral_notes.csv")

    def _export_wellbeing_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._wb_tree, "pastoral_wellbeing.csv")

    def _export_lac_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._lac_tree, "pastoral_lac.csv")

    def refresh(self):
        self._load_notes()
        self._load_lac()
