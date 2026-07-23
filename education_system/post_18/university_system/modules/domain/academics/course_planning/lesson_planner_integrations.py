"""Cross-system integrations for the University Lesson Planner.

The planner is otherwise a self-contained weekly-timetable tool. This
module is the single seam through which it reaches the rest of the
university system: the event bus, room booking, equipment, curriculum
spec, attendance, tutor groups/advising, staff-HR, communications,
export, analytics/KPIs, audit, and permissions.

Design rules (so the planner never breaks when a subsystem moves or is
absent — it is sometimes launched as a bare subprocess):

* Every connector imports its dependency lazily, inside the method.
* Every connector is wrapped so a failure logs at debug and returns a
  benign default (None / False / [] / a status dict) — never raises.
* No connector blocks the GUI on import.

Lessons are weekly templates: ``day`` is a weekday name and
``start``/``end`` are ``HH:MM``. Connectors that need an absolute date
(room booking, attendance) accept one, defaulting to the next
occurrence of the lesson's weekday.
"""

import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


# Weekday-name → Python weekday() index and iCalendar BYDAY token.
_WEEKDAYS = {
    "Monday": (0, "MO"), "Tuesday": (1, "TU"), "Wednesday": (2, "WE"),
    "Thursday": (3, "TH"), "Friday": (4, "FR"), "Saturday": (5, "SA"),
    "Sunday": (6, "SU"),
}


def _course_code(lesson):
    """Extract the bare course code from a planner lesson's ``course``
    field, which is stored as ``"CODE - Course Name"``."""
    raw = (lesson or {}).get("course", "") or ""
    return raw.split(" - ", 1)[0].strip() or raw.strip()


def _next_date_for_day(day_name, *, today=None):
    """Return the YYYY-MM-DD of the next occurrence of ``day_name``
    (today counts). Falls back to today for unknown names."""
    today = today or date.today()
    target = _WEEKDAYS.get(day_name, (today.weekday(), ""))[0]
    delta = (target - today.weekday()) % 7
    return (today + timedelta(days=delta)).isoformat()


class PlannerIntegrations:
    """Facade over every external subsystem the planner touches.

    Construct once per app with the signed-in user dict; call the
    connector methods as needed. All methods are safe to call even when
    the backing subsystem is unavailable.
    """

    def __init__(self, user=None, user_display="", db_path=None):
        self.user = user or {}
        self.user_display = user_display or ""
        self._db_path = db_path or self._resolve_db_path()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_db_path():
        try:
            from education_system.post_18.university_system.core import paths
            return str(paths.DEFAULT_DB_PATH)
        except Exception:
            logger.debug("Could not resolve DEFAULT_DB_PATH", exc_info=True)
            return None

    def _user_id_int(self):
        for key in ("user_id", "id"):
            val = self.user.get(key)
            if val is None:
                continue
            try:
                return int(val)
            except (TypeError, ValueError):
                return None
        return None

    # ------------------------------------------------------------------
    # 1. Event bus  (publish lesson/timetable events, read exam conflicts)
    # ------------------------------------------------------------------
    def publish_lesson_event(self, action, lesson):
        """Fan out a lesson create/update/delete onto the integration
        bus so timetable-aware consumers (exams, attendance) can react."""
        try:
            from education_system.post_18.university_system.modules.services.integration_bus import (
                log_and_publish,
            )
            from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import (
                EVENT_MODULE_SCHEDULE_CHANGED,
            )
            log_and_publish(
                EVENT_MODULE_SCHEDULE_CHANGED,
                source="lesson_planner",
                action=f"lesson_{action}",
                course_code=_course_code(lesson),
                title=lesson.get("title"),
                day=lesson.get("day"),
                start=lesson.get("start"),
                end=lesson.get("end"),
                room=lesson.get("room"),
                instructor=lesson.get("instructor"),
                actor=self.user_display,
            )
            return True
        except Exception:
            logger.debug("publish_lesson_event failed", exc_info=True)
            return False

    def publish_timetable_locked(self, user_ids=None, *, academic_year=None,
                                 semester=None):
        """Reuse the canonical timetable-lock fan-out."""
        try:
            from education_system.post_18.university_system.modules.services.integration_bus import (
                publish_timetable_locked,
            )
            publish_timetable_locked(
                [str(u) for u in (user_ids or [])],
                academic_year=academic_year, semester=semester,
            )
            return True
        except Exception:
            logger.debug("publish_timetable_locked failed", exc_info=True)
            return False

    def find_exam_conflicts(self, lessons):
        """Scan recent ``exam.changed`` bus events and flag any whose
        scheduled slot collides with a planned lesson on the same day.
        Best-effort overlay — returns a list of conflict dicts."""
        conflicts = []
        try:
            from education_system.post_18.university_system.modules.services.integration_bus import (
                recent_events,
            )
            exams = [e for e in recent_events(200)
                     if e.get("event_name") == "exam.changed"]
            for ev in exams:
                p = ev.get("payload", {})
                start = p.get("start_time") or ""
                # start_time may be a full timestamp "YYYY-MM-DD HH:MM[:SS]"
                ex_day = ex_hhmm = None
                try:
                    dt = datetime.fromisoformat(start.replace("Z", ""))
                    ex_day = list(_WEEKDAYS)[dt.weekday()]
                    ex_hhmm = dt.strftime("%H:%M")
                except Exception:
                    continue
                for lesson in lessons:
                    if lesson.get("day") != ex_day:
                        continue
                    if lesson.get("start", "") <= ex_hhmm < lesson.get("end", ""):
                        conflicts.append({
                            "lesson": lesson.get("title"),
                            "exam": p.get("exam_title") or p.get("module_code"),
                            "day": ex_day, "time": ex_hhmm,
                        })
        except Exception:
            logger.debug("find_exam_conflicts failed", exc_info=True)
        return conflicts

    # ------------------------------------------------------------------
    # 2. Room booking + capacity (campus.room_booking / facilities)
    # ------------------------------------------------------------------
    def find_available_rooms(self, lesson, *, on_date=None, capacity_min=None,
                             equipment_csv=""):
        """List rooms free for the lesson's slot on a concrete date."""
        try:
            from education_system.post_18.university_system.modules.domain.campus.room_booking.services.room_booking_service import (
                RoomBookingService,
            )
            on_date = on_date or _next_date_for_day(lesson.get("day"))
            svc = RoomBookingService(db_path=self._db_path)
            return svc.find_available_rooms(
                f"{on_date} {lesson.get('start')}",
                f"{on_date} {lesson.get('end')}",
                capacity_min=capacity_min,
                equipment_csv=equipment_csv,
            )
        except Exception:
            logger.debug("find_available_rooms failed", exc_info=True)
            return []

    def reserve_room(self, lesson, room_id, *, on_date=None):
        """Reserve a real room for a lesson; returns booking_id or None.
        Room-booking owns the cross-university clash detection."""
        try:
            from education_system.post_18.university_system.modules.domain.campus.room_booking.services.room_booking_service import (
                RoomBookingService, RoomBookingError,
            )
            on_date = on_date or _next_date_for_day(lesson.get("day"))
            svc = RoomBookingService(db_path=self._db_path)
            try:
                return svc.create_booking(
                    room_id=int(room_id),
                    start_datetime=f"{on_date} {lesson.get('start')}",
                    end_datetime=f"{on_date} {lesson.get('end')}",
                    booked_by=self.user_display or "lesson_planner",
                    purpose=f"{lesson.get('type', 'Lesson')}: {lesson.get('title', '')}",
                    equipment_needed="",
                    booking_type="class",
                )
            except RoomBookingError as exc:
                logger.info("Room reservation clash/validation: %s", exc)
                return None
        except Exception:
            logger.debug("reserve_room failed", exc_info=True)
            return None

    def check_room_capacity(self, room_type="", min_capacity=0):
        """Return rooms matching a type/capacity (status-based, not
        time-based) from facilities management."""
        try:
            from education_system.post_18.university_system.modules.domain.campus.facilities.services.facilities_management_core import (
                RoomManager,
            )
            return RoomManager.get_available_rooms(
                room_type=room_type, min_capacity=min_capacity)
        except Exception:
            logger.debug("check_room_capacity failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # 3. Equipment reservation (campus.equipment)
    # ------------------------------------------------------------------
    def list_equipment(self, category=None):
        try:
            from education_system.post_18.university_system.modules.domain.campus.equipment.services.equipment_core import (
                EquipmentManager,
            )
            return EquipmentManager.get_available_items(category=category)
        except Exception:
            logger.debug("list_equipment failed", exc_info=True)
            return []

    def reserve_equipment(self, lesson, item_id, *, on_date=None, quantity=1,
                          daily_rate=0.0):
        """Reserve a piece of equipment for a lesson; returns rental_id."""
        try:
            from education_system.post_18.university_system.modules.domain.campus.equipment.services.equipment_core import (
                RentalManager,
            )
            on_date = on_date or _next_date_for_day(lesson.get("day"))
            return RentalManager.create_rental(
                item_id=int(item_id),
                borrower_id=str(self.user.get("user_id") or self.user.get("id") or "planner"),
                borrower_name=self.user_display or "Lesson Planner",
                checkout_date=on_date, checkout_time=lesson.get("start", "09:00"),
                due_date=on_date, due_time=lesson.get("end", "10:00"),
                daily_rate=float(daily_rate), quantity=int(quantity),
                purpose=f"Lesson: {lesson.get('title', '')}",
            )
        except Exception:
            logger.debug("reserve_equipment failed", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # 4. Curriculum spec validation (academics.curriculum_specification)
    # ------------------------------------------------------------------
    def validate_contact_hours(self, course_code, planned_weekly_hours):
        """Compare planned weekly contact hours for a course against the
        approved curriculum descriptor. Returns a verdict dict."""
        try:
            from education_system.post_18.university_system.modules.domain.academics.curriculum_specification.services.curriculum_specification_service import (
                CurriculumSpecificationService,
            )
            svc = CurriculumSpecificationService()
            approved = None
            for mod in svc.list_module_descriptors():
                if str(mod.get("module_code", "")).upper() == str(course_code).upper():
                    approved = mod.get("contact_hours")
                    break
            if approved is None:
                return {"known": False, "course_code": course_code,
                        "planned": planned_weekly_hours}
            return {
                "known": True, "course_code": course_code,
                "approved_contact_hours": approved,
                "planned": planned_weekly_hours,
                "ok": float(planned_weekly_hours) <= float(approved),
            }
        except Exception:
            logger.debug("validate_contact_hours failed", exc_info=True)
            return {"known": False, "course_code": course_code,
                    "planned": planned_weekly_hours}

    # ------------------------------------------------------------------
    # 5. Attendance session creation (academics.services.attendance)
    # ------------------------------------------------------------------
    def create_attendance_session(self, lesson, *, on_date=None):
        """Seed an attendance session for a planned lesson so the
        attendance tracker has a canonical slot to register against."""
        try:
            from education_system.post_18.university_system.modules.domain.academics.services.course_management.attendance_sessions_sync import (
                find_or_create_session,
            )
            on_date = on_date or _next_date_for_day(lesson.get("day"))
            return find_or_create_session(_course_code(lesson), on_date)
        except Exception:
            logger.debug("create_attendance_session failed", exc_info=True)
            return None

    def generate_attendance_sessions(self, lesson, start_date, end_date):
        try:
            from education_system.post_18.university_system.modules.domain.academics.services.course_management.attendance_sessions_sync import (
                generate_sessions_for_module,
            )
            return generate_sessions_for_module(
                _course_code(lesson), start_date, end_date)
        except Exception:
            logger.debug("generate_attendance_sessions failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # 6. Tutor groups + advising (academics.tutor_groups / advising)
    # ------------------------------------------------------------------
    def list_tutor_groups(self, *, academic_year=None, programme=None):
        try:
            from education_system.post_18.university_system.modules.domain.academics.tutor_groups import (
                TutorGroupService,
            )
            return TutorGroupService(db_path=self._db_path).list_groups(
                academic_year=academic_year, programme=programme)
        except Exception:
            logger.debug("list_tutor_groups failed", exc_info=True)
            return []

    def schedule_tutor_meeting(self, group_id, scheduled_at, *,
                               duration_minutes=60, location="", agenda=""):
        try:
            from education_system.post_18.university_system.modules.domain.academics.tutor_groups import (
                TutorGroupService,
            )
            return TutorGroupService(db_path=self._db_path).schedule_meeting(
                group_id=int(group_id), scheduled_at=scheduled_at,
                duration_minutes=duration_minutes, location=location,
                agenda=agenda)
        except Exception:
            logger.debug("schedule_tutor_meeting failed", exc_info=True)
            return None

    def list_advisors(self):
        try:
            from education_system.post_18.university_system.modules.domain.academics.advising.services.advising_service import (
                get_all_advisors,
            )
            return get_all_advisors()
        except Exception:
            logger.debug("list_advisors failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # 7. Staff-HR availability + teaching load (operations.staff_hr)
    # ------------------------------------------------------------------
    def check_instructor_available(self, instructor_id, start_date, end_date):
        """Return any approved-leave conflicts for an instructor over a
        date range (empty list == available)."""
        try:
            from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.leave_manager import (
                LeaveManager,
            )
            return LeaveManager.check_conflicts(
                user_id=str(instructor_id), start_date=start_date,
                end_date=end_date)
        except Exception:
            logger.debug("check_instructor_available failed", exc_info=True)
            return []

    def instructor_load(self, instructor_id, academic_year, semester):
        try:
            from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.teaching_load_manager import (
                TeachingLoadManager,
            )
            return TeachingLoadManager.get_user_load_summary(
                user_id=str(instructor_id), academic_year=academic_year,
                semester=semester)
        except Exception:
            logger.debug("instructor_load failed", exc_info=True)
            return {}

    # ------------------------------------------------------------------
    # 8. Communications + email (shared.communication / infrastructure.email)
    # ------------------------------------------------------------------
    def notify_users(self, recipients, subject, body):
        """Send a schedule notification. Prefers the multi-channel
        CommunicationManager; falls back to direct email."""
        recipients = [r for r in (recipients or []) if r]
        if not recipients:
            return 0
        try:
            from education_system.post_18.university_system.modules.shared.services.communication.communication_manager import (
                CommunicationManager,
            )
            return CommunicationManager().send_bulk_email(
                recipients=recipients, subject=subject, body=body)
        except Exception:
            logger.debug("CommunicationManager unavailable; trying send_email",
                         exc_info=True)
        sent = 0
        try:
            from education_system.post_18.university_system.infrastructure.email import (
                send_email,
            )
            for addr in recipients:
                try:
                    if send_email(recipient_email=addr, subject=subject, body=body):
                        sent += 1
                except Exception:
                    logger.debug("send_email to %s failed", addr, exc_info=True)
        except Exception:
            logger.debug("email infrastructure unavailable", exc_info=True)
        return sent

    # ------------------------------------------------------------------
    # 9. Export (CSV / HTML-PDF / ICS) of the weekly schedule
    # ------------------------------------------------------------------
    def export_schedule_csv(self, lessons, filepath):
        try:
            from education_system.shared.reporting.csv_exporter import export_to_csv
            headers = ["course", "title", "type", "day", "start", "end",
                       "room", "instructor"]
            rows = [{h: lesson.get(h, "") for h in headers} for lesson in lessons]
            export_to_csv(rows, headers, filepath)
            return True
        except Exception:
            logger.debug("export_schedule_csv failed", exc_info=True)
            return False

    def export_schedule_html(self, lessons, filepath, *, title="Weekly Timetable"):
        try:
            from education_system.shared.reporting.pdf_exporter import save_report_html
            rows = [{
                "day": lesson.get("day", ""),
                "time": f"{lesson.get('start', '')}-{lesson.get('end', '')}",
                "title": lesson.get("title", ""),
                "type": lesson.get("type", ""),
                "room": lesson.get("room", ""),
                "instructor": lesson.get("instructor", ""),
            } for lesson in lessons]
            sections = [{"heading": "Scheduled Lessons", "type": "table", "data": rows}]
            save_report_html(title, sections, filepath,
                             institution="University Lesson Planner")
            return True
        except Exception:
            logger.debug("export_schedule_html failed", exc_info=True)
            return False

    def export_schedule_ics(self, lessons, filepath):
        """Write the weekly schedule as a weekly-recurring iCalendar
        file. Self-contained (no external dependency)."""
        try:
            base = date.today()
            lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
                     "PRODID:-//University Lesson Planner//EN"]
            for i, lesson in enumerate(lessons):
                day = lesson.get("day")
                if day not in _WEEKDAYS:
                    continue
                byday = _WEEKDAYS[day][1]
                first = base + timedelta(days=(_WEEKDAYS[day][0] - base.weekday()) % 7)
                start = (lesson.get("start") or "09:00").replace(":", "")
                end = (lesson.get("end") or "10:00").replace(":", "")
                stamp = first.strftime("%Y%m%d")
                lines += [
                    "BEGIN:VEVENT",
                    f"UID:lesson-{i}@lesson-planner",
                    f"DTSTART:{stamp}T{start}00",
                    f"DTEND:{stamp}T{end}00",
                    "RRULE:FREQ=WEEKLY;BYDAY=" + byday,
                    f"SUMMARY:{lesson.get('title', '')} ({lesson.get('type', '')})",
                    f"LOCATION:{lesson.get('room', '')}",
                    f"DESCRIPTION:{lesson.get('course', '')} - {lesson.get('instructor', '')}",
                    "END:VEVENT",
                ]
            lines.append("END:VCALENDAR")
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write("\r\n".join(lines))
            return True
        except Exception:
            logger.debug("export_schedule_ics failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # 10. Analytics + KPI feed (integration_bus KPIs / shared analytics)
    # ------------------------------------------------------------------
    def record_kpi(self, name, category, value):
        try:
            from education_system.post_18.university_system.modules.services.integration_bus import (
                _set_kpi,
            )
            _set_kpi(name=name, category=category, value=float(value))
            return True
        except Exception:
            logger.debug("record_kpi failed", exc_info=True)
            return False

    def bump_kpi(self, category, increment=1.0):
        try:
            from education_system.post_18.university_system.modules.services.integration_bus import (
                _bump_kpi,
            )
            _bump_kpi(category=category, increment=float(increment))
            return True
        except Exception:
            logger.debug("bump_kpi failed", exc_info=True)
            return False

    def room_utilisation(self, lessons):
        """Lightweight, dependency-free utilisation summary the planner
        can surface or feed onward: scheduled hours per room/day."""
        summary = {"total_hours": 0.0, "by_room": {}, "by_day": {}}
        for lesson in lessons:
            try:
                sh = int(lesson["start"].split(":")[0])
                eh = int(lesson["end"].split(":")[0])
                hours = max(0, eh - sh)
            except Exception:
                hours = 0
            summary["total_hours"] += hours
            room = lesson.get("room") or "(unassigned)"
            day = lesson.get("day") or "(none)"
            summary["by_room"][room] = summary["by_room"].get(room, 0) + hours
            summary["by_day"][day] = summary["by_day"].get(day, 0) + hours
        return summary

    # ------------------------------------------------------------------
    # 11. Audit logging (shared.audit)
    # ------------------------------------------------------------------
    def audit(self, action, *, target_type="lesson", target_id=None, details=None):
        """Append a tamper-evident audit entry for a planner action."""
        try:
            from education_system.shared.audit.logger import AuditLogger
            AuditLogger("university").log(
                action,
                user_id=self._user_id_int(),
                username=self.user_display or None,
                target_type=target_type, target_id=target_id,
                details=details,
            )
            return True
        except Exception:
            logger.debug("audit failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # 12. Permission / role checks (shared.auth.role_manager)
    # ------------------------------------------------------------------
    def can(self, permission, *, min_role="instructor"):
        """True if the signed-in user holds ``permission`` outright or
        meets ``min_role`` in the role hierarchy."""
        perms = self.user.get("permissions") or []
        if permission in perms:
            return True
        role = self.user.get("role")
        if not role:
            return False
        try:
            from education_system.shared.auth.role_manager import RoleManager
            return RoleManager().has_minimum_role(role, min_role)
        except Exception:
            logger.debug("can() role check failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Aggregate hook + status
    # ------------------------------------------------------------------
    def on_lesson_changed(self, action, lesson):
        """Single entry point the planner calls after every lesson
        create/update/delete: publish the bus event, audit it, and bump
        the timetable-activity KPI. Best-effort; never raises."""
        self.publish_lesson_event(action, lesson)
        self.audit(
            f"timetable.lesson_{action}",
            target_id=_course_code(lesson) or lesson.get("title"),
            details={k: lesson.get(k) for k in
                     ("title", "day", "start", "end", "room", "instructor")},
        )
        self.bump_kpi("timetable", 1.0)

    def status(self):
        """Probe which subsystems are importable right now — useful for
        a diagnostics panel. Returns {name: bool}."""
        probes = {
            "event_bus": "education_system.post_18.university_system.modules.services.integration_bus",
            "room_booking": "education_system.post_18.university_system.modules.domain.campus.room_booking.services.room_booking_service",
            "equipment": "education_system.post_18.university_system.modules.domain.campus.equipment.services.equipment_core",
            "curriculum": "education_system.post_18.university_system.modules.domain.academics.curriculum_specification.services.curriculum_specification_service",
            "attendance": "education_system.post_18.university_system.modules.domain.academics.services.course_management.attendance_sessions_sync",
            "tutor_groups": "education_system.post_18.university_system.modules.domain.academics.tutor_groups",
            "staff_hr": "education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.leave_manager",
            "email": "education_system.post_18.university_system.infrastructure.email",
            "audit": "education_system.shared.audit.logger",
            "roles": "education_system.shared.auth.role_manager",
        }
        import importlib
        out = {}
        for name, mod in probes.items():
            try:
                importlib.import_module(mod)
                out[name] = True
            except Exception:
                out[name] = False
        return out
