"""Scholarship management: creation, awarding, browsing, and reporting."""

import sys
import io
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from education_system.post_18.university_system.core.i18n import get_text as _
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.finance.scholarships.scholarship_programs import scholarship_distribution_summary, scholarship_utilization_analysis
from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.scholarships import student_scholarship_report


class ScholarshipsMixin:
    """Scholarships tab, award workflow, and scholarship reports."""

    def create_scholarships_tab(self):
        """Create scholarships management tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['scholarships'] = tab

        main_frame = ttk.Frame(tab, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Control buttons
        control_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.scholarship_management_frame"), padding=15)
        control_frame.pack(fill='x', pady=(0, 20))

        buttons = [
            (_("finance_gui.settings.view_scholarships_btn"), self.gui_view_available_scholarships),
            (_("finance_gui.settings.create_scholarship_btn"), self.gui_create_new_scholarship),
            (_("finance_gui.settings.award_scholarship_btn"), self.gui_award_scholarship_to_student),
            (_("finance_gui.settings.scholarship_reports_btn"), self.gui_scholarship_reports),
        ]

        for i, (text, command) in enumerate(buttons):
            ttk.Button(control_frame, text=text, command=command, width=25).grid(row=i//2, column=i%2, padx=10, pady=5)

        # Scholarships display
        display_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.available_scholarships_frame"), padding=15)
        display_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Name', 'Amount', 'Academic Year', 'Criteria', 'Deadline', 'Status')
        self.scholarships_tree = ttk.Treeview(display_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.scholarships_tree.heading(col, text=col)
            width = 150 if col in ['Name', 'Criteria'] else 100
            self.scholarships_tree.column(col, width=width, anchor='center')

        # Scrollbars
        scholar_v_scroll = ttk.Scrollbar(display_frame, orient='vertical', command=self.scholarships_tree.yview)
        scholar_h_scroll = ttk.Scrollbar(display_frame, orient='horizontal', command=self.scholarships_tree.xview)
        self.scholarships_tree.configure(yscrollcommand=scholar_v_scroll.set, xscrollcommand=scholar_h_scroll.set)

        self.scholarships_tree.pack(side='left', fill='both', expand=True)
        scholar_v_scroll.pack(side='right', fill='y')
        scholar_h_scroll.pack(side='bottom', fill='x')

        self.refresh_scholarships()


    def refresh_scholarships(self):
        """Refresh scholarships display"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT scholarship_id, scholarship_name, amount, academic_year,
                   criteria, deadline,
                   CASE WHEN is_active = 1 THEN 'Active' ELSE 'Inactive' END as status
            FROM scholarships
            WHERE is_active = 1
            ORDER BY scholarship_name
            LIMIT 50
            ''')

            scholarships = cursor.fetchall()

            # Clear existing items if scholarships_tree exists
            if hasattr(self, 'scholarships_tree'):
                for item in self.scholarships_tree.get_children():
                    self.scholarships_tree.delete(item)

                # Add scholarship data
                for scholarship in scholarships:
                    scholarship_id, name, amount, year, criteria, deadline, status = scholarship
                    criteria_short = criteria[:30] + "..." if len(criteria) > 30 else criteria

                    self.scholarships_tree.insert('', 'end', values=(
                        scholarship_id, name, f"\u00a3{amount:.2f}", year,
                        criteria_short, deadline, status
                    ))

            conn.close()

        except Exception as e:
            print(f"Error refreshing scholarships: {e}")


    def gui_create_new_scholarship(self):
        """GUI wrapper for creating new scholarship"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.create_scholarship_title"))
        dialog.geometry("600x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Scholarship details form
        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.scholarship_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Scholarship name
        ttk.Label(form_frame, text=_("finance_gui.settings.scholarship_name_label"), font=('Arial', 12)).pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, font=('Arial', 12), width=50).pack(anchor='w', pady=5)

        # Description
        ttk.Label(form_frame, text=_("finance_gui.settings.description_form_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        desc_text = tk.Text(form_frame, height=4, width=60, font=('Arial', 10))
        desc_text.pack(anchor='w', pady=5)

        # Amount
        ttk.Label(form_frame, text=_("finance_gui.settings.scholarship_amount_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        # Academic year
        ttk.Label(form_frame, text=_("finance_gui.settings.academic_year_form_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        year_var = tk.StringVar(value="2024-2025")
        ttk.Entry(form_frame, textvariable=year_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        # Eligibility criteria
        ttk.Label(form_frame, text=_("finance_gui.settings.eligibility_criteria_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        criteria_text = tk.Text(form_frame, height=3, width=60, font=('Arial', 10))
        criteria_text.pack(anchor='w', pady=5)

        # Deadline
        ttk.Label(form_frame, text=_("finance_gui.settings.deadline_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))
        deadline_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=deadline_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        def create_scholarship():
            try:
                name = name_var.get().strip()
                description = desc_text.get("1.0", tk.END).strip()
                amount = float(amount_var.get())
                academic_year = year_var.get().strip()
                criteria = criteria_text.get("1.0", tk.END).strip()
                deadline = deadline_var.get().strip()

                if not all([name, description, amount > 0, academic_year, criteria, deadline]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.all_fields_required_scholarship"))
                    return

                # Call the original function indirectly
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO scholarships
                (scholarship_name, description, amount, academic_year, criteria, deadline, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, description, amount, academic_year, criteria, deadline, now, now))

                scholarship_id = cursor.lastrowid
                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.scholarship_created_msg", scholarship_id=scholarship_id))
                dialog.destroy()
                self.refresh_scholarships()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_amount_entered"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_create_scholarship", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("finance_gui.settings.create_scholarship_form_btn"), command=create_scholarship).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.settings.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)


    def gui_award_scholarship_to_student(self):
        """GUI wrapper for awarding scholarship to student"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.award_scholarship_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student and scholarship selection
        selection_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.award_details_frame"), padding=20)
        selection_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(selection_frame, text=_("finance_gui.settings.student_id_award_label"), font=('Arial', 12)).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(selection_frame, textvariable=student_id_var, font=('Arial', 12), width=20).pack(anchor='w', pady=5)

        # Scholarship selection
        ttk.Label(selection_frame, text=_("finance_gui.settings.available_scholarships_combo_label"), font=('Arial', 12)).pack(anchor='w', pady=(15, 5))

        # Load available scholarships
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT scholarship_id, scholarship_name, amount, academic_year
            FROM scholarships
            WHERE is_active = 1 AND deadline >= date('now')
            ORDER BY scholarship_name
            ''')
            scholarships = cursor.fetchall()
            conn.close()
        except Exception:
            scholarships = []

        scholarship_var = tk.StringVar()
        scholarship_combo = ttk.Combobox(selection_frame, textvariable=scholarship_var,
                                       state='readonly', width=60, font=('Arial', 12))

        scholarship_values = []
        self.scholarship_data = {}

        for scholarship in scholarships:
            scholarship_id, name, amount, year = scholarship
            display_text = f"{name} - \u00a3{amount:.2f} ({year})"
            scholarship_values.append(display_text)
            self.scholarship_data[display_text] = scholarship

        scholarship_combo['values'] = scholarship_values
        scholarship_combo.pack(anchor='w', pady=5)

        def award_scholarship():
            try:
                student_id = student_id_var.get().strip()
                selected_scholarship = scholarship_var.get()

                if not student_id or not selected_scholarship:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.student_id_and_scholarship_required"))
                    return

                if selected_scholarship not in self.scholarship_data:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_scholarship_selection"))
                    return

                scholarship_info = self.scholarship_data[selected_scholarship]
                scholarship_id, name, amount, year = scholarship_info

                # Check if student exists
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.student_not_found", student_id=student_id))
                    conn.close()
                    return

                # Check if already awarded
                cursor.execute('''
                SELECT COUNT(*) FROM student_scholarships
                WHERE student_id = ? AND scholarship_id = ?
                ''', (student_id, scholarship_id))

                if cursor.fetchone()[0] > 0:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.student_already_awarded"))
                    conn.close()
                    return

                # Award the scholarship
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                award_date = datetime.now().strftime('%Y-%m-%d')

                cursor.execute('''
                INSERT INTO student_scholarships
                (student_id, scholarship_id, award_date, amount_awarded, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'awarded', ?, ?)
                ''', (student_id, scholarship_id, award_date, amount, now, now))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.settings.success_title"),
                                   _("finance_gui.settings.scholarship_awarded_msg", student_id=student_id, name=name, amount=f"\u00a3{amount:.2f}"))

                dialog.destroy()
                self.update_status(_("finance_gui.settings.scholarship_awarded_status", student_id=student_id))

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_award_scholarship", error=str(e)))

        ttk.Button(selection_frame, text=_("finance_gui.settings.award_scholarship_form_btn"), command=award_scholarship).pack(pady=20)
        ttk.Button(selection_frame, text=_("finance_gui.settings.btn_cancel"), command=dialog.destroy).pack(pady=5)


    def gui_scholarship_reports(self):
        """GUI wrapper for scholarship reports"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.scholarship_reports_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Report selection
        selection_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.report_options_frame"), padding=15)
        selection_frame.pack(fill='x', padx=20, pady=10)

        report_type_var = tk.StringVar(value="distribution")

        ttk.Radiobutton(selection_frame, text=_("finance_gui.settings.distribution_summary_radio"),
                       variable=report_type_var, value="distribution").pack(anchor='w', pady=2)
        ttk.Radiobutton(selection_frame, text=_("finance_gui.settings.student_scholarship_report_radio"),
                       variable=report_type_var, value="student").pack(anchor='w', pady=2)
        ttk.Radiobutton(selection_frame, text=_("finance_gui.settings.utilization_analysis_radio"),
                       variable=report_type_var, value="utilization").pack(anchor='w', pady=2)

        # Report output
        output_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.report_output_frame"), padding=15)
        output_frame.pack(fill='both', expand=True, padx=20, pady=10)

        report_output = ScrolledText(output_frame, height=20, width=80, font=('Courier', 10))
        report_output.pack(fill='both', expand=True)

        def generate_scholarship_report():
            try:
                report_type = report_type_var.get()

                old_stdout = sys.stdout
                sys.stdout = mystdout = io.StringIO()

                if report_type == "distribution":
                    scholarship_distribution_summary()
                elif report_type == "student":
                    student_scholarship_report()
                elif report_type == "utilization":
                    scholarship_utilization_analysis()

                output = mystdout.getvalue()
                sys.stdout = old_stdout

                report_output.delete('1.0', tk.END)
                report_output.insert('1.0', output)

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_generate_report", error=str(e)))

        ttk.Button(selection_frame, text=_("finance_gui.settings.generate_report_btn"), command=generate_scholarship_report).pack(pady=10)


    def gui_manage_scholarships(self):
        """Switch to scholarships tab"""
        self.show_tab('scholarships')


    def gui_view_available_scholarships(self):
        """View available scholarships"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.available_scholarships_title"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Scholarships display
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Filter frame
        filter_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.filter_options_frame"), padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text=_("finance_gui.settings.filter_academic_year_label")).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        year_var = tk.StringVar(value="2024-2025")
        ttk.Entry(filter_frame, textvariable=year_var, width=12).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(filter_frame, text=_("finance_gui.settings.filter_status_label")).grid(row=0, column=2, padx=5, pady=5, sticky='e')
        status_var = tk.StringVar(value="active")
        status_combo = ttk.Combobox(filter_frame, textvariable=status_var,
                                   values=["active", "inactive", "all"], state='readonly', width=10)
        status_combo.grid(row=0, column=3, padx=5, pady=5)

        def load_scholarships():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                query = '''
                SELECT scholarship_id, scholarship_name, description, amount,
                       academic_year, criteria, deadline,
                       CASE WHEN is_active = 1 THEN 'Active' ELSE 'Inactive' END as status
                FROM scholarships
                WHERE 1=1
                '''
                params = []

                if year_var.get():
                    query += ' AND academic_year = ?'
                    params.append(year_var.get())

                if status_var.get() != 'all':
                    query += ' AND is_active = ?'
                    params.append(1 if status_var.get() == 'active' else 0)

                query += ' ORDER BY scholarship_name'

                cursor.execute(query, params)
                scholarships = cursor.fetchall()

                # Clear existing items
                for item in scholarship_tree.get_children():
                    scholarship_tree.delete(item)

                # Add scholarship data
                for scholarship in scholarships:
                    scholarship_id, name, desc, amount, year, criteria, deadline, status = scholarship
                    display_data = (
                        scholarship_id, name, f"\u00a3{amount:.2f}", year,
                        criteria[:30] + "..." if len(criteria) > 30 else criteria,
                        deadline, status
                    )
                    scholarship_tree.insert('', 'end', values=display_data)

                conn.close()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_load_scholarships", error=str(e)))

        ttk.Button(filter_frame, text=_("finance_gui.settings.load_scholarships_btn"), command=load_scholarships).grid(row=0, column=4, padx=10, pady=5)

        # Scholarships table
        columns = ('ID', 'Name', 'Amount', 'Year', 'Criteria', 'Deadline', 'Status')
        scholarship_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

        for col in columns:
            scholarship_tree.heading(col, text=col)
            width = 200 if col in ['Name', 'Criteria'] else 100
            scholarship_tree.column(col, width=width, anchor='center')

        # Scrollbars
        v_scroll = ttk.Scrollbar(main_frame, orient='vertical', command=scholarship_tree.yview)
        h_scroll = ttk.Scrollbar(main_frame, orient='horizontal', command=scholarship_tree.xview)
        scholarship_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        scholarship_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill='x')

        # Load initial data
        load_scholarships()
