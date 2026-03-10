"""Case details and witness dialogs."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.infrastructure.email.template_utils import render_template

from ..constants import CAMPUS_INCIDENT_TYPES, CAMPUS_LOCATIONS
from ..utils import get_officer_email, send_notification_email
from ..widgets import ScrollableFrame


class CaseDetailsDialog(tk.Toplevel):
    """Detailed case view and edit dialog."""

    def __init__(self, parent, case, colors, officers_list, witnesses=None, on_save=None):
        super().__init__(parent)
        self.title(f"Case Details - {case.get('id', 'New Case')}")
        self.geometry("700x600")
        self.configure(bg=colors["bg_dark"])
        self.transient(parent)

        self.case = case.copy() if case else {}
        self.colors = colors
        self.officers_list = officers_list
        self.witnesses = witnesses or []
        self.on_save = on_save
        self.result = None

        self.setup_ui()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()

    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg=self.colors["accent"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text=f"Case: {self.case.get('id', 'New Case')}",
                font=("Segoe UI", 16, "bold"), bg=self.colors["accent"],
                fg="white").pack(side="left", padx=20, pady=15)

        status = self.case.get('status', 'Open')
        status_color = "#00d26a" if status == "Closed" else "#ffc107" if status == "In Progress" else "#e94560"
        tk.Label(header, text=f"Status: {status}", font=("Segoe UI", 12),
                bg=self.colors["accent"], fg=status_color).pack(side="right", padx=20)

        # Scrollable content
        scroll_frame = ScrollableFrame(self, bg=self.colors["bg_dark"])
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        content = scroll_frame.scrollable_frame

        # Case Info Section
        self.create_section_label(content, "Case Information")

        info_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        info_frame.pack(fill="x", pady=5)

        # Title
        self.title_entry = self.create_field(info_frame, "Title:", self.case.get('title', ''))

        # Type
        type_frame = tk.Frame(info_frame, bg=self.colors["bg_medium"])
        type_frame.pack(fill="x", pady=5)
        tk.Label(type_frame, text=_t("police_station.case_details.type"), font=("Segoe UI", 10),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.type_combo = ttk.Combobox(type_frame, values=CAMPUS_INCIDENT_TYPES)
        self.type_combo.set(self.case.get('type', 'Other'))
        self.type_combo.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Status
        status_frame = tk.Frame(info_frame, bg=self.colors["bg_medium"])
        status_frame.pack(fill="x", pady=5)
        tk.Label(status_frame, text=_t("police_station.case_details.status_label"), font=("Segoe UI", 10),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.status_combo = ttk.Combobox(status_frame, values=["Open", "In Progress", "Under Review", "Closed"])
        self.status_combo.set(self.case.get('status', 'Open'))
        self.status_combo.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Priority
        priority_frame = tk.Frame(info_frame, bg=self.colors["bg_medium"])
        priority_frame.pack(fill="x", pady=5)
        tk.Label(priority_frame, text=_t("police_station.case_details.priority"), font=("Segoe UI", 10),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.priority_combo = ttk.Combobox(priority_frame, values=["Low", "Medium", "High", "Critical"])
        self.priority_combo.set(self.case.get('priority', 'Medium'))
        self.priority_combo.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Assigned Officer
        officer_frame = tk.Frame(info_frame, bg=self.colors["bg_medium"])
        officer_frame.pack(fill="x", pady=5)
        tk.Label(officer_frame, text=_t("police_station.case_details.assigned_officer"), font=("Segoe UI", 10),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.officer_combo = ttk.Combobox(officer_frame, values=self.officers_list)
        self.officer_combo.set(self.case.get('officer', ''))
        self.officer_combo.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Location (Campus Building/Area)
        location_frame = tk.Frame(info_frame, bg=self.colors["bg_medium"])
        location_frame.pack(fill="x", pady=5)
        tk.Label(location_frame, text=_t("police_station.case_details.location"), font=("Segoe UI", 10),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.location_combo = ttk.Combobox(location_frame, values=CAMPUS_LOCATIONS)
        self.location_combo.set(self.case.get('location', ''))
        self.location_combo.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Student Involvement Section
        student_frame = tk.Frame(info_frame, bg=self.colors["bg_medium"])
        student_frame.pack(fill="x", pady=5)

        self.is_student_var = tk.BooleanVar(value=self.case.get('is_student_involved', False))
        tk.Checkbutton(student_frame, text=_t("police_station.case_details.student_involved"), variable=self.is_student_var,
                      bg=self.colors["bg_medium"], fg=self.colors["text"],
                      selectcolor=self.colors["bg_dark"], activebackground=self.colors["bg_medium"],
                      command=self.toggle_student_fields).pack(side="left")

        self.student_id_frame = tk.Frame(info_frame, bg=self.colors["bg_medium"])
        self.student_id_frame.pack(fill="x", pady=5)
        tk.Label(self.student_id_frame, text=_t("police_station.case_details.student_id"), font=("Segoe UI", 10),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.student_id_entry = tk.Entry(self.student_id_frame, font=("Segoe UI", 10),
                                         bg=self.colors["bg_dark"], fg=self.colors["text"],
                                         insertbackground=self.colors["text"])
        self.student_id_entry.pack(side="left", fill="x", expand=True, padx=(10, 5))
        self.student_id_entry.insert(0, self.case.get('student_id', ''))

        tk.Button(self.student_id_frame, text=_t("police_station.case_details.lookup"), bg=self.colors["accent"],
                 fg="white", bd=0, padx=8, pady=2, cursor="hand2",
                 command=self.lookup_student).pack(side="right")

        self.student_name_label = tk.Label(info_frame, text="", font=("Segoe UI", 10, "italic"),
                                           bg=self.colors["bg_medium"], fg=self.colors["text"])
        self.student_name_label.pack(fill="x", pady=2)
        if self.case.get('student_name'):
            self.student_name_label.config(text=f"Student: {self.case.get('student_name')}")

        # Hide student fields if not student-involved
        if not self.is_student_var.get():
            self.student_id_frame.pack_forget()
            self.student_name_label.pack_forget()

        # Description Section
        self.create_section_label(content, "Description")

        desc_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        desc_frame.pack(fill="x", pady=5)

        self.description_text = tk.Text(desc_frame, height=6, font=("Segoe UI", 10),
                                        bg=self.colors["bg_dark"], fg=self.colors["text"],
                                        insertbackground=self.colors["text"], wrap=tk.WORD)
        self.description_text.pack(fill="x")
        self.description_text.insert("1.0", self.case.get('description', ''))

        # Witnesses Section
        self.create_section_label(content, "Witnesses")

        witness_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        witness_frame.pack(fill="x", pady=5)

        self.witness_list = tk.Listbox(witness_frame, height=4, font=("Segoe UI", 10),
                                       bg=self.colors["bg_dark"], fg=self.colors["text"],
                                       selectbackground=self.colors["accent"])
        self.witness_list.pack(fill="x", side="left", expand=True)

        for witness in self.case.get('witnesses', []):
            self.witness_list.insert(tk.END, f"{witness.get('name', 'Unknown')} - {witness.get('phone', 'N/A')}")

        witness_btn_frame = tk.Frame(witness_frame, bg=self.colors["bg_medium"])
        witness_btn_frame.pack(side="right", padx=(10, 0))

        tk.Button(witness_btn_frame, text=_t("police_station.buttons.add"), bg=self.colors["success"],
                 fg="white", bd=0, padx=10, pady=5, cursor="hand2",
                 command=self.add_witness).pack(pady=2)
        tk.Button(witness_btn_frame, text=_t("police_station.buttons.remove"), bg=self.colors["accent"],
                 fg="white", bd=0, padx=10, pady=5, cursor="hand2",
                 command=self.remove_witness).pack(pady=2)

        # Notes Section
        self.create_section_label(content, "Investigation Notes")

        notes_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        notes_frame.pack(fill="x", pady=5)

        self.notes_text = tk.Text(notes_frame, height=4, font=("Segoe UI", 10),
                                  bg=self.colors["bg_dark"], fg=self.colors["text"],
                                  insertbackground=self.colors["text"], wrap=tk.WORD)
        self.notes_text.pack(fill="x")
        self.notes_text.insert("1.0", self.case.get('notes', ''))

        # Buttons
        btn_frame = tk.Frame(self, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", padx=20, pady=15)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=self.colors["bg_medium"],
                 fg=self.colors["text"], font=("Segoe UI", 11), bd=0,
                 padx=25, pady=10, cursor="hand2",
                 command=self.destroy).pack(side="right", padx=5)

        tk.Button(btn_frame, text=_t("police_station.case_details.save_case"), bg=self.colors["success"],
                 fg="white", font=("Segoe UI", 11, "bold"), bd=0,
                 padx=25, pady=10, cursor="hand2",
                 command=self.save).pack(side="right", padx=5)

        if self.case.get('id'):
            tk.Button(btn_frame, text=_t("police_station.case_details.send_update_email"), bg=self.colors["bg_light"],
                     fg=self.colors["text"], font=("Segoe UI", 11), bd=0,
                     padx=25, pady=10, cursor="hand2",
                     command=self.send_update_email).pack(side="left", padx=5)

    def create_section_label(self, parent, text):
        tk.Label(parent, text=text, font=("Segoe UI", 12, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["accent"]).pack(anchor="w", pady=(15, 5))

    def create_field(self, parent, label, value):
        frame = tk.Frame(parent, bg=self.colors["bg_medium"])
        frame.pack(fill="x", pady=5)

        tk.Label(frame, text=label, font=("Segoe UI", 10),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")

        entry = tk.Entry(frame, font=("Segoe UI", 10), bg=self.colors["bg_dark"],
                        fg=self.colors["text"], insertbackground=self.colors["text"])
        entry.insert(0, value)
        entry.pack(side="right", fill="x", expand=True, padx=(10, 0), ipady=3)

        return entry

    def toggle_student_fields(self):
        """Show/hide student ID fields based on checkbox."""
        if self.is_student_var.get():
            self.student_id_frame.pack(fill="x", pady=5, after=self.student_id_frame.master.winfo_children()[0])
            self.student_name_label.pack(fill="x", pady=2)
        else:
            self.student_id_frame.pack_forget()
            self.student_name_label.pack_forget()

    def lookup_student(self):
        """Look up student information from the database."""
        student_id = self.student_id_entry.get().strip()
        if not student_id:
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.enter_student_id"))
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                result = conn.execute(
                    "SELECT first_name, last_name, email FROM students WHERE student_id = ?",
                    (student_id,)
                ).fetchone()

                if result:
                    full_name = f"{result[0]} {result[1]}"
                    self.student_name_label.config(text=f"Student: {full_name} ({result[2]})")
                    self.case['student_name'] = full_name
                else:
                    self.student_name_label.config(text=_t("police_station.case_details.student_not_found"))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Student lookup failed: {e}")
            self.student_name_label.config(text=_t("police_station.case_details.could_not_lookup"))

    def add_witness(self):
        dialog = WitnessDialog(self, self.colors)
        if dialog.result:
            name = dialog.result.get('name', 'Unknown')
            phone = dialog.result.get('phone', 'N/A')
            self.witness_list.insert(tk.END, f"{name} - {phone}")
            if 'witnesses' not in self.case:
                self.case['witnesses'] = []
            self.case['witnesses'].append(dialog.result)

    def remove_witness(self):
        selection = self.witness_list.curselection()
        if selection:
            self.witness_list.delete(selection[0])
            if 'witnesses' in self.case and len(self.case['witnesses']) > selection[0]:
                del self.case['witnesses'][selection[0]]

    def send_update_email(self):
        officer = self.officer_combo.get()
        if officer:
            officer_email = get_officer_email(officer)
            if officer_email:
                subject, body = render_template('police_case_update', {
                    'case_id': self.case.get('id', 'Unknown'),
                    'title': self.title_entry.get(),
                    'status': self.status_combo.get(),
                    'priority': self.priority_combo.get()
                })
                if subject and body and send_notification_email(officer_email, subject, body):
                    messagebox.showinfo(_t("police_station.buttons.success"), _t("police_station.messages.email_sent", officer=officer))
                else:
                    messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.messages.email_failed"))
            else:
                messagebox.showinfo(_t("police_station.buttons.info"), _t("police_station.messages.no_email_found"))

    def save(self):
        self.result = {
            'title': self.title_entry.get(),
            'type': self.type_combo.get(),
            'status': self.status_combo.get(),
            'priority': self.priority_combo.get(),
            'officer': self.officer_combo.get(),
            'location': self.location_combo.get(),
            'description': self.description_text.get("1.0", "end-1c"),
            'notes': self.notes_text.get("1.0", "end-1c"),
            'witnesses': self.case.get('witnesses', []),
            'is_student_involved': self.is_student_var.get(),
            'student_id': self.student_id_entry.get() if self.is_student_var.get() else '',
            'student_name': self.case.get('student_name', '')
        }

        if self.on_save:
            self.on_save(self.result)

        self.destroy()


class WitnessDialog(tk.Toplevel):
    """Dialog for adding witness information."""

    def __init__(self, parent, colors):
        super().__init__(parent)
        self.title("Add Witness")
        self.geometry("400x300")
        self.configure(bg=colors["bg_dark"])
        self.transient(parent)

        self.colors = colors
        self.result = None

        self.setup_ui()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 300) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()
        self.wait_window()

    def setup_ui(self):
        tk.Label(self, text=_t("police_station.witness.title"), font=("Segoe UI", 14, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(pady=15)

        fields = [
            ("Name:", "name"),
            ("Phone:", "phone"),
            ("Email:", "email"),
            ("Address:", "address"),
        ]

        self.entries = {}
        for label, field in fields:
            frame = tk.Frame(self, bg=self.colors["bg_dark"])
            frame.pack(fill="x", padx=30, pady=5)

            tk.Label(frame, text=label, font=("Segoe UI", 10), width=10,
                    bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left")

            entry = tk.Entry(frame, font=("Segoe UI", 10), bg=self.colors["bg_medium"],
                           fg=self.colors["text"], insertbackground=self.colors["text"])
            entry.pack(side="right", fill="x", expand=True, ipady=5)
            self.entries[field] = entry

        # Statement
        stmt_frame = tk.Frame(self, bg=self.colors["bg_dark"])
        stmt_frame.pack(fill="x", padx=30, pady=5)
        tk.Label(stmt_frame, text=_t("police_station.witness.statement"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(anchor="w")
        self.statement = tk.Text(stmt_frame, height=3, font=("Segoe UI", 10),
                                bg=self.colors["bg_medium"], fg=self.colors["text"])
        self.statement.pack(fill="x")

        btn_frame = tk.Frame(self, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", padx=30, pady=15)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=self.colors["bg_medium"],
                 fg=self.colors["text"], bd=0, padx=20, pady=8,
                 command=self.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_t("police_station.witness.add"), bg=self.colors["success"],
                 fg="white", bd=0, padx=20, pady=8,
                 command=self.save).pack(side="right", padx=5)

    def save(self):
        self.result = {field: entry.get() for field, entry in self.entries.items()}
        self.result['statement'] = self.statement.get("1.0", "end-1c")
        self.destroy()
