"""Methods show_accommodations through _edit_selected_ta_permissions."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_manager_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})
from education_system.systems.university.domains.academics.interfaces.gui.assignment_system._dialogs import make_toplevel
from education_system.systems.university.domains.academics.interfaces.gui._field_pickers import attach_picker


class AdminToolsManager:
    def show_accommodations(self):
        """Open the Accessibility & Accommodation Tools GUI.

        Accommodations used to be managed here as well, over
        ``student_accommodations``. That made the assignment system a
        second, disconnected place to grant them: the accessibility hub
        already owned accessibility profiles, the request/approval
        workflow, per-exam arrangements and assistive tech, so a student
        could be approved there and still have nothing recorded here (or
        the reverse). The general accommodations now live on that hub's
        "General Accommodations" tab, and this button opens it.
        """
        if not self._check_permission('manage_accommodations'):
            messagebox.showerror(
                _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.access_denied', default="Access Denied"),
                _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.you_do_not_have_permission_to_manage_accommodations', default="You do not have permission to manage accommodations."))
            return

        from education_system.systems.university.domains.academics.interfaces.gui._cross_launchers import (
            open_accessibility_gui,
        )
        open_accessibility_gui(self.root, getattr(self, 'auth', None))


    def show_ta_management(self):
        """Unified TA/co-instructor management with assignments, permissions, and evaluation"""
        if not self._check_permission('manage_tas'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.you_do_not_have_permission_to_manage_ta_assignments', default="You do not have permission to manage TA assignments."))
            return

        self._ensure_ta_evaluation_table()

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.teaching_assistant_management', default="Teaching Assistant Management"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        # Tabbed notebook for TA features
        notebook = ttk.Notebook(content)
        notebook.pack(fill='both', expand=True)

        # ── Tab 1: TA Assignments ──
        assign_frame = ttk.Frame(notebook)
        notebook.add(assign_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.tabs.ta_assignments', default="TA Assignments"))
        self._build_ta_assignments_tab(assign_frame)

        # ── Tab 2: Permissions ──
        perm_frame = ttk.Frame(notebook)
        notebook.add(perm_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.tabs.permissions', default="Permissions"))
        self._build_ta_permissions_tab(perm_frame)

        # ── Tab 3: Performance Evaluation ──
        eval_frame = ttk.Frame(notebook)
        notebook.add(eval_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.tabs.performance_evaluation', default="Performance Evaluation"))
        self._build_ta_evaluation_tab(eval_frame)

    def _ensure_ta_evaluation_table(self):
        """Ensure ta_evaluations table exists"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ta_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ta_id TEXT NOT NULL,
                    module_code TEXT NOT NULL,
                    evaluation_period TEXT,
                    hours_logged REAL DEFAULT 0,
                    avg_grading_turnaround_days REAL DEFAULT 0,
                    submissions_graded INTEGER DEFAULT 0,
                    feedback_score REAL,
                    evaluator_id TEXT,
                    evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _build_ta_assignments_tab(self, parent):
        """Build the TA assignments management tab"""
        # Action buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=(10, 5))

        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.assign_ta', default="Assign TA"), command=lambda: self.assign_ta(None)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.view_workload', default="View Workload"), command=self._view_ta_workload).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.refresh', default="Refresh"), command=self._load_ta_assignments).pack(side='right', padx=5)

        # Filter bar
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=10, pady=(0, 5))

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.module', default="Module:")).pack(side='left', padx=(0, 5))
        self.ta_module_var = tk.StringVar()
        attach_picker(filter_frame, 'module', id_var=self.ta_module_var,
                      width=28).pack(side='left', padx=5)

        ttk.Label(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.labels.role', default="Role:")).pack(side='left', padx=(15, 5))
        self.ta_role_var = tk.StringVar(value=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.values.all', default='all'))
        ttk.Combobox(filter_frame, textvariable=self.ta_role_var,
                     values=['all', 'ta', 'lead_ta', 'grader', 'co_instructor'],
                     state='readonly', width=15).pack(side='left', padx=5)

        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.search', default="Search"), command=self._load_ta_assignments).pack(side='left', padx=15)
        ttk.Button(filter_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.clear', default="Clear"), command=self._clear_ta_filter).pack(side='left', padx=5)

        # TA assignments treeview
        ta_frame = ttk.Frame(parent)
        ta_frame.pack(fill='both', expand=True, padx=10)

        columns = ('ID', 'User', 'Section', 'Module', 'Role', 'Hours/Wk',
                   'Grade', 'Create', 'Analytics', 'Assigned By', 'Date')
        self.ta_tree = ttk.Treeview(ta_frame, columns=columns, show='headings', height=12)

        col_widths = {'ID': 35, 'User': 80, 'Section': 70, 'Module': 75, 'Role': 85,
                      'Hours/Wk': 65, 'Grade': 45, 'Create': 50, 'Analytics': 60,
                      'Assigned By': 90, 'Date': 110}
        for col in columns:
            self.ta_tree.heading(col, text=col)
            self.ta_tree.column(col, width=col_widths.get(col, 70))

        scrollbar = ttk.Scrollbar(ta_frame, orient='vertical', command=self.ta_tree.yview)
        self.ta_tree.configure(yscrollcommand=scrollbar.set)
        self.ta_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.ta_tree.bind('<Double-1>', lambda e: self._on_ta_double_click())

        # Bottom buttons
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill='x', padx=10, pady=(5, 10))
        ttk.Button(bottom_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.edit_permissions', default="Edit Permissions"), command=self._edit_selected_ta_permissions).pack(side='left', padx=5)
        ttk.Button(bottom_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.buttons.remove_assignment', default="Remove Assignment"), command=self._remove_ta_assignment).pack(side='left', padx=5)

        self._load_ta_assignments()

    def _clear_ta_filter(self):
        """Clear TA filter and reload"""
        self.ta_module_var.set('')
        self.ta_role_var.set('all')
        self._load_ta_assignments()

    def _load_ta_assignments(self):
        """Load TA assignments into treeview"""
        for item in self.ta_tree.get_children():
            self.ta_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, user_id, section_id, module_code, role,
                       COALESCE(hours_per_week, 0),
                       can_grade, can_create_assignments, can_view_analytics,
                       assigned_by, assigned_at
                FROM ta_assignments WHERE 1=1
            '''
            params = []

            module_filter = self.ta_module_var.get().strip()
            if module_filter:
                query += ' AND module_code LIKE ?'
                params.append(f'%{module_filter}%')

            role_filter = self.ta_role_var.get()
            if role_filter != 'all':
                query += ' AND role = ?'
                params.append(role_filter)

            query += ' ORDER BY assigned_at DESC LIMIT 200'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                display_row = list(row)
                display_row[6] = 'Yes' if display_row[6] else 'No'
                display_row[7] = 'Yes' if display_row[7] else 'No'
                display_row[8] = 'Yes' if display_row[8] else 'No'
                self.ta_tree.insert('', 'end', values=display_row)

            conn.close()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.error', default="Error"), f"Failed to load TA assignments: {e}")

    def _on_ta_double_click(self):
        """Handle double-click on TA assignment"""
        selection = self.ta_tree.selection()
        if selection:
            values = self.ta_tree.item(selection[0], 'values')
            if values:
                self.configure_ta_permissions(values[0])

    def _edit_selected_ta_permissions(self):
        """Edit permissions for selected TA"""
        selection = self.ta_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_show_accommodations.dialogs.no_ta_assignment_selected', default="No TA assignment selected."))
            return
        values = self.ta_tree.item(selection[0], 'values')
        if values:
            self.configure_ta_permissions(values[0])
