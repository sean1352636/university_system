"""Room management tab for the Exam Scheduling System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.models import Room

# i18n import
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _
except ImportError:
    def _(key, **kwargs):
        return key


class RoomsTabMixin:
    """Mixin providing the room management tab and its operations."""

    # ── Building / room pickers ─────────────────────────────────────

    def refresh_room_choices(self):
        """Reload the building list from the rooms already in the database.

        Sourced from ``data_manager.rooms`` rather than a fresh query so the
        dropdowns always agree with the list on the right of this tab.
        """
        rooms = getattr(self.data_manager, "rooms", []) or []
        buildings = sorted({(r.building or "").strip()
                            for r in rooms if (r.building or "").strip()})
        try:
            self.building_combo["values"] = buildings
        except (tk.TclError, AttributeError):
            return
        self._refresh_room_names(self.room_form_vars["building"].get())

    def _rooms_in_building(self, building):
        building = (building or "").strip().lower()
        return [r for r in (getattr(self.data_manager, "rooms", []) or [])
                if (r.building or "").strip().lower() == building]

    def _refresh_room_names(self, building):
        """Narrow the room dropdown to one building."""
        names = sorted({(r.name or "").strip()
                        for r in self._rooms_in_building(building)
                        if (r.name or "").strip()})
        try:
            self.room_name_combo["values"] = names
        except (tk.TclError, AttributeError):
            pass

    def _on_building_selected(self, _event=None):
        """Building changed: re-list its rooms and drop a now-invalid room."""
        building = self.room_form_vars["building"].get()
        self._refresh_room_names(building)
        current = self.room_form_vars["room_name"].get().strip()
        if current and current not in (self.room_name_combo["values"] or ()):
            # The selected room is not in this building — clear it rather than
            # leave a pairing that does not exist.
            self.room_form_vars["room_name"].set("")
            self.room_form_vars["capacity"].set("")

    def _on_room_name_selected(self, _event=None):
        """Room chosen: fill in its capacity and facilities."""
        building = self.room_form_vars["building"].get()
        name = self.room_form_vars["room_name"].get().strip().lower()
        for room in self._rooms_in_building(building):
            if (room.name or "").strip().lower() == name:
                self.room_form_vars["capacity"].set(str(room.capacity or 0))
                # The checkboxes describe the same room, so match them too;
                # leaving them stale would silently edit the room's facilities.
                try:
                    self.has_computers_var.set(bool(room.has_computers))
                    self.has_projector_var.set(bool(room.has_projector))
                except (tk.TclError, AttributeError):
                    pass
                self.selected_room_id = room.id
                return

    def create_rooms_tab(self):
        """Create the room management tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("exam_scheduler.tabs.manage_rooms"))

        # Split layout
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left - Form
        form_frame = ttk.LabelFrame(paned, text=_("exam_scheduler.frames.room_details"), padding="15")
        paned.add(form_frame, weight=1)

        # Room form fields.
        #
        # Building and room are dropdowns over what is already in the database,
        # and picking an existing room fills in its capacity — typing a
        # building name and a room number from memory was the old interface and
        # a typo silently created a duplicate room in a building that did not
        # exist.
        #
        # They stay *editable* comboboxes rather than readonly: this same form
        # adds new rooms, and a readonly list could only ever describe rooms
        # that already exist.
        fields = [
            (_("exam_scheduler.labels.building"), "building"),
            (_("exam_scheduler.labels.room_name"), "room_name"),
            (_("exam_scheduler.labels.capacity"), "capacity"),
        ]
        self.room_form_vars = {name: tk.StringVar() for _label, name in fields}
        for i, (label, var_name) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)

        self.building_combo = ttk.Combobox(
            form_frame, textvariable=self.room_form_vars["building"], width=23)
        self.building_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.building_combo.bind("<<ComboboxSelected>>", self._on_building_selected)

        self.room_name_combo = ttk.Combobox(
            form_frame, textvariable=self.room_form_vars["room_name"], width=23)
        self.room_name_combo.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.room_name_combo.bind("<<ComboboxSelected>>", self._on_room_name_selected)

        ttk.Entry(form_frame, textvariable=self.room_form_vars["capacity"],
                  width=25).grid(row=2, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        self.refresh_room_choices()

        # Checkboxes
        self.has_computers_var = tk.BooleanVar()
        self.has_projector_var = tk.BooleanVar()

        ttk.Checkbutton(form_frame, text=_("exam_scheduler.labels.has_computers"), variable=self.has_computers_var).grid(
            row=len(fields), column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(form_frame, text=_("exam_scheduler.labels.has_projector"), variable=self.has_projector_var).grid(
            row=len(fields)+1, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=len(fields)+2, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.add_room"), command=self.add_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.update"), command=self.update_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.delete"), command=self.delete_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.clear"), command=self.clear_room_form).pack(side=tk.LEFT, padx=5)

        self.selected_room_id = None

        # Right - List
        list_frame = ttk.LabelFrame(paned, text=_("exam_scheduler.frames.room_list"), padding="10")
        paned.add(list_frame, weight=2)

        columns = ('id', 'name', 'building', 'capacity', 'facilities')
        self.room_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.room_tree.heading('id', text=_("exam_scheduler.columns.id"))
        self.room_tree.heading('name', text=_("exam_scheduler.columns.room"))
        self.room_tree.heading('building', text=_("exam_scheduler.columns.building"))
        self.room_tree.heading('capacity', text=_("exam_scheduler.columns.capacity"))
        self.room_tree.heading('facilities', text=_("exam_scheduler.columns.facilities"))

        self.room_tree.column('id', width=40)
        self.room_tree.column('name', width=100)
        self.room_tree.column('building', width=120)
        self.room_tree.column('capacity', width=70)
        self.room_tree.column('facilities', width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.room_tree.yview)
        self.room_tree.configure(yscrollcommand=scrollbar.set)

        self.room_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.room_tree.bind('<<TreeviewSelect>>', self.on_room_select)

    # --- Room CRUD ---

    def refresh_room_list(self):
        """Refresh the room list."""
        # Tabs build lazily; skip widgets that haven't been created yet.
        if getattr(self, "room_tree", None) is not None:
            for item in self.room_tree.get_children():
                self.room_tree.delete(item)

            for room in self.data_manager.rooms:
                facilities = []
                if room.has_computers:
                    facilities.append(_("exam_scheduler.facilities.computers"))
                if room.has_projector:
                    facilities.append(_("exam_scheduler.facilities.projector"))
                facilities_str = ", ".join(facilities) if facilities else _("exam_scheduler.facilities.none")

                self.room_tree.insert('', tk.END, values=(
                    room.id, room.name, room.building, room.capacity, facilities_str
                ))

        # Keep the building/room dropdowns in step with the list — otherwise a
        # room added here would not appear in its own picker until reopen.
        if getattr(self, "building_combo", None) is not None:
            self.refresh_room_choices()

        if getattr(self, "room_combo", None) is not None:
            self.update_room_combo()

    def add_room(self):
        """Add a new room."""
        name = self.room_form_vars['room_name'].get().strip()
        building = self.room_form_vars['building'].get().strip()
        capacity_str = self.room_form_vars['capacity'].get().strip()

        if not all([name, building, capacity_str]):
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.fill_all_fields"))
            return

        try:
            capacity = int(capacity_str)
        except ValueError:
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.capacity_must_be_number"))
            return

        room = Room(
            id=self.data_manager.get_next_room_id(),
            name=name,
            building=building,
            capacity=capacity,
            has_computers=self.has_computers_var.get(),
            has_projector=self.has_projector_var.get()
        )

        self.data_manager.add_room(room)
        self.refresh_room_list()
        self.clear_room_form()
        messagebox.showinfo(_("exam_scheduler.dialogs.success"), _("exam_scheduler.messages.room_added"))

    def update_room(self):
        """Update the selected room."""
        if not self.selected_room_id:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.select_room_to_update"))
            return

        name = self.room_form_vars['room_name'].get().strip()
        building = self.room_form_vars['building'].get().strip()
        capacity_str = self.room_form_vars['capacity'].get().strip()

        if not all([name, building, capacity_str]):
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.fill_all_fields"))
            return

        try:
            capacity = int(capacity_str)
        except ValueError:
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.capacity_must_be_number"))
            return

        room = Room(
            id=self.selected_room_id,
            name=name,
            building=building,
            capacity=capacity,
            has_computers=self.has_computers_var.get(),
            has_projector=self.has_projector_var.get()
        )

        self.data_manager.update_room(room)
        self.refresh_room_list()
        self.clear_room_form()
        messagebox.showinfo(_("exam_scheduler.dialogs.success"), _("exam_scheduler.messages.room_updated"))

    def delete_room(self):
        """Delete the selected room."""
        if not self.selected_room_id:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.select_room_to_delete"))
            return

        # Check if room is in use
        room = next((r for r in self.data_manager.rooms if r.id == self.selected_room_id), None)
        if room:
            in_use = any(e.room == room.name for e in self.data_manager.exams)
            if in_use:
                messagebox.showerror(_("exam_scheduler.dialogs.error"), _("exam_scheduler.messages.room_in_use"))
                return

        if messagebox.askyesno(_("exam_scheduler.dialogs.confirm_delete"), _("exam_scheduler.messages.confirm_delete_room")):
            self.data_manager.delete_room(self.selected_room_id)
            self.refresh_room_list()
            self.clear_room_form()
            messagebox.showinfo(_("exam_scheduler.dialogs.success"), _("exam_scheduler.messages.room_deleted"))

    def clear_room_form(self):
        """Clear the room form."""
        for var in self.room_form_vars.values():
            var.set("")
        self.has_computers_var.set(False)
        self.has_projector_var.set(False)
        self.selected_room_id = None
        # With no building selected the room list has nothing to narrow to;
        # leaving the previous building's rooms listed would be misleading.
        if getattr(self, "room_name_combo", None) is not None:
            self._refresh_room_names("")

    def on_room_select(self, event):
        """Handle room selection in the tree."""
        selection = self.room_tree.selection()
        if not selection:
            return

        item = self.room_tree.item(selection[0])
        room_id = item['values'][0]

        room = next((r for r in self.data_manager.rooms if r.id == room_id), None)
        if not room:
            return

        self.selected_room_id = room_id

        self.room_form_vars['room_name'].set(room.name)
        self.room_form_vars['building'].set(room.building)
        self.room_form_vars['capacity'].set(str(room.capacity))
        self.has_computers_var.set(room.has_computers)
        self.has_projector_var.set(room.has_projector)
