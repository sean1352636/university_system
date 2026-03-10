from ._imports import (
    messagebox, scrolledtext, tk, ttk, sqlite3, get_connection,
)


class AdminApplicationsMixin:
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
                    from education_system.university_system.infrastructure.email.email_service import send_internship_notification
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
