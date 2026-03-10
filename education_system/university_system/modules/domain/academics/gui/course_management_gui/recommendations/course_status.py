from ._imports import (
    tk, ttk, messagebox, sqlite3, _, DEFAULT_DB_PATH, datetime,
)


class CourseStatusMixin:
    def manage_course_status_gui(self):
        """
        Manage course status (Active, Inactive, Archived, Cancelled).
        Opens a dialog to change course status.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Course Status")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Manage Course Status",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection
        select_frame = ttk.LabelFrame(main_frame, text="Select Course", padding="10")
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(select_frame, textvariable=course_var, state='readonly', width=45)
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Current status display
        current_status_var = tk.StringVar(value="No course selected")
        ttk.Label(select_frame, text="Current Status:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(select_frame, textvariable=current_status_var,
                 font=('Arial', 10, 'bold')).grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

        # New status selection
        status_frame = ttk.LabelFrame(main_frame, text="Select New Status", padding="10")
        status_frame.pack(fill=tk.X, pady=5)

        ttk.Label(status_frame, text="New Status:").grid(row=0, column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(status_frame, textvariable=status_var,
                                   values=["Active", "Inactive", "Archived", "Cancelled"],
                                   state='readonly', width=25)
        status_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        def load_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, course_code, course_name, status
                    FROM courses ORDER BY course_code
                """)
                courses = cursor.fetchall()
                conn.close()

                course_list = [f"{code} - {name} (ID: {id})" for id, code, name, status in courses]
                course_combo['values'] = course_list

                # Store course data for status display
                course_combo.course_data = {
                    f"{code} - {name} (ID: {id})": status
                    for id, code, name, status in courses
                }

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
                dialog.destroy()

        def on_course_select(*args):
            selected = course_var.get()
            if selected and hasattr(course_combo, 'course_data'):
                current_status = course_combo.course_data.get(selected, "Unknown")
                current_status_var.set(current_status)
                status_var.set(current_status)

        course_combo.bind('<<ComboboxSelected>>', on_course_select)

        def update_status():
            if not course_var.get():
                messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a course")
                return

            if not status_var.get():
                messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a new status")
                return

            current = current_status_var.get()
            new = status_var.get()

            if current == new:
                messagebox.showinfo("No Change", "Status is already set to " + new)
                return

            if messagebox.askyesno("Confirm Status Change",
                                  f"Change course status from {current} to {new}?"):
                try:
                    course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))

                    conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                    cursor = conn.cursor()

                    cursor.execute("""
                        UPDATE courses SET status = ?, updated_at = ?
                        WHERE id = ?
                    """, (new, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), course_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_("common.success"), f"Course status updated to {new}")
                    self.update_status(f"Course status changed to {new}")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_("common.error"), f"Failed to update status: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Update Status", command=update_status).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        load_courses()

    def view_course_history_gui(self):
        """
        View historical changes to courses (audit trail).
        Opens a dialog with course history information.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("View Course History")
        dialog.geometry("900x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Course Change History",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="Filter by Course:").pack(side=tk.LEFT, padx=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Treeview for history
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ('Course', 'Field', 'Old Value', 'New Value', 'Changed By', 'Date')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def load_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, course_code, course_name FROM courses "
                    "WHERE course_code IS NOT NULL "
                    "AND course_name IS NOT NULL "
                    "AND LOWER(COALESCE(status, 'active')) = 'active' "
                    "ORDER BY course_code"
                )
                courses = cursor.fetchall()
                conn.close()

                course_list = ["-- All Courses --"] + [f"{code} - {name} (ID: {id})" for id, code, name in courses]
                course_combo['values'] = course_list
                course_combo.current(0)

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

        def load_history(*args):
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Check if course_history table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='course_history'
                """)
                if not cursor.fetchone():
                    tree.insert('', tk.END, values=(
                        "History table not found", "", "", "", "", ""
                    ))
                    conn.close()
                    return

                selected = course_var.get()

                if selected == "-- All Courses --" or not selected:
                    cursor.execute("""
                        SELECT c.course_code, h.field_name, h.old_value,
                               h.new_value, h.changed_by, h.changed_at
                        FROM course_history h
                        JOIN courses c ON h.course_id = c.id
                        ORDER BY h.changed_at DESC
                        LIMIT 100
                    """)
                else:
                    course_id = int(selected.split("ID: ")[1].rstrip(")"))
                    cursor.execute("""
                        SELECT c.course_code, h.field_name, h.old_value,
                               h.new_value, h.changed_by, h.changed_at
                        FROM course_history h
                        JOIN courses c ON h.course_id = c.id
                        WHERE h.course_id = ?
                        ORDER BY h.changed_at DESC
                    """, (course_id,))

                history = cursor.fetchall()
                conn.close()

                for entry in history:
                    code, field, old_val, new_val, changed_by, changed_at = entry
                    old_display = (old_val[:25] + "...") if old_val and len(old_val) > 25 else (old_val or "")
                    new_display = (new_val[:25] + "...") if new_val and len(new_val) > 25 else (new_val or "")
                    date_display = changed_at.split()[0] if changed_at else ""

                    tree.insert('', tk.END, values=(
                        code, field, old_display, new_display,
                        changed_by or "System", date_display
                    ))

                if not history:
                    tree.insert('', tk.END, values=(
                        "No history records found", "", "", "", "", ""
                    ))

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to load history: {e}")

        course_combo.bind('<<ComboboxSelected>>', load_history)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Refresh", command=load_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
        load_history()
