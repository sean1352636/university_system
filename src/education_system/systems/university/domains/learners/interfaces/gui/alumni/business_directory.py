
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.sql_safety import escape_like
import tkinter as tk
from education_system.systems.university.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.systems.university.domains.learners.interfaces.gui.alumni._service_imports import (
    init_alumni_db,
    view_events,
    create_enhanced_event,
    event_check_in_system,
    view_connection_requests,
    manage_business_directory,
    manage_alumni_forum,
    post_job_opportunity,
    view_job_board,
    schedule_career_counseling,
    view_engagement_leaderboard,
    view_my_badges,
    manage_photo_gallery,
    manage_class_reunions,
    generate_alumni_report,
    set_auth,
    setup_alumni_permissions,
    generate_engagement_recommendations,
    get_connection,
)



class BusinessDirectoryMixin:
        def _delete_business_listing(self):
            """Delete a business listing"""
            if messagebox.askyesno(_t('gui.learners.alumni.business_directory.dialogs.confirm_deletion', default="Confirm Deletion"),
                                  _t('gui.learners.alumni.business_directory.dialogs.are_you_sure_you_want_to_delete_this_business_listing', default="Are you sure you want to delete this business listing?")):
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
                        cursor.execute("DELETE FROM business_directory WHERE business_id = ?", (listing_id,))
                        conn.commit()

                    messagebox.showinfo(_t('gui.learners.alumni.business_directory.dialogs.success', default="Success"), _t('gui.learners.alumni.business_directory.dialogs.business_listing_deleted_successfully', default="Business listing deleted successfully!"))
                    self.update_business_listing()  # Reload

                    # Log activity
                    from education_system.systems.university.infrastructure.activity_logger import log_activity
                    log_activity('delete', 'business_listing', listing_id=listing_id,
                               details={'action': 'deleted'})

                except sqlite3.Error as e:
                    messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.database_error', default="Database Error"), f"Failed to delete listing: {str(e)}")

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
                messagebox.showwarning(_t('gui.learners.alumni.business_directory.dialogs.no_selection', default="No Selection"), _t('gui.learners.alumni.business_directory.dialogs.please_select_a_business_to_update', default="Please select a business to update."))
                return

            # Extract listing_id
            import re
            match = re.search(r'ID:\s*(\d+)', business_selection)
            if not match:
                messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.error', default="Error"), _t('gui.learners.alumni.business_directory.dialogs.invalid_business_selection', default="Invalid business selection."))
                return

            listing_id = int(match.group(1))

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT business_name, industry, website, COALESCE(contact_email, email), phone,
                               location, COALESCE(business_description, description),
                               COALESCE(services_offered, services)
                        FROM business_directory
                        WHERE business_id = ?
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
                        messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.error', default="Error"), _t('gui.learners.alumni.business_directory.dialogs.business_not_found', default="Business not found."))

            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.database_error', default="Database Error"), f"Failed to load business: {str(e)}")

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
                        SELECT b.business_name, b.industry, b.location,
                               TRIM(COALESCE(a.first_name, '') || ' ' || COALESCE(a.last_name, '')) AS owner_name,
                               COALESCE(b.contact_email, b.email)
                        FROM business_directory b
                        LEFT JOIN alumni a ON b.alumni_id = a.alumni_id
                        WHERE 1=1
                    """
                    params = []

                    # Add keyword filter
                    keyword = self.biz_search_keyword.get().strip()
                    if keyword:
                        query += (" AND (b.business_name LIKE ? OR COALESCE(b.business_description, b.description) LIKE ?"
                                  " OR COALESCE(b.services_offered, b.services) LIKE ?)")
                        params.extend([f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%"])

                    # Add industry filter
                    industry = self.biz_search_industry.get()
                    if industry != "All":
                        query += " AND b.industry = ?"
                        params.append(industry)

                    # Add location filter
                    location = self.biz_search_location.get().strip()
                    if location:
                        query += " AND b.location LIKE ?"
                        params.append(f"%{escape_like(location)}%")

                    query += " ORDER BY b.business_name"

                    cursor.execute(query, params)
                    results = cursor.fetchall()

                    for business in results:
                        self.biz_search_tree.insert('', tk.END, values=business)

                    self.update_status(f"Found {len(results)} business(es)")

            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.database_error', default="Database Error"), f"Search failed: {str(e)}")

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
                messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.validation_error', default="Validation Error"), _t('gui.learners.alumni.business_directory.dialogs.business_name_is_required', default="Business name is required!"))
                return

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE business_directory
                        SET business_name = ?, industry = ?, website = ?,
                            email = ?, contact_email = ?, phone = ?, location = ?,
                            description = ?, business_description = ?,
                            services = ?, services_offered = ?
                        WHERE business_id = ?
                    """, (
                        self.edit_business_vars['name'].get(),
                        self.edit_business_vars['industry'].get(),
                        self.edit_business_vars['website'].get(),
                        self.edit_business_vars['email'].get(),
                        self.edit_business_vars['email'].get(),
                        self.edit_business_vars['phone'].get(),
                        self.edit_business_vars['location'].get(),
                        self.edit_business_description.get(1.0, tk.END).strip(),
                        self.edit_business_description.get(1.0, tk.END).strip(),
                        self.edit_business_services.get(1.0, tk.END).strip(),
                        self.edit_business_services.get(1.0, tk.END).strip(),
                        listing_id
                    ))
                    conn.commit()

                messagebox.showinfo(_t('gui.learners.alumni.business_directory.dialogs.success', default="Success"), _t('gui.learners.alumni.business_directory.dialogs.business_listing_updated_successfully', default="Business listing updated successfully!"))
                self.update_status("Business listing saved")

                # Log activity
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('update', 'business_listing', listing_id=listing_id,
                           details={'name': self.edit_business_vars['name'].get()})

            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.database_error', default="Database Error"), f"Failed to save changes: {str(e)}")

        def _view_business_details(self):
            """View details for selected business"""
            if not hasattr(self, 'biz_search_tree'):
                return

            selection = self.biz_search_tree.selection()
            if not selection:
                messagebox.showwarning(_t('gui.learners.alumni.business_directory.dialogs.no_selection', default="No Selection"), _t('gui.learners.alumni.business_directory.dialogs.please_select_a_business_to_view', default="Please select a business to view."))
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

            ttk.Button(frame, text=_t('gui.learners.alumni.business_directory.buttons.close', default="Close"),
                      command=details_window.destroy).pack()

        def create_business_form(self, parent):
            """Create the add business form"""
            # Title
            ttk.Label(parent, text=_t('gui.learners.alumni.business_directory.labels.add_your_business_to_the_directory', default="Add Your Business to the Directory"),
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
                ("Location", "location"),
                ("Listing Fee (£)", "listing_fee")
            ]

            for label, var_name in business_fields:
                field_frame = ttk.Frame(form_frame)
                field_frame.pack(fill=tk.X, pady=5)

                ttk.Label(field_frame, text=label, width=15).pack(side=tk.LEFT, padx=(0, 10))
                self.business_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.business_vars[var_name]).pack(side=tk.LEFT, fill=tk.X, expand=True)

            self.business_vars['listing_fee'].set("0.00")

            # Description
            desc_frame = ttk.Frame(form_frame)
            desc_frame.pack(fill=tk.X, pady=10)

            ttk.Label(desc_frame, text=_t('gui.learners.alumni.business_directory.labels.business_description', default="Business Description:")).pack(anchor='w')
            self.business_desc = ScrolledText(desc_frame, height=4, wrap=tk.WORD)
            self.business_desc.pack(fill=tk.X, pady=(5, 0))

            # Services
            services_frame = ttk.Frame(form_frame)
            services_frame.pack(fill=tk.X, pady=10)

            ttk.Label(services_frame, text=_t('gui.learners.alumni.business_directory.labels.services_offered', default="Services Offered:")).pack(anchor='w')
            self.business_services = ScrolledText(services_frame, height=3, wrap=tk.WORD)
            self.business_services.pack(fill=tk.X, pady=(5, 0))

            # Submit button
            ttk.Button(form_frame, text=_t('gui.learners.alumni.business_directory.buttons.add_business_to_directory', default="Add Business to Directory"),
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

            ttk.Label(self.content_frame, text=_t('gui.learners.alumni.business_directory.labels.search_business_directory', default="Search Business Directory"),
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Search criteria
            search_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.learners.alumni.business_directory.labels.search_criteria', default="Search Criteria"), padding=10)
            search_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            # Row 1: Keyword and Industry
            row1 = ttk.Frame(search_frame)
            row1.pack(fill=tk.X, pady=5)

            ttk.Label(row1, text=_t('gui.learners.alumni.business_directory.labels.keyword', default="Keyword:")).pack(side=tk.LEFT, padx=(0, 10))
            self.biz_search_keyword = tk.StringVar()
            ttk.Entry(row1, textvariable=self.biz_search_keyword, width=25).pack(side=tk.LEFT, padx=(0, 20))

            ttk.Label(row1, text=_t('gui.learners.alumni.business_directory.labels.industry', default="Industry:")).pack(side=tk.LEFT, padx=(0, 10))
            self.biz_search_industry = tk.StringVar()
            industry_combo = ttk.Combobox(row1, textvariable=self.biz_search_industry,
                                         values=["All", "Technology", "Finance", "Healthcare",
                                                "Education", "Marketing", "Consulting", "Other"])
            industry_combo.pack(side=tk.LEFT)
            industry_combo.set("All")

            # Row 2: Location
            row2 = ttk.Frame(search_frame)
            row2.pack(fill=tk.X, pady=5)

            ttk.Label(row2, text=_t('gui.learners.alumni.business_directory.labels.location', default="Location:")).pack(side=tk.LEFT, padx=(0, 10))
            self.biz_search_location = tk.StringVar()
            ttk.Entry(row2, textvariable=self.biz_search_location, width=25).pack(side=tk.LEFT)

            # Search button
            ttk.Button(search_frame, text=_t('gui.learners.alumni.business_directory.buttons.search', default="Search"),
                      command=self._perform_business_search).pack(pady=(10, 0))

            # Results table
            results_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.learners.alumni.business_directory.labels.search_results', default="Search Results"), padding=10)
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

            ttk.Button(button_frame, text=_t('gui.learners.alumni.business_directory.buttons.view_details', default="View Details"),
                      command=self._view_business_details).pack(side=tk.LEFT)

        def show_business_directory(self):
            """Show business directory interface"""
            self.clear_content()
            self.update_status("Alumni Business Directory")

            ttk.Label(self.content_frame, text=_t('gui.learners.alumni.business_directory.labels.alumni_business_directory', default="Alumni Business Directory"),
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for viewing and adding businesses
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # View businesses tab
            view_frame = ttk.Frame(notebook)
            notebook.add(view_frame, text=_t('gui.learners.alumni.business_directory.tabs.browse_businesses', default="Browse Businesses"))

            # Search and filter
            filter_frame = ttk.Frame(view_frame)
            filter_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(filter_frame, text=_t('gui.learners.alumni.business_directory.labels.filter_by_industry', default="Filter by Industry:")).pack(side=tk.LEFT, padx=(0, 10))
            industry_var = tk.StringVar()
            industry_combo = ttk.Combobox(filter_frame, textvariable=industry_var,
                                         values=["All", "Technology", "Healthcare", "Finance", "Education", "Other"])
            industry_combo.pack(side=tk.LEFT, padx=(0, 10))
            industry_combo.set("All")

            ttk.Button(filter_frame, text=_t('gui.learners.alumni.business_directory.buttons.filter', default="Filter"),
                      command=lambda: self.filter_businesses(industry_var.get())).pack(side=tk.LEFT)
            ttk.Button(filter_frame, text=_t('gui.learners.alumni.business_directory.buttons.refresh', default="🔄 Refresh"),
                      command=self.load_business_listings).pack(side=tk.LEFT, padx=(10, 0))

            # Business listings
            self.business_text = ScrolledText(view_frame, wrap=tk.WORD)
            self.business_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Load listings from the database
            self.load_business_listings()

            # Add business tab
            add_frame = ttk.Frame(notebook)
            notebook.add(add_frame, text=_t('gui.learners.alumni.business_directory.tabs.add_my_business', default="Add My Business"))

            self.create_business_form(add_frame)

        def _resolve_business_alumni_id(self):
            """Return the current user's alumni_id if they have an alumni
            record, else None (FK to alumni allows NULL)."""
            user = getattr(self, 'current_user', {}) or {}
            uid = str(user.get('username') or user.get('id') or '')
            if not uid:
                return None
            try:
                with db_get_connection() as conn:
                    row = conn.execute(
                        "SELECT alumni_id FROM alumni WHERE alumni_id = ? OR student_id = ? LIMIT 1",
                        (uid, uid)).fetchone()
                    if row:
                        return str(row[0])
            except sqlite3.Error:
                pass
            return None

        def _resolve_owner_student_id(self, alumni_id):
            """Return the finance student_id linked to an alumni_id, or None."""
            if not alumni_id:
                return None
            try:
                with db_get_connection() as conn:
                    r = conn.execute("SELECT student_id FROM alumni WHERE alumni_id = ?",
                                     (alumni_id,)).fetchone()
                    if r and r[0]:
                        return str(r[0])
            except sqlite3.Error:
                pass
            return None

        def _prompt_listing_payment(self, name, fee, student_id=None):
            """Modal dialog to choose how to pay a business listing fee.
            Returns the chosen method, or None if cancelled."""
            win = tk.Toplevel(self.root)
            win.title(_t('gui.learners.alumni.business_directory.windows.listing_fee_payment', default="Listing Fee Payment"))
            win.geometry("440x330")
            win.grab_set()
            ttk.Label(win, text=f"Listing fee for: {name}",
                      font=('Arial', 12, 'bold')).pack(pady=(15, 5))
            ttk.Label(win, text=f"Fee: £{fee:.2f}").pack(pady=(0, 10))

            method = tk.StringVar(value=_t('gui.learners.alumni.business_directory.values.card', default="Card"))
            for m in ("Cash", "Card", "Finance Account"):
                ttk.Radiobutton(win, text=m, variable=method, value=m).pack(anchor='w', padx=50)

            bal_text = "No linked finance account (Finance Account unavailable)."
            if student_id:
                try:
                    with db_get_connection() as conn:
                        r = conn.execute(
                            "SELECT balance FROM student_finance_accounts WHERE student_id = ?",
                            (student_id,)).fetchone()
                    bal_text = (f"Finance account ({student_id}) balance: £{float(r[0] or 0):.2f}"
                                if r else f"No finance account on file for {student_id}.")
                except sqlite3.Error:
                    pass
            ttk.Label(win, text=bal_text, foreground='#555555').pack(pady=12, padx=20)

            result = {'method': None}

            def confirm():
                result['method'] = method.get()
                win.destroy()
            btns = ttk.Frame(win)
            btns.pack(pady=15)
            ttk.Button(btns, text=_t('gui.learners.alumni.business_directory.buttons.confirm_payment', default="Confirm Payment"), command=confirm).pack(side=tk.LEFT, padx=8)
            ttk.Button(btns, text=_t('gui.learners.alumni.business_directory.buttons.cancel', default="Cancel"), command=win.destroy).pack(side=tk.LEFT)
            win.wait_window()
            return result['method']

        def submit_business(self):
            """Persist a new business listing to the business_directory table."""
            # Validate required fields
            required_fields = ['business_name', 'industry', 'email']
            for field in required_fields:
                if not self.business_vars[field].get().strip():
                    messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.validation_error', default="Validation Error"), f"{field.replace('_', ' ').title()} is required!")
                    return

            name = self.business_vars['business_name'].get().strip()
            industry = self.business_vars['industry'].get().strip()
            website = self.business_vars['website'].get().strip()
            email = self.business_vars['email'].get().strip()
            location = self.business_vars['location'].get().strip()
            description = self.business_desc.get(1.0, tk.END).strip()
            services = self.business_services.get(1.0, tk.END).strip()
            alumni_id = self._resolve_business_alumni_id()
            owner_student_id = self._resolve_owner_student_id(alumni_id)
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            try:
                listing_fee = float(self.business_vars.get('listing_fee').get() or 0)
            except (ValueError, AttributeError):
                listing_fee = 0.0

            # Collect a payment method up front for a paid listing; Finance
            # Account debits the owner's university finance account.
            payment_method = None
            if listing_fee > 0:
                payment_method = self._prompt_listing_payment(name, listing_fee, owner_student_id)
                if not payment_method:
                    return  # cancelled

                if payment_method == "Finance Account":
                    if not owner_student_id:
                        messagebox.showerror(
                            _t('gui.learners.alumni.business_directory.dialogs.no_finance_account', default="No Finance Account"),
                            _t('gui.learners.alumni.business_directory.dialogs.no_finance_account_is_linked_to_this_alumnus_so_the_fee_cannot_b', default="No finance account is linked to this alumnus, so the fee "
                            "cannot be paid from a finance account."))
                        return
                    try:
                        with db_get_connection() as conn:
                            bal = conn.execute(
                                "SELECT balance FROM student_finance_accounts WHERE student_id = ?",
                                (owner_student_id,)).fetchone()
                    except sqlite3.Error as e:
                        messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.database_error', default="Database Error"), f"Finance lookup failed: {e}")
                        return
                    if bal is None:
                        messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.no_finance_account', default="No Finance Account"),
                                             f"No finance account exists for {owner_student_id}.")
                        return
                    if float(bal[0] or 0) < listing_fee:
                        messagebox.showerror(
                            _t('gui.learners.alumni.business_directory.dialogs.insufficient_funds', default="Insufficient Funds"),
                            f"Balance (£{float(bal[0] or 0):.2f}) is less than the "
                            f"listing fee (£{listing_fee:.2f}).")
                        return
                    try:
                        from education_system.systems.university.services.bus.finance_bus import raise_charge
                        tx = raise_charge(
                            owner_student_id, listing_fee, source="business_listing",
                            description=f"Business directory listing: {name}",
                            reference_id=f"BIZ-{alumni_id or owner_student_id}-{now}",
                            processed_by=str(getattr(self, 'current_user', {}).get('username', 'alumni_gui')))
                        if tx is None:
                            messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.payment_failed', default="Payment Failed"),
                                                 _t('gui.learners.alumni.business_directory.dialogs.could_not_debit_the_finance_account', default="Could not debit the finance account."))
                            return
                    except Exception as e:
                        messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.payment_failed', default="Payment Failed"), f"Charge failed: {e}")
                        return

            try:
                with db_get_connection() as conn:
                    cur = conn.execute(
                        """
                        INSERT INTO business_directory
                            (alumni_id, business_name, business_description, industry,
                             website, contact_email, services_offered, location, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (alumni_id, name, description, industry, website, email,
                         services, location, now),
                    )
                    business_id = cur.lastrowid
                    conn.commit()
            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.learners.alumni.business_directory.dialogs.database_error', default="Database Error"), f"Failed to add business: {e}")
                return

            # Book the listing fee as revenue in the central finance system.
            if listing_fee > 0:
                try:
                    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
                        record_revenue_to_finance,
                    )
                    record_revenue_to_finance(
                        student_id=str(owner_student_id or 'EXTERNAL'),
                        amount=listing_fee,
                        revenue_category="Business Listing Fee",
                        transaction_source="Alumni",
                        transaction_ref=f"BIZ-{business_id}",
                        payment_method=payment_method or "Listing Fee",
                        notes=f"Business directory listing: {name}",
                    )
                except Exception as e:
                    import logging
                    logging.warning(f"record_revenue_to_finance failed (listing still created): {e}")

            messagebox.showinfo(
                _t('gui.learners.alumni.business_directory.dialogs.success', default="Success"),
                "Business listing added successfully!" +
                (f"\nListing fee of £{listing_fee:.2f} paid via {payment_method}."
                 if listing_fee > 0 else ""))
            self.update_status("Business listing submitted")

            # Clear form
            for var in self.business_vars.values():
                var.set("")
            self.business_desc.delete(1.0, tk.END)
            self.business_services.delete(1.0, tk.END)

            # Refresh the browse list if it's on screen.
            if hasattr(self, 'business_text'):
                try:
                    self.load_business_listings()
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

        def update_business_listing(self):
            """Edit an existing business listing"""
            self.clear_content()
            self.update_status("Update Business Listing")

            ttk.Label(self.content_frame, text=_t('gui.learners.alumni.business_directory.labels.update_business_listing', default="Update Business Listing"),
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Business selection
            select_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.learners.alumni.business_directory.labels.select_business_to_update', default="Select Business to Update"), padding=10)
            select_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            ttk.Label(select_frame, text=_t('gui.learners.alumni.business_directory.labels.select_business', default="Select Business:")).pack(side=tk.LEFT, padx=(0, 10))
            self.selected_business = tk.StringVar()

            # Load businesses owned by user
            business_options = []
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    alumni_id = self._resolve_business_alumni_id()

                    cursor.execute("""
                        SELECT business_id, business_name, industry
                        FROM business_directory
                        WHERE alumni_id = ?
                        ORDER BY business_name
                    """, (alumni_id,))
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

            ttk.Button(select_frame, text=_t('gui.learners.alumni.business_directory.buttons.load_business', default="Load Business"),
                      command=self._load_business_for_edit).pack(side=tk.LEFT)

            # Edit form
            self.business_edit_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.learners.alumni.business_directory.labels.business_details', default="Business Details"), padding=10)
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
            ttk.Label(self.business_edit_frame, text=_t('gui.learners.alumni.business_directory.labels.description', default="Description:")).pack(anchor='w', pady=(10, 5))
            self.edit_business_description = ScrolledText(self.business_edit_frame, height=5, wrap=tk.WORD)
            self.edit_business_description.pack(fill=tk.X)

            # Services
            ttk.Label(self.business_edit_frame, text=_t('gui.learners.alumni.business_directory.labels.services_offered', default="Services Offered:")).pack(anchor='w', pady=(10, 5))
            self.edit_business_services = ScrolledText(self.business_edit_frame, height=4, wrap=tk.WORD)
            self.edit_business_services.pack(fill=tk.X)

            # Action buttons
            button_frame = ttk.Frame(self.business_edit_frame)
            button_frame.pack(fill=tk.X, pady=(20, 0))

            ttk.Button(button_frame, text=_t('gui.learners.alumni.business_directory.buttons.save_changes', default="Save Changes"),
                      command=self._save_business_changes).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text=_t('gui.learners.alumni.business_directory.buttons.delete_listing', default="Delete Listing"),
                      command=self._delete_business_listing).pack(side=tk.LEFT)

