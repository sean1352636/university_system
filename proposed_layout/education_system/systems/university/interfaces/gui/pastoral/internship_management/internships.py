from education_system.systems.university.interfaces.gui.pastoral.internship_management._imports import (
    _t, datetime, messagebox, scrolledtext, tk, ttk, sqlite3, get_connection,
)


class InternshipsBrowseMixin:
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
                from education_system.systems.university.infrastructure.email.email_service import send_application_confirmation
                send_application_confirmation(student_id, internship_id)
            except Exception as e:
                import logging
                logging.warning(f"Failed to send application confirmation email: {e}")

            messagebox.showinfo("Success", "Application submitted successfully!")
            self.show_my_applications()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error submitting application: {e}")
