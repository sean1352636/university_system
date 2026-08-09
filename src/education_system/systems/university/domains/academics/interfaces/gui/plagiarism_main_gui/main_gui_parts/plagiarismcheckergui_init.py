"""Methods __init__ through _on_close."""

from .. import main_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class PlagiarismCheckerGUI:
    def __init__(self, parent=None, auth=None):
        # Use provided parent window or create new root
        if parent:
            self.root = parent
            self.launched_from_main = True
        else:
            self.root = tk.Tk()
            self.launched_from_main = False

        # Initialize i18n system
        init_i18n()

        self.root.title(_t("plagiarism.title"))
        self.root.geometry(f"{GuiConfig.MAIN_WINDOW_WIDTH}x{GuiConfig.MAIN_WINDOW_HEIGHT}")

        # Initialize components
        self.checker = None
        self.auth = auth  # Use provided auth or None
        self.task_queue = queue.Queue()
        self._task_after_id = None
        # Stop the after() poll loop with a flag rather than racing after_cancel
        # against a firing timer, which can trigger a Tcl "invalid command
        # name ...process_tasks" background error on teardown.
        self._closing = False

        # Set up styles
        self.setup_styles()

        # Create GUI components
        self.create_menu()
        self.create_main_interface()
        self.create_status_bar()

        # Initialize system
        self.initialize_system()

        # Start periodic task processor
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.process_tasks()

        # Download NLTK data if needed
        download_nltk_data()

    def setup_styles(self):
        """Configure ttk styles"""
        self.style = ttk.Style()

        # Configure notebook style
        self.style.configure('TNotebook', background=GuiConfig.LIGHT_BG)
        self.style.configure('TNotebook.Tab', padding=[GuiConfig.PADDING_MEDIUM, GuiConfig.PADDING_SMALL])

        # Configure button styles
        self.style.configure('Accent.TButton', foreground=GuiConfig.PRIMARY_COLOR)

    def create_menu(self):
        """Create application menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("plagiarism.menu_file"), menu=file_menu)
        file_menu.add_command(label=_t("plagiarism.submit_document"), command=self.show_submit_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=_t("plagiarism.import_documents"), command=self.import_documents)
        file_menu.add_command(label=_t("plagiarism.export_documents"), command=self.export_documents)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("plagiarism.menu_tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("plagiarism.check_document"), command=self.show_check_dialog)
        tools_menu.add_command(label=_t("plagiarism.search_repository"), command=self.show_search_dialog)
        tools_menu.add_command(label=_t("plagiarism.view_my_documents"), command=self.show_my_documents)
        tools_menu.add_command(label=_t("plagiarism.view_results"), command=self.show_view_results)
        tools_menu.add_command(label=_t("plagiarism.advanced_search"), command=self.show_advanced_repository_search)
        tools_menu.add_command(label=_t("plagiarism.bulk_operations"), command=self.show_bulk_operations)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("plagiarism.system_testing"), command=self.show_system_testing)
        tools_menu.add_command(label=_t("plagiarism.generate_reports"), command=self.generate_reports_gui)
        tools_menu.add_command(label=_t("plagiarism.compare_documents"), command=self.show_document_comparison)
        tools_menu.add_command(label=_t("plagiarism.file_converter"), command=self.show_file_converter)
        tools_menu.add_command(label=_t("plagiarism.advanced_search"), command=self.show_advanced_repository_search)
        tools_menu.add_command(label=_t("plagiarism.bulk_operations"), command=self.show_bulk_operations)
        tools_menu.add_command(label=_t("plagiarism.document_workflow"), command=self.show_document_workflow)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("plagiarism.system_testing"), command=self.show_system_testing)
        tools_menu.add_command(label=_t("plagiarism.generate_reports"), command=self.generate_reports_gui)

        repo_menu = tk.Menu(tools_menu, tearoff=0)
        repo_menu.add_command(label=_t("plagiarism.delete_document"), command=self.show_delete_document_dialog)
        repo_menu.add_command(label=_t("plagiarism.check_repository_integrity"), command=self.show_repository_integrity_dialog)
        repo_menu.add_command(label=_t("plagiarism.check_integrity"), command=self.check_repository_integrity_gui)
        repo_menu.add_command(label=_t("plagiarism.backup_restore"), command=self.show_backup_restore)
        tools_menu.add_cascade(label=_t("plagiarism.repository"), menu=repo_menu)
        repo_menu.add_command(label=_t("plagiarism.check_integrity"), command=self.check_repository_integrity_gui)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("plagiarism.statistics"), command=self.show_statistics)
        tools_menu.add_command(label=_t("plagiarism.setup_testing"), command=self.show_setup_testing)

        # Language menu
        language_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=f"\U0001f310 {_t('gui.language')}", menu=language_menu)
        language_menu.add_command(label=_t("gui.change_language"), command=self.change_language)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("plagiarism.menu_help"), menu=help_menu)
        help_menu.add_command(label=_t("plagiarism.about"), command=self.show_about)

        self.create_main_menu_button()

    def change_language(self):
        """Open language selector and refresh UI if language changes"""
        old_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()
        if old_lang != new_lang:
            # Refresh the entire interface with new language
            self.refresh_interface()

    def create_main_menu_button(self):
        """Place a navigation button in the top-right corner"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception as e:
            logger.debug(f"Error checking main_menu_button existence: {e}")

        self.main_menu_button = ttk.Button(
            self.root,
            text=f"\U0001f3e0 {_t('common.return_to_main_menu')}",
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def refresh_interface(self):
        """Refresh the entire interface after language change"""
        # Update window title
        self.root.title(_t("plagiarism.title"))

        # Clear and recreate menu
        self.root.config(menu=None)
        self.create_menu()

        # Clear and recreate main interface
        for widget in self.root.winfo_children():
            if widget != getattr(self, 'main_menu_button', None):
                widget.destroy()

        self.create_main_interface()
        self.create_status_bar()
        self.create_main_menu_button()

    def create_main_interface(self):
        """Create the main interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=GuiConfig.PADDING_MEDIUM, pady=GuiConfig.PADDING_MEDIUM)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Dashboard tab
        self.create_dashboard_tab()

        # Documents tab
        self.create_documents_tab()

        # Results tab
        self.create_results_tab()

        # Settings tab
        self.create_settings_tab()

    def create_dashboard_tab(self):
        """Create dashboard tab"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text=_t("plagiarism.dashboard"))

        # Welcome section
        welcome_frame = ttk.LabelFrame(dashboard_frame, text=_t("plagiarism.welcome"), padding=GuiConfig.PADDING_MEDIUM)
        welcome_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        welcome_label = ttk.Label(
            welcome_frame,
            text=_t("plagiarism.title"),
            font=GuiConfig.HEADER_FONT
        )
        welcome_label.pack()

        subtitle_label = ttk.Label(
            welcome_frame,
            text=_t("plagiarism.subtitle"),
            font=GuiConfig.BODY_FONT
        )
        subtitle_label.pack()

        # Quick actions
        actions_frame = ttk.LabelFrame(dashboard_frame, text=_t("plagiarism.quick_actions"), padding=GuiConfig.PADDING_MEDIUM)
        actions_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Action buttons
        btn_frame = ttk.Frame(actions_frame)
        btn_frame.pack()

        submit_btn = ttk.Button(
            btn_frame,
            text=_t("plagiarism.submit_document"),
            style='Accent.TButton',
            command=self.show_submit_dialog
        )
        submit_btn.pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_MEDIUM))

        check_btn = ttk.Button(
            btn_frame,
            text=_t("plagiarism.check_for_plagiarism"),
            command=self.show_check_dialog
        )
        check_btn.pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_MEDIUM))

        search_btn = ttk.Button(
            btn_frame,
            text=_t("plagiarism.search_repository"),
            command=self.show_search_dialog
        )
        search_btn.pack(side=tk.LEFT)

        # Statistics summary
        self.stats_frame = ttk.LabelFrame(dashboard_frame, text=_t("plagiarism.system_statistics"), padding=GuiConfig.PADDING_MEDIUM)
        self.stats_frame.pack(fill=tk.BOTH, expand=True)

        self.stats_text = scrolledtext.ScrolledText(
            self.stats_frame,
            height=10,
            font=GuiConfig.MONOSPACE_FONT,
            state=tk.DISABLED
        )
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        # Load statistics
        self.load_dashboard_stats()

    def create_documents_tab(self):
        """Create documents tab"""
        documents_frame = ttk.Frame(self.notebook)
        self.documents_tab = documents_frame  # added for tab focusing
        self.notebook.add(documents_frame, text=_t("plagiarism.documents_tab"))

        # Controls frame
        controls_frame = ttk.Frame(documents_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Search controls
        search_frame = ttk.LabelFrame(controls_frame, text=_t("plagiarism.search_documents"), padding=GuiConfig.PADDING_SMALL)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))

        ttk.Label(search_frame, text=_t("plagiarism.title_label")).grid(row=0, column=0, sticky=tk.W, padx=(0, GuiConfig.PADDING_SMALL))
        self.doc_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.doc_search_var, width=30)
        search_entry.grid(row=0, column=1, padx=(0, GuiConfig.PADDING_SMALL))

        search_btn = ttk.Button(search_frame, text=_t("common.search"), command=self.search_documents)
        search_btn.grid(row=0, column=2, padx=(0, GuiConfig.PADDING_SMALL))

        refresh_btn = ttk.Button(search_frame, text=_t("common.refresh"), command=self.load_documents)
        refresh_btn.grid(row=0, column=3)

        # Documents list
        self.documents_frame = ScrollableFrame(documents_frame)
        self.documents_frame.pack(fill=tk.BOTH, expand=True)

        # Load documents
        self.load_documents()

    def create_results_tab(self):
        """Create results tab"""
        results_frame = ttk.Frame(self.notebook)
        self.results_tab = results_frame  # added for tab focusing
        self.notebook.add(results_frame, text=_t("plagiarism.check_results_tab"))

        # Controls
        controls_frame = ttk.Frame(results_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        refresh_results_btn = ttk.Button(
            controls_frame,
            text=_t("plagiarism.refresh_results"),
            command=self.load_results
        )
        refresh_results_btn.pack(side=tk.LEFT)

        # Results list
        self.results_frame = ScrollableFrame(results_frame)
        self.results_frame.pack(fill=tk.BOTH, expand=True)

        # Load results
        self.load_results()

    def create_settings_tab(self):
        """Create settings tab"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text=_t("plagiarism.settings_tab"))

        # Plagiarism detection settings
        detection_frame = ttk.LabelFrame(settings_frame, text=_t("plagiarism.detection_settings"), padding=GuiConfig.PADDING_MEDIUM)
        detection_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Similarity threshold
        ttk.Label(detection_frame, text=_t("plagiarism.similarity_threshold")).grid(row=0, column=0, sticky=tk.W)
        self.threshold_var = tk.DoubleVar(value=0.3)
        threshold_scale = ttk.Scale(
            detection_frame,
            from_=0.1,
            to=0.9,
            variable=self.threshold_var,
            orient=tk.HORIZONTAL,
            length=200
        )
        threshold_scale.grid(row=0, column=1, padx=GuiConfig.PADDING_SMALL)

        self.threshold_label = ttk.Label(detection_frame, text="30%")
        self.threshold_label.grid(row=0, column=2)

        def update_threshold_label(*args):
            self.threshold_label.config(text=f"{int(self.threshold_var.get() * 100)}%")

        self.threshold_var.trace('w', update_threshold_label)

        # System information
        info_frame = ttk.LabelFrame(settings_frame, text=_t("plagiarism.system_information"), padding=GuiConfig.PADDING_MEDIUM)
        info_frame.pack(fill=tk.X)

        self.info_text = scrolledtext.ScrolledText(
            info_frame,
            height=15,
            font=GuiConfig.MONOSPACE_FONT,
            state=tk.DISABLED
        )
        self.info_text.pack(fill=tk.BOTH, expand=True)

        self.load_system_info()

    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = StatusBar(self.root, controller=self)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def initialize_system(self):
        """Initialize the plagiarism checking system"""
        def init_task():
            try:
                self.status_bar.set_status("Initializing system...")
                self.status_bar.show_progress()

                # Initialize checker
                if not PLAGIARISM_BACKEND_AVAILABLE or PlagiarismChecker is None:
                    raise RuntimeError(
                        "Plagiarism detection backend is unavailable. "
                        f"Details: {PLAGIARISM_IMPORT_ERROR}"
                        if PLAGIARISM_IMPORT_ERROR else "Plagiarism module missing."
                    )

                self.checker = PlagiarismChecker()

                # Initialize UserAuth for GUI with default test user
                self.auth = get_authenticated_user_auth()

                self.task_queue.put(('init_complete', None))

            except Exception as e:
                self.task_queue.put(('init_error', str(e)))

        # Run initialization in background thread
        thread = threading.Thread(target=init_task, daemon=True)
        thread.start()

    def _on_close(self):
        """Stop the task poll loop and destroy the window."""
        self._closing = True
        self._task_after_id = None
        self.root.destroy()
