from ._imports import (
    messagebox, scrolledtext, tk, ttk, sqlite3, get_connection,
)


class PlacementsMixin:
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
