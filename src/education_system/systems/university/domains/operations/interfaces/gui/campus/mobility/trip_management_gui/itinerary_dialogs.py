
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from tkinter.simpledialog import Dialog
from datetime import datetime

from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, call, list_itinerary, show_error,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.itinerary_dialogs'


def _trip_days(trip):
    try:
        start = datetime.strptime(str(trip['start_date'])[:10], '%Y-%m-%d')
        end = datetime.strptime(str(trip.get('end_date') or trip['start_date'])[:10], '%Y-%m-%d')
        return max((end - start).days + 1, 1)
    except (TypeError, ValueError, KeyError):
        return 1


class ViewItineraryDialog(Dialog):
    """Read-only itinerary for a trip (anyone who can see the trip)."""

    def __init__(self, parent, trip_id):
        self.trip_id = int(trip_id)
        self.trip_data = None
        self.load_trip_info()
        super().__init__(parent, _t(f"{_K}.windows.view", default="View Trip Itinerary"))

    def load_trip_info(self):
        try:
            trip = tm('trips').get_trip(self.trip_id)
            self.trip_data = {'trip_info': trip, 'itinerary': list_itinerary(self.trip_id)} if trip else None
        except Exception:
            self.trip_data = None

    def body(self, master):
        if not self.trip_data:
            ttk.Label(master, text=_t(f"{_K}.labels.trip_not_found_or_no_itinerary_available", default="Trip not found or no itinerary available.")).pack(pady=20)
            return None
        trip = self.trip_data['trip_info']
        items = self.trip_data['itinerary']

        info_frame = ttk.LabelFrame(master, text=_t(f"{_K}.labels.trip_information", default="Trip Information"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(info_frame, text=f"Trip: {trip['trip_name']}", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Destination: {trip.get('destination') or ''}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Dates: {trip['start_date']} to {trip.get('end_date') or trip['start_date']}").pack(anchor=tk.W)

        itinerary_frame = ttk.LabelFrame(master, text=_t(f"{_K}.labels.itinerary", default="Itinerary"), padding=10)
        itinerary_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        if not items:
            ttk.Label(itinerary_frame, text=_t(f"{_K}.labels.no_itinerary_items_found_for_this_trip", default="No itinerary items found for this trip.")).pack(pady=20)
            return None

        text = scrolledtext.ScrolledText(itinerary_frame, width=70, height=20, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        current_day = None
        for item in items:
            if current_day != item['day_number']:
                if current_day is not None:
                    text.insert(tk.END, "\n")
                text.insert(tk.END, f"DAY {item['day_number']}:\n", "day_header")
                text.insert(tk.END, "-" * 20 + "\n")
                current_day = item['day_number']
            start, end = item.get('start_time'), item.get('end_time')
            time_info = f"({start} - {end})" if start and end else (f"(from {start})" if start else "")
            location = f" at {item['location']}" if item.get('location') else ""
            text.insert(tk.END, f"• {item['activity']}{location} {time_info}\n")
            if item.get('notes'):
                text.insert(tk.END, f"  Notes: {item['notes']}\n")
            text.insert(tk.END, "\n")
        text.tag_configure("day_header", font=('Arial', 10, 'bold'))
        text.config(state=tk.DISABLED)
        return None

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text=_t(f"{_K}.buttons.close", default="Close"), command=self.ok).pack()
        box.pack(pady=10)


class ItineraryDialog(Dialog):
    """Manage a trip's itinerary through ``itinerary.add/update/remove_itinerary_item``."""

    def __init__(self, parent, auth, trip_id):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.trip_info = tm('trips').get_trip(self.trip_id)
        self.items = {}
        super().__init__(parent, _t(f"{_K}.windows.manage", default="Manage Itinerary"))

    def body(self, master):
        if not self.trip_info:
            ttk.Label(master, text=_t(f"{_K}.labels.trip_not_found", default="Trip not found.")).pack(pady=20)
            return None
        trip = self.trip_info
        days = _trip_days(trip)

        info_frame = ttk.LabelFrame(master, text=_t(f"{_K}.labels.trip_information", default="Trip Information"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(info_frame, text=f"Trip: {trip['trip_name']}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Duration: {days} days ({trip['start_date']} to {trip.get('end_date') or trip['start_date']})").pack(anchor=tk.W)

        existing_frame = ttk.LabelFrame(master, text=_t(f"{_K}.labels.existing_itinerary", default="Existing Itinerary"), padding=10)
        existing_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Action bar first, so the list never squeezes it out.
        buttons_frame = ttk.Frame(existing_frame)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(buttons_frame, text=_t(f"{_K}.buttons.add_item", default="Add Item"), command=self.add_itinerary_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_t(f"{_K}.buttons.edit_item", default="Edit Item"), command=self.edit_itinerary_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t(f"{_K}.buttons.delete_item", default="Delete Item"), command=self.delete_itinerary_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t(f"{_K}.buttons.refresh", default="Refresh"), command=self.load_itinerary).pack(side=tk.LEFT, padx=5)

        self.itinerary_tree = ttk.Treeview(existing_frame, columns=('day', 'activity', 'location', 'time'), show='headings', height=10)
        self.itinerary_tree.heading('day', text=_t(f"{_K}.headings.day", default='Day'))
        self.itinerary_tree.heading('activity', text=_t(f"{_K}.headings.activity", default='Activity'))
        self.itinerary_tree.heading('location', text=_t(f"{_K}.headings.location", default='Location'))
        self.itinerary_tree.heading('time', text=_t(f"{_K}.headings.time", default='Time'))
        self.itinerary_tree.column('day', width=50)
        self.itinerary_tree.column('activity', width=200)
        self.itinerary_tree.column('location', width=150)
        self.itinerary_tree.column('time', width=100)
        self.itinerary_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.load_itinerary()
        return None

    def load_itinerary(self):
        self.itinerary_tree.delete(*self.itinerary_tree.get_children())
        try:
            items = list_itinerary(self.trip_id)
        except Exception as exc:
            show_error(self, exc)
            return
        self.items = {str(i['id']): i for i in items}
        for item in items:
            start, end = item.get('start_time'), item.get('end_time')
            time_info = f"{start}-{end}" if start and end else (f"from {start}" if start else "All day")
            self.itinerary_tree.insert('', 'end', iid=str(item['id']), values=(
                f"Day {item['day_number']}", item['activity'], item.get('location') or "", time_info))

    def _selected(self):
        selection = self.itinerary_tree.selection()
        if not selection:
            messagebox.showwarning(_t(f"{_K}.dialogs.no_selection", default="No Selection"), _t(f"{_K}.dialogs.please_select_an_itinerary_item", default="Please select an itinerary item."), parent=self)
            return None
        return self.items.get(selection[0])

    def add_itinerary_item(self):
        if self.trip_info:
            AddItineraryItemDialog(self, self.auth, self.trip_id, _trip_days(self.trip_info), self.load_itinerary)

    def edit_itinerary_item(self):
        item = self._selected()
        if item:
            EditItineraryItemDialog(self, self.auth, self.trip_id, item, self.load_itinerary)

    def delete_itinerary_item(self):
        item = self._selected()
        if not item:
            return
        if messagebox.askyesno(_t(f"{_K}.dialogs.confirm_deletion", default="Confirm Deletion"), f"Are you sure you want to delete '{item['activity']}'?", parent=self):
            ok, _ = call(self, tm('itinerary').remove_itinerary_item, self.auth, self.trip_id, item['id'])
            if ok:
                messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), _t(f"{_K}.dialogs.itinerary_item_deleted_successfully", default="Itinerary item deleted successfully!"), parent=self)
                self.load_itinerary()

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text=_t(f"{_K}.buttons.close", default="Close"), command=self.ok).pack(side=tk.RIGHT, padx=5)
        box.pack(pady=5)


class _ItemForm(Dialog):
    """Shared fields for adding / editing an itinerary item."""

    def _fields(self, master, item, *, with_day):
        row = 0
        if with_day:
            ttk.Label(master, text=f"Day number (1-{self.trip_days}):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            self.day_var = tk.StringVar(value=str(item.get('day_number') or 1))
            ttk.Combobox(master, textvariable=self.day_var, values=[str(i) for i in range(1, self.trip_days + 1)],
                         state="readonly", width=37).grid(row=row, column=1, padx=5, pady=5)
            row += 1
        ttk.Label(master, text=_t(f"{_K}.labels.activity_description", default="Activity description:")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.activity_var = tk.StringVar(value=item.get('activity') or '')
        self.activity_entry = ttk.Entry(master, textvariable=self.activity_var, width=40)
        self.activity_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1
        ttk.Label(master, text=_t(f"{_K}.labels.location_optional", default="Location (optional):")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.location_var = tk.StringVar(value=item.get('location') or '')
        ttk.Entry(master, textvariable=self.location_var, width=40).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        ttk.Label(master, text=_t(f"{_K}.labels.start_time_hh_mm_optional", default="Start time (HH:MM, optional):")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_time_var = tk.StringVar(value=item.get('start_time') or '')
        ttk.Entry(master, textvariable=self.start_time_var, width=40).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        ttk.Label(master, text=_t(f"{_K}.labels.end_time_hh_mm_optional", default="End time (HH:MM, optional):")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_time_var = tk.StringVar(value=item.get('end_time') or '')
        ttk.Entry(master, textvariable=self.end_time_var, width=40).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        ttk.Label(master, text=_t(f"{_K}.labels.notes_optional", default="Notes (optional):")).grid(row=row, column=0, sticky=tk.NW, padx=5, pady=5)
        self.notes_text = tk.Text(master, width=40, height=3)
        self.notes_text.insert(1.0, item.get('notes') or '')
        self.notes_text.grid(row=row, column=1, padx=5, pady=5)
        return self.activity_entry

    def validate(self):
        if not self.activity_var.get().strip():
            messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), _t(f"{_K}.dialogs.activity_description_is_required", default="Activity description is required."), parent=self)
            return False
        for var, label in ((self.start_time_var, "start time"), (self.end_time_var, "end time")):
            value = var.get().strip()
            if value:
                try:
                    datetime.strptime(value, '%H:%M')
                except ValueError:
                    messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), f"Invalid {label} format. Please use HH:MM.", parent=self)
                    return False
        return True

    def _values(self):
        return {'activity': self.activity_var.get().strip(),
                'location': self.location_var.get().strip() or None,
                'start_time': self.start_time_var.get().strip() or None,
                'end_time': self.end_time_var.get().strip() or None,
                'notes': self.notes_text.get(1.0, tk.END).strip() or None}


class AddItineraryItemDialog(_ItemForm):
    def __init__(self, parent, auth, trip_id, trip_days, refresh_callback):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.trip_days = trip_days
        self.refresh_callback = refresh_callback
        super().__init__(parent, _t(f"{_K}.windows.add", default="Add Itinerary Item"))

    def body(self, master):
        return self._fields(master, {}, with_day=True)

    def apply(self):
        values = self._values()
        # A clash (same day and start time) comes back from the domain as a
        # ValueError with its own message.
        ok, _ = call(self.parent, tm('itinerary').add_itinerary_item, self.auth, self.trip_id,
                     int(self.day_var.get()), values['activity'], values['location'],
                     values['start_time'], values['end_time'], values['notes'])
        if ok:
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), _t(f"{_K}.dialogs.itinerary_item_added_successfully", default="Itinerary item added successfully!"), parent=self.parent)
            if self.refresh_callback:
                self.refresh_callback()


class EditItineraryItemDialog(_ItemForm):
    def __init__(self, parent, auth, trip_id, item, refresh_callback):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.item_data = item
        self.refresh_callback = refresh_callback
        super().__init__(parent, _t(f"{_K}.windows.edit", default="Edit Itinerary Item"))

    def body(self, master):
        if not self.item_data:
            ttk.Label(master, text=_t(f"{_K}.labels.itinerary_item_not_found", default="Itinerary item not found.")).pack(pady=20)
            return None
        return self._fields(master, self.item_data, with_day=False)

    def apply(self):
        ok, _ = call(self.parent, tm('itinerary').update_itinerary_item, self.auth, self.trip_id,
                     self.item_data['id'], **self._values())
        if ok:
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), _t(f"{_K}.dialogs.itinerary_item_updated_successfully", default="Itinerary item updated successfully!"), parent=self.parent)
            if self.refresh_callback:
                self.refresh_callback()
