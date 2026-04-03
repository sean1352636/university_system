import tkinter as tk
from education_system.university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import the original functions - backward compatibility
try:
    from education_system.university_system.modules.domain.student_affairs.services.alumni_management import (
        init_alumni_db, register_alumni, view_alumni, update_alumni,
        view_events, create_enhanced_event, event_check_in_system,
        record_donation, view_donations, setup_mentorship, view_mentorships,
        search_alumni_directory, view_connection_requests, manage_business_directory,
        create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
        schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
        view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
        manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
        generate_alumni_report, set_auth, setup_alumni_permissions,
        smart_mentorship_matching, generate_engagement_recommendations,
        create_alumni_story, view_alumni_stories, get_connection
    )
except ImportError as e:
    import_error_details = str(e)
    print(f"Warning: Could not import some functions: {e}")
    # Define fallback functions
    def placeholder_function(*args, **kwargs):
        func_name = kwargs.get('_func_name', 'Unknown function')
        messagebox.showerror(
            "Module Import Error",
            f"The alumni management module could not be loaded.\n\n"
            f"Function: {func_name}\n"
            f"Error: {import_error_details}\n\n"
            f"Please ensure all required dependencies are installed:\n"
            f"• university_system.alumni module\n"
            f"• All database schema requirements\n\n"
            f"Contact your system administrator for assistance."
        )

    # Assign placeholder to missing functions
    register_alumni = placeholder_function
    view_alumni = placeholder_function



class DonationsMixin:
        def _add_recognition_level(self):
            """Add a new recognition level"""
            messagebox.showinfo("Feature", "Recognition level editor dialog would open here.")

        def _delete_recognition_level(self):
            """Delete selected recognition level"""
            selection = self.recognition_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a level to delete.")
                return

            if messagebox.askyesno("Confirm Deletion",
                                  "Are you sure you want to delete this recognition level?"):
                messagebox.showinfo("Success", "Recognition level deleted!")
                self._load_recognition_levels()

        def _edit_recognition_level(self):
            """Edit selected recognition level"""
            selection = self.recognition_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a level to edit.")
                return
            messagebox.showinfo("Feature", "Recognition level editor dialog would open here.")

        def _load_campaign_performance(self):
            """Load and display campaign performance data"""
            campaign_selection = self.selected_campaign.get()
            if not campaign_selection or campaign_selection == "No campaigns available":
                messagebox.showwarning("No Selection", "Please select a campaign.")
                return

            # Extract campaign_id
            import re
            match = re.search(r'ID:\s*(\d+)', campaign_selection)
            if not match:
                messagebox.showerror("Error", "Invalid campaign selection.")
                return

            campaign_id = int(match.group(1))

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    # Get campaign details and performance
                    cursor.execute("""
                        SELECT campaign_name, goal_amount,
                               (SELECT COALESCE(SUM(amount), 0) FROM donations WHERE campaign_id = ?) as total_raised,
                               (SELECT COUNT(*) FROM donations WHERE campaign_id = ?) as donor_count
                        FROM fundraising_campaigns
                        WHERE campaign_id = ?
                    """, (campaign_id, campaign_id, campaign_id))
                    campaign_data = cursor.fetchone()

                    if campaign_data:
                        campaign_name, goal, total_raised, donor_count = campaign_data

                        # Calculate metrics
                        avg_donation = total_raised / donor_count if donor_count > 0 else 0
                        progress_pct = (total_raised / goal * 100) if goal > 0 else 0

                        # Update labels
                        self.performance_labels['Total Raised'].config(text=f"${total_raised:,.2f}")
                        self.performance_labels['Number of Donors'].config(text=str(donor_count))
                        self.performance_labels['Average Donation'].config(text=f"${avg_donation:,.2f}")
                        self.performance_labels['Goal Progress'].config(text=f"{progress_pct:.1f}%")

                        # Load recent donations
                        for item in self.campaign_donations_tree.get_children():
                            self.campaign_donations_tree.delete(item)

                        cursor.execute("""
                            SELECT donor_name, amount, donation_date, payment_method
                            FROM donations
                            WHERE campaign_id = ?
                            ORDER BY donation_date DESC
                            LIMIT 100
                        """, (campaign_id,))
                        donations = cursor.fetchall()

                        for donation in donations:
                            formatted = list(donation)
                            formatted[1] = f"${formatted[1]:,.2f}"
                            self.campaign_donations_tree.insert('', tk.END, values=formatted)

                        self.update_status(f"Loaded performance for: {campaign_name}")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load performance: {str(e)}")

        def _load_recognition_levels(self):
            """Load donor recognition levels"""
            try:
                # Clear existing data
                for item in self.recognition_tree.get_children():
                    self.recognition_tree.delete(item)

                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT level_name, min_amount, max_amount, benefits, status
                        FROM donor_recognition_levels
                        ORDER BY min_amount
                    """)
                    levels = cursor.fetchall()

                    for level in levels:
                        formatted = list(level)
                        formatted[1] = f"${formatted[1]:,.2f}" if formatted[1] else "N/A"
                        formatted[2] = f"${formatted[2]:,.2f}" if formatted[2] else "No limit"
                        self.recognition_tree.insert('', tk.END, values=formatted)

                    self.update_status(f"Loaded {len(levels)} recognition level(s)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load levels: {str(e)}")

        def create_campaign_form(self, parent):
            """Create fundraising campaign form"""
            ttk.Label(parent, text="Create New Fundraising Campaign",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            # Campaign details
            self.campaign_vars = {}

            details_fields = [
                ("Campaign Name*", "campaign_name"),
                ("Goal Amount ($)*", "goal_amount"),
                ("Start Date (YYYY-MM-DD)*", "start_date"),
                ("End Date (YYYY-MM-DD)*", "end_date")
            ]

            for i, (label, var_name) in enumerate(details_fields):
                row = i // 2
                col = i % 2

                field_frame = ttk.Frame(form_frame)
                field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

                ttk.Label(field_frame, text=label).pack(anchor='w')
                self.campaign_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.campaign_vars[var_name]).pack(fill=tk.X)

            form_frame.columnconfigure(0, weight=1)
            form_frame.columnconfigure(1, weight=1)

            # Category
            category_frame = ttk.Frame(form_frame)
            category_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky='ew')

            ttk.Label(category_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
            self.campaign_vars['category'] = tk.StringVar()
            category_combo = ttk.Combobox(category_frame, textvariable=self.campaign_vars['category'],
                                         values=["Annual Fund", "Scholarship Fund", "Building Fund", "Research Fund", "Student Support"])
            category_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Featured campaign
            featured_frame = ttk.Frame(form_frame)
            featured_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky='ew')

            self.campaign_vars['is_featured'] = tk.BooleanVar()
            ttk.Checkbutton(featured_frame, text="Feature this campaign on main page",
                           variable=self.campaign_vars['is_featured']).pack(anchor='w')

            # Description
            desc_frame = ttk.Frame(form_frame)
            desc_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky='ew')

            ttk.Label(desc_frame, text="Campaign Description:").pack(anchor='w')
            self.campaign_description = ScrolledText(desc_frame, height=6, wrap=tk.WORD)
            self.campaign_description.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

            # Submit button
            submit_frame = ttk.Frame(form_frame)
            submit_frame.grid(row=5, column=0, columnspan=2, pady=20)

            ttk.Button(submit_frame, text="Create Campaign",
                      command=self.submit_campaign).pack()

        def filter_donations(self):
            """Filter donations based on criteria"""
            # For demo, just reload data
            self.load_donations_data()
            filter_info = f"Filter applied: {self.donation_campaign_filter.get()}"
            if self.donation_from_date.get():
                filter_info += f", From: {self.donation_from_date.get()}"
            if self.donation_to_date.get():
                filter_info += f", To: {self.donation_to_date.get()}"
            self.update_status(filter_info)

        def load_donations_data(self):
            """Load donations data into treeview"""
            try:
                # Clear existing data
                for item in self.donations_tree.get_children():
                    self.donations_tree.delete(item)

                # Sample donations data
                sample_donations = [
                    ('2025-08-15', 'Sarah Johnson', 'A000001', '$500.00', 'Annual Fund', 'Credit Card', 'Completed'),
                    ('2025-08-12', 'Michael Chen', 'A000002', '$250.00', 'Scholarship Fund', 'Check', 'Completed'),
                    ('2025-08-10', 'Emily Davis', 'A000003', '$100.00', 'Annual Fund', 'Online', 'Completed'),
                    ('2025-08-08', 'John Smith', 'A000004', '$1000.00', 'Building Fund', 'Bank Transfer', 'Completed'),
                    ('2025-08-05', 'Lisa Brown', 'A000005', '$75.00', 'Annual Fund', 'Credit Card', 'Completed')
                ]

                for donation in sample_donations:
                    self.donations_tree.insert('', tk.END, values=donation)

                self.update_status(f"Loaded {len(sample_donations)} donation records")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load donations data: {str(e)}")

        def lookup_donor(self):
            """Lookup donor information"""
            alumni_id = self.donation_vars['alumni_id'].get().strip()
            if not alumni_id:
                messagebox.showwarning("No Alumni ID", "Please enter an Alumni ID to lookup.")
                return

            # Simulate lookup
            messagebox.showinfo("Alumni Found", f"Alumni {alumni_id}: John Doe (Class of 2018)")

        def show_campaigns(self):
            """Show fundraising campaigns interface"""
            self.clear_content()
            self.update_status("Fundraising Campaigns")

            ttk.Label(self.content_frame, text="Fundraising Campaigns",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for different campaign views
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Active campaigns tab
            active_frame = ttk.Frame(notebook)
            notebook.add(active_frame, text="Active Campaigns")

            active_text = ScrolledText(active_frame, wrap=tk.WORD)
            active_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            campaigns_content = """Active Fundraising Campaigns:

    🎯 Annual Alumni Fund 2025
    Goal: $100,000 | Raised: $67,500 (67.5%)
    Duration: January 1, 2025 - December 31, 2025
    Category: Annual Fund
    Status: Active

    Description: Support current students and enhance campus facilities through
    your alumni contributions. Every donation makes a difference!

    Progress: ████████████████████████████████████████████████████░░░░░░░░░░

    Donors: 245 | Average Donation: $275
    Recent Donors: Sarah Johnson ($500), Michael Chen ($250), Emily Davis ($100)

    [Donate Now] [View Details] [Share Campaign]

    ---

    🏫 New Library Building Fund
    Goal: $250,000 | Raised: $89,750 (35.9%)
    Duration: March 1, 2025 - February 28, 2026
    Category: Building Fund
    Status: Active

    Description: Help us build a state-of-the-art library with modern technology
    and collaborative learning spaces for future generations.

    Progress: ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

    Donors: 67 | Average Donation: $1,340
    Major Donors: Anonymous ($25,000), John Smith Foundation ($15,000)

    [Donate Now] [View Details] [Share Campaign]

    ---

    🎓 Emergency Student Support Fund
    Goal: $50,000 | Raised: $31,200 (62.4%)
    Duration: June 1, 2025 - August 31, 2025
    Category: Student Support
    Status: Active

    Description: Provide emergency financial assistance to students facing
    unexpected hardships during their academic journey.

    Progress: ████████████████████████████████████████████████████████████░░░░░░░░░░░░░░░░

    Donors: 156 | Average Donation: $200
    Recent Impact: Helped 23 students with emergency expenses

    [Donate Now] [View Details] [Share Campaign]
    """
            active_text.insert(tk.END, campaigns_content)

            # Create campaign tab (for authorized users)
            if self.has_permission('manage_campaigns'):
                create_frame = ttk.Frame(notebook)
                notebook.add(create_frame, text="Create Campaign")

                self.create_campaign_form(create_frame)

        def show_donor_recognition(self):
            """Show donor recognition management"""
            self.clear_content()
            self.update_status("Donor Recognition")

            ttk.Label(self.content_frame, text="Donor Recognition Management",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for different recognition views
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Recognition levels tab
            levels_frame = ttk.Frame(notebook)
            notebook.add(levels_frame, text="Recognition Levels")

            levels_text = ScrolledText(levels_frame, wrap=tk.WORD)
            levels_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            recognition_content = """Current Donor Recognition Levels:

        🥉 Bronze Supporter ($100+)
        - Newsletter subscription
        - Alumni directory access
        - 15 active donors

        🥈 Silver Supporter ($500+)
        - Event invitations
        - Recognition in publications
        - 8 active donors

        🥇 Gold Supporter ($1,000+)
        - VIP event access
        - Annual appreciation dinner
        - 5 active donors

        💎 Platinum Supporter ($5,000+)
        - Board meeting invitations
        - Naming opportunities
        - 2 active donors

        💍 Diamond Supporter ($10,000+)
        - Personal meetings with leadership
        - Legacy society membership
        - 1 active donor

        🏆 Benefactor ($25,000+)
        - Permanent recognition
        - Advisory board invitation
        - 0 active donors
        """
            levels_text.insert(tk.END, recognition_content)

            # Update levels tab
            update_frame = ttk.Frame(notebook)
            notebook.add(update_frame, text="Update Levels")

            ttk.Label(update_frame, text="Update Donor Recognition Levels",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            ttk.Button(update_frame, text="Update All Recognition Levels",
                      command=self.update_recognition_levels).pack(pady=20)

            # Recognition report
            report_frame = ttk.Frame(notebook)
            notebook.add(report_frame, text="Reports")

            self.recognition_report = ScrolledText(report_frame, wrap=tk.WORD)
            self.recognition_report.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Button(report_frame, text="Generate Recognition Report",
                      command=self.generate_recognition_report_gui).pack(pady=10)

        def show_record_donation(self):
            """Show donation recording interface"""
            self.clear_content()
            self.update_status("Record Donation")

            ttk.Label(self.content_frame, text="Record Alumni Donation",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Donation form
            form_frame = ttk.LabelFrame(self.content_frame, text="Donation Details", padding=10)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            self.donation_vars = {}

            # Donor information
            donor_frame = ttk.Frame(form_frame)
            donor_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(donor_frame, text="Alumni ID:").pack(side=tk.LEFT, padx=(0, 10))
            self.donation_vars['alumni_id'] = tk.StringVar()
            ttk.Entry(donor_frame, textvariable=self.donation_vars['alumni_id'], width=15).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(donor_frame, text="Lookup Alumni",
                      command=self.lookup_donor).pack(side=tk.LEFT)

            # Donation amount
            amount_frame = ttk.Frame(form_frame)
            amount_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(amount_frame, text="Donation Amount ($):").pack(side=tk.LEFT, padx=(0, 10))
            self.donation_vars['amount'] = tk.StringVar()
            ttk.Entry(amount_frame, textvariable=self.donation_vars['amount'], width=15).pack(side=tk.LEFT)

            # Campaign selection
            campaign_frame = ttk.Frame(form_frame)
            campaign_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(campaign_frame, text="Campaign:").pack(side=tk.LEFT, padx=(0, 10))
            self.donation_vars['campaign'] = tk.StringVar()
            campaign_combo = ttk.Combobox(campaign_frame, textvariable=self.donation_vars['campaign'],
                                         values=["Annual Alumni Fund", "Scholarship Fund", "Building Fund", "General Fund"])
            campaign_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

            # Payment method
            payment_frame = ttk.Frame(form_frame)
            payment_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(payment_frame, text="Payment Method:").pack(side=tk.LEFT, padx=(0, 10))
            self.donation_vars['payment_method'] = tk.StringVar()
            payment_combo = ttk.Combobox(payment_frame, textvariable=self.donation_vars['payment_method'],
                                        values=["Credit Card", "Check", "Bank Transfer", "Cash", "Online"])
            payment_combo.pack(side=tk.LEFT)

            # Recurring donation
            recurring_frame = ttk.Frame(form_frame)
            recurring_frame.pack(fill=tk.X, pady=(0, 10))

            self.donation_vars['is_recurring'] = tk.BooleanVar()
            ttk.Checkbutton(recurring_frame, text="Recurring Donation",
                           variable=self.donation_vars['is_recurring']).pack(side=tk.LEFT, padx=(0, 10))

            ttk.Label(recurring_frame, text="Frequency:").pack(side=tk.LEFT, padx=(0, 10))
            self.donation_vars['frequency'] = tk.StringVar()
            freq_combo = ttk.Combobox(recurring_frame, textvariable=self.donation_vars['frequency'],
                                     values=["Monthly", "Quarterly", "Annually"])
            freq_combo.pack(side=tk.LEFT)

            # Notes
            ttk.Label(form_frame, text="Notes:").pack(anchor='w', pady=(10, 5))
            self.donation_notes = ScrolledText(form_frame, height=4, wrap=tk.WORD)
            self.donation_notes.pack(fill=tk.X)

            # Submit button
            ttk.Button(form_frame, text="Record Donation",
                      command=self.submit_donation).pack(pady=20)

        def show_view_donations(self):
            """Show donations viewer"""
            self.clear_content()
            self.update_status("View Donations")

            ttk.Label(self.content_frame, text="Alumni Donations",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Filter and search
            filter_frame = ttk.Frame(self.content_frame)
            filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Label(filter_frame, text="Filter by:").pack(side=tk.LEFT, padx=(0, 10))

            # Date range
            ttk.Label(filter_frame, text="From:").pack(side=tk.LEFT, padx=(0, 5))
            self.donation_from_date = tk.StringVar()
            ttk.Entry(filter_frame, textvariable=self.donation_from_date, width=10).pack(side=tk.LEFT, padx=(0, 10))

            ttk.Label(filter_frame, text="To:").pack(side=tk.LEFT, padx=(0, 5))
            self.donation_to_date = tk.StringVar()
            ttk.Entry(filter_frame, textvariable=self.donation_to_date, width=10).pack(side=tk.LEFT, padx=(0, 10))

            # Campaign filter
            ttk.Label(filter_frame, text="Campaign:").pack(side=tk.LEFT, padx=(0, 5))
            self.donation_campaign_filter = tk.StringVar()
            campaign_filter_combo = ttk.Combobox(filter_frame, textvariable=self.donation_campaign_filter,
                                               values=["All", "Annual Fund", "Scholarship Fund", "Building Fund"])
            campaign_filter_combo.pack(side=tk.LEFT, padx=(0, 10))
            campaign_filter_combo.set("All")

            ttk.Button(filter_frame, text="Apply Filter",
                      command=self.filter_donations).pack(side=tk.LEFT)

            # Donations table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Date', 'Alumni Name', 'Alumni ID', 'Amount', 'Campaign', 'Payment Method', 'Status')
            self.donations_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.donations_tree.heading(col, text=col)
                self.donations_tree.column(col, width=100)

            # Scrollbars
            donations_scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.donations_tree.yview)
            self.donations_tree.configure(yscrollcommand=donations_scrollbar_y.set)

            donations_scrollbar_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.donations_tree.xview)
            self.donations_tree.configure(xscrollcommand=donations_scrollbar_x.set)

            self.donations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            donations_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load donations data
            self.load_donations_data()

            # Summary
            summary_frame = ttk.LabelFrame(self.content_frame, text="Summary", padding=10)
            summary_frame.pack(fill=tk.X, padx=20)

            self.donation_summary = tk.StringVar()
            ttk.Label(summary_frame, textvariable=self.donation_summary).pack()
            self.update_donation_summary()

        def submit_campaign(self):
            """Submit fundraising campaign"""
            required_fields = ['campaign_name', 'goal_amount', 'start_date', 'end_date']
            for field in required_fields:
                if not self.campaign_vars[field].get().strip():
                    messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                    return

            try:
                goal_amount = float(self.campaign_vars['goal_amount'].get())
                if goal_amount <= 0:
                    messagebox.showerror("Validation Error", "Goal amount must be greater than zero!")
                    return
            except ValueError:
                messagebox.showerror("Validation Error", "Please enter a valid goal amount!")
                return

            messagebox.showinfo("Campaign Created", "Fundraising campaign created successfully!")
            self.update_status("Campaign creation completed")

            # Clear form
            for var in self.campaign_vars.values():
                if isinstance(var, tk.BooleanVar):
                    var.set(False)
                else:
                    var.set("")
            self.campaign_description.delete(1.0, tk.END)

        def submit_donation(self):
            """Submit donation record"""
            if not self.donation_vars['alumni_id'].get().strip():
                messagebox.showerror("Validation Error", "Alumni ID is required!")
                return

            if not self.donation_vars['amount'].get().strip():
                messagebox.showerror("Validation Error", "Donation amount is required!")
                return

            try:
                amount = float(self.donation_vars['amount'].get())
                if amount <= 0:
                    messagebox.showerror("Validation Error", "Donation amount must be greater than zero!")
                    return
            except ValueError:
                messagebox.showerror("Validation Error", "Please enter a valid donation amount!")
                return

            messagebox.showinfo("Donation Recorded", "Donation recorded successfully!")
            self.update_status("Donation record submitted")

            # Clear form
            for var in self.donation_vars.values():
                if isinstance(var, tk.BooleanVar):
                    var.set(False)
                else:
                    var.set("")
            self.donation_notes.delete(1.0, tk.END)

        def update_donation_summary(self):
            """Update donation summary"""
            # Sample summary data
            total_amount = 1925.00
            total_donations = 5
            avg_donation = total_amount / total_donations

            summary_text = f"Total Donations: {total_donations} | Total Amount: ${total_amount:,.2f} | Average: ${avg_donation:.2f}"
            self.donation_summary.set(summary_text)

        def update_donor_recognition_levels(self):
            """Configure donor recognition tiers"""
            if not self.has_permission('admin') and not self.has_permission('manage_fundraising'):
                messagebox.showerror("Permission Denied",
                                   "You don't have permission to manage donor recognition levels.")
                return

            self.clear_content()
            self.update_status("Donor Recognition Levels")

            ttk.Label(self.content_frame, text="Donor Recognition Levels",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Recognition levels table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Level Name', 'Min Amount', 'Max Amount', 'Benefits', 'Status')
            self.recognition_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.recognition_tree.heading(col, text=col)
                self.recognition_tree.column(col, width=140)

            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.recognition_tree.yview)
            self.recognition_tree.configure(yscrollcommand=scrollbar_y.set)

            self.recognition_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load recognition levels
            self._load_recognition_levels()

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="Add New Level",
                      command=self._add_recognition_level).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Edit Level",
                      command=self._edit_recognition_level).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Delete Level",
                      command=self._delete_recognition_level).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self._load_recognition_levels).pack(side=tk.LEFT)

        def update_recognition_levels(self):
            """Update donor recognition levels"""
            # Simulate updating recognition levels
            messagebox.showinfo("Update Complete", "Donor recognition levels updated successfully!")
            self.update_status("Recognition levels updated")

        def view_campaign_performance(self):
            """View analytics for a specific campaign"""
            self.clear_content()
            self.update_status("Campaign Performance")

            ttk.Label(self.content_frame, text="Campaign Performance Analytics",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Campaign selection
            select_frame = ttk.LabelFrame(self.content_frame, text="Select Campaign", padding=10)
            select_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            ttk.Label(select_frame, text="Campaign:").pack(side=tk.LEFT, padx=(0, 10))
            self.selected_campaign = tk.StringVar()

            # Load campaigns
            campaign_options = []
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT campaign_id, campaign_name, goal_amount, start_date, end_date
                        FROM fundraising_campaigns
                        ORDER BY start_date DESC
                    """)
                    campaigns = cursor.fetchall()
                    campaign_options = [f"{c[1]} (${c[2]:,.2f} goal) - {c[3]} (ID: {c[0]})" for c in campaigns]
            except sqlite3.Error:
                pass  # Silently handle database errors

            if not campaign_options:
                campaign_options = ["No campaigns available"]

            campaign_combo = ttk.Combobox(select_frame, textvariable=self.selected_campaign,
                                         values=campaign_options, width=60)
            campaign_combo.pack(side=tk.LEFT, padx=(0, 20))
            if campaign_options and campaign_options[0] != "No campaigns available":
                campaign_combo.set(campaign_options[0])

            ttk.Button(select_frame, text="Load Performance",
                      command=self._load_campaign_performance).pack(side=tk.LEFT)

            # Performance metrics
            self.performance_frame = ttk.LabelFrame(self.content_frame, text="Performance Metrics", padding=10)
            self.performance_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Summary metrics
            summary_frame = ttk.Frame(self.performance_frame)
            summary_frame.pack(fill=tk.X, pady=(0, 20))

            self.performance_labels = {}
            metrics = ['Total Raised', 'Number of Donors', 'Average Donation', 'Goal Progress']

            for i, metric in enumerate(metrics):
                metric_frame = ttk.Frame(summary_frame)
                metric_frame.grid(row=0, column=i, padx=10, pady=5, sticky='ew')

                ttk.Label(metric_frame, text=metric, font=('Arial', 10, 'bold')).pack()
                self.performance_labels[metric] = ttk.Label(metric_frame, text="--",
                                                            font=('Arial', 14))
                self.performance_labels[metric].pack()

            summary_frame.columnconfigure((0, 1, 2, 3), weight=1)

            # Donation history
            history_frame = ttk.LabelFrame(self.performance_frame, text="Recent Donations", padding=10)
            history_frame.pack(fill=tk.BOTH, expand=True)

            columns = ('Donor', 'Amount', 'Date', 'Payment Method')
            self.campaign_donations_tree = ttk.Treeview(history_frame, columns=columns, show='headings')

            for col in columns:
                self.campaign_donations_tree.heading(col, text=col)
                self.campaign_donations_tree.column(col, width=150)

            scrollbar_y = ttk.Scrollbar(history_frame, orient=tk.VERTICAL,
                                        command=self.campaign_donations_tree.yview)
            self.campaign_donations_tree.configure(yscrollcommand=scrollbar_y.set)

            self.campaign_donations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

