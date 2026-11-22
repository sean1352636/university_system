
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog

from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, call, list_trip_staff, staff_candidates, show_error,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.staff_dialogs'


class AssignStaffDialog(Dialog):
    """Put a member of staff on a trip through ``staff.assign_staff_member``.

    The domain refuses a duplicate assignment with a ValueError, which is
    shown as it is.
    """

    def __init__(self, parent, auth, trip_id, refresh_callback):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.refresh_callback = refresh_callback
        self.candidates = []
        super().__init__(parent, _t(f"{_K}.windows.assign", default="Assign Staff to Trip"))

    def body(self, master):
        trip = tm('trips').get_trip(self.trip_id)
        if trip:
            ttk.Label(master, text=f"{trip['trip_name']} ({trip['start_date']})",
                      font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 6))
        ttk.Label(master, text=_t(f"{_K}.labels.available_staff", default="Available Staff:")).pack(anchor=tk.W)

        self.staff_listbox = tk.Listbox(master, width=60, height=10)
        self.staff_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Label(master, text=_t(f"{_K}.labels.role", default="Role:")).pack(anchor=tk.W)
        self.role_var = tk.StringVar(value='supervisor')
        role_frame = ttk.Frame(master)
        role_frame.pack(fill=tk.X, pady=5)
        for role in tm('staff').STAFF_ROLES:
            ttk.Radiobutton(role_frame, text=role.title(), variable=self.role_var,
                            value=role).pack(side=tk.LEFT, padx=(0, 20))

        self.first_aider_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(master, text=_t(f"{_K}.labels.first_aider", default="Qualified first aider on this trip"),
                        variable=self.first_aider_var).pack(anchor=tk.W, pady=(4, 0))

        self.load_available_staff()
        return self.staff_listbox

    def load_available_staff(self):
        """Staff not already on the trip."""
        try:
            on_trip = {s['staff_user_id'] for s in list_trip_staff(self.trip_id)}
            self.candidates = staff_candidates(on_trip)
        except Exception as exc:
            show_error(self, exc)
            self.candidates = []
        for person in self.candidates:
            name = " ".join(p for p in (person['first_name'], person['last_name']) if p) or person['username']
            self.staff_listbox.insert(tk.END, f"{person['id']}: {name} ({person['username']}) - "
                                              f"{(person['role'] or 'staff').title()}")

    def validate(self):
        if not self.staff_listbox.curselection():
            messagebox.showwarning(_t(f"{_K}.dialogs.no_selection", default="No Selection"), _t(f"{_K}.dialogs.please_select_a_staff_member", default="Please select a staff member."), parent=self)
            return False
        return True

    def apply(self):
        selection = self.staff_listbox.curselection()
        if not selection:
            return
        staff_id = self.candidates[selection[0]]['id']
        ok, _ = call(self.parent, tm('staff').assign_staff_member, self.auth, self.trip_id, staff_id,
                     self.role_var.get(), first_aider=self.first_aider_var.get())
        if ok:
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), _t(f"{_K}.dialogs.staff_member_assigned_successfully", default="Staff member assigned successfully!"), parent=self.parent)
            if self.refresh_callback:
                self.refresh_callback()
