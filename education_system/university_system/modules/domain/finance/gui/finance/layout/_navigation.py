"""Navigation and tab management mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.shared.utils.i18n import get_text as _


class NavigationMixin:
    """Main interface creation, navigation setup, and tab switching."""

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Initialize colors if not already defined
        if not hasattr(self, 'colors'):
            self.colors = {
                'primary': '#2c3e50',
                'secondary': '#3498db',
                'success': '#27ae60',
                'warning': '#f39c12',
                'danger': '#e74c3c',
                'light': '#ecf0f1',
                'dark': '#2c3e50',
                'info': '#17a2b8'
            }

        # Main header
        header_frame = tk.Frame(self.root, bg=self.colors['primary'], height=80)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text=_("finance_gui.header.title"),
            font=('Arial', 20, 'bold'),
            fg='white',
            bg=self.colors['primary']
        )
        title_label.pack(side=tk.LEFT, expand=True, padx=20)

        # Return to Main Menu button
        return_btn = tk.Button(
            header_frame,
            text=_("finance_gui.header.return_to_main"),
            command=self.gui.return_to_main_menu,
            font=('Arial', 10, 'bold'),
            bg='white',
            fg=self.colors['primary'],
            padx=15,
            pady=5
        )
        return_btn.pack(side=tk.RIGHT, padx=20)

        # Main content area with button navigation
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Create scrollable sidebar navigation
        sidebar_container = tk.Frame(self.main_container, width=250)
        sidebar_container.pack(side='left', fill='y', padx=(0, 10))
        sidebar_container.pack_propagate(False)

        # Canvas + scrollbar for sidebar
        self.nav_canvas = tk.Canvas(sidebar_container, bg=self.colors['primary'], highlightthickness=0, width=230)
        nav_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=self.nav_canvas.yview)
        self.nav_frame = tk.Frame(self.nav_canvas, bg=self.colors['primary'])

        self.nav_frame.bind(
            "<Configure>",
            lambda e: self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))
        )

        # Put navigation frame inside canvas
        self.nav_window = self.nav_canvas.create_window((0, 0), window=self.nav_frame, anchor="nw")

        # Wire up scrolling
        self.nav_canvas.configure(yscrollcommand=nav_scrollbar.set)
        self.nav_canvas.pack(side='left', fill='both', expand=True)
        nav_scrollbar.pack(side='right', fill='y')

        # Keep navigation width in sync with canvas width
        def _on_nav_canvas_configure(event):
            self.nav_canvas.itemconfig(self.nav_window, width=event.width)
        self.nav_canvas.bind("<Configure>", _on_nav_canvas_configure)

        # Bind mouse wheel scrolling for navigation
        self._bind_nav_scroll_events()

        # Content frame where different tabs will be shown
        self.content_frame = tk.Frame(self.main_container, bg='white')
        self.content_frame.pack(side='right', fill='both', expand=True)

        # Track current tab and tab frames
        self.current_tab = None
        self.tab_frames = {}

        # Create navigation buttons and tab frames
        self.setup_navigation()

        # Create all tab content
        self.create_dashboard_tab()
        self.create_core_finance_tab()
        self.create_payments_tab()
        self.create_payment_plans_tab()
        self.create_fees_tab()
        self.create_late_fees_tab()
        self.create_students_tab()
        self.create_currency_tab()
        self.create_analytics_tab()
        # self.create_scholarships_tab()  # Removed - integrated into Financial Aid tab
        self.create_reports_tab()
        self.create_revenue_source_tab()
        self.create_collections_tab()
        self.create_aid_tab()
        self.create_budget_tab()
        self.create_forecasting_tab()
        self.create_research_grants_tab()
        self.create_admin_tab()
        self.create_settings_tab()

        # Show default tab
        self.show_tab('dashboard')

        # Status bar
        self.create_status_bar()


    def setup_navigation(self):
        """Setup navigation buttons for different sections with role-based access"""
        is_admin = self.gui.is_admin()
        is_staff = self.gui.is_staff()
        is_student = self.gui.is_student()

        # Define all navigation buttons
        all_nav_buttons = [
            (_("finance_gui.nav.dashboard"), "dashboard", "all"),  # Available to all
            (_("finance_gui.nav.my_finances"), "my_finances", "student"),  # Students only - view own finances
            (_("finance_gui.nav.core_finance"), "core_finance", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.payments"), "payments", "all"),  # All can view payments
            (_("finance_gui.nav.fees"), "fees", "all"),  # All can view fees
            (_("finance_gui.nav.students"), "students", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.reports"), "reports", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.revenue_source"), "revenue_source", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.collections"), "collections", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.aid"), "aid", "all"),  # All can view aid (students view their own)
            (_("finance_gui.nav.budget"), "budget", "admin"),  # Admin only
            (_("finance_gui.nav.forecasting"), "forecasting", "admin"),  # Admin only
            (_("finance_gui.nav.research_grants"), "research_grants", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.admin"), "admin", "admin"),  # Admin only
            (_("finance_gui.nav.settings"), "settings", "admin_staff")  # Admin and Staff only
        ]

        # Filter buttons based on role
        nav_buttons = []
        for text, tab_id, access_level in all_nav_buttons:
            if access_level == "all":
                nav_buttons.append((text, tab_id))
            elif access_level == "admin" and is_admin:
                nav_buttons.append((text, tab_id))
            elif access_level == "admin_staff" and (is_admin or is_staff):
                nav_buttons.append((text, tab_id))
            elif access_level == "student" and is_student:
                nav_buttons.append((text, tab_id))

        # Create buttons
        for text, tab_id in nav_buttons:
            btn = tk.Button(
                self.nav_frame,
                text=text,
                command=lambda t=tab_id: self.show_tab(t),
                bg=self.colors['secondary'],
                fg='white',
                font=('Arial', 10, 'bold'),
                relief='flat',
                padx=10,
                pady=8
            )
            btn.pack(side='top', padx=5, pady=2, fill='x')

        # Add separator
        separator = tk.Frame(self.nav_frame, height=2, bg=self.colors['dark'])
        separator.pack(side='top', fill='x', padx=5, pady=10)

        # Force scroll region update after all content is added
        self.nav_frame.update_idletasks()
        self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))

        # Ensure canvas shows scrollbar when needed
        self.nav_canvas.update_idletasks()


    def _bind_nav_scroll_events(self):
        """Bind mouse wheel and keys to navigation scrolling"""
        def _on_mousewheel(event):
            # Only scroll if bar is visible (i.e., content taller than viewport)
            if hasattr(self, 'nav_canvas') and self.nav_canvas.winfo_exists():
                try:
                    scrollbar = None
                    for child in self.nav_canvas.master.winfo_children():
                        if isinstance(child, ttk.Scrollbar):
                            scrollbar = child
                            break
                    if scrollbar and scrollbar.winfo_viewable():
                        if event.delta:  # Windows
                            self.nav_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                        else:            # Linux
                            if event.num == 4:
                                self.nav_canvas.yview_scroll(-1, "units")
                            elif event.num == 5:
                                self.nav_canvas.yview_scroll(1, "units")
                except Exception as e:
                    # Scroll event failed, silently ignore
                    print(f"Debug: Mousewheel scroll failed: {e}")

        def _on_keypress(event):
            if hasattr(self, 'nav_canvas') and self.nav_canvas.winfo_exists():
                try:
                    scrollbar = None
                    for child in self.nav_canvas.master.winfo_children():
                        if isinstance(child, ttk.Scrollbar):
                            scrollbar = child
                            break
                    if scrollbar and scrollbar.winfo_viewable():
                        if event.keysym == 'Up':
                            self.nav_canvas.yview_scroll(-1, "units")
                        elif event.keysym == 'Down':
                            self.nav_canvas.yview_scroll(1, "units")
                        elif event.keysym == 'Page_Up':
                            self.nav_canvas.yview_scroll(-10, "units")
                        elif event.keysym == 'Page_Down':
                            self.nav_canvas.yview_scroll(10, "units")
                except Exception as e:
                    # Key scroll event failed, silently ignore
                    print(f"Debug: Keypress scroll failed: {e}")

        # Bind to navigation canvas
        try:
            self.nav_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
            self.nav_canvas.bind("<Button-4>", _on_mousewheel)    # Linux
            self.nav_canvas.bind("<Button-5>", _on_mousewheel)    # Linux
            self.nav_canvas.bind("<KeyPress>", _on_keypress)
            self.nav_canvas.focus_set()
        except Exception as e:
            # Event binding failed, navigation canvas may not be ready
            print(f"Debug: Canvas event binding failed: {e}")


    # Tab creation methods - stub implementations
    def _create_placeholder_tab(self, tab_id, title):
        """Create a placeholder tab with basic structure when main tab creation fails"""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames[tab_id] = frame

        # Add title
        title_label = tk.Label(frame, text=title, font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=20)

        # Add informative message
        msg_frame = tk.Frame(frame, bg='white')
        msg_frame.pack(pady=20, padx=40)

        tk.Label(msg_frame, text=_("finance_gui.placeholder.loading_issue"),
                font=('Arial', 14, 'bold'), bg='white', fg='#e74c3c').pack(pady=5)

        tk.Label(msg_frame, text=_("finance_gui.placeholder.not_initialized"),
                font=('Arial', 11), bg='white', fg='gray').pack(pady=2)

        tk.Label(msg_frame, text=_("finance_gui.placeholder.may_be_due_to"),
                font=('Arial', 10), bg='white', fg='gray').pack(anchor='w', pady=(10, 2))

        reasons = [
            _("finance_gui.placeholder.reason_missing_tables"),
            _("finance_gui.placeholder.reason_module_not_loaded"),
            _("finance_gui.placeholder.reason_init_error")
        ]
        for reason in reasons:
            tk.Label(msg_frame, text=reason, font=('Arial', 10), bg='white', fg='gray').pack(anchor='w')

        # Retry button
        def retry_tab():
            try:
                method_name = f"create_{tab_id}_tab"
                if hasattr(self, method_name):
                    getattr(self, method_name)()
                    self.show_tab(tab_id)
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance_gui.placeholder.retry_failed", error=str(e)))

        tk.Button(msg_frame, text=_("finance_gui.placeholder.retry_loading"), command=retry_tab,
                 bg=self.colors.get('primary', '#3498db'), fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(pady=20)

    def show_tab(self, tab_id):
        """Show the specified tab and hide others"""
        # Special handling for my_finances - opens student's own finance dialog
        if tab_id == 'my_finances':
            if hasattr(self.gui, 'view_my_finances'):
                self.gui.view_my_finances()
            elif hasattr(self.gui, 'view_student_finances'):
                self.gui.view_student_finances()
            return

        # Hide current tab if exists
        if self.current_tab and self.current_tab in self.tab_frames:
            self.tab_frames[self.current_tab].pack_forget()

        # Show new tab
        if tab_id in self.tab_frames:
            self.tab_frames[tab_id].pack(fill='both', expand=True)
            self.current_tab = tab_id

        # Update button styles
        for widget in self.nav_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(bg=self.colors['secondary'])

        # Highlight active button (simple approach)
        for widget in self.nav_frame.winfo_children():
            if isinstance(widget, tk.Button) and tab_id in widget['text'].lower():
                widget.config(bg=self.colors['primary'])
