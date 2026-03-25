from education_system.university_system.modules.domain.student_affairs.gui.internship_management._imports import (
    datetime, messagebox, scrolledtext, tk, ttk, sqlite3, get_connection,
)


class ManageInternshipsMixin:
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
