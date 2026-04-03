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



class AlumniCRUDMixin:
        def _fetch_alumni_record(self, alumni_id: str | None):
            """Retrieve an alumni record from the database."""
            if not alumni_id:
                return None
            conn = self._get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM alumni
                WHERE alumni_id = ?
                """,
                (alumni_id,)
            )
            row = cursor.fetchone()

            # If not found, try alternative identifiers (e.g., without leading 'A')
            if not row and alumni_id.upper().startswith('A'):
                cursor.execute(
                    """
                    SELECT *
                    FROM alumni
                    WHERE alumni_id = ?
                    """,
                    (alumni_id.upper(),)
                )
                row = cursor.fetchone()

            if row:
                record = dict(row)
                record['source'] = 'alumni'
                conn.close()
                return record

            # Attempt fallback to students table
            candidate_ids = [alumni_id]
            if alumni_id.upper().startswith('A'):
                candidate_ids.append(alumni_id[1:])

            record = None
            for candidate in candidate_ids:
                cursor.execute(
                    """
                    SELECT student_id, first_name, middle_name, last_name, course,
                           email_address AS email, '' AS phone, '' AS city, '' AS country, '' AS linkedin_url,
                           '' AS graduation_year
                    FROM students
                    WHERE student_id = ?
                    """,
                    (candidate,)
                )
                student_row = cursor.fetchone()
                if student_row:
                    data = dict(student_row)
                    data['alumni_id'] = alumni_id if alumni_id.startswith('A') else f"A{candidate}"
                    data['source'] = 'students'
                    data['email_address'] = data.get('email')
                    data.setdefault('graduation_year', '')
                    data['degree_earned'] = data.get('course')
                    data['current_employer'] = ''
                    data['job_title'] = ''
                    data['industry'] = ''
                    record = data
                    break

            conn.close()
            return record

        def _open_alumni_editor(self, record: dict):
            """Open an editor dialog for the given alumni record."""
            if not record:
                messagebox.showerror("Not Found", "Alumni record could not be located.")
                return

            editor = tk.Toplevel(self.root)
            editor.title(f"Edit Alumni - {record.get('alumni_id')}")
            editor.geometry("500x600")
            editor.transient(self.root)
            editor.grab_set()

            form_frame = ttk.Frame(editor, padding=20)
            form_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(form_frame, text=f"Editing {record.get('alumni_id')}", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

            fields = [
                ("First Name", "first_name"),
                ("Middle Name", "middle_name"),
                ("Last Name", "last_name"),
                ("Graduation Year", "graduation_year"),
                ("Degree", "degree_earned"),
                ("Current Employer", "current_employer"),
                ("Job Title", "job_title"),
                ("Industry", "industry"),
                ("Email Address", "email_address"),
                ("Phone", "phone"),
                ("City", "city"),
                ("Country", "country"),
                ("LinkedIn URL", "linkedin_url"),
            ]

            form_vars = {}
            for label, key in fields:
                value = record.get(key) or ''
                var = tk.StringVar(value=str(value) if value is not None else '')
                form_vars[key] = var

                row = ttk.Frame(form_frame)
                row.pack(fill=tk.X, pady=4)
                ttk.Label(row, text=label + ":", width=18).pack(side=tk.LEFT)
                ttk.Entry(row, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)

            def save_changes():
                updates = {key: var.get().strip() for key, var in form_vars.items()}
                try:
                    self._save_alumni_updates(record, updates)
                    editor.destroy()
                    self.load_alumni_data()
                    messagebox.showinfo("Success", "Alumni record updated successfully.")
                except ValueError as exc:
                    messagebox.showerror("Validation Error", f"Invalid input: {exc}")
                except sqlite3.Error as exc:
                    messagebox.showerror("Database Error", f"Could not save changes: {exc}")

            button_frame = ttk.Frame(form_frame)
            button_frame.pack(fill=tk.X, pady=20)
            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT)
            ttk.Button(button_frame, text="Cancel", command=editor.destroy).pack(side=tk.RIGHT)

        def _save_alumni_updates(self, record: dict, updates: dict):
            """Persist updates to the alumni table."""
            conn = self._get_db_connection()
            cursor = conn.cursor()

            alumni_id = record.get('alumni_id') or record.get('student_id')
            if not alumni_id:
                raise ValueError("Alumni identifier missing.")

            # Normalise graduation year to integer when possible
            grad_year_text = updates.get('graduation_year', '')
            graduation_year = None
            if grad_year_text:
                try:
                    graduation_year = int(grad_year_text)
                except ValueError:
                    raise ValueError("Graduation year must be a number.")

            data = {
                'alumni_id': alumni_id,
                'student_id': record.get('student_id'),
                'first_name': updates.get('first_name'),
                'middle_name': updates.get('middle_name'),
                'last_name': updates.get('last_name'),
                'graduation_year': graduation_year,
                'degree_earned': updates.get('degree_earned'),
                'current_employer': updates.get('current_employer'),
                'job_title': updates.get('job_title'),
                'industry': updates.get('industry'),
                'email_address': updates.get('email_address'),
                'phone': updates.get('phone'),
                'city': updates.get('city'),
                'country': updates.get('country'),
                'linkedin_url': updates.get('linkedin_url'),
                'date_registered': record.get('date_registered') or datetime.now().isoformat(),
            }

            if record.get('source') == 'alumni':
                cursor.execute(
                    """
                    UPDATE alumni
                    SET first_name = ?, middle_name = ?, last_name = ?, graduation_year = ?, degree_earned = ?,
                        current_employer = ?, job_title = ?, industry = ?, email_address = ?, phone = ?,
                        city = ?, country = ?, linkedin_url = ?, date_registered = COALESCE(date_registered, ?)
                    WHERE alumni_id = ?
                    """,
                    (
                        data['first_name'], data['middle_name'], data['last_name'], data['graduation_year'],
                        data['degree_earned'], data['current_employer'], data['job_title'], data['industry'],
                        data['email_address'], data['phone'], data['city'], data['country'],
                        data['linkedin_url'], data['date_registered'], alumni_id
                    )
                )
            else:
                # Insert or replace alumni record derived from student data
                if not data['student_id']:
                    data['student_id'] = alumni_id[1:] if alumni_id.upper().startswith('A') else alumni_id
                cursor.execute(
                    """
                    INSERT INTO alumni (
                        alumni_id, student_id, email_address, title, first_name, middle_name, last_name,
                        graduation_year, degree_earned, current_employer, job_title, industry,
                        city, country, phone, linkedin_url, date_registered, is_donor, is_mentor, is_board_member
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0
                    )
                    ON CONFLICT(alumni_id) DO UPDATE SET
                        student_id = excluded.student_id,
                        email_address = excluded.email_address,
                        first_name = excluded.first_name,
                        middle_name = excluded.middle_name,
                        last_name = excluded.last_name,
                        graduation_year = excluded.graduation_year,
                        degree_earned = excluded.degree_earned,
                        current_employer = excluded.current_employer,
                        job_title = excluded.job_title,
                        industry = excluded.industry,
                        city = excluded.city,
                        country = excluded.country,
                        phone = excluded.phone,
                        linkedin_url = excluded.linkedin_url,
                        date_registered = excluded.date_registered
                    """,
                    (
                        data['alumni_id'], data['student_id'], data['email_address'], None,
                        data['first_name'], data['middle_name'], data['last_name'],
                        data['graduation_year'], data['degree_earned'], data['current_employer'],
                        data['job_title'], data['industry'], data['city'], data['country'],
                        data['phone'], data['linkedin_url'], data['date_registered']
                    )
                )

            conn.commit()
            conn.close()

            # Send alumni welcome email automatically
            try:
                from education_system.university_system.infrastructure.email.email_service import send_alumni_welcome_email
                full_name = f"{data['first_name']} {data.get('middle_name', '')} {data['last_name']}".replace('  ', ' ')
                send_alumni_welcome_email(data['alumni_id'], data['email_address'], full_name)
            except ImportError as e:
                import logging
                logging.warning(f"Email service not available: {e}")
            except (sqlite3.Error, AttributeError, KeyError) as e:
                import logging
                logging.warning(f"Failed to send alumni welcome email: {e}")

        def check_finance_status(self, student_id, alumni_email):
            """Check if alumni owes money to the university"""
            try:
                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Check outstanding balances
                cursor.execute('''
                    SELECT
                        SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END) as pending_amount,
                        SUM(CASE WHEN status = 'overdue' THEN amount ELSE 0 END) as overdue_amount
                    FROM financial_records
                    WHERE student_id = ?
                ''', (student_id,))

                result = cursor.fetchone()
                conn.close()

                pending_amount = result[0] if result[0] else 0
                overdue_amount = result[1] if result[1] else 0
                total_owed = pending_amount + overdue_amount

                return {
                    'has_debt': total_owed > 0,
                    'pending_amount': pending_amount,
                    'overdue_amount': overdue_amount,
                    'total_owed': total_owed
                }

            except sqlite3.Error as e:
                print(f"Error checking finance status: {e}")
                return {'has_debt': False, 'error': f'Could not check finance status: {e}'}

        def clear_alumni_form(self):
            """Clear all form fields"""
            for var in self.form_vars.values():
                if isinstance(var, tk.BooleanVar):
                    var.set(False)
                else:
                    var.set("")

        def delete_alumni_record(self, alumni_id, alumni_name, alumni_email):
            """Delete alumni record with confirmation"""
            result = messagebox.askyesno("Delete Alumni",
                                       f"Are you sure you want to permanently delete the alumni record for {alumni_name}?\n\n"
                                       "This action cannot be undone.")
            if result:
                # Confirm deletion one more time
                confirm = messagebox.askyesno("Final Confirmation",
                                            "This will permanently delete all alumni data.\n\n"
                                            "Are you absolutely sure?")
                if confirm:
                    # Simulate deletion
                    # Here you would call the backend deletion function

                    # Send deletion confirmation email
                    self.send_profile_deletion_confirmation(alumni_email, alumni_name)

                    messagebox.showinfo("Success", f"Alumni record for {alumni_name} has been deleted.\nConfirmation email sent.")

        def edit_selected_alumni(self):
            """Edit the selected alumni record"""
            selection = self.alumni_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an alumni record to edit.")
                return

            item = self.alumni_tree.item(selection[0])
            alumni_id = item['values'][0]
            record = self._fetch_alumni_record(alumni_id)
            self._open_alumni_editor(record)

        def load_alumni_data(self):
            """Load alumni data into the treeview"""
            try:
                # Clear existing data
                for item in self.alumni_tree.get_children():
                    self.alumni_tree.delete(item)
                conn = self._get_db_connection()
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        alumni_id,
                        first_name,
                        middle_name,
                        last_name,
                        graduation_year,
                        degree_earned,
                        current_employer,
                        email_address,
                        privacy_level
                    FROM alumni
                    ORDER BY COALESCE(graduation_year, 0) DESC, last_name, first_name
                    """
                )
                rows = cursor.fetchall()

                if rows:
                    for row in rows:
                        formatted = self._format_alumni_row(row)
                        self.alumni_tree.insert('', tk.END, values=formatted)
                    self.update_status(f"Loaded {len(rows)} alumni records")
                else:
                    # Fallback to students who have graduated
                    cursor.execute(
                        """
                        SELECT
                            student_id,
                            first_name,
                            middle_name,
                            last_name,
                            '' AS graduation_year,
                            course,
                            '' AS current_employer,
                            email_address AS email,
                            1 AS privacy_level
                        FROM students
                        WHERE status = 'Graduated'
                        ORDER BY last_name, first_name
                        """
                    )
                    fallback_rows = cursor.fetchall()
                    if fallback_rows:
                        for row in fallback_rows:
                            formatted = self._format_alumni_row(row)
                            self.alumni_tree.insert('', tk.END, values=formatted)
                        self.update_status("Showing graduated students (no dedicated alumni records found)")
                    else:
                        self.update_status("No alumni records found")
                        self.alumni_tree.insert(
                            '',
                            tk.END,
                            values=('N/A', 'No alumni records available', '', '', '', '', 'Setup required')
                        )

                conn.close()
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load alumni data: {str(e)}")

        def load_alumni_for_update(self, alumni_id):
            """Load alumni data for updating"""
            if not alumni_id:
                messagebox.showwarning("Input Required", "Please enter an Alumni ID")
                return
            record = self._fetch_alumni_record(alumni_id.strip())
            if not record:
                messagebox.showerror("Not Found", f"No alumni or graduated student record found for ID {alumni_id}.")
                return

            self._open_alumni_editor(record)
            self.update_status(f"Loaded alumni record {record.get('alumni_id')} for editing")

        def search_alumni(self, search_term):
            """Search alumni based on search term"""
            search_term = (search_term or "").strip()
            if not search_term:
                self.load_alumni_data()
                return

            try:
                # Clear existing data
                for item in self.alumni_tree.get_children():
                    self.alumni_tree.delete(item)

                conn = self._get_db_connection()
                cursor = conn.cursor()
                like_term = f"%{escape_like(search_term)}%"

                cursor.execute(
                    """
                    SELECT
                        alumni_id,
                        first_name,
                        middle_name,
                        last_name,
                        graduation_year,
                        degree_earned,
                        current_employer,
                        email_address,
                        privacy_level
                    FROM alumni
                    WHERE (
                        alumni_id LIKE ?
                        OR first_name LIKE ?
                        OR last_name LIKE ?
                        OR email_address LIKE ?
                        OR degree_earned LIKE ?
                        OR current_employer LIKE ?
                        OR industry LIKE ?
                    )
                    ORDER BY COALESCE(graduation_year, 0) DESC, last_name, first_name
                    """,
                    (like_term,) * 7
                )
                rows = cursor.fetchall()

                if not rows:
                    cursor.execute(
                        """
                        SELECT
                            student_id,
                            first_name,
                            middle_name,
                            last_name,
                            '' AS graduation_year,
                            course,
                            '' AS current_employer,
                            email_address AS email,
                            1 AS privacy_level
                        FROM students
                        WHERE (
                            student_id LIKE ?
                            OR first_name LIKE ?
                            OR last_name LIKE ?
                            OR email_address LIKE ?
                            OR course LIKE ?
                        )
                        AND status = 'Graduated'
                        ORDER BY last_name, first_name
                        """,
                        (like_term,) * 5
                    )
                    rows = cursor.fetchall()

                conn.close()

                for row in rows:
                    formatted = self._format_alumni_row(row)
                    self.alumni_tree.insert('', tk.END, values=formatted)

                self.update_status(f"Found {len(rows)} alumni matching '{search_term}'")
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Search failed: {str(e)}")

        def show_finance_check(self):
            """Show finance status check interface"""
            self.clear_content()
            self.update_status("Finance Status Check")

            # Title
            title_label = ttk.Label(self.content_frame, text="Finance Status Check",
                                   font=('Arial', 16, 'bold'))
            title_label.pack(pady=20)

            # Input frame
            input_frame = ttk.LabelFrame(self.content_frame, text="Check Finance Status", padding=20)
            input_frame.pack(fill=tk.X, padx=20, pady=10)

            # Student ID input
            ttk.Label(input_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
            student_id_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=student_id_var, width=20).grid(row=0, column=1, padx=10, pady=5)

            # Email input
            ttk.Label(input_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=5)
            email_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=email_var, width=30).grid(row=1, column=1, padx=10, pady=5)

            # Check button
            def check_finance():
                student_id = student_id_var.get().strip()
                email = email_var.get().strip()

                if not student_id:
                    messagebox.showerror("Input Required", "Please enter Student ID")
                    return

                finance_status = self.check_finance_status(student_id, email)

                if 'error' in finance_status:
                    messagebox.showerror("Error", finance_status['error'])
                else:
                    self.show_finance_status_dialog(finance_status, f"Student {student_id}")

            ttk.Button(input_frame, text="Check Finance Status",
                      command=check_finance).grid(row=2, column=0, columnspan=2, pady=20)

        def show_finance_status_dialog(self, finance_status, alumni_name):
            """Show dialog with finance status information"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Finance Status")
            dialog.geometry("400x300")
            dialog.configure(bg='white')
            dialog.grab_set()

            if finance_status['has_debt']:
                # Show debt information
                tk.Label(dialog, text="Outstanding Balance", font=('Arial', 14, 'bold'),
                        bg='white', fg='#e74c3c').pack(pady=10)

                info_frame = tk.Frame(dialog, bg='white')
                info_frame.pack(fill='x', padx=20, pady=10)

                tk.Label(info_frame, text=f"Pending Amount: ${finance_status['pending_amount']:.2f}",
                        font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w')
                tk.Label(info_frame, text=f"Overdue Amount: ${finance_status['overdue_amount']:.2f}",
                        font=('Arial', 11), bg='white', fg='#e74c3c').pack(anchor='w')
                tk.Label(info_frame, text=f"Total Owed: ${finance_status['total_owed']:.2f}",
                        font=('Arial', 12, 'bold'), bg='white', fg='#e74c3c').pack(anchor='w', pady=(5, 0))

                tk.Button(dialog, text="Open Finance System",
                         command=lambda: self.open_finance_gui(),
                         bg='#27ae60', fg='white', font=('Arial', 11),
                         padx=20, pady=8, relief='flat').pack(pady=10)
            else:
                # No debt
                tk.Label(dialog, text="Finance Status: Clear", font=('Arial', 14, 'bold'),
                        bg='white', fg='#27ae60').pack(pady=20)
                tk.Label(dialog, text="No outstanding balance found.",
                        font=('Arial', 11), bg='white', fg='#34495e').pack(pady=10)

            tk.Button(dialog, text="Close", command=dialog.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 10),
                     padx=20, pady=5, relief='flat').pack(pady=10)

        def show_register_alumni(self):
            """Show alumni registration form"""
            self.clear_content()
            self.update_status("Alumni Registration Form")

            # Create scrollable frame
            canvas = tk.Canvas(self.content_frame)
            scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Title
            ttk.Label(scrollable_frame, text="Register New Alumni",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Personal Information Section
            personal_frame = ttk.LabelFrame(scrollable_frame, text="Personal Information", padding=10)
            personal_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            # Create form fields
            self.form_vars = {}

            personal_fields = [
                ("Title", "title"),
                ("First Name*", "first_name"),
                ("Middle Name", "middle_name"),
                ("Last Name*", "last_name"),
                ("Email Address*", "email"),
                ("Gender", "gender"),
                ("Date of Birth (YYYY-MM-DD)", "dob"),
                ("Phone Number", "phone")
            ]

            for i, (label, var_name) in enumerate(personal_fields):
                row = i // 2
                col = i % 2

                field_frame = ttk.Frame(personal_frame)
                field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

                ttk.Label(field_frame, text=label).pack(anchor='w')

                if var_name == "gender":
                    self.form_vars[var_name] = tk.StringVar()
                    combo = ttk.Combobox(field_frame, textvariable=self.form_vars[var_name],
                                       values=["Male", "Female", "Other", "Prefer not to say"])
                    combo.pack(fill=tk.X)
                else:
                    self.form_vars[var_name] = tk.StringVar()
                    ttk.Entry(field_frame, textvariable=self.form_vars[var_name]).pack(fill=tk.X)

            personal_frame.columnconfigure(0, weight=1)
            personal_frame.columnconfigure(1, weight=1)

            # Academic Information Section
            academic_frame = ttk.LabelFrame(scrollable_frame, text="Academic Information", padding=10)
            academic_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            academic_fields = [
                ("Student ID", "student_id"),
                ("Graduation Year*", "graduation_year"),
                ("Degree Earned*", "degree"),
                ("GPA (Optional)", "gpa")
            ]

            for i, (label, var_name) in enumerate(academic_fields):
                row = i // 2
                col = i % 2

                field_frame = ttk.Frame(academic_frame)
                field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

                ttk.Label(field_frame, text=label).pack(anchor='w')
                self.form_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.form_vars[var_name]).pack(fill=tk.X)

            academic_frame.columnconfigure(0, weight=1)
            academic_frame.columnconfigure(1, weight=1)

            # Employment Information Section
            employment_frame = ttk.LabelFrame(scrollable_frame, text="Employment Information", padding=10)
            employment_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            employment_fields = [
                ("Current Employer", "employer"),
                ("Job Title", "job_title"),
                ("Industry", "industry"),
                ("Annual Salary (Optional)", "salary")
            ]

            for i, (label, var_name) in enumerate(employment_fields):
                row = i // 2
                col = i % 2

                field_frame = ttk.Frame(employment_frame)
                field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

                ttk.Label(field_frame, text=label).pack(anchor='w')
                self.form_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.form_vars[var_name]).pack(fill=tk.X)

            employment_frame.columnconfigure(0, weight=1)
            employment_frame.columnconfigure(1, weight=1)

            # Contact Information Section
            contact_frame = ttk.LabelFrame(scrollable_frame, text="Contact Information", padding=10)
            contact_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            contact_fields = [
                ("Address", "address"),
                ("City", "city"),
                ("Country", "country"),
                ("LinkedIn URL", "linkedin")
            ]

            for i, (label, var_name) in enumerate(contact_fields):
                row = i // 2
                col = i % 2

                field_frame = ttk.Frame(contact_frame)
                field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

                ttk.Label(field_frame, text=label).pack(anchor='w')
                self.form_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.form_vars[var_name]).pack(fill=tk.X)

            contact_frame.columnconfigure(0, weight=1)
            contact_frame.columnconfigure(1, weight=1)

            # Additional Information Section
            additional_frame = ttk.LabelFrame(scrollable_frame, text="Additional Information", padding=10)
            additional_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            # Bio text area
            ttk.Label(additional_frame, text="Biography/Description").pack(anchor='w')
            self.form_vars['bio'] = tk.StringVar()
            bio_text = ScrolledText(additional_frame, height=4, wrap=tk.WORD)
            bio_text.pack(fill=tk.X, pady=(0, 10))

            # Skills
            ttk.Label(additional_frame, text="Skills (comma-separated)").pack(anchor='w')
            self.form_vars['skills'] = tk.StringVar()
            ttk.Entry(additional_frame, textvariable=self.form_vars['skills']).pack(fill=tk.X, pady=(0, 10))

            # Achievements
            ttk.Label(additional_frame, text="Notable Achievements").pack(anchor='w')
            self.form_vars['achievements'] = tk.StringVar()
            achievements_text = ScrolledText(additional_frame, height=3, wrap=tk.WORD)
            achievements_text.pack(fill=tk.X)

            # Role Assignments Section
            roles_frame = ttk.LabelFrame(scrollable_frame, text="Role Assignments", padding=10)
            roles_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            self.form_vars['is_donor'] = tk.BooleanVar()
            self.form_vars['is_mentor'] = tk.BooleanVar()
            self.form_vars['is_board_member'] = tk.BooleanVar()
            self.form_vars['is_ambassador'] = tk.BooleanVar()

            ttk.Checkbutton(roles_frame, text="Alumni Donor", variable=self.form_vars['is_donor']).pack(anchor='w')
            ttk.Checkbutton(roles_frame, text="Available as Mentor", variable=self.form_vars['is_mentor']).pack(anchor='w')
            ttk.Checkbutton(roles_frame, text="Board Member", variable=self.form_vars['is_board_member']).pack(anchor='w')
            ttk.Checkbutton(roles_frame, text="Alumni Ambassador", variable=self.form_vars['is_ambassador']).pack(anchor='w')

            # Buttons
            button_frame = ttk.Frame(scrollable_frame)
            button_frame.pack(fill=tk.X, pady=20, padx=20)

            ttk.Button(button_frame, text="Register Alumni",
                      command=self.submit_alumni_registration).pack(side=tk.RIGHT, padx=(10, 0))
            ttk.Button(button_frame, text="Clear Form",
                      command=self.clear_alumni_form).pack(side=tk.RIGHT)

            # Pack the canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        def show_student_validation(self):
            """Show student validation interface"""
            self.clear_content()
            self.update_status("Student Validation")

            # Title
            title_label = ttk.Label(self.content_frame, text="Student Record Validation",
                                   font=('Arial', 16, 'bold'))
            title_label.pack(pady=20)

            # Input frame
            input_frame = ttk.LabelFrame(self.content_frame, text="Validation Inputs", padding=20)
            input_frame.pack(fill=tk.X, padx=20, pady=10)

            # Student ID input
            ttk.Label(input_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
            student_id_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=student_id_var, width=20).grid(row=0, column=1, padx=10, pady=5)

            # Email input
            ttk.Label(input_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=5)
            email_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=email_var, width=30).grid(row=1, column=1, padx=10, pady=5)

            # Validate button
            def validate_student():
                student_id = student_id_var.get().strip()
                email = email_var.get().strip()

                if not student_id and not email:
                    messagebox.showerror("Input Required", "Please enter either Student ID or Email")
                    return

                result = self.validate_student_record(student_id, email)

                if result['valid']:
                    messagebox.showinfo("Validation Result",
                                      f"Valid Student Found!\n\n"
                                      f"Student ID: {result['student_id']}\n"
                                      f"Name: {result['name']}\n"
                                      f"Email: {result['email']}\n"
                                      f"Graduation Date: {result.get('graduation_date', 'N/A')}")
                else:
                    messagebox.showerror("Validation Result",
                                       f"Validation Failed!\n\n"
                                       f"Error: {result['error']}")

            ttk.Button(input_frame, text="Validate Student",
                      command=validate_student).grid(row=2, column=0, columnspan=2, pady=20)

        def show_update_alumni(self):
            """Show alumni update interface"""
            self.clear_content()
            self.update_status("Alumni Update Interface")

            # Implementation would be similar to registration form but with pre-filled data
            ttk.Label(self.content_frame, text="Update Alumni Record",
                     font=('Arial', 16, 'bold')).pack(pady=20)

            # Alumni selection
            selection_frame = ttk.LabelFrame(self.content_frame, text="Select Alumni to Update", padding=10)
            selection_frame.pack(fill=tk.X, pady=(0, 20), padx=20)

            ttk.Label(selection_frame, text="Alumni ID:").pack(side=tk.LEFT, padx=(0, 10))
            alumni_id_var = tk.StringVar()
            ttk.Entry(selection_frame, textvariable=alumni_id_var, width=15).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(selection_frame, text="Load Alumni Data",
                      command=lambda: self.load_alumni_for_update(alumni_id_var.get())).pack(side=tk.LEFT)

            # Update form would go here (similar to registration form)
            update_info = ttk.Label(self.content_frame, text="Enter Alumni ID above to load update form",
                                   font=('Arial', 12))
            update_info.pack(pady=50)

        def show_view_alumni(self):
            """Show alumni records viewer"""
            self.clear_content()
            self.update_status("Viewing Alumni Records")

            # Title and search
            title_frame = ttk.Frame(self.content_frame)
            title_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(title_frame, text="Alumni Records",
                     font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

            search_frame = ttk.Frame(title_frame)
            search_frame.pack(side=tk.RIGHT)

            ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
            search_var = tk.StringVar()
            search_entry = ttk.Entry(search_frame, textvariable=search_var, width=20)
            search_entry.pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(search_frame, text="🔍", command=lambda: self.search_alumni(search_var.get())).pack(side=tk.LEFT)

            # Alumni table
            table_frame = ttk.Frame(self.content_frame)
            table_frame.pack(fill=tk.BOTH, expand=True)

            # Create treeview
            columns = ('ID', 'Name', 'Graduation Year', 'Degree', 'Employer', 'Email', 'Status')
            self.alumni_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            # Configure columns
            for col in columns:
                self.alumni_tree.heading(col, text=col)
                self.alumni_tree.column(col, width=120)

            # Add scrollbar
            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.alumni_tree.yview)
            self.alumni_tree.configure(yscrollcommand=scrollbar_y.set)

            scrollbar_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.alumni_tree.xview)
            self.alumni_tree.configure(xscrollcommand=scrollbar_x.set)

            # Pack treeview and scrollbars
            self.alumni_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
            scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

            # Load alumni data
            self.load_alumni_data()

            # Buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, pady=10)

            ttk.Button(button_frame, text="View Details",
                      command=self.view_alumni_details).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Edit Alumni",
                      command=self.edit_selected_alumni).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Refresh",
                      command=self.load_alumni_data).pack(side=tk.LEFT)

        def submit_alumni_registration(self):
            """Submit the alumni registration form"""
            try:
                # Validate required fields
                required_fields = ['first_name', 'last_name', 'email', 'graduation_year', 'degree']
                for field in required_fields:
                    if not self.form_vars[field].get().strip():
                        messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                        return

                # Get form data
                first_name = self.form_vars['first_name'].get().strip()
                last_name = self.form_vars['last_name'].get().strip()
                email = self.form_vars['email'].get().strip()
                student_id = self.form_vars['student_id'].get().strip()

                # Validate student record
                if student_id or email:
                    validation_result = self.validate_student_record(student_id, email)
                    if not validation_result['valid']:
                        messagebox.showerror("Validation Error",
                                           f"Student validation failed: {validation_result['error']}\n\n"
                                           "You must be a valid student to register as alumni.")
                        return

                    # Check finance status
                    finance_status = self.check_finance_status(validation_result['student_id'], email)
                    if finance_status['has_debt']:
                        result = messagebox.askyesno("Outstanding Balance",
                                                   f"You have an outstanding balance of ${finance_status['total_owed']:.2f}.\n\n"
                                                   "Do you want to view your finance status before proceeding with registration?")
                        if result:
                            self.show_finance_status_dialog(finance_status, f"{first_name} {last_name}")
                            return

                # Process registration (call backend function)
                try:
                    # Here you would normally call the backend registration function
                    # For now, we'll simulate success
                    registration_successful = True

                    if registration_successful:
                        # Send confirmation email
                        self.send_alumni_registration_confirmation(email, f"{first_name} {last_name}")

                        messagebox.showinfo("Success", "Alumni registered successfully!\nConfirmation email sent.")
                        self.update_status("Alumni registration completed")

                        # Clear the form
                        self.clear_alumni_form()
                    else:
                        messagebox.showerror("Error", "Registration failed. Please try again.")

                except sqlite3.Error as reg_error:
                    messagebox.showerror("Registration Error", f"Database error during registration: {str(reg_error)}")

            except (ValueError, KeyError) as e:
                messagebox.showerror("Validation Error", f"Invalid input data: {str(e)}")
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to register alumni: {str(e)}")

        def validate_student_record(self, student_id, email):
            """Validate if user is a valid student in the database"""
            try:
                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Check if student exists in students table
                cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name, s.email, s.graduation_date
                    FROM students s
                    WHERE s.student_id = ? OR s.email = ?
                ''', (student_id, email))

                student_record = cursor.fetchone()
                conn.close()

                if student_record:
                    return {
                        'valid': True,
                        'student_id': student_record[0],
                        'name': f"{student_record[1]} {student_record[2]}",
                        'email': student_record[3],
                        'graduation_date': student_record[4]
                    }
                else:
                    return {'valid': False, 'error': 'Student record not found'}

            except sqlite3.Error as e:
                return {'valid': False, 'error': f'Database error: {e}'}

        def view_alumni_details(self):
            """View detailed information for selected alumni"""
            selection = self.alumni_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an alumni record to view details.")
                return

            item = self.alumni_tree.item(selection[0])
            alumni_data = item['values']

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Alumni Details - {alumni_data[1]}")
            details_window.geometry("600x500")

            # Create scrollable text
            text_widget = ScrolledText(details_window, wrap=tk.WORD, padx=10, pady=10)
            text_widget.pack(fill=tk.BOTH, expand=True)

            # Display alumni details
            details_text = f"""
    ALUMNI DETAILS
    {'='*50}

    Personal Information:
    • Alumni ID: {alumni_data[0]}
    • Name: {alumni_data[1]}
    • Email: {alumni_data[5]}

    Academic Information:
    • Graduation Year: {alumni_data[2]}
    • Degree: {alumni_data[3]}

    Employment Information:
    • Current Employer: {alumni_data[4]}
    • Status: {alumni_data[6]}

    Registration Date: {datetime.now().strftime('%Y-%m-%d')}
    Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """

            text_widget.insert(tk.END, details_text)
            text_widget.config(state=tk.DISABLED)

