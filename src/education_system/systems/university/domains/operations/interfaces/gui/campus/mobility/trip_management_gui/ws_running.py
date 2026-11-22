"""Running a trip: communications, roll call on the day, money (budget,
instalments, reconciliation) and evaluations afterwards."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.simpledialog import Dialog

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, call, run_async, show_error, make_tree, clear_tree, selected_iid, money,
    text_window, title_case,
)
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.workspace import (
    Panel,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.running'


# ---------------------------------------------------------------------------
# Communications
# ---------------------------------------------------------------------------

class CommsPanel(Panel):
    key = 'comms'
    title = _t(f"{_K}.comms_tab", default="Communications")

    def build(self):
        msg = ttk.LabelFrame(self, text=_t(f"{_K}.message", default="Message everyone holding a place"), padding=6)
        msg.pack(fill=tk.BOTH, expand=True)
        row = ttk.Frame(msg)
        row.pack(fill=tk.X)
        ttk.Label(row, text=_t(f"{_K}.subject", default="Subject:")).pack(side=tk.LEFT)
        self.subject_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.subject_var, width=70).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        buttons = ttk.Frame(msg)
        buttons.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))
        ttk.Button(buttons, text=_t(f"{_K}.send", default="Send to Participants"), command=self.send_message).pack(side=tk.LEFT)
        ttk.Button(buttons, text=_t(f"{_K}.change_notice", default="Send as Change Notice"),
                   command=self.change_notice).pack(side=tk.LEFT, padx=5)
        self.body = tk.Text(msg, height=8, wrap=tk.WORD)
        self.body.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        docs = ttk.LabelFrame(self, text=_t(f"{_K}.documents", default="Trip documents"), padding=6)
        docs.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(docs, text=_t(f"{_K}.pack", default="Itinerary Pack (preview / print)"),
                   command=self.pack_preview).pack(side=tk.LEFT)
        ttk.Button(docs, text=_t(f"{_K}.card", default="Emergency Card (preview / print)"),
                   command=self.card_preview).pack(side=tk.LEFT, padx=5)
        self.info_var = tk.StringVar()
        ttk.Label(self, textvariable=self.info_var, foreground='#444').pack(anchor=tk.W, pady=(6, 0))

    def clear(self):
        self.info_var.set('')

    def load(self, trip_id):
        trip = self.trip
        self.info_var.set(tf(f"{_K}.comms_info", "{n} place(s) held on {name}. 24/7 contact: {c}.",
                             n=trip.get('current_participants') or self._count(trip_id), name=trip['trip_name'],
                             c=trip.get('emergency_contact_24h') or 'NOT SET'))

    def _count(self, trip_id):
        try:
            return tm('rollcall').emergency_card(trip_id)['participant_count']
        except Exception:
            return '?'

    def send_message(self):
        if not self.need_trip():
            return
        subject, body = self.subject_var.get().strip(), self.body.get('1.0', tk.END).strip()
        trip_id, auth = self.trip_id, self.auth
        if not messagebox.askyesno(self.title, _t(f"{_K}.confirm_send", default="E-mail this to everyone holding a place?"),
                                   parent=self.winfo_toplevel()):
            return
        self.async_call(lambda: tm('comms').notify_participants(auth, trip_id, subject, body),
                        done=lambda _n: (self.subject_var.set(''), self.body.delete('1.0', tk.END)),
                        message=lambda n: tf(f"{_K}.sent", "{n} e-mail(s) sent.", n=n))

    def change_notice(self):
        if not self.need_trip():
            return
        text = self.body.get('1.0', tk.END).strip()
        trip_id, auth = self.trip_id, self.auth
        self.async_call(lambda: tm('comms').change_notice(auth, trip_id, text),
                        done=lambda _n: self.body.delete('1.0', tk.END),
                        message=lambda n: tf(f"{_K}.sent", "{n} e-mail(s) sent.", n=n))

    def pack_preview(self):
        if self.need_trip():
            ok, text = call(self, tm('comms').itinerary_pack, self.trip_id)
            if ok:
                text_window(self, tf(f"{_K}.pack_title", "Itinerary Pack — {name}", name=self.trip['trip_name']),
                            text, save_name=f"trip_{self.trip_id}_pack.txt")

    def card_preview(self):
        if self.need_trip():
            ok, card = call(self, tm('rollcall').emergency_card, self.trip_id)
            if ok:
                text_window(self, tf(f"{_K}.card_title", "Emergency Card — {name}", name=self.trip['trip_name']),
                            card['text'], width=620, height=440, save_name=f"trip_{self.trip_id}_emergency_card.txt")


# ---------------------------------------------------------------------------
# On the day: roll call
# ---------------------------------------------------------------------------

class OnTheDayPanel(Panel):
    key = 'on_the_day'
    title = _t(f"{_K}.day_tab", default="On the Day")

    def build(self):
        self.rollcalls = {}
        self.entries = {}
        self.rollcall_id = None
        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 8))
        lbar = ttk.Frame(left)
        lbar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(lbar, text=_t(f"{_K}.start", default="Start Roll Call"), command=self.start).pack(side=tk.LEFT)
        ttk.Button(lbar, text=_t("common.refresh", default="Refresh"), command=self.reload).pack(side=tk.LEFT, padx=5)
        self.calls = make_tree(left, [('label', _t(f"{_K}.rollcall", default="Roll Call"), 180),
                                      ('when', _t(f"{_K}.when", default="Taken"), 120),
                                      ('count', _t(f"{_K}.present", default="Present"), 70)], height=14)
        self.calls.bind('<<TreeviewSelect>>', lambda _e: self.open_rollcall())

        right = ttk.Frame(self)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rbar = ttk.Frame(right)
        rbar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(rbar, text=_t(f"{_K}.tick", default="Present ✓"), command=lambda: self.mark(True)).pack(side=tk.LEFT)
        ttk.Button(rbar, text=_t(f"{_K}.untick", default="Not Present"), command=lambda: self.mark(False)).pack(side=tk.LEFT, padx=5)
        ttk.Button(rbar, text=_t(f"{_K}.note", default="Not Present with Note..."), command=self.mark_note).pack(side=tk.LEFT)
        ttk.Button(rbar, text=_t(f"{_K}.missing", default="Show Missing"), command=self.show_missing).pack(side=tk.LEFT, padx=5)
        self.count_var = tk.StringVar()
        ttk.Label(rbar, textvariable=self.count_var, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10)
        self.ticks = make_tree(right, [('name', _t(f"{_K}.name", default="Name"), 220),
                                       ('student', _t(f"{_K}.student", default="Student"), 90),
                                       ('present', _t(f"{_K}.present", default="Present"), 70),
                                       ('contact', _t(f"{_K}.contact", default="Emergency Contact"), 260)], height=14)
        self.ticks.configure(selectmode='extended')
        self.ticks.tag_configure('missing', background='#f7cccc')
        self.ticks.tag_configure('present', background='#d6f0d6')
        self.ticks.bind('<Double-1>', lambda _e: self.toggle())

    def clear(self):
        clear_tree(self.calls)
        clear_tree(self.ticks)
        self.rollcall_id = None
        self.count_var.set('')

    def load(self, trip_id):
        keep = self.rollcall_id
        self.clear()
        self.rollcalls = {}
        for rc in tm('rollcall').list_rollcalls(trip_id):
            iid = str(rc['id'])
            self.rollcalls[iid] = rc
            self.calls.insert('', 'end', iid=iid, values=(rc['label'], (rc.get('taken_at') or '')[:16],
                                                           f"{rc['present']}/{rc['total']}"))
        if keep and str(keep) in self.rollcalls:
            self.calls.selection_set(str(keep))
            self.open_rollcall()

    def start(self):
        if not self.need_trip():
            return
        label = simpledialog.askstring(self.title, _t(f"{_K}.label_prompt",
                                                      default="Name this roll call (e.g. 'Coach departure'):"),
                                       parent=self.winfo_toplevel())
        if label is None:
            return
        ok, rid = call(self, tm('rollcall').start_rollcall, self.auth, self.trip_id, label)
        if ok:
            self.rollcall_id = rid
            self.reload()

    def open_rollcall(self):
        iid = selected_iid(self.calls)
        if not iid:
            return
        self.rollcall_id = int(iid)
        try:
            people = tm('registrations').list_participants(self.auth, self.trip_id)
            missing = {m['participant_id']: m for m in tm('rollcall').missing(self.rollcall_id)}
        except Exception as exc:
            show_error(self, exc)
            return
        on_roll = tm('rollcall').ON_ROLL
        clear_tree(self.ticks)
        self.entries = {}
        present = 0
        for p in people:
            if p['status'] not in on_roll:
                continue
            here = p['id'] not in missing
            present += here
            m = missing.get(p['id']) or {}
            self.entries[str(p['id'])] = here
            contact = " ".join(x for x in (p.get('emergency_contact_name') or m.get('emergency_contact_name'),
                                           p.get('emergency_contact_phone') or p.get('emergency_contact')) if x)
            self.ticks.insert('', 'end', iid=str(p['id']), tags=('present' if here else 'missing',), values=(
                p.get('name') or '', p.get('student_id') or 'staff', '✓' if here else
                (m.get('note') or ''), contact))
        self.count_var.set(tf(f"{_K}.count", "{present} of {total} present", present=present, total=len(self.entries)))

    def _mark_ids(self, ids, present, note=""):
        """Tick each selected person (one short write each) off the Tk thread."""
        auth, rollcall_id, ids = self.auth, self.rollcall_id, [int(i) for i in ids]

        def work():
            for pid in ids:
                tm('rollcall').mark(auth, rollcall_id, pid, present, note)

        run_async(self, work, lambda _r: self.reload(),
                  lambda exc: (show_error(self, exc), self.reload()))

    def mark(self, present):
        if not self.rollcall_id:
            messagebox.showwarning(self.title, _t(f"{_K}.pick_rollcall", default="Start or choose a roll call."),
                                   parent=self.winfo_toplevel())
            return
        ids = self.ticks.selection()
        if ids:
            self._mark_ids(ids, present)

    def mark_note(self):
        ids = self.ticks.selection()
        if not self.rollcall_id or not ids:
            return
        note = simpledialog.askstring(self.title, _t(f"{_K}.note_prompt", default="Note (e.g. 'with leader B'):"),
                                      parent=self.winfo_toplevel())
        if note is not None:
            self._mark_ids(ids, False, note)

    def toggle(self):
        iid = selected_iid(self.ticks)
        if iid and self.rollcall_id:
            self._mark_ids([iid], not self.entries.get(iid, False))

    def show_missing(self):
        if not self.rollcall_id:
            return
        ok, rows = call(self, tm('rollcall').missing, self.rollcall_id)
        if ok:
            text = "\n".join(f"{r['name']}: {r.get('emergency_contact_name') or ''} "
                             f"{r.get('emergency_contact_phone') or ''}{'  (' + r['note'] + ')' if r.get('note') else ''}"
                             for r in rows) or _t(f"{_K}.all_present", default="Everyone is present.")
            text_window(self, _t(f"{_K}.missing_title", default="Missing"), text, width=600, height=420,
                        save_name=f"rollcall_{self.rollcall_id}_missing.txt")


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

class InstalmentDialog(Dialog):
    def __init__(self, parent, item=None):
        self.item = item or {}
        self.values = None
        super().__init__(parent, _t(f"{_K}.instalment", default="Instalment"))

    def body(self, master):
        self.label_var = tk.StringVar(value=self.item.get('label') or '')
        self.due_var = tk.StringVar(value=self.item.get('due_date') or '')
        self.amount_var = tk.StringVar(value=str(self.item.get('amount') or ''))
        for r, (label, var) in enumerate(((_t(f"{_K}.inst_label", default="Label:"), self.label_var),
                                          (_t(f"{_K}.inst_due", default="Due (YYYY-MM-DD):"), self.due_var),
                                          (_t(f"{_K}.inst_amount", default="Amount (£):"), self.amount_var))):
            ttk.Label(master, text=label).grid(row=r, column=0, sticky=tk.W, padx=5, pady=3)
            ttk.Entry(master, textvariable=var, width=24).grid(row=r, column=1, sticky=tk.W, padx=5)
        return None

    def apply(self):
        self.values = {'label': self.label_var.get(), 'due_date': self.due_var.get(), 'amount': self.amount_var.get()}


class MoneyPanel(Panel):
    key = 'money'
    title = _t(f"{_K}.money_tab", default="Money")

    def build(self):
        self.instalments = {}
        summary = ttk.LabelFrame(self, text=_t(f"{_K}.budget", default="Budget vs actual"), padding=6)
        summary.pack(fill=tk.X)
        self.summary_text = tk.Text(summary, height=9, wrap=tk.WORD)
        self.summary_text.pack(fill=tk.X)
        self.summary_text.tag_configure('over', foreground='#b00')
        self.summary_text.tag_configure('under', foreground='#070')

        inst = ttk.LabelFrame(self, text=_t(f"{_K}.instalments", default="Payment instalments"), padding=6)
        inst.pack(fill=tk.BOTH, expand=True, pady=6)
        ibar = ttk.Frame(inst)
        ibar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(ibar, text=_t(f"{_K}.add_inst", default="Add"), command=self.add_instalment).pack(side=tk.LEFT)
        ttk.Button(ibar, text=_t(f"{_K}.edit_inst", default="Edit"), command=self.edit_instalment).pack(side=tk.LEFT, padx=5)
        ttk.Button(ibar, text=_t(f"{_K}.remove_inst", default="Remove"), command=self.remove_instalment).pack(side=tk.LEFT)
        self.inst_tree = make_tree(inst, [('label', _t(f"{_K}.inst_label_col", default="Instalment"), 220),
                                          ('due', _t(f"{_K}.inst_due_col", default="Due"), 100),
                                          ('amount', _t(f"{_K}.inst_amount_col", default="Amount"), 90)], height=4)

        rec = ttk.LabelFrame(self, text=_t(f"{_K}.reconcile", default="Reconciliation"), padding=6)
        rec.pack(fill=tk.X)
        self.rec_var = tk.StringVar()
        ttk.Label(rec, textvariable=self.rec_var, wraplength=1100, justify=tk.LEFT).pack(anchor=tk.W)
        rrow = ttk.Frame(rec)
        rrow.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(rrow, text=_t(f"{_K}.notes", default="Notes:")).pack(side=tk.LEFT)
        self.rec_notes = tk.StringVar()
        ttk.Entry(rrow, textvariable=self.rec_notes, width=70).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(rrow, text=_t(f"{_K}.sign_reconcile", default="Sign Off Accounts"), command=self.reconcile).pack(side=tk.LEFT)

    def clear(self):
        self.summary_text.delete('1.0', tk.END)
        clear_tree(self.inst_tree)
        self.rec_var.set('')

    def load(self, trip_id):
        money_mod = tm('money')
        self.clear()
        figures = money_mod.budget_vs_actual(trip_id)
        lines = [f"Budget: {money(figures['budget']) if figures['budget'] is not None else 'not set'}",
                 "Spend by category: " + (", ".join(f"{k} {money(v)}" for k, v in figures['expenses'].items()) or 'none'),
                 f"Actual spend: {money(figures['actual'])}",
                 f"Income (paid less refunds): {money(figures['income'])}  "
                 f"[paid {money(figures['paid'])}, refunded {money(figures['refunded'])}, hardship {money(figures['hardship'])}]"]
        self.summary_text.insert('1.0', "\n".join(lines) + "\n")
        if figures['variance'] is not None:
            tag = 'over' if figures['variance'] < 0 else 'under'
            self.summary_text.insert(tk.END, f"Variance (budget - actual): {money(figures['variance'])}"
                                             f"{' OVERSPENT' if figures['variance'] < 0 else ''}\n", tag)
        tag = 'over' if figures['net'] < 0 else 'under'
        self.summary_text.insert(tk.END, f"Net (income - spend): {money(figures['net'])}\n", tag)
        self.instalments = {}
        for item in money_mod.list_instalments(trip_id):
            iid = str(item['id'])
            self.instalments[iid] = item
            self.inst_tree.insert('', 'end', iid=iid, values=(item['label'], item['due_date'], money(item['amount'])))
        rec = money_mod.get_reconciliation(trip_id)
        if rec and rec.get('signed_off_by'):
            self.rec_var.set(tf(f"{_K}.reconciled", "Signed off by {who} on {when}: budget {b}, actual {a}, income {i}. {notes}",
                                who=rec['signed_off_by'], when=(rec.get('signed_off_at') or '')[:10],
                                b=money(rec.get('budget')), a=money(rec.get('actual')), i=money(rec.get('income')),
                                notes=rec.get('notes') or ''))
        else:
            self.rec_var.set(_t(f"{_K}.not_reconciled",
                                default="Not signed off. The accounts are signed off once the trip has finished."))

    def add_instalment(self):
        if not self.need_trip():
            return
        dialog = InstalmentDialog(self.winfo_toplevel())
        if dialog.values:
            v = dialog.values
            ok, _ = call(self, tm('money').add_instalment, self.auth, self.trip_id, v['label'], v['due_date'], v['amount'])
            if ok:
                self.changed()

    def _selected(self):
        item = self.instalments.get(selected_iid(self.inst_tree) or '')
        if not item:
            messagebox.showwarning(self.title, _t(f"{_K}.pick_inst", default="Select an instalment."),
                                   parent=self.winfo_toplevel())
        return item

    def edit_instalment(self):
        item = self._selected()
        if item:
            dialog = InstalmentDialog(self.winfo_toplevel(), item)
            if dialog.values:
                ok, _ = call(self, tm('money').update_instalment, self.auth, item['id'], **dialog.values)
                if ok:
                    self.changed()

    def remove_instalment(self):
        item = self._selected()
        if item and messagebox.askyesno(self.title, tf(f"{_K}.confirm_remove", "Remove '{label}'?", label=item['label']),
                                        parent=self.winfo_toplevel()):
            ok, _ = call(self, tm('money').remove_instalment, self.auth, item['id'])
            if ok:
                self.changed()

    def reconcile(self):
        if self.need_trip() and messagebox.askyesno(
                self.title, _t(f"{_K}.confirm_reconcile",
                               default="Sign off this trip's accounts? The figures are frozen and cannot be signed again."),
                parent=self.winfo_toplevel()):
            ok, _ = call(self, tm('money').reconcile, self.auth, self.trip_id, self.rec_notes.get())
            if ok:
                self.rec_notes.set('')
                self.changed()


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

class EvaluateDialog(Dialog):
    """Evaluate a trip the user went on or led (``evaluation.submit_evaluation``)."""

    def __init__(self, parent, auth, trip_id, trip_name="", on_done=None):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.trip_name = trip_name
        self.on_done = on_done
        super().__init__(parent, _t(f"{_K}.evaluate", default="Evaluate Trip"))

    def body(self, master):
        if self.trip_name:
            ttk.Label(master, text=self.trip_name, font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        row = ttk.Frame(master)
        row.pack(fill=tk.X, pady=6)
        ttk.Label(row, text=_t(f"{_K}.rating", default="Overall rating (1 = poor, 5 = excellent):")).pack(side=tk.LEFT)
        self.rating_var = tk.IntVar(value=4)
        for n in range(1, 6):
            ttk.Radiobutton(row, text=str(n), variable=self.rating_var, value=n).pack(side=tk.LEFT, padx=3)
        ttk.Label(master, text=_t(f"{_K}.went_well", default="What went well:")).pack(anchor=tk.W)
        self.well = tk.Text(master, width=60, height=4, wrap=tk.WORD)
        self.well.pack(fill=tk.X)
        ttk.Label(master, text=_t(f"{_K}.improve", default="What could be better:")).pack(anchor=tk.W, pady=(6, 0))
        self.improve = tk.Text(master, width=60, height=4, wrap=tk.WORD)
        self.improve.pack(fill=tk.X)
        ttk.Label(master, text=_t(f"{_K}.anonymous", default="Participants' comments reach the organisers without your name."),
                  foreground='gray').pack(anchor=tk.W, pady=(6, 0))
        return self.well

    def apply(self):
        ok, _ = call(self.parent, tm('evaluation').submit_evaluation, self.auth, self.trip_id, self.rating_var.get(),
                     self.well.get('1.0', tk.END).strip(), self.improve.get('1.0', tk.END).strip())
        if ok:
            messagebox.showinfo(self.title(), _t(f"{_K}.thanks", default="Thank you — your evaluation is recorded."),
                                parent=self.parent)
            if self.on_done:
                self.on_done()


class EvaluationPanel(Panel):
    key = 'evaluation'
    title = _t(f"{_K}.evaluation_tab", default="Evaluation")

    def build(self):
        bar = self.bar()
        self.button(bar, _t(f"{_K}.evaluate_leader", default="Evaluate This Trip (as leader)"), self.evaluate)
        self.button(bar, _t("common.refresh", default="Refresh"), self.reload)
        self.results = tk.Text(self, wrap=tk.WORD)
        self.results.pack(fill=tk.BOTH, expand=True)

    def clear(self):
        self.results.delete('1.0', tk.END)

    def load(self, trip_id):
        self.clear()
        try:
            r = tm('evaluation').results(self.auth, trip_id)
        except PermissionError as exc:
            self.results.insert('1.0', str(exc))
            return
        if not r['responses']:
            self.results.insert('1.0', _t(f"{_K}.no_responses", default="No evaluations yet. Participants and leaders "
                                                                     "are asked to evaluate once the trip is completed."))
            return
        lines = [tf(f"{_K}.results_head", "{n} response(s); average rating {avg} / 5.", n=r['responses'], avg=r['average']),
                 "By role: " + ", ".join(f"{role} {v['count']} (avg {v['average']})" for role, v in r['by_role'].items()),
                 "Ratings: " + "  ".join(f"{k}★ {v}" for k, v in r['distribution'].items()), ""]
        for c in r['comments']:
            who = c['respondent'] or c['role']
            lines.append(f"[{c['rating']}★ {who}]")
            if c.get('went_well'):
                lines.append(f"  Went well: {c['went_well']}")
            if c.get('improve'):
                lines.append(f"  Improve: {c['improve']}")
        self.results.insert('1.0', "\n".join(lines))

    def evaluate(self):
        if self.need_trip():
            EvaluateDialog(self.winfo_toplevel(), self.auth, self.trip_id, self.trip['trip_name'], self.reload)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class HistoryPanel(Panel):
    """Every recorded change to the trip, newest first (organisers and
    approvers only — ``trips.list_history`` checks)."""

    key = 'history'
    title = _t(f"{_K}.history_tab", default="History")

    _ACTIONS_ALL = _t(f"{_K}.history_all", default="All changes")

    def build(self):
        bar = self.bar()
        ttk.Label(bar, text=_t(f"{_K}.history_show", default="Show:")).pack(side=tk.LEFT, padx=(0, 4))
        self.action_var = tk.StringVar(value=self._ACTIONS_ALL)
        self.action_box = ttk.Combobox(bar, textvariable=self.action_var, state='readonly', width=24)
        self.action_box.pack(side=tk.LEFT, padx=(0, 8))
        self.action_box.bind('<<ComboboxSelected>>', lambda _e: self._fill())
        self.button(bar, _t("common.refresh", default="Refresh"), self.reload)
        self.button(bar, _t(f"{_K}.history_save", default="Save as CSV"), self.save_csv)
        self.note = ttk.Label(self, foreground='#555555')
        self.note.pack(side=tk.BOTTOM, anchor='w', pady=(4, 0))
        self.tree = make_tree(self, [
            ('changed_at', _t(f"{_K}.history_when", default="When"), 140),
            ('changed_by', _t(f"{_K}.history_who", default="By"), 110),
            ('action', _t(f"{_K}.history_action", default="Change"), 140),
            ('field', _t(f"{_K}.history_field", default="Field"), 110),
            ('old_value', _t(f"{_K}.history_from", default="From"), 170),
            ('new_value', _t(f"{_K}.history_to", default="To"), 170),
            ('version', _t(f"{_K}.history_version", default="Version"), 60),
        ], height=16)
        self.rows = []

    def clear(self):
        self.rows = []
        clear_tree(self.tree)
        self.note.config(text="")

    def load(self, trip_id):
        self.clear()
        try:
            self.rows = tm('trips').list_history(self.auth, trip_id)
        except PermissionError as exc:
            self.note.config(text=str(exc))
            return
        actions = sorted({r['action'] for r in self.rows if r.get('action')})
        self.action_box['values'] = [self._ACTIONS_ALL] + [title_case(a) for a in actions]
        if self.action_var.get() not in self.action_box['values']:
            self.action_var.set(self._ACTIONS_ALL)
        self._fill()

    def _fill(self):
        clear_tree(self.tree)
        wanted = self.action_var.get()
        shown = [r for r in self.rows
                 if wanted == self._ACTIONS_ALL or title_case(r.get('action') or '') == wanted]
        for r in shown:
            self.tree.insert('', tk.END, iid=str(r['id']), values=(
                r.get('changed_at') or '', r.get('changed_by') or '',
                title_case(r.get('action') or ''), title_case(r.get('field') or ''),
                r.get('old_value') or '', r.get('new_value') or '', r.get('version') or ''))
        self.note.config(text=tf(f"{_K}.history_count", "{shown} of {total} change(s).",
                                 shown=len(shown), total=len(self.rows)))

    def save_csv(self):
        if not self.need_trip() or not self.rows:
            return
        from tkinter import filedialog
        import csv
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"trip_{self.trip_id}_history.csv")
        if not path:
            return
        cols = ('changed_at', 'changed_by', 'action', 'field', 'old_value', 'new_value', 'version')
        try:
            with open(path, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(cols)
                for r in self.rows:
                    writer.writerow([r.get(c) if r.get(c) is not None else '' for c in cols])
        except OSError as exc:
            show_error(self, exc)
            return
        messagebox.showinfo(_t(f"{_K}.done", default="Done"),
                            tf(f"{_K}.history_saved", "History saved to {path}", path=path),
                            parent=self.winfo_toplevel())

