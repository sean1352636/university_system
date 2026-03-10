"""Evidence management tab mixin."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from ..dialogs.evidence import EvidenceDialog


class EvidenceMixin:
    """Evidence management view methods."""

    def show_evidence(self):
        """Display evidence management view"""
        self.clear_content()
        self.create_section_header("Evidence Locker", self.add_evidence)

        columns = ("ID", "Description", "Case #", "Type", "Location", "Date Added")
        self.evidence_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.evidence_tree.heading(col, text=col)
            self.evidence_tree.column(col, width=120)

        self.evidence_tree.pack(fill="both", expand=True)
        self.refresh_evidence()

        btn_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", pady=10)

        tk.Button(btn_frame, text=_t("police_station.officers.edit"), bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.edit_evidence).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.cases.delete"), bg=self.colors["accent"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.delete_evidence).pack(side="left", padx=5)

    def refresh_evidence(self):
        """Refresh the evidence treeview"""
        for item in self.evidence_tree.get_children():
            self.evidence_tree.delete(item)

        for evidence in self.data["evidence"]:
            self.evidence_tree.insert("", "end", values=(
                evidence.get("id", ""),
                evidence.get("description", "")[:40],
                evidence.get("case_number", ""),
                evidence.get("type", ""),
                evidence.get("location", ""),
                evidence.get("date_added", "")
            ))

    def add_evidence(self):
        """Add new evidence"""
        dialog = EvidenceDialog(self.root, "Add Evidence", self.colors)
        if dialog.result:
            evidence_id = self._db_get_next_id("EV", "police_evidence")
            evidence = dialog.result.copy()
            evidence['id'] = evidence_id
            evidence['date_added'] = datetime.now().strftime("%Y-%m-%d")
            if self._db_save_evidence(evidence):
                self.data["evidence"].append(evidence)
                if hasattr(self, 'evidence_tree'):
                    self.refresh_evidence()
                messagebox.showinfo(_t("police_station.msg_titles.success"), f"Evidence {evidence_id} added!")

    def edit_evidence(self):
        """Edit selected evidence"""
        selected = self.evidence_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), "Please select evidence to edit.")
            return

        item = self.evidence_tree.item(selected[0])
        evidence_id = item["values"][0]

        for evidence in self.data["evidence"]:
            if evidence["id"] == evidence_id:
                dialog = EvidenceDialog(self.root, "Edit Evidence", self.colors, evidence)
                if dialog.result:
                    evidence.update(dialog.result)
                    if self._db_save_evidence(evidence):
                        self.refresh_evidence()
                        messagebox.showinfo(_t("police_station.msg_titles.success"), "Evidence updated!")
                break

    def delete_evidence(self):
        """Delete selected evidence"""
        selected = self.evidence_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), "Please select evidence to delete.")
            return

        if messagebox.askyesno(_t("police_station.buttons.confirm"), "Are you sure you want to delete this evidence?"):
            item = self.evidence_tree.item(selected[0])
            evidence_id = item["values"][0]
            if self._db_delete_evidence(evidence_id):
                self.data["evidence"] = [e for e in self.data["evidence"] if e["id"] != evidence_id]
                self.refresh_evidence()
                messagebox.showinfo(_t("police_station.msg_titles.success"), "Evidence deleted!")
