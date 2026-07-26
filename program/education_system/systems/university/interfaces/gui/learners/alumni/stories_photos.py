from education_system.systems.university.infrastructure.sql_safety import escape_like
import tkinter as tk
import os
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

# Import secure file upload handler
try:
    from education_system.systems.university.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    def secure_filename(x):
        return x

# Import activity logger
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

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
from education_system.systems.university.interfaces.gui.learners.alumni._service_imports import init_alumni_db, register_alumni, view_alumni, update_alumni, view_events, create_enhanced_event, event_check_in_system, record_donation, view_donations, setup_mentorship, view_mentorships, search_alumni_directory, view_connection_requests, manage_business_directory, create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board, schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign, view_engagement_leaderboard, view_my_badges, manage_photo_gallery, manage_class_reunions, manage_regional_chapters, setup_alumni_directory, generate_alumni_report, set_auth, setup_alumni_permissions, smart_mentorship_matching, generate_engagement_recommendations, create_alumni_story, get_connection



class StoriesPhotosMixin:
        def _delete_my_photo(self):
            """Delete a selected photo"""
            if not hasattr(self, 'my_photos_tree'):
                return

            selection = self.my_photos_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a photo to delete.")
                return

            if messagebox.askyesno("Confirm Deletion",
                                   "Are you sure you want to delete this photo?"):
                item = self.my_photos_tree.item(selection[0])
                photo_data = item['values']

                try:
                    with db_get_connection() as conn:
                        cursor = conn.cursor()
                        user_id = self._current_user_id()

                        # Delete from database
                        cursor.execute("""
                            DELETE FROM photo_gallery
                            WHERE uploaded_by = ? AND photo_path LIKE ?
                        """, (user_id, f"%{escape_like(photo_data[1])}"))

                        conn.commit()

                    messagebox.showinfo("Success", "Photo deleted successfully!")
                    self.view_my_photos()  # Refresh

                    # Log activity
                    from education_system.systems.university.infrastructure.activity_logger import log_activity
                    log_activity('delete', 'photo', details={'photo_path': photo_data[1]})

                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Failed to delete photo: {str(e)}")

        def _load_alumni_stories(self):
            """Load alumni stories from database"""
            try:
                # Clear existing data
                for item in self.stories_tree.get_children():
                    self.stories_tree.delete(item)

                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    query = """
                        SELECT story_id, title, author_name, category, published_date, view_count
                        FROM alumni_stories
                        WHERE status = 'published'
                    """
                    params = []

                    # Add category filter
                    category = self.story_filter_category.get()
                    if category != "All":
                        query += " AND category = ?"
                        params.append(category)

                    query += " ORDER BY published_date DESC"

                    cursor.execute(query, params)
                    stories = cursor.fetchall()

                    for story in stories:
                        # Display without story_id
                        self.stories_tree.insert('', tk.END, values=story[1:])

                    self.update_status(f"Loaded {len(stories)} story/stories")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load stories: {str(e)}")

        def _load_event_photos(self):
            """Load photos for selected event"""
            try:
                # Clear existing data
                for item in self.event_photos_tree.get_children():
                    self.event_photos_tree.delete(item)

                event_selection = self.event_photo_filter.get()
                if not event_selection or event_selection == "No events available":
                    messagebox.showwarning("No Event", "Please select an event.")
                    return

                # Extract event_id from selection (format: "Event Name (ID: 123)")
                import re
                match = re.search(r'ID:\s*(\d+)', event_selection)
                if not match:
                    messagebox.showerror("Error", "Invalid event selection.")
                    return

                event_id = int(match.group(1))

                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    query = """
                        SELECT photo_id, uploaded_by, caption, upload_date, status
                        FROM photo_gallery
                        WHERE event_id = ?
                        ORDER BY upload_date DESC
                    """
                    cursor.execute(query, (event_id,))
                    photos = cursor.fetchall()

                    for photo in photos:
                        self.event_photos_tree.insert('', tk.END, values=photo)

                    self.update_status(f"Loaded {len(photos)} photo(s) for event")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load event photos: {str(e)}")

        def _load_photos_for_moderation(self):
            """Load photos for moderation based on filter"""
            try:
                # Clear existing data
                for item in self.moderate_photos_tree.get_children():
                    self.moderate_photos_tree.delete(item)

                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    query = """
                        SELECT pg.photo_id, e.title, pg.uploaded_by,
                               pg.caption, pg.upload_date, pg.status
                        FROM photo_gallery pg
                        LEFT JOIN unified_events e ON pg.event_id = e.event_id
                        WHERE 1=1
                    """
                    params = []

                    # Add status filter
                    status = self.photo_status_filter.get()
                    if status != "All":
                        query += " AND pg.status = ?"
                        params.append(status)

                    query += " ORDER BY pg.upload_date DESC"

                    cursor.execute(query, params)
                    photos = cursor.fetchall()

                    for photo in photos:
                        self.moderate_photos_tree.insert('', tk.END, values=photo)

                    self.update_status(f"Loaded {len(photos)} photo(s) for moderation")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load photos: {str(e)}")

        def _moderate_photo_action(self, action):
            """Perform moderation action on selected photo"""
            if not hasattr(self, 'moderate_photos_tree'):
                return

            selection = self.moderate_photos_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a photo.")
                return

            item = self.moderate_photos_tree.item(selection[0])
            photo_data = item['values']
            photo_id = photo_data[0]

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    if action == 'deleted':
                        # Delete the photo
                        cursor.execute("DELETE FROM photo_gallery WHERE photo_id = ?", (photo_id,))
                        message = "Photo deleted successfully!"
                    else:
                        # Update status
                        cursor.execute("""
                            UPDATE photo_gallery
                            SET status = ?
                            WHERE photo_id = ?
                        """, (action, photo_id))
                        message = f"Photo {action} successfully!"

                    conn.commit()

                messagebox.showinfo("Success", message)
                self._load_photos_for_moderation()  # Refresh

                # Log activity
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('update', 'photo', photo_id=photo_id,
                           details={'action': action, 'moderator': self._current_user_id()})

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to perform action: {str(e)}")

        def browse_photo_files(self):
            """Select photo files for upload and stage them for storage."""
            filepaths = filedialog.askopenfilenames(
                title="Select photo files",
                filetypes=[
                    ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                    ("All files", "*.*")
                ]
            )
            if not filepaths:
                return

            self._photo_file_paths = list(filepaths)
            filenames = [Path(path).name for path in self._photo_file_paths]
            preview = ", ".join(filenames[:3])
            if len(filenames) > 3:
                preview += ", ..."
            self.selected_files.set(f"{len(filenames)} photo(s) selected: {preview}")
            self.update_status(f"Selected {len(filenames)} photo(s) for upload")

        def create_photo_upload_form(self, parent):
            """Create photo upload form"""
            ttk.Label(parent, text="Upload Event Photos",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            # Event selection
            event_frame = ttk.Frame(form_frame)
            event_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(event_frame, text="Select Event:").pack(side=tk.LEFT, padx=(0, 10))
            self.photo_event = tk.StringVar()
            events = self._get_event_options()
            self._event_lookup = {row['event_name']: row['event_id'] for row in events}
            if self._event_lookup:
                event_names = list(self._event_lookup.keys())
            else:
                event_names = []
            event_combo = ttk.Combobox(event_frame, textvariable=self.photo_event,
                                      values=event_names if event_names else ["No events available"],
                                      state='readonly' if event_names else 'disabled')
            event_combo.pack(side=tk.LEFT)
            if event_names:
                self.photo_event.set(event_names[0])
            else:
                self.photo_event.set("")

            # File selection (simulated)
            file_frame = ttk.Frame(form_frame)
            file_frame.pack(fill=tk.X, pady=10)

            ttk.Label(file_frame, text="Select Photos:").pack(anchor='w')
            file_info_frame = ttk.Frame(file_frame)
            file_info_frame.pack(fill=tk.X, pady=(5, 0))

            self.selected_files = tk.StringVar(value="No files selected")
            ttk.Label(file_info_frame, textvariable=self.selected_files).pack(side=tk.LEFT)
            ttk.Button(file_info_frame, text="Browse Files",
                      command=self.browse_photo_files).pack(side=tk.RIGHT)

            # Caption
            caption_frame = ttk.Frame(form_frame)
            caption_frame.pack(fill=tk.X, pady=10)

            ttk.Label(caption_frame, text="Album Caption:").pack(anchor='w')
            self.photo_caption = ScrolledText(caption_frame, height=3, wrap=tk.WORD)
            self.photo_caption.pack(fill=tk.X, pady=(5, 0))

            # Upload button
            ttk.Button(form_frame, text="Upload Photos",
                      command=self.upload_photos).pack(pady=20)

        def create_story_form(self, parent):
            """Create the story submission form"""
            ttk.Label(parent, text="Share Your Alumni Story",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            # Story type
            type_frame = ttk.Frame(form_frame)
            type_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(type_frame, text="Story Type:").pack(side=tk.LEFT, padx=(0, 10))
            self.story_type = tk.StringVar()
            type_combo = ttk.Combobox(type_frame, textvariable=self.story_type,
                                     values=["Career Achievement", "Community Service", "Entrepreneurship",
                                            "Research & Innovation", "Personal Journey", "Alumni Spotlight"])
            type_combo.pack(side=tk.LEFT)
            type_combo.set("Career Achievement")

            # Title
            title_frame = ttk.Frame(form_frame)
            title_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(title_frame, text="Story Title:").pack(anchor='w')
            self.story_title = tk.StringVar()
            ttk.Entry(title_frame, textvariable=self.story_title).pack(fill=tk.X, pady=(5, 0))

            # Content
            ttk.Label(form_frame, text="Your Story:").pack(anchor='w', pady=(10, 5))
            self.story_content = ScrolledText(form_frame, height=12, wrap=tk.WORD)
            self.story_content.pack(fill=tk.BOTH, expand=True)

            # Placeholder text
            placeholder_text = """Tell us your story! Share your journey, achievements, challenges overcome, or how your education has impacted your life and career.

    Some ideas to get you started:
    • What has been your biggest accomplishment since graduation?
    • How has your education influenced your career path?
    • What advice would you give to current students or recent graduates?
    • Describe a project or initiative you're proud of
    • Share how you're making a difference in your community or industry

    Your story will inspire other alumni and current students!"""

            self.story_content.insert(tk.END, placeholder_text)

            # Submit button
            ttk.Button(form_frame, text="Submit Story",
                      command=self.submit_story).pack(pady=20)

        def moderate_photos(self):
            """Admin function to moderate uploaded photos"""
            if not self.has_permission('admin') and not self.has_permission('manage_alumni'):
                messagebox.showerror("Permission Denied",
                                   "You don't have permission to moderate photos.")
                return

            self.clear_content()
            self.update_status("Moderate Photos")

            ttk.Label(self.content_frame, text="Photo Moderation",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Filter frame
            filter_frame = ttk.Frame(self.content_frame)
            filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Label(filter_frame, text="Filter by Status:").pack(side=tk.LEFT, padx=(0, 10))
            self.photo_status_filter = tk.StringVar()
            status_combo = ttk.Combobox(filter_frame, textvariable=self.photo_status_filter,
                                       values=["All", "pending", "approved", "rejected"])
            status_combo.pack(side=tk.LEFT, padx=(0, 20))
            status_combo.set("pending")

            ttk.Button(filter_frame, text="Apply Filter",
                      command=self._load_photos_for_moderation).pack(side=tk.LEFT)

            # Photos table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Photo ID', 'Event', 'Uploader', 'Caption', 'Upload Date', 'Status')
            self.moderate_photos_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.moderate_photos_tree.heading(col, text=col)
                self.moderate_photos_tree.column(col, width=130)

            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.moderate_photos_tree.yview)
            self.moderate_photos_tree.configure(yscrollcommand=scrollbar_y.set)

            self.moderate_photos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load photos for moderation
            self._load_photos_for_moderation()

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="Approve",
                      command=lambda: self._moderate_photo_action('approved')).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Reject",
                      command=lambda: self._moderate_photo_action('rejected')).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Delete",
                      command=lambda: self._moderate_photo_action('deleted')).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self._load_photos_for_moderation).pack(side=tk.LEFT)

        def read_full_story(self):
            """View complete story details"""
            if not hasattr(self, 'stories_tree'):
                messagebox.showwarning("Not Available", "Please use 'View Alumni Stories' first.")
                return

            selection = self.stories_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a story to read.")
                return

            item = self.stories_tree.item(selection[0])
            story_data = item['values']

            # Create story window
            story_window = tk.Toplevel(self.root)
            story_window.title(f"{story_data[0]}")
            story_window.geometry("700x600")
            story_window.configure(bg='white')

            # Main frame
            main_frame = ttk.Frame(story_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Title
            ttk.Label(main_frame, text=story_data[0],
                     font=('Arial', 16, 'bold')).pack(pady=(0, 10))

            # Meta info
            meta_text = f"By {story_data[1]} | {story_data[2]} | Published: {story_data[3]} | Views: {story_data[4]}"
            ttk.Label(main_frame, text=meta_text,
                     font=('Arial', 9), foreground='gray').pack(pady=(0, 20))

            # Story content
            content_frame = ttk.Frame(main_frame)
            content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

            story_text = ScrolledText(content_frame, wrap=tk.WORD)
            story_text.pack(fill=tk.BOTH, expand=True)

            # Load story content from database
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT content FROM alumni_stories
                        WHERE title = ? AND author_name = ?
                    """, (story_data[0], story_data[1]))
                    result = cursor.fetchone()

                    if result:
                        story_text.insert(tk.END, result[0])

                        # Increment view count
                        cursor.execute("""
                            UPDATE alumni_stories
                            SET view_count = view_count + 1
                            WHERE title = ? AND author_name = ?
                        """, (story_data[0], story_data[1]))
                        conn.commit()
                    else:
                        story_text.insert(tk.END, "[Story content would be displayed here]")

            except sqlite3.Error:
                story_text.insert(tk.END, "[Story content would be displayed here]")

            story_text.config(state='disabled')

            # Close button
            ttk.Button(main_frame, text="Close",
                      command=story_window.destroy).pack()

        def show_create_story(self):
            """Show create alumni story interface"""
            self.clear_content()
            self.update_status("Create Alumni Story")

            ttk.Label(self.content_frame, text="Create Alumni Story",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Get current user's alumni ID
            alumni_id = None
            if hasattr(self.current_user, 'username') and self.current_user['username'].startswith('A'):
                alumni_id = self.current_user['username']
            elif self.has_permission('manage_social_features'):
                alumni_id_frame = ttk.Frame(self.content_frame)
                alumni_id_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

                ttk.Label(alumni_id_frame, text="Alumni ID:").pack(side=tk.LEFT, padx=(0, 10))
                self.story_alumni_id = tk.StringVar()
                ttk.Entry(alumni_id_frame, textvariable=self.story_alumni_id).pack(side=tk.LEFT)

            # Story form
            form_frame = ttk.Frame(self.content_frame)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            # Story type
            type_frame = ttk.Frame(form_frame)
            type_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(type_frame, text="Story Type:").pack(side=tk.LEFT, padx=(0, 10))
            self.story_type = tk.StringVar()
            type_combo = ttk.Combobox(type_frame, textvariable=self.story_type,
                                     values=["Career Achievement", "Community Service", "Entrepreneurship",
                                           "Research & Innovation", "Personal Journey", "Alumni Spotlight"])
            type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            type_combo.set("Career Achievement")

            # Title
            title_frame = ttk.Frame(form_frame)
            title_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(title_frame, text="Story Title:").pack(anchor='w')
            self.story_title = tk.StringVar()
            ttk.Entry(title_frame, textvariable=self.story_title).pack(fill=tk.X, pady=(5, 0))

            # Category
            category_frame = ttk.Frame(form_frame)
            category_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(category_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
            self.story_category = tk.StringVar()
            category_combo = ttk.Combobox(category_frame, textvariable=self.story_category,
                                         values=["Professional Success", "Community Impact", "Innovation",
                                               "Leadership", "Inspiration", "Education", "Technology", "Arts"])
            category_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            category_combo.set("Professional Success")

            # Content
            ttk.Label(form_frame, text="Story Content:").pack(anchor='w', pady=(10, 5))
            self.story_content = ScrolledText(form_frame, height=15, wrap=tk.WORD)
            self.story_content.pack(fill=tk.BOTH, expand=True)

            # Submit button
            ttk.Button(form_frame, text="Submit Story",
                      command=self.submit_alumni_story).pack(pady=20)

        def show_photo_gallery(self):
            """Show photo gallery interface"""
            self.clear_content()
            self.update_status("Photo Gallery")

            ttk.Label(self.content_frame, text="Alumni Photo Gallery",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Gallery tabs
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Browse photos tab
            browse_frame = ttk.Frame(notebook)
            notebook.add(browse_frame, text="Browse Photos")

            # Event filter
            filter_frame = ttk.Frame(browse_frame)
            filter_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(filter_frame, text="Filter by Event:").pack(side=tk.LEFT, padx=(0, 10))
            event_var = tk.StringVar()
            event_combo = ttk.Combobox(filter_frame, textvariable=event_var,
                                      values=["All Events", "Annual Gala 2025", "Tech Networking", "Class Reunions"])
            event_combo.pack(side=tk.LEFT)
            event_combo.set("All Events")

            # Photo listings
            photo_text = ScrolledText(browse_frame, wrap=tk.WORD)
            photo_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            photo_content = """Photo Gallery - Recent Uploads:

    📸 Annual Alumni Gala 2025
    Uploaded by: Sarah Johnson | Date: August 15, 2025
    Photos: 15 | Event Date: August 10, 2025
    Caption: "Amazing turnout at this year's gala! Great to see everyone."
    [View Album]

    📸 Tech Industry Networking Event
    Uploaded by: Michael Chen | Date: August 12, 2025
    Photos: 8 | Event Date: August 8, 2025
    Caption: "Productive networking session with tech alumni."
    [View Album]

    📸 Class of 2020 Reunion Planning
    Uploaded by: Emily Davis | Date: August 5, 2025
    Photos: 12 | Event Date: August 3, 2025
    Caption: "Planning committee hard at work for the upcoming reunion!"
    [View Album]

    📸 Regional Chapter Meetup - SF Bay Area
    Uploaded by: Alex Wong | Date: July 28, 2025
    Photos: 20 | Event Date: July 25, 2025
    Caption: "Great turnout for our monthly Bay Area chapter meeting."
    [View Album]
    """
            photo_text.insert(tk.END, photo_content)

            # Upload photos tab
            upload_frame = ttk.Frame(notebook)
            notebook.add(upload_frame, text="Upload Photos")

            self.create_photo_upload_form(upload_frame)

        def show_stories(self):
            """Show alumni stories interface"""
            self.clear_content()
            self.update_status("Alumni Stories")

            ttk.Label(self.content_frame, text="Alumni Stories & Spotlights",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Stories tabs
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Featured stories tab
            featured_frame = ttk.Frame(notebook)
            notebook.add(featured_frame, text="Featured Stories")

            featured_text = ScrolledText(featured_frame, wrap=tk.WORD)
            featured_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            stories_content = """Featured Alumni Stories:

    ⭐ "From Student to CEO: Sarah's Journey"
    By: Sarah Johnson (Class of 2015) | Category: Career Achievement
    Published: August 10, 2025 | Views: 245

    Sarah shares her inspiring journey from computer science student to founding her own tech startup. "The skills I learned at university gave me the foundation, but the alumni network provided the connections and mentorship that made it possible..."

    Read more →

    ---

    ⭐ "Making a Difference in Healthcare"
    By: Dr. Lisa Martinez (Class of 2012) | Category: Community Impact
    Published: August 5, 2025 | Views: 189

    Dr. Martinez talks about her work providing healthcare in underserved communities. "My education taught me medicine, but my experiences taught me compassion. Every day I'm grateful for the opportunity to serve..."

    Read more →

    ---

    ⭐ "Innovation in Renewable Energy"
    By: Michael Green (Class of 2017) | Category: Innovation
    Published: July 28, 2025 | Views: 156

    Michael discusses his breakthrough research in solar energy efficiency. "The research opportunities at university sparked my passion for renewable energy. Now I'm working to make clean energy accessible to everyone..."

    Read more →
    """
            featured_text.insert(tk.END, stories_content)

            # Submit story tab
            submit_frame = ttk.Frame(notebook)
            notebook.add(submit_frame, text="Submit Your Story")

            self.create_story_form(submit_frame)

        def submit_alumni_story(self):
            """Submit alumni story"""
            if not self.story_title.get().strip():
                messagebox.showerror("Validation Error", "Story title is required!")
                return

            content = self.story_content.get(1.0, tk.END).strip()
            if not content:
                messagebox.showerror("Validation Error", "Story content is required!")
                return

            messagebox.showinfo("Story Submitted", "Alumni story submitted successfully!")
            self.update_status("Alumni story submitted")

            # Clear form
            self.story_title.set("")
            self.story_category.set("Professional Success")
            self.story_type.set("Career Achievement")
            self.story_content.delete(1.0, tk.END)

        def submit_story(self):
            """Submit alumni story"""
            if not self.story_title.get().strip():
                messagebox.showerror("Validation Error", "Story title is required!")
                return

            content = self.story_content.get(1.0, tk.END).strip()
            if not content or content.startswith("Tell us your story"):
                messagebox.showerror("Validation Error", "Please write your story content!")
                return

            messagebox.showinfo("Story Submitted", "Your story has been submitted for review. Thank you for sharing!")
            self.update_status("Alumni story submitted")

            # Clear form
            self.story_title.set("")
            self.story_content.delete(1.0, tk.END)

        def upload_photos(self):
            """Upload photos"""
            if not self.photo_event.get():
                messagebox.showerror("Validation Error", "Please select an event!")
                return

            if not getattr(self, "_photo_file_paths", None):
                messagebox.showerror("Validation Error", "Please select photos to upload!")
                return

            event_name = self.photo_event.get()
            event_id = self._event_lookup.get(event_name)
            if not event_id:
                messagebox.showerror("Validation Error", "Selected event is not available.")
                return

            caption = self.photo_caption.get("1.0", tk.END).strip()
            uploader = self._current_user_id()
            upload_time = datetime.now().isoformat()

            stored_files = []
            skipped_files = []
            for index, source_path in enumerate(self._photo_file_paths, start=1):
                src = Path(source_path)
                if not src.exists():
                    continue

                # Security: Validate file before upload
                if SECURE_UPLOAD_AVAILABLE and validate_upload:
                    try:
                        with open(src, 'rb') as f:
                            file_content = f.read()
                        validation = validate_upload(src.name, file_content, category='images')
                        if not validation['valid']:
                            skipped_files.append(f"{src.name}: {validation['error']}")
                            if ACTIVITY_LOGGER_AVAILABLE:
                                log_activity(
                                    'security_blocked',
                                    'photo_upload',
                                    filename=src.name,
                                    reason=validation['error']
                                )
                            continue
                        safe_filename_str = validation.get('sanitized_filename', secure_filename(src.name))
                    except Exception as e:
                        skipped_files.append(f"{src.name}: Validation error - {str(e)}")
                        continue
                else:
                    safe_filename_str = secure_filename(src.name)

                destination = self._photo_storage_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{index}_{safe_filename_str}"
                shutil.copy2(src, destination)
                # Set restrictive permissions on uploaded file
                os.chmod(destination, 0o600)
                stored_files.append(destination)

            if skipped_files:
                messagebox.showwarning(
                    "Some Files Skipped",
                    "The following files were skipped due to security validation:\n" +
                    "\n".join(skipped_files[:5]) +
                    (f"\n... and {len(skipped_files) - 5} more" if len(skipped_files) > 5 else "")
                )

            if not stored_files:
                messagebox.showerror("Upload Failed", "Selected files could not be processed.")
                return

            conn = self._get_db_connection()
            cursor = conn.cursor()
            for filepath in stored_files:
                cursor.execute(
                    """
                    INSERT INTO photo_gallery (event_id, uploaded_by, photo_path, caption, upload_date)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (event_id, uploader, str(filepath), caption, upload_time)
                )
            conn.commit()
            conn.close()

            messagebox.showinfo("Upload Complete", "Photos uploaded successfully to the gallery!")
            self.update_status(f"Uploaded {len(stored_files)} photo(s) to gallery")
            self._photo_file_paths = []
            self.selected_files.set("No files selected")
            self.photo_caption.delete("1.0", tk.END)

        def view_alumni_stories(self):
            """List all alumni stories"""
            self.clear_content()
            self.update_status("Alumni Stories")

            ttk.Label(self.content_frame, text="Alumni Stories",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Filter frame
            filter_frame = ttk.Frame(self.content_frame)
            filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
            self.story_filter_category = tk.StringVar()
            category_combo = ttk.Combobox(filter_frame, textvariable=self.story_filter_category,
                                         values=["All", "Career Success", "Entrepreneurship", "Community Impact",
                                                "Academic Achievement", "Personal Journey"])
            category_combo.pack(side=tk.LEFT, padx=(0, 20))
            category_combo.set("All")

            ttk.Button(filter_frame, text="Filter",
                      command=self._load_alumni_stories).pack(side=tk.LEFT)

            # Stories table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Title', 'Author', 'Category', 'Published Date', 'Views')
            self.stories_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.stories_tree.heading(col, text=col)
                self.stories_tree.column(col, width=140)

            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.stories_tree.yview)
            self.stories_tree.configure(yscrollcommand=scrollbar_y.set)

            self.stories_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load stories
            self._load_alumni_stories()

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="Read Full Story",
                      command=self.read_full_story).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Submit Your Story",
                      command=self.show_create_story).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self._load_alumni_stories).pack(side=tk.LEFT)

        def view_event_photos(self):
            """View photos filtered by specific event"""
            self.clear_content()
            self.update_status("Event Photos")

            ttk.Label(self.content_frame, text="Event Photos",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Event selection frame
            event_frame = ttk.Frame(self.content_frame)
            event_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Label(event_frame, text="Select Event:").pack(side=tk.LEFT, padx=(0, 10))
            self.event_photo_filter = tk.StringVar()

            # Get event options
            event_options = []
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT event_id, title FROM unified_events ORDER BY start_datetime DESC")
                    events = cursor.fetchall()
                    event_options = [f"{event[1]} (ID: {event[0]})" for event in events]
            except sqlite3.Error:
                pass  # Silently handle database errors

            if not event_options:
                event_options = ["No events available"]

            event_combo = ttk.Combobox(event_frame, textvariable=self.event_photo_filter,
                                       values=event_options, width=40)
            event_combo.pack(side=tk.LEFT, padx=(0, 20))
            if event_options and event_options[0] != "No events available":
                event_combo.set(event_options[0])

            ttk.Button(event_frame, text="Load Photos",
                      command=self._load_event_photos).pack(side=tk.LEFT)

            # Photos table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Photo ID', 'Uploader', 'Caption', 'Upload Date', 'Status')
            self.event_photos_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.event_photos_tree.heading(col, text=col)
                self.event_photos_tree.column(col, width=150)

            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.event_photos_tree.yview)
            self.event_photos_tree.configure(yscrollcommand=scrollbar_y.set)

            self.event_photos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="Refresh",
                      command=self._load_event_photos).pack(side=tk.LEFT)

        def view_my_photos(self):
            """View photos uploaded by the current user"""
            self.clear_content()
            self.update_status("My Photos")

            ttk.Label(self.content_frame, text="My Uploaded Photos",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Photos table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Event', 'Photo Path', 'Caption', 'Upload Date', 'Status')
            self.my_photos_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.my_photos_tree.heading(col, text=col)
                self.my_photos_tree.column(col, width=150)

            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.my_photos_tree.yview)
            self.my_photos_tree.configure(yscrollcommand=scrollbar_y.set)

            self.my_photos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load user's photos
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    query = """
                        SELECT e.title, pg.photo_path, pg.caption,
                               pg.upload_date, pg.status
                        FROM photo_gallery pg
                        LEFT JOIN unified_events e ON pg.event_id = e.event_id
                        WHERE pg.uploaded_by = ?
                        ORDER BY pg.upload_date DESC
                    """
                    cursor.execute(query, (user_id,))
                    photos = cursor.fetchall()

                    for photo in photos:
                        # Shorten photo path for display
                        display_photo = list(photo)
                        if display_photo[1]:
                            display_photo[1] = Path(display_photo[1]).name
                        self.my_photos_tree.insert('', tk.END, values=display_photo)

                    self.update_status(f"Loaded {len(photos)} photo(s)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load photos: {str(e)}")

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="Delete Photo",
                      command=self._delete_my_photo).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self.view_my_photos).pack(side=tk.LEFT)

