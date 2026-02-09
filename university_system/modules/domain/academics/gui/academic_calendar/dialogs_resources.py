import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from university_system.modules.shared.utils.i18n import get_text as _
from university_system.modules.domain.academics.gui.academic_calendar.utils import safe_grab_set

gui_logger = logging.getLogger(__name__)

class ResourceManagementDialog:
    """Dialog for managing resources (rooms, equipment, etc.)"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.resource_management.title"))
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._load_resources()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.resource_management.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Button(action_frame, text=_("academic_calendar.buttons.add_resource"),
                  command=self._add_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_("academic_calendar.buttons.book_resource"),
                  command=self._book_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_("academic_calendar.buttons.refresh"),
                  command=self._load_resources).pack(side=tk.RIGHT, padx=5)
        
        # Resources tree
        self.resources_tree = ttk.Treeview(main_frame, 
                                         columns=('Type', 'Capacity', 'Location', 'Status'),
                                         show='tree headings')
        self.resources_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Configure columns
        self.resources_tree.heading('#0', text=_("academic_calendar.columns.resource_name"))
        self.resources_tree.heading('Type', text=_("academic_calendar.columns.type"))
        self.resources_tree.heading('Capacity', text=_("academic_calendar.columns.capacity"))
        self.resources_tree.heading('Location', text=_("academic_calendar.columns.location"))
        self.resources_tree.heading('Status', text=_("academic_calendar.columns.status"))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.resources_tree.yview)
        self.resources_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _load_resources(self):
        """Load resources into tree"""
        try:
            # Clear existing items
            for item in self.resources_tree.get_children():
                self.resources_tree.delete(item)
            
            # Get resources from database
            resources = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM resources ORDER BY type, name"
            )
            
            for resource in resources:
                self.resources_tree.insert('', 'end',
                                         text=resource['name'],
                                         values=(resource['type'], 
                                               resource['capacity'] or 'N/A',
                                               resource['location'] or 'N/A',
                                               resource['status']))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_load_resources", error=str(e)))

    def _add_resource(self):
        """Show add resource dialog"""
        AddResourceDialog(self.dialog, self.calendar_manager, self._load_resources)

    def _book_resource(self):
        """Show resource booking dialog"""
        selection = self.resources_tree.selection()
        if selection:
            resource_name = self.resources_tree.item(selection[0], 'text')
            BookResourceDialog(self.dialog, self.calendar_manager, resource_name, self._load_resources)
        else:
            messagebox.showwarning(_("academic_calendar.messages.selection_required"), _("academic_calendar.messages.select_resource_to_book"))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AddResourceDialog:
    """Dialog for adding new resources"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.resource_management.add_title"))
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.resource_management.add_header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Resource name
        ttk.Label(main_frame, text=_("academic_calendar.labels.resource_name_required")).pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # Resource type
        ttk.Label(main_frame, text=_("academic_calendar.labels.resource_type_required")).pack(anchor=tk.W)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=37,
                                values=["Classroom", "Laboratory", "Auditorium", "Equipment", "Vehicle", "Other"])
        type_combo.pack(fill=tk.X, pady=(5, 15))

        # Capacity
        ttk.Label(main_frame, text=_("academic_calendar.labels.capacity")).pack(anchor=tk.W)
        self.capacity_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.capacity_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # Location
        ttk.Label(main_frame, text=_("academic_calendar.labels.location")).pack(anchor=tk.W)
        self.location_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.location_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.add_resource"), command=self._add_resource).pack(side=tk.RIGHT)
    
    def _add_resource(self):
        """Add the resource"""
        try:
            name = self.name_var.get().strip()
            resource_type = self.type_var.get().strip()
            
            if not name or not resource_type:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.name_type_required"))
                return

            resource_data = {
                'name': name,
                'type': resource_type,
                'capacity': int(self.capacity_var.get()) if self.capacity_var.get().strip() else None,
                'location': self.location_var.get().strip() or None
            }

            success, message = self.calendar_manager.resources.create_resource(resource_data)

            if success:
                messagebox.showinfo(_("common.success"), message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message)

        except ValueError:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.capacity_must_be_number"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_add_resource", error=str(e)))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class BookResourceDialog:
    """Dialog for booking resources"""
    
    def __init__(self, parent, calendar_manager, resource_name=None, callback=None):
        self.calendar_manager = calendar_manager
        self.resource_name = resource_name
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.resource_management.book_title"))
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.resource_management.book_header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Resource selection
        ttk.Label(main_frame, text=_("academic_calendar.labels.resource_required")).pack(anchor=tk.W)
        self.resource_var = tk.StringVar(value=self.resource_name or "")
        resource_combo = ttk.Combobox(main_frame, textvariable=self.resource_var, width=42)
        resource_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Load resources
        try:
            resources = self.calendar_manager.db_manager.execute_query(
                "SELECT name FROM resources WHERE status = 'available' ORDER BY name"
            )
            resource_names = [r['name'] for r in resources]
            resource_combo['values'] = resource_names
        except Exception as e:
            gui_logger.warning(f"Failed to load resources for allocation: {e}")
        
        # Event selection
        ttk.Label(main_frame, text=_("academic_calendar.labels.event_optional")).pack(anchor=tk.W)
        self.event_var = tk.StringVar()
        event_combo = ttk.Combobox(main_frame, textvariable=self.event_var, width=42)
        event_combo.pack(fill=tk.X, pady=(5, 15))

        # Load recent events
        try:
            events = self.calendar_manager.db_manager.execute_query(
                "SELECT id, name FROM academic_calendar_events ORDER BY date_added DESC LIMIT 20"
            )
            event_list = [f"{e['name']} ({e['id'][:8]})" for e in events]
            event_combo['values'] = event_list
        except Exception as e:
            gui_logger.warning(f"Failed to load events for allocation: {e}")

        # Start time
        ttk.Label(main_frame, text=_("academic_calendar.labels.start_time_required")).pack(anchor=tk.W)
        self.start_time_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_time_var, width=45).pack(fill=tk.X, pady=(5, 15))

        # End time
        ttk.Label(main_frame, text=_("academic_calendar.labels.end_time_required")).pack(anchor=tk.W)
        self.end_time_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_time_var, width=45).pack(fill=tk.X, pady=(5, 15))

        # Notes
        ttk.Label(main_frame, text=_("academic_calendar.labels.notes")).pack(anchor=tk.W)
        self.notes_text = scrolledtext.ScrolledText(main_frame, height=3, width=45)
        self.notes_text.pack(fill=tk.X, pady=(5, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.book_resource"), command=self._book_resource).pack(side=tk.RIGHT)
    
    def _book_resource(self):
        """Book the resource"""
        try:
            resource_name = self.resource_var.get().strip()
            start_time = self.start_time_var.get().strip()
            end_time = self.end_time_var.get().strip()
            
            if not all([resource_name, start_time, end_time]):
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.resource_start_end_required"))
                return

            # Get resource ID
            resource_rows = self.calendar_manager.db_manager.execute_query(
                "SELECT id FROM resources WHERE name = ?", (resource_name,)
            )
            if not resource_rows:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.resource_not_found"))
                return
            
            resource_id = resource_rows[0]['id']
            
            # Get event ID if selected
            event_id = None
            event_selection = self.event_var.get().strip()
            if event_selection:
                # Extract ID from "Name (ID)" format
                if '(' in event_selection and ')' in event_selection:
                    event_id_part = event_selection.split('(')[1].split(')')[0]
                    # Find full event ID
                    event_rows = self.calendar_manager.db_manager.execute_query(
                        "SELECT id FROM academic_calendar_events WHERE id LIKE ?", (f"{event_id_part}%",)
                    )
                    if event_rows:
                        event_id = event_rows[0]['id']
            
            booking_data = {
                'resource_id': resource_id,
                'event_id': event_id,
                'start_time': start_time,
                'end_time': end_time,
                'notes': self.notes_text.get(1.0, tk.END).strip()
            }
            
            success, message = self.calendar_manager.resources.book_resource(booking_data)

            if success:
                messagebox.showinfo(_("common.success"), message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_book_resource", error=str(e)))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class CourseManagementDialog:
    """Dialog for managing courses"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.course_management.title"))
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._load_courses()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.course_management.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Button(action_frame, text=_("academic_calendar.buttons.add_course"),
                  command=self._add_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_("academic_calendar.buttons.link_to_event"),
                  command=self._link_to_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_("academic_calendar.buttons.refresh"),
                  command=self._load_courses).pack(side=tk.RIGHT, padx=5)
        
        # Courses tree
        self.courses_tree = ttk.Treeview(main_frame, 
                                       columns=('Code', 'Credits', 'Department', 'Status'),
                                       show='tree headings')
        self.courses_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Configure columns
        self.courses_tree.heading('#0', text=_("academic_calendar.columns.course_name"))
        self.courses_tree.heading('Code', text=_("academic_calendar.columns.code"))
        self.courses_tree.heading('Credits', text=_("academic_calendar.columns.credits"))
        self.courses_tree.heading('Department', text=_("academic_calendar.columns.department"))
        self.courses_tree.heading('Status', text=_("academic_calendar.columns.status"))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.courses_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.courses_tree.xview)
        
        self.courses_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _load_courses(self):
        """Load courses into tree"""
        try:
            # Clear existing items
            for item in self.courses_tree.get_children():
                self.courses_tree.delete(item)
            
            # Get courses from database
            courses = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM courses ORDER BY department, code"
            )
            
            for course in courses:
                self.courses_tree.insert('', 'end',
                                       text=course['name'],
                                       values=(course['code'], 
                                             course['credits'] or 'N/A',
                                             course['department'] or 'N/A',
                                             course['status']))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_load_courses", error=str(e)))

    def _add_course(self):
        """Show add course dialog"""
        AddCourseDialog(self.dialog, self.calendar_manager, self._load_courses)

    def _link_to_event(self):
        """Show link course to event dialog"""
        selection = self.courses_tree.selection()
        if selection:
            course_name = self.courses_tree.item(selection[0], 'text')
            LinkCourseEventDialog(self.dialog, self.calendar_manager, course_name, self._load_courses)
        else:
            messagebox.showwarning(_("academic_calendar.messages.selection_required"), _("academic_calendar.messages.select_course_to_link"))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AddCourseDialog:
    """Simple dialog for adding courses"""

    def __init__(self, parent, calendar_manager, callback=None):
        code = simpledialog.askstring(_("academic_calendar.messages.add_course_dialog.title"), _("academic_calendar.messages.add_course_dialog.course_code"))
        if not code:
            return

        name = simpledialog.askstring(_("academic_calendar.messages.add_course_dialog.title"), _("academic_calendar.messages.add_course_dialog.course_name"))
        if not name:
            return

        credits = simpledialog.askinteger(_("academic_calendar.messages.add_course_dialog.title"), _("academic_calendar.messages.add_course_dialog.credits"), initialvalue=3) or 3
        department = simpledialog.askstring(_("academic_calendar.messages.add_course_dialog.title"), _("academic_calendar.messages.add_course_dialog.department")) or None
        
        course_data = {
            'code': code,
            'name': name,
            'credits': credits,
            'department': department
        }
        
        try:
            success, message = calendar_manager.courses.create_course(course_data)
            if success:
                messagebox.showinfo(_("common.success"), message)
                if callback:
                    callback()
            else:
                messagebox.showerror(_("common.error"), message)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_add_course", error=str(e)))


class LinkCourseEventDialog:
    """Simple dialog for linking courses to events"""

    def __init__(self, parent, calendar_manager, course_name, callback=None):
        event_id = simpledialog.askstring(_("academic_calendar.messages.link_course_dialog.title"), _("academic_calendar.messages.link_course_dialog.event_id"))
        if not event_id:
            return
        
        try:
            # Get course ID by name
            courses = calendar_manager.db_manager.execute_query(
                "SELECT id FROM courses WHERE name = ?", (course_name,)
            )
            
            if not courses:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.course_not_found"))
                return

            course_id = courses[0]['id']

            success, message = calendar_manager.courses.link_event_to_course(event_id, course_id)
            if success:
                messagebox.showinfo(_("common.success"), message)
                if callback:
                    callback()
            else:
                messagebox.showerror(_("common.error"), message)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_link_course", error=str(e)))


