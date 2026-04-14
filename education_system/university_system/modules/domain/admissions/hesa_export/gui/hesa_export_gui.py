import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class HESAExportGUI:
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("HESA Export Management")
        self.root.geometry("1200x800")
        try:
            from education_system.university_system.modules.domain.admissions.hesa_export.services.hesa_export_service import HESAExportService
            self.service = HESAExportService()
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
        self._create_returns_tab(notebook)
        self._create_field_mappings_tab(notebook)
        self._create_submission_log_tab(notebook)
        self._create_statistics_tab(notebook)

    # ------------------------------------------------------------------ Returns
    def _create_returns_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Returns")

        cols = ("year", "type", "status", "date")
        self.returns_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.returns_tree.heading(c, text=c.replace("_", " ").title())
            self.returns_tree.column(c, width=150)
        self.returns_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Create", command=self._create_return).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Generate XML", command=self._generate_xml).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Submit", command=self._submit_return).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_returns).pack(side=tk.RIGHT, padx=2)

        self._refresh_returns()

    def _refresh_returns(self):
        for row in self.returns_tree.get_children():
            self.returns_tree.delete(row)
        if not self.service:
            return
        try:
            returns = self.service.list_returns()
            for r in returns:
                self.returns_tree.insert("", tk.END, values=(
                    r.get("year", ""), r.get("type", ""),
                    r.get("status", ""), r.get("date", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading returns: {e}")

    def _create_return(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Create HESA Return")
        dlg.geometry("400x300")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Academic Year:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(dlg, textvariable=year_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Return Type:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        type_var = tk.StringVar()
        ttk.Combobox(dlg, textvariable=type_var, values=[
            "Student", "Staff", "Destinations", "Finance", "Estates",
        ], state="readonly").pack(fill=tk.X, padx=10)

        def save():
            if not year_var.get() or not type_var.get():
                messagebox.showwarning("Validation", "All fields are required.", parent=dlg)
                return
            try:
                self.service.create_return(
                    academic_year=year_var.get(),
                    return_type=type_var.get(),
                )
                dlg.destroy()
                self._refresh_returns()
                messagebox.showinfo("Success", "HESA return created.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    def _get_selected_return_id(self):
        """Get the return ID for the selected treeview row."""
        sel = self.returns_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a return first.", parent=self.root)
            return None
        values = self.returns_tree.item(sel[0], "values")
        # Look up the return ID by year and type
        try:
            returns = self.service.list_returns()
            for r in returns:
                if r.get("academic_year") == values[0] and r.get("return_type") == values[1]:
                    return r["id"]
        except Exception:
            pass
        return None

    def _generate_xml(self):
        return_id = self._get_selected_return_id()
        if return_id is None:
            return
        try:
            self.service.generate_xml_export(return_id)
            messagebox.showinfo("Success", "XML generated successfully.", parent=self.root)
            self._refresh_returns()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    def _submit_return(self):
        return_id = self._get_selected_return_id()
        if return_id is None:
            return
        sel = self.returns_tree.selection()
        values = self.returns_tree.item(sel[0], "values")
        if not messagebox.askyesno("Confirm", f"Submit {values[1]} return for {values[0]}?", parent=self.root):
            return
        try:
            username = self.auth.current_user.get("username") if self.auth and hasattr(self.auth, "current_user") and self.auth.current_user else None
            self.service.update_return_status(return_id, "submitted", performed_by=username)
            messagebox.showinfo("Success", "Return submitted.", parent=self.root)
            self._refresh_returns()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # ---------------------------------------------------------- Field Mappings
    def _create_field_mappings_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Field Mappings")

        cols = ("type", "hesa_field", "local_field")
        self.mappings_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.mappings_tree.heading(c, text=c.replace("_", " ").title())
            self.mappings_tree.column(c, width=200)
        self.mappings_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Add", command=self._add_mapping).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_mappings).pack(side=tk.RIGHT, padx=2)

        self._refresh_mappings()

    def _refresh_mappings(self):
        for row in self.mappings_tree.get_children():
            self.mappings_tree.delete(row)
        if not self.service:
            return
        try:
            mappings = self.service.get_field_mappings()
            for m in mappings:
                self.mappings_tree.insert("", tk.END, values=(
                    m.get("type", ""), m.get("hesa_field", ""),
                    m.get("local_field", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading mappings: {e}")

    def _add_mapping(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Field Mapping")
        dlg.geometry("400x300")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Return Type:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        type_var = tk.StringVar()
        ttk.Combobox(dlg, textvariable=type_var, values=[
            "Student", "Staff", "Destinations", "Finance", "Estates",
        ], state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="HESA Field:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        hesa_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=hesa_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Local Field:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        local_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=local_var).pack(fill=tk.X, padx=10)

        def save():
            if not type_var.get() or not hesa_var.get() or not local_var.get():
                messagebox.showwarning("Validation", "All fields are required.", parent=dlg)
                return
            try:
                self.service.add_field_mapping(
                    return_type=type_var.get(),
                    hesa_field=hesa_var.get(),
                    local_field=local_var.get(),
                )
                dlg.destroy()
                self._refresh_mappings()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    # ---------------------------------------------------------- Submission Log
    def _create_submission_log_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Submission Log")

        cols = ("action", "details", "by", "date")
        self.log_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.log_tree.heading(c, text=c.replace("_", " ").title())
            self.log_tree.column(c, width=200)
        self.log_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_log).pack(side=tk.RIGHT, padx=2)

        self._refresh_log()

    def _refresh_log(self):
        for row in self.log_tree.get_children():
            self.log_tree.delete(row)
        if not self.service:
            return
        try:
            # Show all submission log entries across all returns
            logs = []
            for r in (self.service.list_returns() or []):
                logs.extend(self.service.get_submission_log(r["id"]))
            for entry in logs:
                self.log_tree.insert("", tk.END, values=(
                    entry.get("action", ""), entry.get("details", ""),
                    entry.get("by", ""), entry.get("date", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading submission log: {e}")

    # ------------------------------------------------------------- Statistics
    def _create_statistics_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Statistics")

        stats_frame = ttk.LabelFrame(tab, text="HESA Export Statistics")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.stats_labels = {}
        stat_names = [
            "Total Returns", "Draft Returns", "Generated Returns",
            "Submitted Returns", "Total Mappings", "Last Submission",
        ]
        for i, name in enumerate(stat_names):
            row = i // 2
            col = (i % 2) * 2
            ttk.Label(stats_frame, text=f"{name}:", font=("", 10, "bold")).grid(
                row=row, column=col, padx=15, pady=8, sticky=tk.W)
            lbl = ttk.Label(stats_frame, text="0")
            lbl.grid(row=row, column=col + 1, padx=10, pady=8, sticky=tk.W)
            self.stats_labels[name] = lbl

        ttk.Button(stats_frame, text="Refresh Statistics", command=self._refresh_statistics).grid(
            row=len(stat_names) // 2 + 1, column=0, columnspan=4, pady=15)

        self._refresh_statistics()

    def _refresh_statistics(self):
        if not self.service:
            return
        try:
            stats = self.service.get_return_statistics()
            for key, lbl in self.stats_labels.items():
                lbl.config(text=str(stats.get(key.lower().replace(" ", "_"), 0)))
        except Exception as e:
            logger.error(f"Error loading statistics: {e}")
