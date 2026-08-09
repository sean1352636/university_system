"""Methods __init__ through _create_irb_tab."""

from .. import research_grants_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ResearchGrantsGUI:
    def __init__(self, root, auth, parent_container=None):
        """Initialize the Research & Grants GUI.

        If `parent_container` is supplied, the GUI is hosted inside that frame
        instead of a new Toplevel — used to embed it in the Finance GUI's
        Research & Grants tab.
        """
        self.root = root
        self.auth = auth
        self._is_embedded = parent_container is not None

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("research_grants.errors.login_required"))
            return

        if self._is_embedded:
            self.window = parent_container
        else:
            self.window = tk.Toplevel(root)
            self.window.title(_("research_grants.title"))
            self.window.geometry("1200x800")
            self.window.minsize(1000, 600)

        # Initialize database tables
        self._init_database()

        # Setup UI
        self._create_widgets()

        # Log activity
        log_activity('Accessed research_grants', user=self.auth.current_user.get('username') if self.auth.current_user else None)
        print("✅ Research & Grants Management GUI opened successfully")

    def _init_database(self):
        """Initialize database tables if they don't exist"""
        try:
            from education_system.systems.university.infrastructure.database.schemas.research_integration_schemas import init_research_grants_system_db
            init_research_grants_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.db_init_issue").format(error=e))

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text=_("research_grants.header_title"),
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        # Language change button
        ttk.Button(
            header_frame,
            text=_("research_grants.buttons.change_language").format(lang=get_current_language_name()),
            command=self._on_language_change
        ).pack(side=tk.RIGHT, padx=5)

        user_label = ttk.Label(
            header_frame,
            text=_("research_grants.labels.user").format(username=self.auth.current_user.get('username', 'Unknown')),
            font=('Arial', 10)
        )
        user_label.pack(side=tk.RIGHT, padx=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self._create_projects_tab()
        self._create_grants_tab()
        self._create_publications_tab()
        self._create_milestones_tab()
        self._create_equipment_tab()
        self._create_irb_tab()

        # Close button — only shown in standalone (Toplevel) mode; when
        # embedded inside the Finance GUI, the parent owns navigation.
        if not self._is_embedded:
            ttk.Button(
                main_frame,
                text=_("common.close"),
                command=self.window.destroy
            ).pack(pady=(10, 0))

    def _create_projects_tab(self):
        """Create Research Projects tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.research_projects"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.create_project"), command=self._create_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("research_grants.buttons.add_team_member"), command=self._add_team_member).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_projects).pack(side=tk.LEFT, padx=5)

        # Projects list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.active_projects"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Title', 'PI', 'Department', 'Type', 'Start Date', 'Budget', 'Status')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Title': _("research_grants.columns.title"),
            'PI': _("research_grants.columns.pi"),
            'Department': _("research_grants.columns.department"),
            'Type': _("research_grants.columns.type"),
            'Start Date': _("research_grants.columns.start_date"),
            'Budget': _("research_grants.columns.budget"),
            'Status': _("research_grants.columns.status")
        }
        self.projects_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.projects_tree.heading('#0', text='')
        self.projects_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.projects_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.projects_tree.column(col, width=50)
            elif col in ['Type', 'Budget', 'Status']:
                self.projects_tree.column(col, width=100)
            elif col == 'Title':
                self.projects_tree.column(col, width=250)
            else:
                self.projects_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.projects_tree.yview)
        self.projects_tree.configure(yscrollcommand=scrollbar.set)

        self.projects_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_projects()

    def _create_grants_tab(self):
        """Create Grant Applications tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.grant_applications"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.submit_application"), command=self._submit_grant).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("research_grants.buttons.update_decision"), command=self._update_grant_decision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_grants).pack(side=tk.LEFT, padx=5)

        # Grants list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.grant_applications"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Grant Name', 'Agency', 'PI', 'Requested', 'Awarded', 'Status', 'Deadline')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Grant Name': _("research_grants.columns.grant_name"),
            'Agency': _("research_grants.columns.agency"),
            'PI': _("research_grants.columns.pi"),
            'Requested': _("research_grants.columns.requested"),
            'Awarded': _("research_grants.columns.awarded"),
            'Status': _("research_grants.columns.status"),
            'Deadline': _("research_grants.columns.deadline")
        }
        self.grants_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.grants_tree.heading('#0', text='')
        self.grants_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.grants_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.grants_tree.column(col, width=50)
            elif col in ['Requested', 'Awarded', 'Status']:
                self.grants_tree.column(col, width=100)
            elif col == 'Grant Name':
                self.grants_tree.column(col, width=220)
            else:
                self.grants_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.grants_tree.yview)
        self.grants_tree.configure(yscrollcommand=scrollbar.set)

        self.grants_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_grants()

    def _create_publications_tab(self):
        """Create Publications tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.publications"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.add_publication"), command=self._add_publication).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_publications).pack(side=tk.LEFT, padx=5)

        # Publications list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.research_publications"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Title', 'Authors', 'Publication Type', 'Journal', 'Year', 'Citations')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Title': _("research_grants.columns.title"),
            'Authors': _("research_grants.columns.authors"),
            'Publication Type': _("research_grants.columns.publication_type"),
            'Journal': _("research_grants.columns.journal"),
            'Year': _("research_grants.columns.year"),
            'Citations': _("research_grants.columns.citations")
        }
        self.publications_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.publications_tree.heading('#0', text='')
        self.publications_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.publications_tree.heading(col, text=column_headers.get(col, col))
            if col in ['ID', 'Year', 'Citations']:
                self.publications_tree.column(col, width=60)
            elif col == 'Title':
                self.publications_tree.column(col, width=300)
            else:
                self.publications_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.publications_tree.yview)
        self.publications_tree.configure(yscrollcommand=scrollbar.set)

        self.publications_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_publications()

    def _create_milestones_tab(self):
        """Create Project Milestones tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.milestones"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.add_milestone"), command=self._add_milestone).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("research_grants.buttons.update_status"), command=self._update_milestone).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_milestones).pack(side=tk.LEFT, padx=5)

        # Milestones list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.project_milestones"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Project', 'Milestone', 'Due Date', 'Completed', 'Status')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Project': _("research_grants.columns.project"),
            'Milestone': _("research_grants.columns.milestone"),
            'Due Date': _("research_grants.columns.due_date"),
            'Completed': _("research_grants.columns.completed"),
            'Status': _("research_grants.columns.status")
        }
        self.milestones_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.milestones_tree.heading('#0', text='')
        self.milestones_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.milestones_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.milestones_tree.column(col, width=50)
            elif col in ['Due Date', 'Completed', 'Status']:
                self.milestones_tree.column(col, width=120)
            else:
                self.milestones_tree.column(col, width=200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.milestones_tree.yview)
        self.milestones_tree.configure(yscrollcommand=scrollbar.set)

        self.milestones_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_milestones()

    def _create_equipment_tab(self):
        """Create Equipment Tracking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.equipment"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.add_equipment"), command=self._add_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_equipment).pack(side=tk.LEFT, padx=5)

        # Equipment list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.research_equipment"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Equipment Name', 'Project', 'Purchase Date', 'Cost', 'Location', 'Status')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Equipment Name': _("research_grants.columns.equipment_name"),
            'Project': _("research_grants.columns.project"),
            'Purchase Date': _("research_grants.columns.purchase_date"),
            'Cost': _("research_grants.columns.cost"),
            'Location': _("research_grants.columns.location"),
            'Status': _("research_grants.columns.status")
        }
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.equipment_tree.heading('#0', text='')
        self.equipment_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.equipment_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.equipment_tree.column(col, width=50)
            elif col in ['Cost', 'Status']:
                self.equipment_tree.column(col, width=100)
            elif col == 'Equipment Name':
                self.equipment_tree.column(col, width=220)
            else:
                self.equipment_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=scrollbar.set)

        self.equipment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_equipment()

    def _create_irb_tab(self):
        """Create IRB/Ethics Reviews tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.irb_ethics"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.submit_irb"), command=self._submit_irb).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("research_grants.buttons.update_decision"), command=self._update_irb_decision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_irb).pack(side=tk.LEFT, padx=5)

        # IRB list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.irb_applications"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Project', 'Protocol Number', 'Submission Date', 'Review Type', 'Decision', 'Status')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Project': _("research_grants.columns.project"),
            'Protocol Number': _("research_grants.columns.protocol_number"),
            'Submission Date': _("research_grants.columns.submission_date"),
            'Review Type': _("research_grants.columns.review_type"),
            'Decision': _("research_grants.columns.decision"),
            'Status': _("research_grants.columns.status")
        }
        self.irb_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.irb_tree.heading('#0', text='')
        self.irb_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.irb_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.irb_tree.column(col, width=50)
            elif col in ['Review Type', 'Decision', 'Status']:
                self.irb_tree.column(col, width=110)
            else:
                self.irb_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.irb_tree.yview)
        self.irb_tree.configure(yscrollcommand=scrollbar.set)

        self.irb_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_irb()
