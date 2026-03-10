"""Cases management tab mixin."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from ..dialogs.case_details import CaseDetailsDialog
from ..utils import get_officer_email, send_notification_email


class CasesMixin:
    """Cases management view methods."""

    def show_cases(self):
        """Display cases management view"""
        self.clear_content()
        self.create_section_header(_t("police_station.cases.title"), self.add_case)

        # Search and filter frame
        filter_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        filter_frame.pack(fill="x", pady=(0, 15))

        # Search
        self.case_search_var = tk.StringVar()
        self.case_search_var.trace('w', lambda *args: self.filter_cases())

        search_entry = tk.Entry(filter_frame, textvariable=self.case_search_var,
                               font=("Segoe UI", 11), bg=self.colors["bg_medium"],
                               fg=self.colors["text"], insertbackground=self.colors["text"],
                               width=30)
        search_entry.pack(side="left", ipady=8, ipadx=10)

        tk.Label(filter_frame, text=_t("police_station.cases.search"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text_secondary"]).pack(side="left", padx=10)

        # Status filter
        tk.Label(filter_frame, text=_t("police_station.cases.status"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left", padx=(20, 5))

        self.case_status_filter = ttk.Combobox(filter_frame,
                                               values=[_t("police_station.cases.all"), _t("police_station.cases.open"), _t("police_station.cases.in_progress"), _t("police_station.cases.under_review"), _t("police_station.cases.closed")],
                                               width=15)
        self.case_status_filter.set(_t("police_station.cases.all"))
        self.case_status_filter.bind("<<ComboboxSelected>>", lambda e: self.filter_cases())
        self.case_status_filter.pack(side="left")

        # Treeview for cases
        columns = ("ID", "Title", "Type", "Status", "Priority", "Officer", "Date")
        self.cases_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=15)

        widths = {"ID": 80, "Title": 200, "Type": 100, "Status": 100, "Priority": 80, "Officer": 120, "Date": 100}
        for col in columns:
            self.cases_tree.heading(col, text=col, command=lambda c=col: self.sort_cases(c))
            self.cases_tree.column(col, width=widths.get(col, 100))

        self.cases_tree.pack(fill="both", expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=self.cases_tree.yview)
        self.cases_tree.configure(yscrollcommand=scrollbar.set)

        # Double-click to view details
        self.cases_tree.bind("<Double-1>", lambda e: self.view_case_details())

        # Load cases
        self.refresh_cases()

        # Buttons
        btn_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", pady=10)

        tk.Button(btn_frame, text=_t("police_station.cases.view_edit"), bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, cursor="hand2", command=self.view_case_details).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.cases.delete"), bg=self.colors["accent"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, cursor="hand2", command=self.delete_case).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.cases.export_cases"), bg=self.colors["bg_medium"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, cursor="hand2", command=self.export_cases).pack(side="right", padx=5)

    def refresh_cases(self):
        """Refresh the cases treeview"""
        for item in self.cases_tree.get_children():
            self.cases_tree.delete(item)

        for case in self.data["cases"]:
            self.cases_tree.insert("", "end", values=(
                case.get("id", ""),
                case.get("title", "")[:40],
                case.get("type", ""),
                case.get("status", ""),
                case.get("priority", "Medium"),
                case.get("officer", ""),
                case.get("date", "")
            ))

    def filter_cases(self):
        """Filter cases based on search and status"""
        search_term = self.case_search_var.get().lower()
        status_filter = self.case_status_filter.get()

        for item in self.cases_tree.get_children():
            self.cases_tree.delete(item)

        for case in self.data["cases"]:
            # Check status filter
            if status_filter != "All" and case.get("status") != status_filter:
                continue

            # Check search term
            if search_term:
                searchable = f"{case.get('id', '')} {case.get('title', '')} {case.get('officer', '')}".lower()
                if search_term not in searchable:
                    continue

            self.cases_tree.insert("", "end", values=(
                case.get("id", ""),
                case.get("title", "")[:40],
                case.get("type", ""),
                case.get("status", ""),
                case.get("priority", "Medium"),
                case.get("officer", ""),
                case.get("date", "")
            ))

    def sort_cases(self, column):
        """Sort cases by column"""
        # Simple toggle sort
        items = [(self.cases_tree.set(item, column), item) for item in self.cases_tree.get_children("")]
        items.sort()
        for index, (_, item) in enumerate(items):
            self.cases_tree.move(item, "", index)

    def add_case(self):
        """Add a new case"""
        officers = self.get_officers_list()
        dialog = CaseDetailsDialog(self.root, {}, self.colors, officers)

        if dialog.result:
            case_id = self._db_get_next_id("CS", "police_cases")
            case = dialog.result.copy()
            case['id'] = case_id
            case['date'] = datetime.now().strftime("%Y-%m-%d")

            if self._db_save_case(case):
                self.data["cases"].append(case)
                if hasattr(self, 'cases_tree'):
                    self.refresh_cases()

            # Send email to assigned officer
            if case.get('officer'):
                officer_email = get_officer_email(case['officer'])
                if officer_email:
                    # Use email template
                    try:
                        from education_system.university_system.infrastructure.email.template_utils import render_template
                        subject, body = render_template("police_case_assigned", {
                            "case_id": case_id,
                            "case_title": case.get('title', 'N/A'),
                            "case_type": case.get('type', 'N/A'),
                            "priority": case.get('priority', 'Medium')
                        })
                    except Exception as template_error:
                        # Fallback to hardcoded email
                        subject = f"New Case Assigned: {case_id}"
                        body = f"""You have been assigned a new case.

Case ID: {case_id}
Title: {case.get('title', 'N/A')}
Type: {case.get('type', 'N/A')}
Priority: {case.get('priority', 'Medium')}

Please review the incident in the Campus Public Safety System.
"""
                    send_notification_email(officer_email, subject, body)

            messagebox.showinfo(_t("police_station.msg_titles.success"), _t("police_station.messages.case_created", id=case_id))

    def view_case_details(self):
        """View and edit case details"""
        selected = self.cases_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), _t("police_station.warnings.select_case"))
            return

        item = self.cases_tree.item(selected[0])
        case_id = item["values"][0]

        for i, case in enumerate(self.data["cases"]):
            if case["id"] == case_id:
                officers = self.get_officers_list()

                def on_save(result):
                    updated_case = self.data["cases"][i].copy()
                    updated_case.update(result)
                    if self._db_save_case(updated_case):
                        self.data["cases"][i].update(result)
                        self.refresh_cases()

                dialog = CaseDetailsDialog(self.root, case, self.colors, officers, on_save=on_save)
                break

    def delete_case(self):
        """Delete selected case"""
        selected = self.cases_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), _t("police_station.warnings.select_case"))
            return

        if messagebox.askyesno(_t("police_station.buttons.confirm"), _t("police_station.confirm.delete_case")):
            item = self.cases_tree.item(selected[0])
            case_id = item["values"][0]
            if self._db_delete_case(case_id):
                self.data["cases"] = [c for c in self.data["cases"] if c["id"] != case_id]
                self.refresh_cases()
                messagebox.showinfo(_t("police_station.msg_titles.success"), _t("police_station.messages.case_deleted"))

    def export_cases(self):
        """Export cases to CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"cases_export_{datetime.now().strftime('%Y%m%d')}.csv"
        )

        if filename:
            try:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "Title", "Type", "Status", "Priority", "Officer", "Date", "Description"])
                    for case in self.data["cases"]:
                        writer.writerow([
                            case.get("id", ""),
                            case.get("title", ""),
                            case.get("type", ""),
                            case.get("status", ""),
                            case.get("priority", ""),
                            case.get("officer", ""),
                            case.get("date", ""),
                            case.get("description", "")
                        ])
                messagebox.showinfo(_t("police_station.buttons.success"), _t("police_station.messages.cases_exported", filename=filename))
            except Exception as e:
                messagebox.showerror(_t("police_station.buttons.warning"), _t("police_station.messages.export_failed", error=str(e)))
