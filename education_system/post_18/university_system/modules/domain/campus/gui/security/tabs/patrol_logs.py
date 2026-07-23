"""Patrol logs management tab mixin."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.post_18.university_system.core.i18n import get_text as _t

from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.patrol_log import PatrolLogDialog


class PatrolLogsMixin:
    """Patrol logs management view methods."""

    def show_patrol_logs(self):
        """Display patrol logs view"""
        self.clear_content()
        self.create_section_header("Patrol Logs", self.add_patrol_log)

        columns = ("Date", "Officer", "Area", "Start", "End", "Status")
        self.patrol_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.patrol_tree.heading(col, text=col)
            self.patrol_tree.column(col, width=130)

        self.patrol_tree.pack(fill="both", expand=True)
        self.refresh_patrol_logs()

        btn_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", pady=10)

        tk.Button(btn_frame, text=_t("police_station.patrol.view_notes"), bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.view_patrol_notes).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.cases.delete"), bg=self.colors["accent"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.delete_patrol_log).pack(side="left", padx=5)

    def refresh_patrol_logs(self):
        """Refresh patrol logs treeview"""
        for item in self.patrol_tree.get_children():
            self.patrol_tree.delete(item)

        for log in sorted(self.data.get("patrol_logs", []),
                         key=lambda x: x.get('date', ''), reverse=True):
            self.patrol_tree.insert("", "end", values=(
                log.get("date", ""),
                log.get("officer", ""),
                log.get("area", ""),
                log.get("start_time", ""),
                log.get("end_time", ""),
                log.get("status", "")
            ))

    def add_patrol_log(self):
        """Add new patrol log"""
        officers = self.get_officers_list()
        dialog = PatrolLogDialog(self.root, self.colors, self.current_user, officers)

        if dialog.result:
            if self._db_save_patrol_log(dialog.result):
                if 'patrol_logs' not in self.data:
                    self.data['patrol_logs'] = []
                self.data['patrol_logs'].append(dialog.result)
                if hasattr(self, 'patrol_tree'):
                    self.refresh_patrol_logs()
                messagebox.showinfo(_t("police_station.msg_titles.success"), "Patrol log entry added!")

    def view_patrol_notes(self):
        """View patrol log notes"""
        selected = self.patrol_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), "Please select a patrol log to view.")
            return

        item = self.patrol_tree.item(selected[0])
        date = item["values"][0]
        officer = item["values"][1]

        for log in self.data.get("patrol_logs", []):
            if log.get("date") == date and log.get("officer") == officer:
                notes = log.get("notes", "No notes recorded.")
                messagebox.showinfo(_t("police_station.msg_titles.patrol_notes"), f"Officer: {officer}\nDate: {date}\n\n{notes}")
                break

    def delete_patrol_log(self):
        """Delete patrol log"""
        selected = self.patrol_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), "Please select a patrol log to delete.")
            return

        if messagebox.askyesno(_t("police_station.buttons.confirm"), "Delete this patrol log entry?"):
            item = self.patrol_tree.item(selected[0])
            date = item["values"][0]
            officer = item["values"][1]

            if self._db_delete_patrol_log(date, officer):
                self.data["patrol_logs"] = [l for l in self.data.get("patrol_logs", [])
                                            if not (l.get("date") == date and l.get("officer") == officer)]
                self.refresh_patrol_logs()
