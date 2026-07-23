import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from education_system.post_18.university_system.core.i18n import get_text as _
from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.utils import safe_grab_set

gui_logger = logging.getLogger(__name__)

class AddEventDialog:
    """Dialog for adding new events"""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.add_event.title"))
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.add_event.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Event name
        ttk.Label(main_frame, text=_("academic_calendar.labels.event_name_required")).pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=50).pack(fill=tk.X, pady=(5, 15))

        # Event type
        ttk.Label(main_frame, text=_("academic_calendar.labels.event_type")).pack(anchor=tk.W)
        self.type_var = tk.StringVar(value="Academic")
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=47,
                                values=["Academic", "Holiday", "Administrative", "Social",
                                       "Sports", "Trip", "Deadline"])
        type_combo.pack(fill=tk.X, pady=(5, 15))

        # Date type selection
        date_type_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.date_configuration"), padding=10)
        date_type_frame.pack(fill=tk.X, pady=(0, 15))

        self.date_type = tk.StringVar(value="single")
        ttk.Radiobutton(date_type_frame, text=_("academic_calendar.labels.single_date"), variable=self.date_type,
                       value="single", command=self._toggle_date_fields).pack(anchor=tk.W)
        ttk.Radiobutton(date_type_frame, text=_("academic_calendar.labels.date_range"), variable=self.date_type,
                       value="range", command=self._toggle_date_fields).pack(anchor=tk.W)

        # Single date
        self.single_date_frame = ttk.Frame(date_type_frame)
        self.single_date_frame.pack(fill=tk.X, pady=5)

        ttk.Label(self.single_date_frame, text=_("academic_calendar.labels.date_format")).pack(anchor=tk.W)
        self.single_date_var = tk.StringVar()
        ttk.Entry(self.single_date_frame, textvariable=self.single_date_var, width=47).pack(fill=tk.X)

        # Date range
        self.date_range_frame = ttk.Frame(date_type_frame)

        ttk.Label(self.date_range_frame, text=_("academic_calendar.labels.start_date_format")).pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(self.date_range_frame, textvariable=self.start_date_var, width=47).pack(fill=tk.X)

        ttk.Label(self.date_range_frame, text=_("academic_calendar.labels.end_date_format")).pack(anchor=tk.W, pady=(10, 0))
        self.end_date_var = tk.StringVar()
        ttk.Entry(self.date_range_frame, textvariable=self.end_date_var, width=47).pack(fill=tk.X)

        # Description
        ttk.Label(main_frame, text=_("academic_calendar.labels.description")).pack(anchor=tk.W)
        self.description_text = scrolledtext.ScrolledText(main_frame, height=5, width=50)
        self.description_text.pack(fill=tk.X, pady=(5, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.add_event_action"), command=self._add_event).pack(side=tk.RIGHT)

        # Initialize date fields
        self._toggle_date_fields()

    def _toggle_date_fields(self):
        """Toggle date fields based on selection"""
        if self.date_type.get() == "single":
            self.single_date_frame.pack(fill=tk.X, pady=5)
            self.date_range_frame.pack_forget()
        else:
            self.single_date_frame.pack_forget()
            self.date_range_frame.pack(fill=tk.X, pady=5)

    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _add_event(self):
        """Add the event"""
        try:
            name = self.name_var.get().strip()
            if not name:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.event_name_required"))
                return

            event_type = self.type_var.get()
            description = self.description_text.get(1.0, tk.END).strip()

            if self.date_type.get() == "single":
                date = self.single_date_var.get().strip()
                if not date:
                    messagebox.showerror(_("common.error"), _("academic_calendar.messages.date_required"))
                    return

                result = self.calendar_manager.add_event(
                    name=name,
                    date=date,
                    description=description,
                    event_type=event_type
                )
            else:
                start_date = self.start_date_var.get().strip()
                end_date = self.end_date_var.get().strip()

                if not start_date or not end_date:
                    messagebox.showerror(_("common.error"), _("academic_calendar.messages.both_dates_required"))
                    return

                result = self.calendar_manager.add_event(
                    name=name,
                    date_start=start_date,
                    date_end=end_date,
                    description=description,
                    event_type=event_type
                )

            if result['success']:
                messagebox.showinfo(_("common.success"), result['message'])
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), result['message'])

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_to_add_event").format(error=e))


class EditEventDialog:
    """Dialog for editing existing events"""

    def __init__(self, parent, calendar_manager, event_data, callback=None):
        self.calendar_manager = calendar_manager
        self.event_data = event_data
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.edit_event.title"))
        self.dialog.geometry("550x750")
        self.dialog.minsize(500, 650)
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._load_event_data()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        # Buttons at the bottom — packed FIRST so they always show
        button_frame = ttk.Frame(self.dialog, padding=(20, 10))
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Button(button_frame, text=_("academic_calendar.buttons.save_changes"), command=self._save_event).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT)

        ttk.Separator(self.dialog, orient="horizontal").pack(side=tk.BOTTOM, fill=tk.X)

        # Scrollable content area
        canvas = tk.Canvas(self.dialog, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, padding=20)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Mouse wheel scrolling
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        main_frame = scroll_frame

        # Title
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.edit_event.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Event ID (read-only)
        ttk.Label(main_frame, text=_("academic_calendar.labels.event_id")).pack(anchor=tk.W)
        id_frame = ttk.Frame(main_frame)
        id_frame.pack(fill=tk.X, pady=(5, 10))

        self.id_var = tk.StringVar()
        id_entry = ttk.Entry(id_frame, textvariable=self.id_var, state="readonly")
        id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(id_frame, text=_("common.copy"), width=8,
                  command=lambda: self._copy_to_clipboard(self.id_var.get())).pack(side=tk.RIGHT, padx=(5, 0))

        # Event name
        ttk.Label(main_frame, text=_("academic_calendar.labels.event_name_required")).pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=50).pack(fill=tk.X, pady=(5, 10))

        # Event type
        ttk.Label(main_frame, text=_("academic_calendar.labels.event_type")).pack(anchor=tk.W)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=47,
                                values=["Academic", "Holiday", "Administrative", "Social",
                                       "Sports", "Trip", "Deadline"])
        type_combo.pack(fill=tk.X, pady=(5, 10))

        # Dates
        date_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.dates"), padding=10)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        # Single date
        ttk.Label(date_frame, text=_("academic_calendar.labels.date_format")).pack(anchor=tk.W)
        self.date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.date_var, width=47).pack(fill=tk.X, pady=(5, 8))

        # Start date
        ttk.Label(date_frame, text=_("academic_calendar.labels.start_date_format")).pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=47).pack(fill=tk.X, pady=(5, 8))

        # End date
        ttk.Label(date_frame, text=_("academic_calendar.labels.end_date_format")).pack(anchor=tk.W)
        self.end_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=47).pack(fill=tk.X, pady=(5, 0))

        # Description
        ttk.Label(main_frame, text=_("academic_calendar.labels.description")).pack(anchor=tk.W, pady=(10, 0))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=4, width=50)
        self.description_text.pack(fill=tk.X, pady=(5, 0))

    def _load_event_data(self):
        """Load event data into form"""
        self.id_var.set(self.event_data.get('id', ''))
        self.name_var.set(self.event_data.get('name', ''))
        self.type_var.set(self.event_data.get('event_type', 'Academic'))
        self.date_var.set(self.event_data.get('date', ''))
        self.start_date_var.set(self.event_data.get('date_start', ''))
        self.end_date_var.set(self.event_data.get('date_end', ''))

        description = self.event_data.get('description', '')
        if description:
            self.description_text.insert(1.0, description)

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(text)
        messagebox.showinfo(_("academic_calendar.messages.copied"), _("academic_calendar.messages.event_id_copied"))

    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _save_event(self):
        """Save event changes"""
        try:
            updates = {}

            # Check what changed
            if self.name_var.get() != self.event_data.get('name', ''):
                updates['name'] = self.name_var.get().strip()

            if self.type_var.get() != self.event_data.get('event_type', ''):
                updates['event_type'] = self.type_var.get()

            if self.date_var.get() != self.event_data.get('date', ''):
                updates['date'] = self.date_var.get().strip() or None

            if self.start_date_var.get() != self.event_data.get('date_start', ''):
                updates['date_start'] = self.start_date_var.get().strip() or None

            if self.end_date_var.get() != self.event_data.get('date_end', ''):
                updates['date_end'] = self.end_date_var.get().strip() or None

            new_description = self.description_text.get(1.0, tk.END).strip()
            if new_description != self.event_data.get('description', ''):
                updates['description'] = new_description

            if not updates:
                messagebox.showinfo(_("academic_calendar.messages.no_changes"), _("academic_calendar.messages.no_changes_made"))
                return

            result = self.calendar_manager.update_event(self.event_data['id'], updates)

            if result['success']:
                messagebox.showinfo(_("common.success"), result['message'])
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), result['message'])

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_to_update_event").format(error=e))


class EventDetailsDialog:
    """Dialog for viewing event details"""

    def __init__(self, parent, event_data):
        self.event_data = event_data

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.event_details.title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.event_details.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Details frame
        details_frame = ttk.Frame(main_frame)
        details_frame.pack(fill=tk.BOTH, expand=True)

        # Event details
        details = [
            (_("academic_calendar.labels.event_id_colon"), self.event_data.get('id', _("common.na"))),
            (_("academic_calendar.labels.name_colon"), self.event_data.get('name', _("common.na"))),
            (_("academic_calendar.labels.type_colon"), self.event_data.get('event_type', _("common.na"))),
            (_("academic_calendar.labels.date_colon"), self.event_data.get('date', _("common.na"))),
            (_("academic_calendar.labels.start_date_colon"), self.event_data.get('date_start', _("common.na"))),
            (_("academic_calendar.labels.end_date_colon"), self.event_data.get('date_end', _("common.na"))),
            (_("academic_calendar.labels.created_colon"), self.event_data.get('date_added', _("common.na"))),
            (_("academic_calendar.labels.modified_colon"), self.event_data.get('last_modified', _("common.na"))),
            (_("academic_calendar.labels.created_by_colon"), self.event_data.get('created_by', _("common.na")))
        ]

        for i, (label, value) in enumerate(details):
            if value and value != _("common.na"):
                label_widget = ttk.Label(details_frame, text=label, font=('Arial', 9, 'bold'))
                label_widget.grid(row=i, column=0, sticky=tk.W, padx=(0, 10), pady=2)

                value_widget = ttk.Label(details_frame, text=str(value))
                value_widget.grid(row=i, column=1, sticky=tk.W, pady=2)

        # Description
        desc_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.description"), padding=10)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        description = self.event_data.get('description', _("academic_calendar.messages.no_description_available"))
        desc_text = scrolledtext.ScrolledText(desc_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        desc_text.pack(fill=tk.BOTH, expand=True)
        desc_text.config(state=tk.NORMAL)
        desc_text.insert(1.0, description)
        desc_text.config(state=tk.DISABLED)

        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(20, 0))

    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


