from ._common import datetime, messagebox, scrolledtext, tk, ttk
from education_system.post_18.university_system.infrastructure.email.announcements import (
    get_announcement_by_id,
    mark_announcement_viewed,
)

class AnnouncementDetailsDialog:
    def __init__(self, parent, dashboard, announcement_id):
        self.dashboard = dashboard
        self.announcement_id = announcement_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Announcement Details")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        self.load_announcement()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        self.title_label = ttk.Label(main_frame, text="", font=('Arial', 14, 'bold'))
        self.title_label.pack(anchor=tk.W, pady=(0, 10))

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Announcement Details", padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 10))

        self.details_text = tk.Text(details_frame, height=3, wrap=tk.WORD, state=tk.DISABLED)
        self.details_text.pack(fill=tk.X)

        # Content
        content_frame = ttk.LabelFrame(main_frame, text="Content", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True)

        self.content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.content_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_announcement(self):
        try:
            announcement = get_announcement_by_id(self.dashboard, self.announcement_id)
            if announcement:
                self.title_label.config(text=announcement['title'])

                details = f"Created by: {announcement['creator']}\n"
                details += f"Target: {announcement['target_audience']}\n"
                details += f"Created: {announcement['created_at']}\n"
                details += f"Priority: {'URGENT' if announcement['is_urgent'] else 'Normal'}\n"
                details += f"Status: {'Active' if announcement['is_active'] else 'Inactive'}"

                self.details_text.config(state=tk.NORMAL)
                self.details_text.insert(1.0, details)
                self.details_text.config(state=tk.DISABLED)

                self.content_text.config(state=tk.NORMAL)
                self.content_text.insert(1.0, announcement['content'])
                self.content_text.config(state=tk.DISABLED)

                # Mark as viewed
                mark_announcement_viewed(self.dashboard, self.announcement_id)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading announcement: {e}")


class CreateAnnouncementDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Announcement")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=60)
        self.title_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5)

        # Target audience
        ttk.Label(main_frame, text="Target Audience:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.audience_var = tk.StringVar(value="all")
        audience_frame = ttk.Frame(main_frame)
        audience_frame.grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Radiobutton(audience_frame, text="All Users", variable=self.audience_var, value="all").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Students", variable=self.audience_var, value="students").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(audience_frame, text="Staff", variable=self.audience_var, value="staff").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Instructors", variable=self.audience_var, value="instructors").pack(side=tk.LEFT, padx=10)

        # Urgent checkbox
        self.urgent_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Mark as urgent", variable=self.urgent_var).grid(row=2, column=1, sticky=tk.W, pady=5)

        # Content
        ttk.Label(main_frame, text="Content:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.content_text = scrolledtext.ScrolledText(main_frame, width=60, height=15)
        self.content_text.grid(row=3, column=1, columnspan=2, sticky=tk.NSEW, pady=5)

        # Date options
        ttk.Label(main_frame, text="Start Date:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.start_date_entry = ttk.Entry(main_frame, width=20)
        self.start_date_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
        self.start_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        ttk.Label(main_frame, text="End Date (optional):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.end_date_entry = ttk.Entry(main_frame, width=20)
        self.end_date_entry.grid(row=5, column=1, sticky=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=20)

        ttk.Button(button_frame, text="Create", command=self.create_announcement).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def create_announcement(self):
        title = self.title_entry.get().strip()
        content = self.content_text.get(1.0, tk.END).strip()
        target_audience = self.audience_var.get()
        is_urgent = 1 if self.urgent_var.get() else 0
        start_date = self.start_date_entry.get().strip()
        end_date = self.end_date_entry.get().strip() or None

        if not title or not content:
            messagebox.showwarning("Missing Information", "Title and content are required")
            return

        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized")
            return

        try:
            result = self.dashboard.create_announcement(
                title,
                content,
                target_audience,
                is_urgent=is_urgent,
                start_date=start_date or None,
                end_date=end_date,
            )
            if result:
                messagebox.showinfo("Success", "Announcement created successfully!")
                self.dialog.destroy()
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to create announcement (check permissions and date format YYYY-MM-DD HH:MM:SS)",
                )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create announcement: {e}")


class EditAnnouncementDialog:
    def __init__(self, parent, dashboard, announcement_id, refresh_callback):
        self.dashboard = dashboard
        self.announcement_id = announcement_id
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Announcement")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.load_announcement()

    def load_announcement(self):
        """Load existing announcement data"""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT title, content, is_urgent
                FROM announcements WHERE id = ?
            ''', (self.announcement_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                self.title = row[0]
                self.content = row[1]
                self.is_urgent = row[2]
                self.create_widgets()
            else:
                messagebox.showerror("Error", "Announcement not found")
                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load announcement: {e}")
            self.dialog.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Edit Announcement", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Title
        ttk.Label(main_frame, text="Title:").pack(anchor=tk.W)
        self.title_entry = ttk.Entry(main_frame, width=50)
        self.title_entry.insert(0, self.title)
        self.title_entry.pack(fill=tk.X, pady=(0, 10))

        # Message
        ttk.Label(main_frame, text="Message:").pack(anchor=tk.W)
        self.message_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.message_text.insert(1.0, self.content)
        self.message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Priority
        priority_frame = ttk.Frame(main_frame)
        priority_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(priority_frame, text="Priority:").pack(side=tk.LEFT, padx=(0, 5))

        # Map is_urgent to priority string
        initial_priority = "high" if self.is_urgent else "normal"
        self.priority_var = tk.StringVar(value=initial_priority)

        ttk.Radiobutton(priority_frame, text="Low", variable=self.priority_var, value="low").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(priority_frame, text="Normal", variable=self.priority_var, value="normal").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(priority_frame, text="High", variable=self.priority_var, value="high").pack(side=tk.LEFT, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Save", command=self.save_announcement).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def save_announcement(self):
        title = self.title_entry.get().strip()
        message = self.message_text.get(1.0, tk.END).strip()
        priority = self.priority_var.get()

        if not title or not message:
            messagebox.showwarning("Missing Information", "Please provide both title and message")
            return

        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_db_connection
            from datetime import datetime

            conn = get_db_connection()
            cursor = conn.cursor()

            # Map priority to is_urgent
            is_urgent = 1 if priority.lower() == 'high' else 0

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Update the announcement
            cursor.execute('''
                UPDATE announcements
                SET title = ?, content = ?, is_urgent = ?, updated_at = ?
                WHERE id = ?
            ''', (title, message, is_urgent, current_time, self.announcement_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Announcement updated successfully!")
            self.dialog.destroy()

            # Refresh the announcements list
            if self.refresh_callback:
                self.refresh_callback()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update announcement: {e}")

