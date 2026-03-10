import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import queue
import json
from typing import Any, Optional, List, Dict
from education_system.university_system.modules.shared.utils.i18n import get_text as _

gui_logger = logging.getLogger(__name__)

# Import dialog - use lazy import to avoid circular dependency
def _get_add_event_dialog():
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.dialogs_event import AddEventDialog
    return AddEventDialog

class CalendarViewMixin:
    def _show_calendar_view(self):
        """Show calendar view"""
        self._clear_content_area()
        self.current_view = "calendar"
    
        # Header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
    
        ttk.Label(header_frame, text=_("academic_calendar.calendar_view.title"), style='Header.TLabel').pack(side=tk.LEFT)
    
        # Filters
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
    
        ttk.Label(filter_frame, text=_("academic_calendar.labels.academic_year")).pack(side=tk.LEFT, padx=(0, 5))
        self.year_var = tk.StringVar()
        year_combo = ttk.Combobox(filter_frame, textvariable=self.year_var, width=15)
        year_combo.pack(side=tk.LEFT, padx=(0, 10))
    
        ttk.Label(filter_frame, text=_("academic_calendar.labels.semester")).pack(side=tk.LEFT, padx=(0, 5))
        self.semester_var = tk.StringVar()
        semester_combo = ttk.Combobox(filter_frame, textvariable=self.semester_var, width=15)
        semester_combo.pack(side=tk.LEFT, padx=(0, 10))
    
        view_btn = ttk.Button(filter_frame, text=_("academic_calendar.buttons.view"), command=self._load_calendar_data)
        view_btn.pack(side=tk.LEFT)
        
        # Content area
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create treeview for calendar data
        self._create_calendar_treeview(content_frame)
        
        # Load initial data
        self._load_calendar_data()

    def _create_calendar_treeview(self, parent):
        """Create treeview for calendar display"""
        # Treeview
        self.calendar_tree = ttk.Treeview(parent, 
                                        columns=('Date', 'End Date', 'Type', 'Description'),
                                        show='tree headings')
        self.calendar_tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure columns
        self.calendar_tree.heading('#0', text=_("academic_calendar.columns.event_name"))
        self.calendar_tree.heading('Date', text=_("academic_calendar.columns.start_date"))
        self.calendar_tree.heading('End Date', text=_("academic_calendar.columns.end_date"))
        self.calendar_tree.heading('Type', text=_("academic_calendar.columns.type"))
        self.calendar_tree.heading('Description', text=_("academic_calendar.columns.description"))
        
        self.calendar_tree.column('#0', width=250)
        self.calendar_tree.column('Date', width=120)
        self.calendar_tree.column('End Date', width=120)
        self.calendar_tree.column('Type', width=120)
        self.calendar_tree.column('Description', width=300)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.calendar_tree.yview)
        h_scrollbar = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.calendar_tree.xview)
        
        self.calendar_tree.configure(yscrollcommand=v_scrollbar.set, 
                                   xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Context menu
        self._create_calendar_context_menu()

    def _create_calendar_context_menu(self):
        """Create context menu for calendar items"""
        self.calendar_context_menu = tk.Menu(self.root, tearoff=0)
        self.calendar_context_menu.add_command(label=_("academic_calendar.context_menu.edit_event"), command=self._edit_selected_event)
        self.calendar_context_menu.add_command(label=_("academic_calendar.context_menu.delete_event"), command=self._delete_selected_event)
        self.calendar_context_menu.add_separator()
        self.calendar_context_menu.add_command(label=_("academic_calendar.context_menu.view_details"), command=self._view_event_details)
        self.calendar_context_menu.add_separator()
        self.calendar_context_menu.add_command(label=_("academic_calendar.context_menu.send_email_reminder"), command=self._send_email_reminder)
        
        def show_context_menu(event):
            try:
                self.calendar_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.calendar_context_menu.grab_release()
        
        self.calendar_tree.bind("<Button-3>", show_context_menu)  # Right click

    def _load_calendar_data(self):
        """Load calendar data into treeview"""
        try:
            if not self.calendar_manager:
                return
            
            # Clear existing data
            for item in self.calendar_tree.get_children():
                self.calendar_tree.delete(item)
            
            # Get filter values
            academic_year = self.year_var.get() if hasattr(self, 'year_var') else None
            semester = self.semester_var.get() if hasattr(self, 'semester_var') else None
            
            academic_year = academic_year if academic_year and academic_year != '' else None
            semester = semester if semester and semester != '' else None
            
            # Get calendar data
            success, data = self.calendar_manager.view_calendar(academic_year, semester)
            
            if success and data:
                # Group by semester
                semester_groups = {}
                for item in data:
                    semester_name = item.get('semester_name', 'Unknown')
                    if semester_name not in semester_groups:
                        semester_groups[semester_name] = []
                    if item.get('event_name'):  # Only add items with events
                        semester_groups[semester_name].append(item)
                
                # Add to treeview
                for semester_name, events in semester_groups.items():
                    if events:  # Only show semesters with events
                        # Add semester header
                        semester_node = self.calendar_tree.insert('', 'end',
                                                                text=f"📖 {semester_name}",
                                                                values=('', '', _("academic_calendar.labels.semester"), ''),
                                                                open=True)
                        
                        # Add events
                        for event in events:
                            event_date = event.get('date') or event.get('date_start', '')
                            end_date = event.get('date_end', '')
                            event_type = event.get('event_type', '')
                            description = event.get('description', '')[:100]
                            
                            # Add event type icon
                            type_icons = {
                                'Academic': '📚',
                                'Holiday': '🎉',
                                'Administrative': '📋',
                                'Trip': '🎒',
                                'Deadline': '⏰',
                                'Social': '🎊',
                                'Sports': '⚽'
                            }
                            icon = type_icons.get(event_type, '📅')
                            
                            self.calendar_tree.insert(semester_node, 'end',
                                                    text=f"{icon} {event['event_name']}",
                                                    values=(event_date, end_date, event_type, description))
                
                self._update_status(_("academic_calendar.messages.loaded_calendar_items").format(count=len(data)), "success")
            else:
                self._update_status(_("academic_calendar.messages.no_calendar_data"), "warning")
                
        except Exception as e:
            gui_logger.error(f"Failed to load calendar data: {e}")
            self._show_error(_("academic_calendar.messages.failed_to_load_events").format(error=e))

    def _show_add_event(self):
        """Show add event dialog"""
        _get_add_event_dialog()(self.root, self.calendar_manager, self._refresh_current_view)

    def _search_events(self):
        """Search events based on search term"""
        search_term = self.search_var.get().lower()
        
        # Show/hide items based on search
        for item in self.events_tree.get_children():
            event_name = self.events_tree.item(item, 'text').lower()
            values = [str(v).lower() for v in self.events_tree.item(item, 'values')]
            
            if (search_term in event_name or 
                any(search_term in v for v in values)):
                # Show item
                self.events_tree.item(item, tags=())
            else:
                # Hide item (by moving it out of view)
                self.events_tree.item(item, tags=('hidden',))
        
        # Configure hidden tag
        self.events_tree.tag_configure('hidden', foreground='gray')

