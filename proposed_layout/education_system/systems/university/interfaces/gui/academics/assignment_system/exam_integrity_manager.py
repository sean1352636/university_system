"""Exam integrity management - randomization, time limits, proctoring, and monitoring"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class ExamIntegrityManager:
    """Exam integrity settings, proctoring, and monitoring"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def _ensure_tables(self, cursor):
        """Create exam integrity tables if they don't exist"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exam_integrity_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id INTEGER NOT NULL,
                randomize_questions INTEGER DEFAULT 0,
                randomize_answers INTEGER DEFAULT 0,
                question_count INTEGER DEFAULT 0,
                time_limit_minutes INTEGER DEFAULT 0,
                auto_submit INTEGER DEFAULT 0,
                browser_lockdown INTEGER DEFAULT 0,
                proctoring_provider TEXT DEFAULT '',
                ip_restriction_enabled INTEGER DEFAULT 0,
                allowed_ips_json TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(assessment_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exam_integrity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data_json TEXT DEFAULT '{}',
                timestamp TEXT DEFAULT (datetime('now'))
            )
        ''')

    def _load_assessments_into_combo(self, combo):
        """Load assessments into a combobox"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, assessment_name FROM assessments WHERE status = 'Active' ORDER BY assessment_name"
            )
            rows = cursor.fetchall()
            conn.close()

            self._assessment_map = {f"{row[0]} - {row[1]}": row[0] for row in rows}
            combo['values'] = list(self._assessment_map.keys())
        except Exception:
            combo['values'] = []
            self._assessment_map = {}

    # -------------------------------------------------------------------------
    # Main settings dashboard
    # -------------------------------------------------------------------------

    def show_exam_integrity_settings(self):
        """Main settings dashboard for exam integrity"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to manage exam integrity settings.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text="Exam Integrity Settings", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Assessment selector
        sel_frame = ttk.LabelFrame(content, text="Select Assessment", padding=10)
        sel_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(sel_frame, text="Assessment:").grid(row=0, column=0, sticky='w', pady=5)
        self.integrity_assessment_var = tk.StringVar()
        assessment_combo = ttk.Combobox(
            sel_frame, textvariable=self.integrity_assessment_var, width=50, state='readonly'
        )
        assessment_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        self._load_assessments_into_combo(assessment_combo)

        # Action buttons
        btn_frame = ttk.LabelFrame(content, text="Configuration", padding=10)
        btn_frame.pack(fill='x', pady=(0, 15))

        buttons = [
            ("Configure Randomization", self._on_configure_randomization),
            ("Configure Time Limits", self._on_configure_time_limits),
            ("Configure Browser Lockdown", self._on_configure_browser_lockdown),
            ("Configure IP Restrictions", self._on_configure_ip_restrictions),
        ]
        for i, (text, cmd) in enumerate(buttons):
            ttk.Button(btn_frame, text=text, command=cmd).grid(
                row=i // 2, column=i % 2, padx=10, pady=5, sticky='ew'
            )
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        # Monitoring buttons
        mon_frame = ttk.LabelFrame(content, text="Monitoring & Logs", padding=10)
        mon_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(mon_frame, text="Proctoring Dashboard", command=self.show_proctoring_dashboard).grid(
            row=0, column=0, padx=10, pady=5, sticky='ew'
        )
        ttk.Button(mon_frame, text="View Integrity Logs", command=self.view_integrity_logs).grid(
            row=0, column=1, padx=10, pady=5, sticky='ew'
        )
        ttk.Button(mon_frame, text="Flagged Students", command=self.show_flagged_students).grid(
            row=0, column=2, padx=10, pady=5, sticky='ew'
        )
        mon_frame.columnconfigure(0, weight=1)
        mon_frame.columnconfigure(1, weight=1)
        mon_frame.columnconfigure(2, weight=1)

        # Current settings overview
        self._show_settings_overview(content)

    def _get_selected_assessment_id(self):
        """Get the currently selected assessment ID or show warning"""
        label = getattr(self, 'integrity_assessment_var', tk.StringVar()).get()
        if not label:
            messagebox.showwarning("No Selection", "Please select an assessment first.")
            return None
        return self._assessment_map.get(label)

    def _on_configure_randomization(self):
        assessment_id = self._get_selected_assessment_id()
        if assessment_id:
            self.configure_randomization(assessment_id)

    def _on_configure_time_limits(self):
        assessment_id = self._get_selected_assessment_id()
        if assessment_id:
            self.configure_time_limits(assessment_id)

    def _on_configure_browser_lockdown(self):
        assessment_id = self._get_selected_assessment_id()
        if assessment_id:
            self.configure_browser_lockdown(assessment_id)

    def _on_configure_ip_restrictions(self):
        assessment_id = self._get_selected_assessment_id()
        if assessment_id:
            self.configure_ip_restrictions(assessment_id)

    def _show_settings_overview(self, parent):
        """Show overview table of all assessment integrity settings"""
        overview_frame = ttk.LabelFrame(parent, text="Settings Overview", padding=10)
        overview_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('assessment', 'randomize_q', 'randomize_a', 'q_count', 'time_limit',
                   'auto_submit', 'lockdown', 'proctoring', 'ip_restrict')
        tree = ttk.Treeview(overview_frame, columns=columns, show='headings', height=10)

        headings = {
            'assessment': 'Assessment',
            'randomize_q': 'Rand. Questions',
            'randomize_a': 'Rand. Answers',
            'q_count': 'Q Count',
            'time_limit': 'Time Limit',
            'auto_submit': 'Auto Submit',
            'lockdown': 'Lockdown',
            'proctoring': 'Proctoring',
            'ip_restrict': 'IP Restrict',
        }
        for col, heading in headings.items():
            tree.heading(col, text=heading)
            tree.column(col, width=100, anchor='center')
        tree.column('assessment', width=200, anchor='w')

        scrollbar = ttk.Scrollbar(overview_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_tables(cursor)
            cursor.execute('''
                SELECT s.assessment_id, a.assessment_name,
                       s.randomize_questions, s.randomize_answers, s.question_count,
                       s.time_limit_minutes, s.auto_submit, s.browser_lockdown,
                       s.proctoring_provider, s.ip_restriction_enabled
                FROM exam_integrity_settings s
                LEFT JOIN assessments a ON s.assessment_id = a.id
                ORDER BY a.assessment_name
            ''')
            for row in cursor.fetchall():
                yes_no = lambda v: "Yes" if v else "No"
                tree.insert('', 'end', values=(
                    row[1] or f"ID: {row[0]}",
                    yes_no(row[2]), yes_no(row[3]),
                    row[4] or "All", f"{row[5]} min" if row[5] else "None",
                    yes_no(row[6]), yes_no(row[7]),
                    row[8] or "None", yes_no(row[9])
                ))
            conn.close()
        except Exception as e:
            ttk.Label(overview_frame, text=f"Could not load settings: {e}").pack()

    # -------------------------------------------------------------------------
    # Randomization settings
    # -------------------------------------------------------------------------

    def configure_randomization(self, assessment_id):
        """Randomization settings dialog for an assessment"""
        if not self._check_permission('manage_assignments'):
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Configure Randomization")
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Randomization Settings", font=('Helvetica', 14, 'bold')).pack(
            anchor='w', pady=(0, 15)
        )

        # Load existing settings
        settings = self._load_settings(assessment_id)

        # Randomize question order
        rand_q_var = tk.BooleanVar(value=bool(settings.get('randomize_questions', 0)))
        ttk.Checkbutton(main_frame, text="Randomize question order per student", variable=rand_q_var).pack(
            anchor='w', pady=5
        )

        # Randomize answer choices
        rand_a_var = tk.BooleanVar(value=bool(settings.get('randomize_answers', 0)))
        ttk.Checkbutton(main_frame, text="Randomize answer choices per student", variable=rand_a_var).pack(
            anchor='w', pady=5
        )

        # Question bank selection
        bank_frame = ttk.LabelFrame(main_frame, text="Question Bank Selection", padding=10)
        bank_frame.pack(fill='x', pady=(10, 5))

        ttk.Label(bank_frame, text="Select N questions from bank (0 = all):").grid(
            row=0, column=0, sticky='w', pady=5
        )
        q_count_var = tk.StringVar(value=str(settings.get('question_count', 0)))
        ttk.Entry(bank_frame, textvariable=q_count_var, width=10).grid(
            row=0, column=1, sticky='w', pady=5, padx=(10, 0)
        )

        ttk.Label(bank_frame, text="Each student receives a different random subset\nof questions from the question bank.",
                  foreground='gray').grid(row=1, column=0, columnspan=2, sticky='w', pady=5)

        def save():
            try:
                q_count = int(q_count_var.get())
                if q_count < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Question count must be a non-negative integer.", parent=dialog)
                return

            self._save_settings(assessment_id, {
                'randomize_questions': int(rand_q_var.get()),
                'randomize_answers': int(rand_a_var.get()),
                'question_count': q_count,
            })
            messagebox.showinfo("Saved", "Randomization settings saved successfully.", parent=dialog)
            dialog.destroy()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=save, style='Accent.TButton').pack(side='left')
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=(10, 0))

    # -------------------------------------------------------------------------
    # Time limit settings
    # -------------------------------------------------------------------------

    def configure_time_limits(self, assessment_id):
        """Time limit settings dialog for an assessment"""
        if not self._check_permission('manage_assignments'):
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Configure Time Limits")
        dialog.geometry("450x320")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Time Limit Settings", font=('Helvetica', 14, 'bold')).pack(
            anchor='w', pady=(0, 15)
        )

        settings = self._load_settings(assessment_id)

        # Time limit
        time_frame = ttk.LabelFrame(main_frame, text="Time Limit", padding=10)
        time_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(time_frame, text="Time limit (minutes, 0 = unlimited):").grid(
            row=0, column=0, sticky='w', pady=5
        )
        time_var = tk.StringVar(value=str(settings.get('time_limit_minutes', 0)))
        ttk.Entry(time_frame, textvariable=time_var, width=10).grid(
            row=0, column=1, sticky='w', pady=5, padx=(10, 0)
        )

        # Auto-submit
        auto_var = tk.BooleanVar(value=bool(settings.get('auto_submit', 0)))
        ttk.Checkbutton(
            main_frame, text="Auto-submit when time expires", variable=auto_var
        ).pack(anchor='w', pady=5)

        ttk.Label(
            main_frame,
            text="When enabled, the student's exam will be automatically\n"
                 "submitted when the time limit is reached. Unanswered\n"
                 "questions will be submitted as-is.",
            foreground='gray'
        ).pack(anchor='w', pady=(5, 10))

        # Warning thresholds
        warn_frame = ttk.LabelFrame(main_frame, text="Warnings", padding=10)
        warn_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(warn_frame, text="Students are warned at 10, 5, and 1 minute(s) remaining.").pack(
            anchor='w'
        )

        def save():
            try:
                minutes = int(time_var.get())
                if minutes < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Time limit must be a non-negative integer.", parent=dialog)
                return

            self._save_settings(assessment_id, {
                'time_limit_minutes': minutes,
                'auto_submit': int(auto_var.get()),
            })
            messagebox.showinfo("Saved", "Time limit settings saved successfully.", parent=dialog)
            dialog.destroy()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="Save", command=save, style='Accent.TButton').pack(side='left')
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=(10, 0))

    # -------------------------------------------------------------------------
    # Browser lockdown / proctoring
    # -------------------------------------------------------------------------

    def configure_browser_lockdown(self, assessment_id):
        """Lockdown browser and proctoring integration settings"""
        if not self._check_permission('manage_assignments'):
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Browser Lockdown & Proctoring")
        dialog.geometry("500x420")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Browser Lockdown & Proctoring", font=('Helvetica', 14, 'bold')).pack(
            anchor='w', pady=(0, 15)
        )

        settings = self._load_settings(assessment_id)

        # Lockdown browser
        lockdown_frame = ttk.LabelFrame(main_frame, text="Lockdown Browser", padding=10)
        lockdown_frame.pack(fill='x', pady=(0, 10))

        lockdown_var = tk.BooleanVar(value=bool(settings.get('browser_lockdown', 0)))
        ttk.Checkbutton(
            lockdown_frame, text="Require lockdown browser", variable=lockdown_var
        ).pack(anchor='w', pady=5)

        ttk.Label(
            lockdown_frame,
            text="Students must use a lockdown browser to take the exam.\n"
                 "This prevents opening other applications, tabs, or\n"
                 "right-clicking during the assessment.",
            foreground='gray'
        ).pack(anchor='w', pady=(0, 5))

        # Proctoring provider
        proctor_frame = ttk.LabelFrame(main_frame, text="Proctoring Integration", padding=10)
        proctor_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(proctor_frame, text="Proctoring Provider:").grid(row=0, column=0, sticky='w', pady=5)
        provider_var = tk.StringVar(value=settings.get('proctoring_provider', ''))
        provider_combo = ttk.Combobox(
            proctor_frame, textvariable=provider_var,
            values=["", "Respondus Monitor", "Honorlock", "Proctorio", "ExamSoft", "ProctorU"],
            width=25, state='readonly'
        )
        provider_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(
            proctor_frame,
            text="Select a proctoring provider for webcam/screen monitoring.\n"
                 "Leave empty to disable remote proctoring.",
            foreground='gray'
        ).grid(row=1, column=0, columnspan=2, sticky='w', pady=5)

        # Copy-paste and tab-switch detection
        detect_frame = ttk.LabelFrame(main_frame, text="Activity Detection", padding=10)
        detect_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(
            detect_frame,
            text="Copy-paste detection and tab-switch logging are always\n"
                 "enabled when lockdown browser is required. Events are\n"
                 "recorded in integrity logs for review."
        ).pack(anchor='w')

        def save():
            self._save_settings(assessment_id, {
                'browser_lockdown': int(lockdown_var.get()),
                'proctoring_provider': provider_var.get(),
            })
            messagebox.showinfo("Saved", "Lockdown and proctoring settings saved successfully.", parent=dialog)
            dialog.destroy()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="Save", command=save, style='Accent.TButton').pack(side='left')
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=(10, 0))

    # -------------------------------------------------------------------------
    # IP restrictions
    # -------------------------------------------------------------------------

    def configure_ip_restrictions(self, assessment_id):
        """IP whitelist management for on-campus exams"""
        if not self._check_permission('manage_assignments'):
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("IP Restrictions")
        dialog.geometry("500x480")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="IP Restriction Settings", font=('Helvetica', 14, 'bold')).pack(
            anchor='w', pady=(0, 15)
        )

        settings = self._load_settings(assessment_id)

        # Enable/disable
        ip_enabled_var = tk.BooleanVar(value=bool(settings.get('ip_restriction_enabled', 0)))
        ttk.Checkbutton(
            main_frame, text="Enable IP restriction (campus-only exams)", variable=ip_enabled_var
        ).pack(anchor='w', pady=(0, 10))

        # Allowed IPs list
        ip_frame = ttk.LabelFrame(main_frame, text="Allowed IP Ranges / Subnets", padding=10)
        ip_frame.pack(fill='both', expand=True, pady=(0, 10))

        ttk.Label(ip_frame, text="Enter one IP address or CIDR range per line:").pack(anchor='w', pady=(0, 5))

        ip_text = scrolledtext.ScrolledText(ip_frame, height=8, width=50)
        ip_text.pack(fill='both', expand=True)

        # Load existing IPs
        try:
            allowed_ips = json.loads(settings.get('allowed_ips_json', '[]'))
            ip_text.insert('1.0', '\n'.join(allowed_ips))
        except (json.JSONDecodeError, TypeError):
            pass

        ttk.Label(
            main_frame,
            text="Examples: 192.168.1.0/24, 10.0.0.0/8, 172.16.5.100",
            foreground='gray'
        ).pack(anchor='w', pady=(0, 5))

        # Preset buttons
        preset_frame = ttk.Frame(main_frame)
        preset_frame.pack(fill='x', pady=(0, 10))

        def add_preset(cidr):
            current = ip_text.get('1.0', tk.END).strip()
            if current:
                ip_text.insert(tk.END, f"\n{cidr}")
            else:
                ip_text.insert('1.0', cidr)

        ttk.Button(preset_frame, text="Add 10.0.0.0/8", command=lambda: add_preset("10.0.0.0/8")).pack(
            side='left', padx=(0, 5)
        )
        ttk.Button(preset_frame, text="Add 172.16.0.0/12", command=lambda: add_preset("172.16.0.0/12")).pack(
            side='left', padx=(0, 5)
        )
        ttk.Button(preset_frame, text="Add 192.168.0.0/16", command=lambda: add_preset("192.168.0.0/16")).pack(
            side='left'
        )

        def save():
            raw = ip_text.get('1.0', tk.END).strip()
            ip_list = [line.strip() for line in raw.splitlines() if line.strip()]
            self._save_settings(assessment_id, {
                'ip_restriction_enabled': int(ip_enabled_var.get()),
                'allowed_ips_json': json.dumps(ip_list),
            })
            messagebox.showinfo("Saved", "IP restriction settings saved successfully.", parent=dialog)
            dialog.destroy()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_frame, text="Save", command=save, style='Accent.TButton').pack(side='left')
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=(10, 0))

    # -------------------------------------------------------------------------
    # Proctoring dashboard
    # -------------------------------------------------------------------------

    def show_proctoring_dashboard(self):
        """Live monitoring dashboard showing active exams and flagged students"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to view the proctoring dashboard.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text="Proctoring Dashboard", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Active exams section
        active_frame = ttk.LabelFrame(content, text="Active Exams with Integrity Settings", padding=10)
        active_frame.pack(fill='x', pady=(0, 15))

        active_cols = ('assessment', 'lockdown', 'proctoring', 'time_limit', 'students')
        active_tree = ttk.Treeview(active_frame, columns=active_cols, show='headings', height=6)
        active_tree.heading('assessment', text='Assessment')
        active_tree.heading('lockdown', text='Lockdown')
        active_tree.heading('proctoring', text='Proctoring')
        active_tree.heading('time_limit', text='Time Limit')
        active_tree.heading('students', text='Active Students')
        active_tree.column('assessment', width=200)
        active_tree.column('lockdown', width=80, anchor='center')
        active_tree.column('proctoring', width=120, anchor='center')
        active_tree.column('time_limit', width=80, anchor='center')
        active_tree.column('students', width=100, anchor='center')

        active_scroll = ttk.Scrollbar(active_frame, orient='vertical', command=active_tree.yview)
        active_tree.configure(yscrollcommand=active_scroll.set)
        active_tree.pack(side='left', fill='both', expand=True)
        active_scroll.pack(side='right', fill='y')

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_tables(cursor)
            cursor.execute('''
                SELECT a.assessment_name, s.browser_lockdown, s.proctoring_provider,
                       s.time_limit_minutes, s.assessment_id
                FROM exam_integrity_settings s
                JOIN assessments a ON s.assessment_id = a.id
                WHERE a.status = 'Active'
                ORDER BY a.assessment_name
            ''')
            for row in cursor.fetchall():
                # Count active students with recent logs
                cursor.execute(
                    "SELECT COUNT(DISTINCT student_id) FROM exam_integrity_logs "
                    "WHERE assessment_id = ? AND timestamp > datetime('now', '-2 hours')",
                    (row[4],)
                )
                student_count = cursor.fetchone()[0]
                active_tree.insert('', 'end', values=(
                    row[0],
                    "Yes" if row[1] else "No",
                    row[2] or "None",
                    f"{row[3]} min" if row[3] else "None",
                    student_count,
                ))
            conn.close()
        except Exception as e:
            ttk.Label(active_frame, text=f"Error loading data: {e}").pack()

        # Flagged students summary
        flag_frame = ttk.LabelFrame(content, text="Recently Flagged Students", padding=10)
        flag_frame.pack(fill='both', expand=True, pady=(0, 15))

        flag_cols = ('student', 'assessment', 'event_type', 'count', 'last_event')
        flag_tree = ttk.Treeview(flag_frame, columns=flag_cols, show='headings', height=8)
        flag_tree.heading('student', text='Student ID')
        flag_tree.heading('assessment', text='Assessment')
        flag_tree.heading('event_type', text='Event Type')
        flag_tree.heading('count', text='Count')
        flag_tree.heading('last_event', text='Last Event')
        flag_tree.column('student', width=100)
        flag_tree.column('assessment', width=180)
        flag_tree.column('event_type', width=120, anchor='center')
        flag_tree.column('count', width=60, anchor='center')
        flag_tree.column('last_event', width=150)

        flag_scroll = ttk.Scrollbar(flag_frame, orient='vertical', command=flag_tree.yview)
        flag_tree.configure(yscrollcommand=flag_scroll.set)
        flag_tree.pack(side='left', fill='both', expand=True)
        flag_scroll.pack(side='right', fill='y')

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_tables(cursor)
            cursor.execute('''
                SELECT l.student_id, a.assessment_name, l.event_type,
                       COUNT(*) as cnt, MAX(l.timestamp) as last_ts
                FROM exam_integrity_logs l
                LEFT JOIN assessments a ON l.assessment_id = a.id
                WHERE l.timestamp > datetime('now', '-24 hours')
                GROUP BY l.student_id, l.assessment_id, l.event_type
                HAVING cnt >= 2
                ORDER BY cnt DESC, last_ts DESC
            ''')
            for row in cursor.fetchall():
                flag_tree.insert('', 'end', values=(
                    row[0], row[1] or "Unknown", row[2], row[3], row[4]
                ))
            conn.close()
        except Exception as e:
            ttk.Label(flag_frame, text=f"Error loading flagged data: {e}").pack()

        # Navigation
        nav_frame = ttk.Frame(content)
        nav_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(nav_frame, text="Back to Settings", command=self.show_exam_integrity_settings).pack(side='left')
        ttk.Button(nav_frame, text="Refresh", command=self.show_proctoring_dashboard).pack(side='left', padx=(10, 0))

    # -------------------------------------------------------------------------
    # Integrity logs viewer
    # -------------------------------------------------------------------------

    def view_integrity_logs(self):
        """View tab-switch and copy-paste logs"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to view integrity logs.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text="Exam Integrity Logs", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 15))

        # Filters
        filter_frame = ttk.LabelFrame(content, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Event Type:").grid(row=0, column=0, sticky='w', pady=5)
        event_filter_var = tk.StringVar(value="All")
        event_combo = ttk.Combobox(
            filter_frame, textvariable=event_filter_var,
            values=["All", "tab_switch", "copy_paste", "focus_lost", "ip_violation"],
            width=20, state='readonly'
        )
        event_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(filter_frame, text="Student ID:").grid(row=0, column=2, sticky='w', pady=5, padx=(20, 0))
        student_filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=student_filter_var, width=15).grid(
            row=0, column=3, sticky='w', pady=5, padx=(10, 0)
        )

        # Log tree
        log_frame = ttk.Frame(content)
        log_frame.pack(fill='both', expand=True, pady=(0, 10))

        log_cols = ('id', 'assessment', 'student', 'event_type', 'details', 'timestamp')
        log_tree = ttk.Treeview(log_frame, columns=log_cols, show='headings', height=15)
        log_tree.heading('id', text='ID')
        log_tree.heading('assessment', text='Assessment')
        log_tree.heading('student', text='Student')
        log_tree.heading('event_type', text='Event Type')
        log_tree.heading('details', text='Details')
        log_tree.heading('timestamp', text='Timestamp')
        log_tree.column('id', width=40, anchor='center')
        log_tree.column('assessment', width=180)
        log_tree.column('student', width=100)
        log_tree.column('event_type', width=100, anchor='center')
        log_tree.column('details', width=200)
        log_tree.column('timestamp', width=150)

        log_scroll = ttk.Scrollbar(log_frame, orient='vertical', command=log_tree.yview)
        log_tree.configure(yscrollcommand=log_scroll.set)
        log_tree.pack(side='left', fill='both', expand=True)
        log_scroll.pack(side='right', fill='y')

        def load_logs():
            for item in log_tree.get_children():
                log_tree.delete(item)

            event_type = event_filter_var.get()
            student_id = student_filter_var.get().strip()

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                self._ensure_tables(cursor)

                query = '''
                    SELECT l.id, a.assessment_name, l.student_id, l.event_type,
                           l.event_data_json, l.timestamp
                    FROM exam_integrity_logs l
                    LEFT JOIN assessments a ON l.assessment_id = a.assessment_id
                    WHERE 1=1
                '''
                params = []

                if event_type != "All":
                    query += " AND l.event_type = ?"
                    params.append(event_type)

                if student_id:
                    query += " AND l.student_id = ?"
                    params.append(student_id)

                query += " ORDER BY l.timestamp DESC LIMIT 500"

                cursor.execute(query, params)
                for row in cursor.fetchall():
                    try:
                        details = json.loads(row[4]) if row[4] else {}
                        detail_str = details.get('description', json.dumps(details)[:80])
                    except (json.JSONDecodeError, TypeError):
                        detail_str = str(row[4])[:80] if row[4] else ""

                    log_tree.insert('', 'end', values=(
                        row[0], row[1] or "Unknown", row[2], row[3], detail_str, row[5]
                    ))
                conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load logs: {e}")

        # Filter button
        ttk.Button(filter_frame, text="Apply Filter", command=load_logs).grid(
            row=0, column=4, padx=(15, 0), pady=5
        )

        # Detail view on double-click
        def on_log_select(event):
            selected = log_tree.selection()
            if not selected:
                return
            values = log_tree.item(selected[0], 'values')
            if not values:
                return

            detail_win = tk.Toplevel(self.root)
            detail_win.title(f"Log Entry #{values[0]}")
            detail_win.geometry("400x300")
            detail_win.transient(self.root)

            text = scrolledtext.ScrolledText(detail_win, wrap=tk.WORD)
            text.pack(fill='both', expand=True, padx=10, pady=10)
            text.insert('1.0', (
                f"Log ID: {values[0]}\n"
                f"Assessment: {values[1]}\n"
                f"Student: {values[2]}\n"
                f"Event Type: {values[3]}\n"
                f"Timestamp: {values[5]}\n\n"
                f"Details:\n{values[4]}"
            ))
            text.configure(state='disabled')

        log_tree.bind('<Double-1>', on_log_select)

        # Navigation
        nav_frame = ttk.Frame(content)
        nav_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(nav_frame, text="Back to Settings", command=self.show_exam_integrity_settings).pack(side='left')
        ttk.Button(nav_frame, text="Refresh", command=load_logs).pack(side='left', padx=(10, 0))

        # Initial load
        load_logs()

    # -------------------------------------------------------------------------
    # Flagged students
    # -------------------------------------------------------------------------

    def show_flagged_students(self):
        """Show students flagged for suspicious behavior"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to view flagged students.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text="Flagged Students", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 15))

        ttk.Label(
            content,
            text="Students with 3 or more integrity events in a single assessment are flagged for review.",
            foreground='gray'
        ).pack(anchor='w', pady=(0, 15))

        # Flagged students tree
        tree_frame = ttk.Frame(content)
        tree_frame.pack(fill='both', expand=True, pady=(0, 10))

        cols = ('student', 'assessment', 'tab_switches', 'copy_pastes', 'focus_lost',
                'ip_violations', 'total', 'last_event')
        tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=15)

        tree.heading('student', text='Student ID')
        tree.heading('assessment', text='Assessment')
        tree.heading('tab_switches', text='Tab Switches')
        tree.heading('copy_pastes', text='Copy/Paste')
        tree.heading('focus_lost', text='Focus Lost')
        tree.heading('ip_violations', text='IP Violations')
        tree.heading('total', text='Total Events')
        tree.heading('last_event', text='Last Event')

        tree.column('student', width=100)
        tree.column('assessment', width=170)
        tree.column('tab_switches', width=85, anchor='center')
        tree.column('copy_pastes', width=80, anchor='center')
        tree.column('focus_lost', width=80, anchor='center')
        tree.column('ip_violations', width=85, anchor='center')
        tree.column('total', width=80, anchor='center')
        tree.column('last_event', width=140)

        tree_scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        tree_scroll.pack(side='right', fill='y')

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_tables(cursor)
            cursor.execute('''
                SELECT l.student_id, a.assessment_name, l.assessment_id,
                       SUM(CASE WHEN l.event_type = 'tab_switch' THEN 1 ELSE 0 END) as tab_sw,
                       SUM(CASE WHEN l.event_type = 'copy_paste' THEN 1 ELSE 0 END) as cp,
                       SUM(CASE WHEN l.event_type = 'focus_lost' THEN 1 ELSE 0 END) as fl,
                       SUM(CASE WHEN l.event_type = 'ip_violation' THEN 1 ELSE 0 END) as ipv,
                       COUNT(*) as total,
                       MAX(l.timestamp) as last_ts
                FROM exam_integrity_logs l
                LEFT JOIN assessments a ON l.assessment_id = a.id
                GROUP BY l.student_id, l.assessment_id
                HAVING total >= 3
                ORDER BY total DESC, last_ts DESC
            ''')
            for row in cursor.fetchall():
                tree.insert('', 'end', values=(
                    row[0], row[1] or f"ID: {row[2]}",
                    row[3], row[4], row[5], row[6], row[7], row[8]
                ))
            conn.close()
        except Exception as e:
            ttk.Label(tree_frame, text=f"Error loading flagged students: {e}").pack()

        # Actions
        action_frame = ttk.LabelFrame(content, text="Actions", padding=10)
        action_frame.pack(fill='x', pady=(0, 10))

        def view_student_logs():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Info", "Select a student to view their logs.")
                return
            values = tree.item(selected[0], 'values')
            # Navigate to logs filtered by student
            self.view_integrity_logs()
            # Pre-fill the student filter if available
            if hasattr(self, '_log_student_filter'):
                self._log_student_filter.set(values[0])

        def dismiss_flag():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Info", "Select a student entry to dismiss.")
                return
            values = tree.item(selected[0], 'values')
            if messagebox.askyesno(
                "Confirm Dismiss",
                f"Dismiss all flags for student {values[0]} on {values[1]}?\n"
                "This will add a 'dismissed' event to the log."
            ):
                try:
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()
                    self._ensure_tables(cursor)
                    # Find the assessment_id
                    cursor.execute(
                        "SELECT id FROM assessments WHERE assessment_name = ?",
                        (values[1],)
                    )
                    result = cursor.fetchone()
                    if result:
                        cursor.execute(
                            "INSERT INTO exam_integrity_logs (assessment_id, student_id, event_type, event_data_json) "
                            "VALUES (?, ?, 'dismissed', ?)",
                            (result[0], values[0], json.dumps({'dismissed_by': 'admin', 'reason': 'manual_review'}))
                        )
                        conn.commit()
                    conn.close()
                    messagebox.showinfo("Done", "Flag dismissed successfully.")
                    self.show_flagged_students()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to dismiss: {e}")

        ttk.Button(action_frame, text="View Student Logs", command=view_student_logs).pack(side='left', padx=(0, 10))
        ttk.Button(action_frame, text="Dismiss Flag", command=dismiss_flag).pack(side='left', padx=(0, 10))

        # Navigation
        nav_frame = ttk.Frame(content)
        nav_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(nav_frame, text="Back to Settings", command=self.show_exam_integrity_settings).pack(side='left')
        ttk.Button(nav_frame, text="Refresh", command=self.show_flagged_students).pack(side='left', padx=(10, 0))

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _load_settings(self, assessment_id):
        """Load integrity settings for an assessment, returning a dict"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_tables(cursor)
            conn.commit()
            cursor.execute(
                "SELECT * FROM exam_integrity_settings WHERE assessment_id = ?",
                (assessment_id,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                col_names = [
                    'id', 'assessment_id', 'randomize_questions', 'randomize_answers',
                    'question_count', 'time_limit_minutes', 'auto_submit', 'browser_lockdown',
                    'proctoring_provider', 'ip_restriction_enabled', 'allowed_ips_json',
                    'created_at', 'updated_at'
                ]
                return dict(zip(col_names, row))
            return {}
        except Exception:
            return {}

    def _save_settings(self, assessment_id, updates):
        """Save or update integrity settings for an assessment"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            self._ensure_tables(cursor)

            # Check if record exists
            cursor.execute(
                "SELECT id FROM exam_integrity_settings WHERE assessment_id = ?",
                (assessment_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing record
                set_clauses = []
                values = []
                for key, value in updates.items():
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
                set_clauses.append("updated_at = datetime('now')")
                values.append(assessment_id)
                cursor.execute(
                    f"UPDATE exam_integrity_settings SET {', '.join(set_clauses)} WHERE assessment_id = ?",
                    values
                )
            else:
                # Insert new record with defaults + updates
                columns = ['assessment_id'] + list(updates.keys())
                placeholders = ['?'] * len(columns)
                values = [assessment_id] + list(updates.values())
                cursor.execute(
                    f"INSERT INTO exam_integrity_settings ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",
                    values
                )

            conn.commit()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
