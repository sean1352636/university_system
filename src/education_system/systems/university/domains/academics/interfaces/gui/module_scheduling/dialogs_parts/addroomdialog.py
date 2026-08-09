"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import dialogs_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AddRoomDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.windows.add_new_room', default="Add New Room"))
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Room number
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.labels.room_number', default="Room Number:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.room_number_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.room_number_var, width=30).grid(row=0, column=1, pady=5)

        # Building - Fetch from facilities management database
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.labels.building', default="Building:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.building_var = tk.StringVar()

        # Get list of buildings from database
        buildings = self.get_buildings_from_db()

        building_combo = ttk.Combobox(main_frame, textvariable=self.building_var,
                                      values=buildings, width=27, state='normal')
        building_combo.grid(row=1, column=1, pady=5)

        # Capacity
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.labels.capacity', default="Capacity:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.capacity_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.capacity_var, width=30).grid(row=2, column=1, pady=5)

        # Room type
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.labels.room_type', default="Room Type:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.room_type_var = tk.StringVar()
        ttk.Combobox(main_frame, textvariable=self.room_type_var, values=ROOM_TYPES, width=27).grid(row=3, column=1, pady=5)

        # Equipment
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.labels.equipment', default="Equipment:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.equipment_var = tk.StringVar()
        equipment_entry = tk.Text(main_frame, width=30, height=3)
        equipment_entry.grid(row=4, column=1, pady=5)
        self.equipment_text = equipment_entry

        # Notes
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.labels.notes', default="Notes:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        notes_entry = tk.Text(main_frame, width=30, height=3)
        notes_entry.grid(row=5, column=1, pady=5)
        self.notes_text = notes_entry

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.buttons.save', default="Save"), command=self.save_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def get_buildings_from_db(self):
        """Fetch list of buildings from facilities management database"""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection

            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if buildings table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='buildings'
                """)

                if cursor.fetchone():
                    # Get all building names
                    cursor.execute("""
                        SELECT building_name FROM buildings
                        ORDER BY building_name
                    """)
                    buildings = [row[0] for row in cursor.fetchall()]

                    # If no buildings found, return default list
                    if not buildings:
                        return ["Main Building", "Science Building", "Library", "Sports Center"]

                    return buildings
                else:
                    # Table doesn't exist, return default list
                    return ["Main Building", "Science Building", "Library", "Sports Center"]

        except Exception as e:
            # On error, return default list
            print(f"Error fetching buildings: {e}")
            return ["Main Building", "Science Building", "Library", "Sports Center"]

    def save_room(self):
        try:
            room_number = self.room_number_var.get()
            building = self.building_var.get()
            capacity = int(self.capacity_var.get())
            room_type = self.room_type_var.get()
            equipment = self.equipment_text.get(1.0, tk.END).strip()
            notes = self.notes_text.get(1.0, tk.END).strip()

            if not all([room_number, building, str(capacity), room_type]):
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.dialogs.error', default="Error"), _t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.dialogs.please_fill_in_all_required_fields', default="Please fill in all required fields."), parent=self.dialog)
                return

            room_id = self.scheduler.add_room(room_number, building, capacity, room_type, equipment, notes)

            if room_id:
                self.result = True
                self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.dialogs.error', default="Error"), _t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.dialogs.capacity_must_be_a_number', default="Capacity must be a number."), parent=self.dialog)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addroomdialog.dialogs.error', default="Error"), f"Failed to save room: {str(e)}", parent=self.dialog)

    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
