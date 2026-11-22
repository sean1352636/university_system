"""Assessment management"""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import messagebox
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import make_toplevel
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system import paths
from education_system.systems.university.domains.assessment.domain.assessment_service import AssessmentAssignmentService
from collections import deque
from education_system.systems.university.infrastructure.ui.field_pickers import attach_combo, attach_date, time_values



class AssessmentManager:
    """Assessment management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def load_modules(self, combo):
        """Load available modules"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
            modules = cursor.fetchall()

            module_list = [f"{code} - {name}" for code, name in modules]
            combo['values'] = module_list

            # Create mapping for easy lookup
            self.module_map = {f"{code} - {name}": code for code, name in modules}

            conn.close()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.error', default="Error"), f"Failed to load modules: {e}")

    # ------------------------------------------------------------------
    # Exam scheduling integration
    #
    # An assessment of type 'exam' is also a scheduled exam: it needs a row
    # in `exams` so it shows up in the Exam Scheduling GUI, the academic
    # calendar and the shared room_bookings table. Rather than duplicate
    # that write path, this reuses the exam module's DataManager, which owns
    # the schema, the conflict checks and the calendar/room side effects.
    # ------------------------------------------------------------------

    EXAM_TYPE = "exam"

    def _exam_data_manager(self):
        """Return the exam DataManager, or None when it is unavailable.

        Built lazily and cached: constructing it loads every exam and room
        from the database, which is too slow to do while drawing the form.
        """
        if getattr(self, '_exam_dm', None) is not None:
            return self._exam_dm
        try:
            from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.data_manager import (
                DataManager as ExamDataManager,
            )
            self._exam_dm = ExamDataManager()
        except Exception as exc:
            self._exam_dm = None
            self._exam_dm_error = str(exc)
        return self._exam_dm

    def _room_label(self, room):
        """Match the Exam Scheduling room dropdown exactly."""
        return f"{room.name} ({room.building}) - Cap: {room.capacity}"

    def _selected_exam_room(self):
        """Room name from the dropdown label, or '' when nothing is picked."""
        selection = self.exam_room_var.get() if hasattr(self, 'exam_room_var') else ""
        return selection.split(' (')[0] if selection else ""

    def _selected_exam_instructor(self):
        """Return ``(instructor_id, display_name)`` for the chosen entry."""
        label = self.exam_instructor_var.get() if hasattr(self, 'exam_instructor_var') else ""
        if not label:
            return None, ""
        for inst in getattr(self, '_exam_instructors', []):
            if f"{inst['display_name']} ({inst['department'] or 'N/A'})" == label:
                return inst['id'], inst['display_name']
        # Fall back to free text when the instructors table is empty and the
        # combo was left editable.
        return None, label

    def _build_exam_details_frame(self, parent):
        """Build the exam-only scheduling fields. Hidden unless type == exam."""
        frame = ttk.LabelFrame(
            parent,
            text=_t('gui.academics.assignment_system.assessment_manager.labels.exam_scheduling',
                    default="Exam Scheduling"),
            padding=20,
        )

        hint = ttk.Label(
            frame,
            text=_t('gui.academics.assignment_system.assessment_manager.labels.exam_hint',
                    default="Exams are also scheduled: this books the room and adds the exam "
                            "to the calendar."),
        )
        hint.grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))

        # Exam date — defaults to the assessment due date so the common case
        # (sit the exam on the due date) needs no extra typing.
        ttk.Label(frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.exam_date',
                                 default="Exam Date:")).grid(row=1, column=0, sticky='w', pady=5)
        self.exam_date_var = tk.StringVar(value=self.assessment_due_date_var.get())
        attach_date(frame, id_var=self.exam_date_var).grid(
            row=1, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.start_time',
                                 default="Start Time:")).grid(row=2, column=0, sticky='w', pady=5)
        self.exam_start_time_var = tk.StringVar(value="09:00")
        attach_combo(frame, time_values(), textvariable=self.exam_start_time_var,
                     width=7).grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.end_time',
                                 default="End Time:")).grid(row=3, column=0, sticky='w', pady=5)
        self.exam_end_time_var = tk.StringVar(value="11:00")
        attach_combo(frame, time_values(), textvariable=self.exam_end_time_var,
                     width=7).grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.location',
                                 default="Location (Room):")).grid(row=4, column=0, sticky='w', pady=5)
        self.exam_room_var = tk.StringVar()
        self.exam_room_combo = ttk.Combobox(
            frame, textvariable=self.exam_room_var, width=32, state='readonly')
        self.exam_room_combo.grid(row=4, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.invigilator',
                                 default="Instructor:")).grid(row=5, column=0, sticky='w', pady=5)
        self.exam_instructor_var = tk.StringVar()
        self.exam_instructor_combo = ttk.Combobox(
            frame, textvariable=self.exam_instructor_var, width=32, state='readonly')
        self.exam_instructor_combo.grid(row=5, column=1, sticky='w', pady=5, padx=(10, 0))

        link_frame = ttk.Frame(frame)
        link_frame.grid(row=6, column=0, columnspan=2, sticky='w', pady=(12, 0))
        ttk.Button(
            link_frame,
            text=_t('gui.academics.assignment_system.assessment_manager.buttons.open_exam_scheduling',
                    default="Open Exam Scheduling"),
            command=self.open_exam_scheduling,
        ).pack(side='left')

        return frame

    def populate_exam_choices(self):
        """Fill the room and instructor dropdowns from the exam database."""
        dm = self._exam_data_manager()
        if dm is None:
            self.show_assessment_status(
                "Exam scheduling is unavailable: "
                f"{getattr(self, '_exam_dm_error', 'exam module failed to load')}. "
                "The assessment can still be saved without a scheduled exam.",
                "warning",
            )
            return

        self.exam_room_combo['values'] = [self._room_label(r) for r in dm.rooms]

        self._exam_instructors = dm.get_instructors()
        if self._exam_instructors:
            self.exam_instructor_combo['values'] = [
                f"{i['display_name']} ({i['department'] or 'N/A'})"
                for i in self._exam_instructors
            ]
        else:
            # Mirror the Exam Scheduling GUI: with no instructors on file the
            # combo becomes free text rather than an empty readonly dropdown.
            self.exam_instructor_combo['state'] = 'normal'
            self.exam_instructor_combo['values'] = []

    def on_assessment_type_change(self, event=None):
        """Show the scheduling fields only for an assessment of type 'exam'."""
        if not hasattr(self, 'exam_details_frame'):
            return

        is_exam = self.assessment_type_var.get() == self.EXAM_TYPE
        if is_exam:
            # `before=` keeps the section in place between the details form and
            # the description box across repeated hide/show cycles.
            self.exam_details_frame.pack(
                fill='x', pady=(0, 20), before=self.assessment_desc_frame)
            if not getattr(self, '_exam_choices_loaded', False):
                self.populate_exam_choices()
                self._exam_choices_loaded = True
        else:
            self.exam_details_frame.pack_forget()

    def open_exam_scheduling(self):
        """Open the Exam Scheduling GUI, pre-filtered to this module."""
        from education_system.systems.university.domains.teaching.interfaces.gui._cross_launchers import (
            AcademicContext, open_exam_gui,
        )
        module_label = getattr(self, 'assessment_module_var', tk.StringVar()).get()
        module_code = self.module_map.get(module_label) if hasattr(self, 'module_map') else None
        open_exam_gui(
            self.root,
            getattr(self, 'auth', None),
            context=AcademicContext(
                module_code=module_code,
                exam_id=getattr(self, 'last_created_exam_id', None),
            ),
        )

    def create_assessment(self):
        """Create a new assessment"""
        if not self._check_permission('manage_assignments'):
            return

        # If the creation form is visible, save directly; otherwise show the form
        if hasattr(self, 'assessment_title_var'):
            self.save_assessment()
        else:
            self.show_create_assessment()


    def manage_assessments(self):
        """Manage existing assessments"""
        if not self._check_permission('manage_assignments'):
            return

        self.show_manage_assessments()

    # PEER REVIEW METHODS

    def show_create_assessment(self):
        """Show create assessment form"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text=_t('gui.academics.assignment_system.assessment_manager.labels.create_assessment', default="Create Assessment"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        form_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_t('gui.academics.assignment_system.assessment_manager.labels.assessment_details', default="Assessment Details"), padding=20)
        form_frame.pack(fill='x', pady=(0, 20))

        # Assessment title
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.title', default="Title:")).grid(row=0, column=0, sticky='w', pady=5)
        self.assessment_title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.assessment_title_var, width=40).grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))

        # Module selection
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.module', default="Module:")).grid(row=1, column=0, sticky='w', pady=5)
        self.assessment_module_var = tk.StringVar()
        module_combo = ttk.Combobox(form_frame, textvariable=self.assessment_module_var, width=35, state='readonly')
        module_combo.grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        self.load_modules(module_combo)

        # Assessment type
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.assessment_type', default="Assessment Type:")).grid(row=2, column=0, sticky='w', pady=5)
        self.assessment_type_var = tk.StringVar(value=_t('gui.academics.assignment_system.assessment_manager.values.exam', default="exam"))
        type_combo = ttk.Combobox(
            form_frame,
            textvariable=self.assessment_type_var,
            values=["exam", "quiz", "test", "project", "presentation", "practical"],
            width=20,
            state='readonly'
        )
        type_combo.grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))
        # Selecting 'exam' reveals the date/time/location fields below.
        type_combo.bind('<<ComboboxSelected>>', self.on_assessment_type_change)

        # Due date/time
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.due_date', default="Due Date:")).grid(row=3, column=0, sticky='w', pady=5)
        default_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        default_time = "23:59"
        self.assessment_due_date_var = tk.StringVar(value=default_date)
        self.assessment_due_time_var = tk.StringVar(value=default_time)
        ttk.Entry(form_frame, textvariable=self.assessment_due_date_var, width=14).grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Entry(form_frame, textvariable=self.assessment_due_time_var, width=8).grid(row=3, column=1, sticky='w', pady=5, padx=(120, 0))

        # Duration
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.duration_minutes', default="Duration (minutes):")).grid(row=4, column=0, sticky='w', pady=5)
        self.assessment_duration_var = tk.StringVar(value="120")
        ttk.Entry(form_frame, textvariable=self.assessment_duration_var, width=10).grid(row=4, column=1, sticky='w', pady=5, padx=(10, 0))

        # Max points
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.max_points', default="Max Points:")).grid(row=5, column=0, sticky='w', pady=5)
        self.assessment_max_points_var = tk.StringVar(value="100")
        ttk.Entry(form_frame, textvariable=self.assessment_max_points_var, width=10).grid(row=5, column=1, sticky='w', pady=5, padx=(10, 0))

        # Weight
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.weight', default="Weight (%):")).grid(row=6, column=0, sticky='w', pady=5)
        self.assessment_weight_var = tk.StringVar(value="25")
        ttk.Entry(form_frame, textvariable=self.assessment_weight_var, width=10).grid(row=6, column=1, sticky='w', pady=5, padx=(10, 0))

        # Status
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.status', default="Status:")).grid(row=7, column=0, sticky='w', pady=5)
        self.assessment_status_var = tk.StringVar(value=_t('gui.academics.assignment_system.assessment_manager.values.active', default="Active"))
        status_combo = ttk.Combobox(
            form_frame,
            textvariable=self.assessment_status_var,
            values=["Active", "Draft", "Archived"],
            width=20,
            state='readonly'
        )
        status_combo.grid(row=7, column=1, sticky='w', pady=5, padx=(10, 0))

        # Exam-only scheduling fields. Built now so the widgets exist, but only
        # packed when the type is 'exam' (see on_assessment_type_change).
        self.exam_details_frame = self._build_exam_details_frame(self.gui.layout.content_area)

        # Description
        desc_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_t('gui.academics.assignment_system.assessment_manager.labels.description_notes', default="Description & Notes"), padding=10)
        desc_frame.pack(fill='both', expand=True, pady=(0, 20))
        self.assessment_desc_frame = desc_frame
        self.assessment_description_text = scrolledtext.ScrolledText(desc_frame, height=6)
        self.assessment_description_text.pack(fill='both', expand=True)

        # Buttons
        button_frame = ttk.Frame(self.gui.layout.content_area)
        button_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(button_frame, text=_t('gui.academics.assignment_system.assessment_manager.buttons.save_assessment', default="Save Assessment"), command=self.save_assessment, style='Accent.TButton').pack(side='left')
        ttk.Button(button_frame, text=_t('gui.academics.assignment_system.assessment_manager.buttons.clear_form', default="Clear Form"), command=self.clear_assessment_form).pack(side='left', padx=(10, 0))
        ttk.Button(button_frame, text=_t('gui.academics.assignment_system.assessment_manager.buttons.manage_assessments', default="Manage Assessments"), command=self.show_manage_assessments).pack(side='right')

        # Status frame for feedback
        self.assessment_status_frame = ttk.Frame(self.gui.layout.content_area)
        self.assessment_status_frame.pack(fill='x', pady=(10, 0))
        self.show_assessment_status("Fill in the details and click 'Save Assessment'.", "info")

        # Last: the type defaults to 'exam', so reveal the scheduling fields on
        # open. Runs after the status frame exists so that populate_exam_choices
        # can report an unavailable exam scheduler, and after the default status
        # message so that warning is not immediately overwritten.
        self._exam_choices_loaded = False
        self.on_assessment_type_change()


    def show_assessment_status(self, message, level="info"):
        """Display a status message for assessment actions."""
        if not hasattr(self, 'assessment_status_frame'):
            return

        for widget in self.assessment_status_frame.winfo_children():
            widget.destroy()

        colors = {
            "success": "#e8f5e9",
            "error": "#ffebee",
            "warning": "#fff8e1",
            "info": "#e3f2fd"
        }
        fg_colors = {
            "success": "#2e7d32",
            "error": "#c62828",
            "warning": "#f57c00",
            "info": "#1565c0"
        }
        bg = colors.get(level, "#e3f2fd")
        fg = fg_colors.get(level, "#1565c0")

        label = ttk.Label(self.assessment_status_frame, text=message, foreground=fg, background=bg)
        label.pack(fill='x', padx=5, pady=5)


    def clear_assessment_form(self):
        """Reset the assessment creation form."""
        if hasattr(self, 'assessment_title_var'):
            self.assessment_title_var.set("")
        if hasattr(self, 'assessment_module_var'):
            self.assessment_module_var.set("")
        if hasattr(self, 'assessment_type_var'):
            self.assessment_type_var.set("exam")
        default_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        if hasattr(self, 'assessment_due_date_var'):
            self.assessment_due_date_var.set(default_date)
        if hasattr(self, 'assessment_due_time_var'):
            self.assessment_due_time_var.set("23:59")
        if hasattr(self, 'assessment_duration_var'):
            self.assessment_duration_var.set("120")
        if hasattr(self, 'assessment_max_points_var'):
            self.assessment_max_points_var.set("100")
        if hasattr(self, 'assessment_weight_var'):
            self.assessment_weight_var.set("25")
        if hasattr(self, 'assessment_status_var'):
            self.assessment_status_var.set("Active")
        if hasattr(self, 'assessment_description_text'):
            self.assessment_description_text.delete("1.0", tk.END)

        # Exam-only fields. The date follows the due date, as it does on build.
        if hasattr(self, 'exam_date_var'):
            self.exam_date_var.set(default_date)
        if hasattr(self, 'exam_start_time_var'):
            self.exam_start_time_var.set("09:00")
        if hasattr(self, 'exam_end_time_var'):
            self.exam_end_time_var.set("11:00")
        if hasattr(self, 'exam_room_var'):
            self.exam_room_var.set("")
        if hasattr(self, 'exam_instructor_var'):
            self.exam_instructor_var.set("")
        # The type resets to 'exam', so re-run the toggle to match.
        self.on_assessment_type_change()

        self.show_assessment_status("Form cleared.", "info")


    def validate_assessment_form(self):
        """Validate the assessment form before saving."""
        if not getattr(self, 'assessment_title_var', tk.StringVar()).get().strip():
            self.show_assessment_status("Assessment title is required.", "error")
            return False

        module_label = getattr(self, 'assessment_module_var', tk.StringVar()).get()
        if not module_label:
            self.show_assessment_status("Please select a module.", "error")
            return False

        try:
            due_str = f"{self.assessment_due_date_var.get().strip()} {self.assessment_due_time_var.get().strip()}"
            due_date = datetime.strptime(due_str, "%Y-%m-%d %H:%M")
            if due_date <= datetime.now():
                self.show_assessment_status("Due date must be in the future.", "error")
                return False
        except ValueError:
            self.show_assessment_status("Invalid due date or time. Use YYYY-MM-DD and HH:MM.", "error")
            return False

        try:
            max_points = float(self.assessment_max_points_var.get())
            if max_points <= 0:
                raise ValueError
        except ValueError:
            self.show_assessment_status("Max points must be a positive number.", "error")
            return False

        try:
            weight = float(self.assessment_weight_var.get())
            if weight < 0:
                raise ValueError
        except ValueError:
            self.show_assessment_status("Weight must be a non-negative number.", "error")
            return False

        try:
            duration = int(self.assessment_duration_var.get())
            if duration <= 0:
                raise ValueError
        except ValueError:
            self.show_assessment_status("Duration must be a positive integer.", "error")
            return False

        if self.assessment_type_var.get() == self.EXAM_TYPE and not self.validate_exam_fields():
            return False

        return True

    def validate_exam_fields(self):
        """Validate the exam-only scheduling fields.

        Mirrors the Exam Scheduling GUI's validate_exam_form: the same date and
        time formats, and a room is required. Reported inline through the
        status strip rather than a messagebox, to match this form.
        """
        try:
            exam_date = datetime.strptime(self.exam_date_var.get().strip(), "%Y-%m-%d")
        except ValueError:
            self.show_assessment_status("Invalid exam date. Use YYYY-MM-DD.", "error")
            return False

        times = {}
        for label, var in (("start", self.exam_start_time_var), ("end", self.exam_end_time_var)):
            try:
                times[label] = datetime.strptime(var.get().strip(), "%H:%M")
            except ValueError:
                self.show_assessment_status(
                    f"Invalid exam {label} time. Use HH:MM.", "error")
                return False

        if times["end"] <= times["start"]:
            self.show_assessment_status(
                "Exam end time must be after the start time.", "error")
            return False

        if exam_date.date() < datetime.now().date():
            self.show_assessment_status("Exam date must not be in the past.", "error")
            return False

        if not self._selected_exam_room():
            self.show_assessment_status("Please select a room for the exam.", "error")
            return False

        return True


    def save_assessment(self):
        """Persist assessment information to the database."""
        if not self.validate_assessment_form():
            return

        self.show_assessment_status("Saving assessment...", "info")
        self.root.update_idletasks()

        title = self.assessment_title_var.get().strip()
        module_label = self.assessment_module_var.get()
        module_code = self.module_map.get(module_label) if hasattr(self, 'module_map') else None
        assessment_type = self.assessment_type_var.get()
        due_str = f"{self.assessment_due_date_var.get().strip()} {self.assessment_due_time_var.get().strip()}"
        max_points = float(self.assessment_max_points_var.get())
        weight = float(self.assessment_weight_var.get())
        duration = int(self.assessment_duration_var.get())
        status = self.assessment_status_var.get()
        description = self.assessment_description_text.get("1.0", tk.END).strip()

        if not module_code:
            self.show_assessment_status("Selected module is invalid.", "error")
            return

        # For an exam, check the room/time clash before writing anything, so a
        # conflict cannot leave an assessment row behind with no exam.
        is_exam = assessment_type == self.EXAM_TYPE
        if is_exam and not self.check_exam_availability(module_code):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            self.gui.db.ensure_assessment_schema(cursor)

            cursor.execute(
                """
                INSERT INTO assessments (
                    assessment_name, assessment_type, module_code,
                    max_points, weight, due_date, description, rubric,
                    duration_minutes, status, date_created, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    title, assessment_type, module_code,
                    max_points, weight, due_str, description, None,
                    duration, status
                )
            )

            assessment_id = cursor.lastrowid
            conn.commit()
            conn.close()

            message = f"Assessment '{title}' created successfully (ID: {assessment_id})."
            level = "success"

            if is_exam:
                exam_id, exam_note = self.schedule_exam_for_assessment(
                    assessment_id, module_code, title)
                message += exam_note
                if exam_id is None:
                    # The assessment saved but the exam did not. Say so plainly
                    # rather than reporting an unqualified success.
                    level = "warning"

            self.show_assessment_status(message, level)
            self.clear_assessment_form()

            # Refresh manage view if open
            if hasattr(self, 'assessment_tree') and self.assessment_tree.winfo_exists():
                self.load_assessments_data()
        except Exception as exc:
            self.show_assessment_status(f"Failed to save assessment: {exc}", "error")


    def check_exam_availability(self, module_code):
        """Check the room/time slot before committing anything.

        Returns True when it is safe to proceed. Same two checks the Exam
        Scheduling GUI runs on Add Exam: the exam table's own clash check, then
        the shared room_bookings / lecture timetable cross-check, which is a
        confirmable warning rather than a hard stop.
        """
        dm = self._exam_data_manager()
        if dm is None:
            # Availability cannot be established. Let the operator decide
            # rather than silently skipping the check.
            return messagebox.askyesno(
                _t('gui.academics.assignment_system.assessment_manager.dialogs.exam_unavailable',
                    default="Exam scheduling unavailable"),
                "The exam scheduler could not be loaded, so the room and time "
                "cannot be checked for clashes.\n\nSave the assessment without "
                "scheduling an exam?",
            )

        date = self.exam_date_var.get().strip()
        start = self.exam_start_time_var.get().strip()
        end = self.exam_end_time_var.get().strip()
        room = self._selected_exam_room()

        if dm.check_conflict(date, start, end, room):
            self.show_assessment_status(
                f"Scheduling conflict: {room} is already booked for an exam "
                f"on {date} between {start} and {end}.", "error")
            return False

        try:
            external = dm.find_external_room_conflicts(date, start, end, room)
        except Exception:
            external = None
        if external:
            detail = "\n".join(f"  • {item}" for item in external)
            return messagebox.askyesno(
                _t('gui.academics.assignment_system.assessment_manager.dialogs.room_in_use',
                    default="Room already booked"),
                f"{room} has other bookings in that slot:\n\n{detail}\n\n"
                f"Schedule the exam anyway?",
            )

        return True

    def schedule_exam_for_assessment(self, assessment_id, module_code, title):
        """Create the `exams` row for a saved assessment.

        Returns ``(exam_id, note)``. ``exam_id`` is None when the exam could
        not be created — the assessment itself is already saved by then, so the
        note explains what is missing rather than the failure being swallowed.
        """
        dm = self._exam_data_manager()
        if dm is None:
            return None, "\n\nNo exam was scheduled: the exam scheduler is unavailable."

        try:
            from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.models import Exam

            module = dm.lookup_module(module_code) or {}
            instructor_id, instructor_name = self._selected_exam_instructor()

            # Derive the roster at save time so the snapshot matches current
            # enrolment, exactly as the Exam Scheduling GUI does.
            roster_ids = [s['student_id'] for s in dm.get_enrolled_students(module_code)]

            exam = Exam(
                id=dm.get_next_exam_id(),
                module_code=module_code,
                module_name=module.get('module_name') or title,
                date=self.exam_date_var.get().strip(),
                start_time=self.exam_start_time_var.get().strip(),
                end_time=self.exam_end_time_var.get().strip(),
                room=self._selected_exam_room(),
                instructor_id=instructor_id,
                instructor_name=instructor_name,
                students_enrolled=len(roster_ids),
                enrolled_student_ids=roster_ids,
            )
            dm.add_exam(exam)
        except Exception as exc:
            return None, f"\n\nThe assessment was saved, but the exam could not be scheduled: {exc}"

        self.last_created_exam_id = exam.id
        note = f"\n\n✓ Exam scheduled in {exam.room} on {exam.date} at {exam.start_time}."

        # Link the two rows so the assessment knows which exam it created.
        try:
            link_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            with link_conn:
                link_conn.execute(
                    "UPDATE assessments SET exam_id = ? WHERE assessment_id = ?",
                    (exam.id, assessment_id),
                )
            link_conn.close()
        except Exception as exc:
            note += f"\n⚠ Could not link the assessment to exam {exam.id}: {exc}"

        # The remaining steps are the same side effects Add Exam performs.
        # Each is best-effort: a failure here must not undo a scheduled exam.
        try:
            from education_system.systems.university.infrastructure.event_bus import (
                publish, EVENT_EXAM_CHANGED, EVENT_CALENDAR_CHANGED,
            )
        except Exception:
            publish = None

        if publish is not None:
            try:
                publish(EVENT_EXAM_CHANGED, exam_id=exam.id,
                        module_code=module_code, action="create")
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        try:
            if dm.add_exam_to_calendar(exam):
                note += "\n✓ Added to the academic calendar."
                if publish is not None:
                    try:
                        publish(EVENT_CALENDAR_CHANGED, event_type="Exam",
                                source_id=exam.id, action="create")
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        try:
            if dm.reserve_room_for_exam(exam):
                note += "\n✓ Room reserved in shared bookings."
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        return exam.id, note

    def show_manage_assessments(self):
        """Show assessment management interface"""
        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text=_t('gui.academics.assignment_system.assessment_manager.labels.manage_assessments', default="Manage Assessments"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Create assessments table
        assessments_frame = ttk.Frame(self.gui.layout.content_area)
        assessments_frame.pack(fill='both', expand=True)

        # Treeview for assessments
        columns = ('ID', 'Title', 'Module', 'Type', 'Due Date', 'Max Points', 'Weight', 'Status')
        tree = ttk.Treeview(assessments_frame, columns=columns, show='headings')

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120 if col in ('Title', 'Module') else 100)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(assessments_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=v_scrollbar.set)
        tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')

        assessments_frame.grid_rowconfigure(0, weight=1)
        assessments_frame.grid_columnconfigure(0, weight=1)

        self.assessment_tree = tree
        self.load_assessments_data()

        # Buttons frame
        buttons_frame = ttk.Frame(self.gui.layout.content_area)
        buttons_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assessment_manager.buttons.edit_assessment', default="Edit Assessment"), command=self.edit_assessment).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assessment_manager.buttons.delete_assessment', default="Delete Assessment"), command=self.delete_assessment).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assessment_manager.buttons.view_details', default="View Details"), command=self.view_assessment_results).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text=_t('gui.academics.assignment_system.assessment_manager.buttons.sync_from_assignments', default="🔄 Sync from Assignments"),
                  command=self.sync_assignments_to_assessments,
                  style='Accent.TButton').pack(side='right')


    def load_assessments_data(self):
        """Load assessments into the management treeview."""
        if not hasattr(self, 'assessment_tree'):
            return

        tree = self.assessment_tree
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT assessment_id, assessment_name, assessment_type, module_code,
                       max_points, weight, due_date, duration_minutes, status
                FROM assessments
                ORDER BY date_created DESC
                """
            )
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                due = row['due_date'] or ''
                try:
                    due_display = datetime.strptime(due, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
                except Exception:
                    due_display = due

                tree.insert(
                    '', 'end',
                    values=(
                        row['assessment_id'],
                        row['assessment_name'],
                        row['module_code'],
                        row['assessment_type'],
                        due_display,
                        row['max_points'],
                        row['weight'],
                        row['status'] or 'Active'
                    )
                )

            if not rows:
                tree.insert('', 'end', values=('–', 'No assessments found', '', '', '', '', '', ''))
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.error', default="Error"), f"Failed to load assessments: {exc}")


    def edit_assessment(self):
        """Edit selected assessment"""
        if not self._check_permission('manage_assignments'):
            return
        if not hasattr(self, 'assessment_tree') or not self.assessment_tree.get_children():
            messagebox.showwarning(_t('gui.academics.assignment_system.assessment_manager.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assessment_manager.dialogs.no_assessments_to_edit', default="No assessments to edit."))
            return

        selection = self.assessment_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.assessment_manager.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assessment_manager.dialogs.please_select_an_assessment_to_edit', default="Please select an assessment to edit."))
            return

        assessment_id = self.assessment_tree.item(selection[0])['values'][0]
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM assessments WHERE assessment_id = ?",
                (assessment_id,)
            )
            record = cursor.fetchone()
            conn.close()
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.error', default="Error"), f"Failed to load assessment: {exc}")
            return

        if not record:
            messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.error', default="Error"), _t('gui.academics.assignment_system.assessment_manager.dialogs.selected_assessment_no_longer_exists', default="Selected assessment no longer exists."))
            return

        editor = make_toplevel(self.root)
        editor.title(f"Edit Assessment - {record['assessment_name']}")
        editor.geometry("500x520")
        editor.transient(self.root)
        editor.grab_set()

        form_frame = ttk.Frame(editor, padding=20)
        form_frame.pack(fill='both', expand=True)

        title_var = tk.StringVar(value=record['assessment_name'])
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.title', default="Title:")).grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(form_frame, textvariable=title_var, width=40).grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))

        module_var = tk.StringVar()
        module_combo = ttk.Combobox(form_frame, textvariable=module_var, width=35, state='readonly')
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.module', default="Module:")).grid(row=1, column=0, sticky='w', pady=5)
        module_combo.grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        self.load_modules(module_combo)
        for label, code in getattr(self, 'module_map', {}).items():
            if code == record['module_code']:
                module_var.set(label)
                break

        type_var = tk.StringVar(value=record['assessment_type'])
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.type', default="Type:")).grid(row=2, column=0, sticky='w', pady=5)
        type_combo = ttk.Combobox(form_frame, textvariable=type_var, values=["exam", "quiz", "test", "project", "presentation", "practical"], state='readonly', width=20)
        type_combo.grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))

        due = record['due_date'] or ''
        try:
            due_dt = datetime.strptime(due, "%Y-%m-%d %H:%M")
            due_date_default = due_dt.strftime("%Y-%m-%d")
            due_time_default = due_dt.strftime("%H:%M")
        except Exception:
            due_date_default = datetime.now().strftime("%Y-%m-%d")
            due_time_default = "23:59"

        due_date_var = tk.StringVar(value=due_date_default)
        due_time_var = tk.StringVar(value=due_time_default)
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.due_date', default="Due Date:")).grid(row=3, column=0, sticky='w', pady=5)
        attach_date(form_frame, id_var=due_date_var).grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        attach_combo(form_frame, time_values(step_minutes=15, start_hour=0, end_hour=23),
                     textvariable=due_time_var, width=7).grid(row=3, column=2, sticky='w', pady=5, padx=(10, 0))

        max_points_var = tk.StringVar(value=str(record['max_points']))
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.max_points', default="Max Points:")).grid(row=4, column=0, sticky='w', pady=5)
        ttk.Entry(form_frame, textvariable=max_points_var, width=10).grid(row=4, column=1, sticky='w', pady=5, padx=(10, 0))

        weight_var = tk.StringVar(value=str(record['weight']))
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.weight', default="Weight (%):")).grid(row=5, column=0, sticky='w', pady=5)
        ttk.Entry(form_frame, textvariable=weight_var, width=10).grid(row=5, column=1, sticky='w', pady=5, padx=(10, 0))

        duration_var = tk.StringVar(value=str(record.get('duration_minutes', 0)))
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.duration_minutes', default="Duration (minutes):")).grid(row=6, column=0, sticky='w', pady=5)
        ttk.Entry(form_frame, textvariable=duration_var, width=10).grid(row=6, column=1, sticky='w', pady=5, padx=(10, 0))

        status_var = tk.StringVar(value=record.get('status', 'Active'))
        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.status', default="Status:")).grid(row=7, column=0, sticky='w', pady=5)
        status_combo = ttk.Combobox(form_frame, textvariable=status_var, values=["Active", "Draft", "Archived"], state='readonly', width=20)
        status_combo.grid(row=7, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t('gui.academics.assignment_system.assessment_manager.labels.description', default="Description:")).grid(row=8, column=0, sticky='nw', pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=40)
        desc_text.grid(row=8, column=1, sticky='w', pady=5, padx=(10, 0))
        if record['description']:
            desc_text.insert(tk.END, record['description'])

        def save_changes():
            try:
                module_label = module_var.get()
                module_code = self.module_map.get(module_label)
                if not module_code:
                    raise ValueError("Invalid module selection")

                due_text = f"{due_date_var.get().strip()} {due_time_var.get().strip()}"
                due_dt = datetime.strptime(due_text, "%Y-%m-%d %H:%M")
                if due_dt <= datetime.now():
                    raise ValueError("Due date must be in the future")

                max_points = float(max_points_var.get())
                weight = float(weight_var.get())
                duration = int(duration_var.get())

                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE assessments
                        SET assessment_name = ?, assessment_type = ?, module_code = ?,
                            max_points = ?, weight = ?, due_date = ?, description = ?,
                            duration_minutes = ?, status = ?, updated_at = datetime('now')
                        WHERE assessment_id = ?
                        """,
                        (
                            title_var.get().strip(),
                            type_var.get(),
                            module_code,
                            max_points,
                            weight,
                            due_text,
                            desc_text.get("1.0", tk.END).strip(),
                            duration,
                            status_var.get(),
                            assessment_id
                        )
                    )
                    conn.commit()
                finally:
                    conn.close()

                editor.destroy()
                self.load_assessments_data()
                messagebox.showinfo(_t('gui.academics.assignment_system.assessment_manager.dialogs.success', default="Success"), _t('gui.academics.assignment_system.assessment_manager.dialogs.assessment_updated_successfully', default="Assessment updated successfully."))
            except ValueError as ve:
                messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.validation_error', default="Validation Error"), str(ve))
            except Exception as exc:
                messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.error', default="Error"), f"Failed to update assessment: {exc}")

        button_frame = ttk.Frame(editor)
        button_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(button_frame, text=_t('gui.academics.assignment_system.assessment_manager.buttons.save_changes', default="Save Changes"), command=save_changes, style='Accent.TButton').pack(side='left')
        ttk.Button(button_frame, text=_t('gui.academics.assignment_system.assessment_manager.buttons.cancel', default="Cancel"), command=editor.destroy).pack(side='right')


    def delete_assessment(self):
        """Delete selected assessment"""
        if not self._check_permission('manage_assignments'):
            return
        if not hasattr(self, 'assessment_tree') or not self.assessment_tree.get_children():
            messagebox.showwarning(_t('gui.academics.assignment_system.assessment_manager.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assessment_manager.dialogs.no_assessments_to_delete', default="No assessments to delete."))
            return

        selection = self.assessment_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.assessment_manager.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assessment_manager.dialogs.please_select_an_assessment_to_delete', default="Please select an assessment to delete."))
            return

        assessment_id, title = self.assessment_tree.item(selection[0])['values'][:2]
        if not messagebox.askyesno(_t('gui.academics.assignment_system.assessment_manager.dialogs.confirm', default="Confirm"), f"Delete assessment '{title}' (ID: {assessment_id})? This action cannot be undone."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM assessment_outcomes WHERE assessment_id = ?', (assessment_id,))
            cursor.execute('DELETE FROM assessment_competencies WHERE assessment_id = ?', (assessment_id,))
            cursor.execute('DELETE FROM assessments WHERE assessment_id = ?', (assessment_id,))
            conn.commit()
            conn.close()

            self.load_assessments_data()
            messagebox.showinfo(_t('gui.academics.assignment_system.assessment_manager.dialogs.success', default="Success"), _t('gui.academics.assignment_system.assessment_manager.dialogs.assessment_deleted_successfully', default="Assessment deleted successfully."))
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.error', default="Error"), f"Failed to delete assessment: {exc}")


    def view_assessment_results(self):
        if not self._check_permission('manage_assignments'):
            return
        if not hasattr(self, 'assessment_tree') or not self.assessment_tree.get_children():
            messagebox.showwarning(_t('gui.academics.assignment_system.assessment_manager.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assessment_manager.dialogs.no_assessments_available', default="No assessments available."))
            return

        selection = self.assessment_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.assignment_system.assessment_manager.dialogs.warning', default="Warning"), _t('gui.academics.assignment_system.assessment_manager.dialogs.please_select_an_assessment_to_view', default="Please select an assessment to view."))
            return

        assessment_id = self.assessment_tree.item(selection[0])['values'][0]
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM assessments WHERE assessment_id = ?', (assessment_id,))
            record = cursor.fetchone()
            if not record:
                conn.close()
                messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.error', default="Error"), _t('gui.academics.assignment_system.assessment_manager.dialogs.assessment_record_not_found', default="Assessment record not found."))
                return

            cursor.execute('SELECT COUNT(*) FROM assessment_outcomes WHERE assessment_id = ?', (assessment_id,))
            outcome_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM assessment_competencies WHERE assessment_id = ?', (assessment_id,))
            competency_count = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) as submissions,
                       AVG(grade) as avg_grade,
                       SUM(CASE WHEN grade IS NOT NULL THEN 1 ELSE 0 END) as graded
                FROM assignment_submissions s
                JOIN assignments a ON s.assignment_id = a.id
                WHERE a.module_code = ?
                """,
                (record['module_code'],)
            )
            submission_stats = cursor.fetchone()
            conn.close()

            window = make_toplevel(self.root)
            window.title(f"Assessment Details - {record['assessment_name']}")
            window.geometry("520x420")
            window.transient(self.root)
            window.grab_set()

            text = scrolledtext.ScrolledText(window, wrap=tk.WORD)
            text.pack(fill='both', expand=True, padx=10, pady=10)

            text.insert(tk.END, f"ASSESSMENT DETAILS\n{'='*50}\n\n")
            text.insert(tk.END, f"ID: {record['assessment_id']}\n")
            text.insert(tk.END, f"Title: {record['assessment_name']}\n")
            text.insert(tk.END, f"Module: {record['module_code']}\n")
            text.insert(tk.END, f"Type: {record['assessment_type']}\n")
            text.insert(tk.END, f"Due Date: {record['due_date'] or 'N/A'}\n")
            text.insert(tk.END, f"Max Points: {record['max_points']}\n")
            text.insert(tk.END, f"Weight: {record['weight']}%\n")
            text.insert(tk.END, f"Duration: {record.get('duration_minutes', 0)} minutes\n")
            text.insert(tk.END, f"Status: {record.get('status', 'Active')}\n")
            text.insert(tk.END, f"Created: {record.get('date_created', 'N/A')}\n")
            text.insert(tk.END, f"Updated: {record.get('updated_at', 'N/A')}\n\n")

            if record['description']:
                text.insert(tk.END, "Description:\n")
                text.insert(tk.END, record['description'] + "\n\n")

            text.insert(tk.END, f"Learning Outcomes Linked: {outcome_count}\n")
            text.insert(tk.END, f"Competencies Linked: {competency_count}\n\n")

            if submission_stats:
                submissions, avg_grade, graded = submission_stats
                text.insert(tk.END, "Submission Summary (by module):\n")
                text.insert(tk.END, f"Total Submissions: {submissions}\n")
                text.insert(tk.END, f"Graded Submissions: {graded}\n")
                avg_display = f"{avg_grade:.2f}%" if avg_grade is not None else "N/A"
                text.insert(tk.END, f"Average Grade: {avg_display}\n")

            text.config(state='disabled')
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.error', default="Error"), f"Failed to view assessment details: {exc}")

    def sync_assignments_to_assessments(self):
        """Sync assignments from the assignments table to assessments table"""
        try:
            # Get all assignments
            assignments = AssessmentAssignmentService.get_all_assignments()

            if not assignments:
                messagebox.showinfo(_t('gui.academics.assignment_system.assessment_manager.dialogs.sync_complete', default="Sync Complete"), _t('gui.academics.assignment_system.assessment_manager.dialogs.no_assignments_found_to_sync', default="No assignments found to sync"))
                return

            synced_count = 0
            skipped_count = 0

            for assignment in assignments:
                # Try to sync each assignment
                assessment_id = AssessmentAssignmentService.sync_assignment_to_assessment(
                    assignment['id']
                )
                if assessment_id:
                    synced_count += 1
                else:
                    skipped_count += 1

            # Reload the assessments display
            self.load_assessments_data()

            messagebox.showinfo(
                _t('gui.academics.assignment_system.assessment_manager.dialogs.sync_complete', default="Sync Complete"),
                f"Synced {synced_count} assignment(s) to assessments.\n"
                f"Skipped {skipped_count} (already exist or invalid)."
            )

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assessment_manager.dialogs.sync_error', default="Sync Error"), f"Failed to sync assignments: {e}")

