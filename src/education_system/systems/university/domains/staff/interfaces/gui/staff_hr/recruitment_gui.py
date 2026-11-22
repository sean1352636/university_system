"""
Recruitment GUI

Job postings, applications, interviews and hire-pipeline management.
Wired to the same RecruitmentManager used by the recruitment CLI menu; the
Checks, References, Offers and Hire tabs use ``staff_hr.hiring`` (recruitment
or HR only).
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access, hiring
from education_system.systems.university.domains.staff.domain.staff_hr.services import (
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
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), _t('gui.staff.staff_hr.recruitment.dialogs.login_required_to_access_recruitment', default="Login required to access Recruitment"))
            return

        # Staff HR keys people by username (never current_user['id']).
        self.user_id = access.username_of(auth)
        self.can_hire = hiring.can_hire(auth)

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    # ------------------------------------------------------------------
    # Container setup
    # ------------------------------------------------------------------
    def create_as_tab(self, notebook: ttk.Notebook):
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text=_t('gui.staff.staff_hr.recruitment.tabs.recruitment', default="Recruitment"))
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        self.window = tk.Toplevel(self.root)
        self.window.title(_t('gui.staff.staff_hr.recruitment.windows.recruitment_management', default="Recruitment Management"))
        self.window.geometry("1400x900")
        self.window.minsize(1200, 800)
        ttk.Button(self.window, text=_t('gui.staff.staff_hr.recruitment.buttons.close', default="Close"), command=self.window.destroy).pack(
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
        self._create_checks_tab()
        self._create_references_tab()
        self._create_offers_tab()
        self._create_hire_tab()

    # ------------------------------------------------------------------
    # Job Postings
    # ------------------------------------------------------------------
    def _create_postings_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.recruitment.tabs.job_postings', default="Job Postings"))

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text=_t('gui.staff.staff_hr.recruitment.labels.job_postings', default="Job Postings"), style='Header.TLabel').pack(side=tk.LEFT)

        btns = ttk.Frame(header)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.new_posting', default="New Posting"), command=self._new_posting).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.publish', default="Publish"), command=self._publish_posting).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.close_posting', default="Close Posting"), command=self._close_posting).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.refresh', default="Refresh"), command=self._load_postings).pack(side=tk.LEFT, padx=3)

        filt = ttk.Frame(tab)
        filt.pack(fill=tk.X, padx=10)
        ttk.Label(filt, text=_t('gui.staff.staff_hr.recruitment.labels.status', default="Status:")).pack(side=tk.LEFT, padx=5)
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
                status=None if status == 'All' else status, actor=self.auth)
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), f"Could not load postings: {e}")
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
            messagebox.showwarning(_t('gui.staff.staff_hr.recruitment.dialogs.no_selection', default="No selection"), _t('gui.staff.staff_hr.recruitment.dialogs.select_a_posting_first', default="Select a posting first."))
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
            messagebox.showwarning(_t('gui.staff.staff_hr.recruitment.dialogs.missing_data', default="Missing data"), _t('gui.staff.staff_hr.recruitment.dialogs.title_and_department_are_required', default="Title and Department are required."))
            return
        try:
            pid = RecruitmentManager.create_posting(
                posted_by=self.user_id,
                job_title=d['job_title'], department=d['department'],
                job_type=d.get('job_type') or 'permanent',
                location=d.get('location'), salary_range=d.get('salary_range'),
                description=d.get('description'), requirements=d.get('requirements'),
                posted_by_name=self.current_user.get('username'), actor=self.auth)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.created', default="Created"), f"Job posting created (ID {pid}).")
            self._load_postings()
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), f"Could not create posting: {e}")

    def _publish_posting(self):
        pid = self._selected_posting_id()
        if pid is None:
            return
        try:
            RecruitmentManager.publish_posting(int(pid), actor=self.auth)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.published', default="Published"), _t('gui.staff.staff_hr.recruitment.dialogs.posting_published', default="Posting published."))
            self._load_postings()
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), str(e))

    def _close_posting(self):
        pid = self._selected_posting_id()
        if pid is None:
            return
        try:
            RecruitmentManager.update_posting_status(int(pid), 'closed', actor=self.auth)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.closed', default="Closed"), _t('gui.staff.staff_hr.recruitment.dialogs.posting_closed', default="Posting closed."))
            self._load_postings()
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), str(e))

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------
    def _create_applications_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.recruitment.tabs.applications', default="Applications"))

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text=_t('gui.staff.staff_hr.recruitment.labels.applications', default="Applications"), style='Header.TLabel').pack(side=tk.LEFT)

        btns = ttk.Frame(header)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.new_application', default="New Application"), command=self._new_application).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.shortlist', default="Shortlist"), command=self._shortlist).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.reject', default="Reject"), command=self._reject_application).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.schedule_interview', default="Schedule Interview"), command=self._schedule_interview).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.refresh', default="Refresh"), command=self._load_applications).pack(side=tk.LEFT, padx=3)

        filt = ttk.Frame(tab)
        filt.pack(fill=tk.X, padx=10)
        ttk.Label(filt, text=_t('gui.staff.staff_hr.recruitment.labels.status', default="Status:")).pack(side=tk.LEFT, padx=5)
        self.app_status = ttk.Combobox(filt, values=[
            'All', 'received', 'shortlisted', 'interview_scheduled', 'offered', 'offer_accepted',
            'offer_declined', 'offer_withdrawn', 'hired', 'rejected'],
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
                status=None if status == 'All' else status, actor=self.auth)
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), f"Could not load applications: {e}")
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
            messagebox.showwarning(_t('gui.staff.staff_hr.recruitment.dialogs.no_selection', default="No selection"), _t('gui.staff.staff_hr.recruitment.dialogs.select_an_application_first', default="Select an application first."))
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
                applicant_phone=d.get('applicant_phone'), actor=self.auth)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.submitted', default="Submitted"), f"Application submitted (ID {aid}).")
            self._load_applications()
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), f"Could not submit application: {e}")

    def _shortlist(self):
        aid = self._selected_application_id()
        if aid is None:
            return
        try:
            RecruitmentManager.shortlist_application(int(aid), self.user_id, actor=self.auth)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.shortlisted', default="Shortlisted"), _t('gui.staff.staff_hr.recruitment.dialogs.applicant_shortlisted', default="Applicant shortlisted."))
            self._load_applications()
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), str(e))

    def _reject_application(self):
        aid = self._selected_application_id()
        if aid is None:
            return
        dlg = _FormDialog(self.window or self.root, "Reject Application", [
            ('reason', 'Reason', 'text', None)])
        if not dlg.result:
            return
        try:
            RecruitmentManager.reject_application(int(aid), dlg.result.get('reason') or 'Not selected', actor=self.auth)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.rejected', default="Rejected"), _t('gui.staff.staff_hr.recruitment.dialogs.application_rejected', default="Application rejected."))
            self._load_applications()
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), str(e))

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
                location=d.get('location'), interviewers=d.get('interviewers'), actor=self.auth)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.scheduled', default="Scheduled"), f"Interview scheduled (ID {iid}).")
            self._load_applications()
            self._load_interviews()
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), f"Could not schedule interview: {e}")

    # ------------------------------------------------------------------
    # Interviews
    # ------------------------------------------------------------------
    def _create_interviews_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.recruitment.tabs.interviews', default="Interviews"))

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text=_t('gui.staff.staff_hr.recruitment.labels.interviews', default="Interviews"), style='Header.TLabel').pack(side=tk.LEFT)
        btns = ttk.Frame(header)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.record_feedback', default="Record Feedback"), command=self._record_feedback).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.refresh', default="Refresh"), command=self._load_interviews).pack(side=tk.LEFT, padx=3)

        cols = ('ID', 'Applicant', 'Position', 'Date', 'Time', 'Type', 'Status')
        self.interviews_tree = self._make_tree(tab, cols)

    def _load_interviews(self):
        try:
            interviews = RecruitmentManager.get_interviews(actor=self.auth)
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), f"Could not load interviews: {e}")
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
            messagebox.showwarning(_t('gui.staff.staff_hr.recruitment.dialogs.no_selection', default="No selection"), _t('gui.staff.staff_hr.recruitment.dialogs.select_an_interview_first', default="Select an interview first."))
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
                overall_score=score, feedback=d.get('feedback'), actor=self.auth)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.saved', default="Saved"), _t('gui.staff.staff_hr.recruitment.dialogs.feedback_recorded', default="Feedback recorded."))
            self._load_interviews()
        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"), str(e))

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
        if self.can_hire:
            self._load_checks()
            self._load_references()
            self._load_offers()
            self._load_hire()

    # ------------------------------------------------------------------
    # Hiring: checks, references, offers, hire (staff_hr.hiring)
    # ------------------------------------------------------------------
    def _parent(self):
        return self.window or self.root

    def _error(self, e):
        messagebox.showerror(_t('gui.staff.staff_hr.recruitment.dialogs.error', default="Error"),
                             str(e), parent=self._parent())

    def _hiring_tab(self, key, title):
        """A new tab; None (with an explanation) for people who cannot hire."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t(f'gui.staff.staff_hr.recruitment.tabs.{key}', default=title))
        if not self.can_hire:
            ttk.Label(tab, text=_t('gui.staff.staff_hr.recruitment.labels.hiring_restricted',
                                   default="Only recruitment or HR can manage hiring."),
                      foreground='gray').pack(padx=20, pady=20)
            return None
        return tab

    def _hiring_header(self, tab, title, buttons, with_app_filter=True):
        """Header with buttons; returns the application-ID filter entry (or None)."""
        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text=title, style='Header.TLabel').pack(side=tk.LEFT)
        btns = ttk.Frame(header)
        btns.pack(side=tk.RIGHT)
        for key, label, command in buttons:
            ttk.Button(btns, text=_t(f'gui.staff.staff_hr.recruitment.buttons.{key}', default=label),
                       command=command).pack(side=tk.LEFT, padx=3)
        if not with_app_filter:
            return None
        filt = ttk.Frame(tab)
        filt.pack(fill=tk.X, padx=10)
        ttk.Label(filt, text=_t('gui.staff.staff_hr.recruitment.labels.application_id',
                                default="Application ID:")).pack(side=tk.LEFT, padx=5)
        entry = ttk.Entry(filt, width=10)
        entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(filt, text=_t('gui.staff.staff_hr.recruitment.labels.application_hint',
                                default="(blank = all; the selected application is used "
                                        "when actions need one)"),
                  foreground='gray').pack(side=tk.LEFT, padx=5)
        return entry

    def _hiring_app_id(self, entry, required=True):
        """The application ID typed in ``entry``, else the one selected on Applications."""
        text = entry.get().strip() if entry is not None else ''
        if text:
            if not text.isdigit():
                raise ValueError("Application ID must be a number")
            return int(text)
        sel = self.apps_tree.selection()
        if sel:
            return int(self.apps_tree.item(sel[0])['values'][0])
        if required:
            raise ValueError("Type an application ID or select an application first")
        return None

    def _tree_id(self, tree, what):
        sel = tree.selection()
        if not sel:
            raise ValueError(f"Select {what} first")
        return int(tree.item(sel[0])['values'][0])

    # Checks -----------------------------------------------------------
    def _create_checks_tab(self):
        tab = self._hiring_tab('checks', "Checks")
        if tab is None:
            return
        self.checks_app = self._hiring_header(tab, _t(
            'gui.staff.staff_hr.recruitment.labels.pre_employment_checks',
            default="Pre-employment Checks"), [
            ('start_checks', "Start Required Checks", self._start_checks),
            ('record_check', "Record Check", self._record_check),
            ('check_status', "Check Status", self._show_check_status),
            ('required_checks', "Required Checks...", self._edit_requirements),
            ('refresh', "Refresh", self._load_checks),
        ])
        cols = ('ID', 'App', 'Applicant', 'Check', 'Status', 'Checked By', 'Check Date',
                'Follow-up', 'DBS Level', 'Re-check')
        self.checks_tree = self._make_tree(tab, cols)

    def _load_checks(self):
        try:
            rows = hiring.list_checks(self.auth, application_id=self._hiring_app_id(
                self.checks_app, required=False) if self.checks_app.get().strip() else None)
        except Exception as e:
            self._error(e)
            return
        self.checks_tree.delete(*self.checks_tree.get_children())
        for r in rows:
            self.checks_tree.insert('', tk.END, values=(
                r['check_id'], r.get('application_id') or '', r.get('applicant_name') or '',
                r['check_type'], r['status'], r.get('checked_by') or '',
                r.get('check_date') or '', r.get('follow_up_date') or '',
                r.get('dbs_level') or '', r.get('recheck_date') or ''))

    def _start_checks(self):
        try:
            app_id = self._hiring_app_id(self.checks_app)
            created = hiring.start_checks(self.auth, app_id)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.checks', default="Checks"),
                                "Started: " + (", ".join(created) or "nothing new"),
                                parent=self._parent())
            self._load_checks()
        except Exception as e:
            self._error(e)

    def _record_check(self):
        try:
            app_id = self._hiring_app_id(self.checks_app)
        except Exception as e:
            self._error(e)
            return
        dlg = _FormDialog(self._parent(), f"Record Check - application {app_id}", [
            ('check_type', 'Check', 'combo', list(hiring.CHECK_TYPES)),
            ('status', 'Status', 'combo', list(hiring.CHECK_STATUSES)),
            ('document_type', 'Right-to-work document', 'combo', [''] + list(hiring.RTW_DOCUMENTS)),
            ('share_code', 'Share code', 'entry', None),
            ('check_date', 'Check date (YYYY-MM-DD)', 'entry', None),
            ('follow_up_date', 'Follow-up / expiry date', 'entry', None),
            ('dbs_level', 'DBS level', 'combo', [''] + list(hiring.DBS_LEVELS)),
            ('certificate_number', 'DBS certificate number', 'entry', None),
            ('issue_date', 'DBS issue date', 'entry', None),
            ('update_service', 'On DBS update service', 'combo', ['no', 'yes']),
            ('recheck_date', 'DBS re-check date', 'entry', None),
            ('details', 'Details', 'text', None),
            ('notes', 'Notes', 'text', None),
        ])
        if not dlg.result:
            return
        d = dict(dlg.result)
        check, status = d.pop('check_type'), d.pop('status')
        if check != 'right_to_work':
            for k in ('document_type', 'share_code', 'follow_up_date'):
                d.pop(k, None)
        if check != 'dbs':
            for k in ('dbs_level', 'certificate_number', 'issue_date', 'update_service',
                      'recheck_date'):
                d.pop(k, None)
        try:
            hiring.record_check(self.auth, app_id, check, status, **d)
            self._load_checks()
            self._show_check_status(app_id)
        except Exception as e:
            self._error(e)

    def _status_text(self, app_id):
        state = hiring.check_status(self.auth, app_id)
        lines = [f"Application {app_id} ({state['job_type'] or 'any job'})", ""]
        lines += [f"{check}: {status}" for check, status in state['checks'].items()]
        refs = state['references']
        lines.append(f"references received: {refs['satisfactory']} satisfactory, "
                     f"{refs['unsatisfactory']} not (need {hiring.REFERENCES_REQUIRED})")
        lines += ["", "All required checks cleared." if state['cleared']
                  else "Outstanding: " + ", ".join(state['outstanding'])]
        return "\n".join(lines)

    def _show_check_status(self, app_id=None):
        try:
            app_id = app_id or self._hiring_app_id(self.checks_app)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.check_status',
                                   default="Check Status"), self._status_text(app_id),
                                parent=self._parent())
        except Exception as e:
            self._error(e)

    def _edit_requirements(self):
        try:
            current = hiring.list_requirements(self.auth)
        except Exception as e:
            self._error(e)
            return
        summary = "; ".join(f"{k}: {', '.join(v)}" for k, v in current.items())
        dlg = _FormDialog(self._parent(), "Required Checks", [
            ('job_type', "Job type ('*' = every job)", 'combo',
             ['*', 'permanent', 'fixed_term', 'part_time', 'temporary']),
            ('checks', 'Checks (comma separated: ' + ", ".join(hiring.REQUIREMENT_TYPES) + ')',
             'entry', None),
        ])
        if not dlg.result:
            return
        try:
            checks = [c.strip() for c in dlg.result['checks'].split(',') if c.strip()]
            now = hiring.set_required_checks(self.auth, dlg.result['job_type'], checks)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.saved', default="Saved"),
                                f"Was: {summary}\n\n{dlg.result['job_type']} now requires: "
                                + (", ".join(now) or "nothing"), parent=self._parent())
        except Exception as e:
            self._error(e)

    # References -------------------------------------------------------
    def _create_references_tab(self):
        tab = self._hiring_tab('references', "References")
        if tab is None:
            return
        self.refs_app = self._hiring_header(tab, _t(
            'gui.staff.staff_hr.recruitment.labels.references', default="References"), [
            ('request_reference', "Request Reference", self._request_reference),
            ('record_reference', "Record Reference", self._record_reference),
            ('refresh', "Refresh", self._load_references),
        ])
        cols = ('ID', 'App', 'Applicant', 'Referee', 'Email', 'Relationship', 'Status',
                'Satisfactory', 'Requested', 'Received')
        self.refs_tree = self._make_tree(tab, cols)

    def _load_references(self):
        try:
            rows = hiring.list_references(self.auth, self._hiring_app_id(
                self.refs_app, required=False) if self.refs_app.get().strip() else None)
        except Exception as e:
            self._error(e)
            return
        self.refs_tree.delete(*self.refs_tree.get_children())
        for r in rows:
            self.refs_tree.insert('', tk.END, values=(
                r['reference_id'], r['application_id'], r.get('applicant_name') or '',
                r['referee_name'], r.get('referee_email') or '', r.get('relationship') or '',
                r['status'], {1: 'yes', 0: 'NO'}.get(r.get('satisfactory'), ''),
                r.get('requested_at') or '', r.get('received_at') or ''))

    def _request_reference(self):
        try:
            app_id = self._hiring_app_id(self.refs_app)
        except Exception as e:
            self._error(e)
            return
        dlg = _FormDialog(self._parent(), f"Request Reference - application {app_id}", [
            ('referee_name', 'Referee name', 'entry', None),
            ('referee_email', 'Referee e-mail', 'entry', None),
            ('relationship', 'Relationship', 'entry', None),
        ])
        if not dlg.result:
            return
        try:
            ref_id = hiring.request_reference(self.auth, app_id, **dlg.result)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.requested', default="Requested"),
                                f"Reference #{ref_id} requested; the referee has been e-mailed.",
                                parent=self._parent())
            self._load_references()
        except Exception as e:
            self._error(e)

    def _record_reference(self):
        try:
            ref_id = self._tree_id(self.refs_tree, "a reference")
        except Exception as e:
            self._error(e)
            return
        dlg = _FormDialog(self._parent(), f"Record Reference #{ref_id}", [
            ('status', 'Status', 'combo', ['received', 'declined']),
            ('satisfactory', 'Satisfactory', 'combo', ['yes', 'no']),
            ('content', 'Reference / summary', 'text', None),
            ('notes', 'Notes', 'text', None),
        ])
        if not dlg.result:
            return
        d = dlg.result
        try:
            hiring.record_reference(self.auth, ref_id, status=d['status'],
                                    satisfactory=(d['satisfactory'] == 'yes')
                                    if d['status'] == 'received' else None,
                                    content=d.get('content', ''), notes=d.get('notes', ''))
            self._load_references()
        except Exception as e:
            self._error(e)

    # Offers -----------------------------------------------------------
    def _create_offers_tab(self):
        tab = self._hiring_tab('offers', "Offers")
        if tab is None:
            return
        self._hiring_header(tab, _t('gui.staff.staff_hr.recruitment.labels.offers',
                                    default="Offers"), [
            ('make_offer', "Make Offer", self._make_offer),
            ('offer_accepted', "Accepted", lambda: self._offer_response('accept')),
            ('offer_declined', "Declined", lambda: self._offer_response('decline')),
            ('withdraw_offer', "Withdraw", lambda: self._offer_response('withdraw')),
            ('confirm_start', "Confirm Start Date", self._confirm_start),
            ('refresh', "Refresh", self._load_offers),
        ], with_app_filter=False)
        filt = ttk.Frame(tab)
        filt.pack(fill=tk.X, padx=10)
        ttk.Label(filt, text=_t('gui.staff.staff_hr.recruitment.labels.status',
                                default="Status:")).pack(side=tk.LEFT, padx=5)
        self.offer_status = ttk.Combobox(filt, values=[
            'All', 'made', 'accepted', 'declined', 'withdrawn', 'hired'], width=12,
            state='readonly')
        self.offer_status.set('All')
        self.offer_status.pack(side=tk.LEFT, padx=5)
        self.offer_status.bind('<<ComboboxSelected>>', lambda e: self._load_offers())
        cols = ('ID', 'App', 'Applicant', 'Post', 'Type', 'Status', 'Salary', 'Grade', 'FTE',
                'Start', 'Confirmed', 'Manager')
        self.offers_tree = self._make_tree(tab, cols)

    def _load_offers(self):
        status = self.offer_status.get()
        try:
            rows = hiring.list_offers(self.auth, None if status == 'All' else status)
        except Exception as e:
            self._error(e)
            return
        self.offers_tree.delete(*self.offers_tree.get_children())
        for o in rows:
            self.offers_tree.insert('', tk.END, values=(
                o['offer_id'], o['application_id'], o.get('applicant_name') or '',
                o.get('job_title') or '', o['offer_type'], o['status'],
                '' if o.get('salary') is None else f"{o['salary']:,.0f}", o.get('grade') or '',
                o.get('fte') or '', o.get('start_date') or '',
                'yes' if o.get('start_confirmed') else '', o.get('manager_id') or ''))

    def _make_offer(self):
        dlg = _FormDialog(self._parent(), "Make Offer", [
            ('application_id', 'Application ID (blank = selected)', 'entry', None),
            ('offer_type', 'Offer type', 'combo', list(hiring.OFFER_TYPES)),
            ('salary', 'Full-time annual salary', 'entry', None),
            ('grade', 'Grade', 'entry', None),
            ('fte', 'FTE (e.g. 1.0, 0.6)', 'entry', None),
            ('start_date', 'Start date (YYYY-MM-DD)', 'entry', None),
            ('end_date', 'End date (fixed term only)', 'entry', None),
            ('probation_months', 'Probation months', 'entry', None),
            ('manager_id', 'Line manager username (blank = hiring manager)', 'entry', None),
            ('onboarding_template_id', 'Onboarding template ID (optional)', 'entry', None),
            ('conditions', 'Conditions (blank = the required checks)', 'text', None),
        ])
        if not dlg.result:
            return
        data = dict(dlg.result)
        typed = data.pop('application_id', '').strip()
        try:
            if typed and not typed.isdigit():
                raise ValueError("Application ID must be a number")
            app_id = int(typed) if typed else self._hiring_app_id(None)
            offer_id = hiring.make_offer(self.auth, app_id, **data)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.offer_made',
                                   default="Offer made"),
                                f"Offer #{offer_id} made and e-mailed to the applicant.",
                                parent=self._parent())
            self._load_offers()
            self._load_applications()
        except Exception as e:
            self._error(e)

    def _offer_response(self, action):
        try:
            offer_id = self._tree_id(self.offers_tree, "an offer")
        except Exception as e:
            self._error(e)
            return
        label = 'Reason' if action == 'withdraw' else 'Note'
        dlg = _FormDialog(self._parent(), f"Offer #{offer_id}: {action}", [
            ('note', label, 'text', None)])
        if not dlg.result:
            return
        try:
            fn = {'accept': hiring.accept_offer, 'decline': hiring.decline_offer,
                  'withdraw': hiring.withdraw_offer}[action]
            fn(self.auth, offer_id, dlg.result.get('note', ''))
            self._load_offers()
            self._load_applications()
            self._load_hire()
        except Exception as e:
            self._error(e)

    def _confirm_start(self):
        try:
            offer_id = self._tree_id(self.offers_tree, "an offer")
        except Exception as e:
            self._error(e)
            return
        dlg = _FormDialog(self._parent(), f"Confirm Start Date - offer #{offer_id}", [
            ('start_date', 'Start date (blank = as offered)', 'entry', None)])
        if not dlg.result:
            return
        try:
            offer = hiring.confirm_start_date(self.auth, offer_id, dlg.result.get('start_date'))
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.confirmed',
                                   default="Confirmed"),
                                f"Start date {offer['start_date']} confirmed; the offer is now "
                                "unconditional.", parent=self._parent())
            self._load_offers()
        except Exception as e:
            self._error(e)

    # Hire -------------------------------------------------------------
    def _create_hire_tab(self):
        tab = self._hiring_tab('hire', "Hire")
        if tab is None:
            return
        buttons = [
            ('hire_selected', "Hire Selected", self._hire_selected),
            ('check_status', "Check Status", self._hire_status),
            ('refresh', "Refresh", self._load_hire),
        ]
        if access.is_hr(self.auth):
            buttons.insert(2, ('send_reminders', "Send HR Reminders Now", self._send_reminders))
        self._hiring_header(tab, _t('gui.staff.staff_hr.recruitment.labels.hire',
                                    default="Accepted offers ready to hire"), buttons,
                            with_app_filter=False)
        cols = ('Offer', 'App', 'Applicant', 'Post', 'Start', 'Manager', 'Checks')
        self.hire_tree = self._make_tree(tab, cols)
        self.hire_log = tk.Text(tab, height=6, state=tk.DISABLED)
        self.hire_log.pack(fill=tk.X, padx=10, pady=(0, 10))

    def _load_hire(self):
        if not hasattr(self, 'hire_tree'):
            return
        try:
            rows = hiring.list_offers(self.auth, 'accepted')
            states = {o['offer_id']: hiring.check_status(self.auth, o['application_id'])
                      for o in rows}
        except Exception as e:
            self._error(e)
            return
        self.hire_tree.delete(*self.hire_tree.get_children())
        for o in rows:
            state = states[o['offer_id']]
            self.hire_tree.insert('', tk.END, values=(
                o['offer_id'], o['application_id'], o.get('applicant_name') or '',
                o.get('job_title') or '', o.get('start_date') or '', o.get('manager_id') or '',
                'cleared' if state['cleared'] else 'outstanding: '
                + ", ".join(state['outstanding'])))

    def _log_hire(self, text):
        self.hire_log.config(state=tk.NORMAL)
        self.hire_log.insert(tk.END, text + "\n")
        self.hire_log.see(tk.END)
        self.hire_log.config(state=tk.DISABLED)

    def _hire_status(self):
        try:
            offer_id = self._tree_id(self.hire_tree, "an accepted offer")
            offer = hiring.get_offer(self.auth, offer_id)
            messagebox.showinfo(_t('gui.staff.staff_hr.recruitment.dialogs.check_status',
                                   default="Check Status"),
                                self._status_text(offer['application_id']), parent=self._parent())
        except Exception as e:
            self._error(e)

    def _hire_selected(self):
        try:
            offer_id = self._tree_id(self.hire_tree, "an accepted offer")
        except Exception as e:
            self._error(e)
            return
        dlg = _FormDialog(self._parent(), f"Hire - offer #{offer_id}", [
            ('username', 'Username (blank = automatic)', 'entry', None),
            ('onboarding_template_id', 'Onboarding template ID (blank = automatic)', 'entry', None),
        ])
        if not dlg.result:
            return
        try:
            result = hiring.hire(self.auth, offer_id, username=dlg.result.get('username') or None,
                                 onboarding_template_id=dlg.result.get('onboarding_template_id')
                                 or None)
        except Exception as e:
            self._error(e)
            return
        self._log_hire(f"Offer #{offer_id}: hired as {result['username']}"
                       + (" (new account)" if result['account_created'] else '')
                       + f"; contract #{result['contract_id']}; onboarding "
                       + str(result.get('onboarding_assignment_id') or 'not assigned'))
        for w in result['warnings']:
            self._log_hire(f"  ! {w}")
        self._load_hire()
        self._load_offers()
        self._load_applications()

    def _send_reminders(self):
        try:
            from education_system.systems.university.domains.staff.domain.staff_hr import reminders
            result = reminders.run()
        except Exception as e:
            self._error(e)
            return
        self._log_hire("HR reminders: " + ", ".join(f"{k} {v}" for k, v in result.items()))


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
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.ok', default="OK"), command=self._ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text=_t('gui.staff.staff_hr.recruitment.buttons.cancel', default="Cancel"), command=self._cancel).pack(side=tk.LEFT, padx=5)

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
