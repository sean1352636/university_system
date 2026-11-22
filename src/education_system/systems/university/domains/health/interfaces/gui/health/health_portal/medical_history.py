from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, scrolledtext
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox
from datetime import datetime

from education_system.systems.university.domains.health.application.health import (
    medical_history as medical_history_service,
)
from education_system.systems.university.domains.health.infrastructure.health.storage import (
    get_connection,
)
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal import access_ui


class MedicalHistoryMixin:
    """Mixin for medical history view and management.

    The history is the student's diagnoses (``medical_conditions``) and
    health-centre records (``health_records``) —
    ``application/health/medical_history``. The health team sees any
    student and adds diagnoses; a student sees their own (number locked).
    Every look is audited, and refused if it can't be."""

    def create_view_medical_history(self):
        """View and manage medical history"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        title_label = ttk.Label(content_frame, text=_t('gui.pastoral.health.health_portal.medical_history.labels.medical_history', default="Medical History"),
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        student_row = ttk.Frame(content_frame)
        student_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(student_row, text="Student number:*").pack(side=tk.LEFT)
        self.history_student_var = tk.StringVar()
        self.history_student = ttk.Entry(student_row, textvariable=self.history_student_var,
                                         width=16)
        self.history_student.pack(side=tk.LEFT, padx=(10, 10))
        ttk.Button(student_row, text="Show history",
                   command=self.load_medical_history_display).pack(side=tk.LEFT)
        access_ui.lock_to_own(self.auth, self.history_student_var, self.history_student)

        add_frame = ttk.LabelFrame(content_frame, text=_t('gui.pastoral.health.health_portal.medical_history.labels.add_medical_history_record', default="Add Medical History Record"), padding=15)
        add_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(add_frame, text=_t('gui.pastoral.health.health_portal.medical_history.labels.condition', default="Condition:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.condition_name = ttk.Entry(add_frame, width=30)
        self.condition_name.grid(row=0, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(add_frame, text=_t('gui.pastoral.health.health_portal.medical_history.labels.date', default="Date:")).grid(row=0, column=2, sticky=tk.W, pady=5)
        self.condition_date = ttk.Entry(add_frame, width=15)
        self.condition_date.grid(row=0, column=3, sticky=tk.W, padx=(10, 20), pady=5)
        self.condition_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Button(add_frame, text=_t('gui.pastoral.health.health_portal.medical_history.buttons.add_record', default="Add Record"),
                  command=self.add_medical_history_record).grid(row=0, column=4)

        ttk.Label(add_frame, text="Severity:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.condition_severity = ttk.Combobox(add_frame, width=27, state="readonly",
                                               values=["Mild", "Moderate", "Severe"])
        self.condition_severity.grid(row=1, column=1, sticky=tk.W, padx=(10, 20), pady=5)
        ttk.Label(add_frame, text="Status:").grid(row=1, column=2, sticky=tk.W, pady=5)
        self.condition_status = ttk.Combobox(add_frame, width=12, state="readonly",
                                             values=["active", "resolved", "managed"])
        self.condition_status.set("active")
        self.condition_status.grid(row=1, column=3, sticky=tk.W, padx=(10, 20), pady=5)
        ttk.Label(add_frame, text="Provider:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.condition_provider = ttk.Entry(add_frame, width=30)
        self.condition_provider.grid(row=2, column=1, sticky=tk.W, padx=(10, 20), pady=5)
        ttk.Label(add_frame, text="Notes:").grid(row=2, column=2, sticky=tk.W, pady=5)
        self.condition_notes = ttk.Entry(add_frame, width=30)
        self.condition_notes.grid(row=2, column=3, columnspan=2, sticky=tk.W, padx=(10, 0),
                                  pady=5)
        if not access_ui.is_clinician(self.auth):
            for widget in add_frame.winfo_children():
                try:
                    widget.configure(state="disabled")
                except tk.TclError:
                    pass

        history_frame = ttk.LabelFrame(content_frame, text=_t('gui.pastoral.health.health_portal.medical_history.labels.medical_history_records', default="Medical History Records"), padding=15)
        history_frame.pack(fill=tk.BOTH, expand=True)

        self.medical_history_text = scrolledtext.ScrolledText(history_frame, wrap=tk.WORD, height=15)
        self.medical_history_text.pack(fill=tk.BOTH, expand=True)

        self.load_medical_history_display()

    def _history_student(self, quiet=False):
        typed = self.history_student_var.get().strip()
        if not typed and access_ui.own_student_id(self.auth) is None:
            if not quiet:
                messagebox.showerror(access_ui.TITLE, "Enter the student number first.",
                                     parent=self.root)
            return None
        return access_ui.scoped_student(self.root, self.auth, typed,
                                        var=self.history_student_var,
                                        widget=self.history_student) or None

    def add_medical_history_record(self):
        """Add a diagnosis to the student's medical history (health team)"""
        if not self.condition_name.get().strip():
            messagebox.showerror(_t('gui.pastoral.health.health_portal.medical_history.dialogs.validation_error', default="Validation Error"), _t('gui.pastoral.health.health_portal.medical_history.dialogs.condition_name_is_required', default="Condition name is required."))
            return
        if not access_ui.require_clinician(self.root, self.auth,
                                           "add to a student's medical history"):
            return
        student_id = self._history_student()
        if not student_id:
            return
        conn = get_connection()
        try:
            medical_history_service.add_condition(
                conn, access_ui.who(self.auth), student_id, self.condition_name.get(),
                diagnosed_date=self.condition_date.get().strip() or None,
                severity=self.condition_severity.get() or None,
                status=self.condition_status.get() or "active",
                provider=self.condition_provider.get().strip() or None,
                notes=self.condition_notes.get().strip() or None)
            conn.commit()
        except (PermissionError, ValueError) as e:
            conn.rollback()
            messagebox.showerror(_t('gui.pastoral.health.health_portal.medical_history.dialogs.error', default="Error"), str(e), parent=self.root)
            return
        except Exception as e:
            conn.rollback()
            messagebox.showerror(_t('gui.pastoral.health.health_portal.medical_history.dialogs.error', default="Error"), f"Failed to add medical history record: {str(e)}", parent=self.root)
            return
        finally:
            conn.close()

        self.condition_name.delete(0, tk.END)
        self.condition_date.delete(0, tk.END)
        self.condition_date.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.condition_provider.delete(0, tk.END)
        self.condition_notes.delete(0, tk.END)
        self.condition_severity.set("")
        self.load_medical_history_display()
        messagebox.showinfo(_t('gui.pastoral.health.health_portal.medical_history.dialogs.success', default="Success"), _t('gui.pastoral.health.health_portal.medical_history.dialogs.medical_history_record_added_successfully', default="Medical history record added successfully!"), parent=self.root)

    def load_medical_history_display(self):
        """Load and display the student's medical history"""
        self.medical_history_text.delete("1.0", tk.END)
        header = "MEDICAL HISTORY\n"
        header += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += "=" * 50 + "\n\n"
        student_id = self._history_student(quiet=True)
        if not student_id:
            self.medical_history_text.insert(tk.END, header + "Enter a student number and "
                                             "press Show history.\n")
            return
        if not access_ui.record_view(self.root, self.auth, "medical_history",
                                     student_id=student_id):
            return
        conn = get_connection()
        try:
            rows = medical_history_service.history(conn, student_id)
        except Exception as e:
            self.medical_history_text.insert(tk.END, f"Error loading medical history: {str(e)}")
            return
        finally:
            conn.close()
        lines = [header + f"Student: {student_id}\n"]
        if not rows:
            lines.append("No medical history recorded for this student.\n")
        for row in rows:
            lines.append(f"Date: {row['date'] or 'unknown'}   "
                         f"[{'Diagnosis' if row['source'] == 'condition' else 'Health record'}]\n")
            lines.append(f"Condition: {row['diagnosis'] or '-'}\n")
            if row["severity"] or row["status"]:
                lines.append(f"Severity / status: {row['severity'] or '-'} / "
                             f"{row['status'] or '-'}\n")
            if row["treatment"]:
                lines.append(f"Treatment: {row['treatment']}\n")
            if row["provider"]:
                lines.append(f"Provider: {row['provider']}\n")
            if row["notes"]:
                lines.append(f"Notes: {row['notes']}\n")
            lines.append("-" * 40 + "\n")
        self.medical_history_text.insert(tk.END, "".join(lines))
