"""
Campus Public Safety Management System
A comprehensive GUI application for university campus police and security operations.
Handles student incidents, campus emergencies, patrol logs, and safety complaints.
Integrated with university student records and email notifications.
Uses the central database for data persistence.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, timedelta
import json
import logging

from university_system.modules.shared.utils.i18n import get_text as _t
from university_system.infrastructure.email.template_utils import render_template

logger = logging.getLogger(__name__)


# Campus locations for dropdown menus
CAMPUS_LOCATIONS = [
    "Main Library", "Science Building", "Engineering Hall", "Student Center",
    "Administration Building", "Dormitory - North Hall", "Dormitory - South Hall",
    "Dormitory - East Wing", "Dormitory - West Wing", "Dining Hall",
    "Recreation Center", "Athletic Stadium", "Gymnasium", "Parking Lot A",
    "Parking Lot B", "Parking Garage", "Campus Green", "Quad",
    "Computer Lab", "Art Building", "Music Hall", "Theater",
    "Health Center", "Counseling Center", "Career Services Building",
    "Research Lab", "Graduate Housing", "Faculty Offices", "Bookstore",
    "Campus Police Station", "Maintenance Building", "Other"
]

# Incident types for campus cases
CAMPUS_INCIDENT_TYPES = [
    "Theft", "Bike Theft", "Vehicle Break-in", "Alcohol Violation",
    "Drug Violation", "Noise Violation", "Harassment", "Assault",
    "Sexual Misconduct/Title IX", "Hazing", "Vandalism", "Trespassing",
    "Disorderly Conduct", "Mental Health Crisis", "Medical Emergency",
    "Fire Alarm", "Suspicious Activity", "Lost Property", "Found Property",
    "Parking Violation", "Traffic Incident", "Academic Misconduct Referral",
    "Roommate Conflict", "Weapons Violation", "Threat Assessment", "Other"
]

# Complaint types for campus
CAMPUS_COMPLAINT_TYPES = [
    "Noise Complaint", "Roommate Dispute", "Harassment", "Theft Report",
    "Vandalism Report", "Parking Issue", "Suspicious Person", "Safety Concern",
    "Lighting Issue", "Building Access Problem", "Lost ID Card", "Stalking",
    "Discrimination", "Retaliation", "Housing Concern", "Other"
]

# Emergency alert types
CAMPUS_EMERGENCY_TYPES = [
    "Active Threat", "Campus Lockdown", "Tornado Warning", "Severe Weather",
    "Building Evacuation", "Fire Emergency", "Hazmat Incident", "Gas Leak",
    "Missing Student", "Medical Emergency", "Power Outage", "Water Main Break",
    "Campus Closure", "Shelter in Place", "All Clear", "Other"
]

# Officer ranks for campus police
CAMPUS_OFFICER_RANKS = [
    "Chief of Police", "Deputy Chief", "Lieutenant", "Sergeant",
    "Corporal", "Campus Police Officer", "Security Officer",
    "Parking Enforcement Officer", "Dispatcher", "Student Safety Officer"
]

# Database schema for campus public safety tables
POLICE_STATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS police_cases (
    id TEXT PRIMARY KEY,
    title TEXT,
    type TEXT,
    status TEXT DEFAULT 'Open',
    priority TEXT DEFAULT 'Medium',
    officer TEXT,
    location TEXT,
    description TEXT,
    notes TEXT,
    witnesses TEXT,
    student_id TEXT,
    student_name TEXT,
    is_student_involved INTEGER DEFAULT 0,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_officers (
    badge TEXT PRIMARY KEY,
    name TEXT,
    rank TEXT,
    department TEXT,
    status TEXT DEFAULT 'Active',
    phone TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_complaints (
    id TEXT PRIMARY KEY,
    complainant TEXT,
    email TEXT,
    phone TEXT,
    student_id TEXT,
    is_student INTEGER DEFAULT 0,
    type TEXT,
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Pending',
    incident_date TEXT,
    incident_time TEXT,
    location TEXT,
    description TEXT,
    suspect_description TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_criminals (
    id TEXT PRIMARY KEY,
    name TEXT,
    student_id TEXT,
    is_student INTEGER DEFAULT 0,
    affiliation TEXT,
    crime TEXT,
    status TEXT,
    arrest_date TEXT,
    case_number TEXT,
    description TEXT,
    trespass_notice INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_evidence (
    id TEXT PRIMARY KEY,
    description TEXT,
    case_number TEXT,
    type TEXT,
    location TEXT,
    custody TEXT,
    date_added TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_patrol_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    officer TEXT,
    area TEXT,
    start_time TEXT,
    end_time TEXT,
    status TEXT,
    notes TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS police_emergency_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    location TEXT,
    details TEXT,
    reporter TEXT,
    timestamp TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_police_database():
    """Initialize police station database tables."""
    try:
        from university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            conn.executescript(POLICE_STATION_SCHEMA)
            conn.commit()
        logger.info("Police station database tables initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize police database: {e}")
        return False


def get_current_user():
    """Get the current authenticated user from the system."""
    try:
        from university_system.infrastructure.shared_context import get_current_user as get_user
        user = get_user()
        if user:
            return user
    except ImportError:
        pass
    return None


def send_notification_email(recipient_email, subject, body):
    """Send notification email."""
    # Validate email address before attempting to send
    if not recipient_email or not isinstance(recipient_email, str):
        logger.debug("No recipient email provided, skipping notification")
        return False

    recipient_email = recipient_email.strip()
    if not recipient_email or '@' not in recipient_email:
        logger.debug(f"Invalid email address: {recipient_email}, skipping notification")
        return False

    try:
        from university_system.infrastructure.email.email_service import send_email
        result = send_email(recipient_email, subject, body)
        if result:
            logger.info(f"Email sent to {recipient_email}: {subject}")
            return True
        return False
    except Exception as e:
        logger.warning(f"Failed to send email: {e}")
        return False


def get_admin_emails():
    """Get list of admin user emails for notifications."""
    try:
        from university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT email FROM users WHERE role IN ('admin', 'security_admin', 'police_chief') AND email IS NOT NULL"
            )
            return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []


def get_officer_email(officer_badge):
    """Get officer email by badge number."""
    try:
        from university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT email FROM users WHERE badge_number = ? OR username = ?",
                (officer_badge, officer_badge)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception:
        return None


class ScrollableFrame(tk.Frame):
    """A scrollable frame widget."""

    def __init__(self, parent, bg="white"):
        super().__init__(parent, bg=bg)

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=bg)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)


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
            from university_system.infrastructure.database.db import get_connection
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
            logger.debug(f"Student lookup failed: {e}")
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


class EmergencyAlertDialog(tk.Toplevel):
    """Dialog for sending emergency alerts."""

    def __init__(self, parent, colors, current_user):
        super().__init__(parent)
        self.title("Emergency Alert")
        self.geometry("500x400")
        self.configure(bg="#8B0000")
        self.transient(parent)

        self.colors = colors
        self.current_user = current_user
        self.result = None

        self.setup_ui()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()

    def setup_ui(self):
        # Header
        tk.Label(self, text=_t("police_station.emergency.title"), font=("Segoe UI", 20, "bold"),
                bg="#8B0000", fg="white").pack(pady=20)

        tk.Label(self, text=_t("police_station.emergency.warning"),
                font=("Segoe UI", 10), bg="#8B0000", fg="#ffcccc").pack()

        # Alert type
        type_frame = tk.Frame(self, bg="#8B0000")
        type_frame.pack(fill="x", padx=40, pady=20)

        tk.Label(type_frame, text=_t("police_station.emergency.alert_type"), font=("Segoe UI", 11),
                bg="#8B0000", fg="white").pack(anchor="w")

        self.alert_type = ttk.Combobox(type_frame, values=CAMPUS_EMERGENCY_TYPES, font=("Segoe UI", 11))
        self.alert_type.set("Select alert type...")
        self.alert_type.pack(fill="x", pady=5)

        # Location
        loc_frame = tk.Frame(self, bg="#8B0000")
        loc_frame.pack(fill="x", padx=40, pady=10)

        tk.Label(loc_frame, text=_t("police_station.case_details.location"), font=("Segoe UI", 11),
                bg="#8B0000", fg="white").pack(anchor="w")

        # Add "Campus-Wide" option for alerts that affect the whole campus
        alert_locations = ["Campus-Wide"] + CAMPUS_LOCATIONS
        self.location = ttk.Combobox(loc_frame, values=alert_locations, font=("Segoe UI", 11))
        self.location.set("Select location...")
        self.location.pack(fill="x", pady=5)

        # Description
        desc_frame = tk.Frame(self, bg="#8B0000")
        desc_frame.pack(fill="x", padx=40, pady=10)

        tk.Label(desc_frame, text=_t("police_station.emergency.details"), font=("Segoe UI", 11),
                bg="#8B0000", fg="white").pack(anchor="w")

        self.details = tk.Text(desc_frame, height=4, font=("Segoe UI", 11))
        self.details.pack(fill="x", pady=5)

        # Buttons
        btn_frame = tk.Frame(self, bg="#8B0000")
        btn_frame.pack(fill="x", padx=40, pady=20)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg="#555555", fg="white",
                 font=("Segoe UI", 11), bd=0, padx=25, pady=10,
                 command=self.destroy).pack(side="right", padx=5)

        tk.Button(btn_frame, text=_t("police_station.emergency.send_alert"), bg="#FF0000", fg="white",
                 font=("Segoe UI", 11, "bold"), bd=0, padx=25, pady=10,
                 cursor="hand2", command=self.send_alert).pack(side="right", padx=5)

    def send_alert(self):
        alert_type = self.alert_type.get()
        location = self.location.get()
        details = self.details.get("1.0", "end-1c")

        if "Select" in alert_type:
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.select_alert_type"))
            return

        if not location:
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.enter_location"))
            return

        if messagebox.askyesno(_t("police_station.buttons.confirm"),
                              f"Send {alert_type} alert to all personnel?\n\nThis action will be logged."):
            # Get admin emails
            admin_emails = get_admin_emails()

            reporter = "Unknown"
            if self.current_user:
                reporter = self.current_user.get('name') or self.current_user.get('username', 'Unknown')

            subject, body = render_template('police_emergency_alert', {
                'alert_type': alert_type,
                'location': location,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'reporter': reporter,
                'details': details
            })

            sent_count = 0
            for email in admin_emails:
                if subject and body and send_notification_email(email, subject, body):
                    sent_count += 1

            self.result = {
                'type': alert_type,
                'location': location,
                'details': details,
                'timestamp': datetime.now().isoformat(),
                'reporter': reporter
            }

            messagebox.showinfo(_t("police_station.emergency.alert_sent"),
                              f"Emergency alert sent to {sent_count} personnel")
            self.destroy()


class PatrolLogDialog(tk.Toplevel):
    """Dialog for logging patrol activities."""

    def __init__(self, parent, colors, current_user, officers_list):
        super().__init__(parent)
        self.title("Patrol Log Entry")
        self.geometry("500x500")
        self.configure(bg=colors["bg_dark"])
        self.transient(parent)

        self.colors = colors
        self.current_user = current_user
        self.officers_list = officers_list
        self.result = None

        self.setup_ui()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 500) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()
        self.wait_window()

    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg=self.colors["accent"], height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text=_t("police_station.patrol.new_entry"), font=("Segoe UI", 14, "bold"),
                bg=self.colors["accent"], fg="white").pack(pady=12)

        content = tk.Frame(self, bg=self.colors["bg_dark"])
        content.pack(fill="both", expand=True, padx=30, pady=20)

        # Officer
        tk.Label(content, text=_t("police_station.patrol.officer_label"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(anchor="w")
        self.officer_combo = ttk.Combobox(content, values=self.officers_list)
        if self.current_user:
            name = self.current_user.get('name') or self.current_user.get('username', '')
            if name in self.officers_list:
                self.officer_combo.set(name)
        self.officer_combo.pack(fill="x", pady=(0, 15))

        # Patrol Area
        tk.Label(content, text=_t("police_station.patrol.patrol_area"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(anchor="w")
        patrol_areas = [
            "North Campus Zone", "South Campus Zone", "East Campus Zone", "West Campus Zone",
            "Residence Halls", "Academic Buildings", "Library & Study Areas",
            "Athletic Facilities", "Parking Areas", "Campus Perimeter",
            "Student Center Area", "Administrative Buildings"
        ]
        self.area_combo = ttk.Combobox(content, values=patrol_areas)
        self.area_combo.pack(fill="x", pady=(0, 15))

        # Start/End Time
        time_frame = tk.Frame(content, bg=self.colors["bg_dark"])
        time_frame.pack(fill="x", pady=(0, 15))

        tk.Label(time_frame, text=_t("police_station.patrol.start_time"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left")
        self.start_time = tk.Entry(time_frame, width=12, font=("Segoe UI", 10),
                                  bg=self.colors["bg_medium"], fg=self.colors["text"])
        self.start_time.insert(0, datetime.now().strftime("%H:%M"))
        self.start_time.pack(side="left", padx=10)

        tk.Label(time_frame, text=_t("police_station.patrol.end_time"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left", padx=(20, 0))
        self.end_time = tk.Entry(time_frame, width=12, font=("Segoe UI", 10),
                                bg=self.colors["bg_medium"], fg=self.colors["text"])
        self.end_time.pack(side="left", padx=10)

        # Status
        tk.Label(content, text=_t("police_station.patrol.patrol_status"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(anchor="w")
        self.status_combo = ttk.Combobox(content, values=[
            "Routine - No Incidents", "Suspicious Activity Observed",
            "Incident Reported", "Assistance Provided", "Warning Issued"
        ])
        self.status_combo.set("Routine - No Incidents")
        self.status_combo.pack(fill="x", pady=(0, 15))

        # Notes
        tk.Label(content, text=_t("police_station.patrol.notes"), font=("Segoe UI", 10),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(anchor="w")
        self.notes = tk.Text(content, height=6, font=("Segoe UI", 10),
                            bg=self.colors["bg_medium"], fg=self.colors["text"],
                            insertbackground=self.colors["text"])
        self.notes.pack(fill="both", expand=True, pady=(0, 15))

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x")

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=self.colors["bg_medium"],
                 fg=self.colors["text"], bd=0, padx=25, pady=10,
                 command=self.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_t("police_station.patrol.save_entry"), bg=self.colors["success"],
                 fg="white", bd=0, padx=25, pady=10,
                 command=self.save).pack(side="right", padx=5)

    def save(self):
        self.result = {
            'officer': self.officer_combo.get(),
            'area': self.area_combo.get(),
            'start_time': self.start_time.get(),
            'end_time': self.end_time.get(),
            'status': self.status_combo.get(),
            'notes': self.notes.get("1.0", "end-1c"),
            'date': datetime.now().strftime("%Y-%m-%d")
        }
        self.destroy()


class ComplaintFormDialog(tk.Toplevel):
    """Dialog for filing complaints with user info pre-filled."""

    def __init__(self, parent, colors, current_user):
        super().__init__(parent)
        self.title("File Complaint")
        self.geometry("550x600")
        self.configure(bg=colors["bg_dark"])
        self.transient(parent)

        self.colors = colors
        self.current_user = current_user
        self.result = None

        self.setup_ui()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 550) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()
        self.wait_window()

    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg=self.colors["accent"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text=_t("police_station.complaints.file_complaint"), font=("Segoe UI", 16, "bold"),
                bg=self.colors["accent"], fg="white").pack(pady=15)

        # Scrollable content
        scroll_frame = ScrollableFrame(self, bg=self.colors["bg_dark"])
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)

        content = scroll_frame.scrollable_frame

        # Complainant Info Section
        tk.Label(content, text=_t("police_station.complaints.complainant_info"), font=("Segoe UI", 12, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["accent"]).pack(anchor="w", pady=(10, 5))

        info_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        info_frame.pack(fill="x", pady=5)

        # Pre-fill with current user
        name = ""
        email = ""
        phone = ""
        if self.current_user:
            name = self.current_user.get('name') or self.current_user.get('full_name', '')
            if not name:
                first = self.current_user.get('first_name', '')
                last = self.current_user.get('last_name', '')
                name = f"{first} {last}".strip()
            email = self.current_user.get('email', '')
            phone = self.current_user.get('phone', '')

        # Name
        self.name_entry = self.create_field(info_frame, "Name:", name)
        self.email_entry = self.create_field(info_frame, "Email:", email)
        self.phone_entry = self.create_field(info_frame, "Phone:", phone)

        # Complaint Details Section
        tk.Label(content, text=_t("police_station.complaints.complaint_details"), font=("Segoe UI", 12, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["accent"]).pack(anchor="w", pady=(15, 5))

        details_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        details_frame.pack(fill="x", pady=5)

        # Complaint Type
        type_frame = tk.Frame(details_frame, bg=self.colors["bg_medium"])
        type_frame.pack(fill="x", pady=5)
        tk.Label(type_frame, text=_t("police_station.case_details.type"), font=("Segoe UI", 10), width=12,
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.type_combo = ttk.Combobox(type_frame, values=CAMPUS_COMPLAINT_TYPES)
        self.type_combo.set("Select type...")
        self.type_combo.pack(side="right", fill="x", expand=True)

        # Priority
        priority_frame = tk.Frame(details_frame, bg=self.colors["bg_medium"])
        priority_frame.pack(fill="x", pady=5)
        tk.Label(priority_frame, text=_t("police_station.case_details.priority"), font=("Segoe UI", 10), width=12,
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")
        self.priority_combo = ttk.Combobox(priority_frame, values=["Low", "Medium", "High", "Urgent"])
        self.priority_combo.set("Medium")
        self.priority_combo.pack(side="right", fill="x", expand=True)

        # Date/Time of Incident
        self.incident_date = self.create_field(details_frame, "Incident Date:",
                                               datetime.now().strftime("%Y-%m-%d"))
        self.incident_time = self.create_field(details_frame, "Incident Time:", "")

        # Location
        self.location_entry = self.create_field(details_frame, "Location:", "")

        # Description
        tk.Label(content, text=_t("police_station.case_details.description"), font=("Segoe UI", 12, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["accent"]).pack(anchor="w", pady=(15, 5))

        desc_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        desc_frame.pack(fill="x", pady=5)

        self.description = tk.Text(desc_frame, height=6, font=("Segoe UI", 10),
                                  bg=self.colors["bg_dark"], fg=self.colors["text"],
                                  insertbackground=self.colors["text"], wrap=tk.WORD)
        self.description.pack(fill="x")

        # Suspect Info (optional)
        tk.Label(content, text=_t("police_station.complaints.suspect_info"), font=("Segoe UI", 12, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["accent"]).pack(anchor="w", pady=(15, 5))

        suspect_frame = tk.Frame(content, bg=self.colors["bg_medium"], padx=15, pady=15)
        suspect_frame.pack(fill="x", pady=5)

        self.suspect_desc = self.create_field(suspect_frame, "Description:", "")

        # Buttons
        btn_frame = tk.Frame(self, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", padx=20, pady=15)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=self.colors["bg_medium"],
                 fg=self.colors["text"], font=("Segoe UI", 11), bd=0,
                 padx=25, pady=10, command=self.destroy).pack(side="right", padx=5)

        tk.Button(btn_frame, text=_t("police_station.complaints.submit_complaint"), bg=self.colors["accent"],
                 fg="white", font=("Segoe UI", 11, "bold"), bd=0,
                 padx=25, pady=10, command=self.save).pack(side="right", padx=5)

    def create_field(self, parent, label, value):
        frame = tk.Frame(parent, bg=self.colors["bg_medium"])
        frame.pack(fill="x", pady=5)

        tk.Label(frame, text=label, font=("Segoe UI", 10), width=12,
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")

        entry = tk.Entry(frame, font=("Segoe UI", 10), bg=self.colors["bg_dark"],
                        fg=self.colors["text"], insertbackground=self.colors["text"])
        entry.insert(0, value)
        entry.pack(side="right", fill="x", expand=True, ipady=3)

        return entry

    def save(self):
        if "Select" in self.type_combo.get():
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.select_complaint_type"))
            return

        if not self.description.get("1.0", "end-1c").strip():
            messagebox.showwarning(_t("police_station.buttons.warning"), _t("police_station.warnings.provide_description"))
            return

        self.result = {
            'complainant': self.name_entry.get(),
            'email': self.email_entry.get(),
            'phone': self.phone_entry.get(),
            'type': self.type_combo.get(),
            'priority': self.priority_combo.get(),
            'incident_date': self.incident_date.get(),
            'incident_time': self.incident_time.get(),
            'location': self.location_entry.get(),
            'description': self.description.get("1.0", "end-1c"),
            'suspect_description': self.suspect_desc.get(),
            'status': 'Pending',
            'date': datetime.now().strftime("%Y-%m-%d")
        }
        self.destroy()


class PoliceStationApp:
    def __init__(self, root, current_user=None):
        self.root = root
        self.root.title(_t("police_station.title"))
        self.root.geometry("1200x800")
        self.root.configure(bg="#1a1a2e")

        # Get current user - require login
        self.current_user = current_user or get_current_user()

        if not self.current_user:
            messagebox.showerror(_t("police_station.access_denied"),
                               _t("police_station.login_required"))
            self.root.destroy()
            return

        # Data storage
        self.load_data()

        # Setup UI
        self.setup_styles()
        self.create_header()
        self.create_sidebar()
        self.create_main_content()

        # Show dashboard by default
        self.show_dashboard()

    def load_data(self):
        """Load data from database"""
        # Initialize database tables
        init_police_database()

        # Load data from database
        self.data = {
            "cases": self._db_load_cases(),
            "officers": self._db_load_officers(),
            "complaints": self._db_load_complaints(),
            "criminals": self._db_load_criminals(),
            "evidence": self._db_load_evidence(),
            "patrol_logs": self._db_load_patrol_logs(),
            "emergency_alerts": self._db_load_emergency_alerts()
        }

    def _db_load_cases(self):
        """Load cases from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_cases ORDER BY date DESC")
                rows = cursor.fetchall()
                cases = []
                for row in rows:
                    case = dict(row)
                    # Parse witnesses JSON
                    if case.get('witnesses'):
                        try:
                            case['witnesses'] = json.loads(case['witnesses'])
                        except:
                            case['witnesses'] = []
                    else:
                        case['witnesses'] = []
                    cases.append(case)
                return cases
        except Exception as e:
            logger.error(f"Failed to load cases: {e}")
            return []

    def _db_load_officers(self):
        """Load officers from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_officers ORDER BY name")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load officers: {e}")
            return []

    def _db_load_complaints(self):
        """Load complaints from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_complaints ORDER BY date DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load complaints: {e}")
            return []

    def _db_load_criminals(self):
        """Load criminal records from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_criminals ORDER BY name")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load criminals: {e}")
            return []

    def _db_load_evidence(self):
        """Load evidence from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_evidence ORDER BY date_added DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load evidence: {e}")
            return []

    def _db_load_patrol_logs(self):
        """Load patrol logs from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_patrol_logs ORDER BY date DESC, start_time DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load patrol logs: {e}")
            return []

    def _db_load_emergency_alerts(self):
        """Load emergency alerts from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM police_emergency_alerts ORDER BY timestamp DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to load emergency alerts: {e}")
            return []

    def save_data(self):
        """Refresh data from database (data is saved immediately on each operation)."""
        # Data is saved immediately on each operation, so just reload
        pass

    def _db_save_case(self, case):
        """Save a case to database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            witnesses_json = json.dumps(case.get('witnesses', []))
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_cases
                    (id, title, type, status, priority, officer, location, description, notes, witnesses, date, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (case.get('id'), case.get('title'), case.get('type'), case.get('status'),
                      case.get('priority'), case.get('officer'), case.get('location'),
                      case.get('description'), case.get('notes'), witnesses_json, case.get('date')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save case: {e}")
            return False

    def _db_delete_case(self, case_id):
        """Delete a case from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_cases WHERE id = ?", (case_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete case: {e}")
            return False

    def _db_save_officer(self, officer):
        """Save an officer to database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_officers
                    (badge, name, rank, department, status, phone, email)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (officer.get('badge'), officer.get('name'), officer.get('rank'),
                      officer.get('department'), officer.get('status'), officer.get('phone'),
                      officer.get('email')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save officer: {e}")
            return False

    def _db_delete_officer(self, badge):
        """Delete an officer from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_officers WHERE badge = ?", (badge,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete officer: {e}")
            return False

    def _db_save_complaint(self, complaint):
        """Save a complaint to database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_complaints
                    (id, complainant, email, phone, type, priority, status, incident_date,
                     incident_time, location, description, suspect_description, date, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (complaint.get('id'), complaint.get('complainant'), complaint.get('email'),
                      complaint.get('phone'), complaint.get('type'), complaint.get('priority'),
                      complaint.get('status'), complaint.get('incident_date'), complaint.get('incident_time'),
                      complaint.get('location'), complaint.get('description'),
                      complaint.get('suspect_description'), complaint.get('date')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save complaint: {e}")
            return False

    def _db_delete_complaint(self, complaint_id):
        """Delete a complaint from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_complaints WHERE id = ?", (complaint_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete complaint: {e}")
            return False

    def _db_save_criminal(self, criminal):
        """Save a criminal record to database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_criminals
                    (id, name, crime, status, arrest_date, case_number, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (criminal.get('id'), criminal.get('name'), criminal.get('crime'),
                      criminal.get('status'), criminal.get('arrest_date'),
                      criminal.get('case_number'), criminal.get('description')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save criminal: {e}")
            return False

    def _db_delete_criminal(self, criminal_id):
        """Delete a criminal record from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_criminals WHERE id = ?", (criminal_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete criminal: {e}")
            return False

    def _db_save_evidence(self, evidence):
        """Save evidence to database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO police_evidence
                    (id, description, case_number, type, location, custody, date_added)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (evidence.get('id'), evidence.get('description'), evidence.get('case_number'),
                      evidence.get('type'), evidence.get('location'), evidence.get('custody'),
                      evidence.get('date_added')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save evidence: {e}")
            return False

    def _db_delete_evidence(self, evidence_id):
        """Delete evidence from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_evidence WHERE id = ?", (evidence_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete evidence: {e}")
            return False

    def _db_save_patrol_log(self, log):
        """Save a patrol log to database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO police_patrol_logs
                    (officer, area, start_time, end_time, status, notes, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (log.get('officer'), log.get('area'), log.get('start_time'),
                      log.get('end_time'), log.get('status'), log.get('notes'), log.get('date')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save patrol log: {e}")
            return False

    def _db_delete_patrol_log(self, date, officer):
        """Delete a patrol log from database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("DELETE FROM police_patrol_logs WHERE date = ? AND officer = ?", (date, officer))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete patrol log: {e}")
            return False

    def _db_save_emergency_alert(self, alert):
        """Save an emergency alert to database."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO police_emergency_alerts
                    (type, location, details, reporter, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (alert.get('type'), alert.get('location'), alert.get('details'),
                      alert.get('reporter'), alert.get('timestamp')))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save emergency alert: {e}")
            return False

    def _db_get_next_id(self, prefix, table, id_column='id'):
        """Get the next ID for a table."""
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                return f"{prefix}{count + 1:04d}"
        except Exception as e:
            logger.error(f"Failed to get next ID: {e}")
            return f"{prefix}0001"

    def get_user_display_name(self):
        """Get display name for current user."""
        if self.current_user:
            name = self.current_user.get('name') or self.current_user.get('full_name')
            if not name:
                first = self.current_user.get('first_name', '')
                last = self.current_user.get('last_name', '')
                name = f"{first} {last}".strip()
            return name or self.current_user.get('username', 'User')
        return 'Guest'

    def is_admin(self):
        """Check if current user has admin privileges."""
        if self.current_user:
            role = self.current_user.get('role', '').lower()
            return role in ['admin', 'security_admin', 'police_chief', 'officer']
        return False

    def setup_styles(self):
        """Configure ttk styles"""
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Colors
        self.colors = {
            "bg_dark": "#1a1a2e",
            "bg_medium": "#16213e",
            "bg_light": "#0f3460",
            "accent": "#e94560",
            "text": "#ffffff",
            "text_secondary": "#a0a0a0",
            "success": "#00d26a",
            "warning": "#ffc107",
            "danger": "#dc3545"
        }

        # Configure styles
        self.style.configure("Sidebar.TButton",
                            font=("Segoe UI", 11),
                            padding=15,
                            background=self.colors["bg_medium"],
                            foreground=self.colors["text"])

        self.style.configure("Treeview",
                            background=self.colors["bg_medium"],
                            foreground=self.colors["text"],
                            fieldbackground=self.colors["bg_medium"],
                            font=("Segoe UI", 10))

        self.style.configure("Treeview.Heading",
                            background=self.colors["bg_light"],
                            foreground=self.colors["text"],
                            font=("Segoe UI", 10, "bold"))

        self.style.map("Treeview",
                      background=[("selected", self.colors["accent"])])

    def create_header(self):
        """Create header section"""
        header = tk.Frame(self.root, bg=self.colors["bg_medium"], height=80)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Left side - badge and title
        left_frame = tk.Frame(header, bg=self.colors["bg_medium"])
        left_frame.pack(side="left", padx=20)

        badge_label = tk.Label(left_frame, text="🛡️", font=("Segoe UI", 32),
                              bg=self.colors["bg_medium"], fg=self.colors["accent"])
        badge_label.pack(side="left")

        title_frame = tk.Frame(left_frame, bg=self.colors["bg_medium"])
        title_frame.pack(side="left", padx=15)

        title = tk.Label(title_frame, text=_t("police_station.title_short").upper(),
                        font=("Segoe UI", 20, "bold"),
                        bg=self.colors["bg_medium"], fg=self.colors["text"])
        title.pack(anchor="w")

        subtitle = tk.Label(title_frame, text=_t("police_station.subtitle"),
                           font=("Segoe UI", 10),
                           bg=self.colors["bg_medium"], fg=self.colors["text_secondary"])
        subtitle.pack(anchor="w")

        # Right side - user info and emergency button
        right_frame = tk.Frame(header, bg=self.colors["bg_medium"])
        right_frame.pack(side="right", padx=20)

        # Emergency Alert Button
        emergency_btn = tk.Button(right_frame, text=_t("police_station.header.emergency_alert"),
                                 font=("Segoe UI", 10, "bold"),
                                 bg="#dc3545", fg="white", bd=0,
                                 padx=15, pady=8, cursor="hand2",
                                 command=self.show_emergency_dialog)
        emergency_btn.pack(side="right", padx=10)

        # User info
        user_frame = tk.Frame(right_frame, bg=self.colors["bg_medium"])
        user_frame.pack(side="right", padx=20)

        user_name = self.get_user_display_name()
        tk.Label(user_frame, text=_t("police_station.header.officer", name=user_name),
                font=("Segoe UI", 11), bg=self.colors["bg_medium"],
                fg=self.colors["text"]).pack(anchor="e")

        self.time_label = tk.Label(user_frame, font=("Segoe UI", 10),
                                  bg=self.colors["bg_medium"], fg=self.colors["text_secondary"])
        self.time_label.pack(anchor="e")
        self.update_time()

    def update_time(self):
        """Update the time display"""
        current = datetime.now().strftime("%B %d, %Y | %I:%M:%S %p")
        self.time_label.config(text=current)
        self.root.after(1000, self.update_time)

    def create_sidebar(self):
        """Create sidebar navigation"""
        self.sidebar = tk.Frame(self.root, bg=self.colors["bg_medium"], width=240)
        self.sidebar.pack(fill="y", side="left")
        self.sidebar.pack_propagate(False)

        # Refresh button
        refresh_btn = tk.Button(self.sidebar, text="🔄 " + _t("police_station.sidebar.refresh_data"),
                               font=("Segoe UI", 10), bg=self.colors["bg_light"],
                               fg=self.colors["text"], bd=0, padx=15, pady=8,
                               cursor="hand2", command=self.refresh_data)
        refresh_btn.pack(fill="x", padx=10, pady=10)

        # Menu items
        menu_items = [
            ("📊", _t("police_station.sidebar.dashboard"), self.show_dashboard),
            ("📋", _t("police_station.sidebar.incident_reports"), self.show_cases),
            ("👮", _t("police_station.sidebar.officers"), self.show_officers),
            ("📝", _t("police_station.sidebar.safety_concerns"), self.show_complaints),
            ("🚔", _t("police_station.sidebar.campus_patrols"), self.show_patrol_logs),
            ("🔍", _t("police_station.sidebar.persons_of_interest"), self.show_criminals),
            ("📦", _t("police_station.sidebar.evidence_locker"), self.show_evidence),
            ("📈", _t("police_station.sidebar.reports_analytics"), self.show_reports),
        ]

        for icon, text, command in menu_items:
            btn_frame = tk.Frame(self.sidebar, bg=self.colors["bg_medium"])
            btn_frame.pack(fill="x", pady=2)

            btn = tk.Button(btn_frame, text=f"  {icon}  {text}",
                           font=("Segoe UI", 11),
                           bg=self.colors["bg_medium"],
                           fg=self.colors["text"],
                           activebackground=self.colors["bg_light"],
                           activeforeground=self.colors["text"],
                           bd=0, anchor="w", padx=20, pady=12,
                           command=command, cursor="hand2")
            btn.pack(fill="x")

            # Hover effects
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.colors["bg_light"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.colors["bg_medium"]))

    def create_main_content(self):
        """Create main content area"""
        self.main_frame = tk.Frame(self.root, bg=self.colors["bg_dark"])
        self.main_frame.pack(fill="both", expand=True, side="right")

        self.content_frame = tk.Frame(self.main_frame, bg=self.colors["bg_dark"])
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def clear_content(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def refresh_data(self):
        """Refresh all data"""
        self.load_data()
        messagebox.showinfo(_t("police_station.sidebar.refresh_data"), _t("police_station.messages.refreshed"))

    def create_section_header(self, title, add_callback=None, extra_buttons=None):
        """Create a section header with optional add button"""
        header_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        header_frame.pack(fill="x", pady=(0, 20))

        tk.Label(header_frame, text=title, font=("Segoe UI", 18, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left")

        if add_callback:
            add_btn = tk.Button(header_frame, text=_t("police_station.cases.add_new"),
                               font=("Segoe UI", 10, "bold"),
                               bg=self.colors["accent"], fg=self.colors["text"],
                               bd=0, padx=15, pady=8, cursor="hand2",
                               command=add_callback)
            add_btn.pack(side="right")

        if extra_buttons:
            for btn_text, btn_cmd in extra_buttons:
                btn = tk.Button(header_frame, text=btn_text,
                               font=("Segoe UI", 10),
                               bg=self.colors["bg_light"], fg=self.colors["text"],
                               bd=0, padx=15, pady=8, cursor="hand2",
                               command=btn_cmd)
                btn.pack(side="right", padx=5)

    def show_emergency_dialog(self):
        """Show emergency alert dialog"""
        dialog = EmergencyAlertDialog(self.root, self.colors, self.current_user)
        if dialog.result:
            if self._db_save_emergency_alert(dialog.result):
                if 'emergency_alerts' not in self.data:
                    self.data['emergency_alerts'] = []
                self.data['emergency_alerts'].append(dialog.result)

    def show_dashboard(self):
        """Display dashboard view"""
        self.clear_content()
        self.create_section_header(_t("police_station.dashboard.title"))

        # Stats cards
        stats_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        stats_frame.pack(fill="x", pady=10)

        open_cases = len([c for c in self.data["cases"] if c.get("status") in ["Open", "In Progress"]])
        pending_complaints = len([c for c in self.data["complaints"] if c.get("status") == "Pending"])
        student_incidents = len([c for c in self.data["cases"] if c.get("is_student_involved")])
        today = datetime.now().strftime("%Y-%m-%d")

        stats = [
            ("📋", _t("police_station.dashboard.active_incidents"), open_cases, self.colors["accent"]),
            ("🎓", _t("police_station.dashboard.student_cases"), student_incidents, self.colors["warning"]),
            ("📝", _t("police_station.dashboard.pending_reports"), pending_complaints, self.colors["warning"]),
            ("👮", _t("police_station.dashboard.officers_on_duty"), len([o for o in self.data["officers"] if o.get("status") == "Active"]), self.colors["success"]),
            ("🚔", _t("police_station.dashboard.todays_patrols"), len([p for p in self.data.get("patrol_logs", [])
                                            if p.get("date") == today]),
             self.colors["success"]),
        ]

        for icon, label, value, color in stats:
            card = tk.Frame(stats_frame, bg=color, padx=3, pady=3)
            card.pack(side="left", expand=True, fill="both", padx=8)

            inner = tk.Frame(card, bg=self.colors["bg_medium"])
            inner.pack(fill="both", expand=True)

            tk.Label(inner, text=icon, font=("Segoe UI", 24),
                    bg=self.colors["bg_medium"], fg=color).pack(pady=(15, 5))
            tk.Label(inner, text=str(value), font=("Segoe UI", 28, "bold"),
                    bg=self.colors["bg_medium"], fg=self.colors["text"]).pack()
            tk.Label(inner, text=label, font=("Segoe UI", 10),
                    bg=self.colors["bg_medium"], fg=self.colors["text_secondary"]).pack(pady=(5, 15))

        # Two-column layout
        columns_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        columns_frame.pack(fill="both", expand=True, pady=20)

        # Left column - Recent Activity
        left_col = tk.Frame(columns_frame, bg=self.colors["bg_dark"])
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        activity_frame = tk.Frame(left_col, bg=self.colors["bg_medium"])
        activity_frame.pack(fill="both", expand=True)

        tk.Label(activity_frame, text=_t("police_station.dashboard.recent_cases"), font=("Segoe UI", 14, "bold"),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(anchor="w", padx=15, pady=15)

        if self.data["cases"]:
            for case in sorted(self.data["cases"], key=lambda x: x.get('date', ''), reverse=True)[:5]:
                item_frame = tk.Frame(activity_frame, bg=self.colors["bg_medium"])
                item_frame.pack(fill="x", padx=15, pady=5)

                status = case.get("status", "Open")
                status_color = self.colors["success"] if status == "Closed" else self.colors["warning"]
                tk.Label(item_frame, text="●", fg=status_color,
                        bg=self.colors["bg_medium"], font=("Segoe UI", 12)).pack(side="left")

                case_text = f"Case #{case.get('id', 'N/A')}: {case.get('title', 'Untitled')[:30]}"
                tk.Label(item_frame, text=case_text,
                        bg=self.colors["bg_medium"], fg=self.colors["text"],
                        font=("Segoe UI", 10)).pack(side="left", padx=10)
                tk.Label(item_frame, text=case.get("date", ""),
                        bg=self.colors["bg_medium"], fg=self.colors["text_secondary"],
                        font=("Segoe UI", 9)).pack(side="right")
        else:
            tk.Label(activity_frame, text=_t("police_station.dashboard.no_recent_cases"),
                    bg=self.colors["bg_medium"], fg=self.colors["text_secondary"],
                    font=("Segoe UI", 10)).pack(pady=20)

        # Right column - Quick Actions
        right_col = tk.Frame(columns_frame, bg=self.colors["bg_dark"])
        right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))

        actions_frame = tk.Frame(right_col, bg=self.colors["bg_medium"])
        actions_frame.pack(fill="both", expand=True)

        tk.Label(actions_frame, text=_t("police_station.dashboard.quick_actions"), font=("Segoe UI", 14, "bold"),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(anchor="w", padx=15, pady=15)

        quick_actions = [
            ("📋 " + _t("police_station.dashboard.new_incident_report"), self.add_case),
            ("📝 " + _t("police_station.dashboard.submit_safety_concern"), self.add_complaint),
            ("🚔 " + _t("police_station.dashboard.log_campus_patrol"), self.add_patrol_log),
            ("📦 " + _t("police_station.dashboard.log_evidence"), self.add_evidence),
        ]

        for text, command in quick_actions:
            btn = tk.Button(actions_frame, text=text, font=("Segoe UI", 11),
                           bg=self.colors["bg_light"], fg=self.colors["text"],
                           bd=0, padx=15, pady=12, cursor="hand2",
                           command=command, anchor="w")
            btn.pack(fill="x", padx=15, pady=5)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.colors["accent"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.colors["bg_light"]))

    def get_officers_list(self):
        """Get list of officer names for dropdowns"""
        return [o.get('name', 'Unknown') for o in self.data.get('officers', [])]

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
                        from university_system.infrastructure.email.template_utils import render_template
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
        from tkinter import filedialog
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
                    from university_system.infrastructure.email.template_utils import render_template
                    subject, body = render_template("police_complaint_received", {
                        "complainant_name": complaint.get('complainant', 'Citizen'),
                        "complaint_id": complaint_id,
                        "complaint_type": complaint.get('type', 'N/A'),
                        "priority": complaint.get('priority', 'Medium')
                    })
                except Exception as template_error:
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
                                from university_system.infrastructure.email.template_utils import render_template
                                subject, body = render_template("police_complaint_status_update", {
                                    "complainant_name": complaint.get('complainant', 'Citizen'),
                                    "complaint_id": complaint_id,
                                    "old_status": old_status,
                                    "new_status": status
                                })
                            except Exception as template_error:
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

    def show_reports(self):
        """Display reports view"""
        self.clear_content()
        self.create_section_header("Reports & Statistics")

        # Statistics frame
        stats_frame = tk.Frame(self.content_frame, bg=self.colors["bg_medium"], padx=20, pady=20)
        stats_frame.pack(fill="x", pady=10)

        tk.Label(stats_frame, text=_t("police_station.reports.station_statistics"), font=("Segoe UI", 14, "bold"),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(anchor="w", pady=(0, 15))

        # Calculate statistics
        total_cases = len(self.data["cases"])
        open_cases = len([c for c in self.data["cases"] if c.get("status") in ["Open", "In Progress"]])
        closed_cases = len([c for c in self.data["cases"] if c.get("status") == "Closed"])
        total_officers = len(self.data["officers"])
        active_officers = len([o for o in self.data["officers"] if o.get("status") == "Active"])
        total_complaints = len(self.data["complaints"])
        resolved_complaints = len([c for c in self.data["complaints"] if c.get("status") == "Resolved"])
        total_patrols = len(self.data.get("patrol_logs", []))

        student_incidents = len([c for c in self.data["cases"] if c.get("is_student_involved")])

        stats_data = [
            ("Total Incidents", total_cases),
            ("Active Incidents", open_cases),
            ("Resolved Incidents", closed_cases),
            ("Student-Involved Incidents", student_incidents),
            ("Resolution Rate", f"{(closed_cases/total_cases*100):.1f}%" if total_cases > 0 else "N/A"),
            ("", ""),
            ("Campus Officers", total_officers),
            ("Officers on Duty", active_officers),
            ("", ""),
            ("Safety Concerns Filed", total_complaints),
            ("Concerns Resolved", resolved_complaints),
            ("Response Rate", f"{(resolved_complaints/total_complaints*100):.1f}%" if total_complaints > 0 else "N/A"),
            ("", ""),
            ("Persons of Interest", len(self.data["criminals"])),
            ("Evidence Items Logged", len(self.data["evidence"])),
            ("Campus Patrol Entries", total_patrols),
            ("Emergency Alerts Issued", len(self.data.get("emergency_alerts", []))),
        ]

        for label, value in stats_data:
            if label == "":
                tk.Frame(stats_frame, height=10, bg=self.colors["bg_medium"]).pack()
                continue

            row = tk.Frame(stats_frame, bg=self.colors["bg_medium"])
            row.pack(fill="x", pady=3)

            tk.Label(row, text=label, font=("Segoe UI", 11),
                    bg=self.colors["bg_medium"], fg=self.colors["text_secondary"]).pack(side="left")
            tk.Label(row, text=str(value), font=("Segoe UI", 11, "bold"),
                    bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="right")

        # Report generation buttons
        btn_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        btn_frame.pack(fill="x", pady=20)

        tk.Label(btn_frame, text=_t("police_station.reports.generate_report"),
                font=("Segoe UI", 11, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left", padx=(0, 15))

        tk.Button(btn_frame, text=_t("police_station.reports.full_report"),
                 bg=self.colors["accent"], fg="white",
                 bd=0, padx=20, pady=10, font=("Segoe UI", 11), cursor="hand2",
                 command=lambda: self.open_report_window("full")).pack(side="left", padx=5)

        tk.Button(btn_frame, text=_t("police_station.reports.incidents_only"),
                 bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=10, font=("Segoe UI", 11), cursor="hand2",
                 command=lambda: self.open_report_window("incidents")).pack(side="left", padx=5)

        tk.Button(btn_frame, text=_t("police_station.reports.safety_concerns"),
                 bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=10, font=("Segoe UI", 11), cursor="hand2",
                 command=lambda: self.open_report_window("complaints")).pack(side="left", padx=5)

        tk.Button(btn_frame, text=_t("police_station.reports.patrol_logs"),
                 bg=self.colors["bg_light"], fg=self.colors["text"],
                 bd=0, padx=20, pady=10, font=("Segoe UI", 11), cursor="hand2",
                 command=lambda: self.open_report_window("patrols")).pack(side="left", padx=5)

        # Legacy export buttons
        export_frame = tk.Frame(self.content_frame, bg=self.colors["bg_dark"])
        export_frame.pack(fill="x", pady=10)

        tk.Label(export_frame, text=_t("police_station.reports.export_data"),
                font=("Segoe UI", 11, "bold"),
                bg=self.colors["bg_dark"], fg=self.colors["text"]).pack(side="left", padx=(0, 15))

        tk.Button(export_frame, text=_t("police_station.reports.export_json"),
                 bg=self.colors["bg_medium"], fg=self.colors["text"],
                 bd=0, padx=15, pady=8, font=("Segoe UI", 10), cursor="hand2",
                 command=self.export_report).pack(side="left", padx=5)

        tk.Button(export_frame, text=_t("police_station.reports.export_csv"),
                 bg=self.colors["bg_medium"], fg=self.colors["text"],
                 bd=0, padx=15, pady=8, font=("Segoe UI", 10), cursor="hand2",
                 command=self.export_cases).pack(side="left", padx=5)

    def export_report(self):
        """Export data to JSON"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"campus_safety_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.data, f, indent=2)
                messagebox.showinfo(_t("police_station.msg_titles.success"), f"Report exported to {filename}")
            except Exception as e:
                messagebox.showerror(_t("police_station.msg_titles.error"), f"Export failed: {e}")

    def generate_text_report(self, report_type="full"):
        """Generate a formatted text report."""
        today = datetime.now()
        report_lines = []

        # Header
        report_lines.append("=" * 60)
        report_lines.append("CAMPUS PUBLIC SAFETY REPORT")
        report_lines.append("University Police Department")
        report_lines.append("=" * 60)
        report_lines.append(f"Generated: {today.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Report Type: {report_type.title()}")
        report_lines.append(f"Generated By: {self.current_user.get('username', 'Unknown') if self.current_user else 'System'}")
        report_lines.append("")

        # Calculate statistics
        total_cases = len(self.data["cases"])
        open_cases = len([c for c in self.data["cases"] if c.get("status") in ["Open", "In Progress"]])
        closed_cases = len([c for c in self.data["cases"] if c.get("status") == "Closed"])
        student_incidents = len([c for c in self.data["cases"] if c.get("is_student_involved")])
        total_officers = len(self.data["officers"])
        active_officers = len([o for o in self.data["officers"] if o.get("status") == "Active"])
        total_complaints = len(self.data["complaints"])
        resolved_complaints = len([c for c in self.data["complaints"] if c.get("status") == "Resolved"])
        total_patrols = len(self.data.get("patrol_logs", []))

        # Summary Statistics
        report_lines.append("-" * 60)
        report_lines.append("SUMMARY STATISTICS")
        report_lines.append("-" * 60)
        report_lines.append(f"Total Incidents:              {total_cases}")
        report_lines.append(f"  - Active:                   {open_cases}")
        report_lines.append(f"  - Resolved:                 {closed_cases}")
        report_lines.append(f"  - Student-Involved:         {student_incidents}")
        if total_cases > 0:
            report_lines.append(f"  - Resolution Rate:          {(closed_cases/total_cases*100):.1f}%")
        report_lines.append("")
        report_lines.append(f"Campus Officers:              {total_officers}")
        report_lines.append(f"  - On Duty:                  {active_officers}")
        report_lines.append("")
        report_lines.append(f"Safety Concerns:              {total_complaints}")
        report_lines.append(f"  - Resolved:                 {resolved_complaints}")
        report_lines.append("")
        report_lines.append(f"Patrol Entries:               {total_patrols}")
        report_lines.append(f"Evidence Items:               {len(self.data['evidence'])}")
        report_lines.append(f"Persons of Interest:          {len(self.data['criminals'])}")
        report_lines.append("")

        if report_type in ["full", "incidents"]:
            # Recent Incidents
            report_lines.append("-" * 60)
            report_lines.append("RECENT INCIDENTS")
            report_lines.append("-" * 60)
            recent_cases = sorted(self.data["cases"], key=lambda x: x.get('date', ''), reverse=True)[:10]
            if recent_cases:
                for case in recent_cases:
                    report_lines.append(f"ID: {case.get('id', 'N/A')}")
                    report_lines.append(f"  Title: {case.get('title', 'Untitled')}")
                    report_lines.append(f"  Type: {case.get('type', 'N/A')} | Status: {case.get('status', 'N/A')}")
                    report_lines.append(f"  Location: {case.get('location', 'N/A')}")
                    report_lines.append(f"  Date: {case.get('date', 'N/A')}")
                    if case.get('is_student_involved'):
                        report_lines.append(f"  Student ID: {case.get('student_id', 'N/A')}")
                    report_lines.append("")
            else:
                report_lines.append("No incidents recorded.")
                report_lines.append("")

        if report_type in ["full", "complaints"]:
            # Pending Complaints
            report_lines.append("-" * 60)
            report_lines.append("PENDING SAFETY CONCERNS")
            report_lines.append("-" * 60)
            pending = [c for c in self.data["complaints"] if c.get("status") in ["Pending", "Under Investigation"]]
            if pending:
                for complaint in pending[:10]:
                    report_lines.append(f"ID: {complaint.get('id', 'N/A')}")
                    report_lines.append(f"  Type: {complaint.get('type', 'N/A')} | Priority: {complaint.get('priority', 'N/A')}")
                    report_lines.append(f"  Location: {complaint.get('location', 'N/A')}")
                    report_lines.append(f"  Date Filed: {complaint.get('date', 'N/A')}")
                    report_lines.append("")
            else:
                report_lines.append("No pending concerns.")
                report_lines.append("")

        if report_type in ["full", "patrols"]:
            # Today's Patrols
            report_lines.append("-" * 60)
            report_lines.append("TODAY'S PATROL LOGS")
            report_lines.append("-" * 60)
            today_str = today.strftime("%Y-%m-%d")
            today_patrols = [p for p in self.data.get("patrol_logs", []) if p.get("date") == today_str]
            if today_patrols:
                for patrol in today_patrols:
                    report_lines.append(f"Officer: {patrol.get('officer', 'N/A')}")
                    report_lines.append(f"  Area: {patrol.get('area', 'N/A')}")
                    report_lines.append(f"  Time: {patrol.get('start_time', 'N/A')} - {patrol.get('end_time', 'N/A')}")
                    report_lines.append(f"  Status: {patrol.get('status', 'N/A')}")
                    report_lines.append("")
            else:
                report_lines.append("No patrols logged today.")
                report_lines.append("")

        # Footer
        report_lines.append("=" * 60)
        report_lines.append("END OF REPORT")
        report_lines.append("=" * 60)
        report_lines.append("")
        report_lines.append("This report is confidential and intended for authorized")
        report_lines.append("Campus Public Safety personnel only.")

        return "\n".join(report_lines)

    def open_report_window(self, report_type="full"):
        """Open a window to preview and manage the report."""
        report_content = self.generate_text_report(report_type)
        dialog = ReportPreviewDialog(self.root, self.colors, report_content, report_type, self)

    def get_admin_emails(self):
        """Get email addresses of admin users from the database."""
        admin_emails = []
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                # Try to get admin/staff users
                result = conn.execute("""
                    SELECT DISTINCT email FROM users
                    WHERE role IN ('admin', 'Admin', 'administrator', 'staff', 'Staff', 'security', 'Security')
                    AND email IS NOT NULL AND email != ''
                """).fetchall()
                admin_emails = [row[0] for row in result if row[0] and '@' in row[0]]

                # Also get security officers emails
                for officer in self.data.get("officers", []):
                    if officer.get("email") and '@' in officer.get("email", ""):
                        if officer["email"] not in admin_emails:
                            admin_emails.append(officer["email"])
        except Exception as e:
            logger.debug(f"Could not fetch admin emails: {e}")
            # Fallback to officers in data
            for officer in self.data.get("officers", []):
                if officer.get("email") and '@' in officer.get("email", ""):
                    if officer["email"] not in admin_emails:
                        admin_emails.append(officer["email"])

        return admin_emails

    def send_report_to_admins(self, report_content, report_type="full"):
        """Send report to all admin users via email."""
        admin_emails = self.get_admin_emails()

        if not admin_emails:
            messagebox.showwarning(_t("police_station.msg_titles.no_recipients"),
                "No admin email addresses found in the system.\n\n"
                "Please add email addresses to officers or ensure admin users have emails configured.")
            return False

        # Use email template
        try:
            from university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template("police_safety_report", {
                "report_type": report_type.title(),
                "report_date": datetime.now().strftime('%Y-%m-%d'),
                "report_content": report_content
            })
        except Exception as template_error:
            # Fallback to hardcoded email
            subject = f"Campus Public Safety Report - {report_type.title()} - {datetime.now().strftime('%Y-%m-%d')}"
            body = f"""Campus Public Safety Report

This is an automated report from the Campus Public Safety System.

{report_content}

---
This email was sent automatically. Please do not reply.
Campus Public Safety - University Police Department
"""

        sent_count = 0
        failed = []

        for email in admin_emails:
            if send_notification_email(email, subject, body):
                sent_count += 1
            else:
                failed.append(email)

        if sent_count > 0:
            msg = f"Report sent successfully to {sent_count} recipient(s)."
            if failed:
                msg += f"\n\nFailed to send to: {', '.join(failed)}"
            messagebox.showinfo(_t("police_station.msg_titles.report_sent"), msg)
            return True
        else:
            messagebox.showerror(_t("police_station.msg_titles.send_failed"), "Could not send report to any recipients.")
            return False


class ReportPreviewDialog(tk.Toplevel):
    """Dialog for previewing and managing reports."""

    def __init__(self, parent, colors, report_content, report_type, app):
        super().__init__(parent)
        self.colors = colors
        self.report_content = report_content
        self.report_type = report_type
        self.app = app

        self.title(f"Report Preview - {report_type.title()}")
        self.geometry("700x600")
        self.configure(bg=colors["bg_dark"])
        self.transient(parent)

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")

        self.create_widgets()

        self.wait_visibility()
        self.grab_set()

    def create_widgets(self):
        # Header
        header = tk.Frame(self, bg=self.colors["bg_medium"], padx=20, pady=15)
        header.pack(fill="x")

        tk.Label(header, text=_t("police_station.reports.report_title"),
                font=("Segoe UI", 16, "bold"),
                bg=self.colors["bg_medium"], fg=self.colors["text"]).pack(side="left")

        tk.Label(header, text=f"Type: {self.report_type.title()}",
                font=("Segoe UI", 10),
                bg=self.colors["bg_medium"], fg=self.colors["text_secondary"]).pack(side="right")

        # Report content area
        content_frame = tk.Frame(self, bg=self.colors["bg_dark"], padx=20, pady=10)
        content_frame.pack(fill="both", expand=True)

        # Text widget with scrollbar
        text_frame = tk.Frame(content_frame, bg=self.colors["bg_dark"])
        text_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        self.report_text = tk.Text(text_frame, wrap=tk.WORD,
                                   font=("Consolas", 10),
                                   bg=self.colors["bg_medium"],
                                   fg=self.colors["text"],
                                   insertbackground=self.colors["text"],
                                   yscrollcommand=scrollbar.set,
                                   padx=15, pady=15)
        self.report_text.pack(fill="both", expand=True)
        scrollbar.config(command=self.report_text.yview)

        # Insert report content
        self.report_text.insert("1.0", self.report_content)
        self.report_text.config(state="disabled")  # Make read-only

        # Button frame
        btn_frame = tk.Frame(self, bg=self.colors["bg_dark"], padx=20, pady=15)
        btn_frame.pack(fill="x")

        # Save as TXT button
        save_btn = tk.Button(btn_frame, text=_t("police_station.reports.save_as_txt"),
                            font=("Segoe UI", 11),
                            bg=self.colors["success"], fg="white",
                            bd=0, padx=25, pady=10, cursor="hand2",
                            command=self.save_as_txt)
        save_btn.pack(side="left", padx=5)

        # Send to Admin button
        send_btn = tk.Button(btn_frame, text=_t("police_station.reports.send_to_admin"),
                            font=("Segoe UI", 11),
                            bg=self.colors["accent"], fg="white",
                            bd=0, padx=25, pady=10, cursor="hand2",
                            command=self.send_to_admin)
        send_btn.pack(side="left", padx=5)

        # Show recipients button
        recipients_btn = tk.Button(btn_frame, text=_t("police_station.reports.view_recipients"),
                                  font=("Segoe UI", 11),
                                  bg=self.colors["bg_light"], fg=self.colors["text"],
                                  bd=0, padx=20, pady=10, cursor="hand2",
                                  command=self.show_recipients)
        recipients_btn.pack(side="left", padx=5)

        # Close button
        close_btn = tk.Button(btn_frame, text=_t("police_station.buttons.cancel"),
                             font=("Segoe UI", 11),
                             bg=self.colors["bg_medium"], fg=self.colors["text"],
                             bd=0, padx=25, pady=10, cursor="hand2",
                             command=self.destroy)
        close_btn.pack(side="right", padx=5)

    def save_as_txt(self):
        """Save the report as a TXT file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"campus_safety_report_{self.report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.report_content)
                messagebox.showinfo(_t("police_station.msg_titles.success"), f"Report saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror(_t("police_station.msg_titles.error"), f"Could not save report:\n{e}")

    def send_to_admin(self):
        """Send the report to admin users."""
        admin_emails = self.app.get_admin_emails()

        if not admin_emails:
            messagebox.showwarning(_t("police_station.msg_titles.no_recipients"),
                "No admin email addresses found.\n\n"
                "Please ensure officers have email addresses configured,\n"
                "or add admin users to the system.")
            return

        # Confirm before sending
        confirm = messagebox.askyesno(_t("police_station.msg_titles.confirm_send"),
            f"Send this report to {len(admin_emails)} recipient(s)?\n\n"
            f"Recipients:\n" + "\n".join(f"  - {email}" for email in admin_emails[:5]) +
            ("\n  ..." if len(admin_emails) > 5 else ""))

        if confirm:
            self.app.send_report_to_admins(self.report_content, self.report_type)

    def show_recipients(self):
        """Show list of admin email recipients."""
        admin_emails = self.app.get_admin_emails()

        if admin_emails:
            msg = "Report will be sent to:\n\n"
            for email in admin_emails:
                msg += f"  - {email}\n"
        else:
            msg = "No admin email addresses found.\n\n"
            msg += "To add recipients:\n"
            msg += "1. Add email addresses to officers in the Officers section\n"
            msg += "2. Ensure admin users have emails in the system database"

        messagebox.showinfo(_t("police_station.msg_titles.email_recipients"), msg)


class OfficerDialog:
    """Dialog for adding/editing officers"""
    def __init__(self, parent, title, colors, officer=None):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x400")
        self.dialog.configure(bg=colors["bg_dark"])
        self.dialog.transient(parent)

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_visibility()
        self.dialog.grab_set()

        fields = [
            ("Name:", "name", None),
            ("Rank:", "rank", CAMPUS_OFFICER_RANKS),
            ("Department:", "department", ["Campus Patrol", "Investigations", "Parking Services",
                                           "Event Security", "Dispatch", "Administration",
                                           "Community Outreach", "Student Safety"]),
            ("Status:", "status", ["Active", "On Leave", "Training", "Off Duty", "Resigned"]),
            ("Phone:", "phone", None),
            ("Email:", "email", None),
        ]

        self.entries = {}
        for label, field, options in fields:
            frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
            frame.pack(fill="x", padx=20, pady=5)

            tk.Label(frame, text=label, font=("Segoe UI", 10), width=12,
                    bg=colors["bg_dark"], fg=colors["text"]).pack(side="left")

            if options:
                self.entries[field] = ttk.Combobox(frame, values=options)
                self.entries[field].set(officer.get(field, options[0]) if officer else options[0])
            else:
                self.entries[field] = tk.Entry(frame, font=("Segoe UI", 10),
                                              bg=colors["bg_medium"], fg=colors["text"],
                                              insertbackground=colors["text"])
                if officer:
                    self.entries[field].insert(0, officer.get(field, ""))
            self.entries[field].pack(side="right", fill="x", expand=True, ipady=5)

        btn_frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
        btn_frame.pack(fill="x", padx=20, pady=20)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=colors["bg_medium"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.dialog.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_t("police_station.buttons.save"), bg=colors["accent"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.save).pack(side="right", padx=5)

        self.dialog.wait_window()

    def save(self):
        self.result = {field: self.entries[field].get() for field in self.entries}
        self.dialog.destroy()


class CriminalDialog:
    """Dialog for adding criminal records"""
    def __init__(self, parent, title, colors):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x500")
        self.dialog.configure(bg=colors["bg_dark"])
        self.dialog.transient(parent)

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 500) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_visibility()
        self.dialog.grab_set()

        fields = [
            ("Name:", "name", None),
            ("Crime:", "crime", ["Theft", "Assault", "Fraud", "Drug Possession", "Vandalism", "Trespassing", "Other"]),
            ("Status:", "status", ["In Custody", "Released", "Wanted", "On Parole", "Under Investigation"]),
            ("Arrest Date:", "arrest_date", None),
            ("Related Case #:", "case_number", None),
        ]

        self.entries = {}
        for label, field, options in fields:
            frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
            frame.pack(fill="x", padx=20, pady=5)

            tk.Label(frame, text=label, font=("Segoe UI", 10), width=14,
                    bg=colors["bg_dark"], fg=colors["text"]).pack(side="left")

            if options:
                self.entries[field] = ttk.Combobox(frame, values=options)
                self.entries[field].set(options[0])
            else:
                self.entries[field] = tk.Entry(frame, font=("Segoe UI", 10),
                                              bg=colors["bg_medium"], fg=colors["text"],
                                              insertbackground=colors["text"])
            self.entries[field].pack(side="right", fill="x", expand=True, ipady=5)

        desc_frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
        desc_frame.pack(fill="both", expand=True, padx=20, pady=5)

        tk.Label(desc_frame, text=_t("police_station.case_details.investigation_notes"), font=("Segoe UI", 10),
                bg=colors["bg_dark"], fg=colors["text"]).pack(anchor="w")

        self.description = tk.Text(desc_frame, height=6, font=("Segoe UI", 10),
                                  bg=colors["bg_medium"], fg=colors["text"],
                                  insertbackground=colors["text"])
        self.description.pack(fill="both", expand=True)

        btn_frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
        btn_frame.pack(fill="x", padx=20, pady=15)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=colors["bg_medium"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.dialog.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_t("police_station.buttons.save"), bg=colors["accent"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.save).pack(side="right", padx=5)

        self.dialog.wait_window()

    def save(self):
        self.result = {
            "name": self.entries["name"].get(),
            "crime": self.entries["crime"].get(),
            "status": self.entries["status"].get(),
            "arrest_date": self.entries["arrest_date"].get(),
            "case_number": self.entries["case_number"].get(),
            "description": self.description.get("1.0", "end-1c")
        }
        self.dialog.destroy()


class EvidenceDialog:
    """Dialog for adding/editing evidence"""
    def __init__(self, parent, title, colors, evidence=None):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x400")
        self.dialog.configure(bg=colors["bg_dark"])
        self.dialog.transient(parent)

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.wait_visibility()
        self.dialog.grab_set()

        fields = [
            ("Description:", "description", None),
            ("Related Case #:", "case_number", None),
            ("Evidence Type:", "type", ["Physical", "Digital", "Document", "Weapon", "Clothing", "Vehicle", "Other"]),
            ("Storage Location:", "location", None),
            ("Chain of Custody:", "custody", None),
        ]

        self.entries = {}
        for label, field, options in fields:
            frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
            frame.pack(fill="x", padx=20, pady=5)

            tk.Label(frame, text=label, font=("Segoe UI", 10), width=16,
                    bg=colors["bg_dark"], fg=colors["text"]).pack(side="left")

            if options:
                self.entries[field] = ttk.Combobox(frame, values=options)
                self.entries[field].set(evidence.get(field, options[0]) if evidence else options[0])
            else:
                self.entries[field] = tk.Entry(frame, font=("Segoe UI", 10),
                                              bg=colors["bg_medium"], fg=colors["text"],
                                              insertbackground=colors["text"])
                if evidence:
                    self.entries[field].insert(0, evidence.get(field, ""))
            self.entries[field].pack(side="right", fill="x", expand=True, ipady=5)

        btn_frame = tk.Frame(self.dialog, bg=colors["bg_dark"])
        btn_frame.pack(fill="x", padx=20, pady=20)

        tk.Button(btn_frame, text=_t("police_station.buttons.cancel"), bg=colors["bg_medium"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.dialog.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_t("police_station.buttons.save"), bg=colors["accent"], fg=colors["text"],
                 bd=0, padx=20, pady=8, command=self.save).pack(side="right", padx=5)

        self.dialog.wait_window()

    def save(self):
        self.result = {field: self.entries[field].get() for field in self.entries}
        self.dialog.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = PoliceStationApp(root)
    root.mainloop()
