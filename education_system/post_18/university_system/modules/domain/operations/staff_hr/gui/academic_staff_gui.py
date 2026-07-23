"""
Academic Staff Management GUI

Features:
- Teaching Portfolio - Teaching philosophy, courses, innovations
- Research Output - Publications, citations, h-index tracking
- Supervisions - PhD/Masters student supervision management
- External Examiners - Examiner appointments and assignments
- Peer Observations - Classroom observation records
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
from datetime import datetime
import json

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.core.activity_logger import log_activity

try:
    from education_system.post_18.university_system.infrastructure.database.schemas.staff_hr_schemas_all import (
        get_program_types, get_observation_types
    )
except ImportError:
    get_program_types = lambda: ['phd', 'masters', 'undergraduate']
    get_observation_types = lambda: ['formal', 'informal', 'peer']


class AcademicStaffGUI:
    """Academic Staff Management GUI with multiple tabs."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook=None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None

        if not self.current_user:
            return

        if parent_notebook:
            self.tab = ttk.Frame(parent_notebook)
            parent_notebook.add(self.tab, text="Academic Staff")
            self._create_content(self.tab)
        else:
            self._create_standalone_window()

    def _create_standalone_window(self):
        """Create standalone window when not embedded."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Academic Staff Management")
        self.window.geometry("1200x800")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._create_content(self.window)

    def _create_content(self, parent):
        """Create the main content with notebook tabs."""
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_teaching_portfolio_tab()
        self._create_research_output_tab()
        self._create_supervisions_tab()
        self._create_examiners_tab()
        self._create_peer_observations_tab()

    # ================================================================
    # TEACHING PORTFOLIO TAB
    # ================================================================

    def _create_teaching_portfolio_tab(self):
        """Create Teaching Portfolio tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Teaching Portfolio")

        # Scrollable form
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        form_frame = ttk.Frame(canvas)

        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Teaching Philosophy
        philosophy_frame = ttk.LabelFrame(form_frame, text="Teaching Philosophy", padding=10)
        philosophy_frame.pack(fill=tk.X, padx=10, pady=5)

        self.philosophy_text = tk.Text(philosophy_frame, height=5, width=80)
        self.philosophy_text.pack(fill=tk.X, pady=5)

        # Teaching Interests
        interests_frame = ttk.LabelFrame(form_frame, text="Teaching Interests", padding=10)
        interests_frame.pack(fill=tk.X, padx=10, pady=5)

        self.interests_text = tk.Text(interests_frame, height=3, width=80)
        self.interests_text.pack(fill=tk.X, pady=5)

        # Courses Taught
        courses_frame = ttk.LabelFrame(form_frame, text="Courses Taught", padding=10)
        courses_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(courses_frame, text="Enter courses (one per line):").pack(anchor=tk.W)
        self.courses_text = tk.Text(courses_frame, height=5, width=80)
        self.courses_text.pack(fill=tk.X, pady=5)

        # Teaching Innovations
        innovations_frame = ttk.LabelFrame(form_frame, text="Teaching Innovations & Methods", padding=10)
        innovations_frame.pack(fill=tk.X, padx=10, pady=5)

        self.innovations_text = tk.Text(innovations_frame, height=4, width=80)
        self.innovations_text.pack(fill=tk.X, pady=5)

        # Awards & Recognition
        awards_frame = ttk.LabelFrame(form_frame, text="Awards & Recognition", padding=10)
        awards_frame.pack(fill=tk.X, padx=10, pady=5)

        self.awards_text = tk.Text(awards_frame, height=3, width=80)
        self.awards_text.pack(fill=tk.X, pady=5)

        # Professional Development
        pd_frame = ttk.LabelFrame(form_frame, text="Professional Development", padding=10)
        pd_frame.pack(fill=tk.X, padx=10, pady=5)

        self.pd_text = tk.Text(pd_frame, height=3, width=80)
        self.pd_text.pack(fill=tk.X, pady=5)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="Save Portfolio", command=self._save_teaching_portfolio).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_teaching_portfolio).pack(side=tk.LEFT, padx=5)

        self._load_teaching_portfolio()

    def _load_teaching_portfolio(self):
        """Load teaching portfolio data."""
        user_id = self.current_user.get('id') or self.current_user.get('username')

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT teaching_philosophy, teaching_interests, courses_taught,
                           teaching_innovations, awards_recognition, professional_development
                    FROM teaching_portfolios WHERE user_id = ?
                ''', (user_id,))
                row = cursor.fetchone()

                if row:
                    self.philosophy_text.delete('1.0', tk.END)
                    self.philosophy_text.insert('1.0', row[0] or '')
                    self.interests_text.delete('1.0', tk.END)
                    self.interests_text.insert('1.0', row[1] or '')
                    self.courses_text.delete('1.0', tk.END)
                    self.courses_text.insert('1.0', row[2] or '')
                    self.innovations_text.delete('1.0', tk.END)
                    self.innovations_text.insert('1.0', row[3] or '')
                    self.awards_text.delete('1.0', tk.END)
                    self.awards_text.insert('1.0', row[4] or '')
                    self.pd_text.delete('1.0', tk.END)
                    self.pd_text.insert('1.0', row[5] or '')
        except Exception as e:
            print(f"Error loading teaching portfolio: {e}")

    def _save_teaching_portfolio(self):
        """Save teaching portfolio."""
        user_id = self.current_user.get('id') or self.current_user.get('username')

        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT portfolio_id FROM teaching_portfolios WHERE user_id = ?', (user_id,))
                exists = cursor.fetchone()

                data = (
                    self.philosophy_text.get('1.0', tk.END).strip(),
                    self.interests_text.get('1.0', tk.END).strip(),
                    self.courses_text.get('1.0', tk.END).strip(),
                    self.innovations_text.get('1.0', tk.END).strip(),
                    self.awards_text.get('1.0', tk.END).strip(),
                    self.pd_text.get('1.0', tk.END).strip()
                )

                if exists:
                    cursor.execute('''
                        UPDATE teaching_portfolios SET
                            teaching_philosophy = ?, teaching_interests = ?,
                            courses_taught = ?, teaching_innovations = ?,
                            awards_recognition = ?, professional_development = ?,
                            last_updated = ?
                        WHERE user_id = ?
                    ''', data + (datetime.now().isoformat(), user_id))
                else:
                    cursor.execute('''
                        INSERT INTO teaching_portfolios (
                            user_id, teaching_philosophy, teaching_interests,
                            courses_taught, teaching_innovations,
                            awards_recognition, professional_development
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (user_id,) + data)

                conn.commit()
                log_activity('update', 'teaching_portfolio', user_id=user_id)
                messagebox.showinfo("Success", "Teaching portfolio saved successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save portfolio: {e}")

    # ================================================================
    # RESEARCH OUTPUT TAB
    # ================================================================

    def _create_research_output_tab(self):
        """Create Research Output tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Research Output")

        # Profile frame
        profile_frame = ttk.LabelFrame(tab, text="Research Profile", padding=10)
        profile_frame.pack(fill=tk.X, padx=10, pady=5)

        # Metrics
        metrics_frame = ttk.Frame(profile_frame)
        metrics_frame.pack(fill=tk.X, pady=5)

        ttk.Label(metrics_frame, text="h-Index:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.h_index_var = tk.StringVar(value="0")
        ttk.Entry(metrics_frame, textvariable=self.h_index_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(metrics_frame, text="Total Citations:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.citations_var = tk.StringVar(value="0")
        ttk.Entry(metrics_frame, textvariable=self.citations_var, width=10).grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(metrics_frame, text="Total Publications:").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.publications_var = tk.StringVar(value="0")
        ttk.Entry(metrics_frame, textvariable=self.publications_var, width=10).grid(row=0, column=5, sticky=tk.W, padx=5)

        # IDs frame
        ids_frame = ttk.Frame(profile_frame)
        ids_frame.pack(fill=tk.X, pady=5)

        ttk.Label(ids_frame, text="ORCID:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.orcid_var = tk.StringVar()
        ttk.Entry(ids_frame, textvariable=self.orcid_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(ids_frame, text="Google Scholar:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.scholar_var = tk.StringVar()
        ttk.Entry(ids_frame, textvariable=self.scholar_var, width=25).grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(ids_frame, text="Scopus ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.scopus_var = tk.StringVar()
        ttk.Entry(ids_frame, textvariable=self.scopus_var, width=25).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(ids_frame, text="ResearchGate:").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.rg_var = tk.StringVar()
        ttk.Entry(ids_frame, textvariable=self.rg_var, width=35).grid(row=1, column=3, sticky=tk.W, padx=5)

        # Research Interests
        interests_frame = ttk.LabelFrame(tab, text="Research Interests", padding=10)
        interests_frame.pack(fill=tk.X, padx=10, pady=5)

        self.research_interests_text = tk.Text(interests_frame, height=4, width=80)
        self.research_interests_text.pack(fill=tk.X, pady=5)

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="Save Research Profile", command=self._save_research_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_research_profile).pack(side=tk.LEFT, padx=5)

        # Summary section
        summary_frame = ttk.LabelFrame(tab, text="Publication Summary", padding=10)
        summary_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.research_summary = tk.Text(summary_frame, height=10, state=tk.DISABLED)
        self.research_summary.pack(fill=tk.BOTH, expand=True)

        self._load_research_profile()

    def _load_research_profile(self):
        """Load research profile data."""
        user_id = self.current_user.get('id') or self.current_user.get('username')

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT research_interests, h_index, total_citations,
                           total_publications, orcid_id, google_scholar_id,
                           researchgate_url, scopus_id
                    FROM research_profiles WHERE user_id = ?
                ''', (user_id,))
                row = cursor.fetchone()

                if row:
                    self.research_interests_text.delete('1.0', tk.END)
                    self.research_interests_text.insert('1.0', row[0] or '')
                    self.h_index_var.set(str(row[1] or 0))
                    self.citations_var.set(str(row[2] or 0))
                    self.publications_var.set(str(row[3] or 0))
                    self.orcid_var.set(row[4] or '')
                    self.scholar_var.set(row[5] or '')
                    self.rg_var.set(row[6] or '')
                    self.scopus_var.set(row[7] or '')

                # Load publications summary from research_publications if exists
                cursor.execute('''
                    SELECT title, publication_type, publication_date, citation_count
                    FROM research_publications
                    WHERE project_id IN (
                        SELECT project_id FROM research_projects
                        WHERE principal_investigator_id = ?
                    )
                    ORDER BY publication_date DESC LIMIT 10
                ''', (user_id,))
                pubs = cursor.fetchall()

                self.research_summary.config(state=tk.NORMAL)
                self.research_summary.delete('1.0', tk.END)
                if pubs:
                    for pub in pubs:
                        self.research_summary.insert(tk.END, f"- {pub[0]}\n")
                        self.research_summary.insert(tk.END, f"  Type: {pub[1]}, Date: {pub[2]}, Citations: {pub[3]}\n\n")
                else:
                    self.research_summary.insert(tk.END, "No publications found in the system.\n")
                    self.research_summary.insert(tk.END, "Publications may be tracked in the Research module.")
                self.research_summary.config(state=tk.DISABLED)

        except Exception as e:
            print(f"Error loading research profile: {e}")

    def _save_research_profile(self):
        """Save research profile."""
        user_id = self.current_user.get('id') or self.current_user.get('username')

        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT profile_id FROM research_profiles WHERE user_id = ?', (user_id,))
                exists = cursor.fetchone()

                if exists:
                    cursor.execute('''
                        UPDATE research_profiles SET
                            research_interests = ?, h_index = ?, total_citations = ?,
                            total_publications = ?, orcid_id = ?, google_scholar_id = ?,
                            researchgate_url = ?, scopus_id = ?, last_updated = ?
                        WHERE user_id = ?
                    ''', (
                        self.research_interests_text.get('1.0', tk.END).strip(),
                        int(self.h_index_var.get() or 0),
                        int(self.citations_var.get() or 0),
                        int(self.publications_var.get() or 0),
                        self.orcid_var.get(), self.scholar_var.get(),
                        self.rg_var.get(), self.scopus_var.get(),
                        datetime.now().isoformat(), user_id
                    ))
                else:
                    cursor.execute('''
                        INSERT INTO research_profiles (
                            user_id, research_interests, h_index, total_citations,
                            total_publications, orcid_id, google_scholar_id,
                            researchgate_url, scopus_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id, self.research_interests_text.get('1.0', tk.END).strip(),
                        int(self.h_index_var.get() or 0),
                        int(self.citations_var.get() or 0),
                        int(self.publications_var.get() or 0),
                        self.orcid_var.get(), self.scholar_var.get(),
                        self.rg_var.get(), self.scopus_var.get()
                    ))

                conn.commit()
                log_activity('update', 'research_profile', user_id=user_id)
                messagebox.showinfo("Success", "Research profile saved successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save profile: {e}")

    # ================================================================
    # SUPERVISIONS TAB
    # ================================================================

    def _create_supervisions_tab(self):
        """Create Student Supervisions tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Supervisions")

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="Add Supervision", command=self._add_supervision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit Supervision", command=self._edit_supervision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Update Progress", command=self._update_supervision_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_supervisions).pack(side=tk.LEFT, padx=5)

        # Filter frame
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.supervision_status_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self.supervision_status_var,
                     values=["All", "active", "completed", "withdrawn"],
                     width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Filter", command=self._load_supervisions).pack(side=tk.LEFT, padx=5)

        # Supervisions list
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('ID', 'Student', 'Program', 'Thesis Title', 'Role', 'Start', 'Expected End', 'Status')
        self.supervisions_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.supervisions_tree.heading(col, text=col)
            self.supervisions_tree.column(col, width=100)

        self.supervisions_tree.column('ID', width=50)
        self.supervisions_tree.column('Thesis Title', width=200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.supervisions_tree.yview)
        self.supervisions_tree.configure(yscrollcommand=scrollbar.set)

        self.supervisions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.supervisions_tree.tag_configure('active', background='#90EE90')
        self.supervisions_tree.tag_configure('completed', background='#87CEEB')
        self.supervisions_tree.tag_configure('withdrawn', background='#D3D3D3')

        self._load_supervisions()

    def _load_supervisions(self):
        """Load supervisions data."""
        user_id = self.current_user.get('id') or self.current_user.get('username')
        status_filter = self.supervision_status_var.get()

        self.supervisions_tree.delete(*self.supervisions_tree.get_children())

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT supervision_id, student_name, program_type, thesis_title,
                           supervision_role, start_date, expected_end_date, status
                    FROM student_supervisions
                    WHERE supervisor_id = ?
                '''
                params = [user_id]

                if status_filter != "All":
                    query += ' AND status = ?'
                    params.append(status_filter)

                query += ' ORDER BY start_date DESC'
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    status = row[7] or 'active'
                    self.supervisions_tree.insert('', 'end', values=row, tags=(status,))
        except Exception as e:
            print(f"Error loading supervisions: {e}")

    def _add_supervision(self):
        """Add new supervision."""
        self._supervision_dialog()

    def _edit_supervision(self):
        """Edit selected supervision."""
        selection = self.supervisions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a supervision to edit")
            return

        item = self.supervisions_tree.item(selection[0])
        supervision_id = item['values'][0]
        self._supervision_dialog(supervision_id)

    def _supervision_dialog(self, supervision_id=None):
        """Show supervision add/edit dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Supervision" if supervision_id else "Add Supervision")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Student Name:").pack(pady=5)
        student_name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=student_name_var, width=40).pack(pady=5)

        ttk.Label(dialog, text="Student ID (optional):").pack(pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=student_id_var, width=20).pack(pady=5)

        ttk.Label(dialog, text="Program Type:").pack(pady=5)
        program_var = tk.StringVar()
        ttk.Combobox(dialog, textvariable=program_var, values=get_program_types(), width=20).pack(pady=5)

        ttk.Label(dialog, text="Thesis Title:").pack(pady=5)
        thesis_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=thesis_var, width=50).pack(pady=5)

        ttk.Label(dialog, text="Supervision Role:").pack(pady=5)
        role_var = tk.StringVar(value="primary")
        ttk.Combobox(dialog, textvariable=role_var,
                     values=['primary', 'secondary', 'advisor', 'co-supervisor'],
                     width=20).pack(pady=5)

        ttk.Label(dialog, text="Start Date (YYYY-MM-DD):").pack(pady=5)
        start_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=start_var, width=15).pack(pady=5)

        ttk.Label(dialog, text="Expected End Date (YYYY-MM-DD):").pack(pady=5)
        end_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=end_var, width=15).pack(pady=5)

        ttk.Label(dialog, text="Status:").pack(pady=5)
        status_var = tk.StringVar(value="active")
        ttk.Combobox(dialog, textvariable=status_var,
                     values=['active', 'completed', 'withdrawn'],
                     width=15).pack(pady=5)

        # Load existing data if editing
        if supervision_id:
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT student_name, student_id, program_type, thesis_title,
                               supervision_role, start_date, expected_end_date, status
                        FROM student_supervisions WHERE supervision_id = ?
                    ''', (supervision_id,))
                    row = cursor.fetchone()
                    if row:
                        student_name_var.set(row[0] or '')
                        student_id_var.set(row[1] or '')
                        program_var.set(row[2] or '')
                        thesis_var.set(row[3] or '')
                        role_var.set(row[4] or 'primary')
                        start_var.set(row[5] or '')
                        end_var.set(row[6] or '')
                        status_var.set(row[7] or 'active')
            except Exception as e:
                print(f"Error loading supervision: {e}")

        def save():
            user_id = self.current_user.get('id') or self.current_user.get('username')

            if not student_name_var.get():
                messagebox.showwarning("Warning", "Please enter student name")
                return

            try:
                with transaction() as conn:
                    if supervision_id:
                        conn.execute('''
                            UPDATE student_supervisions SET
                                student_name = ?, student_id = ?, program_type = ?,
                                thesis_title = ?, supervision_role = ?, start_date = ?,
                                expected_end_date = ?, status = ?, updated_at = ?
                            WHERE supervision_id = ?
                        ''', (
                            student_name_var.get(), student_id_var.get(), program_var.get(),
                            thesis_var.get(), role_var.get(), start_var.get() or None,
                            end_var.get() or None, status_var.get(),
                            datetime.now().isoformat(), supervision_id
                        ))
                    else:
                        conn.execute('''
                            INSERT INTO student_supervisions (
                                supervisor_id, student_name, student_id, program_type,
                                thesis_title, supervision_role, start_date,
                                expected_end_date, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            user_id, student_name_var.get(), student_id_var.get(),
                            program_var.get(), thesis_var.get(), role_var.get(),
                            start_var.get() or None, end_var.get() or None, status_var.get()
                        ))
                    conn.commit()

                log_activity('update' if supervision_id else 'create', 'student_supervision', user_id=user_id)
                messagebox.showinfo("Success", "Supervision saved successfully")
                dialog.destroy()
                self._load_supervisions()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save supervision: {e}")

        ttk.Button(dialog, text="Save", command=save).pack(pady=20)

    def _update_supervision_progress(self):
        """Update progress notes for supervision."""
        selection = self.supervisions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a supervision")
            return

        item = self.supervisions_tree.item(selection[0])
        supervision_id = item['values'][0]
        student_name = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Progress Notes - {student_name}")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Progress Notes:").pack(pady=5)
        notes_text = tk.Text(dialog, height=15, width=60)
        notes_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Load existing notes
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT progress_notes FROM student_supervisions WHERE supervision_id = ?',
                               (supervision_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    notes_text.insert('1.0', row[0])
        except Exception as e:
            print(f"Error loading notes: {e}")

        def save_notes():
            try:
                with transaction() as conn:
                    conn.execute('''
                        UPDATE student_supervisions SET
                            progress_notes = ?, updated_at = ?
                        WHERE supervision_id = ?
                    ''', (notes_text.get('1.0', tk.END).strip(),
                          datetime.now().isoformat(), supervision_id))
                    conn.commit()
                messagebox.showinfo("Success", "Progress notes saved")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save notes: {e}")

        ttk.Button(dialog, text="Save Notes", command=save_notes).pack(pady=10)

    # ================================================================
    # EXTERNAL EXAMINERS TAB
    # ================================================================

    def _create_examiners_tab(self):
        """Create External Examiners tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="External Examiners")

        role = self.current_user.get('role')
        is_admin = role in ['admin', 'staff']

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        if is_admin:
            ttk.Button(btn_frame, text="Add Examiner", command=self._add_examiner).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Edit Examiner", command=self._edit_examiner).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="View Assignments", command=self._view_examiner_assignments).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_examiners).pack(side=tk.LEFT, padx=5)

        # Examiners list
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('ID', 'Name', 'Institution', 'Expertise', 'Department', 'Start', 'End', 'Status')
        self.examiners_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.examiners_tree.heading(col, text=col)
            self.examiners_tree.column(col, width=100)

        self.examiners_tree.column('ID', width=50)
        self.examiners_tree.column('Name', width=150)
        self.examiners_tree.column('Institution', width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.examiners_tree.yview)
        self.examiners_tree.configure(yscrollcommand=scrollbar.set)

        self.examiners_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_examiners()

    def _load_examiners(self):
        """Load external examiners."""
        self.examiners_tree.delete(*self.examiners_tree.get_children())

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT examiner_id, name, institution, expertise_area,
                           department, appointment_start, appointment_end, status
                    FROM external_examiners
                    ORDER BY name
                ''')

                for row in cursor.fetchall():
                    self.examiners_tree.insert('', 'end', values=row)
        except Exception as e:
            print(f"Error loading examiners: {e}")

    def _add_examiner(self):
        """Add new external examiner."""
        self._examiner_dialog()

    def _edit_examiner(self):
        """Edit selected examiner."""
        selection = self.examiners_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an examiner to edit")
            return

        item = self.examiners_tree.item(selection[0])
        examiner_id = item['values'][0]
        self._examiner_dialog(examiner_id)

    def _examiner_dialog(self, examiner_id=None):
        """Show examiner add/edit dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Examiner" if examiner_id else "Add Examiner")
        dialog.geometry("450x450")
        dialog.transient(self.root)
        dialog.grab_set()

        fields = {}

        for label, width in [
            ("Name:", 40), ("Institution:", 40), ("Email:", 30),
            ("Phone:", 20), ("Expertise Area:", 40), ("Department:", 30),
            ("Appointment Start (YYYY-MM-DD):", 15),
            ("Appointment End (YYYY-MM-DD):", 15)
        ]:
            ttk.Label(dialog, text=label).pack(pady=2)
            var = tk.StringVar()
            ttk.Entry(dialog, textvariable=var, width=width).pack(pady=2)
            fields[label.split(':')[0].lower().replace(' ', '_')] = var

        ttk.Label(dialog, text="Status:").pack(pady=2)
        status_var = tk.StringVar(value="active")
        ttk.Combobox(dialog, textvariable=status_var,
                     values=['active', 'inactive', 'expired'], width=15).pack(pady=2)

        if examiner_id:
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT name, institution, email, phone, expertise_area,
                               department, appointment_start, appointment_end, status
                        FROM external_examiners WHERE examiner_id = ?
                    ''', (examiner_id,))
                    row = cursor.fetchone()
                    if row:
                        fields['name'].set(row[0] or '')
                        fields['institution'].set(row[1] or '')
                        fields['email'].set(row[2] or '')
                        fields['phone'].set(row[3] or '')
                        fields['expertise_area'].set(row[4] or '')
                        fields['department'].set(row[5] or '')
                        fields['appointment_start_(yyyy-mm-dd)'].set(row[6] or '')
                        fields['appointment_end_(yyyy-mm-dd)'].set(row[7] or '')
                        status_var.set(row[8] or 'active')
            except Exception as e:
                print(f"Error loading examiner: {e}")

        def save():
            if not fields['name'].get():
                messagebox.showwarning("Warning", "Please enter examiner name")
                return

            try:
                with transaction() as conn:
                    if examiner_id:
                        conn.execute('''
                            UPDATE external_examiners SET
                                name = ?, institution = ?, email = ?, phone = ?,
                                expertise_area = ?, department = ?, appointment_start = ?,
                                appointment_end = ?, status = ?
                            WHERE examiner_id = ?
                        ''', (
                            fields['name'].get(), fields['institution'].get(),
                            fields['email'].get(), fields['phone'].get(),
                            fields['expertise_area'].get(), fields['department'].get(),
                            fields['appointment_start_(yyyy-mm-dd)'].get() or None,
                            fields['appointment_end_(yyyy-mm-dd)'].get() or None,
                            status_var.get(), examiner_id
                        ))
                    else:
                        conn.execute('''
                            INSERT INTO external_examiners (
                                name, institution, email, phone, expertise_area,
                                department, appointment_start, appointment_end, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            fields['name'].get(), fields['institution'].get(),
                            fields['email'].get(), fields['phone'].get(),
                            fields['expertise_area'].get(), fields['department'].get(),
                            fields['appointment_start_(yyyy-mm-dd)'].get() or None,
                            fields['appointment_end_(yyyy-mm-dd)'].get() or None,
                            status_var.get()
                        ))
                    conn.commit()

                user_id = self.current_user.get('id') or self.current_user.get('username')
                log_activity('update' if examiner_id else 'create', 'external_examiner', user_id=user_id)
                messagebox.showinfo("Success", "Examiner saved successfully")
                dialog.destroy()
                self._load_examiners()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save examiner: {e}")

        ttk.Button(dialog, text="Save", command=save).pack(pady=15)

    def _view_examiner_assignments(self):
        """View examiner assignments."""
        selection = self.examiners_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an examiner")
            return

        item = self.examiners_tree.item(selection[0])
        examiner_id = item['values'][0]
        examiner_name = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Assignments - {examiner_name}")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        columns = ('ID', 'Student', 'Type', 'Year', 'Report', 'Date')
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=90)

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT assignment_id, student_name, assignment_type,
                           academic_year, report_submitted, report_date
                    FROM examiner_assignments
                    WHERE examiner_id = ?
                    ORDER BY academic_year DESC
                ''', (examiner_id,))

                for row in cursor.fetchall():
                    tree.insert('', 'end', values=(
                        row[0], row[1] or 'N/A', row[2] or 'N/A',
                        row[3] or 'N/A', 'Yes' if row[4] else 'No',
                        row[5] or 'N/A'
                    ))
        except Exception as e:
            print(f"Error loading assignments: {e}")

        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    # ================================================================
    # PEER OBSERVATIONS TAB
    # ================================================================

    def _create_peer_observations_tab(self):
        """Create Peer Observations tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Peer Observations")

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="New Observation", command=self._add_observation).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="View/Edit", command=self._edit_observation).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_observations).pack(side=tk.LEFT, padx=5)

        # Filter frame
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Show:").pack(side=tk.LEFT, padx=5)
        self.obs_view_var = tk.StringVar(value="my_observations")
        ttk.Combobox(filter_frame, textvariable=self.obs_view_var,
                     values=["my_observations", "observations_of_me", "all"],
                     width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Apply", command=self._load_observations).pack(side=tk.LEFT, padx=5)

        # Observations list
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('ID', 'Observer', 'Observee', 'Course', 'Date', 'Type', 'Rating', 'Status')
        self.obs_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.obs_tree.heading(col, text=col)
            self.obs_tree.column(col, width=100)

        self.obs_tree.column('ID', width=50)
        self.obs_tree.column('Rating', width=60)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.obs_tree.yview)
        self.obs_tree.configure(yscrollcommand=scrollbar.set)

        self.obs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.obs_tree.tag_configure('draft', background='#FFFFE0')
        self.obs_tree.tag_configure('submitted', background='#90EE90')
        self.obs_tree.tag_configure('acknowledged', background='#87CEEB')

        self._load_observations()

    def _load_observations(self):
        """Load peer observations."""
        user_id = self.current_user.get('id') or self.current_user.get('username')
        view = self.obs_view_var.get()

        self.obs_tree.delete(*self.obs_tree.get_children())

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                if view == "my_observations":
                    query = '''
                        SELECT observation_id, observer_name, observee_name, course_name,
                               observation_date, observation_type, overall_rating, status
                        FROM peer_observations WHERE observer_id = ?
                        ORDER BY observation_date DESC
                    '''
                    params = [user_id]
                elif view == "observations_of_me":
                    query = '''
                        SELECT observation_id, observer_name, observee_name, course_name,
                               observation_date, observation_type, overall_rating, status
                        FROM peer_observations WHERE observee_id = ?
                        ORDER BY observation_date DESC
                    '''
                    params = [user_id]
                else:
                    query = '''
                        SELECT observation_id, observer_name, observee_name, course_name,
                               observation_date, observation_type, overall_rating, status
                        FROM peer_observations
                        ORDER BY observation_date DESC
                    '''
                    params = []

                cursor.execute(query, params)

                for row in cursor.fetchall():
                    status = row[7] or 'draft'
                    self.obs_tree.insert('', 'end', values=(
                        row[0], row[1] or 'N/A', row[2] or 'N/A', row[3] or 'N/A',
                        row[4] or 'N/A', row[5] or 'N/A', row[6] or 'N/A', status
                    ), tags=(status,))
        except Exception as e:
            print(f"Error loading observations: {e}")

    def _add_observation(self):
        """Add new peer observation."""
        self._observation_dialog()

    def _edit_observation(self):
        """Edit selected observation."""
        selection = self.obs_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an observation")
            return

        item = self.obs_tree.item(selection[0])
        obs_id = item['values'][0]
        self._observation_dialog(obs_id)

    def _observation_dialog(self, obs_id=None):
        """Show observation add/edit dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Observation" if obs_id else "New Peer Observation")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Scrollable form
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        form_frame = ttk.Frame(canvas)

        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Basic info
        basic_frame = ttk.LabelFrame(form_frame, text="Basic Information", padding=10)
        basic_frame.pack(fill=tk.X, pady=5)

        ttk.Label(basic_frame, text="Observee (Staff being observed):").pack(anchor=tk.W)
        observee_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=observee_var, width=40).pack(pady=2)

        ttk.Label(basic_frame, text="Course Code/Name:").pack(anchor=tk.W)
        course_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=course_var, width=40).pack(pady=2)

        ttk.Label(basic_frame, text="Observation Date (YYYY-MM-DD):").pack(anchor=tk.W)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(basic_frame, textvariable=date_var, width=15).pack(pady=2)

        ttk.Label(basic_frame, text="Observation Type:").pack(anchor=tk.W)
        type_var = tk.StringVar(value="peer")
        ttk.Combobox(basic_frame, textvariable=type_var,
                     values=get_observation_types(), width=20).pack(pady=2)

        ttk.Label(basic_frame, text="Class Size:").pack(anchor=tk.W)
        size_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=size_var, width=10).pack(pady=2)

        ttk.Label(basic_frame, text="Duration (minutes):").pack(anchor=tk.W)
        duration_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=duration_var, width=10).pack(pady=2)

        # Feedback
        feedback_frame = ttk.LabelFrame(form_frame, text="Feedback", padding=10)
        feedback_frame.pack(fill=tk.X, pady=5)

        ttk.Label(feedback_frame, text="Strengths:").pack(anchor=tk.W)
        strengths_text = tk.Text(feedback_frame, height=4, width=60)
        strengths_text.pack(pady=2)

        ttk.Label(feedback_frame, text="Areas for Development:").pack(anchor=tk.W)
        areas_text = tk.Text(feedback_frame, height=4, width=60)
        areas_text.pack(pady=2)

        ttk.Label(feedback_frame, text="Action Points:").pack(anchor=tk.W)
        actions_text = tk.Text(feedback_frame, height=3, width=60)
        actions_text.pack(pady=2)

        ttk.Label(feedback_frame, text="Overall Rating (1-5):").pack(anchor=tk.W)
        rating_var = tk.StringVar()
        ttk.Combobox(feedback_frame, textvariable=rating_var,
                     values=['1', '2', '3', '4', '5'], width=5).pack(pady=2)

        ttk.Label(feedback_frame, text="Status:").pack(anchor=tk.W)
        status_var = tk.StringVar(value="draft")
        ttk.Combobox(feedback_frame, textvariable=status_var,
                     values=['draft', 'submitted', 'acknowledged'], width=15).pack(pady=2)

        # Load existing data
        if obs_id:
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT observee_name, course_name, observation_date, observation_type,
                               class_size, duration_minutes, strengths, areas_for_development,
                               action_points, overall_rating, status
                        FROM peer_observations WHERE observation_id = ?
                    ''', (obs_id,))
                    row = cursor.fetchone()
                    if row:
                        observee_var.set(row[0] or '')
                        course_var.set(row[1] or '')
                        date_var.set(row[2] or '')
                        type_var.set(row[3] or 'peer')
                        size_var.set(str(row[4] or ''))
                        duration_var.set(str(row[5] or ''))
                        strengths_text.insert('1.0', row[6] or '')
                        areas_text.insert('1.0', row[7] or '')
                        actions_text.insert('1.0', row[8] or '')
                        rating_var.set(str(row[9] or ''))
                        status_var.set(row[10] or 'draft')
            except Exception as e:
                print(f"Error loading observation: {e}")

        def save():
            user_id = self.current_user.get('id') or self.current_user.get('username')
            username = self.current_user.get('username', user_id)

            if not observee_var.get():
                messagebox.showwarning("Warning", "Please enter observee name")
                return

            try:
                with transaction() as conn:
                    if obs_id:
                        conn.execute('''
                            UPDATE peer_observations SET
                                observee_name = ?, course_name = ?, observation_date = ?,
                                observation_type = ?, class_size = ?, duration_minutes = ?,
                                strengths = ?, areas_for_development = ?, action_points = ?,
                                overall_rating = ?, status = ?
                            WHERE observation_id = ?
                        ''', (
                            observee_var.get(), course_var.get(), date_var.get(),
                            type_var.get(), int(size_var.get() or 0) if size_var.get() else None,
                            int(duration_var.get() or 0) if duration_var.get() else None,
                            strengths_text.get('1.0', tk.END).strip(),
                            areas_text.get('1.0', tk.END).strip(),
                            actions_text.get('1.0', tk.END).strip(),
                            int(rating_var.get()) if rating_var.get() else None,
                            status_var.get(), obs_id
                        ))
                    else:
                        conn.execute('''
                            INSERT INTO peer_observations (
                                observer_id, observer_name, observee_name, course_name,
                                observation_date, observation_type, class_size,
                                duration_minutes, strengths, areas_for_development,
                                action_points, overall_rating, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            user_id, username, observee_var.get(), course_var.get(),
                            date_var.get(), type_var.get(),
                            int(size_var.get() or 0) if size_var.get() else None,
                            int(duration_var.get() or 0) if duration_var.get() else None,
                            strengths_text.get('1.0', tk.END).strip(),
                            areas_text.get('1.0', tk.END).strip(),
                            actions_text.get('1.0', tk.END).strip(),
                            int(rating_var.get()) if rating_var.get() else None,
                            status_var.get()
                        ))
                    conn.commit()

                log_activity('update' if obs_id else 'create', 'peer_observation', user_id=user_id)
                messagebox.showinfo("Success", "Observation saved successfully")
                dialog.destroy()
                self._load_observations()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save observation: {e}")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
