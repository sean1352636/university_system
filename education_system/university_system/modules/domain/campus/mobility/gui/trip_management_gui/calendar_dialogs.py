import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog

from education_system.university_system.modules.domain.campus.mobility.gui.trip_management_gui._imports import safe_db_operation


class CreateCalendarEventDialog(Dialog):
    def __init__(self, parent, auth, calendar_manager, refresh_callback):
        self.auth = auth
        self.calendar_manager = calendar_manager
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Create Calendar Event for Trip")

    def body(self, master):
        """Create the dialog body"""
        ttk.Label(master, text="Select trip to create calendar event:").pack(anchor=tk.W, pady=(0, 10))

        # Trip selection
        self.trip_listbox = tk.Listbox(master, width=60, height=12)
        self.trip_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Load trips without calendar events
        self.load_trips_without_events()

        return self.trip_listbox

    def load_trips_without_events(self):
        """Load trips that don't have calendar events"""
        def get_trips_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
            FROM trips t
            LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
            WHERE tce.trip_id IS NULL AND t.status IN ('planning', 'open')
            ORDER BY t.start_date
            ''')

            return cursor.fetchall()

        trips = safe_db_operation(get_trips_operation)

        if trips:
            for trip in trips:
                trip_id, name, destination, start_date, end_date, status = trip
                display_text = f"{trip_id}: {name} to {destination} ({start_date} - {end_date}) [{status.title()}]"
                self.trip_listbox.insert(tk.END, display_text)
        else:
            self.trip_listbox.insert(tk.END, "No trips available for calendar event creation")

    def validate(self):
        """Validate trip selection"""
        selection = self.trip_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trip.")
            return False

        selected_text = self.trip_listbox.get(selection[0])
        if "No trips available" in selected_text:
            messagebox.showwarning("No Trips", "No trips available for calendar event creation.")
            return False

        return True

    def apply(self):
        """Create the calendar event"""
        selection = self.trip_listbox.curselection()
        if not selection:
            return

        # Extract trip ID from selection
        selected_text = self.trip_listbox.get(selection[0])
        trip_id = int(selected_text.split(':')[0])

        try:
            # Create calendar event using the calendar manager
            result = self.calendar_manager.create_trip_event(trip_id)

            if result['success']:
                messagebox.showinfo("Success", f"\u2713 Calendar event created successfully!\nEvent ID: {result['event_id']}")
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error", f"\u2717 Failed to create calendar event: {result['message']}")

        except Exception as e:
            messagebox.showerror("Error", f"Error creating calendar event: {e}")
