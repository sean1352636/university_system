"""Participant screens: the organisers' participant panel (waiting list,
payments, amount owed, hardship, restricted medical sheet) and the dialogs a
participant uses for their own place (pay, health details)."""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, call, run_async, show_error, make_tree, clear_tree, selected_iid, title_case, money,
)
from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui.workspace import (
    Panel,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.people'


# ---------------------------------------------------------------------------
# Paying for a place
# ---------------------------------------------------------------------------

class PayDialog(Dialog):
    """Pay towards a place (``payments.pay_for_registration``) — the
    participant for their own place, or an organiser recording a payment."""

    def __init__(self, parent, auth, participant_id, on_done=None):
        self.auth = auth
        self.participant_id = int(participant_id)
        self.on_done = on_done
        self.reg = tm('registrations').get_participant(self.participant_id)
        self.trip = tm('trips').get_trip(self.reg['trip_id']) if self.reg else None
        super().__init__(parent, _t(f"{_K}.pay", default="Pay for Trip"))

    def body(self, master):
        if not self.reg or not self.trip:
            ttk.Label(master, text=_t(f"{_K}.not_found", default="Registration not found.")).pack(pady=20)
            return None
        money_mod, payments = tm('money'), tm('payments')
        owed = money_mod.amount_owed(self.reg, self.trip)
        ttk.Label(master, text=self.trip['trip_name'], font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(master, text=tf(f"{_K}.pay_summary",
                                  "Cost {cost}; paid {paid}; refunded {refunded}; hardship award {hardship}.\nStill owed: {owed}",
                                  cost=money(self.trip.get('cost')), paid=money(self.reg.get('amount_paid')),
                                  refunded=money(self.reg.get('amount_refunded')),
                                  hardship=money(self.reg.get('hardship_award')), owed=money(owed)),
                  justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 8))
        try:
            schedule = money_mod.instalment_schedule(self.participant_id)
        except Exception:
            schedule = []
        if schedule:
            box = ttk.LabelFrame(master, text=_t(f"{_K}.instalments", default="Instalments"), padding=6)
            box.pack(fill=tk.X, pady=(0, 8))
            for item in schedule:
                ttk.Label(box, text=f"{item['due_date']}  {item['label']}  {money(item['amount'])}  "
                                    f"{'paid' if item['paid'] else 'due'}").pack(anchor=tk.W)
        row = ttk.Frame(master)
        row.pack(fill=tk.X)
        ttk.Label(row, text=_t(f"{_K}.method", default="Pay by:")).pack(side=tk.LEFT)
        self.methods = {payments.method_label(m): m for m in (payments.CARD, payments.CASH, payments.STUDENT_ACCOUNT)}
        self.method_var = tk.StringVar(value=next(iter(self.methods)))
        ttk.Combobox(row, textvariable=self.method_var, values=list(self.methods), state='readonly',
                     width=24).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text=_t(f"{_K}.amount", default="Amount (£):")).pack(side=tk.LEFT, padx=(10, 0))
        self.amount_var = tk.StringVar(value=f"{owed:.2f}")
        ttk.Entry(row, textvariable=self.amount_var, width=10).pack(side=tk.LEFT, padx=5)
        return None

    def validate(self):
        if not self.reg:
            return False
        try:
            float(self.amount_var.get())
        except ValueError:
            messagebox.showwarning(self.title(), _t(f"{_K}.bad_amount", default="Enter an amount."), parent=self)
            return False
        return True

    def apply(self):
        auth, pid, parent, on_done = self.auth, self.participant_id, self.parent, self.on_done
        method, amount = self.methods[self.method_var.get()], float(self.amount_var.get())

        def done(outcome):
            if outcome.get('success'):
                messagebox.showinfo(_t(f"{_K}.paid", default="Payment Taken"),
                                    tf(f"{_K}.paid_text", "{amount} paid (ref {ref}). Still owed: {owed}.",
                                       amount=money(outcome.get('amount')), ref=outcome.get('reference') or '-',
                                       owed=money(outcome.get('owed'))), parent=parent)
            else:
                messagebox.showerror(_t(f"{_K}.not_paid", default="Payment Failed"),
                                     outcome.get('message') or _t(f"{_K}.not_paid", default="Payment Failed"),
                                     parent=parent)
            if on_done:
                on_done()

        run_async(parent, lambda: tm('payments').pay_for_registration(auth, pid, method, amount), done)


class HardshipDialog(Dialog):
    """Award hardship support towards a place (``money.apply_hardship``)."""

    def __init__(self, parent, auth, participant_id, name=""):
        self.auth = auth
        self.participant_id = int(participant_id)
        self.name = name
        self.saved = False
        super().__init__(parent, _t(f"{_K}.hardship", default="Hardship Award"))

    def body(self, master):
        if self.name:
            ttk.Label(master, text=self.name, font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, sticky=tk.W)
        self.amount_var = tk.StringVar()
        self.application_var = tk.StringVar()
        self.note_var = tk.StringVar()
        for r, (label, var) in enumerate(((_t(f"{_K}.award", default="Award (£):"), self.amount_var),
                                          (_t(f"{_K}.application", default="Bursary application id (optional):"), self.application_var),
                                          (_t(f"{_K}.note", default="Note:"), self.note_var)), start=1):
            ttk.Label(master, text=label).grid(row=r, column=0, sticky=tk.W, padx=5, pady=3)
            ttk.Entry(master, textvariable=var, width=30).grid(row=r, column=1, sticky=tk.W, padx=5)
        return None

    def apply(self):
        ok, place = call(self.parent, tm('money').apply_hardship, self.auth, self.participant_id,
                         self.amount_var.get() or 0, application_id=self.application_var.get().strip() or None,
                         note=self.note_var.get().strip())
        if ok:
            self.saved = True
            messagebox.showinfo(self.title(), tf(f"{_K}.hardship_done", "Award recorded; payment status {s}.",
                                                 s=title_case(place.get('payment_status'))), parent=self.parent)


# ---------------------------------------------------------------------------
# Health details
# ---------------------------------------------------------------------------

class HealthDetailsDialog(Dialog):
    """A participant's medical, dietary and accessibility details and emergency
    contact (``medical.my_health_details`` / ``update_health_details``).

    Reading is audited by the domain. The participant can agree to share
    their health record with the trip and import it from there.
    """

    def __init__(self, parent, auth, participant_id, *, own=True):
        self.auth = auth
        self.participant_id = int(participant_id)
        self.own = own
        self.details = None
        try:
            self.details = tm('medical').my_health_details(auth, self.participant_id)
        except Exception as exc:
            show_error(parent, exc)
        super().__init__(parent, _t(f"{_K}.health", default="Medical & Dietary Details"))

    def body(self, master):
        if self.details is None:
            ttk.Label(master, text=_t(f"{_K}.health_unavailable", default="These details are not available to you.")).pack(pady=20)
            return None
        d = self.details
        self.texts = {}
        for r, (key, label, height) in enumerate((
                ('medical_info', _t(f"{_K}.medical", default="Medical information:"), 4),
                ('dietary_requirements', _t(f"{_K}.dietary", default="Dietary requirements:"), 2),
                ('accessibility_needs', _t(f"{_K}.access", default="Accessibility needs:"), 2))):
            ttk.Label(master, text=label).grid(row=r, column=0, sticky=tk.NW, padx=5, pady=3)
            box = tk.Text(master, width=50, height=height, wrap=tk.WORD)
            box.insert('1.0', d.get(key) or '')
            box.grid(row=r, column=1, columnspan=3, padx=5, pady=3)
            self.texts[key] = box
        self.vars = {}
        for r, (key, label) in enumerate((
                ('emergency_contact_name', _t(f"{_K}.contact_name", default="Emergency contact name:")),
                ('emergency_contact_phone', _t(f"{_K}.contact_phone", default="Phone:")),
                ('emergency_contact_relationship', _t(f"{_K}.contact_rel", default="Relationship:")),
                ('emergency_contact', _t(f"{_K}.contact_text", default="Emergency contact (as written):"))), start=3):
            ttk.Label(master, text=label).grid(row=r, column=0, sticky=tk.W, padx=5, pady=3)
            var = tk.StringVar(value=d.get(key) or '')
            ttk.Entry(master, textvariable=var, width=50).grid(row=r, column=1, columnspan=3, sticky=tk.W, padx=5)
            self.vars[key] = var
        if self.own:
            share = ttk.LabelFrame(master, text=_t(f"{_K}.health_record", default="My health record"), padding=6)
            share.grid(row=7, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=(8, 0))
            self.consent_var = tk.BooleanVar(value=bool(d.get('health_share_consent_at')))
            ttk.Checkbutton(share, text=_t(f"{_K}.consent",
                                           default="I agree my health record (allergies, conditions, medication, "
                                                   "emergency contact) may be copied to this trip"),
                            variable=self.consent_var, command=self.toggle_consent).pack(anchor=tk.W)
            ttk.Button(share, text=_t(f"{_K}.import", default="Import from My Health Record"),
                       command=self.import_record).pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(master, text=_t(f"{_K}.sealed", default="Stored encrypted; only the trip's leaders and the "
                                                          "health team can read it, and every read is logged."),
                  foreground='gray').grid(row=8, column=0, columnspan=4, sticky=tk.W, padx=5, pady=(6, 0))
        return None

    def toggle_consent(self):
        ok, _ = call(self, tm('medical').give_health_share_consent, self.auth, self.participant_id,
                     self.consent_var.get())
        if not ok:
            self.consent_var.set(not self.consent_var.get())

    def import_record(self):
        auth, pid = self.auth, self.participant_id

        def done(fields):
            if not fields:
                messagebox.showinfo(self.title(), _t(f"{_K}.nothing_imported",
                                                     default="Your health record had nothing to copy."), parent=self)
                return
            try:
                fresh = tm('medical').my_health_details(auth, pid)
            except Exception as exc:
                show_error(self, exc)
                return
            for key, box in self.texts.items():
                box.delete('1.0', tk.END)
                box.insert('1.0', fresh.get(key) or '')
            for key, var in self.vars.items():
                var.set(fresh.get(key) or '')
            messagebox.showinfo(self.title(), tf(f"{_K}.imported", "Copied: {fields}.",
                                                 fields=", ".join(title_case(f) for f in fields)), parent=self)

        run_async(self, lambda: tm('medical').import_from_health_record(auth, pid), done)

    def validate(self):
        return self.details is not None

    def apply(self):
        fields = {k: box.get('1.0', tk.END).strip() for k, box in self.texts.items()}
        fields.update({k: var.get().strip() for k, var in self.vars.items()})
        ok, _ = call(self.parent, tm('medical').update_health_details, self.auth, self.participant_id, **fields)
        if ok:
            messagebox.showinfo(self.title(), _t(f"{_K}.health_saved", default="Details saved."), parent=self.parent)


def show_medical_sheet(parent, auth, trip_id):
    """The restricted medical & dietary sheet for a trip (``medical.participant_health``)."""
    if not messagebox.askyesno(
            _t(f"{_K}.medical_sheet", default="Medical & Dietary (restricted)"),
            _t(f"{_K}.medical_warning",
               default="This shows special-category health data for everyone on the trip. Your access "
                       "is recorded in the audit log. Continue?"), icon=messagebox.WARNING, parent=parent):
        return None
    ok, rows = call(parent, tm('medical').participant_health, auth, trip_id)
    if not ok:
        return None
    trip = tm('trips').get_trip(trip_id) or {}
    win = tk.Toplevel(parent)
    win.title(tf(f"{_K}.medical_title", "Medical & Dietary (restricted) — {name}", name=trip.get('trip_name', '')))
    win.geometry("1150x600")
    try:
        win.transient(parent.winfo_toplevel())
    except tk.TclError:
        pass
    bar = ttk.Frame(win)
    bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=8)
    ttk.Label(bar, text=_t(f"{_K}.medical_footer", default="Do not copy or print this list unless the trip needs it."),
              foreground='#a33').pack(side=tk.LEFT)
    ttk.Button(bar, text=_t("common.close", default="Close"), command=win.destroy).pack(side=tk.RIGHT)
    holder = ttk.Frame(win, padding=10)
    holder.pack(fill=tk.BOTH, expand=True)
    tree = make_tree(holder, [('name', _t(f"{_K}.name", default="Name"), 170),
                              ('student', _t(f"{_K}.student", default="Student"), 80),
                              ('status', _t(f"{_K}.status", default="Status"), 80),
                              ('medical', _t(f"{_K}.medical_col", default="Medical"), 280),
                              ('dietary', _t(f"{_K}.dietary_col", default="Dietary"), 150),
                              ('access', _t(f"{_K}.access_col", default="Accessibility"), 150),
                              ('contact', _t(f"{_K}.contact_col", default="Emergency Contact"), 200)], height=20)
    for r in rows:
        tree.insert('', 'end', values=(r['name'], r.get('student_id') or '', title_case(r['status']),
                                       (r.get('medical_info') or '').replace('\n', '; '),
                                       r.get('dietary_requirements') or '', r.get('accessibility_needs') or '',
                                       r.get('emergency_contact') or ''))
    return win


# ---------------------------------------------------------------------------
# Organisers' participant panel
# ---------------------------------------------------------------------------

class ParticipantsPanel(Panel):
    key = 'participants'
    title = _t(f"{_K}.participants_tab", default="Participants & Payments")

    def build(self):
        self.rows = {}
        actions = self.bar()
        self.button(actions, _t(f"{_K}.record_payment", default="Take / Record Payment..."), self.pay)
        self.button(actions, _t(f"{_K}.hardship_btn", default="Hardship Award..."), self.hardship)
        self.button(actions, _t(f"{_K}.schedule", default="Instalment Schedule"), self.schedule)
        self.button(actions, _t(f"{_K}.edit_health", default="Health Details..."), self.health)
        self.button(actions, _t(f"{_K}.medical_sheet", default="Medical & Dietary (restricted)"), self.medical_sheet)
        filters = self.bar()
        ttk.Label(filters, text=_t(f"{_K}.search", default="Search:")).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self._fill())
        ttk.Entry(filters, textvariable=self.search_var, width=24).pack(side=tk.LEFT, padx=5)
        self.ended_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filters, text=_t(f"{_K}.include_ended", default="Include cancelled / removed"),
                        variable=self.ended_var, command=self.reload).pack(side=tk.LEFT, padx=5)
        self.summary_var = tk.StringVar()
        ttk.Label(filters, textvariable=self.summary_var).pack(side=tk.LEFT, padx=10)

        self.tree = make_tree(self, [('name', _t(f"{_K}.name", default="Name"), 170),
                                     ('student', _t(f"{_K}.student", default="Student"), 80),
                                     ('status', _t(f"{_K}.status", default="Status"), 90),
                                     ('waitlist', _t(f"{_K}.waitlist", default="Waitlist"), 70),
                                     ('offer', _t(f"{_K}.offer", default="Offer Expires"), 130),
                                     ('payment', _t(f"{_K}.payment", default="Payment"), 80),
                                     ('paid', _t(f"{_K}.paid_col", default="Paid"), 70),
                                     ('hardship', _t(f"{_K}.hardship_col", default="Hardship"), 70),
                                     ('owed', _t(f"{_K}.owed", default="Owed"), 70),
                                     ('email', _t(f"{_K}.email", default="Email"), 190)], height=14)
        self.tree.tag_configure('waitlisted', foreground='#666')
        self.tree.tag_configure('offered', background='#e6f0ff')
        self.tree.tag_configure('owing', background='#fff1bf')

    def clear(self):
        clear_tree(self.tree)
        self.rows = {}
        self.summary_var.set('')

    def load(self, trip_id):
        auth, include_ended, trip = self.auth, self.ended_var.get(), self.trip

        def work():
            regs, money_mod, db = tm('registrations'), tm('money'), tm('database')
            people = regs.list_participants(auth, trip_id, include_ended=include_ended)
            places = {}
            with db.read_connection() as c:
                for p in people:
                    places[p['id']] = regs.get_participant(p['id'], conn=c)
            waiting = {w['participant_id']: w['place'] for w in tm('waitlist').positions(trip_id)}
            rows = []
            for p in people:
                place = places.get(p['id']) or {}
                owed = (money_mod.amount_owed(place, trip)
                        if p['status'] in ('registered', 'offered', 'confirmed', 'attended') else 0.0)
                rows.append(dict(p, hardship_award=place.get('hardship_award'), owed=owed,
                                 waitlist_place=waiting.get(p['id'])))
            return rows

        def done(rows):
            if self.trip_id != trip_id:
                return
            self.rows = {str(r['id']): r for r in rows}
            self._fill()

        run_async(self, work, done, status=self.ws.status)

    def _fill(self):
        clear_tree(self.tree)
        term = self.search_var.get().strip().lower()
        shown = owed_total = 0
        for iid, r in self.rows.items():
            if term and term not in f"{r.get('name')} {r.get('student_id')} {r.get('email')} {r.get('status')}".lower():
                continue
            shown += 1
            owed_total += r['owed'] or 0
            tags = (r['status'],) if r['status'] in ('waitlisted', 'offered') else (('owing',) if r['owed'] else ())
            self.tree.insert('', 'end', iid=iid, tags=tags, values=(
                r.get('name') or '', r.get('student_id') or 'staff', title_case(r['status']),
                f"#{r['waitlist_place']}" if r.get('waitlist_place') else '', r.get('offer_expires_at') or '',
                title_case(r.get('payment_status')), money(r.get('amount_paid')), money(r.get('hardship_award')),
                money(r['owed']), r.get('email') or ''))
        self.summary_var.set(tf(f"{_K}.summary", "{n} shown; {owed} owed.", n=shown, owed=money(owed_total)))

    def _selected(self):
        row = self.rows.get(selected_iid(self.tree) or '')
        if not row:
            messagebox.showwarning(self.title, _t(f"{_K}.pick", default="Select a participant."),
                                   parent=self.winfo_toplevel())
        return row

    def pay(self):
        row = self._selected()
        if row:
            PayDialog(self.winfo_toplevel(), self.auth, row['id'], self.changed)

    def hardship(self):
        row = self._selected()
        if row and HardshipDialog(self.winfo_toplevel(), self.auth, row['id'], row.get('name') or '').saved:
            self.changed()

    def schedule(self):
        row = self._selected()
        if not row:
            return
        ok, items = call(self, tm('money').instalment_schedule, row['id'])
        if ok:
            text = "\n".join(f"{i['due_date']}  {i['label']}: {money(i['amount'])} — {'paid' if i['paid'] else 'due'}"
                             for i in items) or _t(f"{_K}.no_instalments", default="This trip has no instalment schedule.")
            messagebox.showinfo(tf(f"{_K}.schedule_for", "Instalments — {name}", name=row.get('name') or ''),
                                text + "\n\n" + tf(f"{_K}.owed_now", "Owed now: {owed}", owed=money(row['owed'])),
                                parent=self.winfo_toplevel())

    def health(self):
        row = self._selected()
        if row:
            HealthDetailsDialog(self.winfo_toplevel(), self.auth, row['id'], own=False)

    def medical_sheet(self):
        if self.need_trip():
            show_medical_sheet(self.winfo_toplevel(), self.auth, self.trip_id)
