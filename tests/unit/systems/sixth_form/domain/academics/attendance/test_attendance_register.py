"""Tests for the Sixth Form register-taking lifecycle.

Covers bulk marking, keyboard shorthand, draft/submitted locking, the
unsubmitted-register chase list, copy-forward, arrival and departure
stamps, range marking, undo and unsaved-change detection.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_register as reg,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as cg,
)
from education_system.systems.sixth_form.domain.academics.courses import (
    courses as courses_mod,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as students_mod,
)


def _next_weekday(target: int) -> _dt.date:
    """The next date (today included) whose weekday matches ``target`` (Mon=0)."""
    today = _dt.date.today()
    return today + _dt.timedelta(days=(target - today.weekday()) % 7)


@pytest.fixture
def att(tmp_path, monkeypatch):
    """Every attendance-adjacent module on one temp DB, seeded with a class.

    One course, one class group of three students, and two Monday slots
    (period 1 and period 2) plus a Tuesday slot, so range marking has
    something to skip and something to hit.
    """
    db_path = str(tmp_path / "sixthform.db")
    for mod in (core, reg, tt, cg, courses_mod, students_mod):
        monkeypatch.setattr(mod, "DB_PATH", db_path, raising=False)
        if hasattr(mod, "_DB_READY"):
            monkeypatch.setattr(mod, "_DB_READY", False, raising=False)
    reg.init_db()

    # Seeded by SQL rather than through students.create_student, which
    # would provision a login in the shared platform auth.db.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO courses (course_id, course_code, subject, title, "
        "year_group, academic_year) VALUES (1, 'MAT-A', 'Mathematics', "
        "'A Level Maths', 12, '2025/26')")
    conn.executemany(
        "INSERT INTO class_groups (group_id, course_id, group_name) "
        "VALUES (?, 1, ?)", [(1, "12A"), (2, "12B")])
    for i, name in enumerate(("Ada", "Alan", "Grace"), 1):
        sid = f"T{i:04d}"
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, email, "
            "status) VALUES (?, ?, 'Test', ?, 'Active')",
            (sid, name, f"{sid.lower()}@example.test"))
        conn.execute(
            "INSERT INTO class_group_students (group_id, student_id) "
            "VALUES (1, ?)", (sid,))
    conn.executemany(
        "INSERT INTO timetable_slots (slot_id, group_id, day, period, "
        "start_time, end_time, room) VALUES (?, ?, ?, ?, ?, ?, 'R1')",
        [(1, 1, 1, 1, "09:00", "09:55"),   # 12A, Monday P1
         (2, 1, 1, 2, "09:55", "10:50"),   # 12A, Monday P2
         (3, 2, 2, 1, "09:00", "09:55")])  # 12B (no members), Tuesday P1
    conn.commit()
    conn.close()

    class NS:
        pass
    ns = NS()
    ns.db = db_path
    ns.students = ["T0001", "T0002", "T0003"]
    ns.s1, ns.s2, ns.s3 = ns.students
    ns.slot = 1
    ns.monday = _next_weekday(0).isoformat()
    ns.tuesday = _next_weekday(1).isoformat()
    ns.prev_monday = (_next_weekday(0) - _dt.timedelta(days=7)).isoformat()
    return ns


def _statuses(slot_id: int, date: str) -> dict[str, str]:
    return {r.student_id: r.status
            for r in core.list_records(slot_id=slot_id, date=date)}


# ── 1. Bulk marking ────────────────────────────────────────────────

class TestBulkMarking:

    def test_mark_all_covers_the_whole_roster(self, att):
        assert reg.mark_all(att.slot, att.monday, "Present") == 3
        assert _statuses(att.slot, att.monday) == {
            att.s1: "Present", att.s2: "Present", att.s3: "Present"}

    def test_mark_selected_leaves_the_rest_alone(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.mark_all(att.slot, att.monday, "Absent",
                     student_ids=[att.s2])
        assert _statuses(att.slot, att.monday) == {
            att.s1: "Present", att.s2: "Absent", att.s3: "Present"}

    def test_bulk_keeps_notes_but_drops_stale_late_minutes(self, att):
        core.save_register(att.slot, att.monday, {
            att.s1: {"status": "Late", "minutes_late": 12, "notes": "Bus"}})
        reg.mark_all(att.slot, att.monday, "Present", student_ids=[att.s1])
        record = core.list_records(slot_id=att.slot, date=att.monday)[0]
        assert record.status == "Present"
        assert record.notes == "Bus"
        assert record.minutes_late is None

    def test_marking_someone_off_the_roster_is_rejected(self, att):
        with pytest.raises(core.ValidationError, match="Not on this roster"):
            reg.mark_all(att.slot, att.monday, "Present",
                         student_ids=["T9999"])


# ── 2. Keyboard shorthand ──────────────────────────────────────────

class TestKeyboardShorthand:

    @pytest.mark.parametrize("key,status", [
        ("p", "Present"), ("l", "Late"), ("a", "Absent"), ("u", "Authorised"),
    ])
    def test_each_key_maps_to_its_status(self, key, status):
        assert reg.status_for_key(key) == status

    def test_keys_are_case_insensitive(self):
        assert reg.status_for_key("P") == "Present"

    def test_unknown_key_is_rejected(self):
        with pytest.raises(core.ValidationError, match="Key must be one of"):
            reg.status_for_key("z")

    def test_mark_by_key_writes_the_mapped_status(self, att):
        reg.mark_by_key(att.slot, att.monday, "a")
        assert set(_statuses(att.slot, att.monday).values()) == {"Absent"}


# ── 3. Submit / lock ───────────────────────────────────────────────

class TestSubmitAndLock:

    def test_saving_creates_a_draft_session(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        session = reg.get_session(att.slot, att.monday)
        assert session is not None
        assert session.state == "Draft"
        assert not reg.is_locked(att.slot, att.monday)

    def test_submit_locks_the_register(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        session = reg.submit_register(att.slot, att.monday,
                                      submitted_by="tfrost")
        assert session.is_submitted
        assert session.submitted_by == "tfrost"
        assert session.submitted_at
        assert reg.is_locked(att.slot, att.monday)

    def test_incomplete_register_will_not_submit(self, att):
        reg.mark_all(att.slot, att.monday, "Present", student_ids=[att.s1])
        with pytest.raises(core.ValidationError, match="still unmarked"):
            reg.submit_register(att.slot, att.monday)

    def test_incomplete_can_be_forced(self, att):
        reg.mark_all(att.slot, att.monday, "Present", student_ids=[att.s1])
        session = reg.submit_register(att.slot, att.monday,
                                      allow_incomplete=True)
        assert session.is_submitted

    def test_submitted_register_rejects_every_write_path(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        record_id = core.list_records(slot_id=att.slot, date=att.monday)[0].record_id
        reg.submit_register(att.slot, att.monday)

        with pytest.raises(core.ValidationError, match="has been submitted"):
            core.save_register(att.slot, att.monday,
                               {att.s1: {"status": "Absent"}})
        with pytest.raises(core.ValidationError, match="has been submitted"):
            core.update_record(record_id, {"status": "Absent"})
        with pytest.raises(core.ValidationError, match="has been submitted"):
            core.delete_record(record_id)
        with pytest.raises(core.ValidationError, match="has been submitted"):
            reg.mark_all(att.slot, att.monday, "Absent")
        assert set(_statuses(att.slot, att.monday).values()) == {"Present"}

    def test_double_submit_is_rejected(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.submit_register(att.slot, att.monday)
        with pytest.raises(core.ValidationError, match="already submitted"):
            reg.submit_register(att.slot, att.monday)

    def test_reopen_needs_a_reason_and_records_it(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.submit_register(att.slot, att.monday)
        with pytest.raises(core.ValidationError, match="reason is required"):
            reg.reopen_register(att.slot, att.monday, reason="  ")

        session = reg.reopen_register(att.slot, att.monday,
                                      reason="Wrong student marked",
                                      reopened_by="hoffice")
        assert session.state == "Draft"
        assert session.reopen_reason == "Wrong student marked"
        assert session.reopened_by == "hoffice"
        # …and writing works again.
        assert reg.mark_all(att.slot, att.monday, "Absent") == 3

    def test_reopening_an_unsubmitted_register_is_rejected(self, att):
        with pytest.raises(core.ValidationError, match="not submitted"):
            reg.reopen_register(att.slot, att.monday, reason="why not")

    def test_empty_roster_cannot_be_submitted(self, att):
        # Slot 3 belongs to group 2, which has no members.
        with pytest.raises(core.ValidationError, match="no students"):
            reg.submit_register(3, att.tuesday)

    def test_list_sessions_filters_by_state(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.mark_all(2, att.monday, "Present")
        reg.submit_register(att.slot, att.monday)
        submitted = reg.list_sessions(state="Submitted")
        assert [s.slot_id for s in submitted] == [att.slot]
        assert len(reg.list_sessions(date=att.monday)) == 2


# ── 4. Chase list ──────────────────────────────────────────────────

class TestUnsubmittedRegisters:

    def test_untouched_slots_show_as_not_started(self, att):
        missing = reg.unsubmitted_registers(date_from=att.monday,
                                            date_to=att.monday)
        assert [(m.slot_id, m.state) for m in missing] == [
            (1, "Not started"), (2, "Not started")]
        assert missing[0].expected == 3
        assert missing[0].marked == 0

    def test_partly_filled_slot_shows_as_draft(self, att):
        reg.mark_all(att.slot, att.monday, "Present", student_ids=[att.s1])
        missing = reg.unsubmitted_registers(date_from=att.monday,
                                            date_to=att.monday)
        first = next(m for m in missing if m.slot_id == att.slot)
        assert first.state == "Draft"
        assert first.marked == 1
        assert first.expected == 3

    def test_submitted_slots_drop_off_the_list(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.submit_register(att.slot, att.monday)
        missing = reg.unsubmitted_registers(date_from=att.monday,
                                            date_to=att.monday)
        assert [m.slot_id for m in missing] == [2]

    def test_only_slots_timetabled_on_that_weekday_are_expected(self, att):
        missing = reg.unsubmitted_registers(date_from=att.tuesday,
                                            date_to=att.tuesday)
        assert [m.slot_id for m in missing] == [3]

    def test_group_filter_narrows_the_list(self, att):
        missing = reg.unsubmitted_registers(date_from=att.monday,
                                            date_to=att.monday, group_id=2)
        assert missing == []

    def test_backwards_range_is_rejected(self, att):
        with pytest.raises(core.ValidationError, match="on or before"):
            reg.unsubmitted_registers(date_from=att.tuesday,
                                      date_to=att.monday)


# ── 5. Copy forward ────────────────────────────────────────────────

class TestCopyPrevious:

    def test_copies_the_last_session_forward(self, att):
        core.save_register(att.slot, att.prev_monday, {
            att.s1: {"status": "Present"},
            att.s2: {"status": "Absent", "notes": "Hospital"},
            att.s3: {"status": "Authorised"}})
        result = reg.copy_previous_register(att.slot, att.monday)
        assert result.source_date == att.prev_monday
        assert result.copied == 3
        assert _statuses(att.slot, att.monday) == {
            att.s1: "Present", att.s2: "Absent", att.s3: "Authorised"}

    def test_late_minutes_are_not_carried_over(self, att):
        core.save_register(att.slot, att.prev_monday, {
            att.s1: {"status": "Late", "minutes_late": 20}})
        reg.copy_previous_register(att.slot, att.monday)
        copied = core.list_records(slot_id=att.slot, date=att.monday)[0]
        assert copied.status == "Late"
        assert copied.minutes_late is None

    def test_existing_marks_are_not_stomped(self, att):
        core.save_register(att.slot, att.prev_monday,
                           {s: {"status": "Absent"} for s in att.students})
        core.save_register(att.slot, att.monday, {att.s1: {"status": "Present"}})
        result = reg.copy_previous_register(att.slot, att.monday)
        assert result.copied == 2
        assert result.skipped == 1
        assert _statuses(att.slot, att.monday)[att.s1] == "Present"

    def test_overwrite_replaces_todays_marks(self, att):
        core.save_register(att.slot, att.prev_monday,
                           {s: {"status": "Absent"} for s in att.students})
        core.save_register(att.slot, att.monday, {att.s1: {"status": "Present"}})
        reg.copy_previous_register(att.slot, att.monday, overwrite=True)
        assert _statuses(att.slot, att.monday)[att.s1] == "Absent"

    def test_nothing_to_copy_is_reported_not_raised(self, att):
        result = reg.copy_previous_register(att.slot, att.monday)
        assert result.source_date is None
        assert result.copied == 0

    def test_previous_date_ignores_later_sessions(self, att):
        core.save_register(att.slot, att.prev_monday, {att.s1: {"status": "Present"}})
        core.save_register(att.slot, att.monday, {att.s1: {"status": "Present"}})
        assert reg.previous_register_date(att.slot, att.monday) == att.prev_monday


# ── 6 & 7. Arrival and departure stamps ────────────────────────────

class TestClockStamps:

    def test_arrival_derives_the_late_minutes(self, att):
        record = reg.record_arrival(att.slot, att.monday, att.s1, "09:12")
        assert record.status == "Late"
        assert record.minutes_late == 12
        assert record.arrival_time == "09:12"

    def test_arrival_on_time_is_present_with_no_minutes(self, att):
        record = reg.record_arrival(att.slot, att.monday, att.s1, "09:00")
        assert record.status == "Present"
        assert record.minutes_late is None

    def test_arrival_clears_a_stale_late_count(self, att):
        core.save_register(att.slot, att.monday,
                           {att.s1: {"status": "Late", "minutes_late": 30}})
        record = reg.record_arrival(att.slot, att.monday, att.s1, "09:00")
        assert record.status == "Present"
        assert record.minutes_late is None

    def test_arrival_after_the_lesson_ends_is_rejected(self, att):
        with pytest.raises(core.ValidationError, match="after the lesson ends"):
            reg.record_arrival(att.slot, att.monday, att.s1, "10:30")

    def test_arrival_time_must_be_a_real_clock_time(self, att):
        with pytest.raises(core.ValidationError, match="HH:MM"):
            reg.record_arrival(att.slot, att.monday, att.s1, "9am")

    def test_departure_keeps_the_student_present(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        record = reg.record_departure(att.slot, att.monday, att.s1, "09:30",
                                      reason="Dentist")
        assert record.status == "Present"
        assert record.departure_time == "09:30"
        assert "Left early at 09:30 (Dentist)" in record.notes
        assert reg.left_early(record)
        assert reg.minutes_missed(record) == 25

    def test_departure_outside_the_lesson_is_rejected(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        with pytest.raises(core.ValidationError, match="before the lesson"):
            reg.record_departure(att.slot, att.monday, att.s1, "08:30")
        with pytest.raises(core.ValidationError,
                           match="not an early leave"):
            reg.record_departure(att.slot, att.monday, att.s1, "10:30")

    def test_stamps_survive_a_later_register_save(self, att):
        reg.record_arrival(att.slot, att.monday, att.s1, "09:05")
        core.save_register(att.slot, att.monday,
                           {att.s1: {"status": "Late", "minutes_late": 5,
                                     "notes": "Bus"}})
        record = core.list_records(slot_id=att.slot, date=att.monday)[0]
        assert record.arrival_time == "09:05"

    def test_early_leavers_can_be_listed(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.record_departure(att.slot, att.monday, att.s2, "09:20")
        leavers = reg.list_early_leavers(date_from=att.monday,
                                         date_to=att.monday)
        assert [r.student_id for r in leavers] == [att.s2]

    def test_stamping_someone_off_the_roster_is_rejected(self, att):
        with pytest.raises(core.ValidationError, match="not on the roster"):
            reg.record_arrival(att.slot, att.monday, "T9999", "09:05")

    def test_stamps_respect_the_lock(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.submit_register(att.slot, att.monday)
        with pytest.raises(core.ValidationError, match="has been submitted"):
            reg.record_arrival(att.slot, att.monday, att.s1, "09:05")

    def test_slot_window_falls_back_to_the_period_default(self, att, monkeypatch):
        conn = sqlite3.connect(att.db)
        conn.execute("UPDATE timetable_slots SET start_time = NULL, "
                     "end_time = NULL WHERE slot_id = 1")
        conn.commit()
        conn.close()
        assert reg.slot_window(att.slot) == tt.DEFAULT_PERIOD_TIMES[1]


# ── 8. Range marking ───────────────────────────────────────────────

class TestRangeMarking:

    def test_marks_every_timetabled_day_in_the_range(self, att):
        start = _dt.date.fromisoformat(att.monday)
        end = start + _dt.timedelta(days=6)
        result = reg.mark_range(date_from=att.monday, date_to=end.isoformat(),
                                status="Authorised", student_ids=[att.s1],
                                group_id=1, notes="Study leave")
        # Group 1 has two Monday slots and nothing else in the week.
        assert result.written == 2
        assert _statuses(1, att.monday) == {att.s1: "Authorised"}
        assert _statuses(2, att.monday) == {att.s1: "Authorised"}

    def test_days_with_no_lesson_are_skipped_not_marked(self, att):
        start = _dt.date.fromisoformat(att.monday)
        result = reg.mark_range(
            date_from=(start + _dt.timedelta(days=2)).isoformat(),
            date_to=(start + _dt.timedelta(days=4)).isoformat(),
            status="Absent", group_id=1)
        assert result.written == 0
        assert result.skipped_no_slot == 3

    def test_whole_group_is_marked_when_no_students_given(self, att):
        result = reg.mark_range(date_from=att.monday, date_to=att.monday,
                                status="Absent", slot_ids=[att.slot])
        assert result.written == 3

    def test_locked_days_are_skipped_rather_than_failing_the_batch(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.submit_register(att.slot, att.monday)
        result = reg.mark_range(date_from=att.monday, date_to=att.monday,
                                status="Absent", group_id=1)
        assert result.skipped_locked == 3
        assert result.written == 3            # the period-2 slot still went in
        assert set(_statuses(att.slot, att.monday).values()) == {"Present"}

    def test_notes_are_carried_onto_every_row(self, att):
        reg.mark_range(date_from=att.monday, date_to=att.monday,
                       status="Authorised", slot_ids=[att.slot],
                       notes="Open day")
        assert all(r.notes == "Open day"
                   for r in core.list_records(slot_id=att.slot,
                                              date=att.monday))

    def test_unknown_slot_ids_are_rejected(self, att):
        with pytest.raises(core.ValidationError, match="slot ids"):
            reg.mark_range(date_from=att.monday, date_to=att.monday,
                           status="Absent", slot_ids=[999])

    def test_over_long_ranges_are_refused(self, att):
        start = _dt.date.fromisoformat(att.monday)
        with pytest.raises(core.ValidationError, match="366 days"):
            reg.mark_range(
                date_from=att.monday,
                date_to=(start + _dt.timedelta(days=400)).isoformat(),
                status="Absent", group_id=1)


# ── 9. Undo ────────────────────────────────────────────────────────

class TestUndo:

    def test_undo_restores_the_previous_statuses(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.mark_all(att.slot, att.monday, "Absent")
        result = reg.undo_last_save(att.slot, att.monday)
        assert result.restored == 3
        assert set(_statuses(att.slot, att.monday).values()) == {"Present"}

    def test_undo_removes_rows_the_save_created(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        result = reg.undo_last_save(att.slot, att.monday)
        assert result.deleted == 3
        assert core.list_records(slot_id=att.slot, date=att.monday) == []

    def test_undo_walks_back_one_save_at_a_time(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.mark_all(att.slot, att.monday, "Late")
        reg.mark_all(att.slot, att.monday, "Absent")
        reg.undo_last_save(att.slot, att.monday)
        assert set(_statuses(att.slot, att.monday).values()) == {"Late"}
        reg.undo_last_save(att.slot, att.monday)
        assert set(_statuses(att.slot, att.monday).values()) == {"Present"}

    def test_undo_restores_notes_and_late_minutes(self, att):
        core.save_register(att.slot, att.monday, {
            att.s1: {"status": "Late", "minutes_late": 7, "notes": "Traffic"}})
        reg.mark_all(att.slot, att.monday, "Present", student_ids=[att.s1])
        reg.undo_last_save(att.slot, att.monday)
        record = core.list_records(slot_id=att.slot, date=att.monday)[0]
        assert (record.status, record.minutes_late, record.notes) == (
            "Late", 7, "Traffic")

    def test_undo_with_no_history_is_rejected(self, att):
        with pytest.raises(core.ValidationError, match="Nothing to undo"):
            reg.undo_last_save(att.slot, att.monday)

    def test_a_rejected_save_leaves_no_undo_step(self, att):
        with pytest.raises(core.ValidationError):
            core.save_register(att.slot, att.monday,
                               {att.s1: {"status": "Nonsense"}})
        assert reg.snapshot_count(att.slot, att.monday) == 0

    def test_undo_respects_the_lock(self, att):
        reg.mark_all(att.slot, att.monday, "Present")
        reg.submit_register(att.slot, att.monday)
        with pytest.raises(core.ValidationError, match="has been submitted"):
            reg.undo_last_save(att.slot, att.monday)

    def test_snapshot_buffer_is_bounded(self, att, monkeypatch):
        monkeypatch.setattr(reg, "MAX_SNAPSHOTS", 3)
        for _ in range(6):
            reg.mark_all(att.slot, att.monday, "Present")
        assert reg.snapshot_count(att.slot, att.monday) == 3


# ── 10. Unsaved-change detection ───────────────────────────────────

class TestDirtyDetection:

    def _payload(self, statuses: dict[str, str]) -> dict[str, dict]:
        return {sid: {"status": s, "minutes_late": None, "notes": None}
                for sid, s in statuses.items()}

    def test_saved_register_matches_its_own_payload(self, att):
        payload = self._payload({s: "Present" for s in att.students})
        core.save_register(att.slot, att.monday, payload)
        assert not reg.has_unsaved_changes(att.slot, att.monday, payload)

    def test_changed_status_is_detected(self, att):
        payload = self._payload({s: "Present" for s in att.students})
        core.save_register(att.slot, att.monday, payload)
        payload[att.s2]["status"] = "Absent"
        assert reg.has_unsaved_changes(att.slot, att.monday, payload)

    def test_changed_note_is_detected(self, att):
        payload = self._payload({s: "Present" for s in att.students})
        core.save_register(att.slot, att.monday, payload)
        payload[att.s3]["notes"] = "Arrived without kit"
        assert reg.has_unsaved_changes(att.slot, att.monday, payload)

    def test_digest_ignores_ordering_and_blank_spellings(self, att):
        core.save_register(att.slot, att.monday,
                           self._payload({s: "Present" for s in att.students}))
        reordered = {sid: {"status": "Present", "minutes_late": "",
                           "notes": ""}
                     for sid in reversed(att.students)}
        assert reg.payload_digest(reordered) == reg.register_digest(
            att.slot, att.monday)

    def test_empty_register_differs_from_a_filled_one(self, att):
        payload = self._payload({s: "Present" for s in att.students})
        assert reg.has_unsaved_changes(att.slot, att.monday, payload)


# ── Interface wiring ───────────────────────────────────────────────

class TestInterfaceWiring:
    """The features are only worth having if a user can reach them."""

    def test_attendance_menu_offers_the_register_tools(self):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_cli,
        )
        labels = [label for label, _ in attendance_cli._MENU]
        assert any("Register Tools" in label for label in labels)

    def test_register_cli_covers_every_feature(self):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_register_cli,
        )
        labels = [label for label, _ in attendance_register_cli._MENU]
        for expected in ("Mark Whole Register", "Submit Register (lock)",
                         "Reopen Register", "Registers Not Yet Submitted",
                         "Copy Previous Session", "Record Arrival",
                         "Record Early Leave", "Mark a Date Range",
                         "Undo Last Save"):
            assert expected in labels

    def test_gui_exposes_the_lifecycle_tabs(self):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_register_views as views,
        )
        assert callable(views.build_sessions_tab)
        assert callable(views.build_bulk_tab)

    def test_lifecycle_views_do_not_import_the_register_tab(self):
        # attendance_views imports this module, so the reverse edge would
        # be a cycle waiting for someone to reorder an import.
        import ast
        import inspect

        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_register_views as views,
        )
        tree = ast.parse(inspect.getsource(views))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
        assert not any(name.endswith("attendance_views") for name in imported)
