"""Planning screens: approvals (per trip and the approver's queue) and the
risk assessment editor."""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, call, show_error, make_tree, clear_tree, selected_iid, title_case,
)
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.workspace import (
    Panel, BAND_COLOURS,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.planning'


def _stage_label(stage):
    return tm('approvals').STAGE_LABELS.get(stage, title_case(stage))


# ---------------------------------------------------------------------------
# Approvals for one trip
# ---------------------------------------------------------------------------

class ApprovalsPanel(Panel):
    key = 'approvals'
    title = _t(f"{_K}.approvals_tab", default="Approvals & Status")

    def build(self):
        self.info_var = tk.StringVar()
        ttk.Label(self, textvariable=self.info_var, font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 6))

        actions = self.bar()
        self.button(actions, _t(f"{_K}.submit", default="Submit for Approval"), self.submit)
        self.button(actions, _t("common.refresh", default="Refresh"), self.reload)

        status = self.bar()
        ttk.Label(status, text=_t(f"{_K}.move_to", default="Move trip to:")).pack(side=tk.LEFT)
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(status, textvariable=self.target_var, state='readonly', width=14)
        self.target_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(status, text=_t(f"{_K}.reason", default="Reason:")).pack(side=tk.LEFT)
        self.reason_var = tk.StringVar()
        ttk.Entry(status, textvariable=self.reason_var, width=40).pack(side=tk.LEFT, padx=5)
        self.button(status, _t(f"{_K}.change_status", default="Change Status"), self.change_status)

        gate = ttk.LabelFrame(self, text=_t(f"{_K}.before_open", default="Before it can open for registration"), padding=6)
        gate.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        self.gate_text = tk.Text(gate, height=6, wrap=tk.WORD)
        self.gate_text.pack(fill=tk.X)

        self.tree = make_tree(self, [('stage', _t(f"{_K}.stage", default="Stage"), 140),
                                     ('decision', _t(f"{_K}.decision", default="Decision"), 110),
                                     ('by', _t(f"{_K}.by", default="Decided By"), 120),
                                     ('at', _t(f"{_K}.at", default="Decided At"), 140),
                                     ('comments', _t(f"{_K}.comments", default="Comments"), 420)], height=6)

    def clear(self):
        self.info_var.set(_t(f"{_K}.pick", default="Choose a trip above."))
        clear_tree(self.tree)
        self.gate_text.delete('1.0', tk.END)
        self.target_combo['values'] = []

    def load(self, trip_id):
        approvals = tm('approvals')
        state = approvals.approval_state(trip_id)
        problems = approvals.gate_problems(trip_id, 'open')
        trip = self.trip
        self.info_var.set(tf(f"{_K}.info", "{name} — status {status} (version {version}). Stages needed: {stages}.",
                             name=trip['trip_name'], status=title_case(trip['status']),
                             version=trip.get('version') or 1,
                             stages=", ".join(_stage_label(s) for s in state['required'])))
        clear_tree(self.tree)
        for stage, row in state['stages'].items():
            self.tree.insert('', 'end', values=(_stage_label(stage), title_case(row['decision']),
                                                row.get('decided_by') or '', row.get('decided_at') or '',
                                                row.get('comments') or ''))
        self.gate_text.delete('1.0', tk.END)
        self.gate_text.insert('1.0', "\n".join(f"• {p}" for p in problems)
                              or _t(f"{_K}.gate_clear", default="Nothing outstanding: the trip can open."))
        moves = list(tm('trips').TRIP_STATUS_TRANSITIONS.get(trip['status'], ()))
        self.target_combo['values'] = moves
        self.target_var.set(moves[0] if moves else '')

    def submit(self):
        if not self.need_trip():
            return
        trip_id, auth = self.trip_id, self.auth
        self.async_call(lambda: tm('approvals').submit_for_approval(auth, trip_id),
                        message=lambda state: tf(f"{_K}.submitted", "Submitted. Waiting for: {stages}.",
                                                 stages=", ".join(_stage_label(s) for s in state['outstanding'])))

    def change_status(self):
        if not self.need_trip():
            return
        target = self.target_var.get()
        if not target:
            return
        reason = self.reason_var.get().strip()
        parent = self.winfo_toplevel()
        if target in ('cancelled', 'archived'):
            text = (_t(f"{_K}.confirm_cancel",
                       default="Cancel this trip? Every place is released, paid participants are refunded "
                               "and everyone is told.") if target == 'cancelled' else
                    _t(f"{_K}.confirm_archive",
                       default="Archive this trip? Its records are kept; any places still held are released "
                               "and paid participants refunded."))
            if not messagebox.askyesno(_t(f"{_K}.confirm", default="Confirm"), text, parent=parent):
                return
        trip_id, auth = self.trip_id, self.auth

        def message(result):
            refunds = result.get('refunds') or []
            text = tf(f"{_K}.status_changed", "The trip is now {status}.",
                      status=title_case(result['trip']['status']))
            if refunds:
                failed = [r for r in refunds if not r.get('success')]
                text += "\n" + tf(f"{_K}.refunds", "{n} refund(s) processed, {failed} failed.",
                                  n=len(refunds), failed=len(failed))
            return text

        self.reason_var.set('')
        self.async_call(lambda: tm('trips').set_trip_status(auth, trip_id, target, reason), message=message)


# ---------------------------------------------------------------------------
# The approver's queue (a top-level tab)
# ---------------------------------------------------------------------------

class MyApprovalsTab(ttk.Frame):
    """Approval stages waiting on the signed-in user (``approvals.pending_for``)."""

    def __init__(self, master, gui):
        super().__init__(master, padding=8)
        self.gui = gui
        self.auth = gui.auth
        self.rows = {}

        ttk.Label(self, text=_t(f"{_K}.queue_title", default="Trips Waiting for My Approval"),
                  font=('Arial', 14, 'bold')).pack(anchor=tk.W, pady=(0, 6))

        bottom = ttk.Frame(self)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        ttk.Label(bottom, text=_t(f"{_K}.comments_needed",
                                  default="Comments (required to reject or return):")).pack(anchor=tk.W)
        self.comments = tk.Text(bottom, height=3, wrap=tk.WORD)
        self.comments.pack(fill=tk.X, pady=(0, 6))
        buttons = ttk.Frame(bottom)
        buttons.pack(fill=tk.X)
        for text, decision in ((_t(f"{_K}.approve", default="Approve"), 'approved'),
                               (_t(f"{_K}.reject", default="Reject"), 'rejected'),
                               (_t(f"{_K}.return", default="Return for Changes"), 'returned')):
            ttk.Button(buttons, text=text, command=lambda d=decision: self.decide(d)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons, text=_t("common.refresh", default="Refresh"), command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text=_t(f"{_K}.open_trip", default="Open Trip in Workspace"),
                   command=self.open_trip).pack(side=tk.LEFT, padx=5)
        self.detail_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.detail_var, wraplength=1100, justify=tk.LEFT,
                  foreground='#444').pack(anchor=tk.W, pady=(6, 0))

        self.tree = make_tree(self, [('trip', _t(f"{_K}.trip", default="Trip"), 260),
                                     ('destination', _t(f"{_K}.destination", default="Destination"), 160),
                                     ('dates', _t(f"{_K}.dates", default="Dates"), 170),
                                     ('stage', _t(f"{_K}.stage", default="Stage"), 130),
                                     ('status', _t(f"{_K}.trip_status", default="Trip Status"), 100),
                                     ('requested', _t(f"{_K}.requested", default="Requested"), 140)])
        self.tree.bind('<<TreeviewSelect>>', lambda _e: self.show_detail())
        self.refresh()

    def refresh(self):
        clear_tree(self.tree)
        self.rows = {}
        try:
            rows = tm('approvals').pending_for(self.auth)
        except Exception as exc:
            show_error(self, exc)
            return
        for row in rows:
            iid = str(row['id'])
            self.rows[iid] = row
            self.tree.insert('', 'end', iid=iid, values=(
                f"{row['trip_id']} - {row['trip_name']}", row.get('destination') or '',
                f"{row['start_date']} to {row.get('end_date') or row['start_date']}",
                _stage_label(row['stage']), title_case(row.get('status')), row.get('created_at') or ''))
        self.detail_var.set(tf(f"{_K}.queue_count", "{n} decision(s) waiting.", n=len(rows)))

    def _selected(self):
        iid = selected_iid(self.tree)
        if not iid:
            messagebox.showwarning(_t(f"{_K}.no_selection", default="No Selection"),
                                   _t(f"{_K}.pick_row", default="Select a trip in the list."),
                                   parent=self.winfo_toplevel())
            return None
        return self.rows.get(iid)

    def show_detail(self):
        iid = selected_iid(self.tree)
        row = self.rows.get(iid) if iid else None
        if not row:
            return
        try:
            state = tm('approvals').approval_state(row['trip_id'])
            problems = tm('approvals').gate_problems(row['trip_id'], 'open')
        except Exception as exc:
            show_error(self, exc)
            return
        stages = "; ".join(f"{_stage_label(s)}: {title_case(v['decision'])}" for s, v in state['stages'].items())
        text = tf(f"{_K}.detail", "Stages — {stages}", stages=stages)
        if problems:
            text += "\n" + tf(f"{_K}.detail_gate", "Still needed to open: {p}", p="; ".join(problems))
        self.detail_var.set(text)

    def decide(self, decision):
        row = self._selected()
        if not row:
            return
        comments = self.comments.get('1.0', tk.END).strip()
        ok, _ = call(self, tm('approvals').decide, self.auth, row['trip_id'], row['stage'], decision, comments)
        if ok:
            self.comments.delete('1.0', tk.END)
            messagebox.showinfo(_t(f"{_K}.decided", default="Decision Recorded"),
                                tf(f"{_K}.decided_text", "{stage} approval for '{trip}': {decision}.",
                                   stage=_stage_label(row['stage']), trip=row['trip_name'],
                                   decision=title_case(decision)),
                                parent=self.winfo_toplevel())
            self.refresh()
            self.gui.after_change(source=self)

    def open_trip(self):
        row = self._selected()
        if row:
            self.gui.open_workspace('approvals', row['trip_id'])


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------

class RiskItemDialog(Dialog):
    """Add or edit one hazard. ``item`` is the existing item dict (or ``None``)."""

    def __init__(self, parent, item=None):
        self.item = item or {}
        self.result_fields = None
        super().__init__(parent, _t(f"{_K}.risk_item", default="Risk Assessment Item"))

    def body(self, master):
        item = self.item
        scores = [str(i) for i in range(1, 6)]
        r = 0

        def label(text):
            nonlocal r
            ttk.Label(master, text=text).grid(row=r, column=0, sticky=tk.NW, padx=5, pady=4)

        label(_t(f"{_K}.hazard", default="Hazard:"))
        self.hazard = tk.Text(master, width=56, height=2, wrap=tk.WORD)
        self.hazard.insert('1.0', item.get('hazard') or '')
        self.hazard.grid(row=r, column=1, columnspan=3, padx=5, pady=4)
        r += 1
        label(_t(f"{_K}.who", default="Who is at risk:"))
        self.who_var = tk.StringVar(value=item.get('who_at_risk') or '')
        ttk.Entry(master, textvariable=self.who_var, width=56).grid(row=r, column=1, columnspan=3, sticky=tk.W, padx=5)
        r += 1
        label(_t(f"{_K}.controls", default="Controls:"))
        self.controls = tk.Text(master, width=56, height=4, wrap=tk.WORD)
        self.controls.insert('1.0', item.get('controls') or '')
        self.controls.grid(row=r, column=1, columnspan=3, padx=5, pady=4)
        r += 1
        self.l_var = tk.StringVar(value=str(item.get('likelihood') or 3))
        self.s_var = tk.StringVar(value=str(item.get('severity') or 3))
        self.rl_var = tk.StringVar(value=str(item.get('residual_likelihood') or ''))
        self.rs_var = tk.StringVar(value=str(item.get('residual_severity') or ''))
        label(_t(f"{_K}.before", default="Before controls:"))
        ttk.Label(master, text=_t(f"{_K}.likelihood", default="Likelihood")).grid(row=r, column=1, sticky=tk.W)
        ttk.Combobox(master, textvariable=self.l_var, values=scores, width=4, state='readonly').grid(row=r, column=1, sticky=tk.E)
        ttk.Label(master, text=_t(f"{_K}.severity", default="Severity")).grid(row=r, column=2, sticky=tk.W, padx=(10, 0))
        ttk.Combobox(master, textvariable=self.s_var, values=scores, width=4, state='readonly').grid(row=r, column=3, sticky=tk.W)
        r += 1
        label(_t(f"{_K}.after", default="After controls:"))
        ttk.Label(master, text=_t(f"{_K}.likelihood", default="Likelihood")).grid(row=r, column=1, sticky=tk.W)
        ttk.Combobox(master, textvariable=self.rl_var, values=[''] + scores, width=4, state='readonly').grid(row=r, column=1, sticky=tk.E)
        ttk.Label(master, text=_t(f"{_K}.severity", default="Severity")).grid(row=r, column=2, sticky=tk.W, padx=(10, 0))
        ttk.Combobox(master, textvariable=self.rs_var, values=[''] + scores, width=4, state='readonly').grid(row=r, column=3, sticky=tk.W)
        r += 1
        label(_t(f"{_K}.owner", default="Owner:"))
        self.owner_var = tk.StringVar(value=item.get('owner') or '')
        ttk.Entry(master, textvariable=self.owner_var, width=30).grid(row=r, column=1, columnspan=2, sticky=tk.W, padx=5)
        r += 1
        self.score_var = tk.StringVar()
        self.score_label = tk.Label(master, textvariable=self.score_var, anchor=tk.W)
        self.score_label.grid(row=r, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=(8, 0))
        for var in (self.l_var, self.s_var, self.rl_var, self.rs_var):
            var.trace_add('write', lambda *_: self._score())
        self._score()
        return self.hazard

    def _score(self):
        try:
            l, s = int(self.l_var.get()), int(self.s_var.get())
            rl = int(self.rl_var.get() or l)
            rs = int(self.rs_var.get() or s)
        except ValueError:
            return
        band = tm('risk').band(rl * rs)
        self.score_var.set(tf(f"{_K}.score", "Risk {before} → residual {after} ({band})",
                              before=l * s, after=rl * rs, band=band))
        self.score_label.configure(background=BAND_COLOURS.get(band, ''))

    def validate(self):
        if not self.hazard.get('1.0', tk.END).strip():
            messagebox.showwarning(self.title(), _t(f"{_K}.hazard_required", default="Describe the hazard."), parent=self)
            return False
        return True

    def apply(self):
        self.result_fields = {
            'hazard': self.hazard.get('1.0', tk.END).strip(),
            'who_at_risk': self.who_var.get().strip(),
            'controls': self.controls.get('1.0', tk.END).strip(),
            'likelihood': int(self.l_var.get()), 'severity': int(self.s_var.get()),
            'residual_likelihood': self.rl_var.get() or None,
            'residual_severity': self.rs_var.get() or None,
            'owner': self.owner_var.get().strip() or None,
        }


class RiskPanel(Panel):
    key = 'risk'
    title = _t(f"{_K}.risk_tab", default="Risk Assessment")

    def build(self):
        self.assessment = None
        self.items = {}
        self.header_var = tk.StringVar()
        self.header = tk.Label(self, textvariable=self.header_var, anchor=tk.W, font=('Arial', 10, 'bold'))
        self.header.pack(fill=tk.X, pady=(0, 4))

        history = self.bar()
        ttk.Label(history, text=_t(f"{_K}.history", default="Assessment:")).pack(side=tk.LEFT)
        self.history_var = tk.StringVar()
        self.history_combo = ttk.Combobox(history, textvariable=self.history_var, state='readonly', width=50)
        self.history_combo.pack(side=tk.LEFT, padx=5)
        self.history_combo.bind('<<ComboboxSelected>>', lambda _e: self._show_history())
        ttk.Label(history, text=_t(f"{_K}.template", default="Template:")).pack(side=tk.LEFT, padx=(15, 0))
        self.template_var = tk.StringVar(value='general')
        ttk.Combobox(history, textvariable=self.template_var, state='readonly', width=12,
                     values=list(tm('risk').TEMPLATE_NAMES)).pack(side=tk.LEFT, padx=5)
        self.button(history, _t(f"{_K}.new_assessment", default="New Assessment"), self.new_assessment)

        items = self.bar()
        self.button(items, _t(f"{_K}.add_hazard", default="Add Hazard"), self.add_item)
        self.button(items, _t(f"{_K}.edit_hazard", default="Edit Hazard"), self.edit_item)
        self.button(items, _t(f"{_K}.remove_hazard", default="Remove Hazard"), self.remove_item)
        self.button(items, _t(f"{_K}.submit_assessment", default="Submit for H&S Sign-off"), self.submit)

        hs = ttk.LabelFrame(self, text=_t(f"{_K}.hs_review", default="Health & Safety review"), padding=6)
        hs.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        self.review_text = tk.Text(hs, height=4, wrap=tk.WORD, state=tk.DISABLED, background='#f6f6f6')
        self.review_text.pack(fill=tk.X, pady=(0, 4))
        row = ttk.Frame(hs)
        row.pack(fill=tk.X)
        ttk.Label(row, text=_t(f"{_K}.notes", default="Notes:")).pack(side=tk.LEFT)
        self.notes_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.notes_var, width=70).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(row, text=_t(f"{_K}.sign_off", default="Sign Off"), command=lambda: self.sign_off('signed_off')).pack(side=tk.LEFT, padx=5)
        ttk.Button(row, text=_t(f"{_K}.return_assessment", default="Return to Assessor"), command=lambda: self.sign_off('returned')).pack(side=tk.LEFT)

        self.tree = make_tree(self, [('hazard', _t(f"{_K}.hazard_col", default="Hazard"), 280),
                                     ('who', _t(f"{_K}.who_col", default="Who"), 110),
                                     ('ls', _t(f"{_K}.ls", default="L × S"), 60),
                                     ('score', _t(f"{_K}.score_col", default="Score"), 50),
                                     ('residual', _t(f"{_K}.residual", default="Residual"), 70),
                                     ('band', _t(f"{_K}.band", default="Band"), 70),
                                     ('controls', _t(f"{_K}.controls_col", default="Controls"), 360),
                                     ('owner', _t(f"{_K}.owner_col", default="Owner"), 90)], height=8)
        for band, colour in BAND_COLOURS.items():
            self.tree.tag_configure(band, background=colour)
        self.tree.bind('<Double-1>', lambda _e: self.edit_item())

    def clear(self):
        self.assessment = None
        self.header_var.set(_t(f"{_K}.pick", default="Choose a trip above."))
        self.header.configure(background='#eeeeee')
        clear_tree(self.tree)
        self.history_combo['values'] = []
        self.history_var.set('')
        self._set_review('')

    def load(self, trip_id):
        risk = tm('risk')
        self.history = risk.list_assessments(trip_id)
        self.history_combo['values'] = [
            f"#{a['id']} {a['template']} — {title_case(a['status'])} ({(a.get('created_at') or '')[:10]})"
            for a in self.history]
        current = risk.current(trip_id)
        if current:
            self.history_var.set(self.history_combo['values'][0])
        self._show(current)

    def _show_history(self):
        index = self.history_combo.current()
        if 0 <= index < len(self.history):
            ok, assessment = call(self, tm('risk').get_assessment, self.history[index]['id'])
            if ok:
                self._show(assessment)

    def _set_review(self, text):
        self.review_text.config(state=tk.NORMAL)
        self.review_text.delete('1.0', tk.END)
        self.review_text.insert('1.0', text)
        self.review_text.config(state=tk.DISABLED)

    def _show(self, assessment):
        self.assessment = assessment
        clear_tree(self.tree)
        self.items = {}
        if not assessment:
            self.header_var.set(_t(f"{_K}.no_assessment",
                                   default="No risk assessment yet — start one from a template."))
            self.header.configure(background='#eeeeee')
            self._set_review('')
            return
        residual = assessment.get('computed_residual') or assessment.get('overall_residual')
        self.header_var.set(tf(
            f"{_K}.assessment_header",
            "Assessment #{id} ({template}) — {status} — overall residual risk: {residual}"
            "{signed}", id=assessment['id'], template=assessment['template'],
            status=title_case(assessment['status']), residual=(residual or 'n/a').upper(),
            signed=(f" — signed off by {assessment['signed_off_by']} on {assessment['signed_off_at'][:10]}"
                    if assessment.get('signed_off_by') else "")))
        self.header.configure(background=BAND_COLOURS.get(residual, '#eeeeee'))
        for item in assessment['items']:
            iid = str(item['id'])
            self.items[iid] = item
            rl = item.get('residual_likelihood') or item['likelihood']
            rs = item.get('residual_severity') or item['severity']
            self.tree.insert('', 'end', iid=iid, tags=(item['residual_band'],), values=(
                item['hazard'], item.get('who_at_risk') or '', f"{item['likelihood']} × {item['severity']}",
                item['score'], f"{rl} × {rs} = {item['residual_score']}", item['residual_band'].title(),
                (item.get('controls') or '').replace('\n', ' '), item.get('owner') or ''))
        self._set_review(assessment.get('review_notes') or '')

    def _assessment_id(self):
        if not self.need_trip():
            return None
        if not self.assessment:
            messagebox.showwarning(self.title, _t(f"{_K}.no_assessment",
                                                  default="No risk assessment yet — start one from a template."),
                                   parent=self.winfo_toplevel())
            return None
        return self.assessment['id']

    def new_assessment(self):
        if not self.need_trip():
            return
        ok, assessment = call(self, tm('risk').create_assessment, self.auth, self.trip_id, self.template_var.get())
        if ok:
            self.changed()

    def add_item(self):
        aid = self._assessment_id()
        if aid is None:
            return
        dialog = RiskItemDialog(self.winfo_toplevel())
        if dialog.result_fields:
            f = dialog.result_fields
            ok, _ = call(self, tm('risk').add_item, self.auth, aid, f['hazard'], f['who_at_risk'], f['controls'],
                         f['likelihood'], f['severity'], f['residual_likelihood'], f['residual_severity'], f['owner'])
            if ok:
                self.changed()

    def _selected_item(self):
        iid = selected_iid(self.tree)
        if not iid:
            messagebox.showwarning(self.title, _t(f"{_K}.pick_hazard", default="Select a hazard in the list."),
                                   parent=self.winfo_toplevel())
            return None
        return self.items.get(iid)

    def edit_item(self):
        if self._assessment_id() is None:
            return
        item = self._selected_item()
        if not item:
            return
        dialog = RiskItemDialog(self.winfo_toplevel(), item)
        if dialog.result_fields:
            ok, _ = call(self, tm('risk').update_item, self.auth, item['id'], **dialog.result_fields)
            if ok:
                self.changed()

    def remove_item(self):
        if self._assessment_id() is None:
            return
        item = self._selected_item()
        if item and messagebox.askyesno(self.title, tf(f"{_K}.confirm_remove", "Remove '{hazard}'?",
                                                       hazard=item['hazard'][:80]), parent=self.winfo_toplevel()):
            ok, _ = call(self, tm('risk').remove_item, self.auth, item['id'])
            if ok:
                self.changed()

    def submit(self):
        aid = self._assessment_id()
        if aid is None:
            return
        ok, assessment = call(self, tm('risk').submit, self.auth, aid)
        if ok:
            messagebox.showinfo(self.title, tf(f"{_K}.risk_submitted",
                                               "Submitted for Health & Safety sign-off (overall residual: {r}).",
                                               r=assessment.get('overall_residual')), parent=self.winfo_toplevel())
            self.changed()

    def sign_off(self, decision):
        aid = self._assessment_id()
        if aid is None:
            return
        ok, _ = call(self, tm('risk').sign_off, self.auth, aid, decision, self.notes_var.get())
        if ok:
            self.notes_var.set('')
            self.changed()

