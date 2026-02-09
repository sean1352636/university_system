import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import json
from typing import Any, Optional, List, Dict
from university_system.modules.shared.utils.i18n import get_text as _

gui_logger = logging.getLogger(__name__)

class DashboardMixin:
    def _show_dashboard(self):
        """Show dashboard view"""
        self._clear_content_area()
        self.current_view = "dashboard"
    
        # Dashboard header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
    
        ttk.Label(header_frame, text=_("academic_calendar.dashboard.title"), style='Header.TLabel').pack(side=tk.LEFT)
    
        refresh_btn = ttk.Button(header_frame, text=_("academic_calendar.buttons.refresh"),
                               command=self._refresh_dashboard)
        refresh_btn.pack(side=tk.RIGHT)
        
        # Dashboard content
        dashboard_frame = ttk.Frame(self.content_area)
        dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self._create_dashboard_content(dashboard_frame)

    def _create_dashboard_content(self, parent):
        """Create dashboard content"""
        try:
            # Stats cards row
            stats_frame = ttk.Frame(parent)
            stats_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Get system stats
            if self.calendar_manager:
                stats = self.calendar_manager.get_system_stats()
                
                # Total events card
                self._create_stat_card(stats_frame, _("academic_calendar.dashboard.total_events"),
                                     sum(stats.get('events_by_type', {}).values()),
                                     _("academic_calendar.dashboard.all_events_in_system"))
    
                # Current academic year card
                self._create_stat_card(stats_frame, _("academic_calendar.dashboard.academic_year"),
                                     stats.get('current_academic_year', _("common.none")),
                                     _("academic_calendar.dashboard.current_active_year"))
    
                # Current semester card
                self._create_stat_card(stats_frame, _("academic_calendar.dashboard.semester"),
                                     stats.get('current_semester', _("common.none")),
                                     _("academic_calendar.dashboard.current_active_semester"))
    
                # Upcoming events card
                self._create_stat_card(stats_frame, _("academic_calendar.dashboard.upcoming"),
                                     stats.get('upcoming_events', 0),
                                     _("academic_calendar.dashboard.events_next_30_days"))
            
            # Recent events section
            recent_frame = ttk.LabelFrame(parent, text=_("academic_calendar.dashboard.recent_events"), padding=10)
            recent_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
            self._create_recent_events_list(recent_frame)
    
            # Quick actions section
            actions_frame = ttk.LabelFrame(parent, text=_("academic_calendar.dashboard.quick_actions"), padding=10)
            actions_frame.pack(fill=tk.X)
            
            self._create_quick_actions(actions_frame)
            
        except Exception as e:
            gui_logger.error(f"Dashboard creation failed: {e}")
            ttk.Label(parent, text=_("academic_calendar.messages.error_loading_dashboard").format(error=e)).pack()

    def _create_stat_card(self, parent, title, value, description):
        """Create a statistics card"""
        card_frame = ttk.Frame(parent)
        card_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Card content
        card_content = ttk.LabelFrame(card_frame, text=title, padding=10)
        card_content.pack(fill=tk.BOTH, expand=True)
        
        # Value
        value_label = ttk.Label(card_content, text=str(value), 
                               font=('Arial', 18, 'bold'))
        value_label.pack()
        
        # Description
        desc_label = ttk.Label(card_content, text=description,
                              font=('Arial', 9))
        desc_label.pack()

    def _create_recent_events_list(self, parent):
        """Create recent events list"""
        try:
            # Get recent events
            if self.calendar_manager:
                current_date = datetime.now().strftime("%Y-%m-%d")
                future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                
                events = self.calendar_manager.get_events_by_date_range(
                    current_date, future_date
                )[:10]  # Limit to 10 events
                
                if events:
                    # Treeview for events
                    tree = ttk.Treeview(parent, columns=('Date', 'Type', 'Description'), 
                                       show='tree headings', height=8)
                    tree.pack(fill=tk.BOTH, expand=True)
                    
                    # Configure columns
                    tree.heading('#0', text=_("academic_calendar.columns.event_name"))
                    tree.heading('Date', text=_("academic_calendar.columns.date"))
                    tree.heading('Type', text=_("academic_calendar.columns.type"))
                    tree.heading('Description', text=_("academic_calendar.columns.description"))
                    
                    tree.column('#0', width=200)
                    tree.column('Date', width=100)
                    tree.column('Type', width=100)
                    tree.column('Description', width=300)
                    
                    # Add events
                    for event in events:
                        event_date = event['date'] or event['date_start']
                        description = (event['description'] or '')[:50]
                        if len(event['description'] or '') > 50:
                            description += "..."
                        
                        tree.insert('', 'end', text=event['name'],
                                   values=(event_date, event['event_type'], description))
                    
                    # Scrollbar
                    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                else:
                    ttk.Label(parent, text=_("academic_calendar.messages.no_upcoming_events")).pack()
            else:
                ttk.Label(parent, text=_("academic_calendar.messages.calendar_manager_not_available")).pack()
                
        except Exception as e:
            gui_logger.error(f"Recent events list creation failed: {e}")
            ttk.Label(parent, text=_("academic_calendar.messages.error_loading_events").format(error=e)).pack()

    def _create_quick_actions(self, parent):
        """Create quick action buttons"""
        actions = [
            (_("academic_calendar.buttons.add_event"), self._show_add_event),
            (_("academic_calendar.buttons.view_calendar"), self._show_calendar_view),
            (_("academic_calendar.buttons.export"), self._show_export),
            (_("academic_calendar.buttons.settings"), self._show_settings)
        ]
        
        for text, command in actions:
            if self._has_permission_for_button(text):
                btn = ttk.Button(parent, text=text, command=command)
                btn.pack(side=tk.LEFT, padx=5)

    def _refresh_dashboard(self):
        """Refresh dashboard"""
        self._show_dashboard()

