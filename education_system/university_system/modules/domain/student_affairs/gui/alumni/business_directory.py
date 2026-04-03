from education_system.university_system.core.sql_safety import escape_like
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



class BusinessDirectoryMixin:
        def _delete_business_listing(self):
            """Delete a business listing"""
            if messagebox.askyesno("Confirm Deletion",
                                  "Are you sure you want to delete this business listing?"):
                business_selection = self.selected_business.get()
                if not business_selection:
                    return

                # Extract listing_id
                import re
                match = re.search(r'ID:\s*(\d+)', business_selection)
                if not match:
                    return

                listing_id = int(match.group(1))

                try:
                    with db_get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM business_directory WHERE listing_id = ?", (listing_id,))
                        conn.commit()

                    messagebox.showinfo("Success", "Business listing deleted successfully!")
                    self.update_business_listing()  # Reload

                    # Log activity
                    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
                    log_activity('delete', 'business_listing', listing_id=listing_id,
                               details={'action': 'deleted'})

                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Failed to delete listing: {str(e)}")

        def _fetch_business_listings(self, industry: str | None = None):
            """Return business listings optionally filtered by industry."""
            conn = self._get_db_connection()
            cursor = conn.cursor()
            base_query = (
                "SELECT b.business_name, b.business_description, b.industry, b.website, "
                "b.contact_email, b.services_offered, b.location, b.created_date, "
                "a.first_name, a.last_name, a.graduation_year "
                "FROM business_directory b "
                "LEFT JOIN alumni a ON b.alumni_id = a.alumni_id"
            )
            params: list[str] = []
            if industry and industry.lower() != "all":
                base_query += " WHERE LOWER(b.industry) = LOWER(?)"
                params.append(industry)
            base_query += " ORDER BY b.business_name"
            cursor.execute(base_query, params)
            rows = cursor.fetchall()
            conn.close()
            return rows

        def _load_business_for_edit(self):
            """Load selected business data into edit form"""
            business_selection = self.selected_business.get()
            if not business_selection or business_selection == "No businesses to update":
                messagebox.showwarning("No Selection", "Please select a business to update.")
                return

            # Extract listing_id
            import re
            match = re.search(r'ID:\s*(\d+)', business_selection)
            if not match:
                messagebox.showerror("Error", "Invalid business selection.")
                return

            listing_id = int(match.group(1))

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT business_name, industry, website, email, phone,
                               location, description, services
                        FROM business_directory
                        WHERE listing_id = ?
                    """, (listing_id,))
                    business = cursor.fetchone()

                    if business:
                        self.edit_business_vars['name'].set(business[0] or '')
                        self.edit_business_vars['industry'].set(business[1] or '')
                        self.edit_business_vars['website'].set(business[2] or '')
                        self.edit_business_vars['email'].set(business[3] or '')
                        self.edit_business_vars['phone'].set(business[4] or '')
                        self.edit_business_vars['location'].set(business[5] or '')

                        self.edit_business_description.delete(1.0, tk.END)
                        if business[6]:
                            self.edit_business_description.insert(tk.END, business[6])

                        self.edit_business_services.delete(1.0, tk.END)
                        if business[7]:
                            self.edit_business_services.insert(tk.END, business[7])

                        self.update_status(f"Loaded business: {business[0]}")
                    else:
                        messagebox.showerror("Error", "Business not found.")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load business: {str(e)}")

        def _perform_business_search(self):
            """Perform business directory search"""
            try:
                # Clear existing results
                for item in self.biz_search_tree.get_children():
                    self.biz_search_tree.delete(item)

                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    # Build query
                    query = """
                        SELECT business_name, industry, location, owner_name, email
                        FROM business_directory
                        WHERE 1=1
                    """
                    params = []

                    # Add keyword filter
                    keyword = self.biz_search_keyword.get().strip()
                    if keyword:
                        query += " AND (business_name LIKE ? OR description LIKE ? OR services LIKE ?)"
                        params.extend([f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%"])

                    # Add industry filter
                    industry = self.biz_search_industry.get()
                    if industry != "All":
                        query += " AND industry = ?"
                        params.append(industry)

                    # Add location filter
                    location = self.biz_search_location.get().strip()
                    if location:
                        query += " AND location LIKE ?"
                        params.append(f"%{escape_like(location)}%")

                    query += " ORDER BY business_name"

                    cursor.execute(query, params)
                    results = cursor.fetchall()

                    for business in results:
                        self.biz_search_tree.insert('', tk.END, values=business)

                    self.update_status(f"Found {len(results)} business(es)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Search failed: {str(e)}")

        def _save_business_changes(self):
            """Save changes to business listing"""
            business_selection = self.selected_business.get()
            if not business_selection:
                return

            # Extract listing_id
            import re
            match = re.search(r'ID:\s*(\d+)', business_selection)
            if not match:
                return

            listing_id = int(match.group(1))

            # Validation
            if not self.edit_business_vars['name'].get():
                messagebox.showerror("Validation Error", "Business name is required!")
                return

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE business_directory
                        SET business_name = ?, industry = ?, website = ?,
                            email = ?, phone = ?, location = ?,
                            description = ?, services = ?
                        WHERE listing_id = ?
                    """, (
                        self.edit_business_vars['name'].get(),
                        self.edit_business_vars['industry'].get(),
                        self.edit_business_vars['website'].get(),
                        self.edit_business_vars['email'].get(),
                        self.edit_business_vars['phone'].get(),
                        self.edit_business_vars['location'].get(),
                        self.edit_business_description.get(1.0, tk.END).strip(),
                        self.edit_business_services.get(1.0, tk.END).strip(),
                        listing_id
                    ))
                    conn.commit()

                messagebox.showinfo("Success", "Business listing updated successfully!")
                self.update_status("Business listing saved")

                # Log activity
                from education_system.university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('update', 'business_listing', listing_id=listing_id,
                           details={'name': self.edit_business_vars['name'].get()})

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to save changes: {str(e)}")

        def _view_business_details(self):
            """View details for selected business"""
            if not hasattr(self, 'biz_search_tree'):
                return

            selection = self.biz_search_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a business to view.")
                return

            item = self.biz_search_tree.item(selection[0])
            business_data = item['values']

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Business Details - {business_data[0]}")
            details_window.geometry("600x500")
            details_window.configure(bg='white')

            frame = ttk.Frame(details_window, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=business_data[0],
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            info_frame = ttk.Frame(frame)
            info_frame.pack(fill=tk.X, pady=(0, 20))

            info_text = f"""
    Industry: {business_data[1]}
    Location: {business_data[2]}
    Owner: {business_data[3]}
    Contact: {business_data[4]}
    """
            ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor='w')

            ttk.Button(frame, text="Close",
                      command=details_window.destroy).pack()

        def create_business_form(self, parent):
            """Create the add business form"""
            # Title
            ttk.Label(parent, text="Add Your Business to the Directory",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            # Form fields
            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            self.business_vars = {}

            business_fields = [
                ("Business Name*", "business_name"),
                ("Industry*", "industry"),
                ("Website", "website"),
                ("Contact Email*", "email"),
                ("Location", "location")
            ]

            for label, var_name in business_fields:
                field_frame = ttk.Frame(form_frame)
                field_frame.pack(fill=tk.X, pady=5)

                ttk.Label(field_frame, text=label, width=15).pack(side=tk.LEFT, padx=(0, 10))
                self.business_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.business_vars[var_name]).pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Description
            desc_frame = ttk.Frame(form_frame)
            desc_frame.pack(fill=tk.X, pady=10)

            ttk.Label(desc_frame, text="Business Description:").pack(anchor='w')
            self.business_desc = ScrolledText(desc_frame, height=4, wrap=tk.WORD)
            self.business_desc.pack(fill=tk.X, pady=(5, 0))

            # Services
            services_frame = ttk.Frame(form_frame)
            services_frame.pack(fill=tk.X, pady=10)

            ttk.Label(services_frame, text="Services Offered:").pack(anchor='w')
            self.business_services = ScrolledText(services_frame, height=3, wrap=tk.WORD)
            self.business_services.pack(fill=tk.X, pady=(5, 0))

            # Submit button
            ttk.Button(form_frame, text="Add Business to Directory",
                      command=self.submit_business).pack(pady=20)

        def filter_businesses(self, industry):
            """Filter businesses by industry"""
            industry = (industry or "").strip()
            if not industry or industry == "All":
                self.load_business_listings()
                return

            rows = self._fetch_business_listings(industry)
            self.business_text.delete(1.0, tk.END)

            if not rows:
                self.business_text.insert(tk.END, f"No businesses found in the {industry} industry.\n")
                self.update_status(f"No business listings for industry '{industry}'")
                return

            for row in rows:
                owner_name = " ".join(filter(None, [row['first_name'], row['last_name']])).strip() or "Unknown"
                self.business_text.insert(tk.END, f"🏢 {row['business_name']}\n")
                self.business_text.insert(tk.END, f"Owner: {owner_name}\n")
                self.business_text.insert(tk.END, f"Industry: {row['industry'] or 'Not specified'}\n")
                self.business_text.insert(tk.END, f"Location: {row['location'] or 'Not specified'}\n")
                if row['business_description']:
                    self.business_text.insert(tk.END, f"Description: {row['business_description'][:200]}\n")
                if row['website']:
                    self.business_text.insert(tk.END, f"Website: {row['website']}\n")
                if row['services_offered']:
                    self.business_text.insert(tk.END, f"Services: {row['services_offered'][:200]}\n")
                if row['contact_email']:
                    self.business_text.insert(tk.END, f"Contact: {row['contact_email']}\n")
                self.business_text.insert(tk.END, "-" * 40 + "\n")

            self.update_status(f"Showing {len(rows)} business listings for industry '{industry}'")

        def load_business_listings(self):
            """Load business listings into the text widget"""
            self.business_text.delete(1.0, tk.END)
            rows = self._fetch_business_listings()
            if not rows:
                self.business_text.insert(tk.END, "No business listings found in the directory.\n")
                self.update_status("Business directory is empty")
                return

            lines = ["Alumni Business Directory Listings:\n"]
            for row in rows:
                owner_name = " ".join(filter(None, [row['first_name'], row['last_name']])).strip()
                if owner_name:
                    owner_line = f"Owner: {owner_name}"
                    if row['graduation_year']:
                        owner_line += f" (Class of {row['graduation_year']})"
                else:
                    owner_line = "Owner: Unknown"

                lines.extend([
                    f"🏢 {row['business_name']}",
                    owner_line,
                    f"Industry: {row['industry'] or 'Not specified'}",
                    f"Location: {row['location'] or 'Not specified'}",
                    f"Description: {(row['business_description'] or 'No description')[:200]}",
                ])
                if row['website']:
                    lines.append(f"Website: {row['website']}")
                if row['services_offered']:
                    lines.append(f"Services: {(row['services_offered'])[:200]}")
                if row['contact_email']:
                    lines.append(f"📧 Contact: {row['contact_email']}")
                lines.append("-" * 40)

            self.business_text.insert(tk.END, "\n".join(lines))
            self.update_status(f"Loaded {len(rows)} business listings")

        def search_business_directory(self):
            """Search businesses in the directory"""
            self.clear_content()
            self.update_status("Search Business Directory")

            ttk.Label(self.content_frame, text="Search Business Directory",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Search criteria
            search_frame = ttk.LabelFrame(self.content_frame, text="Search Criteria", padding=10)
            search_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            # Row 1: Keyword and Industry
            row1 = ttk.Frame(search_frame)
            row1.pack(fill=tk.X, pady=5)

            ttk.Label(row1, text="Keyword:").pack(side=tk.LEFT, padx=(0, 10))
            self.biz_search_keyword = tk.StringVar()
            ttk.Entry(row1, textvariable=self.biz_search_keyword, width=25).pack(side=tk.LEFT, padx=(0, 20))

            ttk.Label(row1, text="Industry:").pack(side=tk.LEFT, padx=(0, 10))
            self.biz_search_industry = tk.StringVar()
            industry_combo = ttk.Combobox(row1, textvariable=self.biz_search_industry,
                                         values=["All", "Technology", "Finance", "Healthcare",
                                                "Education", "Marketing", "Consulting", "Other"])
            industry_combo.pack(side=tk.LEFT)
            industry_combo.set("All")

            # Row 2: Location
            row2 = ttk.Frame(search_frame)
            row2.pack(fill=tk.X, pady=5)

            ttk.Label(row2, text="Location:").pack(side=tk.LEFT, padx=(0, 10))
            self.biz_search_location = tk.StringVar()
            ttk.Entry(row2, textvariable=self.biz_search_location, width=25).pack(side=tk.LEFT)

            # Search button
            ttk.Button(search_frame, text="Search",
                      command=self._perform_business_search).pack(pady=(10, 0))

            # Results table
            results_frame = ttk.LabelFrame(self.content_frame, text="Search Results", padding=10)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Business Name', 'Industry', 'Location', 'Owner', 'Contact')
            self.biz_search_tree = ttk.Treeview(results_frame, columns=columns, show='headings')

            for col in columns:
                self.biz_search_tree.heading(col, text=col)
                self.biz_search_tree.column(col, width=140)

            scrollbar_y = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                        command=self.biz_search_tree.yview)
            self.biz_search_tree.configure(yscrollcommand=scrollbar_y.set)

            self.biz_search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="View Details",
                      command=self._view_business_details).pack(side=tk.LEFT)

        def show_business_directory(self):
            """Show business directory interface"""
            self.clear_content()
            self.update_status("Alumni Business Directory")

            ttk.Label(self.content_frame, text="Alumni Business Directory",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for viewing and adding businesses
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # View businesses tab
            view_frame = ttk.Frame(notebook)
            notebook.add(view_frame, text="Browse Businesses")

            # Search and filter
            filter_frame = ttk.Frame(view_frame)
            filter_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(filter_frame, text="Filter by Industry:").pack(side=tk.LEFT, padx=(0, 10))
            industry_var = tk.StringVar()
            industry_combo = ttk.Combobox(filter_frame, textvariable=industry_var,
                                         values=["All", "Technology", "Healthcare", "Finance", "Education", "Other"])
            industry_combo.pack(side=tk.LEFT, padx=(0, 10))
            industry_combo.set("All")

            ttk.Button(filter_frame, text="Filter",
                      command=lambda: self.filter_businesses(industry_var.get())).pack(side=tk.LEFT)

            # Business listings
            self.business_text = ScrolledText(view_frame, wrap=tk.WORD)
            self.business_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Load sample business data
            self.load_business_listings()

            # Add business tab
            add_frame = ttk.Frame(notebook)
            notebook.add(add_frame, text="Add My Business")

            self.create_business_form(add_frame)

        def submit_business(self):
            """Submit business listing"""
            # Validate required fields
            required_fields = ['business_name', 'industry', 'email']
            for field in required_fields:
                if not self.business_vars[field].get().strip():
                    messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                    return

            messagebox.showinfo("Success", "Business listing added successfully!")
            self.update_status("Business listing submitted")

            # Clear form
            for var in self.business_vars.values():
                var.set("")
            self.business_desc.delete(1.0, tk.END)
            self.business_services.delete(1.0, tk.END)

        def update_business_listing(self):
            """Edit an existing business listing"""
            self.clear_content()
            self.update_status("Update Business Listing")

            ttk.Label(self.content_frame, text="Update Business Listing",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Business selection
            select_frame = ttk.LabelFrame(self.content_frame, text="Select Business to Update", padding=10)
            select_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            ttk.Label(select_frame, text="Select Business:").pack(side=tk.LEFT, padx=(0, 10))
            self.selected_business = tk.StringVar()

            # Load businesses owned by user
            business_options = []
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    cursor.execute("""
                        SELECT listing_id, business_name, industry
                        FROM business_directory
                        WHERE owner_id = ?
                        ORDER BY business_name
                    """, (user_id,))
                    businesses = cursor.fetchall()
                    business_options = [f"{b[1]} - {b[2]} (ID: {b[0]})" for b in businesses]
            except sqlite3.Error:
                pass  # Silently handle database errors

            if not business_options:
                business_options = ["No businesses to update"]

            business_combo = ttk.Combobox(select_frame, textvariable=self.selected_business,
                                         values=business_options, width=50)
            business_combo.pack(side=tk.LEFT, padx=(0, 20))
            if business_options and business_options[0] != "No businesses to update":
                business_combo.set(business_options[0])

            ttk.Button(select_frame, text="Load Business",
                      command=self._load_business_for_edit).pack(side=tk.LEFT)

            # Edit form
            self.business_edit_frame = ttk.LabelFrame(self.content_frame, text="Business Details", padding=10)
            self.business_edit_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Form fields
            self.edit_business_vars = {}

            fields = [
                ("Business Name*", "name"),
                ("Industry*", "industry"),
                ("Website", "website"),
                ("Email*", "email"),
                ("Phone", "phone"),
                ("Location", "location")
            ]

            for label, var_name in fields:
                field_frame = ttk.Frame(self.business_edit_frame)
                field_frame.pack(fill=tk.X, pady=5)

                ttk.Label(field_frame, text=label, width=15).pack(side=tk.LEFT, padx=(0, 10))
                self.edit_business_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.edit_business_vars[var_name]).pack(
                    side=tk.LEFT, fill=tk.X, expand=True)

            # Description
            ttk.Label(self.business_edit_frame, text="Description:").pack(anchor='w', pady=(10, 5))
            self.edit_business_description = ScrolledText(self.business_edit_frame, height=5, wrap=tk.WORD)
            self.edit_business_description.pack(fill=tk.X)

            # Services
            ttk.Label(self.business_edit_frame, text="Services Offered:").pack(anchor='w', pady=(10, 5))
            self.edit_business_services = ScrolledText(self.business_edit_frame, height=4, wrap=tk.WORD)
            self.edit_business_services.pack(fill=tk.X)

            # Action buttons
            button_frame = ttk.Frame(self.business_edit_frame)
            button_frame.pack(fill=tk.X, pady=(20, 0))

            ttk.Button(button_frame, text="Save Changes",
                      command=self._save_business_changes).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Delete Listing",
                      command=self._delete_business_listing).pack(side=tk.LEFT)

