"""Student Profile Center GUI (Feature 31).

Allows students to view and edit their personal profile information
including contact details, emergency contacts, and pronouns.
"""

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class StudentProfileGUI:
    """Toplevel window for viewing and editing student profile information."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = ''
        if auth and auth.current_user:
            self.student_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Student Profile Center")
        self.window.geometry("900x600")
        self.window.transient(parent)

        self.field_entries = {}
        self.profile_data = {}

        self._ensure_columns()
        self._setup_ui()
        self._load_profile()

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def _ensure_columns(self):
        """Add emergency_contact and pronouns columns if they are missing."""
        columns_to_add = [
            ("emergency_contact", "TEXT DEFAULT ''"),
            ("pronouns", "TEXT DEFAULT ''"),
        ]
        try:
            with get_connection() as conn:
                for col_name, col_def in columns_to_add:
                    try:
                        conn.execute(
                            f"ALTER TABLE students ADD COLUMN {col_name} {col_def}"
                        )
                        conn.commit()
                        logger.info("Added column %s to students table", col_name)
                    except Exception:
                        # Column already exists — that is fine
                        pass
        except Exception as exc:
            logger.warning("Could not ensure profile columns: %s", exc)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the profile form."""
        ttk.Label(
            self.window,
            text="Student Profile Center",
            font=("Arial", 16, "bold"),
        ).pack(pady=(15, 5))

        ttk.Label(
            self.window,
            text=f"Student ID: {self.student_id}",
            font=("Arial", 10),
        ).pack(pady=(0, 10))

        # Scrollable form area
        form_frame = ttk.Frame(self.window)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)

        fields = [
            ("Name", "name", True),
            ("Email", "email", False),
            ("Gender", "gender", True),
            ("Date of Birth (YYYY-MM-DD)", "dob", True),
            ("Course", "course", True),
            ("Emergency Contact", "emergency_contact", False),
            ("Pronouns", "pronouns", False),
        ]

        for row_idx, (label_text, field_key, readonly) in enumerate(fields):
            ttk.Label(
                form_frame, text=label_text + ":", font=("Arial", 11)
            ).grid(row=row_idx, column=0, sticky=tk.W, padx=(0, 15), pady=8)

            var = tk.StringVar()
            entry = ttk.Entry(form_frame, textvariable=var, width=55)
            if readonly:
                entry.configure(state="readonly")
            entry.grid(row=row_idx, column=1, sticky=tk.W, pady=8)

            self.field_entries[field_key] = {"var": var, "entry": entry, "readonly": readonly}

        # Status label
        self.status_var = tk.StringVar(value="")
        ttk.Label(
            self.window, textvariable=self.status_var, foreground="gray"
        ).pack(pady=(5, 0))

        # Buttons
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text="Save Changes", command=self._save_profile).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_frame, text="Refresh", command=self._load_profile).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_frame, text="Close", command=self.window.destroy).pack(
            side=tk.LEFT, padx=10
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_profile(self):
        """Load student profile data from the database."""
        if not self.student_id:
            self.status_var.set("No student ID available.")
            return

        defaults = {
            "name": "",
            "email": "",
            "gender": "",
            "dob": "",
            "course": "",
            "emergency_contact": "",
            "pronouns": "",
        }

        try:
            with get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT s.first_name, s.last_name, s.email_address,
                           s.gender, s.dob, s.course,
                           s.emergency_contact, s.pronouns
                    FROM students s
                    WHERE s.student_id = ?
                    """,
                    (self.student_id,),
                ).fetchone()

            if row:
                first = row["first_name"] if row["first_name"] else ""
                last = row["last_name"] if row["last_name"] else ""
                self.profile_data = {
                    "name": f"{first} {last}".strip(),
                    "email": row["email_address"] or "",
                    "gender": row["gender"] or "",
                    "dob": row["dob"] or "",
                    "course": row["course"] or "",
                    "emergency_contact": row["emergency_contact"] or "",
                    "pronouns": row["pronouns"] or "",
                }
            else:
                self.profile_data = dict(defaults)
                self.status_var.set("No profile record found.")
                logger.warning("No student record for %s", self.student_id)

        except Exception as exc:
            logger.error("Failed to load profile for %s: %s", self.student_id, exc)
            self.profile_data = dict(defaults)
            self.status_var.set("Error loading profile.")

        # Populate form fields
        for key, info in self.field_entries.items():
            if info["readonly"]:
                info["entry"].configure(state="normal")
            info["var"].set(self.profile_data.get(key, ""))
            if info["readonly"]:
                info["entry"].configure(state="readonly")

        self.status_var.set("Profile loaded.")

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def _save_profile(self):
        """Save the edited profile fields back to the database."""
        if not self.student_id:
            messagebox.showwarning("Warning", "No student ID available.", parent=self.window)
            return

        email = self.field_entries["email"]["var"].get().strip()
        emergency_contact = self.field_entries["emergency_contact"]["var"].get().strip()
        pronouns = self.field_entries["pronouns"]["var"].get().strip()

        try:
            with transaction() as conn:
                conn.execute(
                    """
                    UPDATE students
                    SET email_address = ?,
                        emergency_contact = ?, pronouns = ?
                    WHERE student_id = ?
                    """,
                    (email, emergency_contact, pronouns, self.student_id),
                )

            log_activity(
                self.student_id, self.student_id, 'student',
                'update', 'student_profile',
                details=f"Profile updated for {self.student_id}",
            )

            logger.info("Profile saved for student %s", self.student_id)
            self.status_var.set("Profile saved successfully.")
            messagebox.showinfo(
                "Success", "Your profile has been updated.", parent=self.window
            )

        except Exception as exc:
            logger.error("Failed to save profile for %s: %s", self.student_id, exc)
            messagebox.showerror(
                "Error",
                f"Could not save profile: {exc}",
                parent=self.window,
            )
