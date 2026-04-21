"""Student Jobs — Staff/Instructor portal.

Post jobs, view applicants per job, and move applications through status
transitions (received → interview → offered / rejected). Admins retain
the full `StudentJobsGUI` for skills tagging, work-study flags, pay
reports, and analytics.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


_EMPLOYMENT = ['part-time', 'full-time', 'temporary', 'work-study',
               'internship']
_APP_STATUSES = ['received', 'reviewing', 'interview', 'offered',
                 'accepted', 'rejected', 'withdrawn']


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class StudentJobsStaffPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        user = (auth.current_user if auth else None) or {}
        self.user_id = user.get('id') or user.get('user_id')
        self.user_label = (user.get('display_name')
                           or user.get('username', 'staff'))

        self.window = tk.Toplevel(parent)
        self.window.title("Student Jobs — Staff Portal")
        self.window.geometry("1200x720")
        self.window.minsize(1000, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.show_inactive_var = tk.BooleanVar(value=False)
        self.info_var = tk.StringVar(value="")

        self._build_ui()
        self._load_jobs()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#2c3e50', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"Student Jobs — Staff ({self.user_label})",
                 font=('Arial', 14, 'bold'), bg='#2c3e50', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        bar = ttk.Frame(self.window, padding=(10, 8))
        bar.pack(fill='x')
        ttk.Checkbutton(bar, text="Include closed/inactive postings",
                        variable=self.show_inactive_var,
                        command=self._load_jobs).pack(side='left')
        ttk.Button(bar, text="+ Post Job",
                   command=self._new_job).pack(side='right')
        ttk.Button(bar, text="Close Posting",
                   command=self._close_posting).pack(side='right', padx=4)
        ttk.Button(bar, text="Refresh",
                   command=self._load_jobs).pack(side='right', padx=4)

        paned = ttk.PanedWindow(self.window, orient='vertical')
        paned.pack(fill='both', expand=True, padx=10, pady=(4, 4))

        jobs_frame = ttk.LabelFrame(paned, text="Job Postings", padding=4)
        paned.add(jobs_frame, weight=2)
        cols = ('title', 'employer', 'type', 'rate', 'pos', 'deadline', 'active')
        self.jobs_tree = ttk.Treeview(jobs_frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('title', 'Title', 240), ('employer', 'Employer', 160),
            ('type', 'Type', 110), ('rate', '£/hr', 80),
            ('pos', 'Positions', 100),
            ('deadline', 'Deadline', 120), ('active', 'Active', 80),
        ]:
            self.jobs_tree.heading(key, text=title)
            self.jobs_tree.column(key, width=width,
                                  anchor='w' if key in ('title', 'employer')
                                                else 'center')
        vsb = ttk.Scrollbar(jobs_frame, orient='vertical',
                            command=self.jobs_tree.yview)
        self.jobs_tree.configure(yscrollcommand=vsb.set)
        self.jobs_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.jobs_tree.bind('<<TreeviewSelect>>', self._load_applications)
        self.jobs_tree.tag_configure('inactive', foreground='#888')

        app_frame = ttk.LabelFrame(paned, text="Applications", padding=4)
        paned.add(app_frame, weight=1)

        app_bar = ttk.Frame(app_frame)
        app_bar.pack(fill='x', pady=(0, 4))
        ttk.Label(app_bar, text="Change selected application status:"
                  ).pack(side='left')
        self.new_status_var = tk.StringVar(value='reviewing')
        ttk.Combobox(app_bar, textvariable=self.new_status_var,
                     values=_APP_STATUSES, state='readonly', width=14
                     ).pack(side='left', padx=4)
        ttk.Button(app_bar, text="Update status",
                   command=self._update_app_status).pack(side='left')

        a_cols = ('app_id', 'student', 'applied', 'status', 'interview')
        self.app_tree = ttk.Treeview(app_frame, columns=a_cols,
                                     show='headings', selectmode='browse')
        for key, title, width in [
            ('app_id', 'App ID', 70), ('student', 'Student', 150),
            ('applied', 'Applied', 140), ('status', 'Status', 120),
            ('interview', 'Interview', 140),
        ]:
            self.app_tree.heading(key, text=title)
            self.app_tree.column(key, width=width,
                                 anchor='w' if key == 'student'
                                               else 'center')
        a_vsb = ttk.Scrollbar(app_frame, orient='vertical',
                              command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=a_vsb.set)
        self.app_tree.pack(side='left', fill='both', expand=True)
        a_vsb.pack(side='right', fill='y')

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _load_jobs(self):
        for i in self.jobs_tree.get_children():
            self.jobs_tree.delete(i)
        for i in self.app_tree.get_children():
            self.app_tree.delete(i)

        sql = (
            "SELECT job_id, job_title, employer_name, employment_type, "
            "       hourly_rate, filled_positions, total_positions, "
            "       application_deadline, is_active "
            "FROM campus_job_postings"
        )
        if not self.show_inactive_var.get():
            sql += " WHERE is_active = 1"
        sql += " ORDER BY posted_date DESC LIMIT 500"

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)
            return

        for jid, title, employer, etype, rate, filled, total, dl, active in rows:
            pos = f"{filled or 0}/{total or '?'}"
            rate_str = f"{rate:.2f}" if rate is not None else ''
            tag = ('inactive',) if not active else ()
            self.jobs_tree.insert('', 'end', iid=str(jid), values=(
                title or '', employer or '', etype or '',
                rate_str, pos, (dl or '')[:10],
                'Yes' if active else 'No'
            ), tags=tag)
        self.info_var.set(f"{len(rows)} posting(s).")

    def _load_applications(self, _event=None):
        for i in self.app_tree.get_children():
            self.app_tree.delete(i)
        sel = self.jobs_tree.selection()
        if not sel:
            return
        jid = int(sel[0])
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT application_id, student_id, application_date, "
                    "       status, interview_date "
                    "FROM campus_job_applications "
                    "WHERE job_id = ? "
                    "ORDER BY application_date DESC LIMIT 500",
                    (jid,)
                )
                for row in cur.fetchall():
                    self.app_tree.insert('', 'end', iid=str(row[0]), values=(
                        row[0], row[1] or '', (row[2] or '')[:16],
                        row[3] or '', (row[4] or '')[:16]
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.window)

    def _update_app_status(self):
        sel = self.app_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an application first.",
                                parent=self.window)
            return
        new_status = self.new_status_var.get()
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE campus_job_applications "
                    "SET status = ?, reviewed_by = ?, reviewed_date = ?, "
                    "    updated_at = ? "
                    "WHERE application_id = ?",
                    (new_status, self.user_id,
                     datetime.now().isoformat(timespec='seconds'),
                     datetime.now().isoformat(timespec='seconds'),
                     int(sel[0]))
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Update Failed", str(e),
                                 parent=self.window)
            return
        self._load_applications()
        self.info_var.set(f"Application {sel[0]} → {new_status}.")

    def _close_posting(self):
        sel = self.jobs_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a posting to close.",
                                parent=self.window)
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE campus_job_postings SET is_active = 0, "
                    "       updated_at = ? WHERE job_id = ?",
                    (datetime.now().isoformat(timespec='seconds'),
                     int(sel[0]))
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Update Failed", str(e),
                                 parent=self.window)
            return
        self._load_jobs()

    def _new_job(self):
        JobPostingDialog(self.window, user_id=self.user_id,
                         on_save=self._load_jobs)


class JobPostingDialog:
    def __init__(self, parent, user_id, on_save):
        self.user_id = user_id
        self.on_save = on_save
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Post Job")
        self.dialog.geometry("500x540")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        self.title_var = tk.StringVar()
        self.employer_var = tk.StringVar()
        self.type_var = tk.StringVar(value='part-time')
        self.rate_var = tk.StringVar(value='12.00')
        self.hours_var = tk.StringVar(value='10')
        self.positions_var = tk.StringVar(value='1')
        self.location_var = tk.StringVar()
        default_dl = (datetime.now() + timedelta(days=30)
                      ).date().isoformat()
        self.deadline_var = tk.StringVar(value=default_dl)

        for i, (label, widget_factory) in enumerate([
            ("Title:",
                lambda f: ttk.Entry(f, textvariable=self.title_var, width=34)),
            ("Employer:",
                lambda f: ttk.Entry(f, textvariable=self.employer_var, width=34)),
            ("Type:",
                lambda f: ttk.Combobox(f, textvariable=self.type_var,
                                        values=_EMPLOYMENT, width=32)),
            ("Hourly rate:",
                lambda f: ttk.Entry(f, textvariable=self.rate_var, width=34)),
            ("Hours/week:",
                lambda f: ttk.Entry(f, textvariable=self.hours_var, width=34)),
            ("Positions:",
                lambda f: ttk.Entry(f, textvariable=self.positions_var, width=34)),
            ("Location:",
                lambda f: ttk.Entry(f, textvariable=self.location_var, width=34)),
            ("Deadline (YYYY-MM-DD):",
                lambda f: ttk.Entry(f, textvariable=self.deadline_var, width=34)),
        ]):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky='w', pady=4)
            widget_factory(frame).grid(row=i, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Description:").grid(row=8, column=0,
                                                    sticky='nw', pady=4)
        self.desc_text = tk.Text(frame, width=34, height=5, wrap='word')
        self.desc_text.grid(row=8, column=1, sticky='w', pady=4)

        btns = ttk.Frame(frame)
        btns.grid(row=9, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(btns, text="Save",
                   command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _save(self):
        title = self.title_var.get().strip()
        employer = self.employer_var.get().strip()
        if not (title and employer):
            messagebox.showerror("Missing",
                                 "Title and employer are required.",
                                 parent=self.dialog)
            return
        try:
            rate = float(self.rate_var.get() or 0)
            hours = float(self.hours_var.get() or 0)
            positions = int(self.positions_var.get() or 1)
        except ValueError:
            messagebox.showerror("Invalid",
                                 "Rate, hours and positions must be numbers.",
                                 parent=self.dialog)
            return
        deadline = self.deadline_var.get().strip()
        if deadline:
            try:
                datetime.strptime(deadline, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Invalid Date",
                                     f"'{deadline}' is not YYYY-MM-DD.",
                                     parent=self.dialog)
                return

        now = datetime.now().isoformat(timespec='seconds')
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO campus_job_postings "
                    "(employer_name, job_title, employment_type, "
                    " hourly_rate, hours_per_week, total_positions, "
                    " filled_positions, job_description, location, "
                    " application_deadline, posted_by, posted_date, "
                    " is_active, is_work_study, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
                    (employer, title,
                     self.type_var.get().strip() or 'part-time',
                     rate, hours, positions,
                     self.desc_text.get('1.0', 'end').strip(),
                     self.location_var.get().strip(),
                     deadline or None, self.user_id, now,
                     1 if self.type_var.get().strip() == 'work-study' else 0,
                     now, now)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Save Failed", str(e), parent=self.dialog)
            return
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_student_jobs_staff_portal(parent, auth):
    return StudentJobsStaffPortal(parent, auth)
