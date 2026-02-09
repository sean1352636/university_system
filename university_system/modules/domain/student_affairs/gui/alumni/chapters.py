import tkinter as tk
from university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from university_system.modules.shared.utils.i18n import (
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
    from university_system.modules.domain.student_affairs.services.alumni_management import (
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



class ChaptersMixin:
        def _clear_chapter_form(self):
            """Clear chapter creation form"""
            for var in self.new_chapter_vars.values():
                var.set("")
            self.new_chapter_description.delete(1.0, tk.END)

        def _delete_chapter_admin(self):
            """Delete selected chapter"""
            selection = self.admin_chapters_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a chapter to delete.")
                return

            item = self.admin_chapters_tree.item(selection[0])
            chapter_data = item['values']
            chapter_id = chapter_data[0]

            if messagebox.askyesno("Confirm Deletion",
                                  f"Are you sure you want to delete '{chapter_data[1]}'? "
                                  f"This will also remove all {chapter_data[4]} member(s)."):
                try:
                    with db_get_connection() as conn:
                        cursor = conn.cursor()

                        # Delete chapter members first
                        cursor.execute("DELETE FROM chapter_members WHERE chapter_id = ?", (chapter_id,))

                        # Delete chapter
                        cursor.execute("DELETE FROM regional_chapters WHERE chapter_id = ?", (chapter_id,))

                        conn.commit()

                    messagebox.showinfo("Success", "Chapter deleted successfully!")
                    self._load_all_chapters()

                    # Log activity
                    from university_system.modules.shared.utils.activity_logger import log_activity
                    log_activity('delete', 'chapter', chapter_id=chapter_id,
                               details={'name': chapter_data[1], 'action': 'deleted'})

                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Failed to delete chapter: {str(e)}")

        def _edit_chapter_admin(self):
            """Edit selected chapter"""
            selection = self.admin_chapters_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a chapter to edit.")
                return

            item = self.admin_chapters_tree.item(selection[0])
            chapter_data = item['values']
            chapter_id = chapter_data[0]

            # Create edit dialog
            edit_window = tk.Toplevel(self.root)
            edit_window.title(f"Edit Chapter - {chapter_data[1]}")
            edit_window.geometry("500x400")
            edit_window.configure(bg='white')
            edit_window.grab_set()

            frame = ttk.Frame(edit_window, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=f"Edit Chapter: {chapter_data[1]}",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Form fields
            edit_vars = {}
            fields = [
                ("Chapter Name:", "name", chapter_data[1]),
                ("Location:", "location", chapter_data[2]),
                ("Coordinator:", "coordinator", chapter_data[3])
            ]

            for label, var_name, default_value in fields:
                field_frame = ttk.Frame(frame)
                field_frame.pack(fill=tk.X, pady=5)

                ttk.Label(field_frame, text=label, width=15).pack(side=tk.LEFT, padx=(0, 10))
                edit_vars[var_name] = tk.StringVar(value=default_value)
                ttk.Entry(field_frame, textvariable=edit_vars[var_name]).pack(
                    side=tk.LEFT, fill=tk.X, expand=True)

            def save_chapter_changes():
                try:
                    with db_get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE regional_chapters
                            SET chapter_name = ?, location = ?, coordinator_name = ?
                            WHERE chapter_id = ?
                        """, (
                            edit_vars['name'].get(),
                            edit_vars['location'].get(),
                            edit_vars['coordinator'].get(),
                            chapter_id
                        ))
                        conn.commit()

                    messagebox.showinfo("Success", "Chapter updated successfully!")
                    edit_window.destroy()
                    self._load_all_chapters()

                    # Log activity
                    from university_system.modules.shared.utils.activity_logger import log_activity
                    log_activity('update', 'chapter', chapter_id=chapter_id,
                               details={'name': edit_vars['name'].get()})

                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Failed to update chapter: {str(e)}")

            ttk.Button(frame, text="Save Changes",
                      command=save_chapter_changes).pack(pady=20)
            ttk.Button(frame, text="Cancel",
                      command=edit_window.destroy).pack()

        def _join_selected_chapter(self):
            """Join the selected chapter"""
            if not hasattr(self, 'join_chapters_tree'):
                return

            selection = self.join_chapters_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a chapter to join.")
                return

            item = self.join_chapters_tree.item(selection[0])
            chapter_data = item['values']
            chapter_name = chapter_data[0]

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    # Get chapter_id
                    cursor.execute("SELECT chapter_id FROM regional_chapters WHERE chapter_name = ?",
                                 (chapter_name,))
                    result = cursor.fetchone()

                    if result:
                        chapter_id = result[0]

                        # Join chapter
                        cursor.execute("""
                            INSERT INTO chapter_members (chapter_id, member_id, role, join_date, status)
                            VALUES (?, ?, 'member', datetime('now'), 'active')
                        """, (chapter_id, user_id))

                        # Update member count
                        cursor.execute("""
                            UPDATE regional_chapters
                            SET member_count = member_count + 1
                            WHERE chapter_id = ?
                        """, (chapter_id,))

                        conn.commit()

                        messagebox.showinfo("Success", f"You have joined {chapter_name}!")
                        self.join_regional_chapter()  # Refresh

                        # Log activity
                        from university_system.modules.shared.utils.activity_logger import log_activity
                        log_activity('create', 'chapter_membership',
                                   details={'chapter': chapter_name, 'action': 'joined'})

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to join chapter: {str(e)}")

        def _leave_chapter(self):
            """Leave a selected chapter"""
            if not hasattr(self, 'my_chapters_tree'):
                return

            selection = self.my_chapters_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a chapter to leave.")
                return

            if messagebox.askyesno("Confirm Leave",
                                  "Are you sure you want to leave this chapter?"):
                item = self.my_chapters_tree.item(selection[0])
                chapter_data = item['values']
                chapter_name = chapter_data[0]

                try:
                    with db_get_connection() as conn:
                        cursor = conn.cursor()
                        user_id = self._current_user_id()

                        # Get chapter_id
                        cursor.execute("SELECT chapter_id FROM regional_chapters WHERE chapter_name = ?",
                                     (chapter_name,))
                        result = cursor.fetchone()

                        if result:
                            chapter_id = result[0]
                            cursor.execute("""
                                DELETE FROM chapter_members
                                WHERE chapter_id = ? AND member_id = ?
                            """, (chapter_id, user_id))

                            # Update member count
                            cursor.execute("""
                                UPDATE regional_chapters
                                SET member_count = member_count - 1
                                WHERE chapter_id = ?
                            """, (chapter_id,))

                            conn.commit()

                            messagebox.showinfo("Success", f"You have left {chapter_name}.")
                            self.view_my_chapters()  # Refresh

                            # Log activity
                            from university_system.modules.shared.utils.activity_logger import log_activity
                            log_activity('delete', 'chapter_membership',
                                       details={'chapter': chapter_name, 'action': 'left'})

                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Failed to leave chapter: {str(e)}")

        def _load_all_chapters(self):
            """Load all chapters for admin view"""
            try:
                # Clear existing data
                for item in self.admin_chapters_tree.get_children():
                    self.admin_chapters_tree.delete(item)

                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    query = """
                        SELECT chapter_id, chapter_name, location, coordinator_name,
                               member_count, status, created_date
                        FROM regional_chapters
                        ORDER BY created_date DESC
                    """
                    cursor.execute(query)
                    chapters = cursor.fetchall()

                    for chapter in chapters:
                        self.admin_chapters_tree.insert('', tk.END, values=chapter)

                    self.update_status(f"Loaded {len(chapters)} chapter(s)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load chapters: {str(e)}")

        def _submit_new_chapter(self):
            """Submit new chapter creation"""
            # Validation
            if not self.new_chapter_vars['name'].get().strip():
                messagebox.showerror("Validation Error", "Chapter name is required!")
                return

            if not self.new_chapter_vars['location'].get().strip():
                messagebox.showerror("Validation Error", "Location is required!")
                return

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    # Insert chapter
                    cursor.execute("""
                        INSERT INTO regional_chapters (
                            chapter_name, location, coordinator_name, contact_email,
                            description, created_date, created_by, status, member_count
                        ) VALUES (?, ?, ?, ?, ?, datetime('now'), ?, 'active', 0)
                    """, (
                        self.new_chapter_vars['name'].get(),
                        self.new_chapter_vars['location'].get(),
                        self.new_chapter_vars['coordinator'].get() or user_id,
                        self.new_chapter_vars['email'].get(),
                        self.new_chapter_description.get(1.0, tk.END).strip(),
                        user_id
                    ))

                    chapter_id = cursor.lastrowid

                    # Auto-join the creator
                    cursor.execute("""
                        INSERT INTO chapter_members (chapter_id, member_id, role, join_date, status)
                        VALUES (?, ?, 'coordinator', datetime('now'), 'active')
                    """, (chapter_id, user_id))

                    # Update member count
                    cursor.execute("""
                        UPDATE regional_chapters
                        SET member_count = 1
                        WHERE chapter_id = ?
                    """, (chapter_id,))

                    conn.commit()

                messagebox.showinfo("Success", "Regional chapter created successfully!")
                self.update_status("Chapter created")
                self._clear_chapter_form()

                # Log activity
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('create', 'chapter', chapter_id=chapter_id,
                           details={'name': self.new_chapter_vars['name'].get()})

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to create chapter: {str(e)}")

        def _update_chapter_status(self, status):
            """Update chapter status"""
            selection = self.admin_chapters_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a chapter.")
                return

            item = self.admin_chapters_tree.item(selection[0])
            chapter_data = item['values']
            chapter_id = chapter_data[0]

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE regional_chapters
                        SET status = ?
                        WHERE chapter_id = ?
                    """, (status, chapter_id))
                    conn.commit()

                messagebox.showinfo("Success", f"Chapter {status}!")
                self._load_all_chapters()

                # Log activity
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('update', 'chapter', chapter_id=chapter_id,
                           details={'action': f'status_changed_to_{status}'})

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to update status: {str(e)}")

        def admin_manage_chapters(self):
            """Admin controls for managing chapters"""
            if not self.has_permission('admin') and not self.has_permission('manage_alumni'):
                messagebox.showerror("Permission Denied",
                                   "You don't have permission to manage chapters.")
                return

            self.clear_content()
            self.update_status("Manage Chapters (Admin)")

            ttk.Label(self.content_frame, text="Chapter Management (Admin)",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Chapters table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Chapter ID', 'Chapter Name', 'Location', 'Coordinator', 'Members', 'Status', 'Created')
            self.admin_chapters_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.admin_chapters_tree.heading(col, text=col)
                if col == 'Chapter ID':
                    self.admin_chapters_tree.column(col, width=80)
                else:
                    self.admin_chapters_tree.column(col, width=120)

            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.admin_chapters_tree.yview)
            self.admin_chapters_tree.configure(yscrollcommand=scrollbar_y.set)

            self.admin_chapters_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load all chapters
            self._load_all_chapters()

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="Edit Chapter",
                      command=self._edit_chapter_admin).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Deactivate",
                      command=lambda: self._update_chapter_status('inactive')).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Activate",
                      command=lambda: self._update_chapter_status('active')).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Delete Chapter",
                      command=self._delete_chapter_admin).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self._load_all_chapters).pack(side=tk.LEFT)

        def create_regional_chapter(self):
            """Create a new regional chapter"""
            self.clear_content()
            self.update_status("Create Regional Chapter")

            ttk.Label(self.content_frame, text="Create a New Regional Chapter",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Form
            form_frame = ttk.LabelFrame(self.content_frame, text="Chapter Details", padding=10)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Form fields
            self.new_chapter_vars = {}

            fields = [
                ("Chapter Name*", "name"),
                ("Location*", "location"),
                ("Coordinator Name", "coordinator"),
                ("Contact Email", "email")
            ]

            for label, var_name in fields:
                field_frame = ttk.Frame(form_frame)
                field_frame.pack(fill=tk.X, pady=5)

                ttk.Label(field_frame, text=label, width=18).pack(side=tk.LEFT, padx=(0, 10))
                self.new_chapter_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.new_chapter_vars[var_name]).pack(
                    side=tk.LEFT, fill=tk.X, expand=True)

            # Description
            ttk.Label(form_frame, text="Chapter Description:").pack(anchor='w', pady=(10, 5))
            self.new_chapter_description = ScrolledText(form_frame, height=5, wrap=tk.WORD)
            self.new_chapter_description.pack(fill=tk.X)

            # Action buttons
            button_frame = ttk.Frame(form_frame)
            button_frame.pack(fill=tk.X, pady=(20, 0))

            ttk.Button(button_frame, text="Create Chapter",
                      command=self._submit_new_chapter).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Clear Form",
                      command=self._clear_chapter_form).pack(side=tk.LEFT)

        def join_regional_chapter(self):
            """Join a regional chapter"""
            self.clear_content()
            self.update_status("Join Regional Chapter")

            ttk.Label(self.content_frame, text="Join a Regional Chapter",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Available chapters
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Chapter Name', 'Location', 'Coordinator', 'Members', 'Status')
            self.join_chapters_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.join_chapters_tree.heading(col, text=col)
                self.join_chapters_tree.column(col, width=150)

            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.join_chapters_tree.yview)
            self.join_chapters_tree.configure(yscrollcommand=scrollbar_y.set)

            self.join_chapters_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load available chapters (not already joined)
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    query = """
                        SELECT rc.chapter_id, rc.chapter_name, rc.location,
                               rc.coordinator_name, rc.member_count, rc.status
                        FROM regional_chapters rc
                        WHERE rc.status = 'active'
                        AND rc.chapter_id NOT IN (
                            SELECT chapter_id FROM chapter_members WHERE member_id = ?
                        )
                        ORDER BY rc.chapter_name
                    """
                    cursor.execute(query, (user_id,))
                    chapters = cursor.fetchall()

                    for chapter in chapters:
                        # Display without chapter_id
                        self.join_chapters_tree.insert('', tk.END, values=chapter[1:])

                    self.update_status(f"Found {len(chapters)} available chapter(s)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load chapters: {str(e)}")

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="Join Selected Chapter",
                      command=self._join_selected_chapter).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self.join_regional_chapter).pack(side=tk.LEFT)

        def show_regional_chapters(self):
            """Show regional chapters interface"""
            self.clear_content()
            self.update_status("Regional Alumni Chapters")

            ttk.Label(self.content_frame, text="Regional Alumni Chapters",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for different chapter views
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # View chapters tab
            chapters_frame = ttk.Frame(notebook)
            notebook.add(chapters_frame, text="All Chapters")

            chapters_text = ScrolledText(chapters_frame, wrap=tk.WORD)
            chapters_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            chapters_content = """Regional Alumni Chapters:

    🌎 San Francisco Bay Area Chapter
    Coordinator: Sarah Johnson (Class of 2015)
    Members: 45
    Location: San Francisco, CA
    Description: Connecting tech industry alumni in the Bay Area
    Created: 2023-01-15

    📧 Contact: sf.chapter@alumni.edu
    ---

    🌎 New York City Chapter
    Coordinator: Michael Chen (Class of 2018)
    Members: 62
    Location: New York, NY
    Description: Networking and professional development for NYC alumni
    Created: 2022-09-20

    📧 Contact: nyc.chapter@alumni.edu
    ---

    🌎 Boston Chapter
    Coordinator: Emily Davis (Class of 2020)
    Members: 28
    Location: Boston, MA
    Description: Alumni community in the greater Boston area
    Created: 2024-03-10

    📧 Contact: boston.chapter@alumni.edu
    """
            chapters_text.insert(tk.END, chapters_content)

            # My chapters tab
            my_chapters_frame = ttk.Frame(notebook)
            notebook.add(my_chapters_frame, text="My Chapters")

            my_chapters_text = ScrolledText(my_chapters_frame, wrap=tk.WORD)
            my_chapters_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            my_chapters_content = """My Chapter Memberships:

    ✅ San Francisco Bay Area Chapter
       Role: Member
       Joined: 2025-06-15
       Last Activity: 2025-08-10

       Upcoming Events:
       • Tech Networking Mixer - August 25, 2025
       • Annual Chapter Picnic - September 15, 2025

    ---

    Available Chapters to Join:

    🔗 New York City Chapter
       [Join Chapter]

    🔗 Boston Chapter
       [Join Chapter]
    """
            my_chapters_text.insert(tk.END, my_chapters_content)

        def view_my_chapters(self):
            """View chapters the user is member of"""
            self.clear_content()
            self.update_status("My Chapters")

            ttk.Label(self.content_frame, text="My Chapter Memberships",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Chapters table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Chapter Name', 'Location', 'Role', 'Joined Date', 'Status')
            self.my_chapters_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.my_chapters_tree.heading(col, text=col)
                self.my_chapters_tree.column(col, width=150)

            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.my_chapters_tree.yview)
            self.my_chapters_tree.configure(yscrollcommand=scrollbar_y.set)

            self.my_chapters_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load user's chapters
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    query = """
                        SELECT rc.chapter_name, rc.location, cm.role,
                               cm.join_date, cm.status
                        FROM chapter_members cm
                        JOIN regional_chapters rc ON cm.chapter_id = rc.chapter_id
                        WHERE cm.member_id = ?
                        ORDER BY cm.join_date DESC
                    """
                    cursor.execute(query, (user_id,))
                    chapters = cursor.fetchall()

                    for chapter in chapters:
                        self.my_chapters_tree.insert('', tk.END, values=chapter)

                    self.update_status(f"You are a member of {len(chapters)} chapter(s)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load chapters: {str(e)}")

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="Leave Chapter",
                      command=self._leave_chapter).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Join New Chapter",
                      command=self.join_regional_chapter).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self.view_my_chapters).pack(side=tk.LEFT)

