"""
Recruitment GUI

Job postings, applications, interviews and hire-pipeline management.
Wired to the same RecruitmentManager used by the recruitment CLI menu.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.systems.university.domain.staff.staff_hr.services import (
    RecruitmentManager,
)


class RecruitmentGUI:
    """GUI for staff recruitment: postings, applications and interviews."""

    def __init__(self, root, auth=None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Recruitment")
            return

        self.user_id = self.current_user.get('id') or self.current_user.get('username')

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    # ------------------------------------------------------------------
    # Container setup
    # ------------------------------------------------------------------
    def create_as_tab(self, notebook: ttk.Notebook):
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Recruitment")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        self.window = tk.Toplevel(self.root)
        self.window.title("Recruitment Management")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)
        ttk.Button(self.window, text="Close", command=self.window.destroy).pack(
            side=tk.BOTTOM, anchor=tk.E, padx=10, pady=5)
        self._build_interface(self.window)

    def _build_interface(self, parent):
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_postings_tab()
        self._create_applications_tab()
        self._create_interviews_tab()

    # ------------------------------------------------------------------
    # Job Postings
    # ------------------------------------------------------------------
    def _create_postings_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Job Postings")

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text="Job Postings", style='Header.TLabel').pack(side=tk.LEFT)

        btns = ttk.Frame(header)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text="New Posting", command=self._new_posting).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Publish", command=self._publish_posting).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Close Posting", command=self._close_posting).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Refresh", command=self._load_postings).pack(side=tk.LEFT, padx=3)

        filt = ttk.Frame(tab)
        filt.pack(fill=tk.X, padx=10)
        ttk.Label(filt, text="Status:").pack(side=tk.LEFT, padx=5)
        self.posting_status = ttk.Combobox(
            filt, values=['All', 'draft', 'open', 'closed', 'on_hold'], width=12, state='readonly')
        self.posting_status.set('All')
        self.posting_status.pack(side=tk.LEFT, padx=5)
        self.posting_status.bind('<<ComboboxSelected>>', lambda e: self._load_postings())

        self.stats_label = ttk.Label(filt, text="", foreground='gray')
        self.stats_label.pack(side=tk.RIGHT, padx=10)

        cols = ('ID', 'Title', 'Department', 'Type', 'Status', 'Posted', 'Applications')
        self.postings_tree = self._make_tree(tab, cols)

    def _load_postings(self):
        status = self.posting_status.get()
        try:
            postings = RecruitmentManager.get_staff_recruitment_postings(
                status=None if status == 'All' else status)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load postings: {e}")
            return
        self.postings_tree.delete(*self.postings_tree.get_children())
        for p in postings:
            self.postings_tree.insert('', tk.END, values=(
                p.get('posting_id'), p.get('job_title', ''), p.get('department', ''),
                p.get('job_type', ''), p.get('status', ''), p.get('post_date', ''),
                p.get('applications_count', 0)))
        self.stats_label.config(text=f"{len(postings)} posting(s)")

    def _selected_posting_id(self):
        sel = self.postings_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select a posting first.")
            return None
        return self.postings_tree.item(sel[0])['values'][0]

    def _new_posting(self):
        dlg = _FormDialog(self.window or self.root, "New Job Posting", [
            ('job_title', 'Job Title', 'entry', None),
            ('department', 'Department', 'entry', None),
            ('job_type', 'Job Type', 'combo', ['permanent', 'fixed_term', 'part_time', 'temporary']),
            ('location', 'Location', 'entry', None),
            ('salary_range', 'Salary Range', 'entry', None),
            ('description', 'Description', 'text', None),
            ('requirements', 'Requirements', 'text', None),
        ])
        if not dlg.result:
            return
        d = dlg.result
        if not d.get('job_title') or not d.get('department'):
            messagebox.showwarning("Missing data", "Title and Department are required.")
            return
        try:
            pid = RecruitmentManager.create_posting(
                posted_by=self.user_id,
                job_title=d['job_title'], department=d['department'],
                job_type=d.get('job_type') or 'permanent',
                location=d.get('location'), salary_range=d.get('salary_range'),
                description=d.get('description'), requirements=d.get('requirements'),
                posted_by_name=self.current_user.get('username'))
            messagebox.showinfo("Created", f"Job posting created (ID {pid}).")
            self._load_postings()
        except Exception as e:
            messagebox.showerror("Error", f"Could not create posting: {e}")

    def _publish_posting(self):
        pid = self._selected_posting_id()
        if pid is None:
            return
        try:
            RecruitmentManager.publish_posting(int(pid))
            messagebox.showinfo("Published", "Posting published.")
            self._load_postings()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _close_posting(self):
        pid = self._selected_posting_id()
        if pid is None:
            return
        try:
            RecruitmentManager.update_posting_status(int(pid), 'closed')
            messagebox.showinfo("Closed", "Posting closed.")
            self._load_postings()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------
    def _create_applications_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Applications")

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text="Applications", style='Header.TLabel').pack(side=tk.LEFT)

        btns = ttk.Frame(header)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text="New Application", command=self._new_application).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Shortlist", command=self._shortlist).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Reject", command=self._reject_application).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Schedule Interview", command=self._schedule_interview).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Refresh", command=self._load_applications).pack(side=tk.LEFT, padx=3)

        filt = ttk.Frame(tab)
        filt.pack(fill=tk.X, padx=10)
        ttk.Label(filt, text="Status:").pack(side=tk.LEFT, padx=5)
        self.app_status = ttk.Combobox(filt, values=[
            'All', 'received', 'shortlisted', 'interview_scheduled', 'offered', 'hired', 'rejected'],
            width=18, state='readonly')
        self.app_status.set('All')
        self.app_status.pack(side=tk.LEFT, padx=5)
        self.app_status.bind('<<ComboboxSelected>>', lambda e: self._load_applications())

        cols = ('ID', 'Applicant', 'Email', 'Position', 'Status', 'Applied')
        self.apps_tree = self._make_tree(tab, cols)

    def _load_applications(self):
        status = self.app_status.get()
        try:
            apps = RecruitmentManager.get_applications(
                status=None if status == 'All' else status)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load applications: {e}")
            return
        self.apps_tree.delete(*self.apps_tree.get_children())
        for a in apps:
            self.apps_tree.insert('', tk.END, values=(
                a.get('application_id'), a.get('applicant_name', ''),
                a.get('applicant_email', ''), a.get('job_title', ''),
                a.get('status', ''), a.get('application_date', '')))

    def _selected_application_id(self):
        sel = self.apps_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select an application first.")
            return None
        return self.apps_tree.item(sel[0])['values'][0]

    def _new_application(self):
        dlg = _FormDialog(self.window or self.root, "New Application", [
            ('posting_id', 'Posting ID', 'entry', None),
            ('applicant_name', 'Applicant Name', 'entry', None),
            ('applicant_email', 'Applicant Email', 'entry', None),
            ('applicant_phone', 'Phone', 'entry', None),
        ])
        if not dlg.result:
            return
        d = dlg.result
        try:
            aid = RecruitmentManager.submit_application(
                posting_id=int(d['posting_id']),
                applicant_name=d['applicant_name'],
                applicant_email=d['applicant_email'],
                applicant_phone=d.get('applicant_phone'))
            messagebox.showinfo("Submitted", f"Application submitted (ID {aid}).")
            self._load_applications()
        except Exception as e:
            messagebox.showerror("Error", f"Could not submit application: {e}")

    def _shortlist(self):
        aid = self._selected_application_id()
        if aid is None:
            return
        try:
            RecruitmentManager.shortlist_application(int(aid), self.user_id)
            messagebox.showinfo("Shortlisted", "Applicant shortlisted.")
            self._load_applications()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _reject_application(self):
        aid = self._selected_application_id()
        if aid is None:
            return
        dlg = _FormDialog(self.window or self.root, "Reject Application", [
            ('reason', 'Reason', 'text', None)])
        if not dlg.result:
            return
        try:
            RecruitmentManager.reject_application(int(aid), dlg.result.get('reason') or 'Not selected')
            messagebox.showinfo("Rejected", "Application rejected.")
            self._load_applications()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _schedule_interview(self):
        aid = self._selected_application_id()
        if aid is None:
            return
        dlg = _FormDialog(self.window or self.root, "Schedule Interview", [
            ('interview_date', 'Date (YYYY-MM-DD)', 'entry', None),
            ('interview_time', 'Time (HH:MM)', 'entry', None),
            ('interview_type', 'Type', 'combo', ['in-person', 'video', 'phone']),
            ('location', 'Location / Link', 'entry', None),
            ('interviewers', 'Interviewers', 'entry', None),
        ])
        if not dlg.result:
            return
        d = dlg.result
        try:
            iid = RecruitmentManager.schedule_interview(
                application_id=int(aid),
                interview_date=d['interview_date'],
                interview_time=d['interview_time'],
                interview_type=d.get('interview_type') or 'in-person',
                location=d.get('location'), interviewers=d.get('interviewers'))
            messagebox.showinfo("Scheduled", f"Interview scheduled (ID {iid}).")
            self._load_applications()
            self._load_interviews()
        except Exception as e:
            messagebox.showerror("Error", f"Could not schedule interview: {e}")

    # ------------------------------------------------------------------
    # Interviews
    # ------------------------------------------------------------------
    def _create_interviews_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Interviews")

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text="Interviews", style='Header.TLabel').pack(side=tk.LEFT)
        btns = ttk.Frame(header)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text="Record Feedback", command=self._record_feedback).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Refresh", command=self._load_interviews).pack(side=tk.LEFT, padx=3)

        cols = ('ID', 'Applicant', 'Position', 'Date', 'Time', 'Type', 'Status')
        self.interviews_tree = self._make_tree(tab, cols)

    def _load_interviews(self):
        try:
            interviews = RecruitmentManager.get_interviews()
        except Exception as e:
            messagebox.showerror("Error", f"Could not load interviews: {e}")
            return
        self.interviews_tree.delete(*self.interviews_tree.get_children())
        for i in interviews:
            self.interviews_tree.insert('', tk.END, values=(
                i.get('interview_id'), i.get('applicant_name', ''),
                i.get('job_title', ''), i.get('interview_date', ''),
                i.get('interview_time', ''), i.get('interview_type', ''),
                i.get('status', '')))

    def _record_feedback(self):
        sel = self.interviews_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select an interview first.")
            return
        iid = self.interviews_tree.item(sel[0])['values'][0]
        dlg = _FormDialog(self.window or self.root, "Interview Feedback", [
            ('recommendation', 'Recommendation', 'combo', ['hire', 'hold', 'reject']),
            ('overall_score', 'Overall Score (0-10)', 'entry', None),
            ('feedback', 'Feedback', 'text', None),
        ])
        if not dlg.result:
            return
        d = dlg.result
        try:
            score = float(d['overall_score']) if d.get('overall_score') else None
            RecruitmentManager.record_interview_feedback(
                int(iid), recommendation=d.get('recommendation'),
                overall_score=score, feedback=d.get('feedback'))
            messagebox.showinfo("Saved", "Feedback recorded.")
            self._load_interviews()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _make_tree(self, parent, cols):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        tree = ttk.Treeview(frame, columns=cols, show='headings', yscrollcommand=yscroll.set)
        yscroll.config(command=tree.yview)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=130, anchor=tk.W)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def refresh_all(self):
        """Load all data (used after the tab is first shown)."""
        self._load_postings()
        self._load_applications()
        self._load_interviews()


class _FormDialog:
    """Simple modal form dialog.

    fields: list of (key, label, kind, options) where kind is
    'entry', 'text' or 'combo' (options is the combo value list).
    On OK, self.result is a dict of key -> value; on cancel it is None.
    """

    def __init__(self, parent, title, fields):
        self.result = None
        self._widgets = {}
        self._fields = fields

        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.transient(parent)
        self.top.resizable(False, False)

        body = ttk.Frame(self.top, padding=15)
        body.pack(fill=tk.BOTH, expand=True)

        for row, (key, label, kind, options) in enumerate(fields):
            ttk.Label(body, text=label + ":").grid(row=row, column=0, sticky=tk.W, padx=5, pady=4)
            if kind == 'text':
                widget = tk.Text(body, width=40, height=3)
            elif kind == 'combo':
                widget = ttk.Combobox(body, values=options or [], width=37, state='readonly')
                if options:
                    widget.set(options[0])
            else:
                widget = ttk.Entry(body, width=40)
            widget.grid(row=row, column=1, sticky=tk.W, padx=5, pady=4)
            self._widgets[key] = (widget, kind)

        btns = ttk.Frame(body)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btns, text="OK", command=self._ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side=tk.LEFT, padx=5)

        try:
            self.top.grab_set()
            self.top.wait_window(self.top)
        except tk.TclError:
            # Headless / no event loop - leave result as populated by caller
            pass

    def _ok(self):
        data = {}
        for key, (widget, kind) in self._widgets.items():
            if kind == 'text':
                data[key] = widget.get('1.0', tk.END).strip()
            else:
                data[key] = widget.get().strip()
        self.result = data
        self.top.destroy()

    def _cancel(self):
        self.result = None
        self.top.destroy()
