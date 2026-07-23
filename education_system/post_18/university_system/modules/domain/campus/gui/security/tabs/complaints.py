"""Complaints management tab mixin."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

from education_system.post_18.university_system.core.i18n import get_text as _t

from education_system.post_18.university_system.modules.domain.campus.gui.security.dialogs.complaint_form import ComplaintFormDialog
from education_system.post_18.university_system.modules.domain.campus.gui.security.utils import send_notification_email


class ComplaintsMixin:
    """Complaints management view methods."""

    def show_complaints(self):
        """Display complaints management view"""
        self.clear_content()
        self.create_section_header("Safety Concerns & Complaints", self.add_complaint)

        columns = ("ID", "Complainant", "Type", "Status", "Priority", "Date")
        self.complaints_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.complaints_tree.heading(col, text=col)
            self.complaints_tree.column(col, width=130)

        self.complaints_tree.pack(fill="both", expand=True)
        self.refresh_complaints()

        btn_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", pady=10)

        tk.Button(btn_frame, text=_t("police_station.complaints.view_details"), bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.view_complaint).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.complaints.update_status"), bg=self.colors["warning"], fg="black",
                 bd=0, padx=20, pady=8, command=self.update_complaint_status).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.complaints.convert_to_case"), bg=self.colors["success"], fg="white",
                 bd=0, padx=20, pady=8, command=self.convert_to_case).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_t("police_station.cases.delete"), bg=self.colors["accent"], fg=self.colors["text"],
                 bd=0, padx=20, pady=8, command=self.delete_complaint).pack(side="left", padx=5)

    def refresh_complaints(self):
        """Refresh the complaints treeview"""
        for item in self.complaints_tree.get_children():
            self.complaints_tree.delete(item)

        for complaint in self.data["complaints"]:
            self.complaints_tree.insert("", "end", values=(
                complaint.get("id", ""),
                complaint.get("complainant", ""),
                complaint.get("type", ""),
                complaint.get("status", ""),
                complaint.get("priority", ""),
                complaint.get("date", "")
            ))

    def add_complaint(self):
        """Add a new complaint"""
        dialog = ComplaintFormDialog(self.root, self.colors, self.current_user)

        if dialog.result:
            complaint_id = self._db_get_next_id("CMP", "police_complaints")
            complaint = dialog.result.copy()
            complaint['id'] = complaint_id

            if self._db_save_complaint(complaint):
                self.data["complaints"].append(complaint)
                if hasattr(self, 'complaints_tree'):
                    self.refresh_complaints()

            # Send confirmation email
            if complaint.get('email'):
                # Use email template
                try:
                    from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
                    subject, body = render_template("police_complaint_received", {
                        "complainant_name": complaint.get('complainant', 'Citizen'),
                        "complaint_id": complaint_id,
                        "complaint_type": complaint.get('type', 'N/A'),
                        "priority": complaint.get('priority', 'Medium')
                    })
                except Exception:
                    # Fallback to hardcoded email
                    subject = f"Complaint Received - {complaint_id}"
                    body = f"""Dear {complaint.get('complainant', 'Citizen')},

Your complaint has been received and logged.

Complaint ID: {complaint_id}
Type: {complaint.get('type', 'N/A')}
Priority: {complaint.get('priority', 'Medium')}
Status: Pending

We will investigate your complaint and contact you with updates.

Campus Public Safety
"""
                send_notification_email(complaint['email'], subject, body)

            messagebox.showinfo(_t("police_station.buttons.success"), _t("police_station.messages.complaint_filed", id=complaint_id))

    def view_complaint(self):
        """View complaint details"""
        selected = self.complaints_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.select_complaint"))
            return

        item = self.complaints_tree.item(selected[0])
        complaint_id = item["values"][0]

        for complaint in self.data["complaints"]:
            if complaint["id"] == complaint_id:
                details = f"""
Complaint ID: {complaint.get('id', 'N/A')}
Complainant: {complaint.get('complainant', 'N/A')}
Email: {complaint.get('email', 'N/A')}
Phone: {complaint.get('phone', 'N/A')}

Type: {complaint.get('type', 'N/A')}
Priority: {complaint.get('priority', 'N/A')}
Status: {complaint.get('status', 'N/A')}
Date Filed: {complaint.get('date', 'N/A')}

Location: {complaint.get('location', 'N/A')}
Incident Date: {complaint.get('incident_date', 'N/A')} {complaint.get('incident_time', '')}

Description:
{complaint.get('description', 'No description available.')}

Suspect Info: {complaint.get('suspect_description', 'N/A')}
                """
                messagebox.showinfo(_t("police_station.complaints.view_details"), details)
                break

    def update_complaint_status(self):
        """Update complaint status"""
        selected = self.complaints_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.select_complaint_update"))
            return

        item = self.complaints_tree.item(selected[0])
        complaint_id = item["values"][0]

        status = simpledialog.askstring("Update Status",
                                        "Enter new status:\n(Pending/Under Investigation/Resolved/Dismissed)")
        if status:
            for complaint in self.data["complaints"]:
                if complaint["id"] == complaint_id:
                    old_status = complaint.get("status", "Pending")
                    complaint["status"] = status
                    if self._db_save_complaint(complaint):
                        self.refresh_complaints()

                        # Send email notification
                        if complaint.get('email'):
                            # Use email template
                            try:
                                from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
                                subject, body = render_template("police_complaint_status_update", {
                                    "complainant_name": complaint.get('complainant', 'Citizen'),
                                    "complaint_id": complaint_id,
                                    "old_status": old_status,
                                    "new_status": status
                                })
                            except Exception:
                                # Fallback to hardcoded email
                                subject = f"Complaint Status Update - {complaint_id}"
                                body = f"""Dear {complaint.get('complainant', 'Citizen')},

Your complaint status has been updated.

Complaint ID: {complaint_id}
Previous Status: {old_status}
New Status: {status}

If you have any questions, please contact the Campus Public Safety.

Best regards,
Campus Public Safety
"""
                            send_notification_email(complaint['email'], subject, body)

                        messagebox.showinfo(_t("police_station.msg_titles.success"), "Status updated successfully!")
                    break

    def convert_to_case(self):
        """Convert complaint to case"""
        selected = self.complaints_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), "Please select a complaint to convert.")
            return

        item = self.complaints_tree.item(selected[0])
        complaint_id = item["values"][0]

        for complaint in self.data["complaints"]:
            if complaint["id"] == complaint_id:
                if messagebox.askyesno(_t("police_station.buttons.confirm"), "Convert this complaint to a case?"):
                    case_id = self._db_get_next_id("CS", "police_cases")
                    case = {
                        "id": case_id,
                        "title": f"Case from {complaint_id}: {complaint.get('type', 'Unknown')}",
                        "type": complaint.get("type", "Other"),
                        "status": "Open",
                        "priority": complaint.get("priority", "Medium"),
                        "officer": "",
                        "description": complaint.get("description", ""),
                        "location": complaint.get("location", ""),
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "source_complaint": complaint_id
                    }
                    if self._db_save_case(case):
                        self.data["cases"].append(case)
                        complaint["status"] = "Converted to Case"
                        self._db_save_complaint(complaint)
                        self.refresh_complaints()
                        messagebox.showinfo(_t("police_station.msg_titles.success"), f"Complaint converted to Case {case_id}")
                break

    def delete_complaint(self):
        """Delete selected complaint"""
        selected = self.complaints_tree.selection()
        if not selected:
            messagebox.showwarning(_t("police_station.msg_titles.warning"), "Please select a complaint to delete.")
            return

        if messagebox.askyesno(_t("police_station.buttons.confirm"), "Are you sure you want to delete this complaint?"):
            item = self.complaints_tree.item(selected[0])
            complaint_id = item["values"][0]
            if self._db_delete_complaint(complaint_id):
                self.data["complaints"] = [c for c in self.data["complaints"] if c["id"] != complaint_id]
                self.refresh_complaints()
                messagebox.showinfo(_t("police_station.msg_titles.success"), "Complaint deleted successfully!")
