from education_system.university_system.modules.domain.student_affairs.gui.internship_management._imports import (
    _t, messagebox, scrolledtext, tk, ttk, sqlite3, get_connection,
)


class MyApplicationsMixin:
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
