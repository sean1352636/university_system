"""Students' Union trips screen.

SU trips live in Trip Management's one trip store (``trips`` with
``source = 'su'`` and ``trips.organising_club``; places in
``trip_participants``) — the old ``union_trips`` tables were merged into it.
This screen reaches Trip Management only through
``services.bus.trip_bus``: it runs no SQL against trip tables. Every call
raises PermissionError / ValueError with a message written for the user,
which is shown as it is.

Who may do what:

* any student with ``register_for_trips`` browses open trips, registers
  (or joins the waiting list when a trip is full), pays, takes up or turns
  down a waiting-list offer and cancels their own place;
* Students' Union officers (any club) and club committee members (their
  club) propose trips, and edit, submit, open, cancel or archive them and
  see who is going (``trip_bus.su_organiser_scope``). A proposed trip needs
  approval before it opens for registration.
"""

import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.systems.university.infrastructure.email.email_service.core import send_email
from education_system.systems.university.services.bus import trip_bus

_INDIVIDUAL = '(No club - individual)'
_K = 'gui.pastoral.student_union_gui.trips.trips'


def _k(section, name, default):
    return _t(f'{_K}.{section}.{name}', default=default)


def _money(value):
    try:
        return f"£{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "£0.00"


class _FormDialog:
    """A small modal form: ``fields`` is ``[(key, label, default, kind)]``
    with kind 'entry', 'text' or 'check'. ``result`` is the dict, or None."""

    def __init__(self, parent, title, intro, fields, *, required=(), validate=None):
        self.result = None
        self._required = required
        self._validate = validate
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.transient(parent)
        frame = ttk.Frame(self.top, padding=15)
        frame.pack(fill='both', expand=True)
        if intro:
            ttk.Label(frame, text=intro, wraplength=460, justify='left').grid(
                row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        self._vars = {}
        row = 1
        for key, label, default, kind in fields:
            if kind == 'check':
                var = tk.BooleanVar(value=bool(default))
                ttk.Checkbutton(frame, text=label, variable=var).grid(
                    row=row, column=0, columnspan=2, sticky='w', pady=4)
            elif kind == 'text':
                ttk.Label(frame, text=label).grid(row=row, column=0, sticky='nw', pady=4)
                var = tk.Text(frame, width=40, height=3)
                if default:
                    var.insert('1.0', default)
                var.grid(row=row, column=1, sticky='w', pady=4)
            else:
                ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=4)
                var = tk.StringVar(value='' if default is None else str(default))
                ttk.Entry(frame, textvariable=var, width=40).grid(row=row, column=1, sticky='w', pady=4)
            self._vars[key] = var
            row += 1
        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(buttons, text=_k('buttons', 'ok', "OK"), command=self._ok).pack(side='left', padx=5)
        ttk.Button(buttons, text=_k('buttons', 'cancel', "Cancel"), command=self.top.destroy).pack(side='left', padx=5)
        try:
            self.top.grab_set()
        except tk.TclError:
            pass
        parent.wait_window(self.top)

    def _value(self, var):
        if isinstance(var, tk.Text):
            return var.get('1.0', 'end').strip()
        value = var.get()
        return value.strip() if isinstance(value, str) else value

    def _ok(self):
        values = {key: self._value(var) for key, var in self._vars.items()}
        missing = [key for key in self._required if not values.get(key)]
        if missing:
            messagebox.showwarning(_k('dialogs', 'missing_fields', "Missing Fields"),
                                   _k('dialogs', 'please_fill_in_the_required_fields',
                                      "Please fill in the required fields."), parent=self.top)
            return
        if self._validate:
            problem = self._validate(values)
            if problem:
                messagebox.showwarning(_k('dialogs', 'invalid_value', "Invalid Value"), problem,
                                       parent=self.top)
                return
        self.result = values
        self.top.destroy()


class StudentUnionTripsDialog:
    """Dialog for managing Student Union trips (optionally one club's)."""

    def __init__(self, parent, auth_manager, club=None):
        self.parent = parent
        self.auth = auth_manager
        self.club = club or None

        self.dialog = tk.Toplevel(parent)
        title = _k('windows', 'student_union_trip_management', "Student Union Trip Management")
        if self.club:
            title = f"{title} - {self.club}"
        self.dialog.title(title)
        self.dialog.geometry("1400x900")
        self.dialog.minsize(1200, 800)
        self.dialog.transient(parent)

        try:
            self._scope = trip_bus.su_organiser_scope(self.auth)
        except Exception as e:
            logger.warning("Could not read the Students' Union organiser scope: %s", e)
            self._scope = {'all': False, 'clubs': []}

        self._create_widgets()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _error(self, error, title=None):
        messagebox.showerror(title or _k('dialogs', 'error', "Error"), str(error), parent=self.dialog)

    def _is_organiser(self):
        return bool(self._scope.get('all') or self._scope.get('clubs'))

    @staticmethod
    def _clear(tree):
        for item in tree.get_children():
            tree.delete(item)

    def _make_tree(self, frame, columns):
        """``columns`` is ``[(name, heading, width, anchor)]``."""
        tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show='headings', height=18)
        for name, heading, width, anchor in columns:
            tree.heading(name, text=heading)
            tree.column(name, width=width, anchor=anchor)
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        return tree

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)

        # Tab 1 - Upcoming Trips
        self.upcoming_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.upcoming_frame, text=_k('tabs', 'upcoming_trips', "Upcoming Trips"))
        self._build_upcoming_tab()

        # Tab 2 - Organise Trip
        self.organise_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.organise_frame, text=_k('tabs', 'organise_trip', "Organise Trip"))
        self._build_organise_tab()

        # Tab 3 - My Trips
        self.my_trips_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.my_trips_frame, text=_k('tabs', 'my_trips', "My Trips"))
        self._build_my_trips_tab()

        # Tab 4 - Manage Trips (organisers: officers, club committees, creators)
        self.manage_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.manage_frame, text=_k('tabs', 'manage_trips', "Manage Trips"))
        self._build_manage_tab()

    # ------------------------------------------------------------------
    # Upcoming Trips tab
    # ------------------------------------------------------------------

    def _build_upcoming_tab(self):
        toolbar = ttk.Frame(self.upcoming_frame)
        toolbar.pack(fill='x', pady=(0, 8))

        ttk.Button(toolbar, text=_k('buttons', 'refresh', "Refresh"), command=self._load_upcoming_trips).pack(side='left')
        ttk.Button(toolbar, text=_k('buttons', 'register_for_selected_trip', "Register for Selected Trip"), command=self._register_for_trip).pack(side='right')
        ttk.Label(toolbar, text=_k('labels', 'full_trips_waiting_list',
                                   "Full trips offer a place on the waiting list."),
                  foreground='gray').pack(side='right', padx=10)

        self.upcoming_tree = self._make_tree(self.upcoming_frame, [
            ('trip_id', _k('headings', 'id', 'ID'), 50, 'center'),
            ('trip_name', _k('headings', 'trip_name', 'Trip Name'), 220, 'w'),
            ('date', _k('headings', 'date', 'Date'), 100, 'center'),
            ('destination', _k('headings', 'destination', 'Destination'), 180, 'w'),
            ('organizer', _k('headings', 'organizer', 'Organizer'), 160, 'w'),
            ('capacity', _k('headings', 'capacity', 'Capacity'), 70, 'center'),
            ('registered', _k('headings', 'registered', 'Registered'), 80, 'center'),
            ('cost', _k('headings', 'cost', 'Cost'), 80, 'center'),
            ('status', _k('headings', 'status', 'Status'), 80, 'center'),
        ])
        self._load_upcoming_trips()

    def _load_upcoming_trips(self):
        self._clear(self.upcoming_tree)
        self._upcoming = {}
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            rows = trip_bus.browse_trips(source='su', club=self.club)
        except Exception as e:
            logger.warning("Could not load Students' Union trips: %s", e)
            return
        for trip in rows:
            if trip['status'] not in ('open', 'full') or (trip.get('start_date') or '') < today:
                continue
            item = self.upcoming_tree.insert('', 'end', values=(
                trip['id'], trip['trip_name'], trip['start_date'], trip['destination'],
                trip.get('organising_club') or 'Individual', trip['max_participants'],
                trip.get('current_participants') or 0, _money(trip.get('cost')), trip['status']))
            self._upcoming[item] = trip

    def _registration_details(self, trip):
        """Ask for the emergency contact, needs and health-sharing consent."""
        form = _FormDialog(
            self.dialog, _k('windows', 'trip_registration', "Trip Registration"),
            _t(f'{_K}.labels.registration_intro',
               default="Registering for '{trip}'. Medical, dietary and accessibility details "
                       "are stored sealed and seen only by the trip's leaders.").format(trip=trip['trip_name']),
            [('emergency_contact_name', "Emergency contact name:", '', 'entry'),
             ('emergency_contact_phone', "Emergency contact phone:", '', 'entry'),
             ('emergency_contact_relationship', "Relationship to you:", '', 'entry'),
             ('accessibility_needs', "Accessibility needs:", '', 'text'),
             ('dietary_requirements', "Dietary requirements:", '', 'text'),
             ('medical_info', "Medical information:", '', 'text'),
             ('health_share_consent', "Share my health profile with this trip's leaders", False, 'check')],
            required=('emergency_contact_name', 'emergency_contact_phone'))
        return form.result

    def _register_for_trip(self):
        selected = self.upcoming_tree.selection()
        if not selected:
            messagebox.showwarning(_k('dialogs', 'no_selection', "No Selection"), _k('dialogs', 'please_select_a_trip_to_register_for', "Please select a trip to register for."), parent=self.dialog)
            return
        trip = self._upcoming.get(selected[0])
        if not trip:
            return

        current_user = self.auth.current_user if self.auth else None
        if not current_user:
            messagebox.showerror(_k('dialogs', 'error', "Error"), _k('dialogs', 'you_must_be_logged_in_to_register', "You must be logged in to register."), parent=self.dialog)
            return

        waitlist = False
        if trip['status'] == 'full' or (trip.get('current_participants') or 0) >= (trip['max_participants'] or 0):
            if not messagebox.askyesno(_k('dialogs', 'full', "Full"), _k('dialogs', 'trip_full_join_waiting_list', "This trip is already at full capacity. Join the waiting list? You will be offered a place if one comes free."), parent=self.dialog):
                return
            waitlist = True

        details = self._registration_details(trip)
        if details is None:
            return
        consent = bool(details.pop('health_share_consent', False))

        try:
            booking = trip_bus.register_participant(self.auth, trip['id'], waitlist=waitlist, **details)
        except (PermissionError, ValueError) as e:
            # TripFullError is a ValueError: someone took the last place meanwhile.
            if not waitlist and type(e).__name__ == 'TripFullError' and messagebox.askyesno(
                    _k('dialogs', 'full', "Full"), _k('dialogs', 'trip_full_join_waiting_list', "This trip is already at full capacity. Join the waiting list? You will be offered a place if one comes free."), parent=self.dialog):
                try:
                    booking = trip_bus.register_participant(self.auth, trip['id'], waitlist=True, **details)
                except (PermissionError, ValueError) as e2:
                    self._error(e2)
                    return
            else:
                self._error(e)
                return
        except Exception as e:
            logger.exception("SU trip registration failed")
            messagebox.showerror(_k('dialogs', 'error', "Error"), f"Could not register: {e}", parent=self.dialog)
            return

        if consent:
            try:
                trip_bus.give_trip_health_consent(self.auth, booking['participant_id'], True)
            except (PermissionError, ValueError) as e:
                self._error(e)

        if booking['status'] == 'waitlisted':
            messagebox.showinfo(_k('dialogs', 'waiting_list', "Waiting List"),
                                f"You are number {booking.get('position') or '?'} on the waiting list "
                                f"for '{trip['trip_name']}'. You will be e-mailed if a place is offered.",
                                parent=self.dialog)
        else:
            self._send_confirmation(booking, current_user)
            messagebox.showinfo(_k('dialogs', 'success', "Success"), f"You have been registered for '{trip['trip_name']}'.", parent=self.dialog)
            if float(booking.get('amount') or 0) > 0 and messagebox.askyesno(
                    _k('dialogs', 'payment', "Payment"),
                    f"This trip costs {_money(booking.get('amount'))}. Pay now?", parent=self.dialog):
                self._pay(booking['participant_id'], booking.get('amount'))
        self._load_upcoming_trips()
        self._load_my_trips()

    def _send_confirmation(self, booking, current_user):
        email = booking.get('email') or current_user.get('email')
        if not email:
            return
        try:
            send_email(
                email,
                f"Trip Registration Confirmation - {booking['trip_name']}",
                f"Hello {booking.get('name') or current_user.get('username', 'Student')},\n\n"
                f"You have successfully registered for the trip: {booking['trip_name']}.\n"
                f"Date: {booking.get('start_date')}\n"
                f"Destination: {booking.get('destination')}\n"
                f"Reference: {booking.get('reference')}\n\n"
                f"Thank you,\nStudent Union",
                kind="transactional", category="trips")
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    # ------------------------------------------------------------------
    # Organise Trip tab
    # ------------------------------------------------------------------

    def _build_organise_tab(self):
        form_frame = ttk.LabelFrame(self.organise_frame, text=_k('labels', 'create_a_new_trip', "Create a New Trip"), padding=15)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)

        row = 0
        if self._is_organiser():
            note = _k('labels', 'proposed_needs_approval',
                      "A new trip is proposed first; it opens for registration once it has been approved.")
        else:
            note = _k('labels', 'organisers_only',
                      "Only Students' Union officers and club committee members can propose trips.")
        ttk.Label(form_frame, text=note, foreground='gray').grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 8))

        row += 1
        ttk.Label(form_frame, text=_k('labels', 'trip_name', "Trip Name:")).grid(row=row, column=0, sticky='w', pady=4)
        self.trip_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.trip_name_var, width=40).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text=_k('labels', 'destination', "Destination:")).grid(row=row, column=0, sticky='w', pady=4)
        self.destination_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.destination_var, width=40).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text=_k('labels', 'trip_date_yyyy_mm_dd', "Trip Date (YYYY-MM-DD):")).grid(row=row, column=0, sticky='w', pady=4)
        self.trip_date_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.trip_date_var, width=20).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text=_k('labels', 'return_date_yyyy_mm_dd', "Return Date (YYYY-MM-DD):")).grid(row=row, column=0, sticky='w', pady=4)
        self.return_date_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.return_date_var, width=20).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text=_k('labels', 'description', "Description:")).grid(row=row, column=0, sticky='nw', pady=4)
        self.description_text = tk.Text(form_frame, width=40, height=4)
        self.description_text.grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text=_k('labels', 'max_participants', "Max Participants:")).grid(row=row, column=0, sticky='w', pady=4)
        self.max_participants_var = tk.StringVar(value='30')
        ttk.Entry(form_frame, textvariable=self.max_participants_var, width=10).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text=_k('labels', 'estimated_cost', "Estimated Cost:")).grid(row=row, column=0, sticky='w', pady=4)
        self.cost_var = tk.StringVar(value='0.00')
        ttk.Entry(form_frame, textvariable=self.cost_var, width=10).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text=_k('labels', 'organising_club', "Organising Club:")).grid(row=row, column=0, sticky='w', pady=4)
        self.club_combo = ttk.Combobox(form_frame, state='readonly', width=37)
        self.club_combo.grid(row=row, column=1, sticky='w', pady=4)
        self._load_clubs()

        row += 1
        ttk.Button(form_frame, text=_k('buttons', 'create_trip', "Create Trip"), command=self._create_trip).grid(
            row=row, column=0, columnspan=2, pady=15
        )

    def _load_clubs(self):
        """The clubs this user may propose a trip for (officers: all, or none)."""
        names = list(self._scope.get('clubs') or [])
        if self.club and self.club not in names and self._scope.get('all'):
            names.insert(0, self.club)
        if self._scope.get('all'):
            names.insert(0, _INDIVIDUAL)
        self.club_combo['values'] = names
        if self.club and self.club in names:
            self.club_combo.set(self.club)
        elif names:
            self.club_combo.current(0)

    def _create_trip(self):
        trip_name = self.trip_name_var.get().strip()
        destination = self.destination_var.get().strip()
        trip_date = self.trip_date_var.get().strip()
        return_date = self.return_date_var.get().strip()
        description = self.description_text.get('1.0', 'end').strip()
        max_participants = self.max_participants_var.get().strip()
        cost = self.cost_var.get().strip()
        club_name = self.club_combo.get()

        if not self._is_organiser():
            messagebox.showwarning(_k('dialogs', 'not_allowed', "Not Allowed"), _k('labels', 'organisers_only', "Only Students' Union officers and club committee members can propose trips."), parent=self.dialog)
            return

        # Validation
        if not trip_name or not destination or not trip_date or not return_date:
            messagebox.showwarning(_k('dialogs', 'missing_fields', "Missing Fields"), _k('dialogs', 'trip_name_destination_trip_date_and_return_date_are_required', "Trip name, destination, trip date and return date are required."), parent=self.dialog)
            return

        try:
            datetime.strptime(trip_date, '%Y-%m-%d')
            datetime.strptime(return_date, '%Y-%m-%d')
        except ValueError:
            messagebox.showwarning(_k('dialogs', 'invalid_date', "Invalid Date"), _k('dialogs', 'dates_must_be_in_yyyy_mm_dd_format', "Dates must be in YYYY-MM-DD format."), parent=self.dialog)
            return

        if return_date < trip_date:
            messagebox.showwarning(_k('dialogs', 'invalid_dates', "Invalid Dates"), _k('dialogs', 'return_date_cannot_be_before_the_trip_date', "Return date cannot be before the trip date."), parent=self.dialog)
            return

        try:
            max_participants = int(max_participants)
        except ValueError:
            messagebox.showwarning(_k('dialogs', 'invalid_value', "Invalid Value"), _k('dialogs', 'max_participants_must_be_a_whole_number', "Max participants must be a whole number."), parent=self.dialog)
            return

        try:
            cost = float(cost)
        except ValueError:
            messagebox.showwarning(_k('dialogs', 'invalid_value', "Invalid Value"), _k('dialogs', 'estimated_cost_must_be_a_number', "Estimated cost must be a number."), parent=self.dialog)
            return

        club = None if club_name in ('', _INDIVIDUAL) else club_name
        try:
            trip = trip_bus.create_su_trip(
                self.auth, club, trip_name=trip_name, destination=destination,
                start_date=trip_date, end_date=return_date, description=description or None,
                max_participants=max_participants, cost=cost)
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        except Exception as e:
            logger.exception("SU trip creation failed")
            messagebox.showerror(_k('dialogs', 'error', "Error"), f"Could not create trip: {e}", parent=self.dialog)
            return

        if messagebox.askyesno(
                _k('dialogs', 'trip_proposed', "Trip Proposed"),
                f"Trip '{trip_name}' has been proposed. It needs approval before it opens "
                f"for registration.\n\nSubmit it for approval now?", parent=self.dialog):
            self._submit(trip['id'])
        # Clear form
        self.trip_name_var.set('')
        self.destination_var.set('')
        self.trip_date_var.set('')
        self.return_date_var.set('')
        self.description_text.delete('1.0', 'end')
        self.max_participants_var.set('30')
        self.cost_var.set('0.00')
        self._load_clubs()
        self._load_upcoming_trips()
        self._load_manage_trips()

    # ------------------------------------------------------------------
    # My Trips tab
    # ------------------------------------------------------------------

    def _build_my_trips_tab(self):
        toolbar = ttk.Frame(self.my_trips_frame)
        toolbar.pack(fill='x', pady=(0, 8))

        ttk.Button(toolbar, text=_k('buttons', 'refresh', "Refresh"), command=self._load_my_trips).pack(side='left')
        ttk.Button(toolbar, text=_k('buttons', 'cancel_registration', "Cancel Registration"), command=self._cancel_registration).pack(side='right')
        ttk.Button(toolbar, text=_k('buttons', 'decline_offer', "Decline Offer"), command=self._decline_offer).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_k('buttons', 'accept_offer', "Accept Offer"), command=self._accept_offer).pack(side='right', padx=5)
        ttk.Button(toolbar, text=_k('buttons', 'pay', "Pay"), command=self._pay_selected).pack(side='right', padx=5)

        self.my_tree = self._make_tree(self.my_trips_frame, [
            ('trip_id', _k('headings', 'id', 'ID'), 50, 'center'),
            ('trip_name', _k('headings', 'trip_name', 'Trip Name'), 200, 'w'),
            ('date', _k('headings', 'trip_date', 'Trip Date'), 100, 'center'),
            ('return_date', _k('headings', 'return_date', 'Return Date'), 100, 'center'),
            ('destination', _k('headings', 'destination', 'Destination'), 160, 'w'),
            ('status', _k('headings', 'status', 'Status'), 80, 'center'),
            ('registered_at', _k('headings', 'registered', 'Registered'), 140, 'center'),
            ('place', _k('headings', 'your_place', 'Your Place'), 150, 'center'),
            ('payment', _k('headings', 'payment', 'Payment'), 80, 'center'),
            ('owed', _k('headings', 'owed', 'Owed'), 70, 'center'),
        ])
        self._load_my_trips()

    def _load_my_trips(self):
        self._clear(self.my_tree)
        self._mine = {}
        if not (self.auth and self.auth.current_user):
            return
        try:
            rows = trip_bus.my_trip_places(self.auth)
        except (PermissionError, ValueError) as e:
            logger.info("My trips unavailable: %s", e)
            return
        except Exception as e:
            logger.warning("Could not load my trips: %s", e)
            return
        for row in rows:
            if row.get('source') != 'su' or (self.club and row.get('organising_club') != self.club):
                continue
            place = row['status']
            if place == 'waitlisted':
                place = f"waiting list #{row.get('waitlist_place') or '?'}"
            elif place == 'offered':
                place = f"offered until {(row.get('offer_expires_at') or '')[:16]}"
            item = self.my_tree.insert('', 'end', values=(
                row['trip_id'], row['trip_name'], row['start_date'], row['end_date'],
                row['destination'], row['trip_status'], row['registration_date'], place,
                row.get('payment_status') or '', _money(row.get('owed'))))
            self._mine[item] = row

    def _selected_place(self):
        selected = self.my_tree.selection()
        if not selected:
            messagebox.showwarning(_k('dialogs', 'no_selection', "No Selection"), _k('dialogs', 'please_select_a_trip', "Please select a trip."), parent=self.dialog)
            return None
        return self._mine.get(selected[0])

    def _cancel_registration(self):
        selected = self.my_tree.selection()
        if not selected:
            messagebox.showwarning(_k('dialogs', 'no_selection', "No Selection"), _k('dialogs', 'please_select_a_trip_to_cancel', "Please select a trip to cancel."), parent=self.dialog)
            return
        row = self._mine.get(selected[0])
        if not row:
            return
        trip_name = row['trip_name']

        if row['trip_status'] == 'completed':
            messagebox.showinfo(_k('dialogs', 'cannot_cancel', "Cannot Cancel"), _k('dialogs', 'cannot_cancel_a_completed_trip_registration', "Cannot cancel a completed trip registration."), parent=self.dialog)
            return

        if not messagebox.askyesno(_k('dialogs', 'confirm', "Confirm"), f"Cancel your registration for '{trip_name}'?", parent=self.dialog):
            return

        try:
            outcome = trip_bus.cancel_participant(self.auth, row['participant_id'], "Cancelled by the participant")
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        except Exception as e:
            logger.exception("SU trip cancellation failed")
            messagebox.showerror(_k('dialogs', 'error', "Error"), f"Could not cancel registration: {e}", parent=self.dialog)
            return
        message = f"Registration for '{trip_name}' has been cancelled."
        refund = outcome.get('refund')
        if refund:
            if refund.get('success'):
                message += f"\nRefund: {_money(refund.get('amount'))}."
            else:
                message += f"\nThe refund could not be made: {refund.get('message') or 'unknown error'}."
        elif outcome.get('refund_due'):
            message += f"\nRefund due: {_money(outcome['refund_due'].get('amount'))}."
        messagebox.showinfo(_k('dialogs', 'cancelled', "Cancelled"), message, parent=self.dialog)
        self._load_my_trips()
        self._load_upcoming_trips()

    def _accept_offer(self):
        row = self._selected_place()
        if not row:
            return
        if row['status'] != 'offered':
            messagebox.showinfo(_k('dialogs', 'no_offer', "No Offer"), _k('dialogs', 'no_open_offer', "There is no open offer of a place on this trip."), parent=self.dialog)
            return
        try:
            trip_bus.accept_trip_offer(self.auth, row['participant_id'])
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        messagebox.showinfo(_k('dialogs', 'success', "Success"), f"You have a place on '{row['trip_name']}'.", parent=self.dialog)
        self._load_my_trips()
        self._load_upcoming_trips()
        if float(row.get('cost') or 0) > 0 and messagebox.askyesno(
                _k('dialogs', 'payment', "Payment"), f"This trip costs {_money(row.get('cost'))}. Pay now?",
                parent=self.dialog):
            self._pay(row['participant_id'], row.get('cost'))

    def _decline_offer(self):
        row = self._selected_place()
        if not row:
            return
        if row['status'] != 'offered':
            messagebox.showinfo(_k('dialogs', 'no_offer', "No Offer"), _k('dialogs', 'no_open_offer', "There is no open offer of a place on this trip."), parent=self.dialog)
            return
        if not messagebox.askyesno(_k('dialogs', 'confirm', "Confirm"), f"Turn down the place on '{row['trip_name']}'? It will go to the next person waiting.", parent=self.dialog):
            return
        try:
            trip_bus.decline_trip_offer(self.auth, row['participant_id'], "Offer declined")
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        self._load_my_trips()
        self._load_upcoming_trips()

    def _pay_selected(self):
        row = self._selected_place()
        if not row:
            return
        if float(row.get('owed') or 0) <= 0:
            messagebox.showinfo(_k('dialogs', 'nothing_owed', "Nothing Owed"), _k('dialogs', 'nothing_owed_on_this_place', "Nothing is owed on this place."), parent=self.dialog)
            return
        self._pay(row['participant_id'], row['owed'])

    def _pay(self, participant_id, amount):
        """Choose a payment method, then pay through Finance."""
        methods = trip_bus.trip_payment_methods()
        labels = [label for _m, label in methods]
        top = tk.Toplevel(self.dialog)
        top.title(_k('windows', 'pay_for_trip', "Pay for Trip"))
        top.transient(self.dialog)
        frame = ttk.Frame(top, padding=15)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=f"Amount due: {_money(amount)}").pack(anchor='w', pady=(0, 8))
        choice = tk.StringVar(value=labels[0])
        for label in labels:
            ttk.Radiobutton(frame, text=label, value=label, variable=choice).pack(anchor='w')
        chosen = {}

        def ok():
            chosen['method'] = methods[labels.index(choice.get())][0]
            top.destroy()
        buttons = ttk.Frame(frame)
        buttons.pack(pady=(10, 0))
        ttk.Button(buttons, text=_k('buttons', 'pay', "Pay"), command=ok).pack(side='left', padx=5)
        ttk.Button(buttons, text=_k('buttons', 'cancel', "Cancel"), command=top.destroy).pack(side='left', padx=5)
        try:
            top.grab_set()
        except tk.TclError:
            pass
        self.dialog.wait_window(top)
        if 'method' not in chosen:
            return
        try:
            outcome = trip_bus.pay_for_registration(self.auth, participant_id, chosen['method'])
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        except Exception as e:
            logger.exception("SU trip payment failed")
            messagebox.showerror(_k('dialogs', 'error', "Error"), f"Could not take the payment: {e}", parent=self.dialog)
            return
        if outcome.get('success'):
            message = f"Paid {_money(outcome.get('amount'))}."
            if outcome.get('reference'):
                message += f" Reference: {outcome['reference']}."
            if float(outcome.get('owed') or 0) > 0:
                message += f"\nStill owed: {_money(outcome['owed'])}."
            if outcome.get('message'):
                message += f"\n{outcome['message']}"
            messagebox.showinfo(_k('dialogs', 'payment', "Payment"), message, parent=self.dialog)
        else:
            self._error(outcome.get('message') or "The payment was not taken.")
        self._load_my_trips()

    # ------------------------------------------------------------------
    # Manage Trips tab (organisers)
    # ------------------------------------------------------------------

    def _build_manage_tab(self):
        toolbar = ttk.Frame(self.manage_frame)
        toolbar.pack(fill='x', pady=(0, 8))
        ttk.Button(toolbar, text=_k('buttons', 'refresh', "Refresh"), command=self._load_manage_trips).pack(side='left')
        for key, default, command in (
                ('trip_history', "History", self._view_history),
                ('view_participants', "View Participants", self._view_participants),
                ('archive_trip', "Archive Trip", self._archive_trip),
                ('cancel_trip', "Cancel Trip", self._cancel_trip),
                ('open_for_registration', "Open for Registration", self._open_trip),
                ('submit_for_approval', "Submit for Approval", self._submit_selected),
                ('edit_trip', "Edit Trip", self._edit_trip)):
            ttk.Button(toolbar, text=_k('buttons', key, default), command=command).pack(side='right', padx=3)

        self.manage_note = ttk.Label(self.manage_frame, foreground='gray', text=(
            _k('labels', 'manage_intro', "Trips you organise. Cancelling releases every place and refunds what was paid.")
            if self._is_organiser() else
            _k('labels', 'organisers_only', "Only Students' Union officers and club committee members can propose trips.")))
        self.manage_note.pack(fill='x', pady=(0, 6))

        self.manage_tree = self._make_tree(self.manage_frame, [
            ('trip_id', _k('headings', 'id', 'ID'), 50, 'center'),
            ('trip_name', _k('headings', 'trip_name', 'Trip Name'), 220, 'w'),
            ('club', _k('headings', 'organizer', 'Organizer'), 160, 'w'),
            ('date', _k('headings', 'date', 'Date'), 100, 'center'),
            ('return_date', _k('headings', 'return_date', 'Return Date'), 100, 'center'),
            ('status', _k('headings', 'status', 'Status'), 90, 'center'),
            ('places', _k('headings', 'places', 'Places'), 80, 'center'),
            ('cost', _k('headings', 'cost', 'Cost'), 80, 'center'),
        ])
        self._load_manage_trips()

    def _load_manage_trips(self):
        self._clear(self.manage_tree)
        self._managed = {}
        if not (self.auth and self.auth.current_user):
            return
        try:
            rows = trip_bus.su_organiser_trips(self.auth, club=self.club)
        except Exception as e:
            logger.warning("Could not load the trips you organise: %s", e)
            return
        for trip in rows:
            item = self.manage_tree.insert('', 'end', values=(
                trip['id'], trip['trip_name'], trip.get('organising_club') or 'Individual',
                trip['start_date'], trip['end_date'], trip['status'],
                f"{trip.get('current_participants') or 0}/{trip['max_participants']}",
                _money(trip.get('cost'))))
            self._managed[item] = trip

    def _selected_managed(self):
        selected = self.manage_tree.selection()
        if not selected:
            messagebox.showwarning(_k('dialogs', 'no_selection', "No Selection"), _k('dialogs', 'please_select_a_trip', "Please select a trip."), parent=self.dialog)
            return None
        return self._managed.get(selected[0])

    def _after_change(self):
        self._load_manage_trips()
        self._load_upcoming_trips()
        self._load_my_trips()

    def _edit_trip(self):
        trip = self._selected_managed()
        if not trip:
            return

        def validate(values):
            for name in ('start_date', 'end_date'):
                try:
                    datetime.strptime(values[name], '%Y-%m-%d')
                except ValueError:
                    return _k('dialogs', 'dates_must_be_in_yyyy_mm_dd_format', "Dates must be in YYYY-MM-DD format.")
            try:
                int(values['max_participants'])
                float(values['cost'])
            except ValueError:
                return _k('dialogs', 'max_and_cost_numbers', "Max participants must be a whole number and cost a number.")
            return None

        form = _FormDialog(
            self.dialog, _k('windows', 'edit_trip', "Edit Trip"),
            _k('labels', 'edit_resets_approval', "Changing the dates, destination or cost means the trip is approved again."),
            [('trip_name', "Trip Name:", trip['trip_name'], 'entry'),
             ('destination', "Destination:", trip['destination'], 'entry'),
             ('start_date', "Trip Date (YYYY-MM-DD):", trip['start_date'], 'entry'),
             ('end_date', "Return Date (YYYY-MM-DD):", trip['end_date'], 'entry'),
             ('max_participants', "Max Participants:", trip['max_participants'], 'entry'),
             ('cost', "Cost:", f"{float(trip.get('cost') or 0):.2f}", 'entry'),
             ('description', "Description:", trip.get('description') or '', 'text')],
            required=('trip_name', 'destination', 'start_date', 'end_date'), validate=validate)
        if form.result is None:
            return
        values = dict(form.result)
        values['max_participants'] = int(values['max_participants'])
        values['cost'] = float(values['cost'])
        values['description'] = values['description'] or None
        current = dict(trip, cost=float(trip.get('cost') or 0))
        changes = {k: v for k, v in values.items() if current.get(k) != v}
        if not changes:
            return
        try:
            trip_bus.update_su_trip(self.auth, trip['id'], **changes)
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        messagebox.showinfo(_k('dialogs', 'success', "Success"), f"Trip '{values['trip_name']}' has been updated.", parent=self.dialog)
        self._after_change()

    def _submit(self, trip_id):
        try:
            state = trip_bus.submit_su_trip_for_approval(self.auth, trip_id)
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        stages = ", ".join(str(s).replace('_', ' ') for s in (state.get('required') or [])) if isinstance(state, dict) else ''
        messagebox.showinfo(_k('dialogs', 'submitted', "Submitted"),
                            "The trip has been submitted for approval"
                            + (f" ({stages})." if stages else ".")
                            + " It opens for registration once every stage has approved it.",
                            parent=self.dialog)

    def _submit_selected(self):
        trip = self._selected_managed()
        if trip:
            self._submit(trip['id'])
            self._after_change()

    def _open_trip(self):
        trip = self._selected_managed()
        if not trip:
            return
        if trip['status'] in ('proposed', 'planning'):
            try:
                state = trip_bus.trip_approval_state(trip['id'])
                waiting = ", ".join(str(s).replace('_', ' ') for s in state.get('outstanding') or [])
            except Exception:
                logger.debug("approval state unavailable", exc_info=True)
                waiting = ''
            self._error(f"'{trip['trip_name']}' is still proposed: it opens once it has been approved"
                        + (f" (waiting for: {waiting})." if waiting else ".")
                        + " Use Submit for Approval if it has not been submitted.",
                        _k('dialogs', 'cannot_open_yet', "Cannot Open Yet"))
            return
        first_opening = trip['status'] == 'approved'
        try:
            trip_bus.set_su_trip_status(self.auth, trip['id'], 'open')
        except (PermissionError, ValueError) as e:
            self._error(e, _k('dialogs', 'cannot_open_yet', "Cannot Open Yet"))
            return
        if first_opening:
            self._announce(trip)
        messagebox.showinfo(_k('dialogs', 'success', "Success"), f"'{trip['trip_name']}' is now open for registration.", parent=self.dialog)
        self._after_change()

    def _announce(self, trip):
        """E-mail the trip announcement (club members, or all students) in the
        background — it used to go out at proposal, before approval."""
        import threading

        def send():
            try:
                from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.core.utilities import (
                    announce_trip,
                )
                announce_trip(trip['trip_name'], trip.get('description') or '',
                              trip.get('start_date') or '', float(trip.get('cost') or 0),
                              trip.get('organising_club'))
            except Exception:
                logger.exception("Trip announcement failed for trip %s", trip.get('id'))

        threading.Thread(target=send, daemon=True, name="su-trip-announcement").start()

    def _ask_reason(self, title, prompt):
        form = _FormDialog(self.dialog, title, prompt, [('reason', "Reason:", '', 'entry')],
                           required=('reason',))
        return form.result['reason'] if form.result else None

    def _cancel_trip(self):
        trip = self._selected_managed()
        if not trip:
            return
        reason = self._ask_reason(_k('windows', 'cancel_trip', "Cancel Trip"),
                                  f"Cancel '{trip['trip_name']}'? Every place is released and paid "
                                  f"participants are refunded and told.")
        if reason is None:
            return
        try:
            result = trip_bus.set_su_trip_status(self.auth, trip['id'], 'cancelled', reason)
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        refunds = result.get('refunds') or []
        failed = [r for r in refunds if not (r or {}).get('success')]
        message = f"'{trip['trip_name']}' has been cancelled."
        if refunds:
            message += f"\n{len(refunds) - len(failed)} refund(s) made"
            message += f", {len(failed)} failed - settle them in Trip Management." if failed else "."
        messagebox.showinfo(_k('dialogs', 'cancelled', "Cancelled"), message, parent=self.dialog)
        self._after_change()

    def _archive_trip(self):
        trip = self._selected_managed()
        if not trip:
            return
        reason = self._ask_reason(_k('windows', 'archive_trip', "Archive Trip"),
                                  f"Archive '{trip['trip_name']}'? It is kept on record but leaves "
                                  f"every list; if it has not run, places are released and refunded.")
        if reason is None:
            return
        try:
            trip_bus.archive_su_trip(self.auth, trip['id'], reason)
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        messagebox.showinfo(_k('dialogs', 'archived', "Archived"), f"'{trip['trip_name']}' has been archived.", parent=self.dialog)
        self._after_change()

    def _view_participants(self):
        trip = self._selected_managed()
        if not trip:
            return
        try:
            data = trip_bus.su_trip_participants(self.auth, trip['id'])
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        top = tk.Toplevel(self.dialog)
        top.title(f"Participants - {trip['trip_name']}")
        top.geometry("1100x600")
        top.transient(self.dialog)
        people = data['participants']
        going = [p for p in people if p['status'] != 'waitlisted']
        counts = data['health_counts']
        summary = (f"{len(going)} of {trip['max_participants']} places taken, "
                   f"{len(data['waitlist'])} waiting. Recorded: medical {counts['medical_info']}, "
                   f"dietary {counts['dietary_requirements']}, accessibility {counts['accessibility_needs']} "
                   f"(details are seen by the trip's leaders in Trip Management).")
        # Pack the summary and close button before the expanding table.
        ttk.Label(top, text=summary, wraplength=1050, justify='left').pack(fill='x', padx=10, pady=(10, 5))
        ttk.Button(top, text=_k('buttons', 'close', "Close"), command=top.destroy).pack(side='bottom', pady=8)
        frame = ttk.Frame(top)
        frame.pack(fill='both', expand=True, padx=10)
        waiting = {w['participant_id']: w['place'] for w in data['waitlist']}
        tree = self._make_tree(frame, [
            ('name', "Name", 180, 'w'), ('student', "Student ID", 100, 'center'),
            ('status', "Status", 100, 'center'), ('payment', "Payment", 80, 'center'),
            ('paid', "Paid", 80, 'center'), ('contact', "Emergency Contact", 180, 'w'),
            ('phone', "Phone", 120, 'w'), ('waiting', "Waiting #", 70, 'center'),
            ('registered', "Registered", 140, 'center')])
        for p in people:
            tree.insert('', 'end', values=(
                p.get('name') or '', p.get('student_id') or '', p['status'],
                p.get('payment_status') or '', _money(p.get('amount_paid')),
                p.get('emergency_contact_name') or p.get('emergency_contact') or '',
                p.get('emergency_contact_phone') or '', waiting.get(p['id'], ''),
                p.get('registration_date') or ''))

    def _view_history(self):
        """Every recorded change to the selected trip, newest first."""
        trip = self._selected_managed()
        if not trip:
            return
        try:
            rows = trip_bus.su_trip_history(self.auth, trip['id'])
        except (PermissionError, ValueError) as e:
            self._error(e)
            return
        top = tk.Toplevel(self.dialog)
        top.title(f"History - {trip['trip_name']}")
        top.geometry("1100x600")
        top.transient(self.dialog)
        # Pack the summary and close button before the expanding table.
        ttk.Label(top, text=f"{len(rows)} change(s), newest first.").pack(fill='x', padx=10, pady=(10, 5))
        ttk.Button(top, text=_k('buttons', 'close', "Close"), command=top.destroy).pack(side='bottom', pady=8)
        frame = ttk.Frame(top)
        frame.pack(fill='both', expand=True, padx=10)
        tree = self._make_tree(frame, [
            ('when', "When", 140, 'center'), ('who', "By", 110, 'w'),
            ('change', "Change", 150, 'w'), ('field', "Field", 110, 'w'),
            ('old', "From", 220, 'w'), ('new', "To", 220, 'w'), ('version', "Version", 60, 'center')])

        def label(value):
            return str(value).replace('_', ' ').title() if value else ''

        for r in rows:
            tree.insert('', 'end', values=(
                r.get('changed_at') or '', r.get('changed_by') or '', label(r.get('action')),
                label(r.get('field')),
                '' if r.get('old_value') is None else r['old_value'],
                '' if r.get('new_value') is None else r['new_value'], r.get('version') or ''))


def open_trip_management_dialog(self):
    """Open the Student Union Trip Management dialog.

    Designed to be bound as a method on StudentUnionGUI.
    ``self`` is the StudentUnionGUI instance.
    """
    StudentUnionTripsDialog(self.root, self.auth_manager)


def open_club_trips_dialog(parent, auth_manager, club_name):
    """The Students' Union trips screen for one club's trips."""
    return StudentUnionTripsDialog(parent, auth_manager, club=club_name)
