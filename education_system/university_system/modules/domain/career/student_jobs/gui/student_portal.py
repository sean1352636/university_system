"""Student Jobs — Student portal.

Browse active campus job postings, apply for a job (with cover letter),
view my applications, and withdraw a pending application. Admins retain
the full `StudentJobsGUI`.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class StudentJobsStudentPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        user = (auth.current_user if auth else None) or {}
        self.student_id = str(user.get('student_id') or user.get('username')
                              or user.get('user_id') or '')

        self.window = tk.Toplevel(parent)
        self.window.title("Student Jobs — My Portal")
        self.window.geometry("1100x700")
        self.window.minsize(950, 580)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.search_var = tk.StringVar()
        self.info_var = tk.StringVar(value="")
        self._applied_job_ids = set()

        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#2c3e50', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        user = (self.auth.current_user if self.auth else None) or {}
        display = user.get('display_name') or user.get('username', '')
        tk.Label(header, text=f"Student Jobs — {display}",
                 font=('Arial', 14, 'bold'), bg='#2c3e50', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#1c2833', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh_all).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#1c2833', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))
        self._build_browse_tab(nb)
        self._build_mine_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _build_browse_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Browse Jobs")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side='left', padx=(0, 4))
        entry = ttk.Entry(bar, textvariable=self.search_var, width=30)
        entry.pack(side='left', padx=(0, 6))
        entry.bind('<Return>', lambda _e: self._load_jobs())
        ttk.Button(bar, text="Search",
                   command=self._load_jobs).pack(side='left')
        ttk.Button(bar, text="Apply",
                   command=self._apply).pack(side='right')
        ttk.Button(bar, text="View Details",
                   command=self._view_details).pack(side='right', padx=4)

        cols = ('title', 'employer', 'type', 'rate', 'hours',
                'deadline', 'applied')
        self.jobs_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('title', 'Title', 260), ('employer', 'Employer', 150),
            ('type', 'Type', 100), ('rate', '£/hr', 80),
            ('hours', 'Hrs/wk', 80),
            ('deadline', 'Deadline', 110), ('applied', 'Applied', 80),
        ]:
            self.jobs_tree.heading(key, text=title)
            self.jobs_tree.column(key, width=width,
                                  anchor='w' if key in ('title', 'employer')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.jobs_tree.yview)
        self.jobs_tree.configure(yscrollcommand=vsb.set)
        self.jobs_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.jobs_tree.tag_configure('applied', background='#d5f5e3')

    def _build_mine_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="My Applications")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="My job applications",
                  font=('Arial', 11, 'bold')).pack(side='left')
        ttk.Button(bar, text="Withdraw",
                   command=self._withdraw).pack(side='right')

        cols = ('app_id', 'title', 'employer', 'applied', 'status', 'interview')
        self.mine_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('app_id', 'App ID', 70),
            ('title', 'Job Title', 240),
            ('employer', 'Employer', 150),
            ('applied', 'Applied', 130),
            ('status', 'Status', 120),
            ('interview', 'Interview', 140),
        ]:
            self.mine_tree.heading(key, text=title)
            self.mine_tree.column(key, width=width,
                                  anchor='w' if key in ('title', 'employer')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.mine_tree.yview)
        self.mine_tree.configure(yscrollcommand=vsb.set)
        self.mine_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _refresh_all(self):
        self._load_mine()
        self._load_jobs()

    def _load_jobs(self):
        for i in self.jobs_tree.get_children():
            self.jobs_tree.delete(i)
        today = datetime.now().date().isoformat()
        query = self.search_var.get().strip()

        sql = (
            "SELECT job_id, job_title, employer_name, employment_type, "
            "       hourly_rate, hours_per_week, application_deadline "
            "FROM campus_job_postings "
            "WHERE is_active = 1 "
            "  AND (application_deadline IS NULL "
            "       OR application_deadline >= ?)"
        )
        params = [today]
        if query:
            like = f"%{query}%"
            sql += (" AND (job_title LIKE ? OR employer_name LIKE ? "
                    "      OR job_description LIKE ?)")
            params.extend([like, like, like])
        sql += " ORDER BY posted_date DESC LIMIT 500"

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return

        for jid, title, employer, etype, rate, hours, dl in rows:
            mine = jid in self._applied_job_ids
            tag = ('applied',) if mine else ()
            rate_str = f"{rate:.2f}" if rate is not None else ''
            self.jobs_tree.insert('', 'end', iid=str(jid), values=(
                title or '', employer or '', etype or '',
                rate_str, hours or '', (dl or '')[:10],
                'Yes' if mine else ''
            ), tags=tag)
        self.info_var.set(f"{len(rows)} active posting(s).")

    def _load_mine(self):
        for i in self.mine_tree.get_children():
            self.mine_tree.delete(i)
        self._applied_job_ids.clear()
        if not self.student_id:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT a.application_id, a.job_id, p.job_title, "
                    "       p.employer_name, a.application_date, "
                    "       a.status, a.interview_date "
                    "FROM campus_job_applications a "
                    "JOIN campus_job_postings p ON p.job_id = a.job_id "
                    "WHERE a.student_id = ? "
                    "ORDER BY a.application_date DESC LIMIT 500",
                    (self.student_id,)
                )
                for row in cur.fetchall():
                    self._applied_job_ids.add(row[1])
                    self.mine_tree.insert('', 'end', iid=str(row[0]), values=(
                        row[0], row[2] or '', row[3] or '',
                        (row[4] or '')[:16], row[5] or '',
                        (row[6] or '')[:16]
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)

    def _view_details(self):
        sel = self.jobs_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a job.",
                                parent=self.window)
            return
        jid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT job_title, employer_name, job_description, "
                    "       required_skills, preferred_skills, location, "
                    "       schedule_flexibility, contact_email "
                    "FROM campus_job_postings WHERE job_id = ?", (jid,)
                )
                row = cur.fetchone()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return
        if not row:
            return
        title, employer, desc, req, pref, loc, sched, email = row
        text = (
            f"Title: {title}\n"
            f"Employer: {employer}\n"
            f"Location: {loc or '(not specified)'}\n"
            f"Schedule: {sched or '(not specified)'}\n"
            f"Contact: {email or '(not specified)'}\n\n"
            f"Description:\n{desc or '(none)'}\n\n"
            f"Required skills: {req or '(none listed)'}\n"
            f"Preferred skills: {pref or '(none listed)'}"
        )
        detail = tk.Toplevel(self.window)
        detail.title(f"Job: {title}")
        detail.geometry("640x480")
        detail.transient(self.window)
        txt = tk.Text(detail, wrap='word', padx=12, pady=12)
        txt.insert('1.0', text)
        txt.configure(state='disabled')
        txt.pack(fill='both', expand=True)

    def _apply(self):
        if not self.student_id:
            messagebox.showerror("Not Signed In",
                                 "Your account is not linked to a student_id.",
                                 parent=self.window)
            return
        sel = self.jobs_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a job to apply for.",
                                parent=self.window)
            return
        jid = int(sel[0])
        if jid in self._applied_job_ids:
            messagebox.showinfo("Already Applied",
                                "You've already applied for this job.",
                                parent=self.window)
            return
        ApplyDialog(self.window, jid, self.student_id,
                    on_save=self._refresh_all)

    def _withdraw(self):
        sel = self.mine_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an application to withdraw.",
                                parent=self.window)
            return
        if not messagebox.askyesno("Withdraw",
                                   "Withdraw this application?",
                                   parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE campus_job_applications "
                    "SET status = 'withdrawn', updated_at = ? "
                    "WHERE application_id = ? AND student_id = ?",
                    (datetime.now().isoformat(timespec='seconds'),
                     int(sel[0]), self.student_id)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Withdraw Failed", str(e),
                                 parent=self.window)
            return
        self._refresh_all()


class ApplyDialog:
    def __init__(self, parent, job_id, student_id, on_save):
        self.job_id = job_id
        self.student_id = student_id
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Apply")
        self.dialog.geometry("480x400")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Cover letter (why you're a good fit):"
                  ).pack(anchor='w')
        self.cover_text = tk.Text(frame, width=54, height=9, wrap='word')
        self.cover_text.pack(fill='x', pady=(4, 8))

        ttk.Label(frame, text="Expected hours/week:"
                  ).pack(anchor='w')
        self.hours_var = tk.StringVar(value='10')
        ttk.Entry(frame, textvariable=self.hours_var, width=20
                  ).pack(anchor='w', pady=(4, 8))

        ttk.Label(frame, text="Availability (days/times):"
                  ).pack(anchor='w')
        self.avail_text = tk.Text(frame, width=54, height=3, wrap='word')
        self.avail_text.pack(fill='x', pady=(4, 8))

        btns = ttk.Frame(frame)
        btns.pack(fill='x')
        ttk.Button(btns, text="Submit Application",
                   command=self._save).pack(side='right', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='right', padx=4)

    def _save(self):
        try:
            hours = float(self.hours_var.get() or 0)
        except ValueError:
            hours = 0.0
        now = datetime.now().isoformat(timespec='seconds')
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO campus_job_applications "
                    "(job_id, student_id, cover_letter, availability, "
                    " expected_hours_per_week, application_date, status, "
                    " created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'received', ?, ?)",
                    (self.job_id, self.student_id,
                     self.cover_text.get('1.0', 'end').strip(),
                     self.avail_text.get('1.0', 'end').strip(),
                     hours, now, now, now)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Application Failed", str(e),
                                 parent=self.dialog)
            return
        messagebox.showinfo("Submitted",
                            "Your application has been submitted.",
                            parent=self.dialog)
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_student_jobs_student_portal(parent, auth):
    return StudentJobsStudentPortal(parent, auth)
