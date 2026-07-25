from education_system.systems.university.interfaces.gui.academics.course_management_gui.core._imports import (
    _, csv, datetime, filedialog, messagebox, tk, ttk,
    sqlite3, ScrolledText, DEFAULT_DB_PATH,
)


class DataIOMixin:
    """Import/export CSV, database backup, and detailed course viewer."""

    def import_csv(self):
        """Import courses from CSV file"""
        file_path = filedialog.askopenfilename(
            title="Select CSV file to import",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            imported_count = 0
            error_count = 0

            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                required_fields = ['course_code', 'course_name', 'department']
                if not all(field in reader.fieldnames for field in required_fields):
                    messagebox.showerror(_("common.import_error"), _("course_management.messages.csv_missing_required_columns", columns=', '.join(required_fields)))
                    return

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                try:
                    cursor = conn.cursor()
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    for row_num, row in enumerate(reader, 1):
                        try:
                            course_code = row['course_code'].strip().upper()
                            course_name = row['course_name'].strip()
                            department = row['department'].strip()

                            if not course_code or not course_name:
                                error_count += 1
                                continue

                            # Check for duplicates
                            cursor.execute("SELECT id FROM courses WHERE code = ?", (course_code,))
                            if cursor.fetchone():
                                error_count += 1
                                continue

                            # Prepare optional fields
                            description = row.get('description', '').strip()
                            level = row.get('level', '').strip()
                            credit_hours = float(row.get('credit_hours', 3.0))
                            max_enrollment = int(row.get('max_enrollment', 30))
                            course_type = row.get('course_type', 'Core').strip()

                            import uuid
                            course_id = str(uuid.uuid4())

                            # Insert course
                            cursor.execute('''
                            INSERT INTO courses (
                                id, code, name, credits, date_added,
                                course_code, course_name, description, level, department,
                                credit_hours, max_enrollment, course_type, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (course_id, course_code, course_name, int(credit_hours), timestamp,
                                  course_code, course_name, description, level, department,
                                  credit_hours, max_enrollment, course_type, timestamp, timestamp))

                            imported_count += 1

                        except (ValueError, sqlite3.Error):
                            error_count += 1
                            continue

                    conn.commit()
                finally:
                    conn.close()

            self.refresh_course_list()

            message = _("course_management.messages.import_results", success=imported_count, errors=error_count)
            messagebox.showinfo(_("course_management.messages.import_results"), message)
            self.update_status(_("course_management.status.import_completed"))

        except Exception as e:
            messagebox.showerror(_("common.import_error"), _("course_management.messages.failed_import_csv", error=str(e)))

    def export_csv(self):
        """Export courses to CSV file"""
        file_path = filedialog.asksaveasfilename(
            title="Save CSV file",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM courses ORDER BY course_code")
            courses = cursor.fetchall()

            # Get column names
            cursor.execute("PRAGMA table_info(courses)")
            columns = [col[1] for col in cursor.fetchall()]

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns)
                writer.writerows(courses)

            conn.close()

            messagebox.showinfo(_("common.export_complete"), _("course_management.messages.export_complete_count", count=len(courses), file=file_path))
            self.update_status(_("course_management.status.export_completed", count=len(courses)))

        except Exception as e:
            messagebox.showerror(_("common.export_error"), _("course_management.messages.failed_export_csv", error=str(e)))

    def backup_database(self):
        """Create database backup - enhanced version"""
        file_path = filedialog.asksaveasfilename(
            title="Save database backup",
            defaultextension=".sql",
            filetypes=[("SQL files", "*.sql"), ("SQLite files", "*.db"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")

            if file_path.endswith('.sql'):
                # SQL dump backup
                with open(file_path, 'w') as f:
                    for line in conn.iterdump():
                        f.write('%s\n' % line)
            else:
                # Binary database copy
                backup_conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                try:
                    conn.backup(backup_conn)
                finally:
                    backup_conn.close()

            conn.close()

            messagebox.showinfo(_("course_management.messages.backup_complete"), _("course_management.messages.backup_complete", file=file_path))
            self.update_status(_("course_management.status.database_backup_created"))

        except Exception as e:
            messagebox.showerror(_("course_management.messages.backup_error"), _("course_management.messages.failed_backup", error=str(e)))

    def view_course_details(self, cursor, course_id):
        """Enhanced course details viewer"""
        cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        course = cursor.fetchone()

        if not course:
            messagebox.showerror(_("common.error"), _("course_management.messages.course_not_found"))
            return

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(_("course_management.dialogs.course_details", name=course[1]))
        details_window.geometry("600x700")
        details_window.transient(self.root)

        # Create notebook for different views
        notebook = ttk.Notebook(details_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Basic Info Tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text=_("course_management.analytics_tabs.basic_info"))

        basic_text = ScrolledText(basic_frame, wrap=tk.WORD)
        basic_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        basic_text.insert(tk.END, self.format_course_details(course))
        basic_text.config(state=tk.DISABLED)

        # Prerequisites Tab
        prereq_frame = ttk.Frame(notebook)
        notebook.add(prereq_frame, text=_("course_management.analytics_tabs.prerequisites"))

        prereq_text = ScrolledText(prereq_frame, wrap=tk.WORD)
        prereq_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load prerequisites
        cursor.execute("""
        SELECT c.course_code, c.course_name, cp.is_required
        FROM course_prerequisites cp
        JOIN courses c ON cp.prerequisite_course_id = c.id
        WHERE cp.course_id = ?
        ORDER BY c.course_code
        """, (course_id,))

        prereqs = cursor.fetchall()
        if prereqs:
            prereq_text.insert(tk.END, "PREREQUISITES:\n\n")
            for code, name, required in prereqs:
                req_type = "Required" if required else "Recommended"
                prereq_text.insert(tk.END, f"\u2022 {code} - {name} ({req_type})\n")
        else:
            prereq_text.insert(tk.END, "No prerequisites for this course.")

        prereq_text.config(state=tk.DISABLED)

        # Schedule Tab
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text=_("course_management.analytics_tabs.schedule"))

        schedule_text = ScrolledText(schedule_frame, wrap=tk.WORD)
        schedule_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load schedule
        cursor.execute("""
        SELECT cs.semester, cs.year, cs.start_time, cs.end_time, cs.days_of_week, cs.classroom,
               COALESCE(i.first_name || ' ' || i.last_name, 'Unassigned') as instructor
        FROM course_schedule cs
        LEFT JOIN instructors i ON cs.instructor_id = i.id
        WHERE cs.course_id = ?
        ORDER BY cs.year DESC, cs.semester
        """, (course_id,))

        schedules = cursor.fetchall()
        if schedules:
            schedule_text.insert(tk.END, "COURSE SCHEDULES:\n\n")
            for schedule in schedules:
                semester, year, start, end, days, room, instructor = schedule
                schedule_text.insert(tk.END, f"Semester: {semester} {year}\n")
                if start and end:
                    schedule_text.insert(tk.END, f"Time: {start} - {end}\n")
                if days:
                    schedule_text.insert(tk.END, f"Days: {days}\n")
                if room:
                    schedule_text.insert(tk.END, f"Room: {room}\n")
                schedule_text.insert(tk.END, f"Instructor: {instructor}\n\n")
        else:
            schedule_text.insert(tk.END, "No schedule information available.")

        schedule_text.config(state=tk.DISABLED)

        # Close button
        ttk.Button(details_window, text=_("common.close"), command=details_window.destroy).pack(pady=10)
