import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from education_system.university_system.core.i18n import get_text as _
from education_system.university_system.modules.domain.academics.gui.academic_calendar.utils import safe_grab_set

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

            capacity_str = self.capacity_var.get().strip()
            if capacity_str and not capacity_str.isdigit():
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.capacity_must_be_number"))
                return

            resource_data = {
                'name': name,
                'type': resource_type,
                'capacity': int(capacity_str) if capacity_str else None,
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
    """Dialog for booking resources with date/time pickers"""

    def __init__(self, parent, calendar_manager, resource_name=None, callback=None):
        self.calendar_manager = calendar_manager
        self.resource_name = resource_name
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.resource_management.book_title"))
        self.dialog.geometry("520x600")
        self.dialog.minsize(480, 550)
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        # Get current user info for email
        self._auth = getattr(calendar_manager, '_auth', None) or getattr(calendar_manager, 'auth', None)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.resource_management.book_header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Resource selection
        ttk.Label(main_frame, text=_("academic_calendar.labels.resource_required")).pack(anchor=tk.W)
        self.resource_var = tk.StringVar(value=self.resource_name or "")
        resource_combo = ttk.Combobox(main_frame, textvariable=self.resource_var, width=42, state='readonly')
        resource_combo.pack(fill=tk.X, pady=(5, 10))

        try:
            resources = self.calendar_manager.db_manager.execute_query(
                "SELECT name FROM resources WHERE status = 'available' ORDER BY name"
            )
            resource_combo['values'] = [r['name'] for r in resources]
        except Exception as e:
            gui_logger.warning(f"Failed to load resources: {e}")

        # Event selection
        ttk.Label(main_frame, text=_("academic_calendar.labels.event_optional")).pack(anchor=tk.W)
        self.event_var = tk.StringVar()
        self._event_map = {}
        event_combo = ttk.Combobox(main_frame, textvariable=self.event_var, width=42, state='readonly')
        event_combo.pack(fill=tk.X, pady=(5, 10))

        try:
            events = self.calendar_manager.db_manager.execute_query(
                "SELECT id, name FROM academic_calendar_events ORDER BY date_added DESC LIMIT 30"
            )
            labels = ["(None)"]
            self._event_map["(None)"] = None
            for e in events:
                label = f"{e['name']} ({e['id'][:8]}...)"
                labels.append(label)
                self._event_map[label] = e['id']
            event_combo['values'] = labels
            event_combo.current(0)
        except Exception as e:
            gui_logger.warning(f"Failed to load events: {e}")

        # Date picker
        ttk.Label(main_frame, text="Date:").pack(anchor=tk.W, pady=(5, 0))
        date_frame = ttk.Frame(main_frame)
        date_frame.pack(fill=tk.X, pady=(5, 10))

        now = datetime.now()
        days = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(60)]

        self.date_var = tk.StringVar(value=now.strftime("%Y-%m-%d"))
        date_combo = ttk.Combobox(date_frame, textvariable=self.date_var, values=days, width=42, state='readonly')
        date_combo.pack(fill=tk.X)

        # Start time picker
        ttk.Label(main_frame, text="Start Time:").pack(anchor=tk.W, pady=(5, 0))
        start_frame = ttk.Frame(main_frame)
        start_frame.pack(fill=tk.X, pady=(5, 10))

        hours = [f"{h:02d}" for h in range(7, 22)]
        minutes = ["00", "15", "30", "45"]

        self.start_hour_var = tk.StringVar(value="09")
        self.start_min_var = tk.StringVar(value="00")
        ttk.Combobox(start_frame, textvariable=self.start_hour_var, values=hours, width=5, state='readonly').pack(side=tk.LEFT)
        ttk.Label(start_frame, text=":").pack(side=tk.LEFT, padx=2)
        ttk.Combobox(start_frame, textvariable=self.start_min_var, values=minutes, width=5, state='readonly').pack(side=tk.LEFT)

        # End time picker
        ttk.Label(main_frame, text="End Time:").pack(anchor=tk.W, pady=(5, 0))
        end_frame = ttk.Frame(main_frame)
        end_frame.pack(fill=tk.X, pady=(5, 10))

        self.end_hour_var = tk.StringVar(value="10")
        self.end_min_var = tk.StringVar(value="00")
        ttk.Combobox(end_frame, textvariable=self.end_hour_var, values=hours, width=5, state='readonly').pack(side=tk.LEFT)
        ttk.Label(end_frame, text=":").pack(side=tk.LEFT, padx=2)
        ttk.Combobox(end_frame, textvariable=self.end_min_var, values=minutes, width=5, state='readonly').pack(side=tk.LEFT)

        # Notes
        ttk.Label(main_frame, text=_("academic_calendar.labels.notes")).pack(anchor=tk.W, pady=(5, 0))
        self.notes_text = scrolledtext.ScrolledText(main_frame, height=3, width=45)
        self.notes_text.pack(fill=tk.X, pady=(5, 10))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text=_("academic_calendar.buttons.book_resource"), command=self._book_resource).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _book_resource(self):
        """Book the resource"""
        try:
            resource_name = self.resource_var.get().strip()
            date = self.date_var.get().strip()
            start_time = f"{date} {self.start_hour_var.get()}:{self.start_min_var.get()}"
            end_time = f"{date} {self.end_hour_var.get()}:{self.end_min_var.get()}"

            if not resource_name:
                messagebox.showerror(_("common.error"), "Please select a resource.", parent=self.dialog)
                return

            if start_time >= end_time:
                messagebox.showerror(_("common.error"), "End time must be after start time.", parent=self.dialog)
                return

            # Get resource ID
            resource_rows = self.calendar_manager.db_manager.execute_query(
                "SELECT id FROM resources WHERE name = ?", (resource_name,)
            )
            if not resource_rows:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.resource_not_found"), parent=self.dialog)
                return

            resource_id = resource_rows[0]['id']

            # Get event ID if selected
            event_selection = self.event_var.get()
            event_id = self._event_map.get(event_selection)

            booking_data = {
                'resource_id': resource_id,
                'event_id': event_id,
                'start_time': start_time,
                'end_time': end_time,
                'notes': self.notes_text.get(1.0, tk.END).strip()
            }

            success, message = self.calendar_manager.resources.book_resource(booking_data)

            if success:
                self._send_booking_email(resource_name, start_time, end_time)
                messagebox.showinfo(_("common.success"), message, parent=self.dialog)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message, parent=self.dialog)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_book_resource", error=str(e)), parent=self.dialog)

    def _send_booking_email(self, resource_name, start_time, end_time):
        """Send booking confirmation email to current user"""
        try:
            from education_system.university_system.infrastructure.email.email_service import queue_email

            user_email = None
            username = "User"
            if self._auth:
                if hasattr(self._auth, 'current_user') and self._auth.current_user:
                    user_email = self._auth.current_user.get('email')
                    username = self._auth.current_user.get('username', 'User')
                elif isinstance(self._auth, dict):
                    user_email = self._auth.get('email')
                    username = self._auth.get('username', 'User')

            if not user_email:
                return

            notes = self.notes_text.get(1.0, tk.END).strip()
            subject = f"Resource Booking Confirmation: {resource_name}"
            body = (
                f"Dear {username},\n\n"
                f"Your resource booking has been confirmed:\n\n"
                f"  Resource: {resource_name}\n"
                f"  Start: {start_time}\n"
                f"  End: {end_time}\n"
            )
            if notes:
                body += f"  Notes: {notes}\n"
            body += (
                f"\nPlease ensure you arrive on time and leave the resource in good condition.\n\n"
                f"Kind regards,\n"
                f"Academic Calendar System"
            )
            queue_email(to=user_email, subject=subject, body=body)
            gui_logger.info(f"Booking confirmation email queued for {user_email}")
        except ImportError:
            gui_logger.debug("Email service not available for booking confirmation")
        except Exception as e:
            gui_logger.warning(f"Failed to send booking email: {e}")

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
    """Dialog for linking courses to events — shows dropdowns for both."""

    def __init__(self, parent, calendar_manager, course_name=None, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback

        # Load events
        self.event_map = {}
        try:
            rows = calendar_manager.db_manager.execute_query(
                "SELECT id, name FROM academic_calendar_events ORDER BY name"
            )
            for row in rows:
                label = f"{row['name']} ({row['id'][:8]}...)"
                self.event_map[label] = row['id']
        except Exception:
            pass

        if not self.event_map:
            messagebox.showwarning(_("common.warning"), "No events found. Create an event first.")
            return

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.messages.link_course_dialog.title"))
        self.dialog.geometry("500x250")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        frm = ttk.Frame(self.dialog, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Link Course to Event",
                  font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Course (pre-filled if provided)
        ttk.Label(frm, text="Course:").pack(anchor=tk.W)
        self.course_var = tk.StringVar(value=course_name or "")
        course_entry = ttk.Entry(frm, textvariable=self.course_var, width=55)
        course_entry.pack(fill=tk.X, pady=(5, 10))
        if course_name:
            course_entry.configure(state="readonly")

        # Event dropdown
        ttk.Label(frm, text="Event:").pack(anchor=tk.W)
        self.event_combo = ttk.Combobox(frm, values=list(self.event_map.keys()), width=53, state='readonly')
        self.event_combo.pack(fill=tk.X, pady=(5, 15))
        if self.event_map:
            self.event_combo.current(0)

        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Link", command=self._link).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(btn_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _link(self):
        course_name = self.course_var.get().strip()
        selected_event = self.event_combo.get()

        if not course_name:
            messagebox.showwarning(_("common.warning"), "Please enter a course name.")
            return
        if selected_event not in self.event_map:
            messagebox.showwarning(_("common.warning"), "Please select an event.")
            return

        event_id = self.event_map[selected_event]

        try:
            courses = self.calendar_manager.db_manager.execute_query(
                "SELECT id FROM courses WHERE name = ?", (course_name,)
            )
            if not courses:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.course_not_found"))
                return

            course_id = courses[0]['id']
            success, message = self.calendar_manager.courses.link_event_to_course(event_id, course_id)
            if success:
                messagebox.showinfo(_("common.success"), message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_link_course", error=str(e)))


