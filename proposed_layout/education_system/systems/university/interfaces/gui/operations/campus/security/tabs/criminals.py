"""Criminal records management tab mixin."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.interfaces.gui.operations.campus.security.dialogs.criminal import CriminalDialog


class CriminalsMixin:
    """Criminal records management view methods."""

    def show_criminals(self):
        """Display criminal records view"""
        self.clear_content()
        self.create_section_header("Persons of Interest", self.add_criminal)

        columns = ("ID", "Name", "Crime", "Status", "Arrest Date", "Case #")
        self.criminals_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.criminals_tree.heading(col, text=col)
            self.criminals_tree.column(col, width=120)

        self.criminals_tree.pack(fill="both", expand=True)
        self.refresh_criminals()

        btn_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", pady=10)

        tk.Button(btn_frame, text=_t("police_station.complaints.view_details"), bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.view_criminal).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.cases.delete"), bg=self.colors["accent"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.delete_criminal).pack(side="left", padx=5)

    def refresh_criminals(self):
        """Refresh the criminals treeview"""
        for item in self.criminals_tree.get_children():
            self.criminals_tree.delete(item)

        for criminal in self.data["criminals"]:
            self.criminals_tree.insert("", "end", values=(
                criminal.get("id", ""),
                criminal.get("name", ""),
                criminal.get("crime", ""),
                criminal.get("status", ""),
                criminal.get("arrest_date", ""),
                criminal.get("case_number", "")
            ))

    def add_criminal(self):
        """Add a new criminal record"""
        dialog = CriminalDialog(self.root, "Add Criminal Record", self.colors)
        if dialog.result:
            criminal_id = self._db_get_next_id("CR", "police_criminals")
            criminal = dialog.result.copy()
            criminal['id'] = criminal_id
            if self._db_save_criminal(criminal):
                self.data["criminals"].append(criminal)
                self.refresh_criminals()
                messagebox.showinfo(_t("police_station.msg_titles.success"), f"Criminal record {criminal_id} added!")

    def view_criminal(self):
        """View criminal details"""
        selected = self.criminals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), "Please select a record to view.")
            return

        item = self.criminals_tree.item(selected[0])
        criminal_id = item["values"][0]

        for criminal in self.data["criminals"]:
            if criminal["id"] == criminal_id:
                details = f"""
Criminal ID: {criminal.get('id', 'N/A')}
Name: {criminal.get('name', 'N/A')}
Crime: {criminal.get('crime', 'N/A')}
Status: {criminal.get('status', 'N/A')}
Arrest Date: {criminal.get('arrest_date', 'N/A')}
Related Case: {criminal.get('case_number', 'N/A')}

Description:
{criminal.get('description', 'No description available.')}
                """
                messagebox.showinfo(_t("police_station.msg_titles.criminal_record"), details)
                break

    def delete_criminal(self):
        """Delete selected criminal record"""
        selected = self.criminals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), "Please select a record to delete.")
            return

        if messagebox.askyesno(_t("police_station.buttons.confirm"), "Are you sure you want to delete this record?"):
            item = self.criminals_tree.item(selected[0])
            criminal_id = item["values"][0]
            if self._db_delete_criminal(criminal_id):
                self.data["criminals"] = [c for c in self.data["criminals"] if c["id"] != criminal_id]
                self.refresh_criminals()
                messagebox.showinfo(_t("police_station.msg_titles.success"), "Record deleted successfully!")
