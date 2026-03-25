import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ClearingAdjustmentGUI:
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Clearing & Adjustment")
        self.root.geometry("1200x800")
        try:
            from education_system.university_system.modules.domain.clearing_adjustment.services.clearing_adjustment_service import ClearingAdjustmentService
            self.service = ClearingAdjustmentService()
        except Exception as e:
            logger.error(f"Service init error: {e}")
            self.service = None
        try:
            from education_system.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None
        self.setup_ui()

    def setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._create_vacancies_tab(notebook)
        self._create_applications_tab(notebook)
        self._create_adjustment_tab(notebook)
        self._create_statistics_tab(notebook)

    # -------------------------------------------------------------- Vacancies
    def _create_vacancies_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Vacancies")

        cols = ("course", "department", "places", "min_tariff")
        self.vacancies_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.vacancies_tree.heading(c, text=c.replace("_", " ").title())
            self.vacancies_tree.column(c, width=180)
        self.vacancies_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Add", command=self._add_vacancy).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Update", command=self._update_vacancy).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_vacancies).pack(side=tk.RIGHT, padx=2)

        self._refresh_vacancies()

    def _refresh_vacancies(self):
        for row in self.vacancies_tree.get_children():
            self.vacancies_tree.delete(row)
        if not self.service:
            return
        try:
            vacancies = self.service.get_vacancies()
            for v in vacancies:
                self.vacancies_tree.insert("", tk.END, values=(
                    v.get("course", ""), v.get("department", ""),
                    v.get("places", 0), v.get("min_tariff", 0),
                ))
        except Exception as e:
            logger.error(f"Error loading vacancies: {e}")

    def _add_vacancy(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Vacancy")
        dlg.geometry("450x350")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Course:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        course_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=course_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Department:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        dept_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=dept_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Available Places:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        places_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=places_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Minimum UCAS Tariff:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        tariff_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=tariff_var).pack(fill=tk.X, padx=10)

        def save():
            if not course_var.get() or not dept_var.get():
                messagebox.showwarning("Validation", "Course and department are required.", parent=dlg)
                return
            try:
                places = int(places_var.get())
                tariff = int(tariff_var.get())
            except ValueError:
                messagebox.showwarning("Validation", "Places and tariff must be numbers.", parent=dlg)
                return
            try:
                self.service.add_vacancy(
                    course_code=course_var.get(),
                    course_name=course_var.get(),
                    department=dept_var.get(),
                    available_places=places,
                    minimum_tariff=tariff,
                )
                dlg.destroy()
                self._refresh_vacancies()
                messagebox.showinfo("Success", "Vacancy added.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    def _update_vacancy(self):
        sel = self.vacancies_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a vacancy first.", parent=self.root)
            return
        values = self.vacancies_tree.item(sel[0], "values")

        dlg = tk.Toplevel(self.root)
        dlg.title("Update Vacancy")
        dlg.geometry("400x250")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Course: {values[0]}", font=("", 10, "bold")).pack(padx=10, pady=10)

        ttk.Label(dlg, text="Available Places:").pack(padx=10, anchor=tk.W)
        places_var = tk.StringVar(value=str(values[2]))
        ttk.Entry(dlg, textvariable=places_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Minimum Tariff:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        tariff_var = tk.StringVar(value=str(values[3]))
        ttk.Entry(dlg, textvariable=tariff_var).pack(fill=tk.X, padx=10)

        def save():
            try:
                self.service.update_vacancy(values[0], {
                    "places": int(places_var.get()),
                    "min_tariff": int(tariff_var.get()),
                })
                dlg.destroy()
                self._refresh_vacancies()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Update", command=save).pack(pady=15)

    # ----------------------------------------------------------- Applications
    def _create_applications_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Applications")

        cols = ("name", "ucas_id", "tariff", "course", "status")
        self.apps_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.apps_tree.heading(c, text=c.replace("_", " ").title())
            self.apps_tree.column(c, width=150)
        self.apps_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="View", command=self._view_application).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Shortlist", command=lambda: self._update_app_status("Shortlisted")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Offer", command=lambda: self._update_app_status("Offered")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Reject", command=lambda: self._update_app_status("Rejected")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Auto-Shortlist", command=self._auto_shortlist).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_applications).pack(side=tk.RIGHT, padx=2)

        self._refresh_applications()

    def _refresh_applications(self):
        for row in self.apps_tree.get_children():
            self.apps_tree.delete(row)
        if not self.service:
            return
        try:
            apps = self.service.get_applications()
            for a in apps:
                self.apps_tree.insert("", tk.END, values=(
                    a.get("name", ""), a.get("ucas_id", ""),
                    a.get("tariff", 0), a.get("course", ""),
                    a.get("status", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading applications: {e}")

    def _view_application(self):
        sel = self.apps_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an application first.", parent=self.root)
            return
        values = self.apps_tree.item(sel[0], "values")
        try:
            details = self.service.get_application_details(values[1])
            dlg = tk.Toplevel(self.root)
            dlg.title(f"Application - {values[0]}")
            dlg.geometry("500x400")
            dlg.transient(self.root)

            info = [
                ("Name", details.get("name", values[0])),
                ("UCAS ID", details.get("ucas_id", values[1])),
                ("Tariff Points", details.get("tariff", values[2])),
                ("Course Applied", details.get("course", values[3])),
                ("Status", details.get("status", values[4])),
                ("Email", details.get("email", "")),
                ("Phone", details.get("phone", "")),
                ("Qualifications", details.get("qualifications", "")),
            ]
            for label, val in info:
                frame = ttk.Frame(dlg)
                frame.pack(fill=tk.X, padx=10, pady=2)
                ttk.Label(frame, text=f"{label}:", font=("", 9, "bold"), width=18).pack(side=tk.LEFT)
                ttk.Label(frame, text=str(val)).pack(side=tk.LEFT)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    def _update_app_status(self, new_status):
        sel = self.apps_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an application first.", parent=self.root)
            return
        values = self.apps_tree.item(sel[0], "values")
        if not messagebox.askyesno("Confirm", f"Set status to '{new_status}' for {values[0]}?",
                                    parent=self.root):
            return
        try:
            self.service.update_application_status(values[1], new_status)
            self._refresh_applications()
            messagebox.showinfo("Success", f"Status updated to {new_status}.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    def _auto_shortlist(self):
        if not messagebox.askyesno("Confirm",
                                    "Auto-shortlist all applicants meeting minimum tariff?",
                                    parent=self.root):
            return
        try:
            count = self.service.auto_shortlist()
            self._refresh_applications()
            messagebox.showinfo("Success", f"{count} applicants shortlisted.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # ------------------------------------------------------------- Adjustment
    def _create_adjustment_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Adjustment")

        cols = ("student", "original_course", "requested_course", "status")
        self.adj_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.adj_tree.heading(c, text=c.replace("_", " ").title())
            self.adj_tree.column(c, width=180)
        self.adj_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Submit", command=self._submit_adjustment).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Approve", command=lambda: self._update_adj_status("Approved")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Reject", command=lambda: self._update_adj_status("Rejected")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_adjustments).pack(side=tk.RIGHT, padx=2)

        self._refresh_adjustments()

    def _refresh_adjustments(self):
        for row in self.adj_tree.get_children():
            self.adj_tree.delete(row)
        if not self.service:
            return
        try:
            adjs = self.service.get_adjustments()
            for a in adjs:
                self.adj_tree.insert("", tk.END, values=(
                    a.get("student", ""), a.get("original_course", ""),
                    a.get("requested_course", ""), a.get("status", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading adjustments: {e}")

    def _submit_adjustment(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Submit Adjustment Request")
        dlg.geometry("450x300")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Student Name:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        student_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=student_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Original Course:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        orig_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=orig_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Requested Course:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        req_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=req_var).pack(fill=tk.X, padx=10)

        def save():
            if not student_var.get() or not orig_var.get() or not req_var.get():
                messagebox.showwarning("Validation", "All fields are required.", parent=dlg)
                return
            try:
                self.service.submit_adjustment({
                    "student": student_var.get(),
                    "original_course": orig_var.get(),
                    "requested_course": req_var.get(),
                    "status": "Pending",
                })
                dlg.destroy()
                self._refresh_adjustments()
                messagebox.showinfo("Success", "Adjustment request submitted.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Submit", command=save).pack(pady=15)

    def _update_adj_status(self, new_status):
        sel = self.adj_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an adjustment request first.", parent=self.root)
            return
        values = self.adj_tree.item(sel[0], "values")
        try:
            self.service.update_adjustment_status(values[0], values[2], new_status)
            self._refresh_adjustments()
            messagebox.showinfo("Success", f"Status updated to {new_status}.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # ------------------------------------------------------------- Statistics
    def _create_statistics_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Statistics")

        stats_frame = ttk.LabelFrame(tab, text="Clearing & Adjustment Statistics")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.stats_labels = {}
        stat_names = [
            "Total Applications", "Total Offers Made",
            "Places Remaining", "Shortlisted",
            "Adjustment Requests", "Adjustments Approved",
        ]
        for i, name in enumerate(stat_names):
            row = i // 2
            col = (i % 2) * 2
            ttk.Label(stats_frame, text=f"{name}:", font=("", 11, "bold")).grid(
                row=row, column=col, padx=20, pady=12, sticky=tk.W)
            lbl = ttk.Label(stats_frame, text="0", font=("", 11))
            lbl.grid(row=row, column=col + 1, padx=15, pady=12, sticky=tk.W)
            self.stats_labels[name] = lbl

        ttk.Button(stats_frame, text="Refresh Statistics", command=self._refresh_statistics).grid(
            row=len(stat_names) // 2 + 1, column=0, columnspan=4, pady=15)

        self._refresh_statistics()

    def _refresh_statistics(self):
        if not self.service:
            return
        try:
            stats = self.service.get_statistics()
            for key, lbl in self.stats_labels.items():
                lbl.config(text=str(stats.get(key.lower().replace(" ", "_"), 0)))
        except Exception as e:
            logger.error(f"Error loading statistics: {e}")
