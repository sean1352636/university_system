import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ExternalExaminerGUI:
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("External Examiner Management")
        self.root.geometry("1200x800")
        try:
            from education_system.systems.university.domain.assessment.external_examiners.services.external_examiner_service import ExternalExaminerService
            self.service = ExternalExaminerService()
        except Exception as e:
            logger.error(f"Service init error: {e}")
            self.service = None
        try:
            from education_system.systems.university.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None
        self.setup_ui()

    def setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._create_examiners_tab(notebook)
        self._create_visits_tab(notebook)
        self._create_action_items_tab(notebook)
        self._create_reports_tab(notebook)

    # --------------------------------------------------------------- Examiners
    def _create_examiners_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Examiners")

        cols = ("name", "institution", "specialisation", "status")
        self.examiners_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.examiners_tree.heading(c, text=c.replace("_", " ").title())
            self.examiners_tree.column(c, width=180)
        self.examiners_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Add", command=self._add_examiner).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Edit", command=self._edit_examiner).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="View History", command=self._view_examiner_history).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_examiners).pack(side=tk.RIGHT, padx=2)

        self._refresh_examiners()

    def _view_examiner_history(self):
        sel = self.examiners_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an examiner first.", parent=self.root)
            return
        name = self.examiners_tree.item(sel[0], "values")[0]
        try:
            match = next((e for e in self.service.list_examiners() if e.get("name") == name), None)
            if not match:
                messagebox.showerror("Error", "Could not resolve examiner.", parent=self.root)
                return
            history = self.service.get_examiner_history(match["id"])
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)
            return

        ex = history["examiner"]
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Examiner History — {ex.get('name', '')}")
        dlg.geometry("760x420")
        dlg.transient(self.root)
        ttk.Label(dlg, text=f"{ex.get('name', '')} — {ex.get('institution', '')} "
                            f"({history['total_visits']} visits)",
                  font=("", 10, "bold")).pack(padx=10, pady=10, anchor=tk.W)

        cols = ("date", "department", "purpose", "rating")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", height=15)
        for c in cols:
            tree.heading(c, text=c.title())
            tree.column(c, width=180, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for v in history["visits"]:
            tree.insert("", tk.END, values=(
                v.get("visit_date", ""), v.get("department", ""),
                v.get("purpose", ""), v.get("overall_rating", ""),
            ))

    def _refresh_examiners(self):
        for row in self.examiners_tree.get_children():
            self.examiners_tree.delete(row)
        if not self.service:
            return
        try:
            examiners = self.service.list_examiners()
            for ex in examiners:
                self.examiners_tree.insert("", tk.END, values=(
                    ex.get("name", ""), ex.get("institution", ""),
                    ex.get("specialisation", ""), ex.get("status", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading examiners: {e}")

    def _add_examiner(self):
        self._examiner_dialog()

    def _edit_examiner(self):
        sel = self.examiners_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an examiner first.", parent=self.root)
            return
        values = self.examiners_tree.item(sel[0], "values")
        self._examiner_dialog(values)

    def _examiner_dialog(self, existing=None):
        dlg = tk.Toplevel(self.root)
        dlg.title("Edit Examiner" if existing else "Add Examiner")
        dlg.geometry("450x400")
        dlg.transient(self.root)
        dlg.grab_set()

        fields = [("Name:", "name"), ("Institution:", "institution"),
                   ("Specialisation:", "specialisation")]
        vars_ = {}
        for label, key in fields:
            ttk.Label(dlg, text=label).pack(padx=10, pady=(10, 0), anchor=tk.W)
            var = tk.StringVar(value=existing[fields.index((label, key))] if existing else "")
            ttk.Entry(dlg, textvariable=var).pack(fill=tk.X, padx=10)
            vars_[key] = var

        ttk.Label(dlg, text="Status:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        status_var = tk.StringVar(value=existing[3] if existing else "Active")
        ttk.Combobox(dlg, textvariable=status_var, values=[
            "Active", "Inactive", "Pending Approval",
        ], state="readonly").pack(fill=tk.X, padx=10)

        def save():
            data = {k: v.get() for k, v in vars_.items()}
            data["status"] = status_var.get()
            if not all(data.values()):
                messagebox.showwarning("Validation", "All fields are required.", parent=dlg)
                return
            try:
                if existing:
                    self.service.update_examiner(existing[0], data)
                else:
                    self.service.add_examiner(data)
                dlg.destroy()
                self._refresh_examiners()
                messagebox.showinfo("Success", "Examiner saved.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    # ----------------------------------------------------------------- Visits
    def _create_visits_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Visits")

        cols = ("id", "examiner", "date", "department", "rating")
        self.visits_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.visits_tree.heading(c, text=c.replace("_", " ").title())
            self.visits_tree.column(c, width=150)
        self.visits_tree.column("id", width=50)
        self.visits_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Schedule", command=self._schedule_visit).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Record Findings", command=self._record_findings).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="View Module Descriptor", command=self._open_descriptor_for_visit).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_visits).pack(side=tk.RIGHT, padx=2)

        self._refresh_visits()

    def _refresh_visits(self):
        for row in self.visits_tree.get_children():
            self.visits_tree.delete(row)
        if not self.service:
            return
        try:
            visits = self.service.list_visits()
            for v in visits:
                self.visits_tree.insert("", tk.END, values=(
                    v.get("id", ""), v.get("examiner_id", ""),
                    v.get("visit_date", ""), v.get("department", ""),
                    v.get("overall_rating", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading visits: {e}")

    def _schedule_visit(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Schedule Visit")
        dlg.geometry("400x350")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Examiner:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        examiner_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=examiner_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Date (YYYY-MM-DD):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(dlg, textvariable=date_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Department:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        dept_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=dept_var).pack(fill=tk.X, padx=10)

        def save():
            if not examiner_var.get() or not date_var.get() or not dept_var.get():
                messagebox.showwarning("Validation", "All fields are required.", parent=dlg)
                return
            try:
                self.service.schedule_visit({
                    "examiner": examiner_var.get(),
                    "date": date_var.get(),
                    "department": dept_var.get(),
                    "rating": "",
                })
                dlg.destroy()
                self._refresh_visits()
                messagebox.showinfo("Success", "Visit scheduled.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    def _record_findings(self):
        sel = self.visits_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a visit first.", parent=self.root)
            return
        values = self.visits_tree.item(sel[0], "values")

        dlg = tk.Toplevel(self.root)
        dlg.title("Record Findings")
        dlg.geometry("450x400")
        dlg.transient(self.root)
        dlg.grab_set()

        visit_id = values[0]
        examiner = values[1]
        visit_date = values[2]

        ttk.Label(dlg, text=f"Visit #{visit_id}: {examiner} on {visit_date}",
                  font=("", 10, "bold")).pack(padx=10, pady=10)

        ttk.Label(dlg, text="Rating:").pack(padx=10, anchor=tk.W)
        rating_var = tk.StringVar()
        ttk.Combobox(dlg, textvariable=rating_var, values=[
            "Excellent", "Good", "Satisfactory", "Needs Improvement",
        ], state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Findings:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        findings_text = tk.Text(dlg, height=8)
        findings_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def save():
            if not rating_var.get():
                messagebox.showwarning("Validation", "Please provide a rating.", parent=dlg)
                return
            try:
                self.service.record_findings(
                    visit_id=int(visit_id),
                    findings=findings_text.get("1.0", tk.END).strip(),
                    overall_rating=rating_var.get(),
                )
                dlg.destroy()
                self._refresh_visits()
                messagebox.showinfo("Success", "Findings recorded.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=10)

    def _open_descriptor_for_visit(self):
        sel = self.visits_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a visit first.", parent=self.root)
            return
        visit_id = self.visits_tree.item(sel[0], "values")[0]
        try:
            visit = self.service.get_visit(int(visit_id))
            modules_reviewed = (visit or {}).get("modules_reviewed") or ""
            from education_system.systems.university.domain.academics.curriculum_specification.services.curriculum_specification_service import CurriculumSpecificationService
            curr = CurriculumSpecificationService()
            descriptors = curr.list_module_descriptors()
            matches = [d for d in descriptors if d["module_code"] in modules_reviewed]
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Module Descriptors for Visit #{visit_id}")
        dlg.geometry("800x420")
        dlg.transient(self.root)
        if not matches:
            ttk.Label(dlg, text="No curriculum-spec descriptors match the modules\n"
                                "listed for this visit. (Set 'Modules reviewed' on the\n"
                                "visit using module codes.)",
                      padding=20).pack()
            return
        cols = ("code", "version", "title", "credits", "level", "leader")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", height=15)
        widths = {"code": 90, "version": 60, "title": 320, "credits": 70, "level": 60, "leader": 150}
        for c in cols:
            tree.heading(c, text=c.title())
            tree.column(c, width=widths[c], anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for d in matches:
            tree.insert("", tk.END, values=(
                d["module_code"], d["version"], d["title"],
                d.get("credits") or "", d.get("level") or "",
                d.get("module_leader") or "",
            ))

    # ------------------------------------------------------------- Action Items
    def _create_action_items_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Action Items")

        cols = ("id", "description", "responsible", "deadline", "status")
        self.actions_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.actions_tree.heading(c, text=c.replace("_", " ").title())
            self.actions_tree.column(c, width=180)
        self.actions_tree.column("id", width=50)
        self.actions_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Add", command=self._add_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Update Status", command=self._update_action_status).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Overdue Actions", command=self._show_overdue_actions).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_actions).pack(side=tk.RIGHT, padx=2)

        self._refresh_actions()

    def _show_overdue_actions(self):
        try:
            overdue = self.service.get_overdue_actions()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Overdue Actions")
        dlg.geometry("760x420")
        dlg.transient(self.root)
        if not overdue:
            ttk.Label(dlg, text="No overdue actions.", padding=20).pack()
            return
        cols = ("deadline", "description", "responsible", "status")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", height=15)
        for c in cols:
            tree.heading(c, text=c.title())
            tree.column(c, width=180, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for a in overdue:
            tree.insert("", tk.END, values=(
                a.get("deadline", ""), a.get("action_description", ""),
                a.get("responsible_person", ""), a.get("status", ""),
            ))

    def _refresh_actions(self):
        for row in self.actions_tree.get_children():
            self.actions_tree.delete(row)
        if not self.service:
            return
        try:
            actions = self.service.list_actions()
            for a in actions:
                self.actions_tree.insert("", tk.END, values=(
                    a.get("id", ""), a.get("action_description", ""),
                    a.get("responsible_person", ""), a.get("deadline", ""),
                    a.get("status", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading action items: {e}")

    def _add_action(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Action Item")
        dlg.geometry("450x350")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Description:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        desc_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=desc_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Responsible:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        resp_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=resp_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Deadline (YYYY-MM-DD):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        deadline_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=deadline_var).pack(fill=tk.X, padx=10)

        def save():
            if not desc_var.get() or not resp_var.get() or not deadline_var.get():
                messagebox.showwarning("Validation", "All fields are required.", parent=dlg)
                return
            try:
                self.service.add_action_item({
                    "description": desc_var.get(),
                    "responsible": resp_var.get(),
                    "deadline": deadline_var.get(),
                    "status": "Open",
                })
                dlg.destroy()
                self._refresh_actions()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    def _update_action_status(self):
        sel = self.actions_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an action item first.", parent=self.root)
            return
        values = self.actions_tree.item(sel[0], "values")

        dlg = tk.Toplevel(self.root)
        dlg.title("Update Status")
        dlg.geometry("350x200")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Action: {values[1][:60]}").pack(padx=10, pady=10)
        ttk.Label(dlg, text="New Status:").pack(padx=10, anchor=tk.W)
        status_var = tk.StringVar(value=values[4])
        ttk.Combobox(dlg, textvariable=status_var, values=[
            "Open", "In Progress", "Completed", "Overdue",
        ], state="readonly").pack(fill=tk.X, padx=10)

        def save():
            try:
                self.service.update_action_status(int(values[0]), status_var.get())
                dlg.destroy()
                self._refresh_actions()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Update", command=save).pack(pady=15)

    # ---------------------------------------------------------------- Reports
    def _create_reports_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Reports")

        report_frame = ttk.LabelFrame(tab, text="Department Summary")
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cols = ("department", "examiners", "visits", "avg_rating", "open_actions")
        self.reports_tree = ttk.Treeview(report_frame, columns=cols, show="headings", height=15)
        for c in cols:
            self.reports_tree.heading(c, text=c.replace("_", " ").title())
            self.reports_tree.column(c, width=150)
        self.reports_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Button(report_frame, text="Generate Report", command=self._generate_report).pack(pady=5)

    def _generate_report(self):
        for row in self.reports_tree.get_children():
            self.reports_tree.delete(row)
        if not self.service:
            return
        try:
            report = self.service.get_department_summary()
            for r in report:
                self.reports_tree.insert("", tk.END, values=(
                    r.get("department", ""), r.get("examiners", 0),
                    r.get("visits", 0), r.get("avg_rating", ""),
                    r.get("open_actions", 0),
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)
