"""Safety screens: incidents, safeguarding & staffing, overseas checks and
the academic link (module, attendance credit, timetable clashes)."""

import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import ttk, messagebox, simpledialog
from tkinter.simpledialog import Dialog

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, call, run_async, make_tree, clear_tree, selected_iid, title_case,
    list_trip_staff, ask_text,
)
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.workspace import (
    Panel,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.safety'


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class ReportIncidentDialog(Dialog):
    """Report an incident on a trip (``incidents.report_incident``).

    Any participant or member of the trip's staff may report; the domain
    routes serious ones to Health & Safety, safeguarding concerns to the
    safeguarding team and conduct (with a named student) to a disciplinary
    case after the record is saved.
    """

    def __init__(self, parent, auth, trip_id, on_done=None, *, staff=False):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.on_done = on_done
        self.staff = staff
        super().__init__(parent, _t(f"{_K}.report_incident", default="Report an Incident"))

    def body(self, master):
        incidents = tm('incidents')
        r = 0

        def row(label, widget, sticky=tk.W):
            nonlocal r
            ttk.Label(master, text=label).grid(row=r, column=0, sticky=tk.NW, padx=5, pady=3)
            widget.grid(row=r, column=1, sticky=sticky, padx=5, pady=3)
            r += 1

        self.kind_var = tk.StringVar(value='incident')
        row(_t(f"{_K}.kind", default="What kind:"),
            ttk.Combobox(master, textvariable=self.kind_var, values=list(incidents.KINDS), state='readonly', width=18))
        self.severity_var = tk.StringVar(value='minor')
        row(_t(f"{_K}.severity", default="How serious:"),
            ttk.Combobox(master, textvariable=self.severity_var, values=list(incidents.SEVERITIES), state='readonly', width=18))
        self.when_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d %H:%M'))
        row(_t(f"{_K}.when", default="When (YYYY-MM-DD HH:MM):"), ttk.Entry(master, textvariable=self.when_var, width=20))
        self.where_var = tk.StringVar()
        row(_t(f"{_K}.where", default="Where:"), ttk.Entry(master, textvariable=self.where_var, width=50))
        self.description = tk.Text(master, width=50, height=4, wrap=tk.WORD)
        row(_t(f"{_K}.what", default="What happened:"), self.description)
        self.people_var = tk.StringVar()
        row(_t(f"{_K}.people", default="People involved:"), ttk.Entry(master, textvariable=self.people_var, width=50))
        self.actions = tk.Text(master, width=50, height=3, wrap=tk.WORD)
        row(_t(f"{_K}.actions", default="Action taken:"), self.actions)
        self.riddor_var = tk.StringVar(value='work it out')
        row(_t(f"{_K}.riddor", default="RIDDOR reportable:"),
            ttk.Combobox(master, textvariable=self.riddor_var, values=['work it out', 'yes', 'no'],
                         state='readonly', width=18))
        self.subject_var = tk.StringVar()
        if self.staff:
            row(_t(f"{_K}.subject", default="Student concerned (conduct):"),
                ttk.Entry(master, textvariable=self.subject_var, width=18))
        ttk.Label(master, text=_t(f"{_K}.routing_note",
                                  default="Serious incidents and injuries go to Health & Safety, safeguarding "
                                          "concerns to the safeguarding team, and conduct incidents about a named "
                                          "student to a disciplinary case."),
                  foreground='gray', wraplength=460, justify=tk.LEFT).grid(row=r, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(6, 0))
        return self.description

    def validate(self):
        if len(self.description.get('1.0', tk.END).strip()) < 5:
            messagebox.showwarning(self.title(), _t(f"{_K}.describe", default="Describe what happened."), parent=self)
            return False
        return True

    def apply(self):
        riddor = {'yes': True, 'no': False}.get(self.riddor_var.get())
        args = dict(occurred_at=self.when_var.get().strip() or None, location=self.where_var.get().strip(),
                    persons_involved=self.people_var.get().strip(),
                    actions_taken=self.actions.get('1.0', tk.END).strip(), riddor_reportable=riddor,
                    subject_id=self.subject_var.get().strip() or None)
        auth, trip_id, parent, on_done = self.auth, self.trip_id, self.parent, self.on_done
        kind, severity = self.kind_var.get(), self.severity_var.get()
        description = self.description.get('1.0', tk.END).strip()

        def done(incident_id):
            messagebox.showinfo(_t(f"{_K}.reported", default="Incident Reported"),
                                tf(f"{_K}.reported_text", "Incident #{id} has been recorded.", id=incident_id),
                                parent=parent)
            if on_done:
                on_done()

        run_async(parent, lambda: tm('incidents').report_incident(auth, trip_id, kind, severity, description, **args), done)


class IncidentsPanel(Panel):
    key = 'incidents'
    title = _t(f"{_K}.incidents_tab", default="Incidents")

    def build(self):
        self.rows = {}
        actions = self.bar()
        self.button(actions, _t(f"{_K}.report", default="Report Incident"), self.report)
        self.button(actions, _t(f"{_K}.review_close", default="Review && Close"), lambda: self.review(True))
        self.button(actions, _t(f"{_K}.review_keep", default="Add Review Note (keep open)"), lambda: self.review(False))
        self.button(actions, _t("common.refresh", default="Refresh"), self.reload)

        detail = ttk.LabelFrame(self, text=_t(f"{_K}.details", default="Details"), padding=6)
        detail.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        self.detail = tk.Text(detail, height=8, wrap=tk.WORD)
        self.detail.pack(fill=tk.X)

        self.tree = make_tree(self, [('id', '#', 40),
                                     ('occurred', _t(f"{_K}.occurred", default="When"), 130),
                                     ('kind', _t(f"{_K}.kind_col", default="Kind"), 90),
                                     ('severity', _t(f"{_K}.severity_col", default="Severity"), 80),
                                     ('status', _t(f"{_K}.status", default="Status"), 90),
                                     ('reporter', _t(f"{_K}.reporter", default="Reported By"), 100),
                                     ('riddor', 'RIDDOR', 60),
                                     ('hs', _t(f"{_K}.hs_ref", default="H&S Ref"), 120),
                                     ('case', _t(f"{_K}.case_ref", default="Safeguarding / Conduct Ref"), 170)], height=8)
        self.tree.tag_configure('serious', background='#fbe3d0')
        self.tree.tag_configure('critical', background='#f7cccc')
        self.tree.bind('<<TreeviewSelect>>', lambda _e: self._show_detail())

    def clear(self):
        clear_tree(self.tree)
        self.detail.delete('1.0', tk.END)

    def load(self, trip_id):
        self.clear()
        self.rows = {}
        for row in tm('incidents').list_incidents(self.auth, trip_id):
            iid = str(row['id'])
            self.rows[iid] = row
            self.tree.insert('', 'end', iid=iid, tags=(row['severity'],), values=(
                row['id'], (row.get('occurred_at') or '')[:16], title_case(row['kind']), title_case(row['severity']),
                title_case(row['status']), row.get('reported_by') or '', 'yes' if row.get('riddor_reportable') else '',
                row.get('hs_reference') or '', row.get('conduct_case_ref') or ''))

    def _show_detail(self):
        row = self.rows.get(selected_iid(self.tree) or '')
        self.detail.delete('1.0', tk.END)
        if row:
            self.detail.insert('1.0', "\n".join(x for x in (
                f"Where: {row.get('location') or 'not recorded'}",
                f"What happened: {row.get('description') or ''}",
                f"People involved: {row.get('persons_involved') or 'not recorded'}",
                f"Action taken: {row.get('actions_taken') or 'none recorded'}",
                f"Review: {row.get('review_notes')}" if row.get('review_notes') else '') if x))

    def report(self):
        if self.need_trip():
            staff = tm('trips').can_manage_trip(self.auth, self.trip_id)
            ReportIncidentDialog(self.winfo_toplevel(), self.auth, self.trip_id, self.changed, staff=staff)

    def review(self, close):
        row = self.rows.get(selected_iid(self.tree) or '')
        if not row:
            messagebox.showwarning(self.title, _t(f"{_K}.pick_incident", default="Select an incident."),
                                   parent=self.winfo_toplevel())
            return
        notes = ask_text(self.winfo_toplevel(), _t(f"{_K}.review_title", default="Review Incident"),
                         _t(f"{_K}.review_prompt", default="What was reviewed or done:"))
        if notes:
            ok, _ = call(self, tm('incidents').review_incident, self.auth, row['id'], notes, close)
            if ok:
                self.changed()


# ---------------------------------------------------------------------------
# Safeguarding & staffing
# ---------------------------------------------------------------------------

class SafeguardingPanel(Panel):
    key = 'safeguarding'
    title = _t(f"{_K}.safeguarding_tab", default="Safeguarding & Staffing")

    def build(self):
        self.people = {}
        top = ttk.LabelFrame(self, text=_t(f"{_K}.staffing", default="Staffing"), padding=6)
        top.pack(fill=tk.BOTH, expand=True)
        bar = ttk.Frame(top)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(bar, text=_t(f"{_K}.refresh_checks", default="Refresh DBS / First-aid Checks"),
                   command=self.refresh_checks).pack(side=tk.LEFT)
        ttk.Button(bar, text=_t("common.refresh", default="Refresh"), command=self.reload).pack(side=tk.LEFT, padx=5)
        self.staffing_var = tk.StringVar()
        ttk.Label(top, textvariable=self.staffing_var, foreground='#a33', wraplength=1100,
                  justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 4))
        self.staff_tree = make_tree(top, [('name', _t(f"{_K}.staff_name", default="Staff"), 200),
                                          ('role', _t(f"{_K}.role", default="Role"), 110),
                                          ('aider', _t(f"{_K}.first_aider", default="First Aider"), 90),
                                          ('dbs', 'DBS', 90),
                                          ('checked', _t(f"{_K}.checked", default="Checked"), 140)], height=4)

        bottom = ttk.LabelFrame(self, text=_t(f"{_K}.participants", default="Participants"), padding=6)
        bottom.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        pbar = ttk.Frame(bottom)
        pbar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(pbar, text=_t(f"{_K}.record_conduct", default="Record Code of Conduct (signed copy)"),
                   command=self.record_conduct).pack(side=tk.LEFT)
        ttk.Button(pbar, text=_t(f"{_K}.record_consent", default="Record Parental Consent..."),
                   command=self.record_consent).pack(side=tk.LEFT, padx=5)
        self.people_tree = make_tree(bottom, [('name', _t(f"{_K}.name", default="Name"), 200),
                                              ('student', _t(f"{_K}.student", default="Student"), 90),
                                              ('age', _t(f"{_K}.age", default="Age on Trip"), 90),
                                              ('status', _t(f"{_K}.status", default="Status"), 90),
                                              ('checks', _t(f"{_K}.checks", default="Outstanding"), 420)], height=6)
        self.people_tree.tag_configure('problem', background='#fff1bf')

    def clear(self):
        clear_tree(self.staff_tree)
        clear_tree(self.people_tree)
        self.staffing_var.set('')

    def load(self, trip_id):
        self.clear()
        for s in list_trip_staff(trip_id):
            self.staff_tree.insert('', 'end', values=(s['name'], title_case(s['role']),
                                                      'yes' if s.get('first_aider') else '',
                                                      title_case(s.get('dbs_status'), 'not checked'),
                                                      s.get('dbs_checked_at') or ''))
        auth, start = self.auth, self.trip.get('start_date')

        def work():
            safeguarding, db = tm('safeguarding'), tm('database')
            problems = safeguarding.staffing_check(trip_id)
            people = tm('registrations').list_participants(auth, trip_id)
            checks = {c['participant_id']: c['problems'] for c in safeguarding.participant_checks(trip_id)}
            with db.read_connection() as c:
                ages = {p['id']: safeguarding.age_check(p['student_id'], start, conn=c)
                        for p in people if p.get('student_id')}
            return problems, people, checks, ages

        def done(result):
            if self.trip_id != trip_id:
                return
            problems, people, checks, ages = result
            self.staffing_var.set("\n".join(f"• {p}" for p in problems)
                                  or _t(f"{_K}.staffing_ok", default="Staffing meets the ratio, first-aid and DBS rules."))
            self.people = {str(p['id']): p for p in people}
            clear_tree(self.people_tree)
            for p in people:
                age = ages.get(p['id']) or {}
                outstanding = checks.get(p['id']) or []
                self.people_tree.insert('', 'end', iid=str(p['id']), tags=('problem',) if outstanding else (),
                                        values=(p.get('name') or '', p.get('student_id') or 'staff',
                                                age.get('age') if age.get('age') is not None else '?',
                                                title_case(p['status']), "; ".join(outstanding) or 'OK'))

        run_async(self, work, done, status=self.ws.status)

    def _participant(self):
        p = self.people.get(selected_iid(self.people_tree) or '')
        if not p:
            messagebox.showwarning(self.title, _t(f"{_K}.pick_participant", default="Select a participant."),
                                   parent=self.winfo_toplevel())
        return p

    def refresh_checks(self):
        if self.need_trip():
            trip_id, auth = self.trip_id, self.auth
            self.async_call(lambda: tm('safeguarding').refresh_staff_checks(auth, trip_id),
                            message=lambda problems: ("\n".join(problems) or
                                                      _t(f"{_K}.staffing_ok", default="Staffing meets the ratio, first-aid and DBS rules.")))

    def record_conduct(self):
        p = self._participant()
        if p and messagebox.askyesno(self.title, tf(f"{_K}.confirm_conduct",
                                                    "Record that {name} has signed the code of conduct?",
                                                    name=p.get('name')), parent=self.winfo_toplevel()):
            ok, _ = call(self, tm('safeguarding').record_conduct_acceptance, self.auth, p['id'])
            if ok:
                self.changed()

    def record_consent(self):
        p = self._participant()
        if not p:
            return
        adult = simpledialog.askstring(self.title, tf(f"{_K}.consent_prompt",
                                                      "Name of the parent or guardian who consented for {name}:",
                                                      name=p.get('name')), parent=self.winfo_toplevel())
        if adult:
            ok, _ = call(self, tm('safeguarding').record_parental_consent, self.auth, p['id'], adult)
            if ok:
                self.changed()


# ---------------------------------------------------------------------------
# Overseas
# ---------------------------------------------------------------------------

class DocumentsDialog(Dialog):
    """Passport expiry and visa status for one participant (``overseas.participant_documents``)."""

    def __init__(self, parent, auth, participant_id, name=""):
        self.auth = auth
        self.participant_id = int(participant_id)
        self.name = name
        self.problems = None
        super().__init__(parent, _t(f"{_K}.documents", default="Travel Documents"))

    def body(self, master):
        if self.name:
            ttk.Label(master, text=self.name, font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))
        ttk.Label(master, text=_t(f"{_K}.passport_expiry", default="Passport expiry (YYYY-MM-DD):")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=4)
        self.expiry_var = tk.StringVar()
        entry = ttk.Entry(master, textvariable=self.expiry_var, width=14)
        entry.grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(master, text=_t(f"{_K}.visa", default="Visa:")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=4)
        self.visa_var = tk.StringVar(value='not_required')
        ttk.Combobox(master, textvariable=self.visa_var, values=list(tm('overseas').VISA_STATUSES),
                     state='readonly', width=14).grid(row=2, column=1, sticky=tk.W, padx=5)
        return entry

    def apply(self):
        ok, problems = call(self.parent, tm('overseas').participant_documents, self.auth, self.participant_id,
                            self.expiry_var.get().strip() or None, self.visa_var.get())
        if ok:
            self.problems = problems
            messagebox.showinfo(self.title(), "\n".join(problems) if problems else
                                _t(f"{_K}.documents_ok", default="Documents recorded: nothing outstanding."),
                                parent=self.parent)


class OverseasPanel(Panel):
    key = 'overseas'
    title = _t(f"{_K}.overseas_tab", default="Overseas")

    def build(self):
        self.people = {}
        overseas = tm('overseas')
        grid = ttk.Frame(self)
        grid.pack(fill=tk.X)

        ttk.Label(grid, text=_t(f"{_K}.country", default="Country:")).grid(row=0, column=0, sticky=tk.W, pady=3)
        self.country_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self.country_var, width=24).grid(row=0, column=1, sticky=tk.W, padx=5)
        self.overseas_var = tk.BooleanVar()
        ttk.Checkbutton(grid, text=_t(f"{_K}.is_overseas", default="Overseas trip"),
                        variable=self.overseas_var).grid(row=0, column=2, sticky=tk.W)
        ttk.Button(grid, text=_t(f"{_K}.save_country", default="Save"), command=self.save_country).grid(row=0, column=3, padx=5)
        self.link = tk.Label(grid, text='', fg='#0645ad', cursor='hand2', font=('Arial', 9, 'underline'))
        self.link.grid(row=0, column=4, sticky=tk.W, padx=10)
        self.link.bind('<Button-1>', lambda _e: self.open_advice())

        ttk.Label(grid, text=_t(f"{_K}.fcdo", default="FCDO advice:")).grid(row=1, column=0, sticky=tk.W, pady=3)
        self.level_var = tk.StringVar()
        self.level_labels = {overseas.FCDO_LABELS[k]: k for k in overseas.FCDO_LEVELS}
        ttk.Combobox(grid, textvariable=self.level_var, values=list(self.level_labels), state='readonly',
                     width=46).grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5)
        ttk.Label(grid, text=_t(f"{_K}.checked_on", default="Checked on:")).grid(row=1, column=3, sticky=tk.E)
        self.checked_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(grid, textvariable=self.checked_var, width=12).grid(row=1, column=4, sticky=tk.W, padx=5)
        ttk.Button(grid, text=_t(f"{_K}.record_fcdo", default="Record FCDO Check"),
                   command=self.record_fcdo).grid(row=1, column=5, padx=5)

        ttk.Label(grid, text=_t(f"{_K}.insurance", default="Insurance ref:")).grid(row=2, column=0, sticky=tk.W, pady=3)
        self.insurance_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self.insurance_var, width=24).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Button(grid, text=_t(f"{_K}.record_insurance", default="Record Insurance"),
                   command=self.record_insurance).grid(row=2, column=2, sticky=tk.W)
        self.current_var = tk.StringVar()
        ttk.Label(self, textvariable=self.current_var, foreground='#444', wraplength=1100,
                  justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 0))

        problems = ttk.LabelFrame(self, text=_t(f"{_K}.overseas_problems", default="Overseas checks outstanding"), padding=6)
        problems.pack(fill=tk.X, pady=6)
        self.problems = tk.Text(problems, height=5, wrap=tk.WORD)
        self.problems.pack(fill=tk.X)

        docs = ttk.LabelFrame(self, text=_t(f"{_K}.participant_documents", default="Participant documents"), padding=6)
        docs.pack(fill=tk.BOTH, expand=True)
        dbar = ttk.Frame(docs)
        dbar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(dbar, text=_t(f"{_K}.record_documents", default="Record Passport / Visa..."),
                   command=self.record_documents).pack(side=tk.LEFT)
        self.people_tree = make_tree(docs, [('name', _t(f"{_K}.name", default="Name"), 220),
                                            ('student', _t(f"{_K}.student", default="Student"), 100),
                                            ('status', _t(f"{_K}.status", default="Status"), 100)], height=5)

    def clear(self):
        self.country_var.set('')
        self.current_var.set('')
        self.problems.delete('1.0', tk.END)
        clear_tree(self.people_tree)
        self.link.configure(text='')

    def load(self, trip_id):
        overseas = tm('overseas')
        trip = self.trip
        self.country_var.set(trip.get('country') or '')
        self.overseas_var.set(bool(int(trip.get('is_overseas') or 0)))
        self.insurance_var.set(trip.get('insurance_reference') or '')
        level = trip.get('fcdo_advice_level')
        self.level_var.set(overseas.FCDO_LABELS.get(level, ''))
        url = overseas.advice_url(trip.get('country'))
        self.link.configure(text=tf(f"{_K}.advice_link", "GOV.UK travel advice: {url}", url=url) if url else '')
        self.current_var.set(tf(
            f"{_K}.current", "FCDO: {level} (checked {when} by {who}). Insurance: {ins}.",
            level=overseas.FCDO_LABELS.get(level, 'not checked'), when=(trip.get('fcdo_checked_at') or '-')[:10],
            who=trip.get('fcdo_checked_by') or '-',
            ins=(f"{trip['insurance_reference']} (registered {(trip.get('insurance_registered_at') or '')[:10]})"
                 if trip.get('insurance_reference') else 'not registered')))
        self.problems.delete('1.0', tk.END)
        problems = overseas.overseas_problems(trip_id)
        self.problems.insert('1.0', "\n".join(f"• {p}" for p in problems) or (
            _t(f"{_K}.not_overseas", default="Not an overseas trip.") if not int(trip.get('is_overseas') or 0)
            else _t(f"{_K}.overseas_ok", default="All overseas checks are in place.")))
        clear_tree(self.people_tree)
        self.people = {}
        try:
            for p in tm('registrations').list_participants(self.auth, trip_id):
                self.people[str(p['id'])] = p
                self.people_tree.insert('', 'end', iid=str(p['id']), values=(
                    p.get('name') or '', p.get('student_id') or 'staff', title_case(p['status'])))
        except PermissionError:
            pass

    def open_advice(self):
        url = tm('overseas').advice_url(self.country_var.get().strip())
        if url:
            webbrowser.open(url)

    def save_country(self):
        if self.need_trip():
            ok, _ = call(self, tm('trips').update_trip_record, self.auth, self.trip_id,
                         country=self.country_var.get().strip() or None, is_overseas=self.overseas_var.get())
            if ok:
                self.changed()

    def record_fcdo(self):
        if not self.need_trip():
            return
        level = self.level_labels.get(self.level_var.get())
        if not level:
            messagebox.showwarning(self.title, _t(f"{_K}.pick_level", default="Choose the FCDO advice level."),
                                   parent=self.winfo_toplevel())
            return
        ok, result = call(self, tm('overseas').record_fcdo_check, self.auth, self.trip_id, level,
                          self.checked_var.get().strip() or None)
        if ok:
            self.changed()

    def record_insurance(self):
        if self.need_trip():
            ok, _ = call(self, tm('overseas').record_insurance, self.auth, self.trip_id, self.insurance_var.get())
            if ok:
                self.changed()

    def record_documents(self):
        p = self.people.get(selected_iid(self.people_tree) or '')
        if not p:
            messagebox.showwarning(self.title, _t(f"{_K}.pick_participant", default="Select a participant."),
                                   parent=self.winfo_toplevel())
            return
        dialog = DocumentsDialog(self.winfo_toplevel(), self.auth, p['id'], p.get('name') or '')
        if dialog.problems is not None:
            self.changed()


# ---------------------------------------------------------------------------
# Academic link
# ---------------------------------------------------------------------------

class AcademicPanel(Panel):
    key = 'academic'
    title = _t(f"{_K}.academic_tab", default="Academic")

    def build(self):
        grid = ttk.Frame(self)
        grid.pack(fill=tk.X)
        ttk.Label(grid, text=_t(f"{_K}.module", default="Module code:")).grid(row=0, column=0, sticky=tk.W, pady=3)
        self.module_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self.module_var, width=16).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(grid, text=_t(f"{_K}.link", default="Link Module"), command=self.link).grid(row=0, column=2, padx=5)
        ttk.Button(grid, text=_t(f"{_K}.unlink", default="Unlink"), command=self.unlink).grid(row=0, column=3)
        self.counts_var = tk.BooleanVar()
        ttk.Checkbutton(grid, text=_t(f"{_K}.counts", default="Going on the trip counts as attendance for the module"),
                        variable=self.counts_var, command=self.set_counts).grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=4)
        self.current_var = tk.StringVar()
        ttk.Label(self, textvariable=self.current_var, foreground='#444').pack(anchor=tk.W, pady=(4, 6))

        bar = self.bar()
        self.button(bar, _t(f"{_K}.check_clashes", default="Check Timetable Clashes"), self.check_clashes)
        self.summary_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.summary_var).pack(side=tk.LEFT, padx=10)
        self.tree = make_tree(self, [('name', _t(f"{_K}.name", default="Name"), 180),
                                     ('student', _t(f"{_K}.student", default="Student"), 90),
                                     ('date', _t(f"{_K}.date", default="Date"), 90),
                                     ('time', _t(f"{_K}.time", default="Time"), 100),
                                     ('module', _t(f"{_K}.module_col", default="Module"), 90),
                                     ('room', _t(f"{_K}.room", default="Room"), 120),
                                     ('linked', _t(f"{_K}.linked", default="Trip's Module"), 100)], height=10)
        self.tree.tag_configure('linked', background='#e6f0ff')

    def clear(self):
        self.module_var.set('')
        self.current_var.set('')
        self.summary_var.set('')
        clear_tree(self.tree)

    def load(self, trip_id):
        trip = self.trip
        self.module_var.set(trip.get('module_code') or '')
        self.counts_var.set(bool(int(trip.get('counts_as_attendance') or 0)))
        self.current_var.set(tf(f"{_K}.academic_current", "Linked module: {m}. Attendance credit: {c}.",
                                m=trip.get('module_code') or 'none',
                                c='on' if int(trip.get('counts_as_attendance') or 0) else 'off'))
        clear_tree(self.tree)
        self.summary_var.set('')

    def link(self):
        if self.need_trip():
            ok, _ = call(self, tm('academic').link_module, self.auth, self.trip_id, self.module_var.get())
            if ok:
                self.changed()

    def unlink(self):
        if self.need_trip():
            ok, _ = call(self, tm('academic').link_module, self.auth, self.trip_id, None)
            if ok:
                self.changed()

    def set_counts(self):
        if self.need_trip():
            ok, _ = call(self, tm('academic').set_counts_as_attendance, self.auth, self.trip_id, self.counts_var.get())
            if ok:
                self.changed()
            else:
                self.counts_var.set(not self.counts_var.get())

    def check_clashes(self):
        if not self.need_trip():
            return
        trip_id = self.trip_id

        def done(clashes):
            if self.trip_id != trip_id:
                return
            clear_tree(self.tree)
            sessions = 0
            for person in clashes:
                for s in person['sessions']:
                    sessions += 1
                    self.tree.insert('', 'end', tags=('linked',) if s['linked_module'] else (), values=(
                        person.get('name') or '', person['student_id'], s.get('date') or '',
                        f"{s.get('start_time') or ''}-{s.get('end_time') or ''}", s.get('module_code') or '',
                        s.get('room') or '', 'yes' if s['linked_module'] else ''))
            self.summary_var.set(tf(f"{_K}.clash_summary", "{people} participant(s) miss {sessions} session(s).",
                                    people=len(clashes), sessions=sessions))

        run_async(self, lambda: tm('academic').timetable_clashes(trip_id), done, status=self.ws.status)
