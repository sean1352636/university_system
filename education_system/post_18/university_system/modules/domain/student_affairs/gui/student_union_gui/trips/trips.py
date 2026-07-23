import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.infrastructure.email.email_service.core import send_email


def _ensure_union_trips_table(conn):
    """Create the union_trips and union_trip_registrations tables if they do not exist."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS union_trips (
            trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_name TEXT NOT NULL,
            destination TEXT NOT NULL,
            trip_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            description TEXT,
            max_participants INTEGER DEFAULT 30,
            estimated_cost REAL DEFAULT 0.0,
            organizer_club_id INTEGER,
            created_by TEXT,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'upcoming',
            FOREIGN KEY (organizer_club_id) REFERENCES student_clubs (club_id),
            CHECK (status IN ('upcoming', 'full', 'cancelled', 'completed'))
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS union_trip_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES union_trips (trip_id),
            UNIQUE (trip_id, user_id)
        )
    ''')
    conn.commit()


class StudentUnionTripsDialog:
    """Dialog for managing Student Union trips."""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Student Union Trip Management")
        self.dialog.geometry("1050x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Ensure tables exist
        conn = get_connection()
        try:
            _ensure_union_trips_table(conn)
        finally:
            conn.close()

        self._create_widgets()

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
        self.notebook.add(self.upcoming_frame, text="Upcoming Trips")
        self._build_upcoming_tab()

        # Tab 2 - Organise Trip
        self.organise_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.organise_frame, text="Organise Trip")
        self._build_organise_tab()

        # Tab 3 - My Trips
        self.my_trips_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.my_trips_frame, text="My Trips")
        self._build_my_trips_tab()

    # ------------------------------------------------------------------
    # Upcoming Trips tab
    # ------------------------------------------------------------------

    def _build_upcoming_tab(self):
        toolbar = ttk.Frame(self.upcoming_frame)
        toolbar.pack(fill='x', pady=(0, 8))

        ttk.Button(toolbar, text="Refresh", command=self._load_upcoming_trips).pack(side='left')
        ttk.Button(toolbar, text="Register for Selected Trip", command=self._register_for_trip).pack(side='right')

        columns = ('trip_id', 'trip_name', 'date', 'destination', 'organizer', 'capacity', 'registered')
        self.upcoming_tree = ttk.Treeview(self.upcoming_frame, columns=columns, show='headings', height=18)

        self.upcoming_tree.heading('trip_id', text='ID')
        self.upcoming_tree.heading('trip_name', text='Trip Name')
        self.upcoming_tree.heading('date', text='Date')
        self.upcoming_tree.heading('destination', text='Destination')
        self.upcoming_tree.heading('organizer', text='Organizer')
        self.upcoming_tree.heading('capacity', text='Capacity')
        self.upcoming_tree.heading('registered', text='Registered')

        self.upcoming_tree.column('trip_id', width=50, anchor='center')
        self.upcoming_tree.column('trip_name', width=200)
        self.upcoming_tree.column('date', width=100, anchor='center')
        self.upcoming_tree.column('destination', width=180)
        self.upcoming_tree.column('organizer', width=160)
        self.upcoming_tree.column('capacity', width=70, anchor='center')
        self.upcoming_tree.column('registered', width=70, anchor='center')

        scrollbar = ttk.Scrollbar(self.upcoming_frame, orient='vertical', command=self.upcoming_tree.yview)
        self.upcoming_tree.configure(yscrollcommand=scrollbar.set)
        self.upcoming_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self._load_upcoming_trips()

    def _load_upcoming_trips(self):
        for item in self.upcoming_tree.get_children():
            self.upcoming_tree.delete(item)

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.trip_id, t.trip_name, t.trip_date, t.destination,
                       COALESCE(c.club_name, 'Individual'), t.max_participants,
                       (SELECT COUNT(*) FROM union_trip_registrations r WHERE r.trip_id = t.trip_id)
                FROM union_trips t
                LEFT JOIN student_clubs c ON t.organizer_club_id = c.club_id
                WHERE t.status = 'upcoming' AND t.trip_date >= date('now')
                ORDER BY t.trip_date ASC
            ''')
            for row in cursor.fetchall():
                self.upcoming_tree.insert('', 'end', values=row)
        finally:
            conn.close()

    def _register_for_trip(self):
        selected = self.upcoming_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a trip to register for.", parent=self.dialog)
            return

        values = self.upcoming_tree.item(selected[0], 'values')
        trip_id = values[0]
        trip_name = values[1]
        capacity = int(values[5])
        registered = int(values[6])

        if registered >= capacity:
            messagebox.showinfo("Full", "This trip is already at full capacity.", parent=self.dialog)
            return

        current_user = self.auth.current_user
        if not current_user:
            messagebox.showerror("Error", "You must be logged in to register.", parent=self.dialog)
            return

        user_id = current_user.get('id') or current_user.get('user_id', '')

        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Check for duplicate registration
            cursor.execute(
                'SELECT 1 FROM union_trip_registrations WHERE trip_id = ? AND user_id = ?',
                (trip_id, user_id)
            )
            if cursor.fetchone():
                messagebox.showinfo("Already Registered", "You are already registered for this trip.", parent=self.dialog)
                return

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'INSERT INTO union_trip_registrations (trip_id, user_id, registered_at) VALUES (?, ?, ?)',
                (trip_id, user_id, now)
            )

            # Auto-mark trip as full if needed
            new_count = registered + 1
            if new_count >= capacity:
                cursor.execute("UPDATE union_trips SET status = 'full' WHERE trip_id = ?", (trip_id,))

            conn.commit()

            # Send confirmation email
            user_email = current_user.get('email', '')
            if user_email:
                try:
                    send_email(
                        user_email,
                        f"Trip Registration Confirmation - {trip_name}",
                        f"Hello {current_user.get('username', 'Student')},\n\n"
                        f"You have successfully registered for the trip: {trip_name}.\n"
                        f"Date: {values[2]}\n"
                        f"Destination: {values[3]}\n\n"
                        f"Thank you,\nStudent Union"
                    )
                except Exception:
                    pass  # Email failure should not block registration

            messagebox.showinfo("Success", f"You have been registered for '{trip_name}'.", parent=self.dialog)
            self._load_upcoming_trips()
            self._load_my_trips()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", f"Could not register: {e}", parent=self.dialog)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Organise Trip tab
    # ------------------------------------------------------------------

    def _build_organise_tab(self):
        form_frame = ttk.LabelFrame(self.organise_frame, text="Create a New Trip", padding=15)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)

        row = 0
        ttk.Label(form_frame, text="Trip Name:").grid(row=row, column=0, sticky='w', pady=4)
        self.trip_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.trip_name_var, width=40).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text="Destination:").grid(row=row, column=0, sticky='w', pady=4)
        self.destination_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.destination_var, width=40).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text="Trip Date (YYYY-MM-DD):").grid(row=row, column=0, sticky='w', pady=4)
        self.trip_date_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.trip_date_var, width=20).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text="Return Date (YYYY-MM-DD):").grid(row=row, column=0, sticky='w', pady=4)
        self.return_date_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.return_date_var, width=20).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text="Description:").grid(row=row, column=0, sticky='nw', pady=4)
        self.description_text = tk.Text(form_frame, width=40, height=4)
        self.description_text.grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text="Max Participants:").grid(row=row, column=0, sticky='w', pady=4)
        self.max_participants_var = tk.StringVar(value='30')
        ttk.Entry(form_frame, textvariable=self.max_participants_var, width=10).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text="Estimated Cost:").grid(row=row, column=0, sticky='w', pady=4)
        self.cost_var = tk.StringVar(value='0.00')
        ttk.Entry(form_frame, textvariable=self.cost_var, width=10).grid(row=row, column=1, sticky='w', pady=4)

        row += 1
        ttk.Label(form_frame, text="Organising Club:").grid(row=row, column=0, sticky='w', pady=4)
        self.club_combo = ttk.Combobox(form_frame, state='readonly', width=37)
        self.club_combo.grid(row=row, column=1, sticky='w', pady=4)
        self._load_clubs()

        row += 1
        ttk.Button(form_frame, text="Create Trip", command=self._create_trip).grid(
            row=row, column=0, columnspan=2, pady=15
        )

    def _load_clubs(self):
        """Populate the club selector combobox."""
        self._club_map = {}
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT club_id, club_name FROM student_clubs WHERE status = 'active' ORDER BY club_name")
            clubs = cursor.fetchall()
            names = []
            for club in clubs:
                cid = club['club_id'] if isinstance(club, dict) else club[0]
                cname = club['club_name'] if isinstance(club, dict) else club[1]
                names.append(cname)
                self._club_map[cname] = cid
            # Allow organising without a club
            names.insert(0, '(No club - individual)')
            self._club_map['(No club - individual)'] = None
            self.club_combo['values'] = names
            if names:
                self.club_combo.current(0)
        except Exception:
            self.club_combo['values'] = ['(No club - individual)']
            self._club_map['(No club - individual)'] = None
            self.club_combo.current(0)
        finally:
            conn.close()

    def _create_trip(self):
        trip_name = self.trip_name_var.get().strip()
        destination = self.destination_var.get().strip()
        trip_date = self.trip_date_var.get().strip()
        return_date = self.return_date_var.get().strip()
        description = self.description_text.get('1.0', 'end').strip()
        max_participants = self.max_participants_var.get().strip()
        cost = self.cost_var.get().strip()
        club_name = self.club_combo.get()

        # Validation
        if not trip_name or not destination or not trip_date or not return_date:
            messagebox.showwarning("Missing Fields", "Trip name, destination, trip date and return date are required.", parent=self.dialog)
            return

        try:
            datetime.strptime(trip_date, '%Y-%m-%d')
            datetime.strptime(return_date, '%Y-%m-%d')
        except ValueError:
            messagebox.showwarning("Invalid Date", "Dates must be in YYYY-MM-DD format.", parent=self.dialog)
            return

        if return_date < trip_date:
            messagebox.showwarning("Invalid Dates", "Return date cannot be before the trip date.", parent=self.dialog)
            return

        try:
            max_participants = int(max_participants)
        except ValueError:
            messagebox.showwarning("Invalid Value", "Max participants must be a whole number.", parent=self.dialog)
            return

        try:
            cost = float(cost)
        except ValueError:
            messagebox.showwarning("Invalid Value", "Estimated cost must be a number.", parent=self.dialog)
            return

        club_id = self._club_map.get(club_name)

        current_user = self.auth.current_user
        created_by = ''
        if current_user:
            created_by = current_user.get('id') or current_user.get('user_id', '')

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO union_trips
                    (trip_name, destination, trip_date, return_date, description,
                     max_participants, estimated_cost, organizer_club_id, created_by, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming')
            ''', (trip_name, destination, trip_date, return_date, description,
                  max_participants, cost, club_id, created_by, now))
            conn.commit()
            messagebox.showinfo("Success", f"Trip '{trip_name}' has been created.", parent=self.dialog)
            # Clear form
            self.trip_name_var.set('')
            self.destination_var.set('')
            self.trip_date_var.set('')
            self.return_date_var.set('')
            self.description_text.delete('1.0', 'end')
            self.max_participants_var.set('30')
            self.cost_var.set('0.00')
            if self.club_combo['values']:
                self.club_combo.current(0)
            # Refresh upcoming trips list
            self._load_upcoming_trips()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", f"Could not create trip: {e}", parent=self.dialog)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # My Trips tab
    # ------------------------------------------------------------------

    def _build_my_trips_tab(self):
        toolbar = ttk.Frame(self.my_trips_frame)
        toolbar.pack(fill='x', pady=(0, 8))

        ttk.Button(toolbar, text="Refresh", command=self._load_my_trips).pack(side='left')
        ttk.Button(toolbar, text="Cancel Registration", command=self._cancel_registration).pack(side='right')

        columns = ('trip_id', 'trip_name', 'date', 'return_date', 'destination', 'status', 'registered_at')
        self.my_tree = ttk.Treeview(self.my_trips_frame, columns=columns, show='headings', height=18)

        self.my_tree.heading('trip_id', text='ID')
        self.my_tree.heading('trip_name', text='Trip Name')
        self.my_tree.heading('date', text='Trip Date')
        self.my_tree.heading('return_date', text='Return Date')
        self.my_tree.heading('destination', text='Destination')
        self.my_tree.heading('status', text='Status')
        self.my_tree.heading('registered_at', text='Registered')

        self.my_tree.column('trip_id', width=50, anchor='center')
        self.my_tree.column('trip_name', width=200)
        self.my_tree.column('date', width=100, anchor='center')
        self.my_tree.column('return_date', width=100, anchor='center')
        self.my_tree.column('destination', width=170)
        self.my_tree.column('status', width=80, anchor='center')
        self.my_tree.column('registered_at', width=140, anchor='center')

        scrollbar = ttk.Scrollbar(self.my_trips_frame, orient='vertical', command=self.my_tree.yview)
        self.my_tree.configure(yscrollcommand=scrollbar.set)
        self.my_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self._load_my_trips()

    def _load_my_trips(self):
        for item in self.my_tree.get_children():
            self.my_tree.delete(item)

        current_user = self.auth.current_user
        if not current_user:
            return

        user_id = current_user.get('id') or current_user.get('user_id', '')

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.trip_id, t.trip_name, t.trip_date, t.return_date,
                       t.destination, t.status, r.registered_at
                FROM union_trip_registrations r
                JOIN union_trips t ON r.trip_id = t.trip_id
                WHERE r.user_id = ?
                ORDER BY t.trip_date ASC
            ''', (user_id,))
            for row in cursor.fetchall():
                self.my_tree.insert('', 'end', values=row)
        finally:
            conn.close()

    def _cancel_registration(self):
        selected = self.my_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a trip to cancel.", parent=self.dialog)
            return

        values = self.my_tree.item(selected[0], 'values')
        trip_id = values[0]
        trip_name = values[1]
        status = values[5]

        if status == 'completed':
            messagebox.showinfo("Cannot Cancel", "Cannot cancel a completed trip registration.", parent=self.dialog)
            return

        if not messagebox.askyesno("Confirm", f"Cancel your registration for '{trip_name}'?", parent=self.dialog):
            return

        current_user = self.auth.current_user
        user_id = current_user.get('id') or current_user.get('user_id', '')

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM union_trip_registrations WHERE trip_id = ? AND user_id = ?',
                (trip_id, user_id)
            )
            # If trip was full, reopen it
            if status == 'full':
                cursor.execute("UPDATE union_trips SET status = 'upcoming' WHERE trip_id = ?", (trip_id,))
            conn.commit()
            messagebox.showinfo("Cancelled", f"Registration for '{trip_name}' has been cancelled.", parent=self.dialog)
            self._load_my_trips()
            self._load_upcoming_trips()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", f"Could not cancel registration: {e}", parent=self.dialog)
        finally:
            conn.close()


def open_trip_management_dialog(self):
    """Open the Student Union Trip Management dialog.

    Designed to be bound as a method on StudentUnionGUI.
    ``self`` is the StudentUnionGUI instance.
    """
    StudentUnionTripsDialog(self.root, self.auth_manager)
