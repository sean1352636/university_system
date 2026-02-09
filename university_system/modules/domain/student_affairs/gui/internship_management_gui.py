import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import logging
from university_system.infrastructure.database.db import sqlite3
from university_system.infrastructure.database.db import get_connection
from university_system.infrastructure.email.template_utils import render_template

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Configure logging
logger = logging.getLogger(__name__)
# Email functions not available - creating dummy functions
def send_internship_notification(*args, **kwargs):
    """
    Send internship notification - Sends email notifications to students about internship opportunities
    """
    try:
        # Extract arguments if provided positionally or as keywords
        student_id = args[0] if len(args) > 0 else kwargs.get('student_id')
        internship_title = args[1] if len(args) > 1 else kwargs.get('internship_title', 'Internship')
        message = args[2] if len(args) > 2 else kwargs.get('message', 'New internship notification')

        from university_system.infrastructure.email.email_service import EmailService
        from university_system.infrastructure.database.db import get_connection

        email_service = EmailService()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email_address, first_name FROM students WHERE student_id = ?", (student_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            email, first_name = result
            from university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template('internships/internship_update_notification', {
                'internship_title': internship_title,
                'first_name': first_name,
                'message': message
            })
            email_service.send_email(to_address=email, subject=subject, body=body)
            print(f"Notification sent to {email}")
    except Exception as e:
        print(f"Failed to send notification: {e}")

def send_application_confirmation(*args, **kwargs):
    """
    Send application confirmation - Acknowledges receipt of student internship application
    """
    try:
        student_id = args[0] if len(args) > 0 else kwargs.get('student_id')
        internship_id = args[1] if len(args) > 1 else kwargs.get('internship_id')

        from university_system.infrastructure.email.email_service import EmailService
        from university_system.infrastructure.database.db import get_connection

        email_service = EmailService()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.email_address, s.first_name, i.title, i.company
            FROM students s, internships i
            WHERE s.student_id = ? AND i.internship_id = ?
        """, (student_id, internship_id))
        result = cursor.fetchone()
        conn.close()

        if result:
            email, first_name, title, company = result
            from university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template('internships/application_confirmation', {
                'first_name': first_name,
                'title': title,
                'company': company
            })
            email_service.send_email(to_address=email, subject=subject, body=body)
            print(f"Confirmation sent to {email}")
    except Exception as e:
        print(f"Failed to send confirmation: {e}")

# Import all original functions to maintain backward compatibility
from university_system.modules.domain.student_affairs.services.internship_management import (
    setup_internship_permissions,
    init_internship_db,
    set_auth,
    view_available_internships,
    view_internship_details,
    apply_for_internship,
    view_applications,
    review_application,
    create_internship,
    edit_internship,
    delete_internship,
    generate_internship_report,
    display_internship_menu
)

class InternshipGUI:
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

    def show_placement_management(self):
        """Show placement management interface"""
        self.clear_content()
        
        if not self.auth.check_permission('view_all_applications'):
            messagebox.showerror("Permission Error", "You don't have permission to manage placements.")
            return
        
        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))
        
        tk.Label(title_frame, text="Placement Management", 
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')
        
        # Filter frame
        filter_frame = tk.Frame(title_frame, bg='white')
        filter_frame.pack(side='right')
        
        tk.Label(filter_frame, text="Filter by Status:", font=('Arial', 10), 
                bg='white', fg='#34495e').pack(side='left', padx=(0, 5))
        
        self.placement_status_filter = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.placement_status_filter, 
                                   values=["All", "active", "completed", "terminated"],
                                   font=('Arial', 9), state='readonly', width=12)
        status_combo.pack(side='left', padx=5)
        status_combo.bind('<<ComboboxSelected>>', lambda e: self.load_placement_data())
        
        refresh_btn = tk.Button(filter_frame, text="Refresh", command=self.load_placement_data,
                               bg='#27ae60', fg='white', font=('Arial', 10), 
                               padx=10, pady=3, relief='flat')
        refresh_btn.pack(side='left', padx=5)
        
        # Create treeview for placements
        tree_frame = tk.Frame(self.content_frame, bg='white')
        tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Scrollbars
        tree_scroll_y = tk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')
        
        tree_scroll_x = tk.Scrollbar(tree_frame, orient='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x')
        
        # Treeview
        columns = ('Placement ID', 'Student Name', 'Internship', 'Company', 'Supervisor', 'Start Date', 'Status')
        self.placement_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                          yscrollcommand=tree_scroll_y.set,
                                          xscrollcommand=tree_scroll_x.set)
        
        tree_scroll_y.config(command=self.placement_tree.yview)
        tree_scroll_x.config(command=self.placement_tree.xview)
        
        # Define headings
        for col in columns:
            self.placement_tree.heading(col, text=col)
            if col in ['Placement ID', 'Status']:
                self.placement_tree.column(col, width=100)
            else:
                self.placement_tree.column(col, width=150)
        
        self.placement_tree.pack(fill='both', expand=True)
        
        # Load data
        self.load_placement_data()
        
        # Button frame
        btn_frame = tk.Frame(self.content_frame, bg='white')
        btn_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Button(btn_frame, text="View Details", command=self.view_placement_details,
                 bg='#3498db', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="Update Status", command=self.update_placement_status,
                 bg='#f39c12', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)

    def load_placement_data(self):
        """Load placement data into the treeview"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Clear existing data
            for item in self.placement_tree.get_children():
                self.placement_tree.delete(item)
            
            # Build query based on filter
            base_query = '''
            SELECT p.placement_id, s.first_name || ' ' || s.last_name, i.title, 
                   i.company, p.supervisor_name, p.start_date, p.status
            FROM internship_placements p
            JOIN students s ON p.student_id = s.student_id
            JOIN internships i ON p.internship_id = i.internship_id
            '''
            
            if self.placement_status_filter.get() != "All":
                cursor.execute(base_query + ' WHERE p.status = ? ORDER BY p.start_date DESC', 
                              (self.placement_status_filter.get(),))
            else:
                cursor.execute(base_query + ' ORDER BY p.start_date DESC')
            
            placements = cursor.fetchall()
            
            # Insert data with color coding
            for placement in placements:
                tags = []
                if placement[6] == 'active':
                    tags = ['active']
                elif placement[6] == 'completed':
                    tags = ['completed']
                elif placement[6] == 'terminated':
                    tags = ['terminated']

                # Convert Row object to tuple for Treeview display
                values = tuple(placement)
                self.placement_tree.insert('', 'end', values=values, tags=tags)
            
            # Configure tag colors
            self.placement_tree.tag_configure('active', background='#d4edda')
            self.placement_tree.tag_configure('completed', background='#cce5ff')
            self.placement_tree.tag_configure('terminated', background='#f8d7da')
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading placements: {e}")

    def view_placement_details(self):
        """View details of selected placement"""
        selection = self.placement_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select a placement to view.")
            return
        
        item = self.placement_tree.item(selection[0])
        placement_id = item['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT p.*, s.first_name, s.last_name, s.email_address,
                   i.title, i.company, i.location
            FROM internship_placements p
            JOIN students s ON p.student_id = s.student_id
            JOIN internships i ON p.internship_id = i.internship_id
            WHERE p.placement_id = ?
            ''', (placement_id,))
            
            placement_data = cursor.fetchone()
            
            if not placement_data:
                messagebox.showerror("Error", "Placement not found.")
                conn.close()
                return
            
            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title("Placement Details")
            popup.geometry("600x500")
            popup.configure(bg='white')
            popup.grab_set()
            
            # Title
            tk.Label(popup, text="Placement Details", font=('Arial', 16, 'bold'), 
                    bg='white', fg='#2c3e50').pack(pady=10)
            
            # Details frame
            details_frame = tk.Frame(popup, bg='white')
            details_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            # Student info
            student_info = f"""
    Placement ID: {placement_data[0]}
    Student: {placement_data[8]} {placement_data[9]} ({placement_data[1]})
    Email: {placement_data[10]}
    Internship: {placement_data[11]} at {placement_data[12]}
    Location: {placement_data[13]}
    Duration: {placement_data[3]} to {placement_data[4]}
    Supervisor: {placement_data[5]} ({placement_data[6]})
    Status: {placement_data[7].upper()}
    """
            
            tk.Label(details_frame, text=student_info, font=('Arial', 11), 
                    bg='white', fg='#34495e', justify='left').pack(anchor='w')
            
            # Feedback sections
            if placement_data[8]:  # Student feedback
                tk.Label(details_frame, text="Student Feedback:", font=('Arial', 12, 'bold'), 
                        bg='white', fg='#2c3e50').pack(anchor='w', pady=(10, 5))
                
                student_feedback = scrolledtext.ScrolledText(details_frame, height=4, wrap='word', 
                                                           font=('Arial', 10), bg='#f8f9fa')
                student_feedback.pack(fill='x', pady=(0, 10))
                student_feedback.insert('1.0', placement_data[8])
                student_feedback.config(state='disabled')
            
            if placement_data[9]:  # Employer feedback
                tk.Label(details_frame, text="Employer Feedback:", font=('Arial', 12, 'bold'), 
                        bg='white', fg='#2c3e50').pack(anchor='w', pady=(10, 5))
                
                employer_feedback = scrolledtext.ScrolledText(details_frame, height=4, wrap='word', 
                                                            font=('Arial', 10), bg='#f8f9fa')
                employer_feedback.pack(fill='x', pady=(0, 10))
                employer_feedback.insert('1.0', placement_data[9])
                employer_feedback.config(state='disabled')
            
            # Close button
            tk.Button(popup, text="Close", command=popup.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 10), padx=20, pady=5, relief='flat').pack(pady=10)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading placement details: {e}")

    def update_placement_status(self):
        """Update status of selected placement"""
        selection = self.placement_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select a placement to update.")
            return
        
        item = self.placement_tree.item(selection[0])
        placement_id = item['values'][0]
        current_status = item['values'][6]
        
        # Create update dialog
        update_dialog = tk.Toplevel(self.root)
        update_dialog.title("Update Placement Status")
        update_dialog.geometry("400x200")
        update_dialog.configure(bg='white')
        update_dialog.grab_set()
        
        tk.Label(update_dialog, text="Update Placement Status", 
                font=('Arial', 14, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
        
        tk.Label(update_dialog, text=f"Current Status: {current_status}", 
                font=('Arial', 11), bg='white', fg='#34495e').pack()
        
        # Status selection
        tk.Label(update_dialog, text="New Status:", font=('Arial', 12, 'bold'), 
                bg='white', fg='#2c3e50').pack(pady=(10, 5))
        
        new_status_var = tk.StringVar(value=current_status)
        status_options = ['active', 'completed', 'terminated']
        
        for status in status_options:
            tk.Radiobutton(update_dialog, text=status.capitalize(), variable=new_status_var, 
                          value=status, font=('Arial', 10), bg='white').pack()
        
        # Buttons
        btn_frame = tk.Frame(update_dialog, bg='white')
        btn_frame.pack(pady=20)
        
        def save_status():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                UPDATE internship_placements
                SET status = ?
                WHERE placement_id = ?
                ''', (new_status_var.get(), placement_id))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", f"Placement status updated to: {new_status_var.get()}")
                update_dialog.destroy()
                self.load_placement_data()
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error updating placement status: {e}")
        
        tk.Button(btn_frame, text="Save", command=save_status,
                 bg='#27ae60', fg='white', font=('Arial', 10), padx=20, pady=5, relief='flat').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="Cancel", command=update_dialog.destroy,
                 bg='#6c757d', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
        
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
    
    def show_internships(self):
        """Show available internships"""
        self.clear_content()

        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))

        tk.Label(title_frame, text=_t("internship.available.title"),
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')

        # Refresh button
        refresh_btn = tk.Button(title_frame, text=_t("common.refresh"), command=self.show_internships,
                               bg='#27ae60', fg='white', font=('Arial', 10),
                               padx=15, pady=5, relief='flat')
        refresh_btn.pack(side='right')
        
        # Create treeview for internships
        tree_frame = tk.Frame(self.content_frame, bg='white')
        tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Scrollbars
        tree_scroll_y = tk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')
        
        tree_scroll_x = tk.Scrollbar(tree_frame, orient='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x')
        
        # Treeview
        columns = ('ID', 'Title', 'Company', 'Location', 'Deadline', 'Status')
        self.internship_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                           yscrollcommand=tree_scroll_y.set,
                                           xscrollcommand=tree_scroll_x.set)
        
        # Configure scrollbars
        tree_scroll_y.config(command=self.internship_tree.yview)
        tree_scroll_x.config(command=self.internship_tree.xview)
        
        # Define headings
        for col in columns:
            self.internship_tree.heading(col, text=col)
            self.internship_tree.column(col, width=150)
        
        self.internship_tree.pack(fill='both', expand=True)
        
        # Load internships data
        self.load_internships_data()
        
        # Button frame
        btn_frame = tk.Frame(self.content_frame, bg='white')
        btn_frame.pack(fill='x', padx=20, pady=10)

        tk.Button(btn_frame, text=_t("internship.btn.view_details"), command=self.view_selected_internship,
                 bg='#3498db', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)

        if self.auth.check_permission('apply_for_internship'):
            tk.Button(btn_frame, text=_t("internship.btn.apply"), command=self.apply_for_selected_internship,
                     bg='#e74c3c', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
    
    def load_internships_data(self):
        """Load internships data into the treeview"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Clear existing data
            for item in self.internship_tree.get_children():
                self.internship_tree.delete(item)
            
            # Get internships based on user role
            if self.auth.current_user['role'] == 'student':
                # Get student's course
                cursor.execute('''
                SELECT course FROM students 
                JOIN users ON students.student_id = users.student_id
                WHERE users.id = ?
                ''', (self.auth.current_user['id'],))
                
                result = cursor.fetchone()
                if result:
                    course = result[0]
                    cursor.execute('''
                    SELECT internship_id, title, company, location, deadline_date, 'Active'
                    FROM internships 
                    WHERE status = 'active' AND (course_relevance = ? OR course_relevance = 'All')
                    AND deadline_date >= ?
                    ORDER BY deadline_date ASC
                    ''', (course, datetime.now().strftime('%Y-%m-%d')))
                else:
                    cursor.execute('''
                    SELECT internship_id, title, company, location, deadline_date, 'Active'
                    FROM internships 
                    WHERE status = 'active' AND deadline_date >= ?
                    ORDER BY deadline_date ASC
                    ''', (datetime.now().strftime('%Y-%m-%d'),))
            else:
                cursor.execute('''
                SELECT internship_id, title, company, location, deadline_date, status
                FROM internships 
                ORDER BY status, deadline_date ASC
                ''')
            
            internships = cursor.fetchall()
            
            # Insert data into treeview
            for internship in internships:
                # Convert Row object to tuple for Treeview display
                values = tuple(internship)
                self.internship_tree.insert('', 'end', values=values)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading internships: {e}")
    
    def view_selected_internship(self):
        """View details of selected internship"""
        selection = self.internship_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select an internship to view.")
            return
        
        item = self.internship_tree.item(selection[0])
        internship_id = item['values'][0]
        
        self.show_internship_details(internship_id)
    
    def show_internship_details(self, internship_id):
        """Show detailed view of an internship"""
        self.clear_content()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM internships WHERE internship_id = ?', (internship_id,))
            internship = cursor.fetchone()
            
            if not internship:
                messagebox.showerror("Error", "Internship not found.")
                conn.close()
                return
            
            # Main details frame
            details_frame = tk.Frame(self.content_frame, bg='white')
            details_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Title
            tk.Label(details_frame, text=f"{internship[1]}", font=('Arial', 20, 'bold'), 
                    bg='white', fg='#2c3e50').pack(anchor='w', pady=(0, 10))
            
            # Company info
            company_frame = tk.Frame(details_frame, bg='#ecf0f1', relief='raised', bd=1)
            company_frame.pack(fill='x', pady=(0, 15))
            
            tk.Label(company_frame, text=f"Company: {internship[2]}", font=('Arial', 14, 'bold'), 
                    bg='#ecf0f1', fg='#2c3e50').pack(anchor='w', padx=15, pady=5)
            tk.Label(company_frame, text=f"Location: {internship[3]}", font=('Arial', 12), 
                    bg='#ecf0f1', fg='#34495e').pack(anchor='w', padx=15, pady=2)
            tk.Label(company_frame, text=f"Contact: {internship[14]}", font=('Arial', 12), 
                    bg='#ecf0f1', fg='#34495e').pack(anchor='w', padx=15, pady=(2, 5))
            
            # Description
            desc_frame = tk.LabelFrame(details_frame, text="Description", font=('Arial', 12, 'bold'),
                                      bg='white', fg='#2c3e50')
            desc_frame.pack(fill='x', pady=(0, 15))
            
            desc_text = scrolledtext.ScrolledText(desc_frame, height=4, wrap='word', 
                                                 font=('Arial', 10), bg='#f8f9fa')
            desc_text.pack(fill='x', padx=10, pady=5)
            desc_text.insert('1.0', internship[4])
            desc_text.config(state='disabled')
            
            # Requirements
            req_frame = tk.LabelFrame(details_frame, text="Requirements", font=('Arial', 12, 'bold'),
                                     bg='white', fg='#2c3e50')
            req_frame.pack(fill='x', pady=(0, 15))
            
            req_text = scrolledtext.ScrolledText(req_frame, height=3, wrap='word', 
                                               font=('Arial', 10), bg='#f8f9fa')
            req_text.pack(fill='x', padx=10, pady=5)
            req_text.insert('1.0', internship[5])
            req_text.config(state='disabled')
            
            # Details grid
            info_frame = tk.Frame(details_frame, bg='white')
            info_frame.pack(fill='x', pady=(0, 15))
            
            # Left column
            left_col = tk.Frame(info_frame, bg='white')
            left_col.pack(side='left', fill='x', expand=True)
            
            tk.Label(left_col, text=f"Start Date: {internship[6]}", font=('Arial', 11), 
                    bg='white', fg='#34495e').pack(anchor='w')
            tk.Label(left_col, text=f"End Date: {internship[7]}", font=('Arial', 11), 
                    bg='white', fg='#34495e').pack(anchor='w')
            tk.Label(left_col, text=f"Hours/Week: {internship[10]}", font=('Arial', 11), 
                    bg='white', fg='#34495e').pack(anchor='w')
            
            # Right column
            right_col = tk.Frame(info_frame, bg='white')
            right_col.pack(side='left', fill='x', expand=True)
            
            paid_status = "Paid" if internship[8] else "Unpaid"
            tk.Label(right_col, text=f"Type: {paid_status}", font=('Arial', 11), 
                    bg='white', fg='#34495e').pack(anchor='w')
            tk.Label(right_col, text=f"Compensation: {internship[9]}", font=('Arial', 11), 
                    bg='white', fg='#34495e').pack(anchor='w')
            tk.Label(right_col, text=f"Deadline: {internship[12]}", font=('Arial', 11), 
                    bg='white', fg='#34495e').pack(anchor='w')
            
            # Application status for students
            if self.auth.current_user['role'] == 'student':
                cursor.execute('''
                SELECT status, application_date FROM internship_applications
                WHERE student_id = (
                    SELECT student_id FROM users WHERE id = ?
                ) AND internship_id = ?
                ''', (self.auth.current_user['id'], internship_id))
                
                application = cursor.fetchone()
                
                status_frame = tk.Frame(details_frame, bg='#e8f5e8' if application and application[0] == 'approved' 
                                       else '#fff3cd' if application and application[0] == 'pending'
                                       else '#f8d7da' if application and application[0] == 'rejected'
                                       else '#d1ecf1', relief='raised', bd=1)
                status_frame.pack(fill='x', pady=(0, 15))
                
                if application:
                    tk.Label(status_frame, text=f"Application Status: {application[0].upper()}", 
                            font=('Arial', 12, 'bold'), bg=status_frame['bg'], fg='#2c3e50').pack(pady=5)
                    tk.Label(status_frame, text=f"Applied on: {application[1]}", 
                            font=('Arial', 10), bg=status_frame['bg'], fg='#34495e').pack()
                else:
                    tk.Label(status_frame, text="Application Status: NOT APPLIED", 
                            font=('Arial', 12, 'bold'), bg=status_frame['bg'], fg='#2c3e50').pack(pady=5)
            
            # Buttons
            btn_frame = tk.Frame(details_frame, bg='white')
            btn_frame.pack(fill='x', pady=10)
            
            tk.Button(btn_frame, text="Back to List", command=self.show_internships,
                     bg='#6c757d', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
            
            if (self.auth.check_permission('apply_for_internship') and 
                (not application if self.auth.current_user['role'] == 'student' else True)):
                tk.Button(btn_frame, text="Apply Now", command=lambda: self.show_application_form(internship_id),
                         bg='#e74c3c', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading internship details: {e}")
    
    def apply_for_selected_internship(self):
        """Apply for the selected internship"""
        selection = self.internship_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select an internship to apply for.")
            return
        
        item = self.internship_tree.item(selection[0])
        internship_id = item['values'][0]
        
        self.show_application_form(internship_id)
    
    def show_application_form(self, internship_id=None):
        """Show application form"""
        self.clear_content()

        if not self.auth.check_permission('apply_for_internship'):
            messagebox.showerror(_t("common.error"), _t("internship.error.no_apply_permission"))
            return

        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))

        tk.Label(title_frame, text=_t("internship.apply.title"),
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')
        
        # Form frame
        form_frame = tk.Frame(self.content_frame, bg='white')
        form_frame.pack(fill='both', expand=True, padx=40, pady=20)
        
        # Internship selection
        tk.Label(form_frame, text=_t("internship.apply.select_internship"), font=('Arial', 12, 'bold'),
                bg='white', fg='#2c3e50').pack(anchor='w', pady=(0, 5))
        
        self.internship_var = tk.StringVar()
        internship_combo = ttk.Combobox(form_frame, textvariable=self.internship_var, 
                                       font=('Arial', 10), state='readonly', width=80)
        internship_combo.pack(anchor='w', pady=(0, 15))
        
        # Load available internships
        self.load_internship_options(internship_combo, internship_id)
        
        # CV filename
        tk.Label(form_frame, text=_t("internship.apply.cv_filename"), font=('Arial', 12, 'bold'),
                bg='white', fg='#2c3e50').pack(anchor='w', pady=(0, 5))

        self.cv_entry = tk.Entry(form_frame, font=('Arial', 10), width=80)
        self.cv_entry.pack(anchor='w', pady=(0, 15))
        self.cv_entry.insert(0, "my_cv.pdf")

        # Cover letter
        tk.Label(form_frame, text=_t("internship.apply.cover_letter"), font=('Arial', 12, 'bold'),
                bg='white', fg='#2c3e50').pack(anchor='w', pady=(0, 5))
        
        self.cover_letter_text = scrolledtext.ScrolledText(form_frame, height=10, wrap='word', 
                                                          font=('Arial', 10), width=80)
        self.cover_letter_text.pack(anchor='w', pady=(0, 15))
        
        # Buttons
        btn_frame = tk.Frame(form_frame, bg='white')
        btn_frame.pack(anchor='w', pady=10)

        tk.Button(btn_frame, text=_t("internship.apply.submit"), command=self.submit_application,
                 bg='#27ae60', fg='white', font=('Arial', 12, 'bold'), padx=20, pady=8, relief='flat').pack(side='left', padx=5)

        tk.Button(btn_frame, text=_t("common.cancel"), command=self.show_internships,
                 bg='#6c757d', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
    
    def load_internship_options(self, combo, selected_id=None):
        """Load internship options for the combobox"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check user role - admins/staff can see all internships
            if self.auth.current_user['role'] != 'student':
                cursor.execute('''
                SELECT internship_id, title, company FROM internships
                WHERE status = 'active'
                ORDER BY deadline_date ASC
                ''')
            else:
                # Get student's course
                cursor.execute('''
                SELECT course FROM students
                JOIN users ON students.student_id = users.student_id
                WHERE users.id = ?
                ''', (self.auth.current_user['id'],))

                result = cursor.fetchone()
                if result:
                    course = result[0]
                    cursor.execute('''
                    SELECT internship_id, title, company FROM internships
                    WHERE status = 'active' AND (course_relevance = ? OR course_relevance = 'All')
                    AND deadline_date >= ?
                    ORDER BY deadline_date ASC
                    ''', (course, datetime.now().strftime('%Y-%m-%d')))
                else:
                    cursor.execute('''
                    SELECT internship_id, title, company FROM internships
                    WHERE status = 'active' AND deadline_date >= ?
                    ORDER BY deadline_date ASC
                    ''', (datetime.now().strftime('%Y-%m-%d'),))
            
            internships = cursor.fetchall()
            
            # Format options
            options = [f"{i[0]} - {i[1]} at {i[2]}" for i in internships]
            combo['values'] = options
            
            # Set default selection
            if selected_id:
                for i, option in enumerate(options):
                    if option.startswith(str(selected_id)):
                        combo.current(i)
                        break
            elif options:
                combo.current(0)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading internships: {e}")
    
    def submit_application(self):
        """Submit the internship application"""
        try:
            # Validate inputs
            if not self.internship_var.get():
                messagebox.showerror("Validation Error", "Please select an internship.")
                return

            if not self.cv_entry.get().strip():
                messagebox.showerror("Validation Error", "Please enter your CV filename.")
                return

            if not self.cover_letter_text.get('1.0', 'end-1c').strip():
                messagebox.showerror("Validation Error", "Please provide a cover letter.")
                return

            # Extract internship ID
            internship_id = self.internship_var.get().split(' - ')[0]
            cv_filename = self.cv_entry.get().strip()
            cover_letter = self.cover_letter_text.get('1.0', 'end-1c').strip()

            conn = get_connection()
            cursor = conn.cursor()

            # Get student ID
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result or not result[0]:
                messagebox.showerror("Error", "No student record associated with your account.")
                conn.close()
                return

            student_id = result[0]

            # Check eligibility for internship
            if not self.check_student_eligibility(student_id):
                conn.close()
                return

            # Check if already applied
            cursor.execute('''
            SELECT application_id FROM internship_applications
            WHERE student_id = ? AND internship_id = ?
            ''', (student_id, internship_id))

            if cursor.fetchone():
                messagebox.showerror("Error", "You have already applied for this internship.")
                conn.close()
                return

            # Create application
            application_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO internship_applications (
                student_id, internship_id, application_date, status, cv_filename, cover_letter
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, internship_id, application_date, 'pending', cv_filename, cover_letter))

            conn.commit()
            conn.close()

            # Send application confirmation email automatically
            try:
                from university_system.infrastructure.email.email_service import send_application_confirmation
                send_application_confirmation(student_id, internship_id)
            except Exception as e:
                import logging
                logging.warning(f"Failed to send application confirmation email: {e}")

            messagebox.showinfo("Success", "Application submitted successfully!")
            self.show_my_applications()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error submitting application: {e}")
    
    def show_my_applications(self):
        """Show student's applications"""
        self.clear_content()

        if not self.auth.check_permission('view_own_applications'):
            messagebox.showerror(_t("common.error"), _t("internship.error.no_view_permission"))
            return

        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))

        tk.Label(title_frame, text=_t("internship.my_applications.title"),
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')

        # Refresh button
        refresh_btn = tk.Button(title_frame, text=_t("common.refresh"), command=self.show_my_applications,
                               bg='#27ae60', fg='white', font=('Arial', 10),
                               padx=15, pady=5, relief='flat')
        refresh_btn.pack(side='right')
        
        # Create treeview for applications
        tree_frame = tk.Frame(self.content_frame, bg='white')
        tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Scrollbars
        tree_scroll_y = tk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')
        
        # Treeview
        columns = ('App ID', 'Internship', 'Company', 'Applied Date', 'Status')
        self.app_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                    yscrollcommand=tree_scroll_y.set)
        
        tree_scroll_y.config(command=self.app_tree.yview)
        
        # Define headings
        for col in columns:
            self.app_tree.heading(col, text=col)
            self.app_tree.column(col, width=150)
        
        self.app_tree.pack(fill='both', expand=True)
        
        # Load applications data
        self.load_my_applications_data()
        
        # Button frame
        btn_frame = tk.Frame(self.content_frame, bg='white')
        btn_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Button(btn_frame, text="View Details", command=self.view_application_details,
                 bg='#3498db', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
    
    def load_my_applications_data(self):
        """Load student's applications data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Clear existing data
            for item in self.app_tree.get_children():
                self.app_tree.delete(item)
            
            cursor.execute('''
            SELECT a.application_id, i.title, i.company, a.application_date, a.status
            FROM internship_applications a
            JOIN internships i ON a.internship_id = i.internship_id
            WHERE a.student_id = (
                SELECT student_id FROM users WHERE id = ?
            )
            ORDER BY a.application_date DESC
            ''', (self.auth.current_user['id'],))
            
            applications = cursor.fetchall()
            
            # Insert data with color coding
            for app in applications:
                tags = []
                if app[4] == 'approved':
                    tags = ['approved']
                elif app[4] == 'rejected':
                    tags = ['rejected']
                elif app[4] == 'pending':
                    tags = ['pending']

                # Convert Row object to tuple for Treeview display
                values = tuple(app)
                self.app_tree.insert('', 'end', values=values, tags=tags)
            
            # Configure tag colors
            self.app_tree.tag_configure('approved', background='#d4edda')
            self.app_tree.tag_configure('rejected', background='#f8d7da')
            self.app_tree.tag_configure('pending', background='#fff3cd')
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading applications: {e}")
    
    def view_application_details(self):
        """View details of selected application"""
        selection = self.app_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select an application to view.")
            return
        
        item = self.app_tree.item(selection[0])
        app_id = item['values'][0]
        
        self.show_application_details_window(app_id)

    def show_enhanced_application_details(self, app_id):
        """Show enhanced application details with all information"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT a.*, s.first_name, s.last_name, s.email_address, s.course, s.phone_number,
                   i.title, i.company, i.location, i.description, i.requirements
            FROM internship_applications a
            JOIN students s ON a.student_id = s.student_id
            JOIN internships i ON a.internship_id = i.internship_id
            WHERE a.application_id = ?
            ''', (app_id,))
            
            app_data = cursor.fetchone()
            
            if not app_data:
                messagebox.showerror("Error", "Application not found.")
                conn.close()
                return
            
            # Create comprehensive popup window
            popup = tk.Toplevel(self.root)
            popup.title("Complete Application Details")
            popup.geometry("800x600")
            popup.configure(bg='white')
            popup.grab_set()
            
            # Create scrollable content
            canvas = tk.Canvas(popup, bg='white')
            scrollbar = ttk.Scrollbar(popup, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg='white')
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Title
            tk.Label(scrollable_frame, text="Complete Application Details", 
                    font=('Arial', 16, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
            
            # Student Information Section
            student_frame = tk.LabelFrame(scrollable_frame, text="Student Information", 
                                        font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            student_frame.pack(fill='x', padx=20, pady=10)
            
            student_info = f"""
    Application ID: {app_data[0]}
    Student ID: {app_data[1]}
    Name: {app_data[7]} {app_data[8]}
    Email: {app_data[9]}
    Course: {app_data[10]}
    Phone: {app_data[11] if app_data[11] else 'Not provided'}
    """
            tk.Label(student_frame, text=student_info, font=('Arial', 11), 
                    bg='white', fg='#34495e', justify='left').pack(anchor='w', padx=10, pady=5)
            
            # Internship Information Section
            internship_frame = tk.LabelFrame(scrollable_frame, text="Internship Information", 
                                           font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            internship_frame.pack(fill='x', padx=20, pady=10)
            
            internship_info = f"""
    Internship: {app_data[12]} at {app_data[13]}
    Location: {app_data[14]}
    Applied Date: {app_data[3]}
    Current Status: {app_data[4].upper()}
    CV Filename: {app_data[5]}
    """
            tk.Label(internship_frame, text=internship_info, font=('Arial', 11), 
                    bg='white', fg='#34495e', justify='left').pack(anchor='w', padx=10, pady=5)
            
            # Job Description
            desc_frame = tk.LabelFrame(scrollable_frame, text="Job Description", 
                                      font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            desc_frame.pack(fill='x', padx=20, pady=10)
            
            desc_text = scrolledtext.ScrolledText(desc_frame, height=3, wrap='word', 
                                                font=('Arial', 10), bg='#f8f9fa')
            desc_text.pack(fill='x', padx=10, pady=5)
            desc_text.insert('1.0', app_data[15] or "No description available.")
            desc_text.config(state='disabled')
            
            # Requirements
            req_frame = tk.LabelFrame(scrollable_frame, text="Requirements", 
                                     font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            req_frame.pack(fill='x', padx=20, pady=10)
            
            req_text = scrolledtext.ScrolledText(req_frame, height=3, wrap='word', 
                                               font=('Arial', 10), bg='#f8f9fa')
            req_text.pack(fill='x', padx=10, pady=5)
            req_text.insert('1.0', app_data[16] or "No requirements listed.")
            req_text.config(state='disabled')
            
            # Cover Letter Section
            cover_frame = tk.LabelFrame(scrollable_frame, text="Cover Letter", 
                                       font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            cover_frame.pack(fill='x', padx=20, pady=10)
            
            cover_text = scrolledtext.ScrolledText(cover_frame, height=6, wrap='word', 
                                                 font=('Arial', 10), bg='#f8f9fa')
            cover_text.pack(fill='x', padx=10, pady=5)
            cover_text.insert('1.0', app_data[6] or "No cover letter provided.")
            cover_text.config(state='disabled')
            
            # Feedback Section (if available)
            if app_data[7]:  # Assuming feedback is at index 7
                feedback_frame = tk.LabelFrame(scrollable_frame, text="Feedback", 
                                             font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
                feedback_frame.pack(fill='x', padx=20, pady=10)
                
                feedback_text = scrolledtext.ScrolledText(feedback_frame, height=4, wrap='word', 
                                                        font=('Arial', 10), bg='#f8f9fa')
                feedback_text.pack(fill='x', padx=10, pady=5)
                feedback_text.insert('1.0', app_data[7])
                feedback_text.config(state='disabled')
            
            # Buttons
            btn_frame = tk.Frame(scrollable_frame, bg='white')
            btn_frame.pack(fill='x', padx=20, pady=20)
            
            tk.Button(btn_frame, text="Close", command=popup.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 10), padx=20, pady=5, relief='flat').pack(side='left', padx=5)
            
            if self.auth.check_permission('approve_applications'):
                tk.Button(btn_frame, text="Review Application", 
                         command=lambda: self.open_review_dialog(app_id, popup),
                         bg='#f39c12', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
            
            # Pack canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
            scrollbar.pack(side="right", fill="y", pady=10)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading application details: {e}")
    
    def show_application_details_window(self, app_id):
        """Show application details in a popup window"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT a.*, i.title, i.company, i.location
            FROM internship_applications a
            JOIN internships i ON a.internship_id = i.internship_id
            WHERE a.application_id = ?
            ''', (app_id,))
            
            app_data = cursor.fetchone()
            
            if not app_data:
                messagebox.showerror("Error", "Application not found.")
                conn.close()
                return
            
            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title("Application Details")
            popup.geometry("600x500")
            popup.configure(bg='white')
            popup.grab_set()  # Make modal
            
            # Title
            tk.Label(popup, text="Application Details", font=('Arial', 16, 'bold'), 
                    bg='white', fg='#2c3e50').pack(pady=10)
            
            # Details frame
            details_frame = tk.Frame(popup, bg='white')
            details_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            # Application info
            info_text = f"""
Application ID: {app_data[0]}
Internship: {app_data[7]} at {app_data[8]}
Location: {app_data[9]}
Applied Date: {app_data[3]}
Status: {app_data[4].upper()}
CV Filename: {app_data[5]}
"""
            
            tk.Label(details_frame, text=info_text, font=('Arial', 11), 
                    bg='white', fg='#34495e', justify='left').pack(anchor='w')
            
            # Cover letter
            tk.Label(details_frame, text="Cover Letter:", font=('Arial', 12, 'bold'), 
                    bg='white', fg='#2c3e50').pack(anchor='w', pady=(10, 5))
            
            cover_text = scrolledtext.ScrolledText(details_frame, height=8, wrap='word', 
                                                  font=('Arial', 10), bg='#f8f9fa')
            cover_text.pack(fill='both', expand=True, pady=(0, 10))
            cover_text.insert('1.0', app_data[6] or "No cover letter provided.")
            cover_text.config(state='disabled')
            
            # Feedback (if any)
            if app_data[7]:  # Assuming feedback is at index 7
                tk.Label(details_frame, text="Feedback:", font=('Arial', 12, 'bold'), 
                        bg='white', fg='#2c3e50').pack(anchor='w', pady=(10, 5))
                
                feedback_text = scrolledtext.ScrolledText(details_frame, height=4, wrap='word', 
                                                        font=('Arial', 10), bg='#f8f9fa')
                feedback_text.pack(fill='x', pady=(0, 10))
                feedback_text.insert('1.0', app_data[7])
                feedback_text.config(state='disabled')
            
            # Close button
            tk.Button(popup, text="Close", command=popup.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 10), padx=20, pady=5, relief='flat').pack(pady=10)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading application details: {e}")
    
    def show_all_applications(self):
        """Show all applications (staff/admin view)"""
        self.clear_content()
        
        if not self.auth.check_permission('view_all_applications'):
            messagebox.showerror("Permission Error", "You don't have permission to view all applications.")
            return
        
        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))
        
        tk.Label(title_frame, text="All Applications", 
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')
        
        # Filter frame (multiple rows for different filters)
        filter_frame = tk.Frame(self.content_frame, bg='white')
        filter_frame.pack(fill='x', padx=20, pady=(0, 10))

        # Row 1: Status and Internship ID filters
        filter_row1 = tk.Frame(filter_frame, bg='white')
        filter_row1.pack(fill='x', pady=2)

        # Status filter
        tk.Label(filter_row1, text="Filter by Status:", font=('Arial', 10),
                bg='white', fg='#34495e').pack(side='left', padx=(0, 5))

        self.status_filter = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_row1, textvariable=self.status_filter,
                                   values=["All", "pending", "approved", "rejected"],
                                   font=('Arial', 9), state='readonly', width=12)
        status_combo.pack(side='left', padx=5)
        status_combo.bind('<<ComboboxSelected>>', lambda e: self.load_all_applications_data())

        # Internship ID filter
        tk.Label(filter_row1, text="Internship ID:", font=('Arial', 10),
                bg='white', fg='#34495e').pack(side='left', padx=(15, 5))

        self.internship_id_filter = tk.StringVar()
        internship_id_entry = ttk.Entry(filter_row1, textvariable=self.internship_id_filter,
                                        font=('Arial', 9), width=12)
        internship_id_entry.pack(side='left', padx=5)

        tk.Button(filter_row1, text="Filter by Internship",
                 command=self.filter_by_internship_id,
                 bg='#3498db', fg='white', font=('Arial', 9),
                 padx=8, pady=2, relief='flat').pack(side='left', padx=5)

        # Row 2: Student ID filter and controls
        filter_row2 = tk.Frame(filter_frame, bg='white')
        filter_row2.pack(fill='x', pady=2)

        # Student ID filter
        tk.Label(filter_row2, text="Filter by Student ID:", font=('Arial', 10),
                bg='white', fg='#34495e').pack(side='left', padx=(0, 5))

        self.student_id_filter = tk.StringVar()
        student_id_entry = ttk.Entry(filter_row2, textvariable=self.student_id_filter,
                                     font=('Arial', 9), width=12)
        student_id_entry.pack(side='left', padx=5)

        tk.Button(filter_row2, text="Filter by Student",
                 command=self.filter_by_student_id,
                 bg='#9b59b6', fg='white', font=('Arial', 9),
                 padx=8, pady=2, relief='flat').pack(side='left', padx=5)

        # Clear filters and refresh buttons
        tk.Button(filter_row2, text="Clear All Filters",
                 command=self.clear_all_filters,
                 bg='#e74c3c', fg='white', font=('Arial', 9),
                 padx=8, pady=2, relief='flat').pack(side='left', padx=(15, 5))

        refresh_btn = tk.Button(filter_row2, text="Refresh", command=self.load_all_applications_data,
                               bg='#27ae60', fg='white', font=('Arial', 9),
                               padx=8, pady=2, relief='flat')
        refresh_btn.pack(side='left', padx=5)
        
        # Create treeview for all applications
        tree_frame = tk.Frame(self.content_frame, bg='white')
        tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Scrollbars
        tree_scroll_y = tk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')
        
        tree_scroll_x = tk.Scrollbar(tree_frame, orient='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x')
        
        # Treeview
        columns = ('App ID', 'Student ID', 'Student Name', 'Internship', 'Company', 'Applied Date', 'Status')
        self.all_apps_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                         yscrollcommand=tree_scroll_y.set,
                                         xscrollcommand=tree_scroll_x.set)
        
        tree_scroll_y.config(command=self.all_apps_tree.yview)
        tree_scroll_x.config(command=self.all_apps_tree.xview)
        
        # Define headings
        for col in columns:
            self.all_apps_tree.heading(col, text=col)
            if col in ['App ID', 'Student ID']:
                self.all_apps_tree.column(col, width=80)
            elif col == 'Status':
                self.all_apps_tree.column(col, width=100)
            else:
                self.all_apps_tree.column(col, width=150)
        
        self.all_apps_tree.pack(fill='both', expand=True)
        
        # Load applications data
        self.load_all_applications_data()
        
        # Button frame
        btn_frame = tk.Frame(self.content_frame, bg='white')
        btn_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Button(btn_frame, text="View Details", command=self.view_all_app_details,
                 bg='#3498db', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
        
        if self.auth.check_permission('approve_applications'):
            tk.Button(btn_frame, text="Review Application", command=self.review_selected_application,
                     bg='#f39c12', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
    
    def load_all_applications_data(self):
        """Load all applications data with optional filters"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Clear existing data
            for item in self.all_apps_tree.get_children():
                self.all_apps_tree.delete(item)

            # Build query based on filters
            base_query = '''
            SELECT a.application_id, a.student_id, s.first_name || ' ' || s.last_name,
                   i.title, i.company, a.application_date, a.status
            FROM internship_applications a
            JOIN students s ON a.student_id = s.student_id
            JOIN internships i ON a.internship_id = i.internship_id
            '''

            where_clauses = []
            params = []

            # Add status filter
            if hasattr(self, 'status_filter') and self.status_filter.get() != "All":
                where_clauses.append('a.status = ?')
                params.append(self.status_filter.get())

            # Add internship ID filter
            if hasattr(self, 'internship_id_filter') and self.internship_id_filter.get().strip():
                where_clauses.append('a.internship_id = ?')
                params.append(self.internship_id_filter.get().strip())

            # Add student ID filter
            if hasattr(self, 'student_id_filter') and self.student_id_filter.get().strip():
                where_clauses.append('a.student_id = ?')
                params.append(self.student_id_filter.get().strip())

            # Construct final query
            if where_clauses:
                query = base_query + ' WHERE ' + ' AND '.join(where_clauses) + ' ORDER BY a.application_date DESC'
                cursor.execute(query, params)
            else:
                cursor.execute(base_query + ' ORDER BY a.application_date DESC')

            applications = cursor.fetchall()

            # Insert data with color coding
            for app in applications:
                tags = []
                if app[6] == 'approved':
                    tags = ['approved']
                elif app[6] == 'rejected':
                    tags = ['rejected']
                elif app[6] == 'pending':
                    tags = ['pending']

                # Convert Row object to tuple for Treeview display
                values = tuple(app)
                self.all_apps_tree.insert('', 'end', values=values, tags=tags)

            # Configure tag colors
            self.all_apps_tree.tag_configure('approved', background='#d4edda')
            self.all_apps_tree.tag_configure('rejected', background='#f8d7da')
            self.all_apps_tree.tag_configure('pending', background='#fff3cd')

            conn.close()

            # Update status message
            filter_msg = []
            if hasattr(self, 'status_filter') and self.status_filter.get() != "All":
                filter_msg.append(f"Status: {self.status_filter.get()}")
            if hasattr(self, 'internship_id_filter') and self.internship_id_filter.get().strip():
                filter_msg.append(f"Internship ID: {self.internship_id_filter.get()}")
            if hasattr(self, 'student_id_filter') and self.student_id_filter.get().strip():
                filter_msg.append(f"Student ID: {self.student_id_filter.get()}")

            if filter_msg:
                messagebox.showinfo("Filter Applied",
                                  f"Showing {len(applications)} application(s)\nFilters: {', '.join(filter_msg)}")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading applications: {e}")

    def filter_by_internship_id(self):
        """Filter applications by internship ID"""
        internship_id = self.internship_id_filter.get().strip()

        if not internship_id:
            messagebox.showwarning("Input Required", "Please enter an Internship ID to filter.")
            return

        # Validate that internship exists
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT internship_id, title, company FROM internships WHERE internship_id = ?',
                          (internship_id,))
            internship = cursor.fetchone()

            conn.close()

            if not internship:
                messagebox.showerror("Invalid ID",
                                   f"No internship found with ID: {internship_id}")
                self.internship_id_filter.set("")
                return

            # Clear other filters to show only internship filter results
            if hasattr(self, 'student_id_filter'):
                self.student_id_filter.set("")

            # Load applications with this filter
            self.load_all_applications_data()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error validating internship ID: {e}")

    def filter_by_student_id(self):
        """Filter applications by student ID"""
        student_id = self.student_id_filter.get().strip()

        if not student_id:
            messagebox.showwarning("Input Required", "Please enter a Student ID to filter.")
            return

        # Validate that student exists
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT student_id, first_name, last_name FROM students WHERE student_id = ?',
                          (student_id,))
            student = cursor.fetchone()

            conn.close()

            if not student:
                messagebox.showerror("Invalid ID",
                                   f"No student found with ID: {student_id}")
                self.student_id_filter.set("")
                return

            # Clear other filters to show only student filter results
            if hasattr(self, 'internship_id_filter'):
                self.internship_id_filter.set("")

            # Load applications with this filter
            self.load_all_applications_data()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error validating student ID: {e}")

    def clear_all_filters(self):
        """Clear all application filters and reload all data"""
        # Reset all filter values
        if hasattr(self, 'status_filter'):
            self.status_filter.set("All")

        if hasattr(self, 'internship_id_filter'):
            self.internship_id_filter.set("")

        if hasattr(self, 'student_id_filter'):
            self.student_id_filter.set("")

        # Reload all applications
        self.load_all_applications_data()

        messagebox.showinfo("Filters Cleared", "All filters have been cleared. Showing all applications.")

    def view_all_app_details(self):
        """View details of selected application from all applications view"""
        selection = self.all_apps_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select an application to view.")
            return
        
        item = self.all_apps_tree.item(selection[0])
        app_id = item['values'][0]
        
        self.show_detailed_application_view(app_id)
    
    def show_detailed_application_view(self, app_id):
        """Show detailed application view for staff/admin"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT a.*, s.first_name, s.last_name, s.email_address, s.course,
                   i.title, i.company, i.location
            FROM internship_applications a
            JOIN students s ON a.student_id = s.student_id
            JOIN internships i ON a.internship_id = i.internship_id
            WHERE a.application_id = ?
            ''', (app_id,))
            
            app_data = cursor.fetchone()
            
            if not app_data:
                messagebox.showerror("Error", "Application not found.")
                conn.close()
                return
            
            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title("Application Review")
            popup.geometry("700x600")
            popup.configure(bg='white')
            popup.grab_set()
            
            # Title
            tk.Label(popup, text="Application Review", font=('Arial', 16, 'bold'), 
                    bg='white', fg='#2c3e50').pack(pady=10)
            
            # Create scrollable frame
            canvas = tk.Canvas(popup, bg='white')
            scrollbar = ttk.Scrollbar(popup, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg='white')
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Student info
            student_frame = tk.LabelFrame(scrollable_frame, text="Student Information", 
                                        font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            student_frame.pack(fill='x', padx=20, pady=10)
            
            student_info = f"""
Student ID: {app_data[1]}
Name: {app_data[7]} {app_data[8]}
Email: {app_data[9]}
Course: {app_data[10]}
"""
            tk.Label(student_frame, text=student_info, font=('Arial', 11), 
                    bg='white', fg='#34495e', justify='left').pack(anchor='w', padx=10, pady=5)
            
            # Internship info
            internship_frame = tk.LabelFrame(scrollable_frame, text="Internship Information", 
                                           font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            internship_frame.pack(fill='x', padx=20, pady=10)
            
            internship_info = f"""
Internship: {app_data[11]} at {app_data[12]}
Location: {app_data[13]}
Applied Date: {app_data[3]}
Current Status: {app_data[4].upper()}
CV Filename: {app_data[5]}
"""
            tk.Label(internship_frame, text=internship_info, font=('Arial', 11), 
                    bg='white', fg='#34495e', justify='left').pack(anchor='w', padx=10, pady=5)
            
            # Cover letter
            cover_frame = tk.LabelFrame(scrollable_frame, text="Cover Letter", 
                                      font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            cover_frame.pack(fill='x', padx=20, pady=10)
            
            cover_text = scrolledtext.ScrolledText(cover_frame, height=8, wrap='word', 
                                                  font=('Arial', 10), bg='#f8f9fa')
            cover_text.pack(fill='x', padx=10, pady=5)
            cover_text.insert('1.0', app_data[6] or "No cover letter provided.")
            cover_text.config(state='disabled')
            
            # Feedback section
            feedback_frame = tk.LabelFrame(scrollable_frame, text="Feedback", 
                                         font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            feedback_frame.pack(fill='x', padx=20, pady=10)
            
            if app_data[7]:  # If there's existing feedback
                existing_feedback = scrolledtext.ScrolledText(feedback_frame, height=4, wrap='word', 
                                                            font=('Arial', 10), bg='#f8f9fa')
                existing_feedback.pack(fill='x', padx=10, pady=5)
                existing_feedback.insert('1.0', app_data[7])
                existing_feedback.config(state='disabled')
            
            # Buttons
            btn_frame = tk.Frame(scrollable_frame, bg='white')
            btn_frame.pack(fill='x', padx=20, pady=20)
            
            tk.Button(btn_frame, text="Close", command=popup.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 10), padx=20, pady=5, relief='flat').pack(side='left', padx=5)
            
            if self.auth.check_permission('approve_applications'):
                tk.Button(btn_frame, text="Review/Update", 
                         command=lambda: self.open_review_dialog(app_id, popup),
                         bg='#f39c12', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
            
            # Pack canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
            scrollbar.pack(side="right", fill="y", pady=10)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading application details: {e}")
    
    def review_selected_application(self):
        """Review the selected application"""
        selection = self.all_apps_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select an application to review.")
            return
        
        item = self.all_apps_tree.item(selection[0])
        app_id = item['values'][0]
        
        self.open_review_dialog(app_id)
    
    def open_review_dialog(self, app_id, parent_window=None):
        """Open review dialog for an application"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT a.status, a.feedback, s.first_name, s.last_name, i.title, i.company
            FROM internship_applications a
            JOIN students s ON a.student_id = s.student_id
            JOIN internships i ON a.internship_id = i.internship_id
            WHERE a.application_id = ?
            ''', (app_id,))
            
            app_info = cursor.fetchone()
            
            if not app_info:
                messagebox.showerror("Error", "Application not found.")
                conn.close()
                return
            
            # Create review dialog
            review_dialog = tk.Toplevel(self.root)
            review_dialog.title("Review Application")
            review_dialog.geometry("650x550")
            review_dialog.configure(bg='white')
            review_dialog.grab_set()
            
            # Application info
            info_frame = tk.Frame(review_dialog, bg='white')
            info_frame.pack(fill='x', padx=20, pady=10)
            
            tk.Label(info_frame, text=f"Student: {app_info[2]} {app_info[3]}", 
                    font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50').pack(anchor='w')
            tk.Label(info_frame, text=f"Internship: {app_info[4]} at {app_info[5]}", 
                    font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w')
            tk.Label(info_frame, text=f"Current Status: {app_info[0].upper()}", 
                    font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', pady=(0, 10))
            
            # Status selection
            status_frame = tk.Frame(review_dialog, bg='white')
            status_frame.pack(fill='x', padx=20, pady=10)
            
            tk.Label(status_frame, text="New Status:", font=('Arial', 12, 'bold'), 
                    bg='white', fg='#2c3e50').pack(anchor='w')
            
            self.review_status = tk.StringVar(value=app_info[0])
            status_options = ['pending', 'approved', 'rejected']
            
            for status in status_options:
                tk.Radiobutton(status_frame, text=status.capitalize(), variable=self.review_status, 
                              value=status, font=('Arial', 10), bg='white', fg='#34495e').pack(anchor='w')
            
            # Feedback
            feedback_frame = tk.Frame(review_dialog, bg='white')
            feedback_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            tk.Label(feedback_frame, text="Feedback:", font=('Arial', 12, 'bold'), 
                    bg='white', fg='#2c3e50').pack(anchor='w')
            
            self.review_feedback = scrolledtext.ScrolledText(feedback_frame, height=8, wrap='word', 
                                                           font=('Arial', 10))
            self.review_feedback.pack(fill='both', expand=True, pady=5)
            
            if app_info[1]:
                self.review_feedback.insert('1.0', app_info[1])
            
            # Buttons
            btn_frame = tk.Frame(review_dialog, bg='white')
            btn_frame.pack(fill='x', padx=20, pady=10)
            
            tk.Button(btn_frame, text="Update Application", 
                     command=lambda: self.update_application_status(app_id, review_dialog, parent_window),
                     bg='#27ae60', fg='white', font=('Arial', 11, 'bold'), padx=20, pady=8, relief='flat').pack(side='left', padx=5)
            
            tk.Button(btn_frame, text="Cancel", command=review_dialog.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading application for review: {e}")
    
    def update_application_status(self, app_id, dialog, parent_window=None):
        """Update application status and feedback"""
        conn = None
        try:
            new_status = self.review_status.get()
            feedback = self.review_feedback.get('1.0', 'end-1c').strip()

            conn = get_connection()
            cursor = conn.cursor()

            # Update application
            cursor.execute('''
            UPDATE internship_applications
            SET status = ?, feedback = ?
            WHERE application_id = ?
            ''', (new_status, feedback, app_id))

            # Get application details for notifications
            cursor.execute('''
            SELECT student_id, internship_id FROM internship_applications
            WHERE application_id = ?
            ''', (app_id,))
            app_details = cursor.fetchone()

            # If approved, handle placement creation
            if new_status == 'approved' and app_details:
                # Check if placement already exists
                cursor.execute('''
                SELECT placement_id FROM internship_placements
                WHERE student_id = ? AND internship_id = ?
                ''', (app_details[0], app_details[1]))

                if not cursor.fetchone():
                    # Commit before opening placement dialog
                    conn.commit()
                    conn.close()
                    conn = None
                    # Create placement dialog
                    self.create_placement_dialog(app_details[0], app_details[1], dialog)
                    return

            conn.commit()
            conn.close()
            conn = None

            # Send internship status notification automatically
            if app_details:
                try:
                    from university_system.infrastructure.email.email_service import send_internship_notification
                    send_internship_notification(app_details[0], app_details[1], new_status, feedback)
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to send internship status notification: {e}")

            messagebox.showinfo("Success", f"Application status updated to: {new_status}")
            
            # Close dialogs and refresh
            dialog.destroy()
            if parent_window:
                parent_window.destroy()
            
            self.load_all_applications_data()

        except sqlite3.Error as e:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            messagebox.showerror("Database Error", f"Error updating application: {e}")

    def create_placement_dialog(self, student_id, internship_id, parent_dialog):
        """Create placement record dialog"""
        placement_dialog = tk.Toplevel(self.root)
        placement_dialog.title("Create Placement Record")
        placement_dialog.geometry("400x300")
        placement_dialog.configure(bg='white')
        placement_dialog.grab_set()
        
        tk.Label(placement_dialog, text="Create Placement Record", 
                font=('Arial', 14, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
        
        # Form fields
        form_frame = tk.Frame(placement_dialog, bg='white')
        form_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        tk.Label(form_frame, text="Supervisor Name:", font=('Arial', 11), 
                bg='white', fg='#34495e').pack(anchor='w')
        supervisor_name_entry = tk.Entry(form_frame, font=('Arial', 10), width=40)
        supervisor_name_entry.pack(anchor='w', pady=(0, 10))
        
        tk.Label(form_frame, text="Supervisor Email:", font=('Arial', 11), 
                bg='white', fg='#34495e').pack(anchor='w')
        supervisor_email_entry = tk.Entry(form_frame, font=('Arial', 10), width=40)
        supervisor_email_entry.pack(anchor='w', pady=(0, 10))
        
        # Buttons
        btn_frame = tk.Frame(form_frame, bg='white')
        btn_frame.pack(anchor='w', pady=20)
        
        def create_placement():
            supervisor_name = supervisor_name_entry.get().strip()
            supervisor_email = supervisor_email_entry.get().strip()
            
            if not supervisor_name or not supervisor_email:
                messagebox.showerror("Validation Error", "Please fill in all fields.")
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get internship dates
                cursor.execute('''
                SELECT start_date, end_date FROM internships
                WHERE internship_id = ?
                ''', (internship_id,))
                
                dates = cursor.fetchone()
                
                # Create placement
                cursor.execute('''
                INSERT INTO internship_placements (
                    student_id, internship_id, start_date, end_date,
                    supervisor_name, supervisor_email, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, internship_id, dates[0], dates[1],
                      supervisor_name, supervisor_email, 'active'))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Placement record created successfully!")
                placement_dialog.destroy()
                parent_dialog.destroy()
                self.load_all_applications_data()
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error creating placement: {e}")
        
        tk.Button(btn_frame, text="Create Placement", command=create_placement,
                 bg='#27ae60', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="Skip", command=lambda: [placement_dialog.destroy(), parent_dialog.destroy()],
                 bg='#6c757d', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
    
    def show_create_internship(self):
        """Show create internship form"""
        self.clear_content()
        
        if not self.auth.check_permission('create_internship'):
            messagebox.showerror("Permission Error", "You don't have permission to create internships.")
            return
        
        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))
        
        tk.Label(title_frame, text="Create New Internship", 
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')
        
        # Create scrollable form
        canvas = tk.Canvas(self.content_frame, bg='white')
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Form fields
        form_frame = tk.Frame(scrollable_frame, bg='white')
        form_frame.pack(fill='both', expand=True, padx=40, pady=20)
        
        # Basic Information
        basic_frame = tk.LabelFrame(form_frame, text="Basic Information", 
                                   font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
        basic_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(basic_frame, text="Title:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.title_entry = tk.Entry(basic_frame, font=('Arial', 10), width=50)
        self.title_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(basic_frame, text="Company:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.company_entry = tk.Entry(basic_frame, font=('Arial', 10), width=50)
        self.company_entry.grid(row=1, column=1, padx=10, pady=5)
        
        tk.Label(basic_frame, text="Location:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.location_entry = tk.Entry(basic_frame, font=('Arial', 10), width=50)
        self.location_entry.grid(row=2, column=1, padx=10, pady=5)
        
        tk.Label(basic_frame, text="Contact Email:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=3, column=0, sticky='w', padx=10, pady=5)
        self.contact_entry = tk.Entry(basic_frame, font=('Arial', 10), width=50)
        self.contact_entry.grid(row=3, column=1, padx=10, pady=5)
        
        # Description and Requirements
        desc_frame = tk.LabelFrame(form_frame, text="Description & Requirements", 
                                  font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
        desc_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(desc_frame, text="Description:", font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', padx=10, pady=(5, 0))
        self.description_text = scrolledtext.ScrolledText(desc_frame, height=4, wrap='word', font=('Arial', 10))
        self.description_text.pack(fill='x', padx=10, pady=5)
        
        tk.Label(desc_frame, text="Requirements:", font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', padx=10, pady=(5, 0))
        self.requirements_text = scrolledtext.ScrolledText(desc_frame, height=4, wrap='word', font=('Arial', 10))
        self.requirements_text.pack(fill='x', padx=10, pady=5)
        
        # Dates and Compensation
        details_frame = tk.LabelFrame(form_frame, text="Details", 
                                     font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
        details_frame.pack(fill='x', pady=(0, 15))
        
        # Date fields
        tk.Label(details_frame, text="Start Date (YYYY-MM-DD):", font=('Arial', 11), bg='white', fg='#34495e').grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.start_date_entry = tk.Entry(details_frame, font=('Arial', 10), width=20)
        self.start_date_entry.grid(row=0, column=1, padx=10, pady=5, sticky='w')
        
        tk.Label(details_frame, text="End Date (YYYY-MM-DD):", font=('Arial', 11), bg='white', fg='#34495e').grid(row=0, column=2, sticky='w', padx=10, pady=5)
        self.end_date_entry = tk.Entry(details_frame, font=('Arial', 10), width=20)
        self.end_date_entry.grid(row=0, column=3, padx=10, pady=5, sticky='w')
        
        tk.Label(details_frame, text="Application Deadline (YYYY-MM-DD):", font=('Arial', 11), bg='white', fg='#34495e').grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.deadline_entry = tk.Entry(details_frame, font=('Arial', 10), width=20)
        self.deadline_entry.grid(row=1, column=1, padx=10, pady=5, sticky='w')
        
        tk.Label(details_frame, text="Hours per Week:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=1, column=2, sticky='w', padx=10, pady=5)
        self.hours_entry = tk.Entry(details_frame, font=('Arial', 10), width=20)
        self.hours_entry.grid(row=1, column=3, padx=10, pady=5, sticky='w')
        
        # Payment details
        payment_frame = tk.Frame(details_frame, bg='white')
        payment_frame.grid(row=2, column=0, columnspan=4, sticky='w', padx=10, pady=5)
        
        self.is_paid_var = tk.BooleanVar()
        tk.Checkbutton(payment_frame, text="Paid Internship", variable=self.is_paid_var, 
                      font=('Arial', 11), bg='white', fg='#34495e').pack(side='left')
        
        tk.Label(payment_frame, text="Salary/Stipend:", font=('Arial', 11), bg='white', fg='#34495e').pack(side='left', padx=(20, 5))
        self.salary_entry = tk.Entry(payment_frame, font=('Arial', 10), width=30)
        self.salary_entry.pack(side='left')
        
        # Course relevance
        relevance_frame = tk.Frame(details_frame, bg='white')
        relevance_frame.grid(row=3, column=0, columnspan=4, sticky='w', padx=10, pady=5)
        
        tk.Label(relevance_frame, text="Course Relevance:", font=('Arial', 11), bg='white', fg='#34495e').pack(side='left')
        
        self.course_var = tk.StringVar(value="All")
        course_options = [("Computer Science", "CS"), ("Data Science", "DS"), ("All Courses", "All")]
        
        for text, value in course_options:
            tk.Radiobutton(relevance_frame, text=text, variable=self.course_var, value=value,
                          font=('Arial', 10), bg='white', fg='#34495e').pack(side='left', padx=10)
        
        # Buttons
        btn_frame = tk.Frame(form_frame, bg='white')
        btn_frame.pack(fill='x', pady=20)
        
        tk.Button(btn_frame, text="Create Internship", command=self.create_new_internship,
                 bg='#27ae60', fg='white', font=('Arial', 12, 'bold'), padx=25, pady=10, relief='flat').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="Cancel", command=self.show_internships,
                 bg='#6c757d', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
    
    def create_new_internship(self):
        """Create a new internship"""
        try:
            # Validate required fields
            required_fields = [
                (self.title_entry.get().strip(), "Title"),
                (self.company_entry.get().strip(), "Company"),
                (self.location_entry.get().strip(), "Location"),
                (self.contact_entry.get().strip(), "Contact Email"),
                (self.start_date_entry.get().strip(), "Start Date"),
                (self.end_date_entry.get().strip(), "End Date"),
                (self.deadline_entry.get().strip(), "Application Deadline"),
                (self.hours_entry.get().strip(), "Hours per Week"),
                (self.salary_entry.get().strip(), "Salary/Stipend")
            ]
            
            for value, field_name in required_fields:
                if not value:
                    messagebox.showerror("Validation Error", f"Please fill in the {field_name} field.")
                    return
            
            # Validate dates
            try:
                start_date = datetime.strptime(self.start_date_entry.get().strip(), "%Y-%m-%d")
                end_date = datetime.strptime(self.end_date_entry.get().strip(), "%Y-%m-%d")
                deadline_date = datetime.strptime(self.deadline_entry.get().strip(), "%Y-%m-%d")
                
                if end_date <= start_date:
                    messagebox.showerror("Validation Error", "End date must be after start date.")
                    return
                
                if deadline_date >= start_date:
                    messagebox.showerror("Validation Error", "Application deadline must be before start date.")
                    return
                    
            except ValueError:
                messagebox.showerror("Validation Error", "Please enter valid dates in YYYY-MM-DD format.")
                return
            
            # Validate hours
            try:
                hours = int(self.hours_entry.get().strip())
                if hours <= 0:
                    messagebox.showerror("Validation Error", "Hours per week must be greater than 0.")
                    return
            except ValueError:
                messagebox.showerror("Validation Error", "Please enter a valid number for hours per week.")
                return
            
            # Get text fields
            description = self.description_text.get('1.0', 'end-1c').strip()
            requirements = self.requirements_text.get('1.0', 'end-1c').strip()
            
            if not description:
                messagebox.showerror("Validation Error", "Please provide a description.")
                return
            
            if not requirements:
                messagebox.showerror("Validation Error", "Please provide requirements.")
                return
            
            # Create internship in database
            conn = get_connection()
            cursor = conn.cursor()
            
            posted_date = datetime.now().strftime('%Y-%m-%d')
            created_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO internships (
                title, company, location, description, requirements,
                start_date, end_date, is_paid, salary, hours_per_week,
                posted_date, deadline_date, status, contact_email, course_relevance,
                created_by, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.title_entry.get().strip(),
                self.company_entry.get().strip(),
                self.location_entry.get().strip(),
                description,
                requirements,
                self.start_date_entry.get().strip(),
                self.end_date_entry.get().strip(),
                1 if self.is_paid_var.get() else 0,
                self.salary_entry.get().strip(),
                hours,
                posted_date,
                self.deadline_entry.get().strip(),
                'active',
                self.contact_entry.get().strip(),
                self.course_var.get(),
                self.auth.current_user['username'],
                created_date
            ))
            
            conn.commit()
            internship_id = cursor.lastrowid
            conn.close()

            # Send announcement email to all students
            self.send_new_internship_announcement(internship_id)

            messagebox.showinfo("Success", f"Internship created successfully! ID: {internship_id}")
            self.show_internships()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error creating internship: {e}")
    
    def show_manage_internships(self):
        """Show manage internships interface"""
        self.clear_content()
        
        if not self.auth.check_permission('edit_internship'):
            messagebox.showerror("Permission Error", "You don't have permission to manage internships.")
            return
        
        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))
        
        tk.Label(title_frame, text="Manage Internships", 
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')
        
        # Filter frame
        filter_frame = tk.Frame(title_frame, bg='white')
        filter_frame.pack(side='right')
        
        tk.Label(filter_frame, text="Filter by Status:", font=('Arial', 10), 
                bg='white', fg='#34495e').pack(side='left', padx=(0, 5))
        
        self.manage_status_filter = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.manage_status_filter, 
                                   values=["All", "active", "closed", "filled"],
                                   font=('Arial', 9), state='readonly', width=12)
        status_combo.pack(side='left', padx=5)
        status_combo.bind('<<ComboboxSelected>>', lambda e: self.load_manage_internships_data())
        
        refresh_btn = tk.Button(filter_frame, text="Refresh", command=self.load_manage_internships_data,
                               bg='#27ae60', fg='white', font=('Arial', 10), 
                               padx=10, pady=3, relief='flat')
        refresh_btn.pack(side='left', padx=5)
        
        # Create treeview for internships
        tree_frame = tk.Frame(self.content_frame, bg='white')
        tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Scrollbars
        tree_scroll_y = tk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')
        
        tree_scroll_x = tk.Scrollbar(tree_frame, orient='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x')
        
        # Treeview
        columns = ('ID', 'Title', 'Company', 'Location', 'Start Date', 'Deadline', 'Status', 'Applications')
        self.manage_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                       yscrollcommand=tree_scroll_y.set,
                                       xscrollcommand=tree_scroll_x.set)
        
        tree_scroll_y.config(command=self.manage_tree.yview)
        tree_scroll_x.config(command=self.manage_tree.xview)
        
        # Define headings
        for col in columns:
            self.manage_tree.heading(col, text=col)
            if col in ['ID', 'Applications']:
                self.manage_tree.column(col, width=80)
            elif col == 'Status':
                self.manage_tree.column(col, width=100)
            else:
                self.manage_tree.column(col, width=150)
        
        self.manage_tree.pack(fill='both', expand=True)
        
        # Load data
        self.load_manage_internships_data()
        
        # Button frame
        btn_frame = tk.Frame(self.content_frame, bg='white')
        btn_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Button(btn_frame, text="View Details", command=self.view_manage_internship_details,
                 bg='#3498db', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="Edit Internship", command=self.edit_selected_internship,
                 bg='#f39c12', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
        
        if self.auth.check_permission('delete_internship'):
            tk.Button(btn_frame, text="Delete Internship", command=self.delete_selected_internship,
                     bg='#e74c3c', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
    
    def load_manage_internships_data(self):
        """Load internships data for management"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Clear existing data
            for item in self.manage_tree.get_children():
                self.manage_tree.delete(item)
            
            # Build query based on filter
            base_query = '''
            SELECT i.internship_id, i.title, i.company, i.location, i.start_date, 
                   i.deadline_date, i.status, COUNT(a.application_id) as app_count
            FROM internships i
            LEFT JOIN internship_applications a ON i.internship_id = a.internship_id
            '''
            
            if self.manage_status_filter.get() != "All":
                cursor.execute(base_query + ' WHERE i.status = ? GROUP BY i.internship_id ORDER BY i.posted_date DESC', 
                              (self.manage_status_filter.get(),))
            else:
                cursor.execute(base_query + ' GROUP BY i.internship_id ORDER BY i.posted_date DESC')
            
            internships = cursor.fetchall()
            
            # Insert data with color coding
            for internship in internships:
                tags = []
                if internship[6] == 'active':
                    tags = ['active']
                elif internship[6] == 'closed':
                    tags = ['closed']
                elif internship[6] == 'filled':
                    tags = ['filled']

                # Convert Row object to tuple for Treeview display
                values = tuple(internship)
                self.manage_tree.insert('', 'end', values=values, tags=tags)
            
            # Configure tag colors
            self.manage_tree.tag_configure('active', background='#d4edda')
            self.manage_tree.tag_configure('closed', background='#f8d7da')
            self.manage_tree.tag_configure('filled', background='#fff3cd')
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading internships: {e}")
    
    def view_manage_internship_details(self):
        """View details of selected internship from manage view"""
        selection = self.manage_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select an internship to view.")
            return
        
        item = self.manage_tree.item(selection[0])
        internship_id = item['values'][0]
        
        self.show_internship_details(internship_id)
    
    def edit_selected_internship(self):
        """Edit the selected internship"""
        selection = self.manage_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select an internship to edit.")
            return
        
        item = self.manage_tree.item(selection[0])
        internship_id = item['values'][0]
        
        self.show_edit_internship_form(internship_id)
    
    def show_edit_internship_form(self, internship_id):
        """Show edit form for internship"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM internships WHERE internship_id = ?', (internship_id,))
            internship = cursor.fetchone()
            
            if not internship:
                messagebox.showerror("Error", "Internship not found.")
                conn.close()
                return
            
            # Create edit window
            edit_window = tk.Toplevel(self.root)
            edit_window.title(f"Edit Internship - {internship[1]}")
            edit_window.geometry("800x700")
            edit_window.configure(bg='white')
            edit_window.grab_set()
            
            # Title
            tk.Label(edit_window, text=f"Edit Internship: {internship[1]}", 
                    font=('Arial', 16, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
            
            # Create scrollable form
            canvas = tk.Canvas(edit_window, bg='white')
            scrollbar = ttk.Scrollbar(edit_window, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg='white')
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Form fields with current values
            form_frame = tk.Frame(scrollable_frame, bg='white')
            form_frame.pack(fill='both', expand=True, padx=40, pady=20)
            
            # Basic Information
            basic_frame = tk.LabelFrame(form_frame, text="Basic Information", 
                                       font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            basic_frame.pack(fill='x', pady=(0, 15))
            
            fields = {}
            
            tk.Label(basic_frame, text="Title:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=0, column=0, sticky='w', padx=10, pady=5)
            fields['title'] = tk.Entry(basic_frame, font=('Arial', 10), width=50)
            fields['title'].grid(row=0, column=1, padx=10, pady=5)
            fields['title'].insert(0, internship[1])
            
            tk.Label(basic_frame, text="Company:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=1, column=0, sticky='w', padx=10, pady=5)
            fields['company'] = tk.Entry(basic_frame, font=('Arial', 10), width=50)
            fields['company'].grid(row=1, column=1, padx=10, pady=5)
            fields['company'].insert(0, internship[2])
            
            tk.Label(basic_frame, text="Location:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=2, column=0, sticky='w', padx=10, pady=5)
            fields['location'] = tk.Entry(basic_frame, font=('Arial', 10), width=50)
            fields['location'].grid(row=2, column=1, padx=10, pady=5)
            fields['location'].insert(0, internship[3])
            
            tk.Label(basic_frame, text="Contact Email:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=3, column=0, sticky='w', padx=10, pady=5)
            fields['contact'] = tk.Entry(basic_frame, font=('Arial', 10), width=50)
            fields['contact'].grid(row=3, column=1, padx=10, pady=5)
            fields['contact'].insert(0, internship[14])
            
            # Status
            tk.Label(basic_frame, text="Status:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=4, column=0, sticky='w', padx=10, pady=5)
            status_var = tk.StringVar(value=internship[13])
            status_combo = ttk.Combobox(basic_frame, textvariable=status_var, 
                                       values=["active", "closed", "filled"],
                                       font=('Arial', 10), state='readonly', width=20)
            status_combo.grid(row=4, column=1, padx=10, pady=5, sticky='w')
            
            # Description and Requirements
            desc_frame = tk.LabelFrame(form_frame, text="Description & Requirements", 
                                      font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            desc_frame.pack(fill='x', pady=(0, 15))
            
            tk.Label(desc_frame, text="Description:", font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', padx=10, pady=(5, 0))
            fields['description'] = scrolledtext.ScrolledText(desc_frame, height=4, wrap='word', font=('Arial', 10))
            fields['description'].pack(fill='x', padx=10, pady=5)
            fields['description'].insert('1.0', internship[4])
            
            tk.Label(desc_frame, text="Requirements:", font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', padx=10, pady=(5, 0))
            fields['requirements'] = scrolledtext.ScrolledText(desc_frame, height=4, wrap='word', font=('Arial', 10))
            fields['requirements'].pack(fill='x', padx=10, pady=5)
            fields['requirements'].insert('1.0', internship[5])
            
            # Dates and other details
            details_frame = tk.LabelFrame(form_frame, text="Details", 
                                         font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            details_frame.pack(fill='x', pady=(0, 15))
            
            tk.Label(details_frame, text="Start Date:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=0, column=0, sticky='w', padx=10, pady=5)
            fields['start_date'] = tk.Entry(details_frame, font=('Arial', 10), width=20)
            fields['start_date'].grid(row=0, column=1, padx=10, pady=5, sticky='w')
            fields['start_date'].insert(0, internship[6])
            
            tk.Label(details_frame, text="End Date:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=0, column=2, sticky='w', padx=10, pady=5)
            fields['end_date'] = tk.Entry(details_frame, font=('Arial', 10), width=20)
            fields['end_date'].grid(row=0, column=3, padx=10, pady=5, sticky='w')
            fields['end_date'].insert(0, internship[7])
            
            tk.Label(details_frame, text="Deadline:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=1, column=0, sticky='w', padx=10, pady=5)
            fields['deadline'] = tk.Entry(details_frame, font=('Arial', 10), width=20)
            fields['deadline'].grid(row=1, column=1, padx=10, pady=5, sticky='w')
            fields['deadline'].insert(0, internship[12])
            
            tk.Label(details_frame, text="Hours/Week:", font=('Arial', 11), bg='white', fg='#34495e').grid(row=1, column=2, sticky='w', padx=10, pady=5)
            fields['hours'] = tk.Entry(details_frame, font=('Arial', 10), width=20)
            fields['hours'].grid(row=1, column=3, padx=10, pady=5, sticky='w')
            fields['hours'].insert(0, str(internship[10]))
            
            # Payment
            payment_frame = tk.Frame(details_frame, bg='white')
            payment_frame.grid(row=2, column=0, columnspan=4, sticky='w', padx=10, pady=5)
            
            is_paid_var = tk.BooleanVar(value=bool(internship[8]))
            tk.Checkbutton(payment_frame, text="Paid Internship", variable=is_paid_var, 
                          font=('Arial', 11), bg='white', fg='#34495e').pack(side='left')
            
            tk.Label(payment_frame, text="Salary:", font=('Arial', 11), bg='white', fg='#34495e').pack(side='left', padx=(20, 5))
            fields['salary'] = tk.Entry(payment_frame, font=('Arial', 10), width=30)
            fields['salary'].pack(side='left')
            fields['salary'].insert(0, internship[9])
            
            # Course relevance
            relevance_frame = tk.Frame(details_frame, bg='white')
            relevance_frame.grid(row=3, column=0, columnspan=4, sticky='w', padx=10, pady=5)
            
            tk.Label(relevance_frame, text="Course:", font=('Arial', 11), bg='white', fg='#34495e').pack(side='left')
            
            course_var = tk.StringVar(value=internship[15])
            for text, value in [("Computer Science", "CS"), ("Data Science", "DS"), ("All Courses", "All")]:
                tk.Radiobutton(relevance_frame, text=text, variable=course_var, value=value,
                              font=('Arial', 10), bg='white', fg='#34495e').pack(side='left', padx=10)
            
            # Buttons
            btn_frame = tk.Frame(form_frame, bg='white')
            btn_frame.pack(fill='x', pady=20)
            
            def save_changes():
                try:
                    # Validate dates
                    start_date = fields['start_date'].get().strip()
                    end_date = fields['end_date'].get().strip()
                    deadline = fields['deadline'].get().strip()
                    
                    datetime.strptime(start_date, "%Y-%m-%d")
                    datetime.strptime(end_date, "%Y-%m-%d")
                    datetime.strptime(deadline, "%Y-%m-%d")
                    
                    # Validate hours
                    hours = int(fields['hours'].get().strip())
                    
                    # Update database
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    UPDATE internships SET
                        title = ?, company = ?, location = ?, description = ?, requirements = ?,
                        start_date = ?, end_date = ?, is_paid = ?, salary = ?, hours_per_week = ?,
                        deadline_date = ?, status = ?, contact_email = ?, course_relevance = ?
                    WHERE internship_id = ?
                    ''', (
                        fields['title'].get().strip(),
                        fields['company'].get().strip(),
                        fields['location'].get().strip(),
                        fields['description'].get('1.0', 'end-1c').strip(),
                        fields['requirements'].get('1.0', 'end-1c').strip(),
                        start_date,
                        end_date,
                        1 if is_paid_var.get() else 0,
                        fields['salary'].get().strip(),
                        hours,
                        deadline,
                        status_var.get(),
                        fields['contact'].get().strip(),
                        course_var.get(),
                        internship_id
                    ))
                    
                    conn.commit()
                    conn.close()
                    
                    messagebox.showinfo("Success", "Internship updated successfully!")
                    edit_window.destroy()
                    self.load_manage_internships_data()
                    
                except ValueError as e:
                    messagebox.showerror("Validation Error", "Please check your date and number formats.")
                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Error updating internship: {e}")
            
            tk.Button(btn_frame, text="Save Changes", command=save_changes,
                     bg='#27ae60', fg='white', font=('Arial', 12, 'bold'), padx=20, pady=8, relief='flat').pack(side='left', padx=5)
            
            tk.Button(btn_frame, text="Cancel", command=edit_window.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 10), padx=15, pady=5, relief='flat').pack(side='left', padx=5)
            
            # Pack canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
            scrollbar.pack(side="right", fill="y", pady=10)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading internship for editing: {e}")
    
    def delete_selected_internship(self):
        """Delete the selected internship"""
        selection = self.manage_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select an internship to delete.")
            return
        
        item = self.manage_tree.item(selection[0])
        internship_id = item['values'][0]
        internship_title = item['values'][1]
        company = item['values'][2]
        
        # Confirm deletion
        result = messagebox.askyesno("Confirm Deletion", 
                                   f"Are you sure you want to delete '{internship_title}' at {company}?\n\n"
                                   "This will also delete all associated applications and placements.")
        
        if not result:
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Delete associated records
            cursor.execute('DELETE FROM internship_placements WHERE internship_id = ?', (internship_id,))
            cursor.execute('DELETE FROM internship_applications WHERE internship_id = ?', (internship_id,))
            cursor.execute('DELETE FROM internships WHERE internship_id = ?', (internship_id,))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"Internship '{internship_title}' deleted successfully!")
            self.load_manage_internships_data()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error deleting internship: {e}")
    
    def show_reports(self):
        """Show reports interface"""
        self.clear_content()
        
        if not self.auth.check_permission('view_internship_reports'):
            messagebox.showerror("Permission Error", "You don't have permission to view reports.")
            return
        
        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))
        
        tk.Label(title_frame, text="Internship Reports", 
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')
        
        # Report selection
        report_frame = tk.Frame(self.content_frame, bg='white')
        report_frame.pack(fill='x', padx=40, pady=20)
        
        tk.Label(report_frame, text="Select Report Type:", font=('Arial', 12, 'bold'), 
                bg='white', fg='#2c3e50').pack(anchor='w', pady=(0, 10))
        
        report_buttons = [
            ("Current Placements Summary", self.show_placements_report),
            ("Application Success Rate by Course", self.show_success_rate_report),
            ("Top Companies by Placements", self.show_companies_report),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]
        
        for text, command in report_buttons:
            tk.Button(report_frame, text=text, command=command,
                     bg='#3498db', fg='white', font=('Arial', 11), 
                     padx=20, pady=10, relief='flat', width=30).pack(pady=5, anchor='w')
        
        # Report display area
        self.report_display_frame = tk.Frame(self.content_frame, bg='white', relief='sunken', bd=1)
        self.report_display_frame.pack(fill='both', expand=True, padx=40, pady=20)
        
        # Default message
        tk.Label(self.report_display_frame, text="Select a report type above to view data.", 
                font=('Arial', 12), bg='white', fg='#7f8c8d').pack(expand=True)
    
    def clear_report_display(self):
        """Clear the report display area"""
        for widget in self.report_display_frame.winfo_children():
            widget.destroy()
    
    def show_placements_report(self):
        """Show current placements summary report"""
        self.clear_report_display()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT i.company, i.title, COUNT(p.placement_id) as placement_count,
                   GROUP_CONCAT(s.first_name || ' ' || s.last_name) as students
            FROM internship_placements p
            JOIN internships i ON p.internship_id = i.internship_id
            JOIN students s ON p.student_id = s.student_id
            WHERE p.status = 'active'
            GROUP BY i.company, i.title
            ORDER BY placement_count DESC
            ''')
            
            placements = cursor.fetchall()
            
            # Title
            tk.Label(self.report_display_frame, text="Current Placements Summary", 
                    font=('Arial', 16, 'bold'), bg='white', fg='#2c3e50').pack(pady=(10, 20))
            
            if not placements:
                tk.Label(self.report_display_frame, text="No active placements found.", 
                        font=('Arial', 12), bg='white', fg='#7f8c8d').pack()
                conn.close()
                return
            
            # Create treeview for report
            tree_frame = tk.Frame(self.report_display_frame, bg='white')
            tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            columns = ('Company', 'Internship Title', 'Students', 'Students Placed')
            report_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
            
            for col in columns:
                report_tree.heading(col, text=col)
                if col == 'Students Placed':
                    report_tree.column(col, width=120)
                elif col == 'Students':
                    report_tree.column(col, width=200)
                else:
                    report_tree.column(col, width=180)
            
            # Insert data
            total_placements = 0
            for placement in placements:
                students_list = placement[3].split(',') if placement[3] else []
                students_display = ', '.join(students_list[:3])
                if len(students_list) > 3:
                    students_display += f" (+{len(students_list) - 3} more)"
                
                report_tree.insert('', 'end', values=(placement[0], placement[1], students_display, placement[2]))
                total_placements += placement[2]
            
            report_tree.pack(fill='both', expand=True)
            
            # Summary
            summary_frame = tk.Frame(self.report_display_frame, bg='#ecf0f1')
            summary_frame.pack(fill='x', padx=20, pady=10)
            
            tk.Label(summary_frame, text=f"Total Active Placements: {total_placements}", 
                    font=('Arial', 12, 'bold'), bg='#ecf0f1', fg='#2c3e50').pack(pady=10)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error generating placements report: {e}")
    
    def show_success_rate_report(self):
        """Show application success rate by course report"""
        self.clear_report_display()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT s.course,
                   COUNT(a.application_id) as total_applications,
                   SUM(CASE WHEN a.status = 'approved' THEN 1 ELSE 0 END) as approved_applications,
                   SUM(CASE WHEN a.status = 'pending' THEN 1 ELSE 0 END) as pending_applications,
                   SUM(CASE WHEN a.status = 'rejected' THEN 1 ELSE 0 END) as rejected_applications,
                   ROUND(100.0 * SUM(CASE WHEN a.status = 'approved' THEN 1 ELSE 0 END) / COUNT(a.application_id), 2) as success_rate
            FROM internship_applications a
            JOIN students s ON a.student_id = s.student_id
            GROUP BY s.course
            ORDER BY success_rate DESC
            ''')
            
            rates = cursor.fetchall()
            
            # Title
            tk.Label(self.report_display_frame, text="Application Success Rate by Course", 
                    font=('Arial', 16, 'bold'), bg='white', fg='#2c3e50').pack(pady=(10, 20))
            
            if not rates:
                tk.Label(self.report_display_frame, text="No application data found.", 
                        font=('Arial', 12), bg='white', fg='#7f8c8d').pack()
                conn.close()
                return
            
            # Create treeview for report
            tree_frame = tk.Frame(self.report_display_frame, bg='white')
            tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            columns = ('Course', 'Total Apps', 'Approved', 'Pending', 'Rejected', 'Success Rate (%)')
            report_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
            
            for col in columns:
                report_tree.heading(col, text=col)
                report_tree.column(col, width=120)
            
            # Insert data with color coding
            for rate in rates:
                # Convert sqlite3.Row to tuple for display
                rate_values = tuple(rate)
                tags = []
                success_rate = rate_values[5] if rate_values[5] is not None else 0
                if success_rate >= 70:
                    tags = ['high']
                elif success_rate >= 50:
                    tags = ['medium']
                else:
                    tags = ['low']

                report_tree.insert('', 'end', values=rate_values, tags=tags)
            
            # Configure tag colors
            report_tree.tag_configure('high', background='#d4edda')
            report_tree.tag_configure('medium', background='#fff3cd')
            report_tree.tag_configure('low', background='#f8d7da')
            
            report_tree.pack(fill='both', expand=True)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error generating success rate report: {e}")
    
    def show_companies_report(self):
        """Show top companies by placements report"""
        self.clear_report_display()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT i.company,
                   COUNT(p.placement_id) as placement_count,
                   COUNT(DISTINCT i.internship_id) as internship_count,
                   GROUP_CONCAT(DISTINCT i.title) as internship_titles
            FROM internship_placements p
            JOIN internships i ON p.internship_id = i.internship_id
            GROUP BY i.company
            ORDER BY placement_count DESC
            LIMIT 10
            ''')
            
            companies = cursor.fetchall()
            
            # Title
            tk.Label(self.report_display_frame, text="Top Companies by Placement Count", 
                    font=('Arial', 16, 'bold'), bg='white', fg='#2c3e50').pack(pady=(10, 20))
            
            if not companies:
                tk.Label(self.report_display_frame, text="No placement data found.", 
                        font=('Arial', 12), bg='white', fg='#7f8c8d').pack()
                conn.close()
                return
            
            # Create treeview for report
            tree_frame = tk.Frame(self.report_display_frame, bg='white')
            tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            columns = ('Rank', 'Company', 'Placements', 'Internships', 'Internship Types')
            report_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=12)
            
            for col in columns:
                report_tree.heading(col, text=col)
                if col == 'Rank':
                    report_tree.column(col, width=60)
                elif col == 'Internship Types':
                    report_tree.column(col, width=250)
                else:
                    report_tree.column(col, width=120)
            
            # Insert data
            for i, company in enumerate(companies, 1):
                titles = company[3]
                if len(titles) > 60:
                    titles = titles[:57] + "..."
                
                values = (i, company[0], company[1], company[2], titles)
                report_tree.insert('', 'end', values=values)
            
            report_tree.pack(fill='both', expand=True)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error generating companies report: {e}")
    
    def show_status_overview_report(self):
        """Show application status overview report"""
        self.clear_report_display()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get overall statistics
            cursor.execute('''
            SELECT 
                COUNT(*) as total_applications,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
            FROM internship_applications
            ''')
            
            overall_stats = cursor.fetchone()
            
            # Get monthly trends
            cursor.execute('''
            SELECT 
                strftime('%Y-%m', application_date) as month,
                COUNT(*) as applications,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved
            FROM internship_applications
            WHERE application_date >= date('now', '-6 months')
            GROUP BY strftime('%Y-%m', application_date)
            ORDER BY month
            ''')
            
            monthly_trends = cursor.fetchall()
            
            # Title
            tk.Label(self.report_display_frame, text="Application Status Overview", 
                    font=('Arial', 16, 'bold'), bg='white', fg='#2c3e50').pack(pady=(10, 20))
            
            # Overall statistics
            stats_frame = tk.LabelFrame(self.report_display_frame, text="Overall Statistics", 
                                       font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
            stats_frame.pack(fill='x', padx=20, pady=10)
            
            stats_grid = tk.Frame(stats_frame, bg='white')
            stats_grid.pack(fill='x', padx=20, pady=10)
            
            # Create colored boxes for statistics
            stat_boxes = [
                ("Total Applications", overall_stats[0], "#3498db"),
                ("Pending", overall_stats[1], "#f39c12"),
                ("Approved", overall_stats[2], "#27ae60"),
                ("Rejected", overall_stats[3], "#e74c3c")
            ]
            
            for i, (label, value, color) in enumerate(stat_boxes):
                box_frame = tk.Frame(stats_grid, bg=color, relief='raised', bd=2)
                box_frame.grid(row=0, column=i, padx=10, pady=5, sticky='ew')
                
                tk.Label(box_frame, text=str(value), font=('Arial', 18, 'bold'), 
                        bg=color, fg='white').pack(pady=(10, 0))
                tk.Label(box_frame, text=label, font=('Arial', 10), 
                        bg=color, fg='white').pack(pady=(0, 10))
            
            # Configure grid weights
            for i in range(4):
                stats_grid.columnconfigure(i, weight=1)
            
            # Monthly trends
            if monthly_trends:
                trends_frame = tk.LabelFrame(self.report_display_frame, text="Monthly Trends (Last 6 Months)", 
                                           font=('Arial', 12, 'bold'), bg='white', fg='#2c3e50')
                trends_frame.pack(fill='both', expand=True, padx=20, pady=10)
                
                # Create treeview for trends
                tree_frame = tk.Frame(trends_frame, bg='white')
                tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
                
                columns = ('Month', 'Applications', 'Approved', 'Approval Rate (%)')
                trends_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=8)
                
                for col in columns:
                    trends_tree.heading(col, text=col)
                    trends_tree.column(col, width=150)
                
                # Insert trends data
                for trend in monthly_trends:
                    approval_rate = round(100 * trend[2] / trend[1], 2) if trend[1] > 0 else 0
                    trends_tree.insert('', 'end', values=(trend[0], trend[1], trend[2], approval_rate))
                
                trends_tree.pack(fill='both', expand=True)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error generating status overview report: {e}")
    
    def launch_cli_mode(self):
        """Launch the CLI version for backward compatibility"""
        # Hide the GUI window
        self.root.withdraw()
        
        try:
            # Import and run the original CLI function
            display_internship_menu()
        except Exception as e:
            messagebox.showerror("CLI Mode Error", f"Error launching CLI mode: {e}")
        finally:
            # Show the GUI window again
            self.root.deiconify()

    # =========================================================================
    # EMAIL INTEGRATION METHODS
    # =========================================================================

    def send_new_internship_announcement(self, internship_id, internship_title, company_name, description, requirements):
        """Send email to all students about new internship"""
        try:
            from university_system.infrastructure.email.email_service import send_template_email

            # Get all student emails
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT email, first_name, last_name
                FROM students
                WHERE email IS NOT NULL AND email != ""
            ''')
            students = cursor.fetchall()
            conn.close()

            for email, first_name, last_name in students:
                try:
                    template_vars = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "internship_title": internship_title,
                        "company_name": company_name,
                        "internship_id": internship_id,
                        "description": description,
                        "requirements": requirements
                    }
                    send_template_email('internships/internship_opportunity', email, template_vars)
                except Exception as e:
                    print(f"Failed to send announcement to {email}: {e}")

            print(f"New internship announcement sent to {len(students)} students")

        except Exception as e:
            print(f"Failed to send new internship announcements: {e}")

    def send_application_confirmation(self, student_email, student_name, internship_title, company_name, action_type="applied"):
        """Send confirmation email when student applies for or deletes internship application"""
        try:
            from university_system.infrastructure.email.email_service import send_template_email

            if action_type == "applied":
                template_name="internships/internship_application_confirmation"
                action_text = "submitted"
                status_text = "Your application has been successfully submitted and is now under review."
                next_steps = """What happens next:
• Your application will be reviewed by our career services team
• We'll check your academic eligibility
• If eligible, your application will be forwarded to the company
• You'll receive updates via email on your application status"""
            else:  # deleted/withdrawn
                template_name="internships/internship_application_withdrawn"
                action_text = "withdrawn"
                status_text = "Your application has been successfully withdrawn."
                next_steps = """You can still:
• Apply for other available internships
• Reapply for this position if it's still open
• Contact career services if you need assistance"""

            template_vars = {
                "student_name": student_name,
                "internship_title": internship_title,
                "company_name": company_name,
                "action_text": action_text,
                "status_text": status_text,
                "next_steps": next_steps,
                "action_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            send_template_email(template_name, student_email, template_vars)
            messagebox.showinfo("Email Sent", f"Confirmation email sent to {student_name}")

        except Exception as e:
            print(f"Failed to send application confirmation: {e}")

    def send_application_decision(self, student_email, student_name, internship_title, company_name, decision, reason=""):
        """Send email notification for application acceptance or rejection"""
        try:
            from university_system.infrastructure.email.email_service import send_template_email

            if decision.lower() == "accepted":
                template_name="internships/internship_application_accepted"
            else:  # rejected or update
                template_name="internships/internship_application_update"

            template_vars = {
                "student_name": student_name,
                "internship_title": internship_title,
                "company_name": company_name,
                "decision": decision,
                "reason": reason if reason else "",
                "decision_date": datetime.now().strftime('%Y-%m-%d')
            }

            send_template_email(template_name, student_email, template_vars)
            messagebox.showinfo("Decision Email Sent", f"Application decision sent to {student_name}")

        except Exception as e:
            print(f"Failed to send application decision: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email via email manager GUI"""
        try:
            from university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
            email_gui = EmailManagerGUI(self.root, auth=self.auth)

            if hasattr(email_gui, 'send_email'):
                email_gui.send_email(to_email=to_email, subject=subject, message=message)
                return True
            return False
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_email_fallback(self, email, subject, message, email_type):
        """Show fallback dialog for email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title(f"{email_type} Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.root)

            tk.Label(fallback_window,
                    text=f"Email system unavailable. Please manually send this {email_type.lower()}:",
                    font=('Arial', 10, 'bold')).pack(pady=10)

            details_frame = tk.Frame(fallback_window)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            details_text = scrolledtext.ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            tk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show email fallback: {e}")

    # =========================================================================
    # GRADE INTEGRATION METHODS
    # =========================================================================

    def check_student_eligibility(self, student_id, min_gpa=2.5, required_courses=None):
        """Check if student meets academic requirements for internship"""
        try:
            # Connect to database to get student grades
            conn = get_connection()
            cursor = conn.cursor()

            # Get student's overall GPA
            cursor.execute('''
                SELECT AVG(
                    CASE grade
                        WHEN 'A+' THEN 4.3
                        WHEN 'A' THEN 4.0
                        WHEN 'A-' THEN 3.7
                        WHEN 'B+' THEN 3.3
                        WHEN 'B' THEN 3.0
                        WHEN 'B-' THEN 2.7
                        WHEN 'C+' THEN 2.3
                        WHEN 'C' THEN 2.0
                        WHEN 'C-' THEN 1.7
                        WHEN 'D+' THEN 1.3
                        WHEN 'D' THEN 1.0
                        WHEN 'F' THEN 0.0
                        ELSE 0.0
                    END
                ) as gpa
                FROM student_grades sg
                JOIN students s ON sg.student_id = s.student_id
                WHERE s.student_id = ? AND sg.grade IS NOT NULL
            ''', (student_id,))

            gpa_result = cursor.fetchone()
            current_gpa = gpa_result[0] if gpa_result and gpa_result[0] else 0.0

            # Check if GPA meets minimum requirement
            gpa_meets_requirement = current_gpa >= min_gpa

            # Get student details for display
            cursor.execute('''
                SELECT first_name, last_name, email, course_year
                FROM students
                WHERE student_id = ?
            ''', (student_id,))

            student_result = cursor.fetchone()
            if not student_result:
                conn.close()
                return False, "Student not found"

            first_name, last_name, email, course_year = student_result

            # Check specific course requirements if provided
            courses_met = True
            missing_courses = []

            if required_courses:
                for course in required_courses:
                    cursor.execute('''
                        SELECT grade
                        FROM student_grades sg
                        JOIN course_modules cm ON sg.module_id = cm.module_id
                        WHERE sg.student_id = ? AND cm.module_name LIKE ?
                        AND sg.grade NOT IN ('F', 'Fail')
                    ''', (student_id, f"%{course}%"))

                    if not cursor.fetchone():
                        courses_met = False
                        missing_courses.append(course)

            conn.close()

            # Prepare eligibility result
            eligible = gpa_meets_requirement and courses_met

            eligibility_info = {
                'eligible': eligible,
                'student_name': f"{first_name} {last_name}",
                'student_email': email,
                'course_year': course_year,
                'current_gpa': round(current_gpa, 2),
                'min_gpa_required': min_gpa,
                'gpa_meets_requirement': gpa_meets_requirement,
                'courses_met': courses_met,
                'missing_courses': missing_courses
            }

            return eligible, eligibility_info

        except Exception as e:
            print(f"Error checking student eligibility: {e}")
            return False, f"Error checking eligibility: {e}"

    def show_eligibility_dialog(self, student_id, internship_title, requirements=""):
        """Show detailed eligibility information for student"""
        try:
            # Parse requirements to extract GPA and courses
            min_gpa = 2.5  # Default
            required_courses = []

            if requirements:
                # Simple parsing for GPA requirement
                if "GPA" in requirements.upper() or "gpa" in requirements:
                    import re
                    gpa_match = re.search(r'(\d+\.?\d*)\s*GPA', requirements, re.IGNORECASE)
                    if gpa_match:
                        min_gpa = float(gpa_match.group(1))

                # Simple parsing for course requirements
                if "course" in requirements.lower():
                    # Extract potential course names (simplified)
                    course_keywords = ["programming", "computer science", "mathematics", "statistics", "engineering"]
                    for keyword in course_keywords:
                        if keyword.lower() in requirements.lower():
                            required_courses.append(keyword)

            eligible, eligibility_info = self.check_student_eligibility(student_id, min_gpa, required_courses)

            # Create eligibility dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Eligibility Check: {internship_title}")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = tk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            title_label = tk.Label(main_frame, text=f"Eligibility Assessment",
                                  font=('Arial', 14, 'bold'))
            title_label.pack(pady=10)

            if isinstance(eligibility_info, str):
                # Error case
                error_label = tk.Label(main_frame, text=eligibility_info,
                                      font=('Arial', 12), fg='red')
                error_label.pack(pady=20)
            else:
                # Success case - show detailed info
                info_text = scrolledtext.ScrolledText(main_frame, height=15, width=70)
                info_text.pack(fill='both', expand=True, pady=10)

                status_color = "green" if eligible else "red"
                status_text = "✅ ELIGIBLE" if eligible else "❌ NOT ELIGIBLE"

                details = f"""ELIGIBILITY STATUS: {status_text}

Student: {eligibility_info['student_name']}
Course Year: {eligibility_info['course_year']}
Position: {internship_title}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACADEMIC REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GPA Requirement:
• Required: {eligibility_info['min_gpa_required']} or higher
• Current: {eligibility_info['current_gpa']}
• Status: {"✅ Met" if eligibility_info['gpa_meets_requirement'] else "❌ Not Met"}

Course Requirements:
• Status: {"✅ All requirements met" if eligibility_info['courses_met'] else "❌ Missing requirements"}"""

                if eligibility_info['missing_courses']:
                    details += f"\n• Missing: {', '.join(eligibility_info['missing_courses'])}"

                if not eligible:
                    details += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nRECOMMendations:\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                    if not eligibility_info['gpa_meets_requirement']:
                        details += f"• Improve your GPA to at least {eligibility_info['min_gpa_required']}\n"

                    if eligibility_info['missing_courses']:
                        details += f"• Complete required courses: {', '.join(eligibility_info['missing_courses'])}\n"

                    details += "• Consider academic support and tutoring services\n"
                    details += "• Speak with your academic advisor for guidance\n"

                info_text.insert('1.0', details)
                info_text.config(state='disabled')

            # Buttons
            button_frame = tk.Frame(main_frame)
            button_frame.pack(pady=20)

            if eligible:
                tk.Button(button_frame, text="✅ Proceed with Application",
                         command=lambda: [dialog.destroy(), self.show_application_form()],
                         bg='green', fg='white', font=('Arial', 10, 'bold')).pack(side='left', padx=5)

            tk.Button(button_frame, text="View Full Grade Report",
                     command=lambda: self.open_grade_report(student_id)).pack(side='left', padx=5)
            tk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not check eligibility: {e}")

    def show_my_eligibility(self):
        """Show eligibility check dialog for current student - allows selecting an internship"""
        try:
            # Get current student's ID
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result or not result[0]:
                messagebox.showerror("Error", "Could not find your student record.")
                conn.close()
                return

            student_id = result[0]

            # Get available internships
            cursor.execute('''
                SELECT internship_id, title, company, requirements
                FROM internships
                WHERE status = 'active'
                ORDER BY title
            ''')
            internships = cursor.fetchall()
            conn.close()

            if not internships:
                messagebox.showinfo("No Internships", "There are no active internships available.")
                return

            # Create selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Check My Eligibility")
            dialog.geometry("500x300")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = tk.Frame(dialog, padx=20, pady=20)
            main_frame.pack(fill='both', expand=True)

            tk.Label(main_frame, text="Select an Internship to Check Eligibility",
                    font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            tk.Label(main_frame, text="Internship:",
                    font=('Arial', 11)).pack(anchor='w')

            internship_var = tk.StringVar()
            internship_combo = ttk.Combobox(main_frame, textvariable=internship_var,
                                           state='readonly', width=50)

            # Format options and store mapping
            options = []
            internship_map = {}
            for intern in internships:
                option_text = f"{intern[1]} at {intern[2]}"
                options.append(option_text)
                internship_map[option_text] = {
                    'id': intern[0],
                    'title': intern[1],
                    'requirements': intern[3] or ''
                }

            internship_combo['values'] = options
            if options:
                internship_combo.current(0)
            internship_combo.pack(fill='x', pady=10)

            def check_eligibility():
                selected = internship_var.get()
                if not selected:
                    messagebox.showwarning("Selection Required", "Please select an internship.")
                    return

                intern_info = internship_map[selected]
                dialog.destroy()
                self.show_eligibility_dialog(student_id, intern_info['title'], intern_info['requirements'])

            btn_frame = tk.Frame(main_frame)
            btn_frame.pack(pady=20)

            tk.Button(btn_frame, text="Check Eligibility",
                     command=check_eligibility,
                     bg='#9b59b6', fg='white', font=('Arial', 11, 'bold'),
                     padx=20, pady=8).pack(side='left', padx=5)

            tk.Button(btn_frame, text="Cancel",
                     command=dialog.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 11),
                     padx=20, pady=8).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not open eligibility check: {e}")

    def open_grade_report(self, student_id):
        """Open the grade management GUI for detailed grade view"""
        try:
            from university_system.modules.domain.academics.gui.grade_management_gui import GradeManagementGUI

            grade_window = tk.Toplevel(self.root)
            grade_window.title("Student Grade Report")
            grade_window.geometry("1000x700")

            grade_gui = GradeManagementGUI(grade_window, auth=self.auth)

            # Pre-filter for specific student if method exists
            if hasattr(grade_gui, 'filter_student_grades'):
                grade_gui.filter_student_grades(student_id)

            messagebox.showinfo("Grade Report", f"Grade report opened for student ID: {student_id}")

        except ImportError:
            messagebox.showerror("Error", "Grade management system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open grade system: {e}")

    def check_eligibility_before_application(self, internship_id):
        """Check eligibility before allowing application"""
        try:
            # Get current student ID
            if not self.auth or not self.auth.current_user:
                messagebox.showerror("Error", "Please log in to apply for internships")
                return False

            # Get student ID from auth
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_id FROM students s
                JOIN users u ON s.user_id = u.id
                WHERE u.username = ?
            ''', (self.auth.current_user['username'],))

            student_result = cursor.fetchone()
            if not student_result:
                messagebox.showerror("Error", "Student record not found")
                conn.close()
                return False

            student_id = student_result[0]

            # Get internship requirements
            cursor.execute('''
                SELECT title, requirements FROM internships WHERE id = ?
            ''', (internship_id,))

            internship_result = cursor.fetchone()
            conn.close()

            if not internship_result:
                messagebox.showerror("Error", "Internship not found")
                return False

            internship_title, requirements = internship_result

            # Show eligibility dialog
            self.show_eligibility_dialog(student_id, internship_title, requirements or "")

            return True

        except Exception as e:
            messagebox.showerror("Error", f"Could not check eligibility: {e}")
            return False

    def show_integration_menu(self):
        """Show integration services menu"""
        self.clear_content()

        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))

        tk.Label(title_frame, text="Integration Services",
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')

        # Create main content frame
        main_frame = tk.Frame(self.content_frame, bg='white')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Grade Management Integration
        grade_frame = tk.LabelFrame(main_frame, text="Grade Management",
                                   font=('Arial', 14, 'bold'), bg='white', fg='#2c3e50',
                                   padx=10, pady=10)
        grade_frame.pack(fill='x', pady=(0, 15))

        tk.Label(grade_frame, text="Check student grades and eligibility for internships",
                font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', pady=(0, 10))

        grade_btn_frame = tk.Frame(grade_frame, bg='white')
        grade_btn_frame.pack(anchor='w')

        if self.auth.check_permission('view_grades') or self.auth.check_permission('view_student_grades'):
            tk.Button(grade_btn_frame, text="View Student Grades",
                     command=self.open_grade_gui,
                     bg='#3498db', fg='white', font=('Arial', 10),
                     padx=15, pady=8, relief='flat').pack(side='left', padx=(0, 10))

        if self.auth.current_user.get('role') == 'student':
            tk.Button(grade_btn_frame, text="Check My Eligibility",
                     command=self.show_my_eligibility,
                     bg='#9b59b6', fg='white', font=('Arial', 10),
                     padx=15, pady=8, relief='flat').pack(side='left', padx=(0, 10))

        # Email Integration
        email_frame = tk.LabelFrame(main_frame, text="Email Management",
                                   font=('Arial', 14, 'bold'), bg='white', fg='#2c3e50',
                                   padx=10, pady=10)
        email_frame.pack(fill='x', pady=(0, 15))

        tk.Label(email_frame, text="Send notifications and manage email communications",
                font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', pady=(0, 10))

        email_btn_frame = tk.Frame(email_frame, bg='white')
        email_btn_frame.pack(anchor='w')

        tk.Button(email_btn_frame, text="Open Email Manager",
                 command=self.open_email_manager,
                 bg='#e74c3c', fg='white', font=('Arial', 10),
                 padx=15, pady=8, relief='flat').pack(side='left', padx=(0, 10))

        # Finance Integration
        finance_frame = tk.LabelFrame(main_frame, text="Finance Integration",
                                     font=('Arial', 14, 'bold'), bg='white', fg='#2c3e50',
                                     padx=10, pady=10)
        finance_frame.pack(fill='x', pady=(0, 15))

        tk.Label(finance_frame, text="Access financial services and payment systems",
                font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', pady=(0, 10))

        finance_btn_frame = tk.Frame(finance_frame, bg='white')
        finance_btn_frame.pack(anchor='w')

        tk.Button(finance_btn_frame, text="Open Finance System",
                 command=self.open_finance_gui,
                 bg='#27ae60', fg='white', font=('Arial', 10),
                 padx=15, pady=8, relief='flat').pack(side='left', padx=(0, 10))

    def open_email_manager(self):
        """Open email manager GUI"""
        try:
            from university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
            email_window = tk.Toplevel(self.root)
            email_window.title("Email Manager")
            email_window.geometry("800x600")
            email_gui = EmailManagerGUI(email_window, auth=self.auth)
        except ImportError:
            messagebox.showerror("Error", "Email Manager GUI not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening Email Manager: {e}")

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def open_finance_gui(self):
        """Open finance management GUI"""
        try:
            from university_system.modules.domain.finance.gui.finance import FinanceGUI
            finance_window = tk.Toplevel(self.root)
            finance_window.title("Finance Management")
            finance_window.geometry("1000x700")
            finance_gui = FinanceGUI(finance_window, auth=self.auth)
        except ImportError:
            messagebox.showerror("Error", "Finance GUI not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening Finance GUI: {e}")


# Backward compatibility - keep all original functions available
def launch_gui(auth_object=None):
    """Launch the GUI version of the internship management system"""
    root = tk.Tk()
    app = InternshipGUI(root, auth_object)
    root.mainloop()


# Main entry point that supports both CLI and GUI modes
def main(auth_object=None, mode='gui'):
    """
    Main entry point for the internship management system
    
    Args:
        auth_object: Authentication object from main system
        mode: 'gui' for GUI mode, 'cli' for CLI mode
    """
    if auth_object:
        set_auth(auth_object)
    
    if mode.lower() == 'gui':
        launch_gui(auth_object)
    else:
        display_internship_menu()


# For backward compatibility - original functions are still available
if __name__ == "__main__":
    # Default to GUI mode if run directly
    main(mode='gui')
