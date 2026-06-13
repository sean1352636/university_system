import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from education_system.university_system.core.i18n import get_text as _
from education_system.university_system.modules.domain.academics.gui.academic_calendar.utils import safe_grab_set

gui_logger = logging.getLogger(__name__)

class RecurringEventDialog:
    """Dialog for creating recurring events"""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.recurring_events.title"))
        self.dialog.geometry("550x750")
        self.dialog.minsize(500, 650)
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.recurring_events.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Event details
        details_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.event_details"), padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(details_frame, text=_("academic_calendar.labels.event_name_required")).pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.name_var, width=50).pack(fill=tk.X, pady=(5, 15))

        ttk.Label(details_frame, text=_("academic_calendar.labels.start_date_format_required")).pack(anchor=tk.W)
        self.date_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.date_var, width=50).pack(fill=tk.X, pady=(5, 15))

        ttk.Label(details_frame, text=_("academic_calendar.labels.description")).pack(anchor=tk.W)
        self.description_text = scrolledtext.ScrolledText(details_frame, height=3, width=50)
        self.description_text.pack(fill=tk.X, pady=(5, 15))

        ttk.Label(details_frame, text=_("academic_calendar.labels.event_type")).pack(anchor=tk.W)
        self.type_var = tk.StringVar(value="Academic")
        type_combo = ttk.Combobox(details_frame, textvariable=self.type_var, width=47,
                                values=["Academic", "Holiday", "Administrative", "Social", "Sports", "Trip", "Deadline"])
        type_combo.pack(fill=tk.X, pady=(5, 0))

        # Recurrence pattern
        pattern_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.recurrence_pattern"), padding=10)
        pattern_frame.pack(fill=tk.X, pady=(0, 15))

        # Frequency
        freq_frame = ttk.Frame(pattern_frame)
        freq_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(freq_frame, text=_("academic_calendar.labels.frequency")).pack(side=tk.LEFT)
        self.frequency_var = tk.StringVar(value="weekly")
        freq_combo = ttk.Combobox(freq_frame, textvariable=self.frequency_var, width=15,
                                values=["daily", "weekly", "monthly", "yearly"])
        freq_combo.pack(side=tk.LEFT, padx=(5, 15))

        ttk.Label(freq_frame, text=_("academic_calendar.labels.every")).pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value="1")
        ttk.Entry(freq_frame, textvariable=self.interval_var, width=5).pack(side=tk.LEFT, padx=(5, 0))

        # End condition
        end_frame = ttk.LabelFrame(pattern_frame, text=_("academic_calendar.labels.end_condition"), padding=5)
        end_frame.pack(fill=tk.X)

        self.end_type_var = tk.StringVar(value="date")
        ttk.Radiobutton(end_frame, text=_("academic_calendar.labels.end_by_date"), variable=self.end_type_var,
                       value="date", command=self._toggle_end_fields).pack(anchor=tk.W)

        self.end_date_var = tk.StringVar()
        self.end_date_entry = ttk.Entry(end_frame, textvariable=self.end_date_var, width=20)
        self.end_date_entry.pack(anchor=tk.W, padx=(20, 0), pady=(5, 10))

        ttk.Radiobutton(end_frame, text=_("academic_calendar.labels.end_after_occurrences"), variable=self.end_type_var,
                       value="count", command=self._toggle_end_fields).pack(anchor=tk.W)

        self.count_var = tk.StringVar(value="10")
        self.count_entry = ttk.Entry(end_frame, textvariable=self.count_var, width=10)
        self.count_entry.pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.create_recurring_event"), command=self._create_recurring_event).pack(side=tk.RIGHT)

        # Initialize field states
        self._toggle_end_fields()

    def _toggle_end_fields(self):
        """Toggle end condition fields based on selection"""
        if self.end_type_var.get() == "date":
            self.end_date_entry.config(state="normal")
            self.count_entry.config(state="disabled")
        else:
            self.end_date_entry.config(state="disabled")
            self.count_entry.config(state="normal")

    def _create_recurring_event(self):
        """Create the recurring event"""
        try:
            # Validate required fields
            name = self.name_var.get().strip()
            date = self.date_var.get().strip()

            if not name or not date:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.event_name_date_required"))
                return

            # Build base event data
            base_event = {
                'name': name,
                'date': date,
                'description': self.description_text.get(1.0, tk.END).strip(),
                'event_type': self.type_var.get()
            }

            # Build recurrence pattern
            pattern = {
                'frequency': self.frequency_var.get(),
                'interval': int(self.interval_var.get()) if self.interval_var.get().strip() else 1
            }

            if self.end_type_var.get() == "date":
                end_date = self.end_date_var.get().strip()
                if end_date:
                    pattern['end_date'] = end_date
            else:
                count = self.count_var.get().strip()
                if count:
                    pattern['occurrence_count'] = min(int(count), 100)  # Limit for safety

            # Create recurring event
            success, message = self.calendar_manager.recurring_events.create_recurring_event(base_event, pattern)

            if success:
                messagebox.showinfo(_("common.success"), message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message)

        except ValueError as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.invalid_numeric_values"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_create_recurring", error=str(e)))

    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class RecurringEventsDialog:
    """Dialog for managing recurring events with full functionality"""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        self.parent = parent

        # Check dateutil availability
        self.dateutil_available = False
        try:
            from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
            self.dateutil_available = True
        except ImportError:
            pass

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.recurring_events.management_title"))
        self.dialog.geometry("900x700")
        self.dialog.minsize(700, 500)
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._load_recurring_events()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.recurring_events.management_header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Status indicator
        status_text = "dateutil available" if self.dateutil_available else "dateutil not installed - install with: pip install python-dateutil"
        status_color = "green" if self.dateutil_available else "orange"
        ttk.Label(main_frame, text=status_text, foreground=status_color).pack(pady=(0, 15))

        # Create paned window
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel - existing recurring events
        left_frame = ttk.LabelFrame(paned, text=_("academic_calendar.dialogs.recurring_events.existing_events"), padding=10)
        paned.add(left_frame, weight=1)

        # Treeview container with scrollbars
        tree_container = ttk.Frame(left_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.events_tree = ttk.Treeview(tree_container,
                                       columns=('Pattern', 'Start', 'End', 'Occurrences'),
                                       show='tree headings',
                                       height=15)

        self.events_tree.heading('#0', text='Event Name')
        self.events_tree.heading('Pattern', text='Pattern')
        self.events_tree.heading('Start', text='Start Date')
        self.events_tree.heading('End', text='End Date')
        self.events_tree.heading('Occurrences', text='Count')

        self.events_tree.column('#0', width=150, minwidth=100)
        self.events_tree.column('Pattern', width=80, minwidth=60)
        self.events_tree.column('Start', width=90, minwidth=70)
        self.events_tree.column('End', width=90, minwidth=70)
        self.events_tree.column('Occurrences', width=60, minwidth=50)

        v_scroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.events_tree.yview)
        h_scroll = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.events_tree.xview)
        self.events_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.events_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # Action buttons for existing events
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text=_("academic_calendar.buttons.view_details"), command=self._view_details).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_("academic_calendar.buttons.delete"), command=self._delete_recurring).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_("academic_calendar.buttons.refresh"), command=self._load_recurring_events).pack(side=tk.LEFT, padx=2)

        # Right panel - create new recurring event
        right_frame = ttk.LabelFrame(paned, text=_("academic_calendar.buttons.create_new_recurring_event"), padding=10)
        paned.add(right_frame, weight=1)

        # Scrollable form
        form_canvas = tk.Canvas(right_frame, highlightthickness=0)
        form_scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=form_canvas.yview)
        form_frame = ttk.Frame(form_canvas)

        form_frame.bind("<Configure>", lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))
        form_canvas.create_window((0, 0), window=form_frame, anchor='nw')
        form_canvas.configure(yscrollcommand=form_scrollbar.set)

        form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        form_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Form fields
        ttk.Label(form_frame, text=_("academic_calendar.labels.event_name_required")).pack(anchor=tk.W, pady=(5, 0))
        self.name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.name_var, width=35).pack(fill=tk.X, pady=(2, 10))

        ttk.Label(form_frame, text=_("academic_calendar.labels.description")).pack(anchor=tk.W)
        self.desc_text = scrolledtext.ScrolledText(form_frame, height=3, width=35)
        self.desc_text.pack(fill=tk.X, pady=(2, 10))

        ttk.Label(form_frame, text=_("academic_calendar.labels.event_type")).pack(anchor=tk.W)
        self.type_var = tk.StringVar(value="Academic")
        ttk.Combobox(form_frame, textvariable=self.type_var, width=33,
                    values=["Academic", "Holiday", "Administrative", "Social", "Sports"]).pack(fill=tk.X, pady=(2, 10))

        ttk.Label(form_frame, text=_("academic_calendar.labels.start_date_format_required")).pack(anchor=tk.W)
        self.start_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(form_frame, textvariable=self.start_var, width=35).pack(fill=tk.X, pady=(2, 10))

        ttk.Label(form_frame, text=_("academic_calendar.labels.recurrence_pattern_required")).pack(anchor=tk.W)
        self.pattern_var = tk.StringVar(value="weekly")
        pattern_frame = ttk.Frame(form_frame)
        pattern_frame.pack(fill=tk.X, pady=(2, 10))
        for pattern in ["daily", "weekly", "monthly", "yearly"]:
            ttk.Radiobutton(pattern_frame, text=pattern.capitalize(), variable=self.pattern_var,
                           value=pattern).pack(side=tk.LEFT, padx=5)

        ttk.Label(form_frame, text=_("academic_calendar.labels.repeat_every")).pack(anchor=tk.W)
        self.interval_var = tk.StringVar(value="1")
        ttk.Entry(form_frame, textvariable=self.interval_var, width=10).pack(anchor=tk.W, pady=(2, 10))

        ttk.Label(form_frame, text=_("academic_calendar.labels.end_condition")).pack(anchor=tk.W, pady=(10, 0))
        self.end_type_var = tk.StringVar(value="count")

        end_frame = ttk.Frame(form_frame)
        end_frame.pack(fill=tk.X, pady=(2, 5))
        ttk.Radiobutton(end_frame, text=_("academic_calendar.labels.after"), variable=self.end_type_var, value="count").pack(side=tk.LEFT)
        self.count_var = tk.StringVar(value="10")
        ttk.Entry(end_frame, textvariable=self.count_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(end_frame, text=_("academic_calendar.labels.occurrences")).pack(side=tk.LEFT)

        end_frame2 = ttk.Frame(form_frame)
        end_frame2.pack(fill=tk.X, pady=(2, 10))
        ttk.Radiobutton(end_frame2, text=_("academic_calendar.labels.until_date"), variable=self.end_type_var, value="date").pack(side=tk.LEFT)
        self.end_date_var = tk.StringVar()
        ttk.Entry(end_frame2, textvariable=self.end_date_var, width=15).pack(side=tk.LEFT, padx=5)

        # Preview and create buttons
        btn_frame2 = ttk.Frame(form_frame)
        btn_frame2.pack(fill=tk.X, pady=(20, 10))
        ttk.Button(btn_frame2, text=_("academic_calendar.buttons.preview"), command=self._preview_recurring).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame2, text=_("academic_calendar.buttons.create_events"), command=self._create_recurring).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(15, 0))

    def _load_recurring_events(self):
        """Load existing recurring events"""
        for item in self.events_tree.get_children():
            self.events_tree.delete(item)

        try:
            # Try to get recurring events from database
            events = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM academic_calendar_events WHERE is_recurring = 1 OR recurrence_pattern IS NOT NULL ORDER BY date DESC"
            )

            for event in events:
                pattern = event.get('recurrence_pattern', 'N/A')
                start = event.get('date') or event.get('date_start', '')
                end = event.get('recurrence_end_date', '')
                count = event.get('occurrence_count', '')

                self.events_tree.insert('', 'end',
                                       text=event.get('name', 'Unknown'),
                                       values=(pattern, start, end, count),
                                       tags=(event.get('id', ''),))
        except Exception as e:
            gui_logger.warning(f"Failed to load recurring events: {e}")

    def _view_details(self):
        """View details of selected recurring event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning(_("academic_calendar.messages.no_selection"), _("academic_calendar.messages.select_event_to_view_details"), parent=self.dialog)
            return

        item = selection[0]
        event_name = self.events_tree.item(item, 'text')
        values = self.events_tree.item(item, 'values')

        details = f"Event: {event_name}\n"
        details += f"Pattern: {values[0]}\n"
        details += f"Start Date: {values[1]}\n"
        details += f"End Date: {values[2]}\n"
        details += f"Occurrences: {values[3]}"

        messagebox.showinfo(_("academic_calendar.dialogs.event_details.title"), details, parent=self.dialog)

    def _delete_recurring(self):
        """Delete selected recurring event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning(_("academic_calendar.messages.no_selection"), _("academic_calendar.messages.select_event_to_delete_recurring"), parent=self.dialog)
            return

        if messagebox.askyesno(_("academic_calendar.messages.confirm_delete"), _("academic_calendar.messages.confirm_delete_recurring"), parent=self.dialog):
            try:
                item = selection[0]
                event_id = self.events_tree.item(item, 'tags')[0] if self.events_tree.item(item, 'tags') else None

                if event_id:
                    self.calendar_manager.db_manager.execute_query(
                        "DELETE FROM academic_calendar_events WHERE id = ? OR parent_event_id = ?", (event_id, event_id)
                    )

                self._load_recurring_events()
                messagebox.showinfo(_("common.success"), _("academic_calendar.messages.recurring_deleted"), parent=self.dialog)

                if self.callback:
                    self.callback()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_delete_recurring", error=str(e)), parent=self.dialog)

    def _preview_recurring(self):
        """Preview recurring event occurrences"""
        if not self._validate_form():
            return

        try:
            occurrences = self._generate_occurrences()

            preview_text = f"PREVIEW: {len(occurrences)} occurrences\n" + "="*40 + "\n\n"
            for i, date in enumerate(occurrences[:20], 1):
                preview_text += f"{i}. {date}\n"

            if len(occurrences) > 20:
                preview_text += f"\n... and {len(occurrences) - 20} more"

            messagebox.showinfo(_("academic_calendar.buttons.preview"), preview_text, parent=self.dialog)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_preview", error=str(e)), parent=self.dialog)

    def _create_recurring(self):
        """Create recurring events"""
        if not self._validate_form():
            return

        if not self.dateutil_available:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.dateutil_required"), parent=self.dialog)
            return

        try:
            occurrences = self._generate_occurrences()

            if messagebox.askyesno(_("academic_calendar.messages.confirm"), _("academic_calendar.messages.confirm_create_events", count=len(occurrences)), parent=self.dialog):
                event_data = {
                    'name': self.name_var.get().strip(),
                    'description': self.desc_text.get('1.0', tk.END).strip(),
                    'event_type': self.type_var.get(),
                    'is_recurring': True,
                    'recurrence_pattern': self.pattern_var.get()
                }

                created = 0
                for date in occurrences:
                    event_data['date'] = date
                    result = self.calendar_manager.create_event(event_data)
                    if result.get('success'):
                        created += 1

                messagebox.showinfo(_("common.success"), _("academic_calendar.messages.events_created", count=created), parent=self.dialog)
                self._load_recurring_events()

                if self.callback:
                    self.callback()
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_create_events", error=str(e)), parent=self.dialog)

    def _validate_form(self):
        """Validate form inputs"""
        if not self.name_var.get().strip():
            messagebox.showerror(_("academic_calendar.messages.validation_error"), _("academic_calendar.messages.event_name_required"), parent=self.dialog)
            return False
        if not self.start_var.get().strip():
            messagebox.showerror(_("academic_calendar.messages.validation_error"), _("academic_calendar.messages.start_date_required"), parent=self.dialog)
            return False
        return True

    def _generate_occurrences(self):
        """Generate occurrence dates"""
        start_date = datetime.strptime(self.start_var.get().strip(), "%Y-%m-%d")
        pattern = self.pattern_var.get()
        interval = int(self.interval_var.get() or 1)

        occurrences = []

        if self.end_type_var.get() == "count":
            count = int(self.count_var.get() or 10)
            for i in range(count):
                if pattern == "daily":
                    occurrences.append((start_date + timedelta(days=i*interval)).strftime("%Y-%m-%d"))
                elif pattern == "weekly":
                    occurrences.append((start_date + timedelta(weeks=i*interval)).strftime("%Y-%m-%d"))
                elif pattern == "monthly":
                    occurrences.append((start_date + timedelta(days=i*30*interval)).strftime("%Y-%m-%d"))
                elif pattern == "yearly":
                    occurrences.append((start_date + timedelta(days=i*365*interval)).strftime("%Y-%m-%d"))
        else:
            end_date = datetime.strptime(self.end_date_var.get().strip(), "%Y-%m-%d")
            current = start_date
            while current <= end_date:
                occurrences.append(current.strftime("%Y-%m-%d"))
                if pattern == "daily":
                    current += timedelta(days=interval)
                elif pattern == "weekly":
                    current += timedelta(weeks=interval)
                elif pattern == "monthly":
                    current += timedelta(days=30*interval)
                elif pattern == "yearly":
                    current += timedelta(days=365*interval)

        return occurrences

    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


