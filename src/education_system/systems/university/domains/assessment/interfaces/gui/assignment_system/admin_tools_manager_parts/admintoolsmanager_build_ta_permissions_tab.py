"""Methods _build_ta_permissions_tab through _calculate_ta_metrics."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import messagebox
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH

from .. import admin_tools_manager_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsManager:
    def _build_ta_permissions_tab(self, parent):
        """Build the granular module-level permissions tab"""
        # Selector
        selector_frame = ttk.LabelFrame(parent, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.labels.select_ta_and_module', default="Select TA and Module"), padding=10)
        selector_frame.pack(fill='x', padx=10, pady=(10, 5))

        row1 = ttk.Frame(selector_frame)
        row1.pack(fill='x', pady=2)
        ttk.Label(row1, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.labels.ta_assignment_id', default="TA Assignment ID:")).pack(side='left', padx=(0, 5))
        self.perm_ta_id_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.perm_ta_id_var, width=15).pack(side='left', padx=(0, 10))
        ttk.Button(row1, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.buttons.load_ta', default="Load TA"), command=self._load_ta_permissions_info).pack(side='left', padx=5)

        # Info display
        self.perm_info_var = tk.StringVar(value=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.values.enter_a_ta_assignment_id_and_click_load_ta', default="Enter a TA Assignment ID and click 'Load TA'."))
        info_frame = ttk.LabelFrame(parent, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.labels.ta_information', default="TA Information"), padding=10)
        info_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(info_frame, textvariable=self.perm_info_var, wraplength=800).pack(anchor='w')

        # Permission checkboxes
        perm_outer = ttk.LabelFrame(parent, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.labels.module_level_permissions', default="Module-Level Permissions"), padding=10)
        perm_outer.pack(fill='both', expand=True, padx=10, pady=5)

        ttk.Label(perm_outer, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.labels.select_permissions_to_grant_for_this_ta_s_module', default="Select permissions to grant for this TA's module:")).pack(anchor='w', pady=(0, 10))

        self._perm_vars = {}
        for perm_key, perm_label in self.PERMISSION_TYPES:
            var = tk.BooleanVar(value=False)
            self._perm_vars[perm_key] = var
            ttk.Checkbutton(perm_outer, text=perm_label, variable=var).pack(anchor='w', padx=20, pady=2)

        # Current permissions display
        current_frame = ttk.LabelFrame(parent, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.labels.current_permissions', default="Current Permissions"), padding=10)
        current_frame.pack(fill='x', padx=10, pady=5)
        self.current_perms_var = tk.StringVar(value=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.values.load_a_ta_to_see_current_permissions', default="Load a TA to see current permissions."))
        ttk.Label(current_frame, textvariable=self.current_perms_var, wraplength=800).pack(anchor='w')

        # Action buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=(5, 10))
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.buttons.save_permissions', default="Save Permissions"), command=self._save_ta_module_permissions).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.buttons.select_all', default="Select All"), command=lambda: [v.set(True) for v in self._perm_vars.values()]).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.buttons.clear_all', default="Clear All"), command=lambda: [v.set(False) for v in self._perm_vars.values()]).pack(side='left', padx=5)

    def _load_ta_permissions_info(self):
        """Load TA details and current module-level permissions"""
        ta_id_str = self.perm_ta_id_var.get().strip()
        if not ta_id_str:
            messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.validation', default="Validation"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.please_enter_a_ta_assignment_id', default="Please enter a TA Assignment ID."))
            return

        try:
            ta_id = int(ta_id_str)
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ta_assignments WHERE id = ?', (ta_id,))
            ta = cursor.fetchone()
            col_names = [desc[0] for desc in cursor.description]

            if not ta:
                conn.close()
                self.perm_info_var.set(f"No TA assignment found with ID {ta_id}.")
                return

            ta_data = dict(zip(col_names, ta))
            self.perm_info_var.set(
                f"ID: {ta_data['id']}  |  User: {ta_data.get('user_id', '')}  |  "
                f"Module: {ta_data.get('module_code', '')}  |  Role: {ta_data.get('role', '')}")

            # Load existing module-level permissions from ta_permissions table
            # Must match the canonical definition in
            # modules/domain/academics/services/assignments/admin_tools/ta_service.py
            # (granted_by NOT NULL; FK to teaching_assistants;
            # UNIQUE(ta_id, permission_type, module_code)).
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ta_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ta_id INTEGER NOT NULL,
                    permission_type TEXT NOT NULL,
                    module_code TEXT NOT NULL,
                    granted_by TEXT NOT NULL,
                    granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ta_id) REFERENCES teaching_assistants (id),
                    UNIQUE (ta_id, permission_type, module_code)
                )
            ''')
            conn.commit()

            module_code = ta_data.get('module_code', '')
            cursor.execute("SELECT permission_type FROM ta_permissions WHERE ta_id = ? AND module_code = ?",
                          (ta_id, module_code))
            current_perms = {row[0] for row in cursor.fetchall()}
            conn.close()

            for perm_key, var in self._perm_vars.items():
                var.set(perm_key in current_perms)

            if current_perms:
                labels = [lbl for k, lbl in self.PERMISSION_TYPES if k in current_perms]
                self.current_perms_var.set(f"Current: {', '.join(labels)}")
            else:
                self.current_perms_var.set("No module-level permissions currently set.")

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.error', default="Error"), f"Failed to load TA: {e}")

    def _save_ta_module_permissions(self):
        """Save granular module-level permissions"""
        ta_id_str = self.perm_ta_id_var.get().strip()
        if not ta_id_str:
            messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.validation', default="Validation"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.please_enter_a_ta_assignment_id', default="Please enter a TA Assignment ID."))
            return

        try:
            ta_id = int(ta_id_str)
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT module_code FROM ta_assignments WHERE id = ?', (ta_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.not_found', default="Not Found"), f"TA assignment #{ta_id} not found.")
                return

            module_code = row[0]
            selected = [k for k, v in self._perm_vars.items() if v.get()]

            current_user = getattr(self.auth, 'current_user', {})
            granted_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

            # Replace all permissions
            cursor.execute("DELETE FROM ta_permissions WHERE ta_id = ? AND module_code = ?", (ta_id, module_code))
            for perm in selected:
                cursor.execute('''
                    INSERT INTO ta_permissions (ta_id, module_code, permission_type, granted_by)
                    VALUES (?, ?, ?, ?)
                ''', (ta_id, module_code, perm, granted_by))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.success', default="Success"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.module_level_permissions_updated', default="Module-level permissions updated."))
            self._load_ta_permissions_info()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.error', default="Error"), f"Failed to save permissions: {e}")

    def _build_ta_evaluation_tab(self, parent):
        """Build the TA performance evaluation tab"""
        ttk.Label(parent, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.labels.ta_performance_evaluation', default="TA Performance Evaluation"), font=('Arial', 12, 'bold')).pack(anchor='w', padx=10, pady=(10, 5))

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.buttons.refresh', default="Refresh"), command=self._load_ta_evaluations).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.buttons.calculate_metrics', default="Calculate Metrics"), command=self._calculate_ta_metrics).pack(side='left', padx=5)

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        cols = ('TA', 'Module', 'Avg Turnaround (d)', 'Hours/Wk', 'Hours Logged', 'Graded', 'Feedback')
        self.eval_tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        for col in cols:
            self.eval_tree.heading(col, text=col)
            self.eval_tree.column(col, width=110)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.eval_tree.yview)
        self.eval_tree.configure(yscrollcommand=scrollbar.set)
        self.eval_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.eval_status_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.eval_status_var).pack(anchor='w', padx=10, pady=5)

        self._load_ta_evaluations()

    def _load_ta_evaluations(self):
        """Load TA performance data"""
        self.eval_tree.delete(*self.eval_tree.get_children())
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ta.user_id, ta.module_code, COALESCE(ta.hours_per_week, 0),
                       ev.avg_grading_turnaround_days, ev.hours_logged,
                       ev.submissions_graded, ev.feedback_score
                FROM ta_assignments ta
                LEFT JOIN ta_evaluations ev ON ta.user_id = ev.ta_id AND ta.module_code = ev.module_code
                ORDER BY ta.module_code, ta.user_id
            ''')
            rows = cursor.fetchall()
            conn.close()

            for r in rows:
                self.eval_tree.insert('', 'end', values=(
                    r[0], r[1],
                    f"{r[3]:.1f}" if r[3] is not None else "N/A",
                    r[2],
                    f"{r[4]:.1f}" if r[4] is not None else "N/A",
                    r[5] if r[5] is not None else "N/A",
                    f"{r[6]:.1f}" if r[6] is not None else "N/A",
                ))

            self.eval_status_var.set(f"{len(rows)} TAs loaded.")
        except Exception as e:
            self.eval_status_var.set(f"Error: {e}")

    def _calculate_ta_metrics(self):
        """Calculate grading turnaround and submission counts from DB data"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("SELECT user_id, module_code FROM ta_assignments")
            tas = cursor.fetchall()

            if not tas:
                self.eval_status_var.set("No TAs found.")
                conn.close()
                return

            current_user = getattr(self.auth, 'current_user', {})
            evaluator = current_user.get('username', 'system') if isinstance(current_user, dict) else 'system'
            calculated = 0

            for ta_id, mc in tas:
                cursor.execute('''
                    SELECT COUNT(*) FROM assignment_submissions
                    WHERE graded_by = ? AND assignment_id IN
                    (SELECT id FROM assignments WHERE module_code = ?)
                ''', (ta_id, mc))
                graded_count = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT AVG(julianday(sub.graded_date) - julianday(a.due_date))
                    FROM assignment_submissions sub
                    JOIN assignments a ON sub.assignment_id = a.id
                    WHERE sub.graded_by = ? AND a.module_code = ?
                    AND sub.graded_date IS NOT NULL AND a.due_date IS NOT NULL
                ''', (ta_id, mc))
                avg_turn_row = cursor.fetchone()
                avg_turn = round(avg_turn_row[0], 1) if avg_turn_row and avg_turn_row[0] is not None else 0

                cursor.execute("SELECT id FROM ta_evaluations WHERE ta_id = ? AND module_code = ?", (ta_id, mc))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute('''
                        UPDATE ta_evaluations SET avg_grading_turnaround_days = ?,
                        submissions_graded = ?, evaluator_id = ?, evaluated_at = datetime('now')
                        WHERE ta_id = ? AND module_code = ?
                    ''', (avg_turn, graded_count, evaluator, ta_id, mc))
                else:
                    cursor.execute('''
                        INSERT INTO ta_evaluations (ta_id, module_code, avg_grading_turnaround_days,
                        submissions_graded, evaluator_id) VALUES (?, ?, ?, ?, ?)
                    ''', (ta_id, mc, avg_turn, graded_count, evaluator))
                calculated += 1

            conn.commit()
            conn.close()

            self.eval_status_var.set(f"Metrics calculated for {calculated} TAs.")
            self._load_ta_evaluations()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_build_ta_permissions_tab.dialogs.error', default="Error"), f"Failed to calculate metrics: {e}")
