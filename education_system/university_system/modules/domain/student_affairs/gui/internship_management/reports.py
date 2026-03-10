from ._imports import messagebox, tk, ttk, sqlite3, get_connection


class ReportsMixin:
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
            ("\U0001f3e0 Return to Main Menu", self.return_to_main_menu)
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
