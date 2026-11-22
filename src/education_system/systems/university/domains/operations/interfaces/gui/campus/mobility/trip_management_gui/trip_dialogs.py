
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog
from datetime import datetime
import logging

# Dates are picked from dropdowns: the stored format is exact and a
# typed date was a validation error waiting to happen.
from education_system.platform.delivery.gui.date_picker import (
    DatePicker,
    recent_years,
)

from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, call, run_async, money, title_case, trip_label, trips_for, show_error,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.trip_dialogs'
logger = logging.getLogger(__name__)


def _format_trip_dates(start, end):
    """One date for a single-day trip, a span for a longer one."""
    start = (start or "").strip()
    end = (end or "").strip()
    if not start:
        return end or "to be confirmed"
    if not end or end == start:
        return start
    return f"{start} to {end}"


def notify_trip_participants(trip_id, template_name, extra_vars=None):
    """Email everyone holding a place on a trip with one of the mobility templates.

    Uses ``send_template_email`` and the JSON templates under
    ``assets/templates/email/campus_services/mobility/``; the recipients come
    from the trip domain (``comms.participant_contacts``). Returns the number
    of participants emailed. Never raises: a mail problem must not hide the
    trip change the operator just made.
    """
    try:
        trip = tm('trips').get_trip(trip_id)
        if not trip:
            return 0
        with tm('database').read_connection() as c:
            participants = tm('comms').participant_contacts(c, trip_id)
    except Exception:
        logger.warning("trip %s: could not load participants to notify", trip_id, exc_info=True)
        return 0
    return email_people(trip, participants, template_name, extra_vars)


def email_people(trip, participants, template_name, extra_vars=None):
    """Send a mobility template to ``participants`` (``comms.participant_contacts``
    rows) about ``trip`` (a dict). Returns the number sent; never raises."""
    from education_system.systems.university.infrastructure.email import send_template_email

    trip_id = trip.get('id')
    base = {
        "trip_name": trip.get('trip_name') or "",
        "destination": trip.get('destination') or "",
        "trip_dates": _format_trip_dates(trip.get('start_date'), trip.get('end_date')),
        "trip_status": title_case(trip.get('status')),
    }
    base.update(extra_vars or {})
    sent = 0
    for person in participants:
        email = person.get('email')
        if not email or "@" not in str(email):
            continue
        try:
            send_template_email(f"campus_services/mobility/{template_name}", email,
                                dict(base, participant_name=person.get('name') or 'Participant'))
            sent += 1
        except Exception:
            logger.warning("trip %s: could not email %s", trip_id, email, exc_info=True)
    return sent


def _as_dict(row):
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    try:
        return dict(row)          # sqlite3.Row
    except (TypeError, ValueError):
        return {}


class TripDetailsDialog(Dialog):
    """Read-only trip details.

    ``trip_data`` is the trip dict (``trips.get_trip``); ``participants_data``
    the rows from ``registrations.list_participants`` (``None`` when the
    viewer may not see the list); ``details`` optional extras —
    ``approval`` (``approvals.approval_state``), ``problems``
    (``approvals.gate_problems``) and ``health_counts`` (``medical.counts``).
    """

    def __init__(self, parent, trip_data, participants_data, details=None):
        self.trip_data = _as_dict(trip_data)
        self.participants_data = participants_data
        self.details = details or {}
        super().__init__(parent, _t(f"{_K}.windows.details", default="Trip Details"))

    def body(self, master):
        trip = self.trip_data
        info_frame = ttk.LabelFrame(master, text=_t(f"{_K}.labels.trip_information", default="Trip Information"), padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        fields = [
            ("ID:", str(trip.get('id', ''))),
            ("Name:", trip.get('trip_name') or ''),
            ("Description:", trip.get('description') or "None"),
            ("Destination:", trip.get('destination') or ''),
            ("Start Date:", trip.get('start_date') or ''),
            ("End Date:", trip.get('end_date') or ''),
            ("Max Participants:", str(trip.get('max_participants') or '')),
            ("Cost:", money(trip.get('cost'))),
            ("Status:", title_case(trip.get('status'), "Unknown")),
            ("Type:", title_case(trip.get('trip_type'), "Day")),
            ("Organiser:", (f"Students' Union - {trip.get('organising_club')}" if trip.get('source') == 'su'
                            else "University")),
            ("Country:", trip.get('country') or "UK"),
            ("24/7 Contact:", trip.get('emergency_contact_24h') or "Not set"),
            ("Created:", trip.get('created_at') or ''),
            ("Updated:", f"{trip.get('updated_at') or ''} by {trip.get('updated_by') or '-'} (version {trip.get('version') or 1})"),
        ]
        approval = self.details.get('approval')
        if approval:
            parts = [f"{tm('approvals').STAGE_LABELS.get(s, s)}: {title_case(v['decision'])}"
                     for s, v in approval['stages'].items()]
            fields.append(("Approvals:", "; ".join(parts) or "None needed"))
        counts = self.details.get('health_counts')
        if counts is not None:
            fields.append(("Health details:", f"medical {counts['medical_info']}, dietary "
                                              f"{counts['dietary_requirements']}, accessibility "
                                              f"{counts['accessibility_needs']} (restricted)"))
        for row, (label, value) in enumerate(fields):
            ttk.Label(info_frame, text=label, font=('Arial', 9, 'bold')).grid(row=row, column=0, sticky=tk.NW, padx=(0, 10), pady=2)
            ttk.Label(info_frame, text=value, wraplength=460, justify=tk.LEFT).grid(row=row, column=1, sticky=tk.W, pady=2)

        problems = self.details.get('problems')
        if problems:
            gate = ttk.LabelFrame(master, text=_t(f"{_K}.labels.before_opening", default="Before it can open"), padding=8)
            gate.pack(fill=tk.X, padx=10, pady=5)
            ttk.Label(gate, text="\n".join(f"• {p}" for p in problems), foreground="#a33",
                      wraplength=520, justify=tk.LEFT).pack(anchor=tk.W)

        if self.participants_data is None:
            return None
        participants_frame = ttk.LabelFrame(master, text=f"Participants ({len(self.participants_data)})", padding=10)
        participants_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        if not self.participants_data:
            ttk.Label(participants_frame, text=_t(f"{_K}.labels.no_participants_registered_yet", default="No participants registered yet.")).pack()
            return None
        tree = ttk.Treeview(participants_frame, columns=('name', 'email', 'registration', 'payment', 'status'), show='headings', height=8)
        tree.heading('name', text=_t(f"{_K}.headings.name", default='Name'))
        tree.heading('email', text=_t(f"{_K}.headings.email", default='Email'))
        tree.heading('registration', text=_t(f"{_K}.headings.registration_date", default='Registration Date'))
        tree.heading('payment', text=_t(f"{_K}.headings.payment_status", default='Payment Status'))
        tree.heading('status', text=_t(f"{_K}.headings.status", default='Status'))
        for p in self.participants_data:
            p = _as_dict(p)
            tree.insert('', 'end', values=(p.get('name') or p.get('student_id') or "Unknown",
                                           p.get('email') or "N/A", p.get('registration_date') or '',
                                           title_case(p.get('payment_status')), title_case(p.get('status'))))
        tree.pack(fill=tk.BOTH, expand=True)
        return None

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text=_t(f"{_K}.buttons.close", default="Close"), command=self.ok).pack(side=tk.RIGHT, padx=5)
        box.pack(pady=5)


class _TripForm(Dialog):
    """Fields shared by the create and update dialogs."""

    def _build_core(self, master, trip):
        ttk.Label(master, text=_t(f"{_K}.labels.trip_name", default="Trip Name:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.name_var = tk.StringVar(value=trip.get('trip_name') or '')
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.description", default="Description:")).grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.description_text = tk.Text(master, width=40, height=3)
        self.description_text.insert(1.0, trip.get('description') or "")
        self.description_text.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.destination", default="Destination:")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.destination_var = tk.StringVar(value=trip.get('destination') or '')
        ttk.Entry(master, textvariable=self.destination_var, width=40).grid(row=2, column=1, padx=5, pady=5)

    def _build_more(self, master, trip):
        """The planning details the approval / safety gates depend on."""
        more = ttk.LabelFrame(master, text=_t(f"{_K}.labels.more_details", default="Planning details"), padding=8)
        more.grid(row=0, column=2, rowspan=9, sticky=tk.N + tk.S, padx=(12, 5), pady=5)
        db = tm('database')
        r = 0

        def row(label, widget):
            nonlocal r
            ttk.Label(more, text=label).grid(row=r, column=0, sticky=tk.W, pady=2)
            widget.grid(row=r, column=1, sticky=tk.W, pady=2)
            r += 1

        self.type_var = tk.StringVar(value=trip.get('trip_type') or 'day')
        row(_t(f"{_K}.labels.trip_type", default="Trip type:"),
            ttk.Combobox(more, textvariable=self.type_var, values=list(db.TRIP_TYPES), state="readonly", width=18))
        self.country_var = tk.StringVar(value=trip.get('country') or '')
        row(_t(f"{_K}.labels.country", default="Country (if abroad):"), ttk.Entry(more, textvariable=self.country_var, width=20))
        self.budget_var = tk.StringVar(value='' if trip.get('budget') is None else str(trip.get('budget')))
        row(_t(f"{_K}.labels.budget", default="Budget (£):"), ttk.Entry(more, textvariable=self.budget_var, width=12))
        self.deposit_var = tk.StringVar(value=str(trip.get('deposit_amount') or 0))
        row(_t(f"{_K}.labels.deposit", default="Deposit (£):"), ttk.Entry(more, textvariable=self.deposit_var, width=12))
        self.deposit_due_var = tk.StringVar(value=trip.get('deposit_due') or '')
        row(_t(f"{_K}.labels.deposit_due", default="Deposit due (YYYY-MM-DD):"), ttk.Entry(more, textvariable=self.deposit_due_var, width=12))
        self.balance_due_var = tk.StringVar(value=trip.get('balance_due') or '')
        row(_t(f"{_K}.labels.balance_due", default="Balance due (YYYY-MM-DD):"), ttk.Entry(more, textvariable=self.balance_due_var, width=12))
        self.ratio_var = tk.StringVar(value=str(trip.get('min_staff_ratio') or 10))
        row(_t(f"{_K}.labels.ratio", default="Students per staff member:"), ttk.Entry(more, textvariable=self.ratio_var, width=6))
        self.contact_var = tk.StringVar(value=trip.get('emergency_contact_24h') or '')
        row(_t(f"{_K}.labels.contact_24h", default="24/7 emergency contact:"), ttk.Entry(more, textvariable=self.contact_var, width=24))

        def flag(name, default):
            value = trip.get(name)
            return tk.BooleanVar(value=bool(default if value is None else int(value or 0)))

        self.overseas_flag = flag('is_overseas', 0)
        self.first_aider_flag = flag('requires_first_aider', 1)
        self.minors_flag = flag('involves_minors', 0)
        self.vulnerable_flag = flag('involves_vulnerable_adults', 0)
        self.hardship_flag = flag('hardship_eligible', 1)
        for text, var in ((_t(f"{_K}.labels.overseas", default="Overseas trip"), self.overseas_flag),
                          (_t(f"{_K}.labels.first_aider", default="Needs a first aider"), self.first_aider_flag),
                          (_t(f"{_K}.labels.minors", default="Involves under-18s"), self.minors_flag),
                          (_t(f"{_K}.labels.vulnerable", default="Involves vulnerable adults"), self.vulnerable_flag),
                          (_t(f"{_K}.labels.hardship", default="Hardship support available"), self.hardship_flag)):
            ttk.Checkbutton(more, text=text, variable=var).grid(row=r, column=0, columnspan=2, sticky=tk.W)
            r += 1

    def _more_fields(self):
        return {
            'trip_type': self.type_var.get() or 'day',
            'country': self.country_var.get().strip() or None,
            'budget': self.budget_var.get().strip(),
            'deposit_amount': self.deposit_var.get().strip(),
            'deposit_due': self.deposit_due_var.get().strip(),
            'balance_due': self.balance_due_var.get().strip(),
            'min_staff_ratio': self.ratio_var.get().strip() or 10,
            'emergency_contact_24h': self.contact_var.get().strip() or None,
            'is_overseas': self.overseas_flag.get() or self.type_var.get() == 'overseas',
            'requires_first_aider': self.first_aider_flag.get(),
            'involves_minors': self.minors_flag.get(),
            'involves_vulnerable_adults': self.vulnerable_flag.get(),
            'hardship_eligible': self.hardship_flag.get(),
        }

    def _check_basics(self):
        """Quick checks before the domain's own (which has the final say)."""
        error = None
        if len(self.name_var.get().strip()) < 3:
            error = _t(f"{_K}.dialogs.trip_name_must_be_at_least_3_characters_long", default="Trip name must be at least 3 characters long.")
        elif len(self.destination_var.get().strip()) < 3:
            error = _t(f"{_K}.dialogs.destination_must_be_at_least_3_characters_long", default="Destination must be at least 3 characters long.")
        else:
            try:
                if int(self.max_participants_var.get()) <= 0:
                    error = _t(f"{_K}.dialogs.maximum_participants_must_be_greater_than_0", default="Maximum participants must be greater than 0.")
                elif float(self.cost_var.get()) < 0:
                    error = _t(f"{_K}.dialogs.cost_cannot_be_negative", default="Cost cannot be negative.")
            except ValueError as e:
                error = f"Invalid input: {e}"
        if error:
            messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), error, parent=self)
            return False
        return True


class CreateTripDialog(_TripForm):
    """Create a trip through ``trips.create_trip_record`` (it starts 'proposed')."""

    SUBMIT = 'submit for approval'

    def __init__(self, parent, auth, refresh_callback):
        self.auth = auth
        self.refresh_callback = refresh_callback
        super().__init__(parent, _t(f"{_K}.windows.create", default="Create New Trip"))

    def body(self, master):
        self._build_core(master, {})

        ttk.Label(master, text=_t(f"{_K}.labels.duration", default="Duration:")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.duration_var = tk.StringVar(value="single")
        duration_frame = ttk.Frame(master)
        duration_frame.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Radiobutton(duration_frame, text=_t(f"{_K}.labels.single_day", default="Single day"),
                        variable=self.duration_var, value="single",
                        command=self._toggle_duration).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Radiobutton(duration_frame, text=_t(f"{_K}.labels.multiple_days", default="Multiple days"),
                        variable=self.duration_var, value="multi",
                        command=self._toggle_duration).pack(side=tk.LEFT)

        self.start_label = ttk.Label(master, text=_t(f"{_K}.labels.date", default="Date:"))
        self.start_label.grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_date_picker = DatePicker(master, years=recent_years(ahead=3, back=1))
        self.start_date_picker.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        self.end_label = ttk.Label(master, text=_t(f"{_K}.labels.end_date", default="End Date:"))
        self.end_date_picker = DatePicker(master, years=recent_years(ahead=3, back=1))
        self._toggle_duration()

        ttk.Label(master, text=_t(f"{_K}.labels.max_participants", default="Max Participants:")).grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_participants_var = tk.StringVar(value="50")
        ttk.Entry(master, textvariable=self.max_participants_var, width=40).grid(row=6, column=1, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.cost_per_person", default="Cost per person (£):")).grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        self.cost_var = tk.StringVar(value="0.0")
        ttk.Entry(master, textvariable=self.cost_var, width=40).grid(row=7, column=1, padx=5, pady=5)

        # New trips always start 'proposed'; the choice here is whether to
        # send it straight on for approval.
        ttk.Label(master, text=_t(f"{_K}.labels.status", default="Status:")).grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
        self.status_var = tk.StringVar(value='proposed')
        ttk.Combobox(master, textvariable=self.status_var, values=['proposed', self.SUBMIT],
                     state="readonly", width=37).grid(row=8, column=1, padx=5, pady=5)

        self._build_more(master, {})
        return self.name_entry

    def _toggle_duration(self):
        if self.duration_var.get() == "multi":
            self.start_label.configure(text=_t(f"{_K}.labels.start_date", default="Start Date:"))
            self.end_label.grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
            self.end_date_picker.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        else:
            self.start_label.configure(text=_t(f"{_K}.labels.date", default="Date:"))
            self.end_label.grid_remove()
            self.end_date_picker.grid_remove()

    def _dates(self):
        start = self.start_date_picker.get()
        if self.duration_var.get() == "multi":
            return start, self.end_date_picker.get()
        return start, start

    def validate(self):
        if not self._check_basics():
            return False
        raw_start, raw_end = self._dates()
        error = None
        if not raw_start or not raw_end:
            error = _t(f"{_K}.dialogs.pick_the_dates", default="Pick the trip date(s).")
        else:
            start = datetime.strptime(raw_start, '%Y-%m-%d').date()
            end = datetime.strptime(raw_end, '%Y-%m-%d').date()
            if start <= datetime.now().date():
                error = _t(f"{_K}.dialogs.start_date_must_be_in_the_future", default="Start date must be in the future.")
            elif end < start:
                error = _t(f"{_K}.dialogs.end_date_must_be_after_start_date", default="End date must be on or after the start date.")
        if error:
            messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), error, parent=self)
            return False
        return True

    def apply(self):
        start, end = self._dates()
        fields = dict(self._more_fields(),
                      trip_name=self.name_var.get().strip(),
                      description=self.description_text.get(1.0, tk.END).strip(),
                      destination=self.destination_var.get().strip(),
                      start_date=start, end_date=end,
                      max_participants=self.max_participants_var.get(),
                      cost=self.cost_var.get())
        parent = self.parent
        ok, trip = call(parent, tm('trips').create_trip_record, self.auth, **fields)
        if not ok:
            return
        text = tf(f"{_K}.dialogs.created", "Trip '{name}' created (status: Proposed).", name=trip['trip_name'])
        if self.status_var.get() == self.SUBMIT:
            ok, state = call(parent, tm('approvals').submit_for_approval, self.auth, trip['id'])
            if ok:
                labels = tm('approvals').STAGE_LABELS
                text += "\n\n" + tf(f"{_K}.dialogs.submitted", "Submitted for approval: {stages}.",
                                    stages=", ".join(labels.get(s, s) for s in state['outstanding']))
        else:
            text += "\n\n" + _t(f"{_K}.dialogs.next_submit",
                                default="Submit it for approval from Trip Workspace > Approvals when it is ready.")
        messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), text, parent=parent)
        if self.refresh_callback:
            self.refresh_callback()


class UpdateTripDialog(_TripForm):
    """Change a trip through ``trips.update_trip_record``; a status change goes
    through ``trips.set_trip_status`` (gated — every problem is listed) and
    participants are told about changes that affect them
    (``comms.change_notice``)."""

    def __init__(self, parent, auth, trip_id, refresh_callback):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.refresh_callback = refresh_callback
        self.trip_data = None
        self.load_trip_data()
        super().__init__(parent, _t(f"{_K}.windows.update", default="Update Trip"))

    def load_trip_data(self):
        try:
            self.trip_data = tm('trips').get_trip(self.trip_id)
        except Exception:
            self.trip_data = None

    def body(self, master):
        if not self.trip_data:
            ttk.Label(master, text=_t(f"{_K}.labels.trip_not_found", default="Trip not found.")).grid(row=0, column=0, pady=20)
            return None
        trip = self.trip_data
        self._build_core(master, trip)

        ttk.Label(master, text=_t(f"{_K}.labels.start_date_yyyy_mm_dd", default="Start Date (YYYY-MM-DD):")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_date_picker = DatePicker(master, value=trip['start_date'], years=recent_years(ahead=3, back=3))
        self.start_date_picker.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.end_date_yyyy_mm_dd", default="End Date (YYYY-MM-DD):")).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_date_picker = DatePicker(master, value=trip.get('end_date') or trip['start_date'], years=recent_years(ahead=3, back=3))
        self.end_date_picker.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.max_participants", default="Max Participants:")).grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_participants_var = tk.StringVar(value=str(trip.get('max_participants') or ''))
        ttk.Entry(master, textvariable=self.max_participants_var, width=40).grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.cost_per_person", default="Cost per person (£):")).grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.cost_var = tk.StringVar(value=str(trip.get('cost') or 0))
        ttk.Entry(master, textvariable=self.cost_var, width=40).grid(row=6, column=1, padx=5, pady=5)

        # Only the moves the life cycle allows from here are offered.
        ttk.Label(master, text=_t(f"{_K}.labels.status", default="Status:")).grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        current = trip.get('status') or 'proposed'
        allowed = [current] + list(tm('trips').TRIP_STATUS_TRANSITIONS.get(current, ()))
        self.status_var = tk.StringVar(value=current)
        ttk.Combobox(master, textvariable=self.status_var, values=allowed,
                     state="readonly", width=37).grid(row=7, column=1, padx=5, pady=5)
        ttk.Label(master, text=_t(f"{_K}.labels.status_reason", default="Reason for status change:")).grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
        self.reason_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.reason_var, width=40).grid(row=8, column=1, padx=5, pady=5)

        self._build_more(master, trip)
        return self.name_entry

    def validate(self):
        if not self.trip_data:
            return False
        if not self.start_date_picker.get() or not self.end_date_picker.get():
            messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"),
                                 _t(f"{_K}.dialogs.pick_the_dates", default="Pick the trip date(s)."), parent=self)
            return False
        return self._check_basics()

    def _describe_changes(self):
        """One line per changed field a participant would care about."""
        before = self.trip_data or {}
        fields = [
            ("Trip name", before.get('trip_name'), self.name_var.get().strip()),
            ("Destination", before.get('destination'), self.destination_var.get().strip()),
            ("Start date", before.get('start_date'), self.start_date_picker.get()),
            ("End date", before.get('end_date'), self.end_date_picker.get()),
            ("Cost", f"{float(before.get('cost') or 0):.2f}", f"{float(self.cost_var.get() or 0):.2f}"),
        ]
        return "\n".join(f"{label}: {old or '-'} -> {new or '-'}" for label, old, new in fields
                         if str(old or "").strip() != str(new or "").strip())

    def apply(self):
        fields = dict(self._more_fields(),
                      trip_name=self.name_var.get().strip(),
                      description=self.description_text.get(1.0, tk.END).strip(),
                      destination=self.destination_var.get().strip(),
                      start_date=self.start_date_picker.get(), end_date=self.end_date_picker.get(),
                      max_participants=self.max_participants_var.get(), cost=self.cost_var.get())
        old_status = self.trip_data.get('status')
        new_status = self.status_var.get()
        reason = self.reason_var.get().strip()
        changes = self._describe_changes()
        auth, trip_id, parent, refresh = self.auth, self.trip_id, self.parent, self.refresh_callback

        def work():
            trips = tm('trips')
            out = {'trip': trips.update_trip_record(auth, trip_id, **fields)}
            if new_status != old_status:
                try:
                    out.update(trips.set_trip_status(auth, trip_id, new_status, reason))
                except (ValueError, PermissionError) as exc:
                    out['status_error'] = exc
            if changes:
                try:
                    out['emailed'] = tm('comms').change_notice(auth, trip_id, changes)
                except Exception as exc:
                    out['notice_error'] = exc
            return out

        def done(out):
            text = _t(f"{_K}.dialogs.trip_updated_successfully", default="Trip updated successfully!")
            if out.get('emailed'):
                text += "\n\n" + tf(f"{_K}.dialogs.emailed", "{n} participant(s) emailed about the change.",
                                    n=out['emailed'])
            if out.get('notice_error'):
                text += "\n\n" + tf(f"{_K}.dialogs.notice_failed", "Participants could not be told: {error}",
                                    error=out['notice_error'])
            if out.get('refunds'):
                text += "\n\n" + tf(f"{_K}.dialogs.refunds", "{n} refund(s) processed.", n=len(out['refunds']))
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), text, parent=parent)
            if out.get('status_error'):
                show_error(parent, out['status_error'],
                           _t(f"{_K}.dialogs.status_not_changed", default="Status not changed"))
            if refresh:
                refresh()

        run_async(parent, work, done)


class TripSelectionDialog(Dialog):
    """Pick a trip, then ``callback(trip_id)``.

    ``purpose`` chooses the list (``_api.trips_for``): 'view' gives staff
    every trip and students the trips they are registered on; 'manage' the
    trips the user can manage.
    """

    def __init__(self, parent, auth, callback, purpose='view', include_archived=False):
        self.auth = auth
        self.callback = callback
        self.purpose = purpose
        self.include_archived = include_archived
        self.selected_trip_id = None
        self.trips = []
        super().__init__(parent, _t(f"{_K}.windows.select", default="Select Trip"))

    def body(self, master):
        ttk.Label(master, text=_t(f"{_K}.labels.select_a_trip", default="Select a trip:"), font=('Arial', 10, 'bold')).pack(pady=(0, 6))
        search = ttk.Frame(master)
        search.pack(fill=tk.X, padx=10)
        ttk.Label(search, text=_t(f"{_K}.labels.search", default="Search:")).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self._fill())
        entry = ttk.Entry(search, textvariable=self.search_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.trip_listbox = tk.Listbox(master, width=70, height=15)
        self.trip_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 10))
        self.trip_listbox.bind('<Double-1>', lambda _e: self.ok())
        self.load_trips()
        return entry

    def load_trips(self):
        try:
            self.trips = trips_for(self.auth, self.purpose, self.include_archived)
        except Exception as exc:
            show_error(self, exc)
            self.trips = []
        self._fill()
        if not self.trips:
            self.trip_listbox.insert(tk.END, _t(f"{_K}.labels.no_trips", default="(no trips)"))

    def _fill(self):
        term = (self.search_var.get() if hasattr(self, 'search_var') else '').strip().lower()
        self.trip_listbox.delete(0, tk.END)
        self.shown = [t for t in self.trips
                      if not term or term in f"{t.get('trip_name')} {t.get('destination')} {t.get('status')} {t.get('start_date')}".lower()]
        for trip in self.shown:
            self.trip_listbox.insert(tk.END, f"{trip_label(trip)} - {trip.get('destination') or ''}")

    def validate(self):
        selection = self.trip_listbox.curselection()
        if not selection or selection[0] >= len(getattr(self, 'shown', [])):
            messagebox.showwarning(_t(f"{_K}.dialogs.no_selection", default="No Selection"), _t(f"{_K}.dialogs.please_select_a_trip", default="Please select a trip."), parent=self)
            return False
        self.selected_trip_id = self.shown[selection[0]]['id']
        return True

    def apply(self):
        if self.callback and self.selected_trip_id:
            self.callback(self.selected_trip_id)
