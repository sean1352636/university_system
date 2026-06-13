import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import json
from typing import Any, Optional, List, Dict
from education_system.university_system.core.i18n import get_text as _

gui_logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependency
def _get_edit_event_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_event import EditEventDialog
    return EditEventDialog

def _get_event_details_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_event import EventDetailsDialog
    return EventDetailsDialog

class EventsViewMixin:
    def _show_manage_events(self):
        """Show event management view"""
        self._clear_content_area()
        self.current_view = "manage_events"

        # Header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(header_frame, text=_("academic_calendar.manage_events.title"), style='Header.TLabel').pack(side=tk.LEFT)

        # Action buttons
        action_frame = ttk.Frame(header_frame)
        action_frame.pack(side=tk.RIGHT)

        ttk.Button(action_frame, text=_("academic_calendar.buttons.add_event"),
                  command=self._show_add_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_("academic_calendar.buttons.refresh"),
                  command=self._refresh_manage_events).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_("academic_calendar.buttons.open_chat",
                                        default="Open chat"),
                  command=self._open_event_chat).pack(side=tk.LEFT, padx=5)

        # Search frame
        search_frame = ttk.Frame(self.content_area)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        ttk.Label(search_frame, text=_("academic_calendar.labels.search")).pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        search_entry.bind('<KeyRelease>', lambda e: self._search_events())

        ttk.Button(search_frame, text=_("academic_calendar.buttons.search"),
                  command=self._search_events).pack(side=tk.LEFT, padx=5)

        # Events list
        events_frame = ttk.Frame(self.content_area)
        events_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self._create_events_treeview(events_frame)
        self._load_events_data()

    def _create_events_treeview(self, parent):
        """Create treeview for events management with proper scrollbar layout"""
        # Create container frame for proper scrollbar positioning
        tree_container = ttk.Frame(parent)
        tree_container.pack(fill=tk.BOTH, expand=True)

        # Treeview with more height for better visibility
        self.events_tree = ttk.Treeview(tree_container,
                                      columns=('ID', 'Date', 'End Date', 'Type', 'Description', 'full_data'),
                                      show='tree headings',
                                      height=20)

        # Configure columns with better widths
        self.events_tree.heading('#0', text=_("academic_calendar.columns.event_name"))
        self.events_tree.heading('ID', text=_("academic_calendar.columns.id"))
        self.events_tree.heading('Date', text=_("academic_calendar.columns.start_date"))
        self.events_tree.heading('End Date', text=_("academic_calendar.columns.end_date"))
        self.events_tree.heading('Type', text=_("academic_calendar.columns.type"))
        self.events_tree.heading('Description', text=_("academic_calendar.columns.description"))
        self.events_tree.heading('full_data', text='')  # Hidden column

        self.events_tree.column('#0', width=220, minwidth=150)
        self.events_tree.column('ID', width=90, minwidth=70)
        self.events_tree.column('Date', width=110, minwidth=90)
        self.events_tree.column('End Date', width=110, minwidth=90)
        self.events_tree.column('Type', width=130, minwidth=100)
        self.events_tree.column('Description', width=350, minwidth=200)
        self.events_tree.column('full_data', width=0, minwidth=0, stretch=False)  # Hide this column

        # Vertical scrollbar
        v_scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.events_tree.yview)
        # Horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.events_tree.xview)

        self.events_tree.configure(yscrollcommand=v_scrollbar.set,
                                 xscrollcommand=h_scrollbar.set)

        # Use grid layout for proper scrollbar positioning
        self.events_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        # Configure grid weights
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # Context menu
        self._create_events_context_menu()

        # Double-click to edit
        self.events_tree.bind('<Double-1>', lambda e: self._edit_selected_event())

    def _create_events_context_menu(self):
        """Create context menu for events management.

        The static items (edit / delete / copy id / details / email
        reminder) stay as-is. On every right-click we *also* build the
        cross-module jumps fresh from the selected row's ``full_data``
        — see :mod:`._cross_links`. Rebuilding per-click is the same
        pattern the library uses in
        ``library/_cross_links.attach_cross_link_menu`` and lets us
        omit items that don't apply to the row (e.g. no course jump
        when no module code can be extracted)."""
        self.events_context_menu = tk.Menu(self.root, tearoff=0)
        self.events_context_menu.add_command(label=_("academic_calendar.context_menu.edit_event"), command=self._edit_selected_event)
        self.events_context_menu.add_command(label=_("academic_calendar.context_menu.delete_event"), command=self._delete_selected_event)
        self.events_context_menu.add_separator()
        self.events_context_menu.add_command(label=_("academic_calendar.context_menu.copy_id"), command=self._copy_event_id)
        self.events_context_menu.add_command(label=_("academic_calendar.context_menu.view_details"), command=self._view_event_details)
        self.events_context_menu.add_separator()
        self.events_context_menu.add_command(label=_("academic_calendar.context_menu.send_email_reminder"), command=self._send_email_reminder)

        def show_context_menu(event):
            try:
                # Highlight whichever row is under the cursor so the
                # cross-link items pull the right event dict.
                row = self.events_tree.identify_row(event.y)
                if row:
                    self.events_tree.selection_set(row)

                # Build a fresh menu per click. The static items get
                # cloned across; cross-link items are appended on top.
                menu = tk.Menu(self.root, tearoff=0)
                menu.add_command(label=_("academic_calendar.context_menu.edit_event"), command=self._edit_selected_event)
                menu.add_command(label=_("academic_calendar.context_menu.delete_event"), command=self._delete_selected_event)
                menu.add_separator()
                menu.add_command(label=_("academic_calendar.context_menu.copy_id"), command=self._copy_event_id)
                menu.add_command(label=_("academic_calendar.context_menu.view_details"), command=self._view_event_details)
                menu.add_separator()
                menu.add_command(label=_("academic_calendar.context_menu.send_email_reminder"), command=self._send_email_reminder)

                # Cross-links — pull the selected row's full event dict
                # and let _cross_links.event_menu_items build the
                # row-aware portion.
                try:
                    from education_system.university_system.modules.domain.academics.gui.academic_calendar._cross_links import (
                        event_menu_items as _x_items,
                        append_to_menu as _x_append,
                    )
                    event_data = self._get_selected_event_data()
                    if event_data:
                        _x_append(menu, _x_items(event_data, parent=self.root))
                except Exception:
                    gui_logger.debug(
                        "calendar cross-links unavailable; static menu only",
                        exc_info=True)

                try:
                    menu.tk_popup(event.x_root, event.y_root)
                finally:
                    menu.grab_release()
            except Exception:
                gui_logger.exception("show_context_menu failed")

        self.events_tree.bind("<Button-3>", show_context_menu)

    def _get_selected_event_data(self):
        """Return the full event dict for the currently-selected events
        tree row, parsed from the hidden ``full_data`` column. Returns
        ``None`` if no row is selected or the JSON can't be parsed."""
        try:
            sel = self.events_tree.selection()
            if not sel:
                return None
            raw = self.events_tree.set(sel[0], "full_data")
            if not raw:
                return None
            import json
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError, AttributeError):
            return None
        except Exception:
            gui_logger.debug("_get_selected_event_data failed",
                             exc_info=True)
            return None

    def _load_events_data(self):
        """Load events data into treeview"""
        try:
            if not self.calendar_manager:
                return

            # Clear existing data
            for item in self.events_tree.get_children():
                self.events_tree.delete(item)

            # Get all events (recent first)
            current_date = datetime.now().strftime("%Y-%m-%d")
            past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

            events = self.calendar_manager.get_events_by_date_range(past_date, future_date)

            # Load and integrate trip data
            trip_events = self._get_trip_events(past_date, future_date)
            events.extend(trip_events)

            # Load and integrate assignment due dates
            assignment_events = self._get_assignment_events(past_date, future_date)
            events.extend(assignment_events)

            # Load and integrate finance payment due dates
            finance_events = self._get_finance_events(past_date, future_date)
            events.extend(finance_events)

            # Load and integrate library return due dates
            library_events = self._get_library_events(past_date, future_date)
            events.extend(library_events)

            # Sort by date (most recent first)
            events.sort(key=lambda x: x.get('date') or x.get('date_start') or '', reverse=True)

            # Add to treeview
            for event in events:
                event_date = event.get('date') or event.get('date_start', '')
                end_date = event.get('date_end', '')
                event_type = event.get('event_type', '')
                description = (event.get('description', '') or '')[:100]
                event_id = event['id'][:8] + "..." if len(event['id']) > 8 else event['id']

                # Add event type icon
                type_icons = {
                    'Academic': '📚',
                    'Holiday': '🎉',
                    'Administrative': '📋',
                    'Trip': '🎒',
                    'Deadline': '⏰',
                    'Social': '🎊',
                    'Sports': '⚽',
                    'Finance': '💰',
                    'Payment': '💳',
                    'Library': '📖'
                }
                icon = type_icons.get(event_type, '📅')

                item_id = self.events_tree.insert('', 'end',
                                                 text=f"{icon} {event['name']}",
                                                 values=(event_id, event_date, end_date,
                                                        event_type, description))

                # Store full event data as JSON
                import json
                self.events_tree.set(item_id, 'full_data', json.dumps(dict(event) if hasattr(event, 'keys') else event))

            self._update_status(_("academic_calendar.messages.loaded_events").format(count=len(events)), "success")

        except Exception as e:
            gui_logger.error(f"Failed to load events: {e}")
            self._show_error(_("academic_calendar.messages.failed_to_load_events").format(error=e))

    def _get_trip_events(self, start_date, end_date):
        """Get trip events from trip management system"""
        trip_events = []
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT trip_name, start_date, end_date, description, id
                    FROM trips
                    WHERE (start_date BETWEEN ? AND ?) OR (end_date BETWEEN ? AND ?)
                    OR (start_date <= ? AND end_date >= ?)
                    ORDER BY start_date
                ''', (start_date, end_date, start_date, end_date, start_date, end_date))

                for trip in cursor.fetchall():
                    trip_events.append({
                        'id': f'trip_{trip[4]}',
                        'name': f"🎒 {trip[0]}",
                        'date': trip[1],
                        'date_start': trip[1],
                        'date_end': trip[2],
                        'event_type': 'Trip',
                        'description': f"Trip: {trip[3] or 'No description'}",
                        'source': 'trip_management'
                    })
        except Exception as e:
            gui_logger.warning(f"Failed to load trip events: {e}")

        return trip_events

    def _get_assignment_events(self, start_date, end_date):
        """Get assignment due dates from assignment system"""
        assignment_events = []
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT title, due_date, module_code, description, id
                    FROM assignments
                    WHERE due_date BETWEEN ? AND ? AND is_active = 1
                    ORDER BY due_date
                ''', (start_date, end_date))

                for assignment in cursor.fetchall():
                    assignment_events.append({
                        'id': f'assignment_{assignment[4]}',
                        'name': f"📝 {assignment[0]}",
                        'date': assignment[1],
                        'date_start': assignment[1],
                        'date_end': assignment[1],
                        'event_type': 'Deadline',
                        'description': f"Assignment due ({assignment[2]}): {assignment[3] or 'No description'}",
                        'source': 'assignments'
                    })
        except Exception as e:
            gui_logger.warning(f"Failed to load assignment events: {e}")

        return assignment_events

    def _get_finance_events(self, start_date, end_date):
        """Get finance payment due dates from finance system"""
        finance_events = []
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Get payment due dates for student fees
                cursor.execute('''
                    SELECT ft.fee_name, f.due_date, f.amount, s.first_name, s.last_name, f.student_fee_id
                    FROM student_fees f
                    JOIN students s ON f.student_id = s.student_id
                    LEFT JOIN fee_types ft ON f.fee_type_id = ft.fee_type_id
                    WHERE f.due_date BETWEEN ? AND ? AND f.status != 'paid'
                    ORDER BY f.due_date
                ''', (start_date, end_date))

                for fee in cursor.fetchall():
                    fee_name = fee[0] if fee[0] else 'Fee'
                    finance_events.append({
                        'id': f'fee_{fee[5]}',
                        'name': f"💳 {fee_name} Due",
                        'date': fee[1],
                        'date_start': fee[1],
                        'date_end': fee[1],
                        'event_type': 'Payment',
                        'description': f"Payment due: {fee_name} - £{fee[2]:.2f} ({fee[3]} {fee[4]})",
                        'source': 'finance'
                    })

                # Get scholarship deadlines (using correct schema)
                try:
                    cursor.execute('''
                        SELECT sch.scholarship_name, sch.deadline, sch.amount, sch.scholarship_id
                        FROM scholarships sch
                        WHERE sch.deadline BETWEEN ? AND ? AND sch.is_active = 1
                        ORDER BY sch.deadline
                    ''', (start_date, end_date))

                    for scholarship in cursor.fetchall():
                        finance_events.append({
                            'id': f'scholarship_{scholarship[3]}',
                            'name': f"💰 {scholarship[0]} Deadline",
                            'date': scholarship[1],
                            'date_start': scholarship[1],
                            'date_end': scholarship[1],
                            'event_type': 'Finance',
                            'description': f"Scholarship deadline: {scholarship[0]} - £{scholarship[2]:.2f}",
                            'source': 'finance'
                        })
                except Exception as e:
                    gui_logger.debug(f"Could not load scholarship events: {e}")

                # Get financial aid application deadlines
                try:
                    cursor.execute('''
                        SELECT fat.aid_name, fat.application_deadline, fat.max_amount, fat.aid_type_id
                        FROM financial_aid_types fat
                        WHERE fat.application_deadline BETWEEN ? AND ?
                          AND fat.is_active = 1
                        ORDER BY fat.application_deadline
                    ''', (start_date, end_date))

                    for aid_type in cursor.fetchall():
                        finance_events.append({
                            'id': f'aid_deadline_{aid_type[3]}',
                            'name': f"📝 {aid_type[0]} Deadline",
                            'date': aid_type[1],
                            'date_start': aid_type[1],
                            'date_end': aid_type[1],
                            'event_type': 'Finance',
                            'description': f"Financial aid application deadline: {aid_type[0]} - Max £{aid_type[2]:.2f}",
                            'source': 'finance'
                        })
                except Exception as e:
                    gui_logger.debug(f"Could not load financial aid deadlines: {e}")

                # Get student financial aid approval/disbursement dates
                try:
                    cursor.execute('''
                        SELECT sfa.aid_id, fat.aid_name, sfa.approval_date, sfa.awarded_amount,
                               s.first_name, s.last_name, sfa.status
                        FROM student_financial_aid sfa
                        JOIN students s ON sfa.student_id = s.student_id
                        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                        WHERE sfa.approval_date BETWEEN ? AND ?
                          AND sfa.status IN ('approved', 'disbursed', 'completed')
                        ORDER BY sfa.approval_date
                    ''', (start_date, end_date))

                    for aid in cursor.fetchall():
                        finance_events.append({
                            'id': f'aid_approval_{aid[0]}',
                            'name': f"✅ {aid[1]} Approved",
                            'date': aid[2],
                            'date_start': aid[2],
                            'date_end': aid[2],
                            'event_type': 'Finance',
                            'description': f"{aid[1]} approved for {aid[4]} {aid[5]} - £{aid[3]:.2f} (Status: {aid[6]})",
                            'source': 'finance'
                        })
                except Exception as e:
                    gui_logger.debug(f"Could not load student financial aid: {e}")

        except Exception as e:
            gui_logger.warning(f"Failed to load finance events: {e}")

        return finance_events

    def _get_library_events(self, start_date, end_date):
        """Get library book return due dates from library system"""
        library_events = []
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Get book return due dates
                cursor.execute('''
                    SELECT bl.book_id, bl.user_id, bl.due_date,
                           b.title, b.author,
                           s.first_name, s.last_name, bl.loan_id
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    JOIN students s ON bl.user_id = s.student_id
                    WHERE bl.due_date BETWEEN ? AND ? AND bl.status = 'active'
                    ORDER BY bl.due_date
                ''', (start_date, end_date))

                for loan in cursor.fetchall():
                    book_id, user_id, due_date, title, author, first_name, last_name, loan_id = loan
                    library_events.append({
                        'id': f'library_{loan_id}',
                        'name': f"📖 {title} Return Due",
                        'date': due_date,
                        'date_start': due_date,
                        'date_end': due_date,
                        'event_type': 'Library',
                        'description': f"Book return due: {title} by {author} (borrowed by {first_name} {last_name})",
                        'source': 'library'
                    })

        except Exception as e:
            gui_logger.warning(f"Failed to load library events: {e}")

        return library_events

    def _edit_selected_event(self):
        """Edit selected event"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []
        if not selection:
            selection = self.calendar_tree.selection() if hasattr(self, 'calendar_tree') else []

        if selection:
            item = selection[0]
            # Get event data from the item
            if hasattr(self, 'events_tree') and self.events_tree.exists(item):
                event_data_json = self.events_tree.set(item, 'full_data')
                if event_data_json:
                    try:
                        import json
                        event_data = json.loads(event_data_json)
                        _get_edit_event_dialog()(self.root, self.calendar_manager, event_data,
                                      self._refresh_current_view)
                        return
                    except (json.JSONDecodeError, TypeError) as e:
                        # If parsing fails, treat as string (fallback)
                        gui_logger.debug(f"Event data not in expected JSON format, using fallback: {e}")

            # Fallback: get event by name
            event_name = self.events_tree.item(item, 'text') if hasattr(self, 'events_tree') else \
                        self.calendar_tree.item(item, 'text')
            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])

            try:
                events = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM academic_calendar_events WHERE name = ? LIMIT 1", (event_name,)
                )
                if events:
                    _get_edit_event_dialog()(self.root, self.calendar_manager, dict(events[0]),
                                  self._refresh_current_view)
                else:
                    self._show_error(_("academic_calendar.messages.event_not_found"))
            except Exception as e:
                self._show_error(_("academic_calendar.messages.failed_to_load_event").format(error=e))
        else:
            self._show_warning(_("academic_calendar.messages.select_event_to_edit"))

    def _delete_selected_event(self):
        """Delete selected event"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []
        if not selection:
            selection = self.calendar_tree.selection() if hasattr(self, 'calendar_tree') else []

        if selection:
            item = selection[0]
            event_name = self.events_tree.item(item, 'text') if hasattr(self, 'events_tree') else \
                        self.calendar_tree.item(item, 'text')

            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])

            if messagebox.askyesno(_("academic_calendar.messages.confirm_delete"),
                                 _("academic_calendar.messages.confirm_delete_event").format(name=event_name)):
                try:
                    # Get event ID
                    events = self.calendar_manager.db_manager.execute_query(
                        "SELECT id FROM academic_calendar_events WHERE name = ? LIMIT 1", (event_name,)
                    )
                    if events:
                        result = self.calendar_manager.delete_event(events[0]['id'])
                        if result['success']:
                            self._show_success(result['message'])
                            self._refresh_current_view()
                        else:
                            self._show_error(result['message'])
                    else:
                        self._show_error(_("academic_calendar.messages.event_not_found"))
                except Exception as e:
                    self._show_error(_("academic_calendar.messages.failed_to_delete_event").format(error=e))
        else:
            self._show_warning(_("academic_calendar.messages.select_event_to_delete"))

    def _view_event_details(self):
        """View event details"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []
        if not selection:
            selection = self.calendar_tree.selection() if hasattr(self, 'calendar_tree') else []

        if selection:
            item = selection[0]
            event_name = self.events_tree.item(item, 'text') if hasattr(self, 'events_tree') else \
                        self.calendar_tree.item(item, 'text')

            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])

            try:
                events = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM academic_calendar_events WHERE name = ? LIMIT 1", (event_name,)
                )
                if events:
                    _get_event_details_dialog()(self.root, dict(events[0]))
                else:
                    self._show_error(_("academic_calendar.messages.event_not_found"))
            except Exception as e:
                self._show_error(_("academic_calendar.messages.failed_to_load_event_details").format(error=e))
        else:
            self._show_warning(_("academic_calendar.messages.select_event_to_view"))

    def _copy_event_id(self):
        """Copy event ID to clipboard"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []

        if selection:
            item = selection[0]
            event_name = self.events_tree.item(item, 'text')

            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])

            try:
                events = self.calendar_manager.db_manager.execute_query(
                    "SELECT id FROM academic_calendar_events WHERE name = ? LIMIT 1", (event_name,)
                )
                if events:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(events[0]['id'])
                    self._update_status(_("academic_calendar.messages.event_id_copied_success"), "success")
                else:
                    self._show_error(_("academic_calendar.messages.event_not_found"))
            except Exception as e:
                self._show_error(_("academic_calendar.messages.failed_to_copy_id").format(error=e))

    def _send_email_reminder(self):
        """Send email reminder for selected calendar event"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []
        if not selection:
            selection = self.calendar_tree.selection() if hasattr(self, 'calendar_tree') else []

        if not selection:
            safe_show_warning(_("academic_calendar.messages.no_selection"), _("academic_calendar.messages.select_event_for_reminder"), self.root)
            return

        try:
            item = selection[0]
            # Get event details
            if hasattr(self, 'events_tree') and self.events_tree.exists(item):
                event_name = self.events_tree.item(item, 'text')
                values = self.events_tree.item(item, 'values')
                event_date = values[1] if len(values) > 1 else 'Unknown'
                event_type = values[3] if len(values) > 3 else 'Event'
                description = values[4] if len(values) > 4 else ''
            else:
                event_name = self.calendar_tree.item(item, 'text')
                values = self.calendar_tree.item(item, 'values')
                event_date = values[0] if len(values) > 0 else 'Unknown'
                event_type = values[2] if len(values) > 2 else 'Event'
                description = values[3] if len(values) > 3 else ''

            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])

            # Launch email GUI with pre-filled reminder
            self._launch_email_reminder_dialog(event_name, event_date, event_type, description)

        except Exception as e:
            self._show_error(_("academic_calendar.messages.failed_to_prepare_reminder").format(error=e))

    def _launch_email_reminder_dialog(self, event_name, event_date, event_type, description):
        """Launch email dialog for calendar reminder"""
        try:
            # Try to import and use the email manager GUI
            from education_system.university_system.modules.shared.gui.email.email_manager_gui import EmailManagerGUI

            # Create email dialog
            email_dialog = tk.Toplevel(self.root)
            email_dialog.title(_("academic_calendar.dialogs.send_reminder.title"))
            email_dialog.geometry("600x500")
            email_dialog.transient(self.root)

            # Create email manager instance
            email_manager = EmailManagerGUI(parent=email_dialog)

            # Pre-fill email with calendar event details using template system
            from education_system.university_system.infrastructure.email.template_utils import render_template

            try:
                subject, message = render_template("calendar_event_reminder", {
                    "event_name": event_name,
                    "event_date": event_date,
                    "event_type": event_type,
                    "description": description if description else 'No additional details provided.',
                    "recipient_name": "Students/Staff"
                })

            except Exception as e:
                # Error handling for template rendering
                gui_logger.warning(f"Failed to render email template: {e}")
                subject = None
                message = None

            # Set the email content if the email manager supports it
            if subject and message and hasattr(email_manager, 'set_email_content'):
                email_manager.set_email_content(subject, message)

        except ImportError:
            # Fallback to simple dialog if email GUI not available
            self._show_simple_email_dialog(event_name, event_date, event_type, description)
        except Exception as e:
            self._show_error(f"Failed to launch email dialog: {e}")

    def _show_simple_email_dialog(self, event_name, event_date, event_type, description):
        """Show simple email dialog as fallback"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("academic_calendar.dialogs.send_reminder.title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.send_reminder.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Event details
        details_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.send_reminder.event_details"), padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(details_frame, text=f"Event: {event_name}").pack(anchor='w')
        ttk.Label(details_frame, text=f"Date: {event_date}").pack(anchor='w')
        ttk.Label(details_frame, text=f"Type: {event_type}").pack(anchor='w')

        if description:
            ttk.Label(details_frame, text=f"Description: {description}").pack(anchor='w')

        # Email template
        template_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.send_reminder.email_template"), padding=10)
        template_frame.pack(fill=tk.BOTH, expand=True)

        email_text = scrolledtext.ScrolledText(template_frame, wrap=tk.WORD, height=10)
        email_text.pack(fill=tk.BOTH, expand=True)

        # Generate email content using template system
        try:
            from education_system.university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template("calendar_event_reminder", {
                "event_name": event_name,
                "event_date": event_date,
                "event_type": event_type,
                "description": description if description else 'No additional details provided.',
                "recipient_name": "Students/Staff"
            })
            email_content = f"Subject: {subject}\n\n{body}"
        except Exception as template_error:
            gui_logger.warning(f"Failed to render email template: {template_error}. Using fallback.")
            # Fallback to hardcoded template if template system fails
            email_content = f"""Subject: Reminder: {event_name} - {event_date}

Dear Students/Staff,

This is a reminder about an upcoming {event_type.lower()}:

Event: {event_name}
Date: {event_date}
Type: {event_type}

{description if description else 'No additional details provided.'}

Please mark your calendar and prepare accordingly.

Best regards,
Academic Calendar System"""

        email_text.insert(tk.END, email_content)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("academic_calendar.dialogs.send_reminder.copy_to_clipboard"),
                  command=lambda: self._copy_to_clipboard(email_content)).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text=_("common.close"), command=dialog.destroy).pack(side=tk.RIGHT)

    def _refresh_manage_events(self):
        """Refresh events management"""
        self._load_events_data()

    def _open_event_chat(self):
        """Open (or create) the chat room linked to the selected event."""
        sel = self.events_tree.selection() if hasattr(self, 'events_tree') else ()
        if not sel:
            from tkinter import messagebox
            messagebox.showwarning("Open chat",
                                   "Select an event first.")
            return
        item = self.events_tree.item(sel[0])
        # Tree text holds the event name; the ID column is values[0].
        event_name = item.get('text') or 'Event'
        try:
            event_id = item.get('values', [None])[0]
        except Exception:
            event_id = None
        if not event_id:
            from tkinter import messagebox
            messagebox.showerror("Open chat", "Could not determine event id.")
            return
        try:
            from education_system.university_system.infrastructure.email.admin import (
                CommunicationDashboard,
            )
            from education_system.university_system.modules.shared.gui.email.email_gui.chat_launchers import (
                open_chat_for_event,
            )
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Open chat", f"Chat module unavailable: {e}")
            return
        dashboard = CommunicationDashboard(
            auth=getattr(self, 'auth_manager', None) or getattr(self, 'auth', None),
        )
        open_chat_for_event(self.root if hasattr(self, 'root') else None,
                            dashboard, event_id, event_name)

