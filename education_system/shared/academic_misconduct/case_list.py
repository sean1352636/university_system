"""Case list view and tree operations for the Academic Misconduct Panel."""

from education_system.shared.academic_misconduct._imports import tk, ttk, _t


class MisconductCaseListMixin:
    """Mixin providing the case list view and tree operations."""

    def create_cases_view(self):
        """Create the cases view with unified layout."""
        cases_frame = tk.Frame(self.main_content_frame, bg=self.colors['light'])
        self.views['cases'] = cases_frame

        # Main container
        container = tk.Frame(cases_frame, bg=self.colors['light'])
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title and actions bar
        title_bar = tk.Frame(container, bg=self.colors['light'])
        title_bar.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            title_bar,
            text=_t("misconduct.sections.case_management"),
            font=('Segoe UI', 18, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['light']
        ).pack(side=tk.LEFT)

        # Action buttons on right
        actions_frame = tk.Frame(title_bar, bg=self.colors['light'])
        actions_frame.pack(side=tk.RIGHT)

        self.create_button(actions_frame, "➕ New Case", self.new_case, 'primary').pack(side=tk.LEFT, padx=5)
        self.create_button(actions_frame, "🔄 Refresh", lambda: self.refresh_all_data(), 'secondary').pack(side=tk.LEFT, padx=5)

        # Search and filter bar
        search_filter_frame = tk.Frame(container, bg=self.colors['white'], relief='solid', bd=1)
        search_filter_frame.pack(fill=tk.X, pady=(0, 15))

        search_inner = tk.Frame(search_filter_frame, bg=self.colors['white'])
        search_inner.pack(fill=tk.X, padx=15, pady=12)

        # Search box
        search_container = tk.Frame(search_inner, bg=self.colors['white'])
        search_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))

        tk.Label(
            search_container,
            text=_t("misconduct.btn.search"),
            font=('Segoe UI', 12),
            fg=self.colors['text_muted'],
            bg=self.colors['white']
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_cases)

        search_entry = tk.Entry(
            search_container,
            textvariable=self.search_var,
            font=('Segoe UI', 10),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            insertbackground=self.colors['text_dark'],
            relief='flat',
            bd=0
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=5)
        search_placeholder = "Search by case ID, student name, or violation type..."
        search_entry.insert(0, search_placeholder)
        search_entry.bind('<FocusIn>', lambda e: search_entry.delete(0, tk.END) if search_entry.get() == search_placeholder else None)
        search_entry.bind('<FocusOut>', lambda e: search_entry.insert(0, search_placeholder) if not search_entry.get() else None)

        # Filter dropdown
        tk.Label(
            search_inner,
            text=_t("misconduct.labels.status"),
            font=('Segoe UI', 9),
            fg=self.colors['text_muted'],
            bg=self.colors['white']
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.filter_var = tk.StringVar(value="All")
        filter_dropdown = ttk.Combobox(
            search_inner,
            textvariable=self.filter_var,
            values=["All", "Under Review", "Pending Hearing", "Resolved"],
            state='readonly',
            width=15,
            font=('Segoe UI', 9)
        )
        filter_dropdown.pack(side=tk.LEFT, padx=(0, 10))
        filter_dropdown.bind('<<ComboboxSelected>>', self.filter_cases)

        # Severity filter
        tk.Label(
            search_inner,
            text=_t("misconduct.labels.severity"),
            font=('Segoe UI', 9),
            fg=self.colors['text_muted'],
            bg=self.colors['white']
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.severity_filter_var = tk.StringVar(value="All")
        severity_dropdown = ttk.Combobox(
            search_inner,
            textvariable=self.severity_filter_var,
            values=["All", "Low", "Medium", "High", "Critical"],
            state='readonly',
            width=12,
            font=('Segoe UI', 9)
        )
        severity_dropdown.pack(side=tk.LEFT)
        severity_dropdown.bind('<<ComboboxSelected>>', self.filter_cases)

        # Cases table
        table_frame = tk.Frame(container, bg=self.colors['white'], relief='solid', bd=1)
        table_frame.pack(fill=tk.X, pady=(0, 0))

        # Create treeview with more columns
        columns = ('case_id', 'student', 'violation', 'status', 'severity', 'date')
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='headings',
            style="Custom.Treeview",
            selectmode='browse',
            height=10
        )

        self.tree.heading('case_id', text=_t('misconduct.columns.case_id'))
        self.tree.heading('student', text=_t('misconduct.columns.student_name'))
        self.tree.heading('violation', text=_t('misconduct.columns.violation_type'))
        self.tree.heading('status', text=_t('misconduct.columns.status'))
        self.tree.heading('severity', text=_t('misconduct.columns.severity'))
        self.tree.heading('date', text=_t('misconduct.columns.date_filed'))

        self.tree.column('case_id', width=120, minwidth=100)
        self.tree.column('student', width=180, minwidth=150)
        self.tree.column('violation', width=200, minwidth=150)
        self.tree.column('status', width=150, minwidth=120)
        self.tree.column('severity', width=100, minwidth=80)
        self.tree.column('date', width=120, minwidth=100)

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bind double-click to view details
        self.tree.bind('<Double-1>', lambda e: self.view_case_details())
        self.tree.bind('<<TreeviewSelect>>', self.on_case_select)

        # Action buttons below table
        action_bar = tk.Frame(container, bg=self.colors['light'])
        action_bar.pack(fill=tk.X, pady=(15, 0))

        tk.Label(
            action_bar,
            text=_t("misconduct.labels.double_click_case"),
            font=('Segoe UI', 9, 'italic'),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(side=tk.LEFT)

        action_buttons = tk.Frame(action_bar, bg=self.colors['light'])
        action_buttons.pack(side=tk.RIGHT)

        self.create_button(action_buttons, "👁 View Details", self.view_case_details, 'info').pack(side=tk.LEFT, padx=5)
        self.create_button(action_buttons, "✏ Update Case", self.update_case, 'warning').pack(side=tk.LEFT, padx=5)
        self.create_button(action_buttons, "🗑 Delete", self.delete_case, 'danger').pack(side=tk.LEFT, padx=5)
        self.create_button(action_buttons, "📧 Send Email", self.notify_student, 'secondary').pack(side=tk.LEFT, padx=5)
        self.create_button(action_buttons, "⚖ Schedule Hearing", self.schedule_hearing, 'secondary').pack(side=tk.LEFT, padx=5)

        # Populate the tree
        self.populate_tree()

    def create_case_list(self, parent):
        """Create the case list panel."""
        # Header
        header_frame = tk.Frame(parent, bg=self.colors['primary'], height=50)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text=_t("misconduct.case_list.title", "📋 Case Registry"),
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['primary']
        ).pack(side=tk.LEFT, padx=15, pady=10)

        # Search frame
        search_frame = tk.Frame(parent, bg=self.colors['white'], pady=12)
        search_frame.pack(fill=tk.X, padx=15)

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_cases)

        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=('Segoe UI', 10),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            insertbackground=self.colors['text_dark'],
            relief='solid',
            bd=1,
            highlightthickness=0
        )
        search_entry.pack(fill=tk.X, ipady=6)
        search_placeholder = _t("misconduct.case_list.search_placeholder", "🔍 Search cases...")
        search_entry.insert(0, search_placeholder)
        search_entry.bind('<FocusIn>', lambda e: search_entry.delete(0, tk.END) if search_entry.get() == search_placeholder else None)
        search_entry.bind('<FocusOut>', lambda e: search_entry.insert(0, search_placeholder) if not search_entry.get() else None)

        # Filter buttons
        filter_frame = tk.Frame(parent, bg=self.colors['white'])
        filter_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        self.filter_var = tk.StringVar(value=_t("misconduct.filters.all", "All"))
        filters = [
            _t("misconduct.filters.all", "All"),
            _t("misconduct.filters.under_review", "Under Review"),
            _t("misconduct.filters.pending_hearing", "Pending Hearing"),
            _t("misconduct.filters.resolved", "Resolved")
        ]

        for f in filters:
            btn = tk.Radiobutton(
                filter_frame,
                text=f,
                variable=self.filter_var,
                value=f,
                font=('Segoe UI', 9),
                fg=self.colors['text_dark'],
                bg=self.colors['light'],
                selectcolor=self.colors['secondary'],
                activebackground=self.colors['light'],
                activeforeground=self.colors['white'],
                indicatoron=False,
                padx=10,
                pady=5,
                relief='flat',
                highlightthickness=0,
                command=self.filter_cases
            )
            btn.pack(side=tk.LEFT, padx=2)

        # Action buttons - CRUD operations (pack FIRST so they're visible)
        btn_frame = tk.Frame(parent, bg=self.colors['white'])
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=12)

        self.create_button(btn_frame, _t("misconduct.buttons.create", "➕ Create"), self.new_case, 'primary').pack(side=tk.LEFT, padx=(0, 5))
        self.create_button(btn_frame, _t("misconduct.buttons.view", "👁 View"), self.view_case_details, 'info').pack(side=tk.LEFT, padx=(0, 5))
        self.create_button(btn_frame, _t("misconduct.buttons.update", "✏ Update"), self.update_case, 'warning').pack(side=tk.LEFT, padx=(0, 5))
        self.create_button(btn_frame, _t("misconduct.buttons.delete", "🗑 Delete"), self.delete_case, 'danger').pack(side=tk.LEFT, padx=(0, 5))
        self.create_button(btn_frame, _t("misconduct.buttons.refresh", "🔄 Refresh"), self.refresh_dashboard, 'success').pack(side=tk.LEFT)

        # Case list
        list_frame = tk.Frame(parent, bg=self.colors['white'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))

        # Treeview
        columns = ('id', 'student', 'type', 'status')
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            style="Custom.Treeview",
            selectmode='browse'
        )

        self.tree.heading('id', text=_t("misconduct.columns.case_id", "Case ID"))
        self.tree.heading('student', text=_t("misconduct.columns.student", "Student"))
        self.tree.heading('type', text=_t("misconduct.columns.type", "Type"))
        self.tree.heading('status', text=_t("misconduct.columns.status", "Status"))

        self.tree.column('id', width=100, minwidth=80)
        self.tree.column('student', width=120, minwidth=100)
        self.tree.column('type', width=130, minwidth=100)
        self.tree.column('status', width=100, minwidth=80)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<<TreeviewSelect>>', self.on_case_select)

        # Populate tree
        self.populate_tree()

    def populate_tree(self):
        """Populate the treeview with case data."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        filter_status = self.filter_var.get()
        filter_severity = self.severity_filter_var.get() if hasattr(self, 'severity_filter_var') else "All"
        search_text = self.search_var.get().lower()

        # Handle placeholders
        if "search" in search_text.lower():
            search_text = ""

        for case in self.cases:
            # Apply status filter
            if filter_status != "All" and case['status'] != filter_status:
                continue

            # Apply severity filter
            if filter_severity != "All" and case['severity'] != filter_severity:
                continue

            # Apply search filter (search in multiple fields)
            if search_text:
                searchable_text = (
                    case['id'].lower() + " " +
                    case['student'].lower() + " " +
                    case['type'].lower()
                )
                if search_text not in searchable_text:
                    continue

            self.tree.insert('', tk.END, values=(
                case['id'],
                case['student'],
                case['type'],
                case['status'],
                case['severity'],
                case['date_filed']
            ))

    def filter_cases(self, *args):
        """Filter cases based on search and filter criteria."""
        if not hasattr(self, 'tree') or self.tree is None:
            return
        self.populate_tree()

    def on_case_select(self, event):
        """Handle case selection."""
        selected = self.tree.selection()
        if selected:
            item = self.tree.item(selected[0])
            case_id = item['values'][0]

            for case in self.cases:
                if case['id'] == case_id:
                    self.selected_case = case
                    # Note: Case details are shown when user clicks "View Details" button
                    # We just store the selected case here for later use
                    break
