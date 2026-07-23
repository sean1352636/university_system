"""Student experience management for assignments - drafts, receipts, progress, accessibility, timers"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import hashlib
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class StudentExperienceManager:
    """Manages student-facing assignment experience features including draft saving,
    submission receipts, progress tracking, accessibility, and countdown timers."""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style
        self._accessibility_enabled = False
        self._timer_running = False
        self._timer_after_id = None
        self._init_tables()

    def _init_tables(self):
        """Create required database tables if they don't exist"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                # Must match the canonical definition in db_manager.py.
                # student_id is FK to students.student_id which is TEXT
                # (not INTEGER), and timestamps are TEXT.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS submission_drafts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        content TEXT,
                        version INTEGER DEFAULT 1,
                        file_path TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS submission_receipts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        assignment_title TEXT,
                        submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        receipt_hash TEXT,
                        email_sent INTEGER DEFAULT 0,
                        confirmation_code TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS accessibility_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id INTEGER NOT NULL UNIQUE,
                        extended_time INTEGER DEFAULT 0,
                        high_contrast INTEGER DEFAULT 0,
                        screen_reader INTEGER DEFAULT 0,
                        font_size INTEGER DEFAULT 12,
                        extra_settings_json TEXT DEFAULT '{}',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error initializing student experience tables: {e}")

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def _get_student_id(self):
        """Get current student ID from auth context"""
        try:
            if hasattr(self.assignment_system, '_get_student_id'):
                return self.assignment_system._get_student_id()
            if self.auth and self.auth.current_user:
                return self.auth.current_user.get('id') or self.auth.current_user.get('student_id')
            return None
        except Exception:
            return None

    # ─── Draft Management ────────────────────────────────────────────────

    def show_draft_manager(self):
        """View and manage saved drafts with version history"""
        self.gui.layout.clear_content_area()
        container = self.gui.layout.content_area

        header = ttk.Label(container, text="Draft Manager", font=('Helvetica', 16, 'bold'))
        header.pack(pady=(10, 5))

        ttk.Label(container, text="View, restore, and manage your assignment drafts").pack(pady=(0, 10))

        # Controls frame
        ctrl_frame = ttk.Frame(container)
        ctrl_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Button(ctrl_frame, text="Refresh", command=self._load_drafts_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="Delete Selected", command=self._delete_selected_draft).pack(
            side=tk.LEFT, padx=5
        )

        # Drafts treeview
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ('id', 'assignment_id', 'version', 'file_path', 'created_at')
        self._draft_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=12)

        self._draft_tree.heading('id', text='Draft ID')
        self._draft_tree.heading('assignment_id', text='Assignment')
        self._draft_tree.heading('version', text='Version')
        self._draft_tree.heading('file_path', text='File')
        self._draft_tree.heading('created_at', text='Saved At')

        self._draft_tree.column('id', width=60, anchor=tk.CENTER)
        self._draft_tree.column('assignment_id', width=100, anchor=tk.CENTER)
        self._draft_tree.column('version', width=70, anchor=tk.CENTER)
        self._draft_tree.column('file_path', width=200)
        self._draft_tree.column('created_at', width=160)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._draft_tree.yview)
        self._draft_tree.configure(yscrollcommand=scrollbar.set)

        self._draft_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Content preview
        preview_label = ttk.Label(container, text="Draft Content Preview:", font=('Helvetica', 11, 'bold'))
        preview_label.pack(anchor=tk.W, padx=20, pady=(5, 0))

        self._draft_preview = scrolledtext.ScrolledText(container, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self._draft_preview.pack(fill=tk.X, padx=20, pady=(0, 5))

        self._draft_tree.bind('<<TreeviewSelect>>', self._on_draft_select)

        # Restore button
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, padx=20, pady=5)
        ttk.Button(btn_frame, text="Restore Selected Version", command=self._restore_selected_draft).pack(
            side=tk.LEFT, padx=5
        )

        self._load_drafts_list()

    def _load_drafts_list(self):
        """Load drafts into the treeview"""
        student_id = self._get_student_id()
        if not student_id:
            return

        for item in self._draft_tree.get_children():
            self._draft_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, assignment_id, version, file_path, created_at
                       FROM submission_drafts
                       WHERE student_id = ?
                       ORDER BY assignment_id, version DESC""",
                    (student_id,),
                )
                for row in cursor.fetchall():
                    self._draft_tree.insert('', tk.END, values=row)
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load drafts: {e}")

    def _on_draft_select(self, event):
        """Show content preview when a draft is selected"""
        selection = self._draft_tree.selection()
        if not selection:
            return

        draft_id = self._draft_tree.item(selection[0], 'values')[0]
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT content FROM submission_drafts WHERE id = ?", (draft_id,))
                row = cursor.fetchone()
                content = row[0] if row and row[0] else "(no text content)"
            finally:
                conn.close()

            self._draft_preview.configure(state=tk.NORMAL)
            self._draft_preview.delete('1.0', tk.END)
            self._draft_preview.insert('1.0', content)
            self._draft_preview.configure(state=tk.DISABLED)
        except Exception as e:
            print(f"Error loading draft preview: {e}")

    def _delete_selected_draft(self):
        """Delete the selected draft"""
        selection = self._draft_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a draft to delete.")
            return

        draft_id = self._draft_tree.item(selection[0], 'values')[0]
        if not messagebox.askyesno("Confirm", "Delete this draft version? This cannot be undone."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM submission_drafts WHERE id = ?", (draft_id,))
                conn.commit()
            finally:
                conn.close()
            self._load_drafts_list()
            messagebox.showinfo("Deleted", "Draft version deleted.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete draft: {e}")

    def _restore_selected_draft(self):
        """Restore the selected draft version"""
        selection = self._draft_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a draft version to restore.")
            return

        values = self._draft_tree.item(selection[0], 'values')
        draft_id = values[0]
        version = values[2]

        assignment_id = values[1]
        self.restore_draft(draft_id, version)

    def save_draft(self, assignment_id, content, file_path=None):
        """Save a draft with version tracking. Increments version for same assignment."""
        student_id = self._get_student_id()
        if not student_id:
            messagebox.showerror("Error", "Unable to identify current student.")
            return None

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Determine next version number
                cursor.execute(
                    """SELECT COALESCE(MAX(version), 0) FROM submission_drafts
                       WHERE assignment_id = ? AND student_id = ?""",
                    (assignment_id, student_id),
                )
                current_max = cursor.fetchone()[0]
                next_version = current_max + 1

                cursor.execute(
                    """INSERT INTO submission_drafts
                       (assignment_id, student_id, content, version, file_path, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (assignment_id, student_id, content, next_version, file_path, datetime.now().isoformat()),
                )
                conn.commit()
                draft_id = cursor.lastrowid
            finally:
                conn.close()

            messagebox.showinfo("Draft Saved", f"Draft saved (version {next_version}).")
            return draft_id
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save draft: {e}")
            return None

    def restore_draft(self, draft_id, version):
        """Restore a specific draft version and return its content"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT assignment_id, content, file_path FROM submission_drafts WHERE id = ?",
                    (draft_id,),
                )
                row = cursor.fetchone()
            finally:
                conn.close()

            if not row:
                messagebox.showerror("Error", "Draft not found.")
                return None

            assignment_id, content, file_path = row
            messagebox.showinfo(
                "Restored",
                f"Draft version {version} for assignment {assignment_id} has been restored.",
            )
            return {"assignment_id": assignment_id, "content": content, "file_path": file_path}
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore draft: {e}")
            return None

    # ─── Submission Receipts ─────────────────────────────────────────────

    def show_submission_receipt(self, submission_id):
        """Display a receipt window with confirmation details for a submission"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, submission_id, student_id, assignment_title,
                              submitted_at, receipt_hash, email_sent, confirmation_code
                       FROM submission_receipts WHERE submission_id = ?""",
                    (submission_id,),
                )
                row = cursor.fetchone()
            finally:
                conn.close()

            if not row:
                # Generate a receipt if one doesn't exist yet
                row = self._generate_receipt(submission_id)
                if not row:
                    messagebox.showerror("Error", "No receipt found for this submission.")
                    return

            receipt_id, sub_id, student_id, title, submitted_at, receipt_hash, email_sent, conf_code = row

            # Receipt dialog
            win = tk.Toplevel(self.root)
            win.title("Submission Receipt")
            win.geometry("500x420")
            win.resizable(False, False)
            win.transient(self.root)
            win.grab_set()

            main_frame = ttk.Frame(win, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text="Submission Receipt", font=('Helvetica', 16, 'bold')).pack(pady=(0, 15))

            details_frame = ttk.LabelFrame(main_frame, text="Confirmation Details", padding=10)
            details_frame.pack(fill=tk.X, pady=5)

            fields = [
                ("Confirmation Code:", conf_code or "N/A"),
                ("Assignment:", title or "N/A"),
                ("Submission ID:", str(sub_id)),
                ("Submitted At:", submitted_at or "N/A"),
                ("Receipt Hash:", receipt_hash[:16] + "..." if receipt_hash and len(receipt_hash) > 16 else (receipt_hash or "N/A")),
                ("Email Sent:", "Yes" if email_sent else "No"),
            ]

            for i, (label, value) in enumerate(fields):
                ttk.Label(details_frame, text=label, font=('Helvetica', 10, 'bold')).grid(
                    row=i, column=0, sticky=tk.W, padx=(0, 10), pady=2
                )
                ttk.Label(details_frame, text=value).grid(row=i, column=1, sticky=tk.W, pady=2)

            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=15)

            ttk.Button(
                btn_frame,
                text="Send Email Receipt",
                command=lambda: self.send_receipt_email(sub_id),
            ).pack(side=tk.LEFT, padx=5)

            ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show receipt: {e}")

    def _generate_receipt(self, submission_id):
        """Generate a new submission receipt and return the row tuple"""
        student_id = self._get_student_id()
        if not student_id:
            return None

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Try to get assignment title from assignment_submissions table
                assignment_title = "Unknown Assignment"
                try:
                    cursor.execute(
                        "SELECT assignment_id FROM assignment_submissions WHERE id = ?",
                        (submission_id,),
                    )
                    sub_row = cursor.fetchone()
                    if sub_row:
                        cursor.execute(
                            "SELECT title FROM assignments WHERE id = ?", (sub_row[0],)
                        )
                        title_row = cursor.fetchone()
                        if title_row:
                            assignment_title = title_row[0]
                except Exception:
                    pass

                submitted_at = datetime.now().isoformat()
                hash_input = f"{submission_id}-{student_id}-{submitted_at}"
                receipt_hash = hashlib.sha256(hash_input.encode()).hexdigest()
                confirmation_code = f"SUB-{submission_id}-{receipt_hash[:8].upper()}"

                cursor.execute(
                    """INSERT INTO submission_receipts
                       (submission_id, student_id, assignment_title, submitted_at,
                        receipt_hash, email_sent, confirmation_code)
                       VALUES (?, ?, ?, ?, ?, 0, ?)""",
                    (submission_id, student_id, assignment_title, submitted_at, receipt_hash, confirmation_code),
                )
                conn.commit()
                receipt_id = cursor.lastrowid

                return (
                    receipt_id, submission_id, student_id, assignment_title,
                    submitted_at, receipt_hash, 0, confirmation_code,
                )
            finally:
                conn.close()
        except Exception as e:
            print(f"Error generating receipt: {e}")
            return None

    def send_receipt_email(self, submission_id):
        """Send an email receipt for a submission"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT student_id, assignment_title, submitted_at, confirmation_code
                       FROM submission_receipts WHERE submission_id = ?""",
                    (submission_id,),
                )
                row = cursor.fetchone()
                if not row:
                    messagebox.showerror("Error", "No receipt found for this submission.")
                    return

                student_id, title, submitted_at, conf_code = row

                # Attempt to get student email
                email = None
                try:
                    cursor.execute("SELECT email FROM students WHERE id = ?", (student_id,))
                    email_row = cursor.fetchone()
                    if email_row:
                        email = email_row[0]
                except Exception:
                    pass

                # Try to send via infrastructure email service
                email_sent = False
                try:
                    from education_system.post_18.university_system.infrastructure.email import send_email

                    if email:
                        send_email(
                            to=email,
                            subject=f"Submission Receipt - {title}",
                            body=(
                                f"Your assignment '{title}' was submitted successfully.\n"
                                f"Confirmation Code: {conf_code}\n"
                                f"Submitted At: {submitted_at}\n\n"
                                f"Please keep this email for your records."
                            ),
                        )
                        email_sent = True
                except ImportError:
                    pass
                except Exception as e:
                    print(f"Email send failed: {e}")

                # Mark email as sent (or attempted)
                cursor.execute(
                    "UPDATE submission_receipts SET email_sent = 1 WHERE submission_id = ?",
                    (submission_id,),
                )
                conn.commit()
            finally:
                conn.close()

            if email_sent:
                messagebox.showinfo("Email Sent", f"Receipt emailed to {email}.")
            else:
                messagebox.showinfo(
                    "Receipt Recorded",
                    "Email receipt has been recorded. Email delivery may be pending if email service is unavailable.",
                )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send receipt email: {e}")

    # ─── Progress Tracking ───────────────────────────────────────────────

    # ─── Accessibility ───────────────────────────────────────────────────

    def show_accessibility_settings(self):
        """Show accessibility preferences dialog"""
        student_id = self._get_student_id()

        win = tk.Toplevel(self.root)
        win.title("Accessibility Settings")
        win.geometry("480x500")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        main_frame = ttk.Frame(win, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Accessibility Preferences", font=('Helvetica', 16, 'bold')).pack(
            pady=(0, 15)
        )

        # Load current settings
        settings = self._load_accessibility_settings(student_id)

        # Extended time
        extended_var = tk.BooleanVar(value=bool(settings.get('extended_time', 0)))
        ext_check = ttk.Checkbutton(
            main_frame, text="Extended time for assessments (1.5x)", variable=extended_var
        )
        ext_check.pack(anchor=tk.W, pady=5)

        # High contrast
        contrast_var = tk.BooleanVar(value=bool(settings.get('high_contrast', 0)))
        contrast_check = ttk.Checkbutton(
            main_frame, text="High contrast mode", variable=contrast_var
        )
        contrast_check.pack(anchor=tk.W, pady=5)

        # Screen reader support
        reader_var = tk.BooleanVar(value=bool(settings.get('screen_reader', 0)))
        reader_check = ttk.Checkbutton(
            main_frame, text="Screen reader optimised labels", variable=reader_var
        )
        reader_check.pack(anchor=tk.W, pady=5)

        # Font size
        font_frame = ttk.Frame(main_frame)
        font_frame.pack(fill=tk.X, pady=10)
        ttk.Label(font_frame, text="Font size:").pack(side=tk.LEFT)
        font_var = tk.IntVar(value=settings.get('font_size', 12))
        font_spin = ttk.Spinbox(font_frame, from_=8, to=32, width=5, textvariable=font_var)
        font_spin.pack(side=tk.LEFT, padx=10)

        # Extra settings (JSON)
        ttk.Label(main_frame, text="Additional settings (JSON):", font=('Helvetica', 10, 'bold')).pack(
            anchor=tk.W, pady=(10, 2)
        )
        extra_text = scrolledtext.ScrolledText(main_frame, height=5, wrap=tk.WORD)
        extra_text.pack(fill=tk.X, pady=(0, 10))
        extra_json = settings.get('extra_settings_json', '{}')
        extra_text.insert('1.0', extra_json if extra_json else '{}')

        def save_settings():
            extra_raw = extra_text.get('1.0', tk.END).strip()
            try:
                json.loads(extra_raw)
            except json.JSONDecodeError:
                messagebox.showerror("Error", "Additional settings must be valid JSON.")
                return

            self._save_accessibility_settings(
                student_id,
                extended_time=int(extended_var.get()),
                high_contrast=int(contrast_var.get()),
                screen_reader=int(reader_var.get()),
                font_size=font_var.get(),
                extra_settings_json=extra_raw,
            )
            messagebox.showinfo("Saved", "Accessibility settings saved.")
            win.destroy()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Save", command=save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side=tk.RIGHT, padx=5)

    def _load_accessibility_settings(self, student_id):
        """Load accessibility settings for a student"""
        defaults = {
            'extended_time': 0,
            'high_contrast': 0,
            'screen_reader': 0,
            'font_size': 12,
            'extra_settings_json': '{}',
        }
        if not student_id:
            return defaults
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT extended_time, high_contrast, screen_reader, font_size, extra_settings_json
                       FROM accessibility_settings WHERE student_id = ?""",
                    (student_id,),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        'extended_time': row[0],
                        'high_contrast': row[1],
                        'screen_reader': row[2],
                        'font_size': row[3],
                        'extra_settings_json': row[4] or '{}',
                    }
            finally:
                conn.close()
        except Exception as e:
            print(f"Error loading accessibility settings: {e}")
        return defaults

    def _save_accessibility_settings(self, student_id, **kwargs):
        """Persist accessibility settings to the database"""
        if not student_id:
            return
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO accessibility_settings
                       (student_id, extended_time, high_contrast, screen_reader, font_size, extra_settings_json, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(student_id) DO UPDATE SET
                           extended_time=excluded.extended_time,
                           high_contrast=excluded.high_contrast,
                           screen_reader=excluded.screen_reader,
                           font_size=excluded.font_size,
                           extra_settings_json=excluded.extra_settings_json,
                           updated_at=excluded.updated_at""",
                    (
                        student_id,
                        kwargs.get('extended_time', 0),
                        kwargs.get('high_contrast', 0),
                        kwargs.get('screen_reader', 0),
                        kwargs.get('font_size', 12),
                        kwargs.get('extra_settings_json', '{}'),
                        datetime.now().isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error saving accessibility settings: {e}")

    def toggle_accessibility_mode(self):
        """Toggle high contrast, larger fonts, and screen reader labels on the GUI"""
        self._accessibility_enabled = not self._accessibility_enabled
        student_id = self._get_student_id()

        if self._accessibility_enabled:
            # Apply high contrast
            try:
                style = ttk.Style()
                style.configure('TLabel', font=('Helvetica', 14))
                style.configure('TButton', font=('Helvetica', 13))
                style.configure('Treeview', font=('Helvetica', 13), rowheight=30)
                style.configure('Treeview.Heading', font=('Helvetica', 13, 'bold'))
                self.root.option_add('*Font', 'Helvetica 14')
                self.root.configure(bg='#000000')
            except Exception:
                pass

            # Persist the toggle
            self._save_accessibility_settings(
                student_id, high_contrast=1, screen_reader=1, font_size=14
            )
            messagebox.showinfo("Accessibility", "Accessibility mode enabled: high contrast, larger fonts, screen reader labels.")
        else:
            # Revert to defaults
            try:
                style = ttk.Style()
                style.configure('TLabel', font=('Helvetica', 10))
                style.configure('TButton', font=('Helvetica', 10))
                style.configure('Treeview', font=('Helvetica', 10), rowheight=20)
                style.configure('Treeview.Heading', font=('Helvetica', 10, 'bold'))
                self.root.option_add('*Font', 'Helvetica 10')
                self.root.configure(bg='#f0f0f0')
            except Exception:
                pass

            self._save_accessibility_settings(
                student_id, high_contrast=0, screen_reader=0, font_size=12
            )
            messagebox.showinfo("Accessibility", "Accessibility mode disabled: default styles restored.")

    # ─── Mobile-Friendly Submission ──────────────────────────────────────

    def show_mobile_submission_form(self, assignment_id=None):
        """Show a simplified, responsive-layout-hint submission form for mobile-sized views"""
        self.gui.layout.clear_content_area()
        container = self.gui.layout.content_area

        # Use a single column layout with larger touch targets for mobile friendliness
        header = ttk.Label(container, text="Submit Assignment", font=('Helvetica', 18, 'bold'))
        header.pack(pady=(15, 10))

        form_frame = ttk.Frame(container)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        # Assignment selector
        ttk.Label(form_frame, text="Assignment:", font=('Helvetica', 12)).pack(anchor=tk.W, pady=(5, 2))
        self._mobile_assign_var = tk.StringVar()
        assign_combo = ttk.Combobox(form_frame, textvariable=self._mobile_assign_var, state='readonly')
        assign_combo.pack(fill=tk.X, pady=(0, 10), ipady=4)
        self._load_mobile_assignments(assign_combo, assignment_id)

        # Content area
        ttk.Label(form_frame, text="Your Work:", font=('Helvetica', 12)).pack(anchor=tk.W, pady=(5, 2))
        self._mobile_content = scrolledtext.ScrolledText(form_frame, height=10, wrap=tk.WORD, font=('Helvetica', 12))
        self._mobile_content.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Large buttons for touch targets
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        save_btn = ttk.Button(
            btn_frame,
            text="Save Draft",
            command=self._mobile_save_draft,
        )
        save_btn.pack(fill=tk.X, pady=3, ipady=8)

        submit_btn = ttk.Button(
            btn_frame,
            text="Submit",
            command=self._mobile_submit,
        )
        submit_btn.pack(fill=tk.X, pady=3, ipady=8)

    def _load_mobile_assignments(self, combo, preselect_id=None):
        """Load assignments into the mobile form combo"""
        student_id = self._get_student_id()
        if not student_id:
            return
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT a.id, a.title FROM assignments a
                       JOIN enrollments e ON a.module_id = e.module_id
                       WHERE e.student_id = ?
                       ORDER BY a.title""",
                    (student_id,),
                )
                rows = cursor.fetchall()
                self._mobile_assign_map = {f"{r[0]} - {r[1]}": r[0] for r in rows}
                combo['values'] = list(self._mobile_assign_map.keys())

                if preselect_id:
                    for label, aid in self._mobile_assign_map.items():
                        if aid == preselect_id:
                            combo.set(label)
                            break
            finally:
                conn.close()
        except Exception as e:
            print(f"Error loading assignments for mobile form: {e}")

    def _mobile_save_draft(self):
        """Save draft from mobile form"""
        label = self._mobile_assign_var.get()
        if not label or label not in getattr(self, '_mobile_assign_map', {}):
            messagebox.showinfo("Info", "Please select an assignment.")
            return
        assignment_id = self._mobile_assign_map[label]
        content = self._mobile_content.get('1.0', tk.END).strip()
        if not content:
            messagebox.showinfo("Info", "Please enter some content before saving.")
            return
        self.save_draft(assignment_id, content)

    def _mobile_submit(self):
        """Submit from mobile form"""
        label = self._mobile_assign_var.get()
        if not label or label not in getattr(self, '_mobile_assign_map', {}):
            messagebox.showinfo("Info", "Please select an assignment.")
            return
        assignment_id = self._mobile_assign_map[label]
        content = self._mobile_content.get('1.0', tk.END).strip()
        if not content:
            messagebox.showinfo("Info", "Please enter some content before submitting.")
            return

        if not messagebox.askyesno("Confirm Submission", "Are you sure you want to submit? This cannot be undone."):
            return

        student_id = self._get_student_id()
        if not student_id:
            messagebox.showerror("Error", "Unable to identify current student.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO submissions (assignment_id, student_id, content, submitted_at)
                       VALUES (?, ?, ?, ?)""",
                    (assignment_id, student_id, content, datetime.now().isoformat()),
                )
                conn.commit()
                submission_id = cursor.lastrowid
            finally:
                conn.close()

            # Generate receipt
            self._generate_receipt(submission_id)
            messagebox.showinfo("Submitted", "Your assignment has been submitted successfully.")
            self.show_submission_receipt(submission_id)
        except Exception as e:
            messagebox.showerror("Error", f"Submission failed: {e}")

    # ─── Countdown Timer ─────────────────────────────────────────────────

    def show_countdown_timer(self, assessment_id):
        """Show a countdown timer with warning alerts at 10, 5, and 1 minute(s) remaining"""
        # Get assessment duration
        duration_minutes = self._get_assessment_duration(assessment_id)
        if duration_minutes is None:
            messagebox.showerror("Error", "Could not determine assessment duration.")
            return

        # Check for extended time
        student_id = self._get_student_id()
        settings = self._load_accessibility_settings(student_id)
        if settings.get('extended_time'):
            duration_minutes = int(duration_minutes * 1.5)

        self._timer_seconds = duration_minutes * 60
        self._timer_warnings_shown = set()
        self._timer_running = True

        # Timer window
        self._timer_win = tk.Toplevel(self.root)
        self._timer_win.title("Assessment Timer")
        self._timer_win.geometry("350x200")
        self._timer_win.resizable(False, False)
        self._timer_win.attributes('-topmost', True)
        self._timer_win.protocol('WM_DELETE_WINDOW', self._on_timer_close)

        frame = ttk.Frame(self._timer_win, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Time Remaining", font=('Helvetica', 14, 'bold')).pack(pady=(0, 10))

        self._timer_label = ttk.Label(frame, text="", font=('Helvetica', 36, 'bold'))
        self._timer_label.pack(pady=10)

        self._timer_status = ttk.Label(frame, text="", font=('Helvetica', 10))
        self._timer_status.pack(pady=(5, 0))

        # Progress bar
        self._timer_progress = ttk.Progressbar(frame, length=300, mode='determinate', maximum=100)
        self._timer_progress.pack(pady=10)
        self._timer_total = self._timer_seconds

        self._tick_timer()

    def _get_assessment_duration(self, assessment_id):
        """Get the duration in minutes for an assessment"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT duration_minutes FROM assignments WHERE id = ?", (assessment_id,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return int(row[0])
                # Default to 60 minutes if not specified
                return 60
            finally:
                conn.close()
        except Exception:
            return 60

    def _tick_timer(self):
        """Update the countdown timer every second"""
        if not self._timer_running:
            return

        if self._timer_seconds <= 0:
            self._timer_label.configure(text="00:00:00", foreground='red')
            self._timer_status.configure(text="Time is up!")
            self._timer_progress['value'] = 100
            self._timer_running = False
            messagebox.showwarning("Time Up", "Your assessment time has expired.", parent=self._timer_win)
            return

        hours = self._timer_seconds // 3600
        minutes = (self._timer_seconds % 3600) // 60
        seconds = self._timer_seconds % 60
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Update display
        self._timer_label.configure(text=time_str)

        # Progress bar (percentage elapsed)
        elapsed_pct = ((self._timer_total - self._timer_seconds) / self._timer_total) * 100
        self._timer_progress['value'] = elapsed_pct

        # Color coding
        remaining_min = self._timer_seconds / 60
        if remaining_min <= 1:
            self._timer_label.configure(foreground='red')
            self._timer_status.configure(text="Less than 1 minute remaining!", foreground='red')
        elif remaining_min <= 5:
            self._timer_label.configure(foreground='#cc6600')
            self._timer_status.configure(text="Less than 5 minutes remaining", foreground='#cc6600')
        elif remaining_min <= 10:
            self._timer_label.configure(foreground='#996600')
            self._timer_status.configure(text="Less than 10 minutes remaining", foreground='#996600')
        else:
            self._timer_label.configure(foreground='')
            self._timer_status.configure(text="", foreground='')

        # Warning alerts at specific thresholds
        for threshold in [10, 5, 1]:
            if remaining_min <= threshold and threshold not in self._timer_warnings_shown:
                self._timer_warnings_shown.add(threshold)
                if threshold == 1:
                    messagebox.showwarning(
                        "1 Minute Warning",
                        "You have less than 1 minute remaining!",
                        parent=self._timer_win,
                    )
                else:
                    messagebox.showwarning(
                        f"{threshold} Minute Warning",
                        f"You have less than {threshold} minutes remaining.",
                        parent=self._timer_win,
                    )

        self._timer_seconds -= 1
        self._timer_after_id = self._timer_win.after(1000, self._tick_timer)

    def _on_timer_close(self):
        """Handle timer window close"""
        if self._timer_running:
            if not messagebox.askyesno(
                "Close Timer",
                "The timer is still running. Are you sure you want to close it?",
                parent=self._timer_win,
            ):
                return
        self._timer_running = False
        if self._timer_after_id:
            try:
                self._timer_win.after_cancel(self._timer_after_id)
            except Exception:
                pass
            self._timer_after_id = None
        self._timer_win.destroy()
