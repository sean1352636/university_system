import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from tkinter.simpledialog import Dialog
from datetime import datetime

from education_system.university_system.modules.domain.mobility.gui.trip_management_gui._imports import safe_db_operation, sqlite3


class ViewItineraryDialog(Dialog):
    def __init__(self, parent, trip_id):
        self.trip_id = trip_id
        self.trip_info = None
        self.load_trip_info()
        super().__init__(parent, "View Trip Itinerary")

    def load_trip_info(self):
        """Load trip information and itinerary"""
        def get_trip_itinerary_operation(conn):
            cursor = conn.cursor()

            # Get trip details
            cursor.execute('''
            SELECT trip_name, destination, start_date, end_date
            FROM trips WHERE id = ?
            ''', (self.trip_id,))

            trip_info = cursor.fetchone()

            if not trip_info:
                return None

            # Get itinerary items
            cursor.execute('''
            SELECT day_number, activity, location, start_time, end_time, notes
            FROM trip_itinerary
            WHERE trip_id = ?
            ORDER BY day_number, start_time
            ''', (self.trip_id,))

            itinerary_items = cursor.fetchall()

            return {'trip_info': trip_info, 'itinerary': itinerary_items}

        self.trip_data = safe_db_operation(get_trip_itinerary_operation)

    def body(self, master):
        """Create the dialog body"""
        if not self.trip_data:
            ttk.Label(master, text="Trip not found or no itinerary available.").pack(pady=20)
            return None

        trip_info = self.trip_data['trip_info']
        itinerary_items = self.trip_data['itinerary']

        trip_name, destination, start_date, end_date = trip_info

        # Trip information header
        info_frame = ttk.LabelFrame(master, text="Trip Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(info_frame, text=f"Trip: {trip_name}", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Destination: {destination}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Dates: {start_date} to {end_date}").pack(anchor=tk.W)

        # Itinerary display
        itinerary_frame = ttk.LabelFrame(master, text="Itinerary", padding=10)
        itinerary_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        if not itinerary_items:
            ttk.Label(itinerary_frame, text="No itinerary items found for this trip.").pack(pady=20)
            return None

        # Create scrolled text widget for itinerary
        itinerary_text = scrolledtext.ScrolledText(itinerary_frame, width=70, height=20,
                                                  wrap=tk.WORD, state=tk.DISABLED)
        itinerary_text.pack(fill=tk.BOTH, expand=True)

        # Populate itinerary
        itinerary_text.config(state=tk.NORMAL)

        current_day = None
        for item in itinerary_items:
            day_number, activity, location, start_time, end_time, notes = item

            if current_day != day_number:
                if current_day is not None:
                    itinerary_text.insert(tk.END, "\n")
                itinerary_text.insert(tk.END, f"DAY {day_number}:\n", "day_header")
                itinerary_text.insert(tk.END, "-" * 20 + "\n")
                current_day = day_number

            # Format time information
            if start_time and end_time:
                time_info = f"({start_time} - {end_time})"
            elif start_time:
                time_info = f"(from {start_time})"
            else:
                time_info = ""

            # Format location information
            location_info = f" at {location}" if location else ""

            itinerary_text.insert(tk.END, f"\u2022 {activity}{location_info} {time_info}\n")

            if notes:
                itinerary_text.insert(tk.END, f"  Notes: {notes}\n")

            itinerary_text.insert(tk.END, "\n")

        # Configure text tags for styling
        itinerary_text.tag_configure("day_header", font=('Arial', 10, 'bold'))
        itinerary_text.config(state=tk.DISABLED)

        return None

    def buttonbox(self):
        """Create button box"""
        box = ttk.Frame(self)
        ttk.Button(box, text="Close", command=self.ok).pack()
        box.pack(pady=10)


class ItineraryDialog(Dialog):
    def __init__(self, parent, auth, trip_id):
        self.auth = auth
        self.trip_id = trip_id
        self.trip_info = None

        # Load trip info
        self.load_trip_info()

        super().__init__(parent, "Manage Itinerary")

    def load_trip_info(self):
        """Load trip information"""
        def get_trip_info_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT trip_name, start_date, end_date
            FROM trips WHERE id = ?
            ''', (self.trip_id,))

            return cursor.fetchone()

        self.trip_info = safe_db_operation(get_trip_info_operation)

    def body(self, master):
        """Create the dialog body"""
        if not self.trip_info:
            ttk.Label(master, text="Trip not found.").pack(pady=20)
            return None

        trip_name, start_date, end_date = self.trip_info
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        trip_days = (end_date_obj - start_date_obj).days + 1

        # Trip info
        info_frame = ttk.LabelFrame(master, text="Trip Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(info_frame, text=f"Trip: {trip_name}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Duration: {trip_days} days ({start_date} to {end_date})").pack(anchor=tk.W)

        # Existing itinerary
        existing_frame = ttk.LabelFrame(master, text="Existing Itinerary", padding=10)
        existing_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.itinerary_tree = ttk.Treeview(existing_frame, columns=('day', 'activity', 'location', 'time'), show='headings', height=10)

        self.itinerary_tree.heading('day', text='Day')
        self.itinerary_tree.heading('activity', text='Activity')
        self.itinerary_tree.heading('location', text='Location')
        self.itinerary_tree.heading('time', text='Time')

        self.itinerary_tree.column('day', width=50)
        self.itinerary_tree.column('activity', width=200)
        self.itinerary_tree.column('location', width=150)
        self.itinerary_tree.column('time', width=100)

        self.itinerary_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Buttons
        buttons_frame = ttk.Frame(existing_frame)
        buttons_frame.pack(fill=tk.X)

        ttk.Button(buttons_frame, text="Add Item", command=self.add_itinerary_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Edit Item", command=self.edit_itinerary_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Delete Item", command=self.delete_itinerary_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Refresh", command=self.load_itinerary).pack(side=tk.LEFT, padx=5)

        # Load existing itinerary
        self.load_itinerary()

        return None

    def load_itinerary(self):
        """Load existing itinerary items"""
        # Clear existing items
        for item in self.itinerary_tree.get_children():
            self.itinerary_tree.delete(item)

        def get_itinerary_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, day_number, activity, location, start_time, end_time, notes
            FROM trip_itinerary
            WHERE trip_id = ?
            ORDER BY day_number, start_time
            ''', (self.trip_id,))

            return cursor.fetchall()

        items = safe_db_operation(get_itinerary_operation)

        if items:
            for item in items:
                item_id, day, activity, location, start_time, end_time, notes = item

                # Format time information
                if start_time and end_time:
                    time_info = f"{start_time}-{end_time}"
                elif start_time:
                    time_info = f"from {start_time}"
                else:
                    time_info = "All day"

                location_info = location if location else ""

                self.itinerary_tree.insert('', 'end', text=str(item_id), values=(
                    f"Day {day}", activity, location_info, time_info
                ))

    def add_itinerary_item(self):
        """Add new itinerary item"""
        if not self.trip_info:
            return

        trip_name, start_date, end_date = self.trip_info
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        trip_days = (end_date_obj - start_date_obj).days + 1

        AddItineraryItemDialog(self.parent, self.trip_id, trip_days, self.load_itinerary)

    def edit_itinerary_item(self):
        """Edit selected itinerary item"""
        selection = self.itinerary_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an itinerary item.")
            return

        item_id = self.itinerary_tree.item(selection[0])['text']
        EditItineraryItemDialog(self.parent, item_id, self.load_itinerary)

    def delete_itinerary_item(self):
        """Delete selected itinerary item"""
        selection = self.itinerary_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an itinerary item.")
            return

        item_id = self.itinerary_tree.item(selection[0])['text']
        activity = self.itinerary_tree.item(selection[0])['values'][1]

        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete '{activity}'?"):
            def delete_item_operation(conn):
                cursor = conn.cursor()
                cursor.execute('DELETE FROM trip_itinerary WHERE id = ?', (item_id,))
                return True


            if safe_db_operation(delete_item_operation):
                messagebox.showinfo("Success", "Itinerary item deleted successfully!")
                self.load_itinerary()
            else:
                messagebox.showerror("Error", "Failed to delete itinerary item.")

    def buttonbox(self):
        """Create button box"""
        box = ttk.Frame(self)
        ttk.Button(box, text="Close", command=self.ok).pack(side=tk.RIGHT, padx=5)
        box.pack(pady=5)


class AddItineraryItemDialog(Dialog):
    def __init__(self, parent, trip_id, trip_days, refresh_callback):
        self.trip_id = trip_id
        self.trip_days = trip_days
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Add Itinerary Item")

    def body(self, master):
        """Create the dialog body"""
        # Day number
        ttk.Label(master, text=f"Day number (1-{self.trip_days}):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.day_var = tk.StringVar(value="1")
        day_combo = ttk.Combobox(master, textvariable=self.day_var,
                                values=[str(i) for i in range(1, self.trip_days + 1)],
                                state="readonly", width=37)
        day_combo.grid(row=0, column=1, padx=5, pady=5)

        # Activity
        ttk.Label(master, text="Activity description:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.activity_var = tk.StringVar()
        self.activity_entry = ttk.Entry(master, textvariable=self.activity_var, width=40)
        self.activity_entry.grid(row=1, column=1, padx=5, pady=5)

        # Location
        ttk.Label(master, text="Location (optional):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.location_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        # Start time
        ttk.Label(master, text="Start time (HH:MM, optional):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_time_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.start_time_var, width=40).grid(row=3, column=1, padx=5, pady=5)

        # End time
        ttk.Label(master, text="End time (HH:MM, optional):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_time_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.end_time_var, width=40).grid(row=4, column=1, padx=5, pady=5)

        # Notes
        ttk.Label(master, text="Notes (optional):").grid(row=5, column=0, sticky=tk.NW, padx=5, pady=5)
        self.notes_text = tk.Text(master, width=40, height=3)
        self.notes_text.grid(row=5, column=1, padx=5, pady=5)

        return self.activity_entry  # Return widget, not StringVar

    def validate(self):
        """Validate itinerary item data"""
        if not self.activity_var.get().strip():
            messagebox.showerror("Validation Error", "Activity description is required.")
            return False

        # Validate time formats if provided
        for time_var, label in [(self.start_time_var, "start time"), (self.end_time_var, "end time")]:
            time_value = time_var.get().strip()
            if time_value:
                try:
                    datetime.strptime(time_value, '%H:%M')
                except ValueError:
                    messagebox.showerror("Validation Error", f"Invalid {label} format. Please use HH:MM.")
                    return False

        return True

    def apply(self):
        """Add the itinerary item"""
        def add_item_operation(conn):
            cursor = conn.cursor()

            start_time = self.start_time_var.get().strip() or None
            end_time = self.end_time_var.get().strip() or None
            location = self.location_var.get().strip() or None
            notes = self.notes_text.get(1.0, tk.END).strip() or None

            cursor.execute('''
            INSERT INTO trip_itinerary (
                trip_id, day_number, activity, location,
                start_time, end_time, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.trip_id,
                int(self.day_var.get()),
                self.activity_var.get().strip(),
                location,
                start_time,
                end_time,
                notes
            ))

            return True


        try:
            if safe_db_operation(add_item_operation):
                messagebox.showinfo("Success", "Itinerary item added successfully!")
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error", "Failed to add itinerary item.")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Conflicting itinerary item (same day and time). Please use different time.")


class EditItineraryItemDialog(Dialog):
    def __init__(self, parent, item_id, refresh_callback):
        self.item_id = item_id
        self.refresh_callback = refresh_callback
        self.item_data = None

        # Load item data
        self.load_item_data()

        super().__init__(parent, "Edit Itinerary Item")

    def load_item_data(self):
        """Load existing item data"""
        def get_item_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trip_itinerary WHERE id = ?', (self.item_id,))
            return cursor.fetchone()

        self.item_data = safe_db_operation(get_item_operation)

    def body(self, master):
        """Create the dialog body"""
        if not self.item_data:
            ttk.Label(master, text="Itinerary item not found.").pack(pady=20)
            return None

        item = self.item_data

        # Activity
        ttk.Label(master, text="Activity description:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.activity_var = tk.StringVar(value=item[3])
        ttk.Entry(master, textvariable=self.activity_var, width=40).grid(row=0, column=1, padx=5, pady=5)

        # Location
        ttk.Label(master, text="Location (optional):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.location_var = tk.StringVar(value=item[4] or "")
        ttk.Entry(master, textvariable=self.location_var, width=40).grid(row=1, column=1, padx=5, pady=5)

        # Start time
        ttk.Label(master, text="Start time (HH:MM, optional):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_time_var = tk.StringVar(value=item[5] or "")
        ttk.Entry(master, textvariable=self.start_time_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        # End time
        ttk.Label(master, text="End time (HH:MM, optional):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_time_var = tk.StringVar(value=item[6] or "")
        ttk.Entry(master, textvariable=self.end_time_var, width=40).grid(row=3, column=1, padx=5, pady=5)

        # Notes
        ttk.Label(master, text="Notes (optional):").grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        self.notes_text = tk.Text(master, width=40, height=3)
        self.notes_text.insert(1.0, item[7] or "")
        self.notes_text.grid(row=4, column=1, padx=5, pady=5)

        return self.activity_var

    def validate(self):
        """Validate itinerary item data"""
        if not self.activity_var.get().strip():
            messagebox.showerror("Validation Error", "Activity description is required.")
            return False

        # Validate time formats if provided
        for time_var, label in [(self.start_time_var, "start time"), (self.end_time_var, "end time")]:
            time_value = time_var.get().strip()
            if time_value:
                try:
                    datetime.strptime(time_value, '%H:%M')
                except ValueError:
                    messagebox.showerror("Validation Error", f"Invalid {label} format. Please use HH:MM.")
                    return False

        return True

    def apply(self):
        """Update the itinerary item"""
        def update_item_operation(conn):
            cursor = conn.cursor()

            start_time = self.start_time_var.get().strip() or None
            end_time = self.end_time_var.get().strip() or None
            location = self.location_var.get().strip() or None
            notes = self.notes_text.get(1.0, tk.END).strip() or None

            cursor.execute('''
            UPDATE trip_itinerary SET
                activity = ?, location = ?, start_time = ?, end_time = ?, notes = ?
            WHERE id = ?
            ''', (
                self.activity_var.get().strip(),
                location,
                start_time,
                end_time,
                notes,
                self.item_id
            ))

            return True


        if safe_db_operation(update_item_operation):
            messagebox.showinfo("Success", "Itinerary item updated successfully!")
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror("Error", "Failed to update itinerary item.")
