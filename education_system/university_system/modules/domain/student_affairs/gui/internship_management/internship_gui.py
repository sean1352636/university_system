from ._imports import (
    _t, init_i18n, logger, messagebox, set_auth, tk, ttk,
)

from .internships import InternshipsBrowseMixin
from .my_applications import MyApplicationsMixin
from .admin_applications import AdminApplicationsMixin
from .manage_internships import ManageInternshipsMixin
from .placements import PlacementsMixin
from .reports import ReportsMixin
from .eligibility import EligibilityMixin
from .notifications import NotificationsMixin
from .integrations import IntegrationsMixin


class InternshipGUI(
    InternshipsBrowseMixin,
    MyApplicationsMixin,
    AdminApplicationsMixin,
    ManageInternshipsMixin,
    PlacementsMixin,
    ReportsMixin,
    EligibilityMixin,
    NotificationsMixin,
    IntegrationsMixin,
):
    def __init__(self, root, auth_object=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("internship.title"))
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # Set authentication
        self.auth = auth_object
        if self.auth:
            set_auth(self.auth)

        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Configure colors
        self.style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground='#2c3e50')
        self.style.configure('Header.TLabel', font=('Arial', 12, 'bold'), foreground='#34495e')
        self.style.configure('Custom.TButton', font=('Arial', 10))

        # Initialize the GUI
        self.setup_main_interface()

    def setup_main_interface(self):
        """Setup the main interface with navigation"""
        # Clear the window
        for widget in self.root.winfo_children():
            widget.destroy()

        # Add return to homescreen button at the top
        return_btn = ttk.Button(
            self.root,
            text=_t("common.return_to_homescreen"),
            command=self.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Main title
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
        title_frame.pack(fill='x', padx=0, pady=0)
        title_frame.pack_propagate(False)

        title_label = tk.Label(title_frame, text=_t("internship.header_title"),
                              font=('Arial', 20, 'bold'), fg='white', bg='#2c3e50')
        title_label.pack(expand=True)

        # User info
        if self.auth and self.auth.current_user:
            user_info = f"Logged in as: {self.auth.current_user['username']} ({self.auth.current_user['role']})"
            user_label = tk.Label(self.root, text=user_info, font=('Arial', 10),
                                 fg='#7f8c8d', bg='#f0f0f0')
            user_label.pack(pady=5)

        # Main content frame
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Create scrollable sidebar navigation
        sidebar_container = tk.Frame(main_frame, bg='#f0f0f0', width=250)
        sidebar_container.pack(side='left', fill='y', padx=(0, 20))
        sidebar_container.pack_propagate(False)

        # Canvas + scrollbar for sidebar
        self.nav_canvas = tk.Canvas(sidebar_container, bg='#f0f0f0', highlightthickness=0, width=230)
        nav_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=self.nav_canvas.yview)
        nav_frame = tk.Frame(self.nav_canvas, bg='#f0f0f0')

        # Put navigation frame inside canvas
        self.nav_window = self.nav_canvas.create_window((0, 0), window=nav_frame, anchor="nw")

        # Wire up scrolling
        self.nav_canvas.configure(yscrollcommand=nav_scrollbar.set)
        self.nav_canvas.pack(side='left', fill='both', expand=True)
        nav_scrollbar.pack(side='right', fill='y')

        # Keep navigation width in sync with canvas width
        def _on_nav_canvas_configure(event):
            self.nav_canvas.itemconfig(self.nav_window, width=event.width)
        self.nav_canvas.bind("<Configure>", _on_nav_canvas_configure)

        # Update scrollregion whenever navigation content changes
        nav_frame.bind(
            "<Configure>",
            lambda e: self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))
        )

        # Bind mouse wheel scrolling for navigation
        self._bind_nav_scroll_events()

        # Create navigation buttons based on permissions
        self.create_navigation_buttons(nav_frame)

        # Content area
        self.content_frame = tk.Frame(main_frame, bg='white', relief='raised', bd=1)
        self.content_frame.pack(side='right', fill='both', expand=True)

        # Show welcome message by default
        self.show_welcome()

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                role = self.auth.current_user.get('role', '').lower()
                return role
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff or career advisor"""
        role = self.get_user_role()
        return role in ['staff', 'career_advisor', 'internship_coordinator']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def create_navigation_buttons(self, parent):
        """Create navigation buttons based on user permissions"""
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("common.error"), _t("internship.error.login_required"))
            return

        buttons = []

        # Student buttons
        if self.auth.check_permission('view_internships'):
            buttons.append((_t("internship.nav.view_internships"), self.show_internships))

        if self.auth.check_permission('apply_for_internship'):
            buttons.append((_t("internship.nav.apply_for_internship"), self.show_application_form))

        if self.auth.check_permission('view_own_applications'):
            buttons.append((_t("internship.nav.my_applications"), self.show_my_applications))

        # Staff/Admin buttons
        if self.auth.check_permission('view_all_applications'):
            buttons.append((_t("internship.nav.all_applications"), self.show_all_applications))

        if self.auth.check_permission('create_internship'):
            buttons.append((_t("internship.nav.create_internship"), self.show_create_internship))

        if self.auth.check_permission('edit_internship'):
            buttons.append((_t("internship.nav.manage_internships"), self.show_manage_internships))

        # Add placement management
        if self.auth.check_permission('view_all_applications'):
            buttons.append((_t("internship.nav.manage_placements"), self.show_placement_management))

        if self.auth.check_permission('view_internship_reports'):
            buttons.append((_t("internship.nav.reports"), self.show_reports))

        # Integration Services
        buttons.append((_t("internship.nav.integration_services"), self.show_integration_menu))

        # CLI Mode button (backward compatibility)
        buttons.append((_t("internship.nav.cli_mode"), self.launch_cli_mode))

        # Navigation back to homescreen
        buttons.append((_t("common.return_to_homescreen"), self.return_to_main_menu))

        # Create buttons (rest of the method remains the same)
        for i, (text, command) in enumerate(buttons):
            btn = tk.Button(parent, text=text, command=command,
                           font=('Arial', 10), bg='#3498db', fg='white',
                           padx=15, pady=8, relief='flat', cursor='hand2')
            btn.pack(side='top', padx=5, pady=2, fill='x')

            # Hover effects
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg='#2980b9'))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg='#3498db'))

        # Force scroll region update after all content is added
        parent.update_idletasks()
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
                    logger.debug(f"Failed to handle mouse wheel scroll: {e}")

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
                    logger.debug(f"Failed to handle keypress scroll: {e}")

        # Bind to navigation canvas
        try:
            self.nav_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
            self.nav_canvas.bind("<Button-4>", _on_mousewheel)    # Linux
            self.nav_canvas.bind("<Button-5>", _on_mousewheel)    # Linux
            self.nav_canvas.bind("<KeyPress>", _on_keypress)
            self.nav_canvas.focus_set()
        except Exception as e:
            logger.debug(f"Failed to bind canvas events: {e}")

    def clear_content(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_welcome(self):
        """Show welcome message"""
        self.clear_content()

        welcome_frame = tk.Frame(self.content_frame, bg='white')
        welcome_frame.pack(expand=True, fill='both', padx=40, pady=40)

        tk.Label(welcome_frame, text=_t("internship.welcome.title"), font=('Arial', 24, 'bold'),
                bg='white', fg='#2c3e50').pack(pady=(0, 20))

        tk.Label(welcome_frame, text=_t("internship.welcome.message"), font=('Arial', 12),
                bg='white', fg='#34495e', justify='left').pack()
