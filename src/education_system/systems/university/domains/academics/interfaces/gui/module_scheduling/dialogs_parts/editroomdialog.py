"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import dialogs_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class EditRoomDialog:
    def __init__(self, parent, scheduler, room_id):
        self.parent = parent
        self.scheduler = scheduler
        self.room_id = room_id
        self.result = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.windows.edit_room', default="Edit Room"))
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)

        self.load_current_data()
        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass

    def load_current_data(self):
        """Load current room data"""
        try:
            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT * FROM rooms WHERE id = ?', (self.room_id,))
                room = cursor.fetchone()

            if room:
                self.current_data = {
                    'room_number': room[1],
                    'building': room[2],
                    'capacity': room[3],
                    'room_type': room[4],
                    'equipment': room[5] or "",
                    'notes': room[6] or ""
                }
            else:
                raise CourseNotFoundError(f"Room {self.room_id}")

        except (CourseNotFoundError, sqlite3.Error) as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.dialogs.error', default="Error"), f"Failed to load room data: {str(e)}", parent=self.dialog)
            self.dialog.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Room number (read-only)
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.labels.room_number', default="Room Number:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        room_label = ttk.Label(main_frame, text=self.current_data['room_number'], font=('Arial', 10, 'bold'))
        room_label.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Building (read-only)
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.labels.building', default="Building:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        building_label = ttk.Label(main_frame, text=self.current_data['building'], font=('Arial', 10, 'bold'))
        building_label.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Capacity
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.labels.capacity', default="Capacity:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.capacity_var = tk.StringVar(value=str(self.current_data['capacity']))
        ttk.Entry(main_frame, textvariable=self.capacity_var, width=30).grid(row=2, column=1, pady=5)

        # Room type
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.labels.room_type', default="Room Type:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.room_type_var = tk.StringVar(value=self.current_data['room_type'])
        ttk.Combobox(main_frame, textvariable=self.room_type_var, values=ROOM_TYPES, width=27).grid(row=3, column=1, pady=5)

        # Equipment
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.labels.equipment', default="Equipment:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.equipment_text = tk.Text(main_frame, width=30, height=3)
        self.equipment_text.grid(row=4, column=1, pady=5)
        self.equipment_text.insert(1.0, self.current_data['equipment'])

        # Notes
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.labels.notes', default="Notes:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.notes_text = tk.Text(main_frame, width=30, height=3)
        self.notes_text.grid(row=5, column=1, pady=5)
        self.notes_text.insert(1.0, self.current_data['notes'])

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.buttons.update', default="Update"), command=self.update_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def update_room(self):
        try:
            new_capacity = int(self.capacity_var.get())
            new_equipment = self.equipment_text.get(1.0, tk.END).strip()
            new_notes = self.notes_text.get(1.0, tk.END).strip()

            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE rooms SET capacity = ?, equipment = ?, notes = ? WHERE id = ?
                ''', (new_capacity, new_equipment, new_notes, self.room_id))

                conn.commit()

            self.result = True
            # Confirm first, then close — see addholidaydialog.save_holiday.
            messagebox.showinfo(_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.dialogs.success', default="Success"), _t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.dialogs.room_updated_successfully', default="Room updated successfully."), parent=self.dialog)
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.dialogs.error', default="Error"), _t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.dialogs.capacity_must_be_a_number', default="Capacity must be a number."), parent=self.dialog)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editroomdialog.dialogs.error', default="Error"), f"Failed to update room: {str(e)}", parent=self.dialog)

    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
