"""Timetable management service."""

from education_system.college_system.core.exceptions import TimetableError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.infrastructure.validation.validators import (
    validate_day_of_week, validate_time_range,
)

import logging

logger = logging.getLogger(__name__)


class TimetableService:
    """Service for managing course timetable slots."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_slot(self, course_id: int, day: str, start_time: str,
                 end_time: str, room: str | None = None,
                 teacher: str | None = None, instructor: str | None = None) -> dict:
        """Add a timetable slot. Raises TimetableError on conflict."""
        day = validate_day_of_week(day)
        start_time, end_time = validate_time_range(start_time, end_time)

        conn = self._conn()
        try:
            # Verify course exists
            course = conn.execute(
                "SELECT id FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
            if not course:
                raise TimetableError("Course not found.")

            # Support both teacher and instructor params
            teacher_name = teacher or instructor

            # Check conflicts
            conflicts = self.check_conflicts(day, start_time, end_time, room, teacher_name)
            if conflicts:
                reasons = [c["reason"] for c in conflicts]
                raise TimetableError(f"Scheduling conflict: {'; '.join(reasons)}")

            conn.execute(
                """INSERT INTO timetable_slots
                   (course_id, day_of_week, start_time, end_time, room, instructor_name)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (course_id, day, start_time, end_time, room, teacher_name),
            )
            conn.commit()
            logger.info("Timetable slot added: course=%d %s %s-%s", course_id, day, start_time, end_time)

            slot = conn.execute(
                "SELECT * FROM timetable_slots WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(slot)
        except TimetableError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TimetableError(f"Failed to add slot: {e}") from e
        finally:
            conn.close()

    def update_slot(self, slot_id: int, **updates) -> dict:
        """Update a timetable slot."""
        allowed = {"course_id", "day_of_week", "start_time", "end_time", "room", "instructor_name"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise TimetableError("No valid fields to update.")

        if "day_of_week" in updates:
            updates["day_of_week"] = validate_day_of_week(updates["day_of_week"])
        if "start_time" in updates or "end_time" in updates:
            conn = self._conn()
            try:
                current = conn.execute(
                    "SELECT * FROM timetable_slots WHERE id = ?", (slot_id,)
                ).fetchone()
                if not current:
                    raise TimetableError("Slot not found.")
                st = updates.get("start_time", current["start_time"])
                et = updates.get("end_time", current["end_time"])
                st, et = validate_time_range(st, et)
                updates["start_time"] = st
                updates["end_time"] = et
            finally:
                conn.close()

        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT * FROM timetable_slots WHERE id = ?", (slot_id,)
            ).fetchone()
            if not existing:
                raise TimetableError("Slot not found.")

            # Check conflicts with updated values
            day = updates.get("day_of_week", existing["day_of_week"])
            st = updates.get("start_time", existing["start_time"])
            et = updates.get("end_time", existing["end_time"])
            room = updates.get("room", existing["room"])
            instructor = updates.get("instructor_name", existing["instructor_name"])

            conflicts = self.check_conflicts(day, st, et, room, instructor, exclude_id=slot_id)
            if conflicts:
                reasons = [c["reason"] for c in conflicts]
                raise TimetableError(f"Scheduling conflict: {'; '.join(reasons)}")

            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE timetable_slots SET {set_parts} WHERE id = ?",
                (*updates.values(), slot_id),
            )
            conn.commit()
            logger.info("Timetable slot updated: id=%d", slot_id)

            row = conn.execute(
                "SELECT * FROM timetable_slots WHERE id = ?", (slot_id,)
            ).fetchone()
            return dict(row)
        except TimetableError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TimetableError(f"Failed to update slot: {e}") from e
        finally:
            conn.close()

    def delete_slot(self, slot_id: int) -> bool:
        """Delete a timetable slot."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM timetable_slots WHERE id = ?", (slot_id,)
            ).fetchone()
            if not existing:
                raise TimetableError("Slot not found.")

            conn.execute("DELETE FROM timetable_slots WHERE id = ?", (slot_id,))
            conn.commit()
            logger.info("Timetable slot deleted: id=%d", slot_id)
            return True
        except TimetableError:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_course_timetable(self, course_id: int) -> list[dict]:
        """Get all timetable slots for a course."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ts.*, c.course_code, c.title as course_title
                   FROM timetable_slots ts
                   JOIN courses c ON ts.course_id = c.id
                   WHERE ts.course_id = ?
                   ORDER BY ts.day_of_week, ts.start_time""",
                (course_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_student_timetable(self, student_pk: int) -> list[dict]:
        """Get the timetable for a student based on their enrollments."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ts.*, c.course_code, c.title as course_title
                   FROM timetable_slots ts
                   JOIN courses c ON ts.course_id = c.id
                   JOIN enrollments e ON e.course_id = c.id
                   WHERE e.student_id = ? AND e.status = 'enrolled'
                   ORDER BY ts.day_of_week, ts.start_time""",
                (student_pk,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_room_schedule(self, room: str) -> list[dict]:
        """Get all slots for a specific room."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ts.*, c.course_code, c.title as course_title
                   FROM timetable_slots ts
                   JOIN courses c ON ts.course_id = c.id
                   WHERE ts.room = ?
                   ORDER BY ts.day_of_week, ts.start_time""",
                (room,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def generate_full_timetable(self) -> dict:
        """Auto-generate a full weekly timetable for all active courses.

        Schedule structure:
            Period 1:  09:00 - 10:00
            Period 2:  10:00 - 11:00
            Break:     11:00 - 11:20
            Period 3:  11:20 - 12:20
            Lunch:     12:20 - 13:00
            Period 4:  13:00 - 14:00
            Period 5:  14:00 - 15:00

        Phase 1: Each course rotates through different periods (5 singles).
        Phase 2: Each course gets 2 double-lesson extensions (adjacent
                 period added on 2 days) for 7 periods/week total.

        Returns summary dict with slots_created, courses_scheduled, etc.
        """
        DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        PERIODS = [
            ("09:00", "10:00"),  # index 0
            ("10:00", "11:00"),  # index 1
            ("11:20", "12:20"),  # index 2
            ("13:00", "14:00"),  # index 3
            ("14:00", "15:00"),  # index 4
        ]
        # Adjacent period index for forming doubles.
        # Period 2 (11:20) is isolated between break and lunch — cannot double.
        DOUBLE_ADJACENT = {0: 1, 1: 0, 2: None, 3: 4, 4: 3}

        conn = self._conn()
        try:
            # 1. Clear all existing timetable slots
            conn.execute("DELETE FROM timetable_slots")

            # 2. Fetch all active courses with teacher names
            courses = conn.execute(
                "SELECT id, course_code, title, teacher, instructor FROM courses WHERE status = 'active'"
            ).fetchall()
            courses = [dict(c) for c in courses]

            if not courses:
                conn.commit()
                return {
                    "slots_created": 0,
                    "courses_scheduled": 0,
                    "courses_total": 0,
                    "unscheduled": [],
                    "partial": [],
                    "doubles_added": 0,
                }

            # 3. Assign each course an offset (0-4) for period rotation.
            offset_for: dict[int, int] = {}
            teacher_offsets: dict[str, set[int]] = {}

            for course in courses:
                teacher = course.get("teacher") or course.get("instructor") or ""
                used = teacher_offsets.get(teacher, set()) if teacher else set()

                assigned = False
                for candidate in range(5):
                    if candidate not in used:
                        offset_for[course["id"]] = candidate
                        if teacher:
                            teacher_offsets.setdefault(teacher, set()).add(candidate)
                        assigned = True
                        break

                if not assigned:
                    offset_for[course["id"]] = len(used) % 5

            # 4. Phase 1 — Create single-period slots using the rotation
            # Track room and teacher usage per (day_idx, period_idx)
            room_busy: dict[tuple[int, int], int] = {}
            teacher_busy: dict[str, set[tuple[int, int]]] = {}
            slots_created = 0
            course_slot_count: dict[int, int] = {c["id"]: 0 for c in courses}

            for course in courses:
                offset = offset_for[course["id"]]
                teacher = course.get("teacher") or course.get("instructor") or ""
                for day_idx, day in enumerate(DAYS):
                    period_idx = (offset + day_idx) % 5
                    start, end = PERIODS[period_idx]

                    key = (day_idx, period_idx)
                    room_num = room_busy.get(key, 0) + 1
                    room_busy[key] = room_num
                    room = f"Room {room_num}"

                    conn.execute(
                        """INSERT INTO timetable_slots
                           (course_id, day_of_week, start_time, end_time, room, instructor_name)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (course["id"], day, start, end, room, teacher or None),
                    )
                    slots_created += 1
                    course_slot_count[course["id"]] += 1

                    if teacher:
                        teacher_busy.setdefault(teacher, set()).add(key)

            # 5. Phase 2 — Add double-lesson extensions (2 per course)
            doubles_added = 0
            for course in courses:
                offset = offset_for[course["id"]]
                teacher = course.get("teacher") or course.get("instructor") or ""
                added = 0

                # Try each day, starting from a rotating position to spread doubles
                for attempt in range(5):
                    if added >= 2:
                        break
                    day_idx = (offset + attempt) % 5
                    base_period = (offset + day_idx) % 5
                    adj_period = DOUBLE_ADJACENT.get(base_period)

                    if adj_period is None:
                        continue  # Period 2 cannot form a double

                    adj_key = (day_idx, adj_period)

                    # Check teacher conflict
                    if teacher and adj_key in teacher_busy.get(teacher, set()):
                        continue

                    start, end = PERIODS[adj_period]
                    room_num = room_busy.get(adj_key, 0) + 1
                    room_busy[adj_key] = room_num
                    room = f"Room {room_num}"

                    conn.execute(
                        """INSERT INTO timetable_slots
                           (course_id, day_of_week, start_time, end_time, room, instructor_name)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (course["id"], DAYS[day_idx], start, end, room, teacher or None),
                    )
                    slots_created += 1
                    course_slot_count[course["id"]] += 1
                    doubles_added += 1
                    added += 1

                    if teacher:
                        teacher_busy.setdefault(teacher, set()).add(adj_key)

            conn.commit()
            logger.info("Full timetable generated: %d slots for %d courses", slots_created, len(courses))

            # 6. Build summary
            fully_scheduled = []
            partial = []
            unscheduled = []
            for course in courses:
                count = course_slot_count[course["id"]]
                if count == 0:
                    unscheduled.append(course["course_code"])
                elif count < 5:
                    partial.append(f"{course['course_code']} ({count}/5)")
                else:
                    fully_scheduled.append(course["course_code"])

            return {
                "slots_created": slots_created,
                "courses_scheduled": len(fully_scheduled),
                "courses_total": len(courses),
                "unscheduled": unscheduled,
                "partial": partial,
                "doubles_added": doubles_added,
            }
        except Exception as e:
            conn.rollback()
            raise TimetableError(f"Failed to generate timetable: {e}") from e
        finally:
            conn.close()

    def check_conflicts(self, day: str, start_time: str, end_time: str,
                        room: str | None = None, instructor: str | None = None,
                        exclude_id: int | None = None) -> list[dict]:
        """Check for scheduling conflicts. Returns list of conflict descriptions."""
        conflicts = []
        conn = self._conn()
        try:
            base_sql = """
                SELECT ts.*, c.course_code FROM timetable_slots ts
                JOIN courses c ON ts.course_id = c.id
                WHERE ts.day_of_week = ?
                AND ts.start_time < ? AND ts.end_time > ?
            """
            base_params: list = [day, end_time, start_time]

            if exclude_id is not None:
                base_sql += " AND ts.id != ?"
                base_params.append(exclude_id)

            # Room conflict
            if room:
                room_sql = base_sql + " AND ts.room = ?"
                room_params = base_params + [room]
                rows = conn.execute(room_sql, room_params).fetchall()
                for r in rows:
                    conflicts.append({
                        "type": "room",
                        "slot_id": r["id"],
                        "reason": f"Room '{room}' already booked for {r['course_code']} "
                                  f"({r['start_time']}-{r['end_time']})",
                    })

            # Instructor conflict
            if instructor:
                instr_sql = base_sql + " AND ts.instructor_name = ?"
                instr_params = base_params + [instructor]
                rows = conn.execute(instr_sql, instr_params).fetchall()
                for r in rows:
                    conflicts.append({
                        "type": "instructor",
                        "slot_id": r["id"],
                        "reason": f"Instructor '{instructor}' already scheduled for "
                                  f"{r['course_code']} ({r['start_time']}-{r['end_time']})",
                    })
        finally:
            conn.close()

        return conflicts

    def check_student_clashes(self, student_pk: int) -> list[dict]:
        """Find overlapping timetable slots for a student based on enrollments."""
        conn = self._conn()
        try:
            slots = conn.execute(
                """SELECT ts.*, c.course_code, c.title as course_title
                   FROM timetable_slots ts
                   JOIN courses c ON ts.course_id = c.id
                   JOIN enrollments e ON e.course_id = c.id
                   WHERE e.student_id = ? AND e.status = 'enrolled'
                   ORDER BY ts.day_of_week, ts.start_time""",
                (student_pk,),
            ).fetchall()
            slots = [dict(s) for s in slots]

            clashes = []
            for i, a in enumerate(slots):
                for b in slots[i + 1:]:
                    if a["day_of_week"] != b["day_of_week"]:
                        continue
                    if a["start_time"] < b["end_time"] and b["start_time"] < a["end_time"]:
                        clashes.append({
                            "slot_a": a,
                            "slot_b": b,
                            "reason": (
                                f"{a['course_code']} ({a['start_time']}-{a['end_time']}) "
                                f"clashes with {b['course_code']} ({b['start_time']}-{b['end_time']}) "
                                f"on {a['day_of_week']}"
                            ),
                        })
            return clashes
        finally:
            conn.close()

    def get_instructor_schedule(self, instructor_name: str) -> list[dict]:
        """Get all timetable slots for a specific instructor."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ts.*, c.course_code, c.title as course_title
                   FROM timetable_slots ts
                   JOIN courses c ON ts.course_id = c.id
                   WHERE ts.instructor_name = ?
                   ORDER BY ts.day_of_week, ts.start_time""",
                (instructor_name,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
