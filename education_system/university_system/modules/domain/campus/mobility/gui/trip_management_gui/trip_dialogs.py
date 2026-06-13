import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog
from datetime import datetime

from education_system.university_system.modules.domain.campus.mobility.gui.trip_management_gui._imports import safe_db_operation


class TripDetailsDialog(Dialog):
    def __init__(self, parent, trip_data, participants_data):
        self.trip_data = trip_data
        self.participants_data = participants_data
        super().__init__(parent, "Trip Details")

    def body(self, master):
        """Create the dialog body"""
        # Trip information
        info_frame = ttk.LabelFrame(master, text="Trip Information", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        trip = self.trip_data
        row = 0

        fields = [
            ("ID:", str(trip[0])),
            ("Name:", trip[1]),
            ("Description:", trip[2] or "None"),
            ("Destination:", trip[3]),
            ("Start Date:", trip[4]),
            ("End Date:", trip[5]),
            ("Max Participants:", str(trip[6])),
            ("Cost:", f"\u00a3{trip[7]:.2f}" if trip[7] is not None else "\u00a30.00"),
            ("Status:", trip[8].title()),
            ("Created By:", trip[11] if trip[11] else "Unknown"),
            ("Created:", trip[9]),
            ("Updated:", trip[10])
        ]

        for label, value in fields:
            ttk.Label(info_frame, text=label, font=('Arial', 9, 'bold')).grid(row=row, column=0, sticky=tk.W, padx=(0, 10), pady=2)
            ttk.Label(info_frame, text=value).grid(row=row, column=1, sticky=tk.W, pady=2)
            row += 1

        # Participants information
        participants_frame = ttk.LabelFrame(master, text=f"Participants ({len(self.participants_data)})", padding=10)
        participants_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        if self.participants_data:
            # Create treeview for participants
            participants_tree = ttk.Treeview(participants_frame, columns=('name', 'email', 'registration', 'payment'), show='headings', height=8)

            participants_tree.heading('name', text='Name')
            participants_tree.heading('email', text='Email')
            participants_tree.heading('registration', text='Registration Date')
            participants_tree.heading('payment', text='Payment Status')

            for participant in self.participants_data:
                name = participant[9] if participant[9] else "Unknown"
                email = participant[10] if participant[10] else "N/A"
                reg_date = participant[3]
                payment = participant[4].title()

                participants_tree.insert('', 'end', values=(name, email, reg_date, payment))

            participants_tree.pack(fill=tk.BOTH, expand=True)
        else:
            ttk.Label(participants_frame, text="No participants registered yet.").pack()

        return None  # No initial focus

    def buttonbox(self):
        """Create button box"""
        box = ttk.Frame(self)
        ttk.Button(box, text="Close", command=self.ok).pack(side=tk.RIGHT, padx=5)
        box.pack(pady=5)


class CreateTripDialog(Dialog):
    def __init__(self, parent, auth, refresh_callback):
        self.auth = auth
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Create New Trip")

    def body(self, master):
        """Create the dialog body"""
        # Trip name
        ttk.Label(master, text="Trip Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        # Description
        ttk.Label(master, text="Description:").grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.description_text = tk.Text(master, width=40, height=3)
        self.description_text.grid(row=1, column=1, padx=5, pady=5)

        # Destination
        ttk.Label(master, text="Destination:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.destination_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.destination_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        # Start date
        ttk.Label(master, text="Start Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_date_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.start_date_var, width=40).grid(row=3, column=1, padx=5, pady=5)

        # End date
        ttk.Label(master, text="End Date (YYYY-MM-DD):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_date_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.end_date_var, width=40).grid(row=4, column=1, padx=5, pady=5)

        # Max participants
        ttk.Label(master, text="Max Participants:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_participants_var = tk.StringVar(value="50")
        ttk.Entry(master, textvariable=self.max_participants_var, width=40).grid(row=5, column=1, padx=5, pady=5)

        # Cost
        ttk.Label(master, text="Cost per person (\u00a3):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.cost_var = tk.StringVar(value="0.0")
        ttk.Entry(master, textvariable=self.cost_var, width=40).grid(row=6, column=1, padx=5, pady=5)

        # Status
        ttk.Label(master, text="Status:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        self.status_var = tk.StringVar(value="planning")
        status_combo = ttk.Combobox(master, textvariable=self.status_var,
                                   values=["planning", "open"], state="readonly", width=37)
        status_combo.grid(row=7, column=1, padx=5, pady=5)

        return self.name_entry  # Initial focus

    def validate(self):
        """Validate form data"""
        try:
            # Validate required fields
            if len(self.name_var.get().strip()) < 3:
                messagebox.showerror("Validation Error", "Trip name must be at least 3 characters long.")
                return False

            if len(self.destination_var.get().strip()) < 3:
                messagebox.showerror("Validation Error", "Destination must be at least 3 characters long.")
                return False

            # Validate dates
            start_date = datetime.strptime(self.start_date_var.get(), '%Y-%m-%d')
            end_date = datetime.strptime(self.end_date_var.get(), '%Y-%m-%d')

            if start_date.date() <= datetime.now().date():
                messagebox.showerror("Validation Error", "Start date must be in the future.")
                return False

            if end_date.date() <= start_date.date():
                messagebox.showerror("Validation Error", "End date must be after start date.")
                return False

            # Validate numbers
            max_participants = int(self.max_participants_var.get())
            if max_participants <= 0:
                messagebox.showerror("Validation Error", "Maximum participants must be greater than 0.")
                return False

            cost = float(self.cost_var.get())
            if cost < 0:
                messagebox.showerror("Validation Error", "Cost cannot be negative.")
                return False

            return True

        except ValueError as e:
            messagebox.showerror("Validation Error", f"Invalid input: {e}")
            return False

    def apply(self):
        """Apply the changes"""
        def create_trip_operation(conn):
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO trips (
                trip_name, description, destination, start_date, end_date,
                max_participants, cost, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.name_var.get().strip(),
                self.description_text.get(1.0, tk.END).strip(),
                self.destination_var.get().strip(),
                self.start_date_var.get(),
                self.end_date_var.get(),
                int(self.max_participants_var.get()),
                float(self.cost_var.get()),
                self.status_var.get(),
                self.auth.current_user['id'],
                timestamp,
                timestamp
            ))

            return cursor.lastrowid

        # Use the safe_db_operation method (we'll need to pass this from the main class)

        trip_id = safe_db_operation(create_trip_operation)

        if trip_id:
            messagebox.showinfo("Success", f"Trip '{self.name_var.get()}' created successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to create trip.")


class UpdateTripDialog(Dialog):
    def __init__(self, parent, auth, trip_id, refresh_callback):
        self.auth = auth
        self.trip_id = trip_id
        self.refresh_callback = refresh_callback
        self.trip_data = None

        # Load trip data
        self.load_trip_data()

        super().__init__(parent, "Update Trip")

    def load_trip_data(self):
        """Load existing trip data"""
        def get_trip_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trips WHERE id = ?', (self.trip_id,))
            return cursor.fetchone()

        self.trip_data = safe_db_operation(get_trip_operation)

    def body(self, master):
        """Create the dialog body"""
        if not self.trip_data:
            ttk.Label(master, text="Trip not found.").pack(pady=20)
            return None

        # Pre-populate fields with existing data
        trip = self.trip_data

        # Trip name
        ttk.Label(master, text="Trip Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.name_var = tk.StringVar(value=trip[1])
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        # Description
        ttk.Label(master, text="Description:").grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.description_text = tk.Text(master, width=40, height=3)
        self.description_text.insert(1.0, trip[2] or "")
        self.description_text.grid(row=1, column=1, padx=5, pady=5)

        # Destination
        ttk.Label(master, text="Destination:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.destination_var = tk.StringVar(value=trip[3])
        ttk.Entry(master, textvariable=self.destination_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        # Start date
        ttk.Label(master, text="Start Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_date_var = tk.StringVar(value=trip[4])
        ttk.Entry(master, textvariable=self.start_date_var, width=40).grid(row=3, column=1, padx=5, pady=5)

        # End date
        ttk.Label(master, text="End Date (YYYY-MM-DD):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_date_var = tk.StringVar(value=trip[5])
        ttk.Entry(master, textvariable=self.end_date_var, width=40).grid(row=4, column=1, padx=5, pady=5)

        # Max participants
        ttk.Label(master, text="Max Participants:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_participants_var = tk.StringVar(value=str(trip[6]))
        ttk.Entry(master, textvariable=self.max_participants_var, width=40).grid(row=5, column=1, padx=5, pady=5)

        # Cost
        ttk.Label(master, text="Cost per person (\u00a3):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.cost_var = tk.StringVar(value=str(trip[7]))
        ttk.Entry(master, textvariable=self.cost_var, width=40).grid(row=6, column=1, padx=5, pady=5)

        # Status
        ttk.Label(master, text="Status:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        self.status_var = tk.StringVar(value=trip[8])
        status_combo = ttk.Combobox(master, textvariable=self.status_var,
                                   values=["planning", "open", "full", "cancelled", "completed"],
                                   state="readonly", width=37)
        status_combo.grid(row=7, column=1, padx=5, pady=5)

        return self.name_entry  # Initial focus

    def validate(self):
        """Validate form data"""
        try:
            # Validate required fields
            if len(self.name_var.get().strip()) < 3:
                messagebox.showerror("Validation Error", "Trip name must be at least 3 characters long.")
                return False

            if len(self.destination_var.get().strip()) < 3:
                messagebox.showerror("Validation Error", "Destination must be at least 3 characters long.")
                return False

            # Validate dates
            datetime.strptime(self.start_date_var.get(), '%Y-%m-%d')
            datetime.strptime(self.end_date_var.get(), '%Y-%m-%d')

            # Validate numbers
            max_participants = int(self.max_participants_var.get())
            if max_participants <= 0:
                messagebox.showerror("Validation Error", "Maximum participants must be greater than 0.")
                return False

            cost = float(self.cost_var.get())
            if cost < 0:
                messagebox.showerror("Validation Error", "Cost cannot be negative.")
                return False

            return True

        except ValueError as e:
            messagebox.showerror("Validation Error", f"Invalid input: {e}")
            return False

    def apply(self):
        """Apply the changes"""
        def update_trip_operation(conn):
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            UPDATE trips SET
                trip_name = ?, description = ?, destination = ?,
                start_date = ?, end_date = ?, max_participants = ?,
                cost = ?, status = ?, updated_at = ?
            WHERE id = ?
            ''', (
                self.name_var.get().strip(),
                self.description_text.get(1.0, tk.END).strip(),
                self.destination_var.get().strip(),
                self.start_date_var.get(),
                self.end_date_var.get(),
                int(self.max_participants_var.get()),
                float(self.cost_var.get()),
                self.status_var.get(),
                timestamp,
                self.trip_id
            ))

            return True


        if safe_db_operation(update_trip_operation):
            messagebox.showinfo("Success", "Trip updated successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to update trip.")


class TripSelectionDialog(Dialog):
    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback
        self.selected_trip_id = None
        super().__init__(parent, "Select Trip")

    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text="Select a trip:", font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        # Trip selection listbox
        self.trip_listbox = tk.Listbox(master, width=60, height=15)
        self.trip_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Load trips
        self.load_trips()

        return self.trip_listbox  # Initial focus

    def load_trips(self):
        """Load trips into listbox"""
        def get_trips_operation(conn):
            cursor = conn.cursor()

            if self.auth.check_permission('manage_trips'):
                cursor.execute('''
                SELECT id, trip_name, destination, start_date, status
                FROM trips
                ORDER BY start_date DESC
                ''')
            else:
                cursor.execute('''
                SELECT id, trip_name, destination, start_date, status
                FROM trips
                WHERE created_by = ?
                ORDER BY start_date DESC
                ''', (self.auth.current_user['id'],))

            return cursor.fetchall()

        trips = safe_db_operation(get_trips_operation)

        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, status = trip
                display_text = f"{trip_id}: {name} - {destination} ({start_date}) [{status.title()}]"
                self.trip_listbox.insert(tk.END, display_text)

    def validate(self):
        """Validate selection"""
        selection = self.trip_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip.")
            return False

        # Extract trip ID from selection
        selected_text = self.trip_listbox.get(selection[0])
        self.selected_trip_id = int(selected_text.split(':')[0])
        return True

    def apply(self):
        """Apply the selection"""
        if self.callback and self.selected_trip_id:
            self.callback(self.selected_trip_id)
