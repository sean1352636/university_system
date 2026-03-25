"""Officers management tab mixin."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from education_system.university_system.modules.domain.campus.gui.security.dialogs.officer import OfficerDialog


class OfficersMixin:
    """Officers management view methods."""

    def show_officers(self):
        """Display officers management view"""
        self.clear_content()
        self.create_section_header("Officer Management", self.add_officer)

        columns = ("Badge #", "Name", "Rank", "Department", "Status", "Phone", "Cases")
        self.officers_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.officers_tree.heading(col, text=col)
            self.officers_tree.column(col, width=110)

        self.officers_tree.pack(fill="both", expand=True)
        self.refresh_officers()

        btn_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", pady=10)

        tk.Button(btn_frame, text=_t("police_station.officers.edit"), bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.edit_officer).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.cases.delete"), bg=self.colors["accent"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.delete_officer).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.officers.view_workload"), bg=self.colors["bg_medium"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.view_officer_workload).pack(side="left", padx=5)

    def refresh_officers(self):
        """Refresh the officers treeview"""
        for item in self.officers_tree.get_children():
            self.officers_tree.delete(item)

        for officer in self.data["officers"]:
            # Count assigned cases
            case_count = len([c for c in self.data["cases"]
                            if c.get("officer") == officer.get("name") and c.get("status") != "Closed"])

            self.officers_tree.insert("", "end", values=(
                officer.get("badge", ""),
                officer.get("name", ""),
                officer.get("rank", ""),
                officer.get("department", ""),
                officer.get("status", ""),
                officer.get("phone", ""),
                case_count
            ))

    def add_officer(self):
        """Add a new officer"""
        dialog = OfficerDialog(self.root, _t("police_station.officers.add_new"), self.colors)
        if dialog.result:
            badge = self._db_get_next_id("OFF", "police_officers")
            officer = dialog.result.copy()
            officer['badge'] = badge
            if self._db_save_officer(officer):
                self.data["officers"].append(officer)
                self.refresh_officers()
                messagebox.showinfo(_t("police_station.msg_titles.success"), _t("police_station.messages.officer_added", id=badge))

    def edit_officer(self):
        """Edit selected officer"""
        selected = self.officers_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), _t("police_station.warnings.select_officer"))
            return

        item = self.officers_tree.item(selected[0])
        badge = item["values"][0]

        for officer in self.data["officers"]:
            if officer["badge"] == badge:
                dialog = OfficerDialog(self.root, _t("police_station.officers.edit_officer"), self.colors, officer)
                if dialog.result:
                    officer.update(dialog.result)
                    if self._db_save_officer(officer):
                        self.refresh_officers()
                        messagebox.showinfo(_t("police_station.msg_titles.success"), _t("police_station.messages.officer_updated"))
                break

    def delete_officer(self):
        """Delete selected officer"""
        selected = self.officers_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), _t("police_station.warnings.select_officer"))
            return

        if messagebox.askyesno(_t("police_station.buttons.confirm"), _t("police_station.confirm.delete_officer")):
            item = self.officers_tree.item(selected[0])
            badge = item["values"][0]
            if self._db_delete_officer(badge):
                self.data["officers"] = [o for o in self.data["officers"] if o["badge"] != badge]
                self.refresh_officers()
                messagebox.showinfo(_t("police_station.msg_titles.success"), _t("police_station.messages.officer_deleted"))

    def view_officer_workload(self):
        """View officer case workload"""
        workload = {}
        for officer in self.data["officers"]:
            name = officer.get("name", "Unknown")
            cases = [c for c in self.data["cases"] if c.get("officer") == name]
            workload[name] = {
                "total": len(cases),
                "open": len([c for c in cases if c.get("status") in ["Open", "In Progress"]]),
                "closed": len([c for c in cases if c.get("status") == "Closed"])
            }

        report = "Officer Workload Report\n" + "=" * 40 + "\n\n"
        for name, stats in workload.items():
            report += f"{name}:\n"
            report += f"  Total Cases: {stats['total']}\n"
            report += f"  Open/Active: {stats['open']}\n"
            report += f"  Closed: {stats['closed']}\n\n"

        messagebox.showinfo(_t("police_station.officers.workload_report"), report)
