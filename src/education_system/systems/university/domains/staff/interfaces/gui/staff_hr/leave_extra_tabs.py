"""Leave Management tabs for sickness absence, family leave, flexible
working and (HR) entitlements.

Mixed into ``LeaveManagementGUI``, which provides ``self.notebook``,
``self.root``, ``self.actor`` (the signed-in session) and ``self.me``
(their username). Every action goes through the ``domain/staff_hr``
modules, which check who may do what; this screen only hides buttons that
would be refused anyway.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from education_system.systems.university.domains.staff.domain.staff_hr import (
    absence,
    entitlement,
    family_leave,
    flexible_working,
    leave_rules,
)
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import (
    _access as hr_access,
)

logger = logging.getLogger(__name__)


def _yn(value) -> str:
    return 'Yes' if value else ('No' if value is not None else '')


class LeaveExtraTabsMixin:
    """Absence / Family Leave / Flexible Working / Entitlements tabs."""

    # ── shared helpers ──────────────────────────────────────────────────

    def _form(self, title: str, fields: list, width: int = 520) -> dict | None:
        """A modal form. ``fields``: (key, label, kind, default, options)
        with kind entry / combo / check / text. Returns the values or None."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        widgets = {}
        for row, field in enumerate(fields):
            key, label, kind = field[0], field[1], field[2]
            default = field[3] if len(field) > 3 else ''
            options = field[4] if len(field) > 4 else ()
            ttk.Label(frame, text=label, anchor=tk.W).grid(row=row, column=0, sticky=tk.NW,
                                                           padx=5, pady=4)
            if kind == 'check':
                var = tk.BooleanVar(value=bool(default))
                ttk.Checkbutton(frame, variable=var).grid(row=row, column=1, sticky=tk.W)
                widgets[key] = var
            elif kind == 'combo':
                var = tk.StringVar(value=default or '')
                ttk.Combobox(frame, textvariable=var, values=list(options), width=45,
                             state='readonly').grid(row=row, column=1, sticky=tk.W)
                widgets[key] = var
            elif kind == 'text':
                box = scrolledtext.ScrolledText(frame, height=4, width=46)
                box.insert('1.0', default or '')
                box.grid(row=row, column=1, sticky=tk.W)
                widgets[key] = box
            else:
                var = tk.StringVar(value='' if default is None else str(default))
                ttk.Entry(frame, textvariable=var, width=48).grid(row=row, column=1, sticky=tk.W)
                widgets[key] = var
        result: dict = {}

        def ok():
            for key, w in widgets.items():
                if isinstance(w, scrolledtext.ScrolledText):
                    result[key] = w.get('1.0', tk.END).strip()
                elif isinstance(w, tk.BooleanVar):
                    result[key] = bool(w.get())
                else:
                    result[key] = w.get().strip()
            result['_ok'] = True
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=12)
        ttk.Button(buttons, text="OK", command=ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=8)
        dialog.update_idletasks()
        dialog.geometry(f"{width}x{dialog.winfo_reqheight() + 10}")
        try:
            dialog.grab_set()
        except tk.TclError:
            pass
        self.root.wait_window(dialog)
        if not result.pop('_ok', False):
            return None
        return result

    def _run(self, action, done=None, success: str | None = None):
        """Run a domain call; show refusals as messages."""
        try:
            value = action()
        except (PermissionError, ValueError) as e:
            messagebox.showwarning("Not done", str(e))
            return None
        except Exception as e:
            logger.exception("leave action failed")
            messagebox.showerror("Error", f"Something went wrong: {e}")
            return None
        if success:
            messagebox.showinfo("Done", success)
        if done:
            done()
        return value

    def _tree(self, parent, columns, widths=None, height=8):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=height,
                            yscrollcommand=scroll.set)
        scroll.config(command=tree.yview)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=(widths or {}).get(col, 110), anchor=tk.W)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    @staticmethod
    def _selected(tree) -> int | None:
        sel = tree.selection()
        return int(sel[0]) if sel else None

    def _need(self, tree, what='an item'):
        value = self._selected(tree)
        if value is None:
            messagebox.showwarning("Select", f"Please select {what} first")
        return value

    @staticmethod
    def _bar(parent, buttons):
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, padx=10, pady=(8, 2))
        for label, command in buttons:
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=3)
        return bar

    # ── absence ─────────────────────────────────────────────────────────

    def _create_absence_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Absence")
        manager = hr_access.can(self, 'manager')
        ttk.Label(tab, text="Sickness Absence", style='Header.TLabel').pack(anchor=tk.W,
                                                                          padx=10, pady=(10, 0))
        buttons = [("Report Sickness", self._absence_report),
                   ("Record Return", self._absence_close),
                   ("Add Fit Note", self._absence_fit_note),
                   ("Confirm RTW Record", self._absence_confirm_rtw),
                   ("View", self._absence_view),
                   ("Refresh", self._absence_load)]
        if manager:
            buttons[4:4] = [("RTW Interview", self._absence_rtw),
                            ("Refer to OH", self._absence_refer),
                            ("Cancel Episode", self._absence_cancel)]
        self._bar(tab, buttons)
        self.absence_tree = self._tree(
            tab, ('ID', 'Name', 'Start', 'End', 'Days', 'Category', 'Certified', 'Status', 'RTW'),
            {'ID': 50, 'Name': 160, 'Category': 200, 'Days': 60}, height=9)
        self.absence_tree.bind('<Double-1>', lambda e: self._absence_view())

        lower = ttk.Notebook(tab)
        lower.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        due_tab = ttk.Frame(lower)
        lower.add(due_tab, text="Actions Due")
        self.absence_due_tree = self._tree(due_tab, ('Kind', 'Name', 'Detail'),
                                           {'Detail': 500}, height=5)
        if manager:
            alert_tab = ttk.Frame(lower)
            lower.add(alert_tab, text="Trigger Alerts")
            self._bar(alert_tab, [("Review Alert", self._absence_review_alert)])
            self.absence_alert_tree = self._tree(
                alert_tab, ('ID', 'Name', 'Trigger', 'Value', 'Threshold', 'Window', 'Raised'),
                height=4)
        oh_tab = ttk.Frame(lower)
        lower.add(oh_tab, text="Occupational Health")
        oh_buttons = [("Give / Decline Consent", self._oh_consent)]
        if hr_access.can(self, 'hr'):
            oh_buttons += [("Book Appointment", self._oh_book), ("Record Report", self._oh_report),
                           ("Close Referral", self._oh_close)]
        self._bar(oh_tab, oh_buttons)
        self.oh_tree = self._tree(oh_tab, ('ID', 'Name', 'Referred', 'Status', 'Appointment',
                                           'Fitness', 'Adjustments'), {'Adjustments': 260},
                                  height=4)
        self._absence_load()

    def _absence_load(self):
        try:
            for tree in (self.absence_tree, self.absence_due_tree, self.oh_tree):
                tree.delete(*tree.get_children())
            for ep in absence.episodes(self.actor):
                self.absence_tree.insert('', 'end', iid=str(ep['episode_id']), values=(
                    ep['episode_id'], ep['name'], ep['start_date'], ep['end_date'] or '(open)',
                    f"{float(ep['working_days'] or 0):g}", ep['reason_category'],
                    ep['certification'], ep['status'],
                    'Held' if ep['rtw'] else ('Due' if ep['status'] == 'closed' else '')))
            for i, item in enumerate(absence.due_actions(self.actor)):
                self.absence_due_tree.insert('', 'end', iid=str(i), values=(
                    item['kind'], item['name'], item['detail']))
            if hasattr(self, 'absence_alert_tree'):
                self.absence_alert_tree.delete(*self.absence_alert_tree.get_children())
                for a in absence.alerts(self.actor):
                    self.absence_alert_tree.insert('', 'end', iid=str(a['alert_id']), values=(
                        a['alert_id'], a['name'], a['trigger_kind'], f"{a['value']:g}",
                        f"{a['threshold']:g}", f"{a['window_start']} – {a['window_end']}",
                        (a['raised_at'] or '')[:10]))
            for r in absence.referrals(self.actor):
                self.oh_tree.insert('', 'end', iid=str(r['referral_id']), values=(
                    r['referral_id'], r['name'], (r['referred_at'] or '')[:10], r['status'],
                    r['appointment_date'] or '', r['fitness'] or '', r['adjustments'] or ''))
        except Exception as e:
            logger.exception("absence load failed")
            messagebox.showerror("Error", f"Failed to load absence: {e}")

    def _absence_report(self):
        fields = [('username', 'Person (username)', 'entry', self.me),
                  ('start', 'First day off (YYYY-MM-DD)', 'entry', leave_rules.today().isoformat()),
                  ('end', 'Last day off (blank if still off)', 'entry', ''),
                  ('category', 'Reason category', 'combo', 'Other', absence.REASONS),
                  ('detail', 'Medical detail (HR and the person only)', 'text', ''),
                  ('half', 'Went home part way through day one', 'check', False),
                  ('work', 'Work-related', 'check', False)]
        data = self._form("Report Sickness Absence", fields)
        if not data:
            return
        self._run(lambda: absence.record(
            self.actor, data['username'] or self.me, data['start'], data['end'] or None,
            reason_category=data['category'] or 'Other', reason_detail=data['detail'] or None,
            first_day_half=data['half'], work_related=data['work']),
            self._absence_load, "Absence recorded")

    def _absence_close(self):
        ep = self._need(self.absence_tree, 'an absence episode')
        if ep is None:
            return
        data = self._form("Record Return", [('end', 'Last day of absence (YYYY-MM-DD)', 'entry',
                                             leave_rules.today().isoformat())])
        if data:
            self._run(lambda: absence.close(self.actor, ep, data['end']), self._absence_load,
                      "Return recorded")

    def _absence_fit_note(self):
        ep = self._need(self.absence_tree, 'an absence episode')
        if ep is None:
            return
        data = self._form("Add Fit Note", [
            ('issued', 'Issued on (YYYY-MM-DD)', 'entry', leave_rules.today().isoformat()),
            ('from', 'Covers from', 'entry', ''), ('to', 'Covers to', 'entry', ''),
            ('assessment', 'Assessment', 'combo', 'not_fit', ('not_fit', 'may_be_fit')),
            ('adjustments', "'May be fit' adjustments", 'text', ''),
            ('condition', 'Condition (HR and the person only)', 'entry', ''),
            ('issued_by', 'Issued by', 'entry', '')])
        if data:
            self._run(lambda: absence.add_fit_note(
                self.actor, ep, data['issued'], data['from'], data['to'],
                assessment=data['assessment'] or 'not_fit',
                adjustments=data['adjustments'] or None, condition=data['condition'] or None,
                issued_by=data['issued_by'] or None), self._absence_load, "Fit note recorded")

    def _absence_rtw(self):
        ep = self._need(self.absence_tree, 'an absence episode')
        if ep is None:
            return
        data = self._form("Return-to-Work Interview", [
            ('date', 'Interview date', 'entry', leave_rules.today().isoformat()),
            ('fit', 'Fit to return', 'check', True),
            ('adjustments', 'Adjustments agreed', 'text', ''),
            ('support', 'Support offered', 'text', ''),
            ('wellbeing', 'Notes', 'text', ''),
            ('triggers', 'Trigger points discussed', 'check', False),
            ('oh', 'Occupational health referral recommended', 'check', False)])
        if data:
            self._run(lambda: absence.record_rtw(
                self.actor, ep, data['date'], fit_to_return=data['fit'],
                adjustments_agreed=data['adjustments'] or None,
                support_offered=data['support'] or None, wellbeing_notes=data['wellbeing'] or None,
                triggers_discussed=data['triggers'], oh_referral_recommended=data['oh']),
                self._absence_load, "Interview recorded")

    def _absence_confirm_rtw(self):
        ep = self._need(self.absence_tree, 'your absence episode')
        if ep is None:
            return
        data = self._form("Confirm Interview Record", [('comments', 'Your comments', 'text', '')])
        if data is not None:
            self._run(lambda: absence.confirm_rtw(self.actor, ep, data['comments'] or None),
                      self._absence_load, "Confirmed")

    def _absence_refer(self):
        ep = self._selected(self.absence_tree)
        default = ''
        if ep is not None:
            try:
                default = absence.episode(self.actor, ep)['user_id']
            except Exception:
                default = ''
        data = self._form("Refer to Occupational Health", [
            ('username', 'Person (username)', 'entry', default),
            ('reason', 'Reason for referral', 'text', ''),
            ('questions', 'Questions for OH', 'text', ''),
            ('link', 'Link to the selected episode', 'check', ep is not None)])
        if data:
            self._run(lambda: absence.refer(self.actor, data['username'], data['reason'],
                                            data['questions'] or None,
                                            ep if data['link'] else None),
                      self._absence_load, "Referral made; awaiting consent")

    def _absence_cancel(self):
        ep = self._need(self.absence_tree, 'an absence episode')
        if ep is None:
            return
        data = self._form("Cancel Episode", [('reason', 'Why (recorded in error ...)', 'entry', '')])
        if data:
            self._run(lambda: absence.cancel(self.actor, ep, data['reason']), self._absence_load,
                      "Episode cancelled")

    def _absence_view(self):
        ep = self._need(self.absence_tree, 'an absence episode')
        if ep is None:
            return
        e = self._run(lambda: absence.episode(self.actor, ep))
        if not e:
            return
        lines = [f"{e['name']} — {e['start_date']} to {e['end_date'] or '(open)'}",
                 f"Working days: {float(e['working_days'] or 0):g}",
                 f"Reason: {e['reason_category']}",
                 f"Detail: {e['reason_detail'] or ('(medical — HR and the person only)' if e.get('medical_hidden') else '')}",
                 f"Certification: {e['certification']}",
                 f"Work-related: {_yn(e['work_related'])}  Disability: {_yn(e['disability_related'])}"
                 f"  Pregnancy: {_yn(e['pregnancy_related'])}"]
        for n in e['fit_notes']:
            lines.append(f"Fit note {n['from_date']}–{n['to_date']}: {n['assessment']}"
                         + (f" ({n['adjustments']})" if n['adjustments'] else '')
                         + (f" — {n['condition']}" if n['condition'] else ''))
        if e['rtw']:
            r = e['rtw']
            lines.append(f"RTW interview {r['interview_date']} by {r['conducted_by']}: "
                         f"fit {_yn(r['fit_to_return'])}; adjustments: "
                         f"{r['adjustments_agreed'] or 'none'}; confirmed: "
                         f"{_yn(r['employee_confirmed'])}")
        s = absence.stats(e['user_id'])
        lines.append(f"Last {leave_rules.setting('absence_window_months')} months: "
                     f"{s['spells']} spells, {s['days']:g} days, Bradford {s['bradford']:g}")
        messagebox.showinfo("Absence", "\n".join(lines))

    def _absence_review_alert(self):
        alert = self._need(self.absence_alert_tree, 'an alert')
        if alert is None:
            return
        data = self._form("Review Trigger", [
            ('status', 'Outcome', 'combo', 'reviewed', ('reviewed', 'actioned', 'dismissed')),
            ('outcome', 'What was done', 'text', '')])
        if data:
            self._run(lambda: absence.review_alert(self.actor, alert, data['status'],
                                                   data['outcome']), self._absence_load,
                      "Alert updated")

    def _oh_consent(self):
        ref = self._need(self.oh_tree, 'a referral')
        if ref is None:
            return
        given = messagebox.askyesnocancel("Consent", "Do you consent to this occupational "
                                                      "health referral?")
        if given is not None:
            self._run(lambda: absence.consent(self.actor, ref, given), self._absence_load,
                      "Recorded")

    def _oh_book(self):
        ref = self._need(self.oh_tree, 'a referral')
        if ref is None:
            return
        data = self._form("Book OH Appointment", [('provider', 'Provider', 'entry', ''),
                                                  ('date', 'Appointment date', 'entry', '')])
        if data:
            self._run(lambda: absence.book_oh(self.actor, ref, data['provider'], data['date']),
                      self._absence_load, "Booked")

    def _oh_report(self):
        ref = self._need(self.oh_tree, 'a referral')
        if ref is None:
            return
        data = self._form("OH Report", [
            ('fitness', 'Fitness', 'combo', 'fit', absence.OH_FITNESS),
            ('adjustments', 'Recommended adjustments (shared with the manager)', 'text', ''),
            ('outcome', 'Medical outcome (HR and the person only)', 'text', ''),
            ('review', 'Review date', 'entry', '')])
        if data:
            self._run(lambda: absence.record_oh_report(
                self.actor, ref, data['fitness'], data['adjustments'] or None,
                data['outcome'] or None, data['review'] or None), self._absence_load,
                "Report recorded")

    def _oh_close(self):
        ref = self._need(self.oh_tree, 'a referral')
        if ref is not None:
            self._run(lambda: absence.close_referral(self.actor, ref), self._absence_load,
                      "Referral closed")

    # ── family leave ────────────────────────────────────────────────────

    def _create_family_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Family Leave")
        ttk.Label(tab, text="Maternity, Paternity, Adoption and Shared Parental Leave",
                  style='Header.TLabel').pack(anchor=tk.W, padx=10, pady=(10, 0))
        buttons = [("Notify Leave", self._family_notify), ("Edit", self._family_edit),
                   ("View / Pay", self._family_view), ("Cancel", self._family_cancel),
                   ("Refresh", self._family_load)]
        if hr_access.can(self, 'manager'):
            buttons[3:3] = [("Add KIT Day", self._family_kit),
                            ("Record Return", self._family_return)]
        if hr_access.can(self, 'hr'):
            buttons[2:2] = [("Confirm", self._family_confirm)]
        self._bar(tab, buttons)
        self.family_tree = self._tree(
            tab, ('ID', 'Name', 'Kind', 'Status', 'EWC / Match', 'Qualifying Week', 'Start',
                  'End', 'Return', 'Leave OK', 'Pay OK', 'KIT Days'),
            {'ID': 50, 'Name': 150, 'KIT Days': 70}, height=14)
        self.family_tree.bind('<Double-1>', lambda e: self._family_view())
        self._family_load()

    def _family_load(self):
        try:
            self.family_tree.delete(*self.family_tree.get_children())
            for c in family_leave.cases(self.actor):
                self.family_tree.insert('', 'end', iid=str(c['case_id']), values=(
                    c['case_id'], c['name'], c['kind_label'], c['status'],
                    c['ewc'] or c['matching_date'] or '', c['qualifying_week'] or '',
                    c['leave_start'] or '', c['leave_end'] or '',
                    c['actual_return_date'] or c['return_date'] or '', _yn(c['leave_eligible']),
                    _yn(c['pay_eligible']) if not c.get('pay_hidden') else '—',
                    f"{len(c['kit_days'])}/{c['kit_limit']}" if c['kit_limit'] else ''))
        except Exception as e:
            logger.exception("family leave load failed")
            messagebox.showerror("Error", f"Failed to load family leave: {e}")

    def _family_notify(self):
        data = self._form("Notify Family Leave", [
            ('username', 'Person (username)', 'entry', self.me),
            ('kind', 'Kind', 'combo', 'maternity', family_leave.KINDS),
            ('due', 'Expected due date (births)', 'entry', ''),
            ('matching', 'Matching date (adoption)', 'entry', ''),
            ('placement', 'Placement date (adoption / paternity)', 'entry', ''),
            ('start', 'Planned leave start', 'entry', ''),
            ('weeks', 'Weeks (blank = the most allowed)', 'entry', ''),
            ('used', 'Maternity / adoption weeks already used (shared parental)', 'entry', '0'),
            ('notes', 'Notes', 'text', '')])
        if not data:
            return
        self._run(lambda: family_leave.notify(
            self.actor, data['username'] or self.me, data['kind'] or 'maternity',
            due_date=data['due'] or None, matching_date=data['matching'] or None,
            placement_date=data['placement'] or None, leave_start=data['start'] or None,
            leave_weeks=int(data['weeks']) if data['weeks'] else None,
            statutory_weeks_used=int(data['used'] or 0), notes=data['notes'] or None),
            self._family_load, "Family leave notified")

    def _family_edit(self):
        cid = self._need(self.family_tree, 'a case')
        if cid is None:
            return
        c = self._run(lambda: family_leave.case(self.actor, cid))
        if not c:
            return
        hr = hr_access.can(self, 'hr')
        fields = [('leave_start', 'Leave start', 'entry', c['leave_start'] or ''),
                  ('leave_weeks', 'Weeks', 'entry', c['leave_weeks'] or ''),
                  ('return_date', 'Return date', 'entry', c['return_date'] or ''),
                  ('notes', 'Notes', 'text', c['notes'] or '')]
        if hr:
            fields += [('birth_date', 'Actual birth date', 'entry', c['birth_date'] or ''),
                       ('placement_date', 'Placement date', 'entry', c['placement_date'] or ''),
                       ('ewc', 'Expected week of childbirth (any day in it)', 'entry',
                        c['ewc'] or ''),
                       ('average_weekly_earnings', 'Average weekly earnings (£)', 'entry',
                        c['average_weekly_earnings'] or ''),
                       ('service_start', 'Continuous service from', 'entry',
                        c['service_start'] or ''),
                       ('statutory_weeks_used', 'Statutory weeks already used', 'entry',
                        c['statutory_weeks_used'] or 0)]
        data = self._form("Edit Family Leave", fields)
        if not data:
            return
        changes = {}
        for key, value in data.items():
            current = c.get(key)
            if str(value) != str(current if current is not None else ''):
                if key in ('leave_weeks', 'statutory_weeks_used'):
                    value = int(value) if value else None
                elif key == 'average_weekly_earnings':
                    value = float(value) if value else None
                else:
                    value = value or None
                changes[key] = value
        if changes:
            self._run(lambda: family_leave.update(self.actor, cid, **changes), self._family_load,
                      "Case updated")

    def _family_confirm(self):
        cid = self._need(self.family_tree, 'a case')
        if cid is not None:
            self._run(lambda: family_leave.confirm(self.actor, cid), self._family_load,
                      "Confirmed and booked")

    def _family_kit(self):
        cid = self._need(self.family_tree, 'a case')
        if cid is None:
            return
        data = self._form("Keeping-in-Touch Day", [('day', 'Day (YYYY-MM-DD)', 'entry', ''),
                                                   ('hours', 'Hours', 'entry', ''),
                                                   ('notes', 'Notes', 'entry', '')])
        if data:
            self._run(lambda: family_leave.add_kit_day(
                self.actor, cid, data['day'], float(data['hours']) if data['hours'] else None,
                data['notes'] or None), self._family_load, "KIT day recorded")

    def _family_return(self):
        cid = self._need(self.family_tree, 'a case')
        if cid is None:
            return
        data = self._form("Record Return", [('date', 'Back at work on', 'entry',
                                             leave_rules.today().isoformat())])
        if data:
            self._run(lambda: family_leave.record_return(self.actor, cid, data['date']),
                      self._family_load, "Return recorded")

    def _family_cancel(self):
        cid = self._need(self.family_tree, 'a case')
        if cid is None:
            return
        data = self._form("Cancel Case", [('reason', 'Reason', 'entry', '')])
        if data:
            self._run(lambda: family_leave.cancel(self.actor, cid, data['reason']),
                      self._family_load, "Cancelled")

    def _family_view(self):
        cid = self._need(self.family_tree, 'a case')
        if cid is None:
            return
        c = self._run(lambda: family_leave.case(self.actor, cid))
        if not c:
            return
        lines = [f"{c['name']} — {c['kind_label']} leave ({c['status']})",
                 f"EWC: {c['ewc'] or '-'}   Qualifying week: {c['qualifying_week'] or '-'}",
                 f"Leave: {c['leave_start'] or '?'} to {c['leave_end'] or '?'} "
                 f"({c['leave_weeks'] or '?'} weeks); return {c['return_date'] or '?'}",
                 f"Leave eligible: {_yn(c['leave_eligible'])}"]
        if c.get('pay_hidden'):
            lines.append("Pay: (the person, HR and payroll only)")
        else:
            total = sum(w['amount'] for w in c['pay_schedule'])
            lines.append(f"{c['pay_name']}: {_yn(c['pay_eligible'])}; "
                         f"{len(c['pay_schedule'])} weeks, £{total:,.2f} in all")
            for w in c['pay_schedule'][:8]:
                lines.append(f"  week {w['week']} from {w['from']}: £{w['amount']:.2f} "
                             f"({w['basis']})")
            if len(c['pay_schedule']) > 8:
                lines.append("  ...")
        if c['eligibility_notes']:
            lines.append("Notes: " + c['eligibility_notes'].replace('\n', '; '))
        if c['kit_days']:
            lines.append("KIT days: " + ', '.join(k['day'] for k in c['kit_days']))
        messagebox.showinfo("Family Leave", "\n".join(lines))

    # ── flexible working ────────────────────────────────────────────────

    def _create_flexible_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Flexible Working")
        ttk.Label(tab, text="Flexible Working Requests", style='Header.TLabel').pack(
            anchor=tk.W, padx=10, pady=(10, 0))
        buttons = [("New Request", self._fw_new), ("Withdraw", self._fw_withdraw),
                   ("Appeal", self._fw_appeal), ("View", self._fw_view),
                   ("Refresh", self._fw_load)]
        if hr_access.can(self, 'manager'):
            buttons[3:3] = [("Schedule Meeting", self._fw_meeting),
                            ("Record Consultation", self._fw_consult),
                            ("Extend Deadline", self._fw_extend), ("Decide", self._fw_decide),
                            ("Decide Appeal", self._fw_decide_appeal)]
        self._bar(tab, buttons)
        self.fw_tree = self._tree(
            tab, ('ID', 'Name', 'Submitted', 'Change', 'Requested', 'Status', 'Deadline',
                  'Approver'), {'ID': 50, 'Requested': 300}, height=16)
        self.fw_tree.bind('<Double-1>', lambda e: self._fw_view())
        self.fw_tree.tag_configure('overdue', background='#f8d7da')
        self._fw_load()

    def _fw_load(self):
        try:
            self.fw_tree.delete(*self.fw_tree.get_children())
            for r in flexible_working.requests(self.actor):
                self.fw_tree.insert('', 'end', iid=str(r['fw_id']), values=(
                    r['fw_id'], r['name'], (r['submitted_at'] or '')[:10], r['change_type'],
                    r['requested_pattern'], r['status'], r['deadline'] or '',
                    r['approver'] or ''), tags=('overdue',) if r['overdue'] else ())
        except Exception as e:
            logger.exception("flexible working load failed")
            messagebox.showerror("Error", f"Failed to load flexible working: {e}")

    def _fw_new(self):
        data = self._form("Flexible Working Request", [
            ('pattern', 'Working pattern you are asking for', 'text', ''),
            ('change', 'Kind of change', 'combo', 'hours', flexible_working.CHANGE_TYPES),
            ('days', 'New working days (e.g. 0,1,2,3 = Mon–Thu)', 'entry', ''),
            ('hours', 'New hours a week', 'entry', ''),
            ('start', 'From (YYYY-MM-DD)', 'entry', ''),
            ('until', 'Until (temporary change only)', 'entry', ''),
            ('effect', 'Anything to help consider it (optional)', 'text', '')])
        if not data:
            return
        days = [int(d) for d in data['days'].replace(' ', '').split(',') if d.isdigit()] \
            if data['days'] else None
        self._run(lambda: flexible_working.submit(
            self.actor, data['pattern'], change_type=data['change'] or 'hours',
            requested_days=days, requested_hours=float(data['hours']) if data['hours'] else None,
            requested_start=data['start'] or None, temporary_until=data['until'] or None,
            effect_notes=data['effect'] or None), self._fw_load, "Request submitted")

    def _fw_withdraw(self):
        fid = self._need(self.fw_tree, 'a request')
        if fid is not None and messagebox.askyesno("Withdraw", "Withdraw this request? It still "
                                                               "counts towards the yearly limit."):
            self._run(lambda: flexible_working.withdraw(self.actor, fid), self._fw_load,
                      "Withdrawn")

    def _fw_appeal(self):
        fid = self._need(self.fw_tree, 'a request')
        if fid is None:
            return
        data = self._form("Appeal", [('grounds', 'Grounds for appeal', 'text', '')])
        if data:
            self._run(lambda: flexible_working.appeal(self.actor, fid, data['grounds']),
                      self._fw_load, "Appeal made")

    def _fw_meeting(self):
        fid = self._need(self.fw_tree, 'a request')
        if fid is None:
            return
        data = self._form("Schedule Meeting", [('date', 'Meeting date', 'entry', '')])
        if data:
            self._run(lambda: flexible_working.schedule_meeting(self.actor, fid, data['date']),
                      self._fw_load, "Meeting arranged")

    def _fw_consult(self):
        fid = self._need(self.fw_tree, 'a request')
        if fid is None:
            return
        data = self._form("Record Consultation", [('notes', 'What was discussed', 'text', '')])
        if data:
            self._run(lambda: flexible_working.record_consultation(self.actor, fid,
                                                                   data['notes']),
                      self._fw_load, "Consultation recorded")

    def _fw_extend(self):
        fid = self._need(self.fw_tree, 'a request')
        if fid is None:
            return
        data = self._form("Extend Deadline", [('date', 'New decision date', 'entry', ''),
                                              ('note', 'How the person agreed', 'entry', '')])
        if data:
            self._run(lambda: flexible_working.extend(self.actor, fid, data['date'],
                                                      data['note']), self._fw_load, "Extended")

    def _fw_decide(self):
        fid = self._need(self.fw_tree, 'a request')
        if fid is None:
            return
        data = self._form("Decide Request", [
            ('outcome', 'Decision', 'combo', 'approved', flexible_working.OUTCOMES),
            ('reason', 'Refusal reason (statutory)', 'combo', '', flexible_working.REFUSAL_REASONS),
            ('notes', 'Explanation', 'text', ''),
            ('trial', 'Trial ends (trial approvals)', 'entry', ''),
            ('variation', 'Contract variation note (approvals)', 'text', '')], width=720)
        if data:
            self._run(lambda: flexible_working.decide(
                self.actor, fid, data['outcome'], notes=data['notes'] or None,
                refusal_reason=data['reason'] or None, trial_end=data['trial'] or None,
                contract_variation=data['variation'] or None), self._fw_load, "Decision recorded")

    def _fw_decide_appeal(self):
        fid = self._need(self.fw_tree, 'a request')
        if fid is None:
            return
        data = self._form("Decide Appeal", [('upheld', 'Uphold the appeal', 'check', False),
                                            ('notes', 'Reasons', 'text', ''),
                                            ('variation', 'Contract variation (if upheld)',
                                             'text', '')])
        if data:
            self._run(lambda: flexible_working.decide_appeal(
                self.actor, fid, data['upheld'], data['notes'], data['variation'] or None),
                self._fw_load, "Appeal decided")

    def _fw_view(self):
        fid = self._need(self.fw_tree, 'a request')
        if fid is None:
            return
        r = self._run(lambda: flexible_working.request(self.actor, fid))
        if not r:
            return
        fields = [('Name', r['name']), ('Submitted', r['submitted_at']),
                  ('Current pattern', r['current_pattern']),
                  ('Requested', r['requested_pattern']), ('From', r['requested_start']),
                  ('Until', r['temporary_until']), ('Status', r['status']),
                  ('Decide by', r['deadline']), ('Meeting', r['meeting_date']),
                  ('Consulted', _yn(r['consulted'])), ('Decided by', r['decision_by']),
                  ('Decision notes', r['decision_notes']),
                  ('Refusal reason', r['rejection_reason']), ('Trial ends', r['trial_end']),
                  ('Appeal', r['appeal_grounds']), ('Appeal notes', r['appeal_notes']),
                  ('Contract variation', r['contract_variation'])]
        messagebox.showinfo("Flexible Working",
                            "\n".join(f"{k}: {v}" for k, v in fields if v not in (None, '')))

    # ── entitlements (HR) ───────────────────────────────────────────────

    def _create_entitlements_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Entitlements")
        admin = hr_access.can(self, 'hr_admin')
        ttk.Label(tab, text="Leave Entitlements (HR)", style='Header.TLabel').pack(
            anchor=tk.W, padx=10, pady=(10, 0))
        buttons = [("Allocate Leave Year", self._ent_allocate),
                   ("Set Balance by Hand", self._ent_manual),
                   ("Working Pattern", self._ent_pattern),
                   ("Leaver Position", self._ent_leaver),
                   ("Add Closure Day", self._ent_closure),
                   ("Refresh", self._ent_load)]
        if admin:
            buttons[:0] = [("Edit Rule", self._ent_edit_rule), ("Edit Setting", self._ent_setting)]
        self._bar(tab, buttons)
        self.rules_tree = self._tree(
            tab, ('ID', 'Leave Type', 'Basis', 'Full-time Days', 'Pro Rata Service',
                  'Carries Over', 'Cap', 'Includes Bank Hols', 'Active'),
            {'ID': 50, 'Leave Type': 180, 'Basis': 160}, height=8)
        self.settings_tree = self._tree(tab, ('Key', 'Setting', 'Value'),
                                        {'Key': 220, 'Setting': 380, 'Value': 160}, height=10)
        self._ent_load()

    def _ent_load(self):
        try:
            self.rules_tree.delete(*self.rules_tree.get_children())
            for r in entitlement.rules():
                self.rules_tree.insert('', 'end', iid=str(r['leave_type_id']), values=(
                    r['leave_type_id'], r['leave_type_name'],
                    entitlement.BASIS_LABELS.get(r['basis'], r['basis']),
                    f"{float(r['full_time_days'] or 0):g}", _yn(r['pro_rata_service']),
                    _yn(r['carry_over']),
                    '' if r['carry_over_cap'] is None else f"{r['carry_over_cap']:g}",
                    _yn(r['includes_bank_holidays']), _yn(r['is_active'])))
            self.settings_tree.delete(*self.settings_tree.get_children())
            values = leave_rules.settings()
            for key, (_default, label, _kind) in leave_rules.DEFAULTS.items():
                self.settings_tree.insert('', 'end', iid=key, values=(key, label, values[key]))
        except Exception as e:
            logger.exception("entitlements load failed")
            messagebox.showerror("Error", f"Failed to load entitlements: {e}")

    def _ent_edit_rule(self):
        tid = self._need(self.rules_tree, 'a leave type')
        if tid is None:
            return
        r = entitlement.rule_for(tid)
        data = self._form(f"Rule: {r['leave_type_name']}", [
            ('basis', 'Basis', 'combo', r['basis'], entitlement.BASES),
            ('days', 'Full-time days a year', 'entry', r['full_time_days']),
            ('service', 'Pro rata for starters / leavers', 'check', r['pro_rata_service']),
            ('carry', 'Unused days carry over', 'check', r['carry_over']),
            ('cap', 'Carry-over cap (blank = policy setting)', 'entry',
             '' if r['carry_over_cap'] is None else r['carry_over_cap']),
            ('bh', 'Days already include bank holidays', 'check', r['includes_bank_holidays'])])
        if data:
            self._run(lambda: entitlement.set_rule(
                self.actor, tid, data['basis'], float(data['days']) if data['days'] else None,
                data['carry'], float(data['cap']) if data['cap'] else None, data['service'],
                data['bh']), self._ent_load, "Rule saved")

    def _ent_setting(self):
        sel = self.settings_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a setting first")
            return
        key = sel[0]
        data = self._form("Leave Policy", [('value', leave_rules.DEFAULTS[key][1], 'entry',
                                            leave_rules.setting(key))])
        if data:
            self._run(lambda: leave_rules.set_setting(self.actor, key, data['value']),
                      self._ent_load, "Saved")

    def _ent_allocate(self):
        data = self._form("Allocate Leave Year", [
            ('year', 'Leave year', 'entry', leave_rules.leave_year_of()),
            ('users', 'Only these usernames (comma separated, blank = everyone)', 'entry', ''),
            ('force', 'Also recalculate balances set by hand', 'check', False)])
        if not data:
            return
        users = [u.strip() for u in data['users'].split(',') if u.strip()] or None
        result = self._run(lambda: entitlement.allocate_year(
            self.actor, int(data['year']), users, data['force']))
        if result:
            messagebox.showinfo("Allocated", f"Leave year {result['year']}: {result['allocated']} "
                                             f"balances for {result['people']} people "
                                             f"({result['manual_kept']} set by hand kept)")

    def _ent_manual(self):
        types = {t['name']: t['leave_type_id'] for t in entitlement.rules() if t['is_active']}
        data = self._form("Set Balance by Hand", [
            ('username', 'Person (username)', 'entry', ''),
            ('type', 'Leave type', 'combo', '', sorted(types)),
            ('year', 'Leave year', 'entry', leave_rules.leave_year_of()),
            ('days', 'Allocated days', 'entry', ''), ('carried', 'Carried over', 'entry', '0'),
            ('note', 'Why', 'entry', '')])
        if data and data['type']:
            self._run(lambda: entitlement.set_manual(
                self.actor, data['username'], types[data['type']], int(data['year']),
                float(data['days'] or 0), float(data['carried'] or 0), data['note']),
                None, "Balance set")

    def _ent_pattern(self):
        data = self._form("Working Pattern", [
            ('username', 'Person (username)', 'entry', ''),
            ('days', 'Working days (0 = Mon ... 6 = Sun, comma separated)', 'entry', '0,1,2,3,4'),
            ('hours', 'Hours a week', 'entry', ''), ('fte', 'FTE (blank = from hours)', 'entry', ''),
            ('from', 'Effective from', 'entry', '')])
        if not data:
            return
        days = [int(d) for d in data['days'].replace(' ', '').split(',') if d.isdigit()]
        p = self._run(lambda: leave_rules.set_pattern(
            self.actor, data['username'], days, float(data['hours']) if data['hours'] else None,
            float(data['fte']) if data['fte'] else None, data['from'] or None))
        if p:
            messagebox.showinfo("Saved", f"{', '.join(leave_rules.WEEKDAYS[d] for d in p['work_days'])}"
                                         f"; FTE {p['fte']:g}. Run 'Allocate Leave Year' to "
                                         "apply it to balances (the daily job does too).")

    def _ent_leaver(self):
        data = self._form("Leaver Position", [('username', 'Person (username)', 'entry', ''),
                                              ('date', 'Leaving date', 'entry', '')])
        if not data:
            return
        rows = self._run(lambda: entitlement.leaver_position(self.actor, data['username'],
                                                             data['date'] or None))
        if rows is not None:
            messagebox.showinfo("Leaver Position", "\n".join(
                f"{r['leave_type_name']}: {r['position']:+g} days "
                f"(accrued {r['allocated_days']:g}, used {float(r['used_days'] or 0):g}, "
                f"bank holidays {r['bank_holiday_days']:g})" for r in rows) or "No balances")

    def _ent_closure(self):
        data = self._form("Closure Day", [('date', 'Date (YYYY-MM-DD)', 'entry', ''),
                                          ('name', 'Name', 'entry', 'University closure'),
                                          ('remove', 'Remove this closure instead', 'check',
                                           False)])
        if not data:
            return
        if data['remove']:
            self._run(lambda: leave_rules.remove_closure(self.actor, data['date']), None,
                      "Removed")
        else:
            self._run(lambda: leave_rules.add_closure(self.actor, data['date'], data['name']),
                      None, "Closure added")


__all__ = ['LeaveExtraTabsMixin']
