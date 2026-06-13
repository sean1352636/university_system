import tkinter as tk
from tkinter import ttk

try:
    from education_system.university_system.core.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class LayoutManager:
    """Manages the main layout, menu bar, sidebar, status bar, and content area."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Create main menu bar
        self.create_menu_bar()

        # Add return to main menu button at the top
        return_btn = ttk.Button(
            self.root,
            text=_t("common.return_to_main_menu", default="Return to Main Menu"),
            command=self.gui.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Create main frame with sidebar and content area
        self.create_main_layout()

        # Create status bar
        self.create_status_bar()

    def create_menu_bar(self):
        """Create the main menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("common.menu_file", default="File"), menu=file_menu)
        file_menu.add_command(label=_t("docmanager.upload_document", default="Upload Document"), command=self.gui.upload_document_dialog)
        file_menu.add_command(label=_t("docmanager.import_documents", default="Import Documents"), command=self.gui.bulk_import_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=_t("docmanager.export_data", default="Export Data"), command=self.gui.export_data_dialog)
        file_menu.add_command(label=_t("docmanager.backup_system", default="Backup System"), command=self.gui.backup_system)
        file_menu.add_separator()
        file_menu.add_command(label=_t("common.exit", default="Exit"), command=self.root.quit)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("common.menu_edit", default="Edit"), menu=edit_menu)
        edit_menu.add_command(label=_t("docmanager.document_types", default="Document Types"), command=self.gui.manage_document_types)
        edit_menu.add_command(label=_t("docmanager.system_settings", default="System Settings"), command=self.gui.system_settings)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("common.menu_view", default="View"), menu=view_menu)
        view_menu.add_command(label=_t("docmanager.dashboard", default="Dashboard"), command=self.gui.show_dashboard)
        view_menu.add_command(label=_t("docmanager.documents", default="Documents"), command=self.gui.show_documents)
        view_menu.add_command(label=_t("docmanager.reports", default="Reports"), command=self.gui.show_reports)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("common.menu_tools", default="Tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("docmanager.advanced_search", default="Advanced Search"), command=self.gui.advanced_search_dialog)
        tools_menu.add_command(label=_t("docmanager.bulk_operations", default="Bulk Operations"), command=self.gui.bulk_operations_dialog)
        tools_menu.add_command(label=_t("docmanager.workflow_management", default="Workflow Management"), command=self.gui.workflow_management)
        tools_menu.add_command(label=_t("docmanager.notification_center", default="Notification Center"), command=self.gui.notification_center)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("common.menu_help", default="Help"), menu=help_menu)
        help_menu.add_command(label=_t("common.user_guide", default="User Guide"), command=self.gui.show_user_guide)
        help_menu.add_command(label=_t("common.about", default="About"), command=self.gui.show_about)

    def create_main_layout(self):
        """Create the main layout with sidebar and content area"""
        # Create main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True, padx=10, pady=5)

        # Create scrollable sidebar
        sidebar_container = ttk.Frame(main_container, width=250)
        sidebar_container.pack(side='left', fill='y', padx=(0, 10))
        sidebar_container.pack_propagate(False)

        # Canvas + scrollbar for sidebar
        self.gui.sidebar_canvas = tk.Canvas(sidebar_container, highlightthickness=0, bg='#f0f0f0', width=230)
        self.gui.sidebar_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=self.gui.sidebar_canvas.yview)
        self.gui.sidebar = ttk.Frame(self.gui.sidebar_canvas)

        # Put sidebar frame inside canvas
        self.gui.sidebar_window = self.gui.sidebar_canvas.create_window((0, 0), window=self.gui.sidebar, anchor="nw")

        # Wire up scrolling
        self.gui.sidebar_canvas.configure(yscrollcommand=self.gui.sidebar_scrollbar.set)
        self.gui.sidebar_canvas.pack(side='left', fill='both', expand=True)
        self.gui.sidebar_scrollbar.pack(side='right', fill='y')

        # Keep sidebar width in sync with canvas width
        def _on_sidebar_canvas_configure(event):
            self.gui.sidebar_canvas.itemconfig(self.gui.sidebar_window, width=event.width)
        self.gui.sidebar_canvas.bind("<Configure>", _on_sidebar_canvas_configure)

        # Update scrollregion whenever sidebar content changes
        self.gui.sidebar.bind(
            "<Configure>",
            lambda e: self.gui.sidebar_canvas.configure(scrollregion=self.gui.sidebar_canvas.bbox("all"))
        )

        # Bind mouse wheel scrolling for sidebar
        self._bind_sidebar_scroll_events()

        # Create scrollable content area
        content_container = ttk.Frame(main_container)
        content_container.pack(side='right', fill='both', expand=True)

        # Create canvas and scrollbar for content area
        self.gui.content_canvas = tk.Canvas(content_container, highlightthickness=0)
        content_scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.gui.content_canvas.yview)
        self.gui.content_area = ttk.Frame(self.gui.content_canvas)

        self.gui.content_area.bind(
            "<Configure>",
            lambda e: self.gui.content_canvas.configure(scrollregion=self.gui.content_canvas.bbox("all"))
        )

        self.gui.content_canvas.create_window((0, 0), window=self.gui.content_area, anchor="nw")
        self.gui.content_canvas.configure(yscrollcommand=content_scrollbar.set)

        self.gui.content_canvas.pack(side="left", fill="both", expand=True)
        content_scrollbar.pack(side="right", fill="y")

        # Create sidebar navigation
        self.create_sidebar()

        # Show dashboard by default
        self.gui.show_dashboard()

    def _bind_sidebar_scroll_events(self):
        """Bind mouse wheel and keys to sidebar scrolling"""
        def _on_mousewheel(event):
            # Only scroll if bar is visible (i.e., content taller than viewport)
            if self.gui.sidebar_scrollbar.winfo_viewable():
                if event.delta:  # Windows
                    self.gui.sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                else:            # Linux
                    if event.num == 4:
                        self.gui.sidebar_canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        self.gui.sidebar_canvas.yview_scroll(1, "units")

        def _on_keypress(event):
            if self.gui.sidebar_scrollbar.winfo_viewable():
                if event.keysym == 'Up':
                    self.gui.sidebar_canvas.yview_scroll(-1, "units")
                elif event.keysym == 'Down':
                    self.gui.sidebar_canvas.yview_scroll(1, "units")
                elif event.keysym == 'Page_Up':
                    self.gui.sidebar_canvas.yview_scroll(-10, "units")
                elif event.keysym == 'Page_Down':
                    self.gui.sidebar_canvas.yview_scroll(10, "units")

        # Bind to sidebar and its children
        self.gui.sidebar_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
        self.gui.sidebar_canvas.bind("<Button-4>", _on_mousewheel)    # Linux
        self.gui.sidebar_canvas.bind("<Button-5>", _on_mousewheel)    # Linux
        self.gui.sidebar_canvas.bind("<KeyPress>", _on_keypress)
        self.gui.sidebar_canvas.focus_set()

    def create_sidebar(self):
        """Create the navigation sidebar with all features"""
        # Title
        title_label = ttk.Label(self.gui.sidebar, text=_t("docmanager.sidebar_title", default="Document Management"), font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # User info
        user_frame = ttk.LabelFrame(self.gui.sidebar, text=_t("docmanager.current_user", default="Current User"), padding=10)
        user_frame.pack(fill='x', pady=5)

        user_name = self.gui.current_user.get('username', 'Unknown') if self.gui.current_user else 'Unknown'
        user_role = self.gui.current_user.get('role', 'user') if self.gui.current_user else 'user'

        ttk.Label(user_frame, text=f"{_t('docmanager.user', default='User')}: {user_name}").pack(anchor='w')
        ttk.Label(user_frame, text=f"{_t('docmanager.role', default='Role')}: {user_role.title()}").pack(anchor='w')

        # Navigation buttons - Updated with all features
        nav_frame = ttk.LabelFrame(self.gui.sidebar, text=_t("docmanager.navigation", default="Navigation"), padding=10)
        nav_frame.pack(fill='x', pady=5)

        nav_buttons = [
            (_t("docmanager.dashboard", default="Dashboard"), self.gui.show_dashboard),
            (_t("docmanager.documents", default="Documents"), self.gui.show_documents),
            (_t("docmanager.reports", default="Reports"), self.gui.show_reports),
            (_t("docmanager.workflows", default="Workflows"), self.gui.workflow_management),
            (_t("docmanager.search", default="Search"), self.gui.advanced_search_dialog),
            (_t("docmanager.ocr", default="OCR"), self.gui.ocr_integration_menu),
            (_t("common.return_to_main_menu", default="Return to Main Menu"), self.gui.return_to_main_menu)
        ]

        for text, command in nav_buttons:
            btn = ttk.Button(nav_frame, text=text, command=command, width=20)
            btn.pack(fill='x', pady=2)

        # Quick actions - Updated
        actions_frame = ttk.LabelFrame(self.gui.sidebar, text=_t("docmanager.quick_actions", default="Quick Actions"), padding=10)
        actions_frame.pack(fill='x', pady=5)

        action_buttons = [
            (_t("docmanager.upload_document", default="Upload Document"), self.gui.upload_document_dialog),
            (_t("docmanager.bulk_operations", default="Bulk Operations"), self.gui.bulk_operations_dialog),
            (_t("docmanager.process_workflow", default="Process Workflow"), self.gui.process_workflow_step),
            (_t("docmanager.generate_report", default="Generate Report"), self.gui.generate_report_dialog),
            (_t("common.return_to_main_menu", default="Return to Main Menu"), self.gui.return_to_main_menu)
        ]

        for text, command in action_buttons:
            btn = ttk.Button(actions_frame, text=text, command=command, width=20)
            btn.pack(fill='x', pady=2)

        # Force scroll region update after all content is added
        self.gui.sidebar.update_idletasks()
        self.gui.sidebar_canvas.configure(scrollregion=self.gui.sidebar_canvas.bbox("all"))

        # Ensure canvas shows scrollbar when needed
        self.gui.sidebar_canvas.update_idletasks()

    def create_status_bar(self):
        """Create the status bar"""
        self.gui.status_var = tk.StringVar()
        self.gui.status_var.set(_t("common.ready", default="Ready"))

        status_bar = ttk.Label(self.root, textvariable=self.gui.status_var, relief='sunken', anchor='w')
        status_bar.pack(side='bottom', fill='x')

    def clear_content_area(self):
        """Clear the content area"""
        for widget in self.gui.content_area.winfo_children():
            widget.destroy()
