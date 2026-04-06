"""File preview and calendar functionality"""

from education_system.university_system.core.sql_safety import escape_like
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.constants import paths
from collections import deque



class FilePreviewManager:
    """File preview and calendar functionality"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def show_calendar(self):
        """Show assignment calendar"""
        self.gui.layout.clear_content_area()

        # Header with title and button
        header_frame = ttk.Frame(self.gui.layout.content_area)
        header_frame.pack(fill='x', pady=(0, 20))

        title = ttk.Label(header_frame, text="Assignment Calendar", style='Title.TLabel')
        title.pack(side='left')

        # Button to launch full academic calendar
        ttk.Button(header_frame, text="📅 Open Full Academic Calendar",
                  command=self.launch_academic_calendar,
                  style='Accent.TButton').pack(side='right')

        # Calendar frame
        calendar_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Upcoming Assignments", padding=10)
        calendar_frame.pack(fill='both', expand=True)

        # Calendar tree view
        calendar_tree = ttk.Treeview(calendar_frame, columns=('Date', 'Time', 'Assignment', 'Module', 'Status'), show='headings')

        for col in ['Date', 'Time', 'Assignment', 'Module', 'Status']:
            calendar_tree.heading(col, text=col)
            calendar_tree.column(col, width=120)

        calendar_tree.pack(fill='both', expand=True)

        # Load calendar data
        try:
            student_id = self.assignment_system._get_student_id()
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            if student_id:
                # Student view
                cursor.execute('''
                SELECT a.due_date, a.title, a.module_code,
                       CASE
                           WHEN s.id IS NOT NULL THEN 'Submitted'
                           WHEN a.due_date < datetime('now') THEN 'Overdue'
                           ELSE 'Pending'
                       END as status
                FROM assignments a
                JOIN student_modules sm ON a.module_code = sm.module_code
                LEFT JOIN assignment_submissions s ON a.id = s.assignment_id AND s.student_id = ?
                WHERE sm.student_id = ? AND a.is_active = 1
                AND a.due_date >= date('now', '-7 days')
                ORDER BY a.due_date
                ''', (student_id, student_id))
            else:
                # Instructor view
                cursor.execute('''
                SELECT due_date, title, module_code, 'Active' as status
                FROM assignments
                WHERE is_active = 1 AND due_date >= date('now', '-7 days')
                ORDER BY due_date
                ''')

            assignments = cursor.fetchall()

            for assignment in assignments:
                due_datetime = datetime.strptime(assignment[0], '%Y-%m-%d %H:%M:%S')
                date_str = due_datetime.strftime('%Y-%m-%d')
                time_str = due_datetime.strftime('%H:%M')

                # Color code based on status
                tags = []
                if len(assignment) > 3:
                    if assignment[3] == 'Overdue':
                        tags = ['overdue']
                    elif assignment[3] == 'Submitted':
                        tags = ['submitted']

                calendar_tree.insert('', 'end',
                                   values=(date_str, time_str, assignment[1], assignment[2],
                                          assignment[3] if len(assignment) > 3 else 'Active'),
                                   tags=tags)

            # Configure tags
            calendar_tree.tag_configure('overdue', background='#ffebee')
            calendar_tree.tag_configure('submitted', background='#e8f5e8')

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load calendar: {e}")


    def prev_month(self):
        """Navigate to previous month"""
        if self.current_month.month == 1:
            self.current_month = self.current_month.replace(year=self.current_month.year - 1, month=12)
        else:
            self.current_month = self.current_month.replace(month=self.current_month.month - 1)
        self.update_calendar()


    def next_month(self):
        """Navigate to next month"""
        if self.current_month.month == 12:
            self.current_month = self.current_month.replace(year=self.current_month.year + 1, month=1)
        else:
            self.current_month = self.current_month.replace(month=self.current_month.month + 1)
        self.update_calendar()


    def create_calendar_grid(self):
        """Create the calendar grid"""
        # Clear existing calendar
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # Calendar header
        header_frame = ttk.Frame(self.calendar_frame)
        header_frame.pack(fill='x', pady=(0, 10))

        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for i, day in enumerate(days):
            ttk.Label(header_frame, text=day, font=('Arial', 10, 'bold'),
                     background='lightgray').grid(row=0, column=i, sticky='ew', padx=1, pady=1)
            header_frame.grid_columnconfigure(i, weight=1)

        # Calendar body
        self.calendar_body = ttk.Frame(self.calendar_frame)
        self.calendar_body.pack(fill='both', expand=True)

        # Create 6x7 grid for calendar days
        self.day_frames = {}
        for week in range(6):
            for day in range(7):
                day_frame = ttk.Frame(self.calendar_body, relief='ridge', borderwidth=1)
                day_frame.grid(row=week, column=day, sticky='nsew', padx=1, pady=1)
                self.calendar_body.grid_rowconfigure(week, weight=1)
                self.calendar_body.grid_columnconfigure(day, weight=1)
                self.day_frames[(week, day)] = day_frame


    def update_calendar(self):
        """Update calendar with current month data"""
        # Update month label
        month_name = self.current_month.strftime('%B %Y')
        self.month_label.config(text=month_name)

        # Clear existing content
        for frame in self.day_frames.values():
            for widget in frame.winfo_children():
                widget.destroy()

        # Get calendar data
        calendar_data = self.get_calendar_data()

        # Calculate first day of month and number of days
        import calendar
        month_calendar = calendar.monthcalendar(self.current_month.year, self.current_month.month)

        # Fill calendar grid
        for week_num, week in enumerate(month_calendar):
            for day_num, day in enumerate(week):
                if day == 0:  # Empty cell
                    continue

                frame = self.day_frames[(week_num, day_num)]

                # Day number
                day_label = ttk.Label(frame, text=str(day), font=('Arial', 12, 'bold'))
                day_label.pack(anchor='nw')

                # Add assignments for this day
                date_key = f"{self.current_month.year}-{self.current_month.month:02d}-{day:02d}"
                if date_key in calendar_data:
                    assignments = calendar_data[date_key]

                    for assignment in assignments[:3]:  # Show max 3 assignments
                        title_text = assignment['title'][:15] + "..." if len(assignment['title']) > 15 else assignment['title']

                        # Color code by status
                        if assignment['status'] == 'overdue':
                            bg_color = '#ffcdd2'
                        elif assignment['status'] == 'submitted':
                            bg_color = '#c8e6c9'
                        else:
                            bg_color = '#fff3e0'

                        assignment_label = tk.Label(frame, text=title_text,
                                                   font=('Arial', 8), background=bg_color,
                                                   wraplength=80)
                        assignment_label.pack(fill='x', pady=1)

                    if len(assignments) > 3:
                        more_label = tk.Label(frame, text=f"+{len(assignments) - 3} more",
                                            font=('Arial', 7), foreground='gray')
                        more_label.pack()


    def get_calendar_data(self):
        """Get assignment data for calendar display"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Calculate month range
            start_date = self.current_month.strftime('%Y-%m-01')
            if self.current_month.month == 12:
                end_date = self.current_month.replace(year=self.current_month.year + 1, month=1).strftime('%Y-%m-01')
            else:
                end_date = self.current_month.replace(month=self.current_month.month + 1).strftime('%Y-%m-01')

            if self.calendar_view_var.get() == "my_assignments":
                student_id = self.assignment_system._get_student_id()
                if student_id:
                    cursor.execute('''
                    SELECT a.title, a.due_date, a.module_code,
                           CASE
                               WHEN s.id IS NOT NULL THEN 'submitted'
                               WHEN a.due_date < datetime('now') THEN 'overdue'
                               ELSE 'pending'
                           END as status
                    FROM assignments a
                    JOIN student_modules sm ON a.module_code = sm.module_code
                    LEFT JOIN assignment_submissions s ON a.id = s.assignment_id AND s.student_id = ?
                    WHERE sm.student_id = ? AND a.is_active = 1
                    AND date(a.due_date) >= ? AND date(a.due_date) < ?
                    ORDER BY a.due_date
                    ''', (student_id, student_id, start_date, end_date))
                else:
                    return {}
            else:
                cursor.execute('''
                SELECT title, due_date, module_code, 'active' as status
                FROM assignments
                WHERE is_active = 1
                AND date(due_date) >= ? AND date(due_date) < ?
                ORDER BY due_date
                ''', (start_date, end_date))

            assignments = cursor.fetchall()
            conn.close()

            # Group by date
            calendar_data = {}
            for title, due_date, module, status in assignments:
                due_dt = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                date_key = due_dt.strftime('%Y-%m-%d')

                if date_key not in calendar_data:
                    calendar_data[date_key] = []

                calendar_data[date_key].append({
                    'title': title,
                    'module': module,
                    'time': due_dt.strftime('%H:%M'),
                    'status': status
                })

            return calendar_data

        except Exception as e:
            print(f"Error loading calendar data: {e}")
            return {}


    def load_assignments_for_preview(self, combo):
        """Load assignments for preview filter"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT id, title FROM assignments WHERE is_active = 1 ORDER BY due_date DESC')
            assignments = cursor.fetchall()

            assignment_list = ["All Assignments"] + [f"{aid}: {title}" for aid, title in assignments]
            combo['values'] = assignment_list
            combo.set("All Assignments")

            # Create mapping
            self.preview_assignment_map = {"All Assignments": None}
            for aid, title in assignments:
                self.preview_assignment_map[f"{aid}: {title}"] = aid

            conn.close()

        except Exception as e:
            print(f"Error loading assignments: {e}")


    def load_preview_files(self):
        """Load files for preview"""
        # Clear existing data
        for item in self.preview_files_tree.get_children():
            self.preview_files_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Build query with filters
            query = '''
            SELECT s.id, s.file_name, st.first_name, st.last_name, a.title, s.file_path, s.file_size
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.file_path IS NOT NULL
            '''

            params = []

            # Apply filters
            file_type = self.preview_file_type_var.get()
            if file_type != "All":
                query += " AND s.file_name LIKE ?"
                params.append(f"%{escape_like(file_type)}")

            assignment_filter = self.preview_assignment_var.get()
            assignment_id = self.preview_assignment_map.get(assignment_filter)
            if assignment_id:
                query += " AND s.assignment_id = ?"
                params.append(assignment_id)

            query += " ORDER BY s.submission_date DESC LIMIT 100"

            cursor.execute(query, params)
            files = cursor.fetchall()

            for file_info in files:
                sid, filename, fname, lname, assignment, filepath, size = file_info
                student_name = f"{fname} {lname}"
                file_ext = os.path.splitext(filename)[1]
                file_size_kb = f"{size // 1024} KB" if size else "Unknown"

                self.preview_files_tree.insert('', 'end',
                                              values=(sid, filename, student_name, assignment, file_ext, file_size_kb))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load files: {e}")


    def on_preview_file_select(self, event):
        """Handle file selection for preview"""
        selection = self.preview_files_tree.selection()
        if not selection:
            return

        item = self.preview_files_tree.item(selection[0])
        submission_id = item['values'][0]

        self.show_file_preview_content(submission_id)


    def show_file_preview_content(self, submission_id):
        """Show file preview content"""
        # Clear existing preview
        for widget in self.preview_content_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT file_path, file_name FROM assignment_submissions WHERE id = ?', (submission_id,))
            result = cursor.fetchone()

            if not result:
                ttk.Label(self.preview_content_frame, text="File not found").pack()
                return

            file_path, file_name = result

            if not os.path.exists(file_path):
                ttk.Label(self.preview_content_frame, text="File not found on disk").pack()
                return

            # File info
            info_frame = ttk.Frame(self.preview_content_frame)
            info_frame.pack(fill='x', pady=(0, 10))

            ttk.Label(info_frame, text=f"File: {file_name}", font=('Arial', 12, 'bold')).pack(anchor='w')
            ttk.Label(info_frame, text=f"Size: {os.path.getsize(file_path)} bytes").pack(anchor='w')
            ttk.Label(info_frame, text=f"Modified: {datetime.fromtimestamp(os.path.getmtime(file_path))}").pack(anchor='w')

            # Preview content based on file type
            file_ext = os.path.splitext(file_name)[1].lower()

            if file_ext in ['.txt', '.py', '.java', '.cpp', '.c', '.js', '.html', '.css', '.md']:
                self.show_text_preview(file_path)
            elif file_ext == '.pdf':
                self.show_pdf_preview(file_path)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                self.show_image_preview(file_path)
            else:
                self.show_generic_preview(file_path, file_ext)

            # Action buttons
            action_frame = ttk.Frame(self.preview_content_frame)
            action_frame.pack(fill='x', pady=(10, 0))

            ttk.Button(action_frame, text="Download File",
                      command=lambda: self.download_preview_file(file_path, file_name)).pack(side='left', padx=(0, 10))
            ttk.Button(action_frame, text="Open in External App",
                      command=lambda: self.open_external(file_path)).pack(side='left')

            conn.close()

        except Exception as e:
            ttk.Label(self.preview_content_frame, text=f"Error loading preview: {e}").pack()


    def show_text_preview(self, file_path):
        """Show text file preview"""
        try:
            preview_frame = ttk.LabelFrame(self.preview_content_frame, text="Text Preview", padding=5)
            preview_frame.pack(fill='both', expand=True)

            text_widget = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, state='disabled')
            text_widget.pack(fill='both', expand=True)

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(5000)  # Limit to first 5000 characters
                text_widget.config(state='normal')
                text_widget.insert(tk.END, content)
                if len(content) == 5000:
                    text_widget.insert(tk.END, "\n\n... (Preview truncated)")
                text_widget.config(state='disabled')

        except Exception as e:
            ttk.Label(self.preview_content_frame, text=f"Error reading text file: {e}").pack()


    def show_pdf_preview(self, file_path):
        """Show PDF preview (basic info)"""
        preview_frame = ttk.LabelFrame(self.preview_content_frame, text="PDF Preview", padding=5)
        preview_frame.pack(fill='both', expand=True)

        ttk.Label(preview_frame, text="PDF File Detected").pack(pady=20)
        ttk.Label(preview_frame, text="Use 'Open in External App' to view content").pack()

        # Try to get basic PDF info
        try:
            file_size = os.path.getsize(file_path)
            ttk.Label(preview_frame, text=f"File size: {file_size:,} bytes").pack(pady=5)
        except (OSError, IOError):
            pass


    def show_image_preview(self, file_path):
        """Show image preview"""
        try:
            from PIL import Image, ImageTk

            preview_frame = ttk.LabelFrame(self.preview_content_frame, text="Image Preview", padding=5)
            preview_frame.pack(fill='both', expand=True)

            # Load and resize image
            image = Image.open(file_path)

            # Calculate size to fit in preview (max 400x400)
            max_size = 400
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(image)

            # Display image
            image_label = ttk.Label(preview_frame, image=photo)
            image_label.image = photo  # Keep a reference
            image_label.pack(pady=10)

            # Image info
            ttk.Label(preview_frame, text=f"Dimensions: {image.width} x {image.height}").pack()

        except Exception as e:
            ttk.Label(self.preview_content_frame, text=f"Error loading image: {e}").pack()


    def show_generic_preview(self, file_path, file_ext):
        """Show generic file preview"""
        preview_frame = ttk.LabelFrame(self.preview_content_frame, text="File Info", padding=5)
        preview_frame.pack(fill='both', expand=True)

        ttk.Label(preview_frame, text=f"File Type: {file_ext.upper()} file").pack(pady=20)
        ttk.Label(preview_frame, text="Preview not available for this file type").pack()
        ttk.Label(preview_frame, text="Use download or external app to view").pack()


    def download_preview_file(self, file_path, file_name):
        """Download file from preview"""
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=os.path.splitext(file_name)[1],
                initialfile=file_name,
                filetypes=[("All files", "*.*")]
            )

            if save_path:
                shutil.copy2(file_path, save_path)
                messagebox.showinfo("Success", f"File saved to: {save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to download file: {e}")


    def open_external(self, file_path):
        """Open file in external application"""
        try:
            import platform
            import subprocess
            system = platform.system()

            if system == "Windows":
                os.startfile(file_path)
            elif system == "Darwin":  # macOS
                subprocess.run(['open', file_path], check=True)
            else:  # Linux
                # Try common PDF viewers for PDF files
                if file_path.lower().endswith('.pdf'):
                    pdf_viewers = ['evince', 'okular', 'xpdf', 'mupdf', 'firefox', 'google-chrome', 'chromium']
                    opened = False

                    for viewer in pdf_viewers:
                        try:
                            # Check if viewer exists
                            if subprocess.run(['which', viewer], capture_output=True).returncode == 0:
                                subprocess.Popen([viewer, file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                opened = True
                                break
                        except (OSError, subprocess.SubprocessError):
                            continue

                    if not opened:
                        # Fallback to xdg-open
                        subprocess.Popen(['xdg-open', file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # For non-PDF files, use xdg-open
                    subprocess.Popen(['xdg-open', file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                messagebox.showinfo("Success", f"Opening file in external application...")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}\n\nPlease install a PDF viewer (evince, okular, etc.) or open the file manually.")

    # SYSTEM UTILITIES (missing from GUI)

    def show_file_preview(self):
        """Show file preview interface with enhanced features"""
        if not self._check_permission('view_all_submissions'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="File Preview System", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Filter frame
        filter_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="File Type:").grid(row=0, column=0, sticky='w', padx=5)
        self.preview_file_type_var = tk.StringVar(value="All")
        file_type_combo = ttk.Combobox(filter_frame, textvariable=self.preview_file_type_var,
                                      values=["All", ".pdf", ".docx", ".txt", ".jpg", ".png"], width=10)
        file_type_combo.grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text="Assignment:").grid(row=0, column=2, sticky='w', padx=5)
        self.preview_assignment_var = tk.StringVar()
        assignment_combo = ttk.Combobox(filter_frame, textvariable=self.preview_assignment_var, width=25)
        assignment_combo.grid(row=0, column=3, padx=5)
        self.load_assignments_for_preview(assignment_combo)

        ttk.Button(filter_frame, text="Apply Filters",
                  command=self.load_preview_files).grid(row=0, column=4, padx=10)

        # Files list
        files_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Submission Files", padding=5)
        files_frame.pack(fill='x', pady=(0, 10))

        columns = ('ID', 'File Name', 'Student', 'Assignment', 'Type', 'Size')
        self.preview_files_tree = ttk.Treeview(files_frame, columns=columns, show='headings', height=6)

        for col in columns:
            self.preview_files_tree.heading(col, text=col)
            self.preview_files_tree.column(col, width=100)

        v_scroll = ttk.Scrollbar(files_frame, orient='vertical', command=self.preview_files_tree.yview)
        self.preview_files_tree.configure(yscrollcommand=v_scroll.set)
        self.preview_files_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        self.preview_files_tree.bind('<<TreeviewSelect>>', self.on_preview_file_select)

        # File preview
        self.preview_content_frame = ttk.LabelFrame(self.gui.layout.content_area, text="File Preview", padding=10)
        self.preview_content_frame.pack(fill='both', expand=True)

        # Load initial file list
        self.load_preview_files()


    def preview_submission_file(self, *args, **kwargs):
        """Launch the enhanced submission preview tool."""
        self._launch_gui_feature(self.show_file_preview, "submission preview")



    def launch_academic_calendar(self):
        """Launch the full academic calendar GUI in a Toplevel window"""
        try:
            from education_system.university_system.modules.domain.academics.gui.academic_calendar.main_gui import CalendarGUI
            # Launch in a Toplevel so "Return to Main Menu" just closes it
            calendar_window = tk.Toplevel(self.root)
            calendar_window.title("Academic Calendar")
            calendar_window.geometry("1400x900")
            CalendarGUI(auth_manager=self.auth, parent_window=calendar_window)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Academic Calendar: {e}")

    def view_assignment_calendar(self, *args, **kwargs):
        """Display the assignment calendar UI."""
        self._launch_gui_feature(self.show_calendar, "assignment calendar")


    def _show_file_preview(self, file_path, file_name):
        """Show file preview content (helper function)"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()

            # Create preview dialog with larger size
            dialog = tk.Toplevel(self.root)
            dialog.title(f"File Preview - {file_name}")
            dialog.geometry("1200x800")  # Increased from 800x600 for better visibility
            dialog.transient(self.root)

            # Title frame
            title_frame = ttk.Frame(dialog)
            title_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(title_frame, text=f"File: {file_name}",
                     font=('TkDefaultFont', 12, 'bold')).pack(side='left')
            ttk.Label(title_frame, text=f"Type: {file_ext}",
                     style='Info.TLabel').pack(side='right')

            # Content frame
            content_frame = ttk.Frame(dialog)
            content_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            # Route to appropriate preview based on file type
            if file_ext in ['.txt', '.py', '.java', '.c', '.cpp', '.h', '.js', '.html', '.css', '.json', '.xml', '.md']:
                self.show_text_preview_in_dialog(file_path, content_frame)
            elif file_ext == '.pdf':
                self.show_pdf_preview_in_dialog(file_path, content_frame)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                self.show_image_preview_in_dialog(file_path, content_frame)
            else:
                self.show_generic_preview_in_dialog(file_path, file_ext, content_frame)

            # Action buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Download",
                      command=lambda: self.download_preview_file(file_path, file_name)).pack(side='left', padx=(0, 10))
            ttk.Button(button_frame, text="Open in External App",
                      command=lambda: self.open_external(file_path)).pack(side='left')
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to preview file: {e}")


    def show_text_preview_in_dialog(self, file_path, parent):
        """Show text file preview in dialog"""
        try:
            # Increased height and width for better visibility
            text_widget = scrolledtext.ScrolledText(parent, wrap=tk.WORD, height=40, width=140)
            text_widget.pack(fill='both', expand=True)

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                text_widget.insert(tk.END, content)

            text_widget.config(state='disabled')
        except Exception as e:
            ttk.Label(parent, text=f"Error reading file: {e}").pack()


    def show_pdf_preview_in_dialog(self, file_path, parent):
        """Show PDF preview in dialog"""
        ttk.Label(parent, text="PDF Preview", font=('TkDefaultFont', 12, 'bold')).pack(pady=10)
        ttk.Label(parent, text=f"PDF file: {os.path.basename(file_path)}").pack()
        ttk.Label(parent, text="Click 'Open in External App' to view full PDF").pack(pady=20)


    def show_image_preview_in_dialog(self, file_path, parent):
        """Show image preview in dialog"""
        try:
            from PIL import Image, ImageTk

            img = Image.open(file_path)

            # Resize if too large
            max_size = (750, 500)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)

            label = ttk.Label(parent, image=photo)
            label.image = photo  # Keep reference
            label.pack(pady=10)

        except Exception as e:
            ttk.Label(parent, text=f"Error loading image: {e}").pack()


    def show_generic_preview_in_dialog(self, file_path, file_ext, parent):
        """Show generic file info"""
        info_text = f"File Type: {file_ext}\n"
        info_text += f"Size: {os.path.getsize(file_path)} bytes\n"
        info_text += f"Path: {file_path}\n\n"
        info_text += "Preview not available for this file type.\n"
        info_text += "Use 'Open in External App' to view the file."

        ttk.Label(parent, text=info_text, justify='left').pack(pady=20)


    def _launch_gui_feature(self, callback, feature_name):
        """Helper to launch GUI features with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror("Error", f"Error launching {feature_name}: {str(e)}")


