"""
Financial Aid & Scholarships GUI - Main Coordinator

This module provides the main entry point for the Financial Aid & Scholarships GUI,
routing users to either the student portal or admin portal based on their permissions.
"""

from .common_imports import *
from .student_portal import StudentPortal
from .admin_portal import AdminPortal


class FinancialAidGUI:
    """Main coordinator for Financial Aid & Scholarships GUI"""

    def __init__(self, auth_instance=None, parent=None):
        """
        Initialize Financial Aid GUI

        Args:
            auth_instance: Authentication instance
            parent: Parent window (optional)
        """
        self.auth = auth_instance or get_auth()
        self.parent = parent
        self.root = None
        self.main_frame = None

        # Check if user is logged in
        if not self.auth or not self.auth.current_user:
            show_error("Authentication Required", "Please log in to access Financial Aid & Scholarships")
            return

        # Get user info
        self.current_user = get_current_user()
        self.is_admin = check_permission('manage_financial_aid')

        # Initialize portals
        self.student_portal = None
        self.admin_portal = None

    def run(self):
        """Run the Financial Aid GUI application"""
        if self.parent:
            # Running as embedded component
            self.create_embedded_interface()
        else:
            # Running as standalone window
            self.create_standalone_window()

    def create_standalone_window(self):
        """Create standalone window"""
        self.root = tk.Tk()
        self.root.title("Financial Aid & Scholarships Management")
        self.root.geometry("1200x800")

        # Configure styles
        configure_styles()

        # Create main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill='both', expand=True)

        # Show appropriate interface
        self.show_main_interface()

        # Run main loop
        self.root.mainloop()

    def create_embedded_interface(self):
        """Create interface embedded in parent window"""
        # Clear parent
        for widget in self.parent.winfo_children():
            widget.destroy()

        # Configure styles
        configure_styles()

        # Create main frame
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill='both', expand=True)

        # Show appropriate interface
        self.show_main_interface()

    def show_main_interface(self):
        """Show main interface with mode selection"""
        clear_frame(self.main_frame)

        # Header
        header_frame = ttk.Frame(self.main_frame, style='Card.TFrame', relief='raised', borderwidth=2)
        header_frame.pack(fill='x', padx=10, pady=10)

        title_label = ttk.Label(header_frame,
                               text="Financial Aid & Scholarships",
                               font=('Arial', 18, 'bold'),
                               foreground=COLORS['primary'])
        title_label.pack(pady=20)

        # User info
        user_dict = self.current_user.to_dict() if hasattr(self.current_user, 'to_dict') else self.current_user
        user_info = ttk.Label(header_frame,
                              text=f"Logged in as: {user_dict.get('username', 'Unknown')}",
                              font=('Arial', 10))
        user_info.pack(pady=(0, 20))

        # Content frame
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Check permissions and show appropriate interface
        if self.is_admin:
            # Admin user - show mode selection
            self._show_mode_selection(content_frame)
        else:
            # Regular user - go directly to student portal
            self.show_student_portal()

    def _show_mode_selection(self, parent):
        """Show mode selection for admin users"""
        # Welcome message
        welcome_frame = ttk.Frame(parent)
        welcome_frame.pack(pady=20)

        ttk.Label(welcome_frame,
                 text="Select Mode:",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        ttk.Label(welcome_frame,
                 text="You have administrative permissions. Choose how you want to proceed:",
                 font=('Arial', 10)).pack(pady=5)

        # Mode buttons
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(expand=True)

        # Student portal button
        student_card = ttk.Frame(buttons_frame, style='Card.TFrame', relief='raised', borderwidth=2)
        student_card.grid(row=0, column=0, padx=20, pady=20, ipadx=30, ipady=30)

        ttk.Label(student_card,
                 text="Student Portal",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        ttk.Label(student_card,
                 text="Browse scholarships\nApply for financial aid\nTrack your applications and awards",
                 justify='center',
                 font=('Arial', 10)).pack(pady=10)

        ttk.Button(student_card,
                  text="Enter Student Portal",
                  command=self.show_student_portal,
                  style='Primary.TButton',
                  width=25).pack(pady=10)

        # Admin portal button
        admin_card = ttk.Frame(buttons_frame, style='Card.TFrame', relief='raised', borderwidth=2)
        admin_card.grid(row=0, column=1, padx=20, pady=20, ipadx=30, ipady=30)

        ttk.Label(admin_card,
                 text="Admin Portal",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        ttk.Label(admin_card,
                 text="Manage scholarships\nReview applications\nProcess disbursements\nGenerate reports",
                 justify='center',
                 font=('Arial', 10)).pack(pady=10)

        ttk.Button(admin_card,
                  text="Enter Admin Portal",
                  command=self.show_admin_portal,
                  style='Success.TButton',
                  width=25).pack(pady=10)

    def show_student_portal(self):
        """Show student portal"""
        clear_frame(self.main_frame)

        # Create navigation bar
        nav_frame = ttk.Frame(self.main_frame, style='Card.TFrame', relief='raised', borderwidth=1)
        nav_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(nav_frame, text="Financial Aid - Student Portal",
                 font=('Arial', 12, 'bold')).pack(side='left', padx=10, pady=5)

        if self.is_admin:
            ttk.Button(nav_frame, text="Switch to Admin Portal",
                      command=self.show_admin_portal).pack(side='right', padx=5, pady=5)

        ttk.Button(nav_frame, text="Main Menu",
                  command=self.show_main_interface).pack(side='right', padx=5, pady=5)

        # Create content frame for student portal
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill='both', expand=True)

        # Initialize student portal if not already done
        if not self.student_portal:
            self.student_portal = StudentPortal(content_frame, self.auth)

        # Show student dashboard
        self.student_portal.show_dashboard()

    def show_admin_portal(self):
        """Show admin portal"""
        # Check permission
        if not self.is_admin:
            show_error("Access Denied", "You do not have permission to access the admin portal")
            return

        clear_frame(self.main_frame)

        # Create navigation bar
        nav_frame = ttk.Frame(self.main_frame, style='Card.TFrame', relief='raised', borderwidth=1)
        nav_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(nav_frame, text="Financial Aid - Admin Portal",
                 font=('Arial', 12, 'bold'), foreground=COLORS['success']).pack(side='left', padx=10, pady=5)

        ttk.Button(nav_frame, text="Switch to Student Portal",
                  command=self.show_student_portal).pack(side='right', padx=5, pady=5)

        ttk.Button(nav_frame, text="Main Menu",
                  command=self.show_main_interface).pack(side='right', padx=5, pady=5)

        # Create content frame for admin portal
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill='both', expand=True)

        # Initialize admin portal if not already done
        if not self.admin_portal:
            self.admin_portal = AdminPortal(content_frame, self.auth)

        # Show admin dashboard
        self.admin_portal.show_dashboard()


def main():
    """Main entry point for standalone execution"""
    # This would require authentication to be set up first
    try:
        from university_system.infrastructure.shared_context import get_auth

        auth = get_auth()
        if not auth or not auth.current_user:
            print("Please log in first using the main application")
            return

        # Create and run GUI
        app = FinancialAidGUI(auth_instance=auth)
        app.run()

    except Exception as e:
        print(f"Error starting Financial Aid GUI: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
