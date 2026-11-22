"""Methods save_schedule through center_window."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import dialogs_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AddScheduleDialog:
    def save_schedule(self):
        try:
            # The dropdown shows "CODE - Module name" now that it is
            # scoped by course; the schedule stores the bare code.
            module_code = self.module_var.get().split(" - ", 1)[0].strip()
            day = self.day_var.get()
            start_time = self.start_time_var.get()
            end_time = self.end_time_var.get()
            room_str = self.room_var.get()
            instructor_str = self.instructor_var.get()
            session_type = self.session_type_var.get()

            if not all([module_code, day, start_time, end_time, room_str, instructor_str, session_type]):
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_save_schedule.dialogs.error', default="Error"), _t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_save_schedule.dialogs.please_fill_in_all_fields', default="Please fill in all fields."), parent=self.dialog)
                return

            # Extract IDs
            room_id = int(room_str.split(' - ')[0])
            instructor_id = int(instructor_str.split(' - ')[0])

            # Cross-model clash check: the module scheduler's own check_conflicts
            # only sees other module_schedule rows. This also warns when the room
            # is used at the same time by a Course Management section meeting.
            try:
                from education_system.systems.university.domains.teaching.domain.timetable_bridge import (
                    find_timetable_conflicts,
                )
                room_label = room_str.split(' - ', 1)[1] if ' - ' in room_str else room_str
                section_clashes = [
                    c for c in find_timetable_conflicts(
                        day, start_time, end_time, location=room_label, room_id=room_id)
                    if c.startswith("Section ")]
            except Exception:
                section_clashes = []
            if section_clashes and self.status_var.get() != "draft":
                if not messagebox.askyesno(
                        _t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_save_schedule.dialogs.section_clash', default="Section clash"),
                        "This room/time clashes with course section meetings:\n\n"
                        + "\n".join(f"  • {c}" for c in section_clashes[:6])
                        + "\n\nSave anyway?",
                        icon='warning', parent=self.dialog):
                    return

            # Check for conflicts before saving
            self.check_conflicts()

            # Check if there are actual conflicts
            conflict_message = self.conflict_text.get(1.0, tk.END).strip()
            # Drafts are allowed to overlap published rows (that's the whole
            # point of a what-if scenario), so skip the conflict prompt for
            # them. Published saves still surface the warning.
            if (conflict_message and not conflict_message.startswith("✓")
                    and self.status_var.get() != "draft"):
                response = messagebox.askyesno(
                    _t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_save_schedule.dialogs.conflicts_detected', default="Conflicts Detected"),
                    "There are scheduling conflicts:\n\n" + conflict_message + "\n\nDo you want to save anyway?",
                    icon='warning',
                    parent=self.dialog,
                )
                if not response:
                    return

            # Validate the optional recurrence-until date if the user filled
            # it in — empty is fine (= open-ended), garbage isn't.
            rec_until = (self.recurrence_until_var.get() or "").strip() or None
            if rec_until:
                try:
                    datetime.strptime(rec_until, "%Y-%m-%d")
                except ValueError:
                    messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_save_schedule.dialogs.error', default="Error"),
                                         _t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_save_schedule.dialogs.recurrence_end_date_must_be_yyyy_mm_dd_or_blank', default="Recurrence end date must be YYYY-MM-DD or blank."),
                                         parent=self.dialog)
                    return

            try:
                year_int = int(self.year_var.get())
            except (TypeError, ValueError):
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_save_schedule.dialogs.error', default="Error"), _t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_save_schedule.dialogs.year_must_be_a_whole_number', default="Year must be a whole number."),
                                     parent=self.dialog)
                return

            # Resolve the calling user for the audit trail. Prefer the gui's
            # auth context; fall back to a generic 'gui' marker.
            changed_by = "gui"
            try:
                if self.gui and hasattr(self.gui, "auth") and self.gui.auth:
                    user = getattr(self.gui.auth, "current_user", None)
                    if isinstance(user, dict):
                        changed_by = str(user.get("username") or user.get("user_id") or "gui")
                    elif user and hasattr(user, "username"):
                        changed_by = str(user.username)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            # Save schedule
            success = self.scheduler.add_module_schedule(
                module_code, day, start_time, end_time, room_id, instructor_id, session_type,
                semester=self.semester_var.get(),
                year=year_int,
                status=self.status_var.get(),
                recurrence=self.recurrence_var.get(),
                recurrence_until=rec_until,
                changed_by=changed_by,
            )

            if success:
                # Notify open sibling GUIs that a schedule changed.
                try:
                    from education_system.systems.university.infrastructure.event_bus import (
                        publish, EVENT_MODULE_SCHEDULE_CHANGED,
                    )
                    publish(EVENT_MODULE_SCHEDULE_CHANGED,
                            module_code=module_code, action="create")
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

                # Send notifications to instructor and students — ONLY for
                # published rows. Drafts are silent so what-if scenarios
                # don't email students about classes that may never run.
                if self.status_var.get() == "draft":
                    self.result = True
                    self.dialog.destroy()
                    return
                try:
                    # Get module info for the notification
                    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                        cursor = conn.cursor()

                        # Get module name if available
                        cursor.execute('SELECT module_name FROM modules WHERE module_code = ?', (module_code,))
                        module_result = cursor.fetchone()
                        module_name = module_result[0] if module_result else module_code

                        # Get instructor email
                        cursor.execute('SELECT email, first_name, last_name FROM instructors WHERE id = ?', (instructor_id,))
                        instructor = cursor.fetchone()

                        # Get room info
                        cursor.execute('SELECT building, room_number FROM rooms WHERE id = ?', (room_id,))
                        room_info = cursor.fetchone()
                        room_str = f"{room_info[0]}-{room_info[1]}" if room_info else "TBA"

                        # Create notification message
                        message = f"A new class has been scheduled:\n\n{module_name} ({module_code})\n{day} {start_time}-{end_time}\nRoom: {room_str}"

                        # Email all students and instructor using the new function
                        try:
                            target = self.gui or self.parent
                            summary = target.email_all_students_on_module(
                                module_code,
                                f"New Class Schedule: {module_code}",
                                message,
                                include_instructor=True
                            )
                            print(f"Emails sent: {summary['students_emailed']} students, instructor: {summary['instructor_emailed']}")
                            if summary['errors']:
                                for error in summary['errors']:
                                    print(f"  - {error}")
                        except Exception as e:
                            print(f"Note: Notifications may not have been sent: {e}")

                        conn.commit()

                except Exception as notif_error:
                    # Don't fail the save if notifications fail
                    print(f"Note: Notifications may not have been sent: {notif_error}")

                self.result = True
                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_save_schedule.dialogs.error', default="Error"), f"Failed to save schedule: {str(e)}", parent=self.dialog)

    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
