from education_system.systems.university.infrastructure.sql_safety import escape_like
import tkinter as tk
from education_system.systems.university.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.systems.university.infrastructure import paths
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
from education_system.systems.university.interfaces.gui.learners.alumni._service_imports import init_alumni_db, register_alumni, view_alumni, update_alumni, view_events, create_enhanced_event, event_check_in_system, record_donation, view_donations, setup_mentorship, view_mentorships, search_alumni_directory, manage_business_directory, create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board, schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign, view_engagement_leaderboard, view_my_badges, manage_photo_gallery, manage_class_reunions, manage_regional_chapters, setup_alumni_directory, generate_alumni_report, set_auth, setup_alumni_permissions, smart_mentorship_matching, generate_engagement_recommendations, create_alumni_story, view_alumni_stories, get_connection



class DirectoryMixin:
        def _ensure_connections_schema(self, conn=None):
            """Create the alumni_connections table if it doesn't exist."""
            own = conn is None
            if own:
                conn = db_get_connection()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alumni_connections (
                        connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        requester_id  TEXT NOT NULL,
                        recipient_id  TEXT NOT NULL,
                        status        TEXT DEFAULT 'pending',
                        message       TEXT,
                        request_date  TEXT DEFAULT (datetime('now')),
                        response_date TEXT
                    )
                    """
                )
                conn.commit()
            finally:
                if own:
                    conn.close()

        def _current_alumni_id(self):
            """Resolve the signed-in user's alumni_id (via the alumni table),
            falling back to their user id."""
            uid = str(self._current_user_id())
            try:
                with db_get_connection() as conn:
                    row = conn.execute(
                        "SELECT alumni_id FROM alumni WHERE alumni_id = ? OR student_id = ? LIMIT 1",
                        (uid, uid)).fetchone()
                    if row:
                        return str(row[0])
            except sqlite3.Error:
                pass
            return uid

        def _respond_to_request(self, response):
            """Accept/decline the selected incoming connection request."""
            if not hasattr(self, 'incoming_requests_tree'):
                return

            selection = self.incoming_requests_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a request.")
                return

            connection_id = selection[0]  # tree iid is the connection_id
            me = self._current_alumni_id()
            try:
                with db_get_connection() as conn:
                    self._ensure_connections_schema(conn)
                    conn.execute(
                        """
                        UPDATE alumni_connections
                        SET status = ?, response_date = datetime('now')
                        WHERE connection_id = ? AND recipient_id = ? AND status = 'pending'
                        """,
                        (response, connection_id, me))
                    conn.commit()

                messagebox.showinfo("Success", f"Request {response}!")
                self.view_connection_requests()  # Refresh

                try:
                    from education_system.systems.university.infrastructure.activity_logger import log_activity
                    log_activity('update', 'connection_request',
                                 details={'connection_id': connection_id, 'action': response})
                except Exception:
                    pass

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to respond: {str(e)}")

        def _save_basic_directory_settings(self, privacy_vars):
            """Save basic directory privacy settings"""
            messagebox.showinfo("Settings Saved", "Directory privacy settings have been saved successfully!")
            self.update_status("Directory settings updated")

        def _search_alumni_for_connection(self):
            """Search alumni for connection requests"""
            try:
                # Clear existing results
                for item in self.connection_alumni_tree.get_children():
                    self.connection_alumni_tree.delete(item)

                search_term = self.connection_search.get().strip()
                if not search_term:
                    messagebox.showwarning("Search Required", "Please enter a search term.")
                    return

                with db_get_connection() as conn:
                    self._ensure_connections_schema(conn)
                    cursor = conn.cursor()
                    me = self._current_alumni_id()

                    query = """
                        SELECT a.alumni_id, a.first_name || ' ' || a.last_name,
                               a.graduation_year, a.industry,
                               COALESCE(a.city || ', ' || a.country, a.city, a.country, '') AS location,
                               CASE
                                   WHEN EXISTS (
                                       SELECT 1 FROM alumni_connections
                                       WHERE (requester_id = ? AND recipient_id = a.alumni_id)
                                       OR (requester_id = a.alumni_id AND recipient_id = ?)
                                   ) THEN 'Connected/Pending'
                                   ELSE 'Not Connected'
                               END as status
                        FROM alumni a
                        WHERE (a.first_name LIKE ? OR a.last_name LIKE ?)
                        AND a.alumni_id != ?
                        ORDER BY a.last_name
                    """
                    cursor.execute(query, (me, me, f"%{escape_like(search_term)}%",
                                           f"%{escape_like(search_term)}%", me))
                    results = cursor.fetchall()

                    for alumni in results:
                        # iid carries the alumni_id; display the rest.
                        self.connection_alumni_tree.insert('', tk.END, iid=str(alumni[0]),
                                                           values=alumni[1:])

                    self.update_status(f"Found {len(results)} alumni")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Search failed: {str(e)}")

        def _send_selected_connection_request(self):
            """Send connection request to selected alumni"""
            if not hasattr(self, 'connection_alumni_tree'):
                return

            selection = self.connection_alumni_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an alumni to connect with.")
                return

            item = self.connection_alumni_tree.item(selection[0])
            alumni_data = item['values']

            # Check if already connected
            if alumni_data[4] == 'Connected/Pending':
                messagebox.showinfo("Already Connected",
                                  "You already have a connection or pending request with this alumni.")
                return

            # Create message dialog
            msg_window = tk.Toplevel(self.root)
            msg_window.title("Connection Request Message")
            msg_window.geometry("500x300")
            msg_window.configure(bg='white')
            msg_window.grab_set()

            frame = ttk.Frame(msg_window, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=f"Send connection request to {alumni_data[0]}",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            ttk.Label(frame, text="Message (optional):").pack(anchor='w')
            message_text = ScrolledText(frame, height=6, wrap=tk.WORD)
            message_text.pack(fill=tk.BOTH, expand=True, pady=(5, 20))

            recipient_id = selection[0]  # tree iid is the alumni_id

            def send_request():
                try:
                    with db_get_connection() as conn:
                        self._ensure_connections_schema(conn)
                        me = self._current_alumni_id()
                        conn.execute("""
                            INSERT INTO alumni_connections (
                                requester_id, recipient_id, status, message, request_date
                            ) VALUES (?, ?, 'pending', ?, datetime('now'))
                        """, (me, recipient_id, message_text.get(1.0, tk.END).strip()))
                        conn.commit()

                    messagebox.showinfo("Success", "Connection request sent!")
                    msg_window.destroy()
                    self._search_alumni_for_connection()  # Refresh

                    try:
                        from education_system.systems.university.infrastructure.activity_logger import log_activity
                        log_activity('create', 'connection_request',
                                     details={'recipient': alumni_data[0]})
                    except Exception:
                        pass

                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Failed to send request: {str(e)}")

            ttk.Button(frame, text="Send Request",
                      command=send_request).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(frame, text="Cancel",
                      command=msg_window.destroy).pack(side=tk.LEFT)

        def perform_directory_search(self, search_vars):
            """Search the alumni directory (real data). With no criteria, list
            every alumnus."""
            self.directory_results.delete(1.0, tk.END)

            search_criteria = {k: v.get().strip() for k, v in search_vars.items() if v.get().strip()}

            clauses = []
            params = []
            if 'name' in search_criteria:
                clauses.append("(first_name LIKE ? OR last_name LIKE ?)")
                like = f"%{escape_like(search_criteria['name'])}%"
                params += [like, like]
            if 'year' in search_criteria:
                clauses.append("CAST(graduation_year AS TEXT) LIKE ?")
                params.append(f"%{escape_like(search_criteria['year'])}%")
            if 'industry' in search_criteria:
                clauses.append("industry LIKE ?")
                params.append(f"%{escape_like(search_criteria['industry'])}%")
            if 'location' in search_criteria:
                clauses.append("(city LIKE ? OR country LIKE ? OR address LIKE ?)")
                like = f"%{escape_like(search_criteria['location'])}%"
                params += [like, like, like]
            if 'skills' in search_criteria:
                clauses.append("skills LIKE ?")
                params.append(f"%{escape_like(search_criteria['skills'])}%")

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            try:
                with db_get_connection() as conn:
                    rows = conn.execute(
                        "SELECT TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')), "
                        "graduation_year, job_title, current_employer, industry, "
                        "COALESCE(city || ', ' || country, city, country, '') AS location, is_mentor "
                        "FROM alumni" + where +
                        " ORDER BY COALESCE(graduation_year,0) DESC, last_name, first_name",
                        params).fetchall()
            except sqlite3.Error as e:
                self.directory_results.insert(tk.END, f"Search failed: {e}")
                return

            header = "Alumni Directory Search Results\n" + "=" * 40 + "\n\n"
            if search_criteria:
                header += "Search criteria: " + ", ".join(
                    f"{k}: {v}" for k, v in search_criteria.items()) + "\n\n"
            else:
                header += "Showing all alumni.\n\n"
            self.directory_results.insert(tk.END, header)

            if not rows:
                self.directory_results.insert(tk.END, "No alumni matched your search.")
                self.update_status("No alumni found")
                return

            for i, (name, year, title, employer, industry, location, is_mentor) in enumerate(rows, 1):
                line = f"{i}. {name or '(no name)'}"
                if year:
                    line += f" (Class of {year})"
                line += "\n"
                if title or employer:
                    line += f"   Current: {title or 'N/A'}{(' at ' + employer) if employer else ''}\n"
                if industry:
                    line += f"   Industry: {industry}\n"
                if location:
                    line += f"   Location: {location}\n"
                if is_mentor:
                    line += "   ✓ Available as mentor\n"
                self.directory_results.insert(tk.END, line + "\n")

            self.update_status(f"Found {len(rows)} alumni matching search criteria")

        def save_directory_settings(self):
            """Save directory privacy settings"""
            settings_summary = []
            for var_name, var in self.privacy_vars.items():
                if var.get():
                    settings_summary.append(var_name.replace('_', ' ').title())

            summary_text = "Settings saved:\n"
            summary_text += f"• Profile Visibility: {self.visibility_level.get()}\n"
            summary_text += f"• Contact Method: {self.contact_method.get()}\n"
            summary_text += f"• Notification Frequency: {self.notification_freq.get()}\n"
            summary_text += f"• Enabled Options: {', '.join(settings_summary)}"

            messagebox.showinfo("Settings Saved", summary_text)
            self.update_status("Directory settings updated")

        def send_connection_request(self):
            """Send connection request to another alumni"""
            self.clear_content()
            self.update_status("Send Connection Request")

            ttk.Label(self.content_frame, text="Send Connection Request",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Alumni search
            search_frame = ttk.LabelFrame(self.content_frame, text="Find Alumni", padding=10)
            search_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            ttk.Label(search_frame, text="Search by name:").pack(side=tk.LEFT, padx=(0, 10))
            self.connection_search = tk.StringVar()
            ttk.Entry(search_frame, textvariable=self.connection_search, width=30).pack(side=tk.LEFT, padx=(0, 20))

            ttk.Button(search_frame, text="Search",
                      command=self._search_alumni_for_connection).pack(side=tk.LEFT)

            # Search results
            results_frame = ttk.LabelFrame(self.content_frame, text="Alumni", padding=10)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Name', 'Graduation Year', 'Industry', 'Location', 'Status')
            self.connection_alumni_tree = ttk.Treeview(results_frame, columns=columns, show='headings')

            for col in columns:
                self.connection_alumni_tree.heading(col, text=col)
                self.connection_alumni_tree.column(col, width=130)

            scrollbar_y = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                        command=self.connection_alumni_tree.yview)
            self.connection_alumni_tree.configure(yscrollcommand=scrollbar_y.set)

            self.connection_alumni_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="Send Connection Request",
                      command=self._send_selected_connection_request).pack(side=tk.LEFT)

        def show_alumni_directory(self):
            """Show alumni directory settings"""
            self.clear_content()
            self.update_status("Alumni Directory Settings")

            ttk.Label(self.content_frame, text="Alumni Directory Privacy Settings",
                     font=('Arial', 16, 'bold')).pack(pady=20)

            settings_frame = ttk.LabelFrame(self.content_frame, text="Privacy Settings", padding=20)
            settings_frame.pack(fill=tk.X, pady=20, padx=20)

            # Privacy checkboxes
            privacy_vars = {}
            privacy_options = [
                ("show_contact", "Show contact information in directory"),
                ("show_employment", "Show employment information"),
                ("show_education", "Show education information"),
                ("searchable", "Make profile searchable"),
                ("networking", "Available for networking"),
                ("mentor", "Available as mentor")
            ]

            for var_name, description in privacy_options:
                privacy_vars[var_name] = tk.BooleanVar(value=True)
                ttk.Checkbutton(settings_frame, text=description,
                               variable=privacy_vars[var_name]).pack(anchor='w', pady=5)

            # Save button
            ttk.Button(settings_frame, text="Save Settings",
                      command=lambda: self._save_basic_directory_settings(privacy_vars)).pack(pady=20)

        def show_connections(self):
            """Networking connections — uses the functional, DB-backed view."""
            self.view_connection_requests()

        def show_directory_search(self):
            """Show advanced directory search"""
            self.clear_content()
            self.update_status("Alumni Directory Search")

            ttk.Label(self.content_frame, text="Alumni Directory Search",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Search form
            search_frame = ttk.LabelFrame(self.content_frame, text="Search Criteria", padding=10)
            search_frame.pack(fill=tk.X, pady=(0, 20), padx=20)

            search_vars = {}
            search_fields = [
                ("Name", "name"),
                ("Graduation Year", "year"),
                ("Industry", "industry"),
                ("Location", "location"),
                ("Skills", "skills")
            ]

            # Create fields grid
            fields_container = ttk.Frame(search_frame)
            fields_container.pack(fill=tk.X, pady=(0, 10))

            for i, (label, var_name) in enumerate(search_fields):
                row = i // 2
                col = i % 2

                field_frame = ttk.Frame(fields_container)
                field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

                ttk.Label(field_frame, text=f"{label}:").pack(anchor='w')
                search_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=search_vars[var_name]).pack(fill=tk.X)

            fields_container.columnconfigure(0, weight=1)
            fields_container.columnconfigure(1, weight=1)

            # Search button in separate frame using pack
            ttk.Button(search_frame, text="Search Directory",
                      command=lambda: self.perform_directory_search(search_vars)).pack(pady=10)

            # Results area
            self.directory_results = ScrolledText(self.content_frame, height=15, wrap=tk.WORD)
            self.directory_results.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        def show_directory_settings(self):
            """Show directory privacy settings with scrollbar"""
            self.clear_content()
            self.update_status("Directory Settings")

            # Create scrollable container
            canvas = tk.Canvas(self.content_frame)
            scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Enable mouse wheel scrolling
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")

            def _on_mousewheel_linux(event):
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")

            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel_linux)
            canvas.bind_all("<Button-5>", _on_mousewheel_linux)

            # Pack scrollbar and canvas
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Title
            ttk.Label(scrollable_frame, text="Alumni Directory Privacy Settings",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20), padx=20)

            # Settings form
            settings_frame = ttk.LabelFrame(scrollable_frame, text="Privacy Settings", padding=20)
            settings_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            # Privacy options
            self.privacy_vars = {}

            privacy_options = [
                ("show_contact", "Show contact information in directory"),
                ("show_employment", "Show employment information"),
                ("show_education", "Show education information"),
                ("searchable", "Make profile searchable"),
                ("networking", "Available for networking requests"),
                ("mentor", "Available as mentor"),
                ("email_notifications", "Receive email notifications"),
                ("event_invitations", "Receive event invitations"),
                ("newsletter", "Subscribe to alumni newsletter")
            ]

            for var_name, description in privacy_options:
                self.privacy_vars[var_name] = tk.BooleanVar(value=True)
                ttk.Checkbutton(settings_frame, text=description,
                               variable=self.privacy_vars[var_name]).pack(anchor='w', pady=5)

            # Profile visibility level
            visibility_frame = ttk.LabelFrame(scrollable_frame, text="Profile Visibility", padding=20)
            visibility_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            self.visibility_level = tk.StringVar(value="Alumni Only")

            ttk.Radiobutton(visibility_frame, text="Public (visible to all)",
                           variable=self.visibility_level, value="Public").pack(anchor='w', pady=2)
            ttk.Radiobutton(visibility_frame, text="Alumni Only (registered alumni only)",
                           variable=self.visibility_level, value="Alumni Only").pack(anchor='w', pady=2)
            ttk.Radiobutton(visibility_frame, text="Private (only visible to me)",
                           variable=self.visibility_level, value="Private").pack(anchor='w', pady=2)

            # Communication preferences
            comm_frame = ttk.LabelFrame(scrollable_frame, text="Communication Preferences", padding=20)
            comm_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            ttk.Label(comm_frame, text="Preferred Contact Method:").pack(anchor='w', pady=(0, 5))
            self.contact_method = tk.StringVar(value="Email")

            contact_methods = ["Email", "Phone", "LinkedIn", "Alumni Platform Messages"]
            for method in contact_methods:
                ttk.Radiobutton(comm_frame, text=method, variable=self.contact_method,
                               value=method).pack(anchor='w', pady=2)

            # Notification frequency
            freq_frame = ttk.Frame(comm_frame)
            freq_frame.pack(fill=tk.X, pady=(10, 0))

            ttk.Label(freq_frame, text="Notification Frequency:").pack(side=tk.LEFT, padx=(0, 10))
            self.notification_freq = tk.StringVar(value="Weekly")
            freq_combo = ttk.Combobox(freq_frame, textvariable=self.notification_freq,
                                     values=["Immediate", "Daily", "Weekly", "Monthly", "Never"])
            freq_combo.pack(side=tk.LEFT)

            # Save button
            ttk.Button(scrollable_frame, text="Save Settings",
                      command=self.save_directory_settings).pack(pady=20)

        def view_connection_requests(self):
            """View pending connection requests"""
            self.clear_content()
            self.update_status("Connection Requests")

            ttk.Label(self.content_frame, text="Connection Requests",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 10))

            # Toolbar
            toolbar = ttk.Frame(self.content_frame)
            toolbar.pack(fill=tk.X, padx=20, pady=(0, 10))
            ttk.Button(toolbar, text="➕ Find Alumni to Connect",
                       command=self.send_connection_request).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(toolbar, text="🔄 Refresh",
                       command=self.view_connection_requests).pack(side=tk.LEFT)

            # Tabs
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Incoming requests tab
            incoming_frame = ttk.Frame(notebook)
            notebook.add(incoming_frame, text="Incoming Requests")

            incoming_table = ttk.Frame(incoming_frame)
            incoming_table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ('From', 'Industry', 'Message', 'Date')
            self.incoming_requests_tree = ttk.Treeview(incoming_table, columns=columns, show='headings')

            for col in columns:
                self.incoming_requests_tree.heading(col, text=col)
                self.incoming_requests_tree.column(col, width=150)

            scrollbar_y = ttk.Scrollbar(incoming_table, orient=tk.VERTICAL,
                                        command=self.incoming_requests_tree.yview)
            self.incoming_requests_tree.configure(yscrollcommand=scrollbar_y.set)

            self.incoming_requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load incoming requests
            try:
                with db_get_connection() as conn:
                    self._ensure_connections_schema(conn)
                    cursor = conn.cursor()
                    me = self._current_alumni_id()

                    query = """
                        SELECT c.connection_id, a.first_name || ' ' || a.last_name,
                               a.industry, c.message, c.request_date
                        FROM alumni_connections c
                        JOIN alumni a ON c.requester_id = a.alumni_id
                        WHERE c.recipient_id = ? AND c.status = 'pending'
                        ORDER BY c.request_date DESC
                    """
                    cursor.execute(query, (me,))
                    requests = cursor.fetchall()

                    for req in requests:
                        self.incoming_requests_tree.insert('', tk.END, iid=str(req[0]),
                                                           values=req[1:])

                    self.update_status(f"{len(requests)} incoming request(s)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load requests: {str(e)}")

            # Action buttons for incoming
            incoming_buttons = ttk.Frame(incoming_frame)
            incoming_buttons.pack(fill=tk.X, padx=10, pady=(0, 10))

            ttk.Button(incoming_buttons, text="Accept",
                      command=lambda: self._respond_to_request('accepted')).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(incoming_buttons, text="Decline",
                      command=lambda: self._respond_to_request('declined')).pack(side=tk.LEFT)

            # Outgoing requests tab
            outgoing_frame = ttk.Frame(notebook)
            notebook.add(outgoing_frame, text="Sent Requests")

            outgoing_table = ttk.Frame(outgoing_frame)
            outgoing_table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns_out = ('To', 'Industry', 'Status', 'Date')
            self.outgoing_requests_tree = ttk.Treeview(outgoing_table, columns=columns_out, show='headings')

            for col in columns_out:
                self.outgoing_requests_tree.heading(col, text=col)
                self.outgoing_requests_tree.column(col, width=150)

            scrollbar_y2 = ttk.Scrollbar(outgoing_table, orient=tk.VERTICAL,
                                         command=self.outgoing_requests_tree.yview)
            self.outgoing_requests_tree.configure(yscrollcommand=scrollbar_y2.set)

            self.outgoing_requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y2.pack(side=tk.RIGHT, fill=tk.Y)

            # Load outgoing requests
            try:
                with db_get_connection() as conn:
                    self._ensure_connections_schema(conn)
                    cursor = conn.cursor()
                    me = self._current_alumni_id()

                    query = """
                        SELECT a.first_name || ' ' || a.last_name, a.industry,
                               c.status, c.request_date
                        FROM alumni_connections c
                        JOIN alumni a ON c.recipient_id = a.alumni_id
                        WHERE c.requester_id = ?
                        ORDER BY c.request_date DESC
                    """
                    cursor.execute(query, (me,))
                    requests = cursor.fetchall()

                    for req in requests:
                        self.outgoing_requests_tree.insert('', tk.END, values=req)

            except sqlite3.Error:
                pass  # Silently handle database errors in background refresh

