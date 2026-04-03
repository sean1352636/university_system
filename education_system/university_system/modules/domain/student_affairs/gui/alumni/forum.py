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



class ForumMixin:
        def _load_forum_posts(self):
            """Load forum posts from database"""
            try:
                # Clear existing data
                for item in self.forum_posts_tree.get_children():
                    self.forum_posts_tree.delete(item)

                with db_get_connection() as conn:
                    cursor = conn.cursor()

                    # Build query
                    query = """
                        SELECT post_id, title, author_name, category, reply_count,
                               view_count, last_activity_date
                        FROM forum_posts
                        WHERE 1=1
                    """
                    params = []

                    # Add category filter
                    category = self.forum_filter_category.get()
                    if category != "All":
                        query += " AND category = ?"
                        params.append(category)

                    # Add sorting
                    sort_by = self.forum_sort_by.get()
                    if sort_by == "Most Recent":
                        query += " ORDER BY last_activity_date DESC"
                    elif sort_by == "Most Replies":
                        query += " ORDER BY reply_count DESC"
                    elif sort_by == "Most Views":
                        query += " ORDER BY view_count DESC"
                    elif sort_by == "Oldest First":
                        query += " ORDER BY created_date ASC"

                    cursor.execute(query, params)
                    posts = cursor.fetchall()

                    for post in posts:
                        # Display without post_id
                        self.forum_posts_tree.insert('', tk.END, values=post[1:])

                    self.update_status(f"Loaded {len(posts)} forum post(s)")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load forum posts: {str(e)}")

        def _show_reply_dialog(self, post_title, parent_window):
            """Show dialog to add a reply to a forum post"""
            reply_window = tk.Toplevel(parent_window)
            reply_window.title(f"Reply to: {post_title}")
            reply_window.geometry("500x350")
            reply_window.configure(bg='white')
            reply_window.grab_set()

            frame = ttk.Frame(reply_window, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=f"Reply to: {post_title}",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            ttk.Label(frame, text="Your Reply:").pack(anchor='w')
            reply_text = ScrolledText(frame, wrap=tk.WORD, height=10)
            reply_text.pack(fill=tk.BOTH, expand=True, pady=(5, 20))

            def submit_reply():
                reply_content = reply_text.get(1.0, tk.END).strip()
                if not reply_content:
                    messagebox.showerror("Validation Error", "Reply cannot be empty!")
                    return

                try:
                    self.add_forum_reply(post_title, reply_content)
                    messagebox.showinfo("Success", "Reply posted successfully!")
                    reply_window.destroy()
                    parent_window.destroy()  # Close parent detail window
                    self.view_forum_posts()  # Refresh forum view
                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Failed to post reply: {str(e)}")

            ttk.Button(frame, text="Post Reply",
                      command=submit_reply).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(frame, text="Cancel",
                      command=reply_window.destroy).pack(side=tk.LEFT)

        def add_forum_reply(self, post_title, reply_content):
            """Add a reply to a forum post"""
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    # Get post_id
                    cursor.execute("SELECT post_id FROM forum_posts WHERE title = ?", (post_title,))
                    result = cursor.fetchone()

                    if not result:
                        raise ValueError("Forum post not found")

                    post_id = result[0]

                    # Insert reply
                    cursor.execute("""
                        INSERT INTO forum_replies (post_id, author_id, author_name, content, created_date)
                        VALUES (?, ?, ?, ?, datetime('now'))
                    """, (post_id, user_id, self.current_user.get('username', 'Anonymous'), reply_content))

                    # Update post reply count and last activity
                    cursor.execute("""
                        UPDATE forum_posts
                        SET reply_count = reply_count + 1,
                            last_activity_date = datetime('now')
                        WHERE post_id = ?
                    """, (post_id,))

                    conn.commit()
                    self.update_status("Forum reply posted successfully")

                    # Log activity
                    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
                    log_activity('create', 'forum_reply', reply_id=cursor.lastrowid,
                               details={'post_id': post_id, 'post_title': post_title})

            except sqlite3.Error as e:
                raise sqlite3.Error(f"Failed to add forum reply: {str(e)}")

        def create_forum_post_form(self, parent):
            """Create the forum post form"""
            ttk.Label(parent, text="Create New Forum Post",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            # Category
            cat_frame = ttk.Frame(form_frame)
            cat_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(cat_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
            self.post_category = tk.StringVar()
            cat_combo = ttk.Combobox(cat_frame, textvariable=self.post_category,
                                    values=["General Discussion", "Career Advice", "Networking",
                                           "Industry News", "Class Updates", "Events", "Mentorship"])
            cat_combo.pack(side=tk.LEFT)
            cat_combo.set("General Discussion")

            # Title
            title_frame = ttk.Frame(form_frame)
            title_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(title_frame, text="Post Title:").pack(anchor='w')
            self.post_title = tk.StringVar()
            ttk.Entry(title_frame, textvariable=self.post_title).pack(fill=tk.X, pady=(5, 0))

            # Content
            ttk.Label(form_frame, text="Post Content:").pack(anchor='w', pady=(10, 5))
            self.post_content = ScrolledText(form_frame, height=10, wrap=tk.WORD)
            self.post_content.pack(fill=tk.BOTH, expand=True)

            # Submit button
            ttk.Button(form_frame, text="Post to Forum",
                      command=self.submit_forum_post).pack(pady=20)

        def preview_newsletter(self):
            """Preview the newsletter"""
            preview_window = tk.Toplevel(self.root)
            preview_window.title(f"Newsletter Preview - {self.newsletter_title.get()}")
            preview_window.geometry("600x500")

            preview_text = ScrolledText(preview_window, wrap=tk.WORD, padx=10, pady=10)
            preview_text.pack(fill=tk.BOTH, expand=True)

            preview_content = f"Title: {self.newsletter_title.get()}\n"
            preview_content += f"Audience: {self.newsletter_audience.get()}\n"
            preview_content += f"Send Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            preview_content += "=" * 50 + "\n\n"
            preview_content += self.newsletter_content.get(1.0, tk.END)

            preview_text.insert(tk.END, preview_content)
            preview_text.config(state=tk.DISABLED)

        def save_newsletter_draft(self):
            """Save newsletter as draft"""
            messagebox.showinfo("Draft Saved", "Newsletter saved as draft successfully!")
            self.update_status("Newsletter draft saved")

        def send_newsletter(self):
            """Send the newsletter"""
            if not self.newsletter_title.get().strip():
                messagebox.showerror("Validation Error", "Newsletter title is required!")
                return

            if not self.newsletter_content.get(1.0, tk.END).strip():
                messagebox.showerror("Validation Error", "Newsletter content is required!")
                return

            # Confirmation dialog
            if messagebox.askyesno("Confirm Send",
                                  f"Send newsletter '{self.newsletter_title.get()}' to {self.newsletter_audience.get()}?"):
                messagebox.showinfo("Newsletter Sent", "Newsletter has been sent successfully!")
                self.update_status("Newsletter sent to recipients")

        def show_create_newsletter(self):
            """Show newsletter creation interface"""
            self.clear_content()
            self.update_status("Newsletter Creation")

            ttk.Label(self.content_frame, text="Create Alumni Newsletter",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Newsletter form
            form_frame = ttk.LabelFrame(self.content_frame, text="Newsletter Details", padding=10)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Title
            title_frame = ttk.Frame(form_frame)
            title_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(title_frame, text="Newsletter Title:").pack(side=tk.LEFT, padx=(0, 10))
            self.newsletter_title = tk.StringVar()
            ttk.Entry(title_frame, textvariable=self.newsletter_title).pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Target audience
            audience_frame = ttk.Frame(form_frame)
            audience_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(audience_frame, text="Target Audience:").pack(side=tk.LEFT, padx=(0, 10))
            self.newsletter_audience = tk.StringVar()
            audience_combo = ttk.Combobox(audience_frame, textvariable=self.newsletter_audience,
                                         values=["All Alumni", "By Graduation Year", "By Industry", "Donors Only", "Mentors Only"])
            audience_combo.pack(side=tk.LEFT, padx=(0, 10))
            audience_combo.set("All Alumni")

            # Content
            ttk.Label(form_frame, text="Newsletter Content:").pack(anchor='w', pady=(10, 5))
            self.newsletter_content = ScrolledText(form_frame, height=15, wrap=tk.WORD)
            self.newsletter_content.pack(fill=tk.BOTH, expand=True)

            # Sample content
            sample_content = """Subject: Alumni Newsletter - August 2025

    Dear Alumni,

    We hope this newsletter finds you well! Here are the latest updates from our alumni community:

    🎓 ALUMNI SPOTLIGHT
    This month we feature Sarah Johnson (Class of 2015), who recently launched her tech startup...

    📅 UPCOMING EVENTS
    • Annual Alumni Gala - September 15, 2025
    • Tech Industry Networking - August 25, 2025
    • Class of 2020 Reunion - October 10, 2025

    💼 CAREER OPPORTUNITIES
    New job postings from our alumni network:
    • Senior Developer at Tech Corp
    • Financial Analyst at Finance Plus
    • Marketing Manager at StartupCo

    🤝 MENTORSHIP PROGRAM
    Join our expanding mentorship program! We currently have 50+ active mentor-mentee pairs...

    💝 GIVING BACK
    Thank you to our recent donors who contributed to the Annual Alumni Fund...

    Best regards,
    Alumni Relations Team
    """
            self.newsletter_content.insert(tk.END, sample_content)

            # Buttons
            button_frame = ttk.Frame(form_frame)
            button_frame.pack(fill=tk.X, pady=10)

            ttk.Button(button_frame, text="Send Newsletter",
                      command=self.send_newsletter).pack(side=tk.RIGHT, padx=(10, 0))
            ttk.Button(button_frame, text="Save as Draft",
                      command=self.save_newsletter_draft).pack(side=tk.RIGHT)
            ttk.Button(button_frame, text="Preview",
                      command=self.preview_newsletter).pack(side=tk.RIGHT, padx=(0, 10))

        def show_forum(self):
            """Show alumni forum interface"""
            self.clear_content()
            self.update_status("Alumni Forum")

            ttk.Label(self.content_frame, text="Alumni Forum",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Forum tabs
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Recent posts tab
            posts_frame = ttk.Frame(notebook)
            notebook.add(posts_frame, text="Recent Posts")

            posts_text = ScrolledText(posts_frame, wrap=tk.WORD)
            posts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            forum_content = """Recent Forum Posts:

    💼 Career Advice | Posted by: Sarah Johnson | 2 hours ago
    "Transitioning from Academia to Industry - Tips and Experiences"
    Looking for advice on making the switch from research to industry roles...
    📝 5 replies | 👁 23 views

    🤝 Networking | Posted by: Michael Chen | 5 hours ago
    "NYC Alumni Meetup - August 25th"
    Organizing an informal meetup for NYC-based alumni. Who's interested?
    📝 12 replies | 👁 45 views

    🎓 Class Updates | Posted by: Emily Davis | 1 day ago
    "Class of 2020 - Where are we now?"
    Let's catch up! Share what you've been up to since graduation...
    📝 18 replies | 👁 67 views

    💡 Industry News | Posted by: John Smith | 2 days ago
    "The Future of Remote Work - Alumni Perspectives"
    How has remote work affected your career? Share your thoughts...
    📝 8 replies | 👁 34 views
    """
            posts_text.insert(tk.END, forum_content)

            # Create post tab
            create_frame = ttk.Frame(notebook)
            notebook.add(create_frame, text="Create Post")

            self.create_forum_post_form(create_frame)

        def show_moderate_forum_posts(self):
            """Show forum moderation interface"""
            if not self.has_permission('moderate_forum'):
                messagebox.showerror("Access Denied", "You don't have permission to moderate forum posts.")
                return

            moderate_window = tk.Toplevel(self.root)
            moderate_window.title("Moderate Forum Posts")
            moderate_window.geometry("700x500")

            ttk.Label(moderate_window, text="Forum Moderation",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            # Tabs for different moderation views
            notebook = ttk.Notebook(moderate_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Pending posts
            pending_frame = ttk.Frame(notebook)
            notebook.add(pending_frame, text="Pending Posts")

            pending_text = ScrolledText(pending_frame, wrap=tk.WORD)
            pending_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            pending_content = """Posts Pending Moderation:

        ⏳ "New Job Opportunity at My Company"
        Author: John Smith | Category: Job Opportunities
        Posted: 2025-08-19 14:30
        Content: Looking for talented alumni to join our growing team...
        [Approve] [Reject] [Edit]

        ⏳ "Question About Alumni Benefits"
        Author: Sarah Wilson | Category: General Discussion
        Posted: 2025-08-19 11:15
        Content: Can someone clarify what benefits are included...
        [Approve] [Reject] [Edit]
        """

            pending_text.insert(tk.END, pending_content)

            # Reported posts
            reported_frame = ttk.Frame(notebook)
            notebook.add(reported_frame, text="Reported Posts")

            reported_text = ScrolledText(reported_frame, wrap=tk.WORD)
            reported_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            reported_content = """Reported Posts:

        🚩 "Controversial Industry Opinion"
        Author: Anonymous | Reported by: 3 users
        Reason: Inappropriate content
        Action Required: Review and decide
        [View Post] [Remove] [Keep] [Warn Author]

        No other reported posts at this time.
        """

            reported_text.insert(tk.END, reported_content)

        def show_my_forum_posts(self):
            """Show current user's forum posts"""
            posts_window = tk.Toplevel(self.root)
            posts_window.title("My Forum Posts")
            posts_window.geometry("600x400")

            ttk.Label(posts_window, text="My Forum Posts",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            posts_text = ScrolledText(posts_window, wrap=tk.WORD)
            posts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            my_posts_content = """Your Forum Posts:

        📝 "Career Transition Tips" | Posted: 2025-08-15
        Category: Career Advice | Replies: 12 | Views: 156
        Looking for advice on switching from tech to consulting...

        📝 "Alumni Networking Event Ideas" | Posted: 2025-08-10
        Category: Networking | Replies: 8 | Views: 89
        What are some creative ideas for regional chapter events?

        📝 "Startup Funding Experience" | Posted: 2025-08-05
        Category: General Discussion | Replies: 23 | Views: 234
        Sharing my journey securing seed funding for my startup...

        Total Posts: 3
        Total Replies Received: 43
        Total Views: 479
        """

            posts_text.insert(tk.END, my_posts_content)

        def show_search_forum_posts(self):
            """Show forum post search interface"""
            search_window = tk.Toplevel(self.root)
            search_window.title("Search Forum Posts")
            search_window.geometry("400x300")

            ttk.Label(search_window, text="Search Forum Posts",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            # Search criteria
            search_frame = ttk.Frame(search_window)
            search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Label(search_frame, text="Search Term:").pack(anchor='w')
            search_term = tk.StringVar()
            ttk.Entry(search_frame, textvariable=search_term).pack(fill=tk.X, pady=(5, 10))

            ttk.Label(search_frame, text="Category:").pack(anchor='w')
            category_var = tk.StringVar()
            category_combo = ttk.Combobox(search_frame, textvariable=category_var,
                                         values=["All", "General Discussion", "Career Advice", "Networking"])
            category_combo.pack(fill=tk.X, pady=(5, 0))
            category_combo.set("All")

            def perform_search():
                if search_term.get():
                    messagebox.showinfo("Search Results", f"Searching for '{search_term.get()}' in {category_var.get()}")
                search_window.destroy()

            ttk.Button(search_window, text="Search", command=perform_search).pack(pady=20)

        def submit_forum_post(self):
            """Submit forum post"""
            if not self.post_title.get().strip():
                messagebox.showerror("Validation Error", "Post title is required!")
                return

            if not self.post_content.get(1.0, tk.END).strip():
                messagebox.showerror("Validation Error", "Post content is required!")
                return

            messagebox.showinfo("Post Created", "Forum post created successfully!")
            self.update_status("Forum post submitted")

            # Clear form
            self.post_title.set("")
            self.post_content.delete(1.0, tk.END)

        def view_forum_post_details(self):
            """View details for a selected forum post"""
            if not hasattr(self, 'forum_posts_tree'):
                messagebox.showwarning("Not Available", "Please use the 'View Forum Posts' feature first.")
                return

            selection = self.forum_posts_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a forum post to view.")
                return

            item = self.forum_posts_tree.item(selection[0])
            post_data = item['values']

            # Create detail window
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"Forum Post - {post_data[0]}")
            detail_window.geometry("700x600")
            detail_window.configure(bg='white')

            # Main frame with scrollbar
            main_frame = ttk.Frame(detail_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Post header
            header_frame = ttk.Frame(main_frame)
            header_frame.pack(fill=tk.X, pady=(0, 20))

            ttk.Label(header_frame, text=post_data[0],
                     font=('Arial', 16, 'bold')).pack(anchor='w')

            meta_text = f"Author: {post_data[1]} | Category: {post_data[2]} | Replies: {post_data[3]} | Views: {post_data[4]}"
            ttk.Label(header_frame, text=meta_text,
                     font=('Arial', 9), foreground='gray').pack(anchor='w', pady=(5, 0))

            # Post content
            content_frame = ttk.LabelFrame(main_frame, text="Post Content", padding=10)
            content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

            content_text = ScrolledText(content_frame, wrap=tk.WORD, height=10)
            content_text.pack(fill=tk.BOTH, expand=True)

            # Try to load actual content from database
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT content FROM forum_posts WHERE title = ?", (post_data[0],))
                    result = cursor.fetchone()
                    if result:
                        content_text.insert(tk.END, result[0])
                    else:
                        content_text.insert(tk.END, "[Post content would be displayed here]")
            except sqlite3.Error:
                content_text.insert(tk.END, "[Post content would be displayed here]")

            content_text.config(state='disabled')

            # Replies section
            replies_frame = ttk.LabelFrame(main_frame, text="Replies", padding=10)
            replies_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            replies_text = ScrolledText(replies_frame, wrap=tk.WORD, height=8)
            replies_text.pack(fill=tk.BOTH, expand=True)
            replies_text.insert(tk.END, "[Replies would be displayed here]")
            replies_text.config(state='disabled')

            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)

            ttk.Button(button_frame, text="Add Reply",
                      command=lambda: self._show_reply_dialog(post_data[0], detail_window)).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Close",
                      command=detail_window.destroy).pack(side=tk.LEFT)

        def view_forum_posts(self):
            """View all forum posts with filtering options"""
            self.clear_content()
            self.update_status("Forum Posts")

            ttk.Label(self.content_frame, text="Forum Posts",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Filter frame
            filter_frame = ttk.Frame(self.content_frame)
            filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 10))
            self.forum_filter_category = tk.StringVar()
            category_combo = ttk.Combobox(filter_frame, textvariable=self.forum_filter_category,
                                         values=["All", "General Discussion", "Career Advice", "Networking",
                                                "Industry News", "Class Updates", "Events", "Mentorship"])
            category_combo.pack(side=tk.LEFT, padx=(0, 20))
            category_combo.set("All")

            ttk.Label(filter_frame, text="Sort by:").pack(side=tk.LEFT, padx=(0, 10))
            self.forum_sort_by = tk.StringVar()
            sort_combo = ttk.Combobox(filter_frame, textvariable=self.forum_sort_by,
                                     values=["Most Recent", "Most Replies", "Most Views", "Oldest First"])
            sort_combo.pack(side=tk.LEFT, padx=(0, 20))
            sort_combo.set("Most Recent")

            ttk.Button(filter_frame, text="Apply Filter",
                      command=self._load_forum_posts).pack(side=tk.LEFT)

            # Posts table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Title', 'Author', 'Category', 'Replies', 'Views', 'Last Activity')
            self.forum_posts_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                self.forum_posts_tree.heading(col, text=col)
                self.forum_posts_tree.column(col, width=130)

            # Scrollbars
            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                        command=self.forum_posts_tree.yview)
            self.forum_posts_tree.configure(yscrollcommand=scrollbar_y.set)

            self.forum_posts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load posts
            self._load_forum_posts()

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text="View Post",
                      command=self.view_forum_post_details).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Create New Post",
                      command=self.show_forum).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self._load_forum_posts).pack(side=tk.LEFT)

