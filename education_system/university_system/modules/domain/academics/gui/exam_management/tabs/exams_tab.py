"""Exam management tab for the Exam Scheduling System."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from education_system.university_system.modules.domain.academics.gui.exam_management.models import Exam

# i18n import
try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _
except ImportError:
    def _(key, **kwargs):
        return key

# Email imports
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False

# Academic calendar integration
try:
    from education_system.university_system.modules.domain.academics.gui.academic_calendar.database import DatabaseManager as CalendarDB
    HAS_CALENDAR = True
except ImportError:
    HAS_CALENDAR = False


class ExamsTabMixin:
    """Mixin providing the exam management tab and its operations."""

    def create_exams_tab(self):
        """Create the exam management tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("exam_scheduler.tabs.manage_exams"))

        # Split into left (form) and right (list)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left side - Scrollable Form Container
        form_container = ttk.LabelFrame(paned, text=_("exam_scheduler.frames.exam_details"), padding="5")
        paned.add(form_container, weight=1)

        # Create canvas and scrollbar for the form
        form_canvas = tk.Canvas(form_container, highlightthickness=0)
        form_scrollbar = ttk.Scrollbar(form_container, orient=tk.VERTICAL, command=form_canvas.yview)

        # Create frame inside canvas for form content
        form_frame = ttk.Frame(form_canvas, padding="10")

        # Configure canvas scrolling
        form_canvas.configure(yscrollcommand=form_scrollbar.set)

        # Pack scrollbar and canvas
        form_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create window in canvas
        canvas_frame = form_canvas.create_window((0, 0), window=form_frame, anchor=tk.NW)

        # Bind mousewheel for scrolling
        def on_mousewheel(event):
            form_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        def on_configure(event):
            # Update scrollregion when content changes
            form_canvas.configure(scrollregion=form_canvas.bbox("all"))
            # Update canvas window width to match canvas width
            canvas_width = event.width
            form_canvas.itemconfig(canvas_frame, width=canvas_width)

        form_canvas.bind('<Configure>', on_configure)
        form_frame.bind('<Configure>', lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))

        # Bind mousewheel to canvas and all children
        def bind_mousewheel(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>", lambda e: form_canvas.yview_scroll(-1, "units"))
            widget.bind("<Button-5>", lambda e: form_canvas.yview_scroll(1, "units"))
            for child in widget.winfo_children():
                bind_mousewheel(child)

        bind_mousewheel(form_frame)

        # Configure grid column weights for proper expansion
        form_frame.columnconfigure(1, weight=1)

        self.exam_vars = {}
        current_row = 0

        # Module Search Box
        ttk.Label(form_frame, text=_("exam_scheduler.labels.search_module")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        self.module_search_var = tk.StringVar()
        self.module_search_var.trace('w', lambda *args: self.search_modules())
        search_entry = ttk.Entry(form_frame, textvariable=self.module_search_var, width=30)
        search_entry.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        current_row += 1

        # Module Code Dropdown (replaces manual entry)
        ttk.Label(form_frame, text=_("exam_scheduler.labels.module_code")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        self.module_combo = ttk.Combobox(form_frame, textvariable=self.module_var, width=27, state='readonly')
        self.module_combo.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.module_combo.bind('<<ComboboxSelected>>', self.on_module_select)
        self.update_module_combo()
        current_row += 1

        # Module Name (auto-filled after selection)
        ttk.Label(form_frame, text=_("exam_scheduler.labels.module_name")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        self.exam_vars['module_name'] = tk.StringVar()
        self.module_name_entry = ttk.Entry(form_frame, textvariable=self.exam_vars['module_name'], width=30, state='readonly')
        self.module_name_entry.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        current_row += 1

        # Date with quick picker
        ttk.Label(form_frame, text=_("exam_scheduler.labels.date")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        date_frame = ttk.Frame(form_frame)
        date_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.exam_vars['date'] = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.exam_vars['date'], width=15).pack(side=tk.LEFT)
        ttk.Button(date_frame, text="Today", command=lambda: self.set_date_today(), width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(date_frame, text="+7d", command=lambda: self.set_date_offset(7), width=5).pack(side=tk.LEFT, padx=2)
        current_row += 1

        # Start Time with quick buttons
        ttk.Label(form_frame, text=_("exam_scheduler.labels.start_time")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        start_time_frame = ttk.Frame(form_frame)
        start_time_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.exam_vars['start_time'] = tk.StringVar()
        ttk.Entry(start_time_frame, textvariable=self.exam_vars['start_time'], width=10).pack(side=tk.LEFT)
        ttk.Button(start_time_frame, text="09:00", command=lambda: self.exam_vars['start_time'].set("09:00"), width=5).pack(side=tk.LEFT, padx=1)
        ttk.Button(start_time_frame, text="14:00", command=lambda: self.exam_vars['start_time'].set("14:00"), width=5).pack(side=tk.LEFT, padx=1)
        ttk.Button(start_time_frame, text="18:00", command=lambda: self.exam_vars['start_time'].set("18:00"), width=5).pack(side=tk.LEFT, padx=1)
        current_row += 1

        # End Time with duration helpers
        ttk.Label(form_frame, text=_("exam_scheduler.labels.end_time")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        end_time_frame = ttk.Frame(form_frame)
        end_time_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.exam_vars['end_time'] = tk.StringVar()
        ttk.Entry(end_time_frame, textvariable=self.exam_vars['end_time'], width=10).pack(side=tk.LEFT)
        ttk.Button(end_time_frame, text="+1h", command=lambda: self.add_duration(60), width=5).pack(side=tk.LEFT, padx=1)
        ttk.Button(end_time_frame, text="+2h", command=lambda: self.add_duration(120), width=5).pack(side=tk.LEFT, padx=1)
        ttk.Button(end_time_frame, text="+3h", command=lambda: self.add_duration(180), width=5).pack(side=tk.LEFT, padx=1)
        current_row += 1

        # Instructor Dropdown
        ttk.Label(form_frame, text=_("exam_scheduler.labels.instructor")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        instructor_frame = ttk.Frame(form_frame)
        instructor_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.instructor_var = tk.StringVar()
        self.instructor_combo = ttk.Combobox(instructor_frame, textvariable=self.instructor_var, width=27, state='readonly')
        self.instructor_combo.pack(side=tk.LEFT)
        self.update_instructor_combo()
        ttk.Button(instructor_frame, text="Check", command=self.check_instructor_availability, width=8).pack(side=tk.LEFT, padx=5)
        current_row += 1

        # Room dropdown with helper buttons
        ttk.Label(form_frame, text=_("exam_scheduler.labels.room")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        room_frame = ttk.Frame(form_frame)
        room_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.room_var = tk.StringVar()
        self.room_combo = ttk.Combobox(room_frame, textvariable=self.room_var, width=27, state='readonly')
        self.room_combo.pack(side=tk.LEFT)
        self.update_room_combo()
        current_row += 1

        # Room helper buttons
        room_btns_frame = ttk.Frame(form_frame)
        room_btns_frame.grid(row=current_row, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        ttk.Button(room_btns_frame, text="Suggest Rooms", command=self.suggest_available_rooms, width=13).pack(side=tk.LEFT, padx=1)
        ttk.Button(room_btns_frame, text="Check Available", command=self.check_room_availability, width=13).pack(side=tk.LEFT, padx=1)
        ttk.Button(room_btns_frame, text="Check Capacity", command=self.validate_room_capacity, width=13).pack(side=tk.LEFT, padx=1)
        current_row += 1

        # Students Enrolled Section
        ttk.Label(form_frame, text=_("exam_scheduler.labels.students_enrolled")).grid(row=current_row, column=0, sticky=tk.NW, pady=5)
        students_frame = ttk.Frame(form_frame)
        students_frame.grid(row=current_row, column=1, sticky=tk.NSEW, pady=5, padx=(10, 0))

        # Students count and status
        self.students_count_var = tk.StringVar(value=_("exam_scheduler.labels.students_count", count=0))
        ttk.Label(students_frame, textvariable=self.students_count_var, font=('Helvetica', 9, 'bold')).pack(anchor=tk.W)

        # Students listbox with scrollbar
        students_list_frame = ttk.Frame(students_frame)
        students_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.students_listbox = tk.Listbox(students_list_frame, height=5, width=35, selectmode=tk.EXTENDED)
        students_scrollbar = ttk.Scrollbar(students_list_frame, orient=tk.VERTICAL, command=self.students_listbox.yview)
        self.students_listbox.configure(yscrollcommand=students_scrollbar.set)
        self.students_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        students_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Refresh-roster button: re-pull current enrollments from
        # student_modules without changing the selected module. Useful
        # when editing an exam after new students have enrolled.
        ttk.Button(students_frame, text="🔄 Refresh roster from enrolment",
                   command=self.refresh_roster_from_module).pack(
            anchor=tk.W, pady=(4, 0))

        # Store enrolled student IDs
        self.enrolled_student_ids = []
        current_row += 1

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=current_row, column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.add_exam"), command=self.add_exam, style='Accent.TButton').pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.update"), command=self.update_exam).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.duplicate"), command=self.duplicate_exam).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.delete"), command=self.delete_exam).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.clear"), command=self.clear_exam_form).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="External examiners…",
                   command=self.open_external_examiners_dialog).pack(
                       side=tk.LEFT, padx=3)

        # Note about automatic actions
        note_label = ttk.Label(form_frame, text=_("exam_scheduler.labels.auto_notifications_note"),
                              font=('Helvetica', 8, 'italic'), foreground='gray')
        note_label.grid(row=current_row + 1, column=0, columnspan=2, pady=(10, 0))

        self.selected_exam_id = None
        self.selected_instructor_id = None

        # Right side - List
        list_frame = ttk.LabelFrame(paned, text=_("exam_scheduler.frames.exam_list"), padding="10")
        paned.add(list_frame, weight=2)

        # Search
        search_frame = ttk.Frame(list_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_("exam_scheduler.labels.search")).pack(side=tk.LEFT)
        self.exam_search_var = tk.StringVar()
        self.exam_search_var.trace('w', lambda *args: self.search_exams())
        ttk.Entry(search_frame, textvariable=self.exam_search_var, width=30).pack(side=tk.LEFT, padx=5)

        # Exam list
        columns = ('id', 'module', 'name', 'date', 'room')
        self.exam_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.exam_tree.heading('id', text=_("exam_scheduler.columns.id"))
        self.exam_tree.heading('module', text=_("exam_scheduler.columns.module"))
        self.exam_tree.heading('name', text=_("exam_scheduler.columns.name"))
        self.exam_tree.heading('date', text=_("exam_scheduler.columns.date"))
        self.exam_tree.heading('room', text=_("exam_scheduler.columns.room"))

        self.exam_tree.column('id', width=40)
        self.exam_tree.column('module', width=80)
        self.exam_tree.column('name', width=150)
        self.exam_tree.column('date', width=90)
        self.exam_tree.column('room', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.exam_tree.yview)
        self.exam_tree.configure(yscrollcommand=scrollbar.set)

        self.exam_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection
        self.exam_tree.bind('<<TreeviewSelect>>', self.on_exam_select)

    # --- Module/Instructor/Room dropdowns ---

    def update_room_combo(self):
        """Update the room dropdown with available rooms."""
        room_names = [f"{r.name} ({r.building}) - Cap: {r.capacity}" for r in self.data_manager.rooms]
        self.room_combo['values'] = room_names

    def update_instructor_combo(self):
        """Update the instructor dropdown with instructors from database."""
        instructors = self.data_manager.get_instructors()
        if instructors:
            instructor_names = [f"{i['display_name']} ({i['department'] or 'N/A'})" for i in instructors]
            self.instructor_combo['values'] = instructor_names
        else:
            # Fallback: allow manual entry if no instructors in DB
            self.instructor_combo['state'] = 'normal'
            self.instructor_combo['values'] = []

    def update_module_combo(self):
        """Update the module dropdown with modules from database."""
        modules = self.data_manager.get_all_modules()
        self.all_modules = modules  # Store for search functionality
        if modules:
            # Format: "MODULE_CODE - Module Name"
            module_options = [f"{m['module_code']} - {m['module_name']}" for m in modules]
            self.module_combo['values'] = module_options
        else:
            self.module_combo['values'] = []

    def search_modules(self, event=None):
        """Search and filter modules in real-time."""
        search_term = self.module_search_var.get().lower()
        if not search_term or not hasattr(self, 'all_modules'):
            # Show all modules if no search term
            if hasattr(self, 'all_modules'):
                module_options = [f"{m['module_code']} - {m['module_name']}" for m in self.all_modules]
                self.module_combo['values'] = module_options
            return

        # Filter modules based on search term
        filtered = [m for m in self.all_modules
                   if search_term in m['module_code'].lower() or
                      search_term in m['module_name'].lower()]

        module_options = [f"{m['module_code']} - {m['module_name']}" for m in filtered]
        self.module_combo['values'] = module_options

    def on_module_select(self, event=None):
        """Handle module selection from dropdown."""
        module_selection = self.module_var.get()
        if not module_selection:
            return

        # Extract module code (format: "MODULE_CODE - Module Name")
        module_code = module_selection.split(' - ')[0]

        # Look up module details
        module = self.data_manager.lookup_module(module_code)
        if module:
            # Auto-fill module name
            self.exam_vars['module_name'].set(module['module_name'] or '')

            # Get enrolled students
            students = self.data_manager.get_enrolled_students(module_code)
            self.populate_students_list(students)

    def populate_students_list(self, students: List[Dict]):
        """Populate the students listbox with enrolled students."""
        self.students_listbox.delete(0, tk.END)
        self.enrolled_student_ids = []

        for student in students:
            self.students_listbox.insert(tk.END, student['display_name'])
            self.enrolled_student_ids.append(student['student_id'])

        self.students_count_var.set(_("exam_scheduler.labels.students_count", count=len(students)))

    def _current_module_code(self) -> Optional[str]:
        """Extract the module code currently selected in the form, or None."""
        selection = self.module_var.get()
        if not selection:
            return None
        return selection.split(' - ')[0].strip() or None

    def open_external_examiners_dialog(self):
        """Open the external-examiner attachment manager for the selected
        exam. Requires an exam to be selected (since attachments are
        per-exam)."""
        if not self.selected_exam_id:
            messagebox.showinfo(
                "External examiners",
                "Select an exam in the list before managing examiners.",
            )
            return
        ExternalExaminersDialog(
            self.root, self.data_manager, self.selected_exam_id,
        )

    def _confirm_external_conflicts(self, conflicts) -> bool:
        """Show overlapping bookings/lectures from other systems and ask
        whether to proceed anyway. Returns True if the user accepts."""
        if not conflicts:
            return True
        lines = "\n".join(f"  • {desc}  [{src}]" for src, desc in conflicts[:8])
        more = "" if len(conflicts) <= 8 else f"\n  …and {len(conflicts) - 8} more"
        return messagebox.askyesno(
            _("exam_scheduler.dialogs.conflict"),
            "This room is already booked at that time by another part of "
            "the university:\n\n" + lines + more +
            "\n\nProceed anyway?",
        )

    def refresh_roster_from_module(self):
        """Re-pull the enrolled-students list from student_modules for the
        currently selected module. Called from the form's refresh button
        and implicitly at save time so the snapshot stored on the exam is
        always the latest enrolment."""
        module_code = self._current_module_code()
        if not module_code:
            messagebox.showinfo(
                _("exam_scheduler.dialogs.warning"),
                "Select a module first to load its enrolled students.",
            )
            return
        students = self.data_manager.get_enrolled_students(module_code)
        self.populate_students_list(students)

    # --- Selection helpers ---

    def get_selected_instructor_id(self) -> Optional[int]:
        """Get the ID of the selected instructor."""
        instructor_selection = self.instructor_var.get()
        if not instructor_selection:
            return None

        instructors = self.data_manager.get_instructors()
        for inst in instructors:
            if instructor_selection.startswith(inst['display_name']):
                return inst['id']
        return None

    def get_instructor_display_name(self) -> str:
        """Get display name from instructor selection."""
        instructor_selection = self.instructor_var.get()
        if not instructor_selection:
            return ""

        # Extract name before the parenthesis
        if ' (' in instructor_selection:
            return instructor_selection.split(' (')[0]
        return instructor_selection

    def get_selected_module_code(self) -> str:
        """Extract module code from the module dropdown selection."""
        module_selection = self.module_var.get()
        if not module_selection:
            return ""
        # Format: "MODULE_CODE - Module Name"
        return module_selection.split(' - ')[0]

    # --- Exam search ---

    def search_exams(self):
        """Search exams by module code or name."""
        search_term = self.exam_search_var.get().lower()

        for item in self.exam_tree.get_children():
            self.exam_tree.delete(item)

        for exam in self.data_manager.exams:
            if (search_term in exam.module_code.lower() or
                search_term in exam.module_name.lower() or
                search_term in exam.instructor_name.lower()):
                self.exam_tree.insert('', tk.END, values=(
                    exam.id, exam.module_code, exam.module_name, exam.date, exam.room
                ))

    # --- Validation ---

    def validate_exam_form(self) -> bool:
        """Validate the exam form inputs."""
        # Check module selection
        if not self.module_var.get():
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.select_module"))
            return False

        # Check other required fields
        required = ['module_name', 'date', 'start_time', 'end_time']
        for field_name in required:
            if not self.exam_vars[field_name].get().strip():
                messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.fill_required_fields"))
                return False

        if not self.instructor_var.get():
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.select_instructor"))
            return False

        if not self.room_var.get():
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.select_room"))
            return False

        # Validate date format
        try:
            datetime.strptime(self.exam_vars['date'].get(), '%Y-%m-%d')
        except ValueError:
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.invalid_date_format"))
            return False

        # Validate time format
        for time_field in ['start_time', 'end_time']:
            try:
                datetime.strptime(self.exam_vars[time_field].get(), '%H:%M')
            except ValueError:
                messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.invalid_time_format"))
                return False

        return True

    # --- CRUD operations ---

    def add_exam(self):
        """Add a new exam."""
        if not self.validate_exam_form():
            return

        # Extract module code from dropdown
        module_code = self.get_selected_module_code()

        # Extract room name
        room_selection = self.room_var.get()
        room_name = room_selection.split(' (')[0] if room_selection else ""

        # Check for conflicts
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()

        if self.data_manager.check_conflict(date, start, end, room_name):
            messagebox.showerror(_("exam_scheduler.dialogs.conflict"), _("exam_scheduler.messages.scheduling_conflict"))
            return

        # Cross-check shared room_bookings + recurring lecture timetable
        external = self.data_manager.find_external_room_conflicts(
            date, start, end, room_name)
        if external and not self._confirm_external_conflicts(external):
            return

        # Get instructor details
        instructor_id = self.get_selected_instructor_id()
        instructor_name = self.get_instructor_display_name()

        # Re-derive the roster from student_modules so the snapshot stored
        # on the exam matches the current enrolment (covers cases where
        # students enrolled after the form was opened).
        live_students = self.data_manager.get_enrolled_students(module_code)
        roster_ids = [s['student_id'] for s in live_students]

        exam = Exam(
            id=self.data_manager.get_next_exam_id(),
            module_code=module_code,
            module_name=self.exam_vars['module_name'].get().strip(),
            date=date,
            start_time=start,
            end_time=end,
            room=room_name,
            instructor_id=instructor_id,
            instructor_name=instructor_name,
            students_enrolled=len(roster_ids),
            enrolled_student_ids=roster_ids,
        )

        self.data_manager.add_exam(exam)

        # Notify any open sibling GUIs (Grade tracking, Module scheduling,
        # Course mgmt) so their views can refresh without manual reload.
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                publish, EVENT_EXAM_CHANGED, EVENT_CALENDAR_CHANGED,
            )
            publish(EVENT_EXAM_CHANGED,
                    exam_id=exam.id, module_code=module_code, action="create")
        except Exception:
            pass

        # Automatically add to calendar
        calendar_added = False
        if HAS_CALENDAR:
            calendar_added = self.data_manager.add_exam_to_calendar(exam)
            if calendar_added:
                try:
                    publish(EVENT_CALENDAR_CHANGED,
                            event_type="Exam", source_id=exam.id, action="create")
                except Exception:
                    pass

        # Reserve the room in the shared room_bookings table so other
        # systems (lectures, society events, facilities) see it as taken.
        room_reserved = self.data_manager.reserve_room_for_exam(exam)

        # Automatically send email notifications
        email_success, email_failed = 0, 0
        if HAS_EMAIL:
            email_success, email_failed = self.data_manager.send_exam_notifications(exam)

        self.refresh_exam_list()
        self.clear_exam_form()

        # Build success message with details
        msg = _("exam_scheduler.messages.exam_added")
        if calendar_added:
            msg += "\n\n✓ " + _("exam_scheduler.messages.added_to_calendar")
        if room_reserved:
            msg += "\n✓ Room reserved in shared bookings"
        if HAS_EMAIL:
            msg += f"\n✓ {_('exam_scheduler.messages.notifications_sent')}: {email_success}"
            if email_failed > 0:
                msg += f" ({_('exam_scheduler.messages.failed')}: {email_failed})"

        # The DB writes above can take long enough on a contended SQLite
        # database that the user closes the window first; the resulting
        # ``_tkinter.TclError: can't invoke "grab" command: application
        # has been destroyed`` then propagates up through the Tk callback.
        # Skip the dialog cleanly when the parent window is gone.
        try:
            messagebox.showinfo(_("exam_scheduler.dialogs.success"), msg)
        except tk.TclError:
            pass

    def update_exam(self):
        """Update the selected exam."""
        if not self.selected_exam_id:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.select_exam_to_update"))
            return

        if not self.validate_exam_form():
            return

        # Extract module code from dropdown
        module_code = self.get_selected_module_code()

        room_selection = self.room_var.get()
        room_name = room_selection.split(' (')[0] if room_selection else ""

        # Check for conflicts (excluding current exam)
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()

        if self.data_manager.check_conflict(date, start, end, room_name, self.selected_exam_id):
            messagebox.showerror(_("exam_scheduler.dialogs.conflict"), _("exam_scheduler.messages.scheduling_conflict"))
            return

        external = self.data_manager.find_external_room_conflicts(
            date, start, end, room_name, self.selected_exam_id)
        if external and not self._confirm_external_conflicts(external):
            return

        # Get instructor details
        instructor_id = self.get_selected_instructor_id()
        instructor_name = self.get_instructor_display_name()

        # Always refresh the roster on update so the snapshot tracks
        # current enrolment in student_modules.
        live_students = self.data_manager.get_enrolled_students(module_code)
        roster_ids = [s['student_id'] for s in live_students]

        exam = Exam(
            id=self.selected_exam_id,
            module_code=module_code,
            module_name=self.exam_vars['module_name'].get().strip(),
            date=date,
            start_time=start,
            end_time=end,
            room=room_name,
            instructor_id=instructor_id,
            instructor_name=instructor_name,
            students_enrolled=len(roster_ids),
            enrolled_student_ids=roster_ids,
        )

        self.data_manager.update_exam(exam)

        # Mirror the change onto the academic calendar so students/staff
        # see the updated time, room, and instructor.
        calendar_updated = False
        if HAS_CALENDAR:
            calendar_updated = self.data_manager.update_exam_in_calendar(exam)

        # Broadcast to sibling GUIs.
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                publish, EVENT_EXAM_CHANGED,
            )
            publish(EVENT_EXAM_CHANGED,
                    exam_id=exam.id, module_code=exam.module_code, action="update")
        except Exception:
            pass

        # Refresh the shared room reservation (room or time may have changed).
        room_reserved = self.data_manager.reserve_room_for_exam(exam)

        # Send email notifications about the update
        email_success, email_failed = 0, 0
        if HAS_EMAIL:
            email_success, email_failed = self.data_manager.send_exam_update_notifications(exam)

        self.refresh_exam_list()
        self.clear_exam_form()

        # Build success message with details
        msg = _("exam_scheduler.messages.exam_updated")
        if calendar_updated:
            msg += "\n\n✓ " + _("exam_scheduler.messages.added_to_calendar")
        if room_reserved:
            msg += "\n✓ Shared room reservation updated"
        if HAS_EMAIL:
            msg += f"\n✓ {_('exam_scheduler.messages.update_notifications_sent')}: {email_success}"
            if email_failed > 0:
                msg += f" ({_('exam_scheduler.messages.failed')}: {email_failed})"

        messagebox.showinfo(_("exam_scheduler.dialogs.success"), msg)

    def delete_exam(self):
        """Delete the selected exam."""
        if not self.selected_exam_id:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.select_exam_to_delete"))
            return

        if messagebox.askyesno(_("exam_scheduler.dialogs.confirm_delete"), _("exam_scheduler.messages.confirm_delete_exam")):
            exam_id = self.selected_exam_id
            # Capture the exam's details before deleting so cancellation
            # emails can quote the original schedule.
            exam_obj = next((e for e in self.data_manager.exams if e.id == exam_id), None)

            self.data_manager.delete_exam(exam_id)
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    publish, EVENT_EXAM_CHANGED,
                )
                publish(EVENT_EXAM_CHANGED,
                        exam_id=exam_id,
                        module_code=getattr(exam_obj, "module_code", None),
                        action="delete")
            except Exception:
                pass
            if HAS_CALENDAR:
                self.data_manager.remove_exam_from_calendar(exam_id)
            self.data_manager.release_room_for_exam(exam_id)

            email_success = email_failed = 0
            if HAS_EMAIL and exam_obj is not None:
                email_success, email_failed = self.data_manager.send_exam_cancellation_notifications(exam_obj)

            self.refresh_exam_list()
            self.clear_exam_form()

            msg = _("exam_scheduler.messages.exam_deleted")
            if HAS_EMAIL and exam_obj is not None:
                msg += f"\n\n✓ Cancellation notifications sent: {email_success}"
                if email_failed > 0:
                    msg += f" (failed: {email_failed})"
            messagebox.showinfo(_("exam_scheduler.dialogs.success"), msg)

    def clear_exam_form(self):
        """Clear the exam form."""
        for var in self.exam_vars.values():
            var.set("")
        self.module_var.set("")
        self.room_var.set("")
        self.instructor_var.set("")
        self.students_listbox.delete(0, tk.END)
        self.enrolled_student_ids = []
        self.students_count_var.set(_("exam_scheduler.labels.students_count", count=0))
        self.selected_exam_id = None
        self.selected_instructor_id = None

        # Default the date field to the start of the active exam window
        # (#8) so the operator opens the form on a date the gate will
        # accept. Falls through silently if no window is configured.
        try:
            from education_system.university_system.modules.domain.academics.gui._cross_services import (
                current_period,
            )
            window = current_period("exam_window")
            if window:
                start = window.get("date_start") or window.get("date")
                if start:
                    self.exam_vars['date'].set(start[:10])
        except Exception:
            pass

    def on_exam_select(self, event):
        """Handle exam selection in the tree."""
        selection = self.exam_tree.selection()
        if not selection:
            return

        item = self.exam_tree.item(selection[0])
        exam_id = item['values'][0]

        # Find the exam
        exam = next((e for e in self.data_manager.exams if e.id == exam_id), None)
        if not exam:
            return

        self.selected_exam_id = exam_id

        # Soft selection broadcast so siblings highlight this exam.
        try:
            from education_system.university_system.modules.services.academic_state import (
                set_current_selection,
            )
            set_current_selection(
                exam_id=exam_id, module_code=exam.module_code,
                source="exam_scheduler",
            )
        except Exception:
            pass

        # Set module dropdown
        # Find matching module in dropdown options
        module = self.data_manager.lookup_module(exam.module_code)
        if module:
            module_option = f"{exam.module_code} - {module['module_name']}"
            self.module_var.set(module_option)
        else:
            # Fallback: try to find by code only
            for option in self.module_combo['values']:
                if option.startswith(exam.module_code + ' -'):
                    self.module_var.set(option)
                    break

        # Populate form with other fields
        self.exam_vars['module_name'].set(exam.module_name)
        self.exam_vars['date'].set(exam.date)
        self.exam_vars['start_time'].set(exam.start_time)
        self.exam_vars['end_time'].set(exam.end_time)

        # Set instructor combo
        if exam.instructor_id:
            instructor = self.data_manager.get_instructor_by_id(exam.instructor_id)
            if instructor:
                self.instructor_var.set(f"{instructor['display_name']} ({instructor['department'] or 'N/A'})")
                self.selected_instructor_id = exam.instructor_id
        else:
            # Fallback for legacy data with just instructor name
            for inst in self.data_manager.get_instructors():
                if inst['display_name'] == exam.instructor_name:
                    self.instructor_var.set(f"{inst['display_name']} ({inst['department'] or 'N/A'})")
                    break

        # Set room combo
        for room in self.data_manager.rooms:
            if room.name == exam.room:
                self.room_var.set(f"{room.name} ({room.building}) - Cap: {room.capacity}")
                break

        # Populate enrolled students
        self.enrolled_student_ids = exam.enrolled_student_ids.copy() if exam.enrolled_student_ids else []
        self.students_listbox.delete(0, tk.END)

        if self.enrolled_student_ids:
            # Get student details from database
            students = self.data_manager.get_enrolled_students(exam.module_code)
            for student in students:
                if student['student_id'] in self.enrolled_student_ids:
                    self.students_listbox.insert(tk.END, student['display_name'])
            self.students_count_var.set(_("exam_scheduler.labels.students_count", count=len(self.enrolled_student_ids)))
        else:
            self.students_count_var.set(_("exam_scheduler.labels.students_count", count=exam.students_enrolled))

    # --- Date/time helpers ---

    def set_date_today(self):
        """Set the date field to today's date."""
        today = datetime.now().strftime('%Y-%m-%d')
        self.exam_vars['date'].set(today)

    def set_date_offset(self, days: int):
        """Set the date field to today + offset days."""
        target_date = datetime.now() + timedelta(days=days)
        self.exam_vars['date'].set(target_date.strftime('%Y-%m-%d'))

    def add_duration(self, minutes: int):
        """Add duration to start time to calculate end time."""
        start_time_str = self.exam_vars['start_time'].get()
        if not start_time_str:
            messagebox.showwarning("Warning", "Please enter a start time first")
            return

        try:
            start_time = datetime.strptime(start_time_str, '%H:%M')
            end_time = start_time + timedelta(minutes=minutes)
            self.exam_vars['end_time'].set(end_time.strftime('%H:%M'))
        except ValueError:
            messagebox.showerror("Error", "Invalid start time format. Use HH:MM")

    def duplicate_exam(self):
        """Duplicate the currently selected exam with a different date/time."""
        if not self.selected_exam_id:
            messagebox.showwarning("No Selection", "Please select an exam to duplicate")
            return

        # Find the exam
        exam = next((e for e in self.data_manager.exams if e.id == self.selected_exam_id), None)
        if not exam:
            return

        # Clear the ID so it will create a new exam
        self.selected_exam_id = None

        # Suggest next day
        try:
            current_date = datetime.strptime(exam.date, '%Y-%m-%d')
            next_date = current_date + timedelta(days=1)
            self.exam_vars['date'].set(next_date.strftime('%Y-%m-%d'))
        except (ValueError, TypeError):
            pass

        messagebox.showinfo(
            "Duplicate Mode",
            "Exam details loaded. Change the date/time and click 'Add Exam' to create a duplicate."
        )


class ExternalExaminersDialog(tk.Toplevel):
    """Manage which external examiners are attached to a given exam."""

    def __init__(self, parent, data_manager, exam_id: int):
        super().__init__(parent)
        self.title(f"External examiners — exam #{exam_id}")
        self.geometry("560x420")
        self.transient(parent)
        self.grab_set()

        self._dm = data_manager
        self._exam_id = exam_id

        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            wrap,
            text="Examiners are pulled from the external_examiners "
                 "module. Add new examiners there; this dialog only "
                 "manages who is attached to this exam.",
            foreground="#555", wraplength=520, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        # Currently attached
        ttk.Label(wrap, text="Attached to this exam",
                  font=("Helvetica", 10, "bold")).pack(anchor="w")
        self._attached_tree = ttk.Treeview(
            wrap,
            columns=("name", "institution", "role"),
            show="headings", height=6,
        )
        for c, w, h in [("name", 200, "Name"),
                        ("institution", 180, "Institution"),
                        ("role", 130, "Role")]:
            self._attached_tree.heading(c, text=h)
            self._attached_tree.column(c, width=w, anchor="w")
        self._attached_tree.pack(fill=tk.BOTH, expand=True, pady=(2, 6))

        ttk.Button(wrap, text="Remove selected",
                   command=self._remove_selected).pack(anchor="w")

        # Add a new attachment
        sep = ttk.Separator(wrap)
        sep.pack(fill=tk.X, pady=12)

        ttk.Label(wrap, text="Attach an examiner",
                  font=("Helvetica", 10, "bold")).pack(anchor="w")
        row = ttk.Frame(wrap)
        row.pack(fill=tk.X, pady=4)
        self._examiner_var = tk.StringVar()
        self._role_var = tk.StringVar()

        examiners = data_manager.list_active_examiners()

        # Find course-level appointed examiners for this exam's module so
        # they surface at the top of the picker — saves admins re-picking
        # the same examiner that's already appointed for the year.
        appointed_ids: set = set()
        try:
            exam_obj = next(
                (e for e in (data_manager.exams or [])
                 if e.id == self._exam_id), None)
            if exam_obj is not None:
                from education_system.university_system.modules.domain.academics.services.course_management.examiner_assignments import (
                    find_examiners_for_module,
                )
                for ex in find_examiners_for_module(exam_obj.module_code):
                    appointed_ids.add(ex["examiner_id"])
        except Exception:
            pass

        self._examiner_lookup = {}
        # Order: appointed first, then everyone else, both alphabetical.
        def _sort_key(e):
            ex_id = e.get("examiner_id") or e.get("id")
            return (0 if ex_id in appointed_ids else 1,
                    (e.get("name") or "").lower())
        for e in sorted(examiners, key=_sort_key):
            ex_id = e.get("examiner_id") or e.get("id")
            if ex_id is None:
                continue
            prefix = "★ " if ex_id in appointed_ids else ""
            label = f"{prefix}{e.get('name','?')} — {e.get('institution','?')}"
            self._examiner_lookup[label] = ex_id
        self._combo = ttk.Combobox(
            row, textvariable=self._examiner_var,
            values=list(self._examiner_lookup.keys()),
            state="readonly", width=42,
        )
        self._combo.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Entry(row, textvariable=self._role_var, width=18).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Label(row, text="(role, optional)",
                  foreground="#888").pack(side=tk.LEFT)

        ttk.Button(wrap, text="Attach",
                   command=self._attach).pack(anchor="w", pady=(4, 0))

        ttk.Button(wrap, text="Close",
                   command=self.destroy).pack(side=tk.RIGHT, pady=(8, 0))

        self._refresh_attached()

    def _refresh_attached(self):
        for iid in self._attached_tree.get_children():
            self._attached_tree.delete(iid)
        for r in self._dm.list_examiners_for_exam(self._exam_id):
            self._attached_tree.insert(
                "", tk.END,
                iid=str(r["examiner_id"]),
                values=(r.get("name", ""),
                        r.get("institution", "") or "—",
                        r.get("role", "") or "—"),
            )

    def _attach(self):
        label = self._examiner_var.get().strip()
        if not label:
            messagebox.showinfo("Attach", "Pick an examiner first.",
                                parent=self)
            return
        examiner_id = self._examiner_lookup.get(label)
        if not examiner_id:
            messagebox.showerror("Attach", "Unknown examiner.", parent=self)
            return
        ok = self._dm.attach_external_examiner(
            self._exam_id, examiner_id, self._role_var.get().strip(),
        )
        if not ok:
            messagebox.showerror(
                "Attach", "Could not save the attachment — see logs.",
                parent=self)
            return
        self._role_var.set("")
        self._examiner_var.set("")
        self._refresh_attached()

    def _remove_selected(self):
        sel = self._attached_tree.selection()
        if not sel:
            messagebox.showinfo("Remove", "Pick an attached examiner.",
                                parent=self)
            return
        examiner_id = int(sel[0])
        if not messagebox.askyesno(
                "Remove", "Detach this examiner from the exam?",
                parent=self):
            return
        self._dm.detach_external_examiner(self._exam_id, examiner_id)
        self._refresh_attached()
