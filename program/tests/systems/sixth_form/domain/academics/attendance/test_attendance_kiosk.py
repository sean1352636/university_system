"""Tests for kiosk and QR check-in.

The rule the whole module is built around is in section 4: a tap never
raises. Every failure is an outcome on the returned object, because the
worst possible place for an exception is a queue of learners at a door.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_kiosk as kiosk,
    attendance_register as reg,
)


@pytest.fixture
def terminal(attdb):
    """A room-mode terminal standing in R1, where slot 1 is taught."""
    return kiosk.register_device("R1-door", room="R1")


@pytest.fixture
def card(attdb):
    return kiosk.issue_token(attdb.s1, kind=kiosk.KIND_CARD)


# ── 1. Devices ─────────────────────────────────────────────────────

class TestDevices:

    def test_a_device_can_be_registered(self, attdb):
        device = kiosk.register_device("Front desk", mode=kiosk.ENTRANCE)
        assert device.device_id > 0
        assert device.mode == kiosk.ENTRANCE

    def test_the_key_is_returned_once_and_then_withheld(self, attdb):
        device = kiosk.register_device("R1-door", room="R1")
        assert device.api_key
        assert kiosk.get_device(device.device_id).api_key is None

    def test_a_room_device_needs_a_room(self, attdb):
        with pytest.raises(core.ValidationError, match="needs a room"):
            kiosk.register_device("Nowhere", mode=kiosk.ROOM)

    def test_duplicate_names_are_rejected(self, terminal):
        with pytest.raises(core.ValidationError, match="already exists"):
            kiosk.register_device("R1-door", room="R1")

    def test_an_unknown_mode_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Device mode"):
            kiosk.register_device("Odd", mode="telepathy")

    def test_the_right_key_authenticates(self, terminal):
        assert kiosk.authenticate("R1-door", terminal.api_key).device_id == \
            terminal.device_id

    def test_the_wrong_key_does_not(self, terminal):
        with pytest.raises(core.ValidationError, match="Unknown device"):
            kiosk.authenticate("R1-door", "not-the-key")

    def test_a_deactivated_device_cannot_authenticate(self, terminal):
        kiosk.set_device_active(terminal.device_id, False)
        with pytest.raises(core.ValidationError, match="deactivated"):
            kiosk.authenticate("R1-door", terminal.api_key)

    def test_rotating_invalidates_the_old_key(self, terminal):
        rotated = kiosk.rotate_key(terminal.device_id)
        assert rotated.api_key != terminal.api_key
        with pytest.raises(core.ValidationError):
            kiosk.authenticate("R1-door", terminal.api_key)

    def test_a_never_seen_device_reads_as_stale(self, terminal):
        health = {h.device.name: h for h in kiosk.device_health()}
        assert health["R1-door"].stale is True

    def test_authenticating_marks_it_seen(self, terminal):
        kiosk.authenticate("R1-door", terminal.api_key)
        assert kiosk.get_device(terminal.device_id).last_seen_at is not None


# ── 2. Tokens ──────────────────────────────────────────────────────

class TestTokens:

    def test_a_token_resolves_to_its_owner(self, attdb, card):
        student_id, verdict = kiosk.resolve_token(card.token)
        assert (student_id, verdict) == (attdb.s1, kiosk.MARKED)

    def test_an_unknown_token_says_so(self, attdb):
        assert kiosk.resolve_token("nonsense")[1] == kiosk.UNKNOWN_TOKEN

    def test_a_revoked_token_stops_working(self, attdb, card):
        kiosk.revoke_token(card.token)
        assert kiosk.resolve_token(card.token)[1] == kiosk.REVOKED

    def test_an_expired_token_stops_working(self, attdb):
        yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
        token = kiosk.issue_token(attdb.s2, expires_on=yesterday)
        assert kiosk.resolve_token(token.token)[1] == kiosk.EXPIRED

    def test_issuing_a_replacement_revokes_the_old_one(self, attdb, card):
        kiosk.issue_token(attdb.s1)
        assert kiosk.get_token(card.token).revoked is True

    def test_an_existing_card_number_can_be_enrolled(self, attdb):
        token = kiosk.issue_token(attdb.s1, token="0123456789")
        assert token.token == "0123456789"

    def test_a_card_number_cannot_belong_to_two_people(self, attdb):
        kiosk.issue_token(attdb.s1, token="0123456789")
        with pytest.raises(core.ValidationError, match="already in use"):
            kiosk.issue_token(attdb.s2, token="0123456789")

    def test_an_unknown_learner_cannot_hold_a_card(self, attdb):
        with pytest.raises(core.ValidationError, match="No student"):
            kiosk.issue_token("NOPE")


# ── 3. Working out which lesson ────────────────────────────────────

class TestSlotResolution:

    def test_the_lesson_in_progress_is_found(self, attdb):
        assert kiosk.current_slot_for(attdb.s1, date=attdb.monday,
                                      at_time="09:10") == attdb.slot

    def test_arriving_early_still_finds_it(self, attdb):
        assert kiosk.current_slot_for(attdb.s1, date=attdb.monday,
                                      at_time="08:55") == attdb.slot

    def test_too_early_finds_nothing(self, attdb):
        assert kiosk.current_slot_for(attdb.s1, date=attdb.monday,
                                      at_time="07:00") is None

    def test_after_the_lesson_finds_nothing(self, attdb):
        assert kiosk.current_slot_for(attdb.s1, date=attdb.monday,
                                      at_time="10:30") is None

    def test_the_afternoon_slot_is_found_in_the_afternoon(self, attdb):
        assert kiosk.current_slot_for(attdb.s1, date=attdb.monday,
                                      at_time="15:00") == attdb.pm_slot

    def test_a_day_with_no_lessons_finds_nothing(self, attdb):
        assert kiosk.current_slot_for(attdb.s1, date=attdb.tuesday,
                                      at_time="09:10") is None

    @pytest.mark.parametrize("late,code", [
        (0, "/"), (5, "L"), (30, "L"), (31, "U"), (90, "U"),
    ])
    def test_lateness_decides_the_code(self, attdb, late, code):
        assert kiosk.code_for_arrival(late) == code


# ── 4. The tap ─────────────────────────────────────────────────────

class TestCheckIn:

    def test_an_on_time_tap_marks_present(self, attdb, terminal, card):
        result = kiosk.check_in(card.token, device=terminal,
                                date=attdb.monday, at_time="09:00")
        assert result.outcome == kiosk.MARKED
        assert result.code == "/"
        assert result.slot_id == attdb.slot

    def test_the_mark_reaches_the_register(self, attdb, terminal, card):
        kiosk.check_in(card.token, device=terminal, date=attdb.monday,
                       at_time="09:00")
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.status == "Present"
        assert record.arrival_time == "09:00"
        assert record.data_source == kiosk.KIND_QR

    def test_a_late_tap_derives_the_minutes(self, attdb, terminal, card):
        result = kiosk.check_in(card.token, device=terminal,
                                date=attdb.monday, at_time="09:12")
        assert result.minutes_late == 12
        assert result.code == "L"

    def test_a_very_late_tap_lands_on_u(self, attdb, terminal, card):
        result = kiosk.check_in(card.token, device=terminal,
                                date=attdb.monday, at_time="09:45")
        assert result.code == "U"

    def test_a_second_tap_is_a_duplicate_not_a_second_mark(
            self, attdb, terminal, card):
        kiosk.check_in(card.token, device=terminal, date=attdb.monday,
                       at_time="09:00")
        again = kiosk.check_in(card.token, device=terminal,
                               date=attdb.monday, at_time="09:20")
        assert again.outcome == kiosk.DUPLICATE
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.arrival_time == "09:00"

    def test_no_lesson_is_an_outcome_not_an_error(self, attdb, terminal,
                                                  card):
        result = kiosk.check_in(card.token, device=terminal,
                                date=attdb.monday, at_time="20:00")
        assert result.outcome == kiosk.NO_LESSON
        assert result.ok is False

    def test_an_unknown_card_is_an_outcome_not_an_error(self, attdb,
                                                        terminal):
        result = kiosk.check_in("nonsense", device=terminal,
                                date=attdb.monday, at_time="09:00")
        assert result.outcome == kiosk.UNKNOWN_TOKEN
        assert "reception" in result.message

    def test_the_wrong_room_is_caught(self, attdb, card):
        elsewhere = kiosk.register_device("R9-door", room="R9")
        result = kiosk.check_in(card.token, device=elsewhere,
                                date=attdb.monday, at_time="09:00")
        assert result.outcome == kiosk.WRONG_ROOM
        assert core.get_record_for(attdb.slot, attdb.s1, attdb.monday) is None

    def test_room_enforcement_can_be_relaxed(self, attdb, card):
        elsewhere = kiosk.register_device("R9-door", room="R9",
                                          enforce_room=False)
        result = kiosk.check_in(card.token, device=elsewhere,
                                date=attdb.monday, at_time="09:00")
        assert result.outcome == kiosk.MARKED

    def test_an_entrance_device_records_being_on_site(self, attdb, card):
        door = kiosk.register_device("Front", mode=kiosk.ENTRANCE)
        result = kiosk.check_in(card.token, device=door, date=attdb.monday,
                                at_time="08:30")
        assert result.outcome == kiosk.ON_SITE
        assert core.get_record_for(attdb.slot, attdb.s1, attdb.monday) is None

    def test_a_submitted_register_refuses_the_tap(self, attdb, terminal,
                                                  card):
        core.save_register(
            attdb.slot, attdb.monday,
            {sid: {"status": "Present"} for sid in attdb.students})
        reg.submit_register(attdb.slot, attdb.monday, submitted_by="teacher")
        result = kiosk.check_in(card.token, device=terminal,
                                date=attdb.monday, at_time="09:00")
        assert result.outcome == kiosk.LOCKED

    def test_a_deactivated_device_refuses(self, attdb, terminal, card):
        kiosk.set_device_active(terminal.device_id, False)
        result = kiosk.check_in(card.token, device=terminal,
                                date=attdb.monday, at_time="09:00")
        assert result.outcome == kiosk.DEVICE_INACTIVE

    def test_reception_can_check_somebody_in_without_a_card(self, attdb,
                                                            terminal):
        result = kiosk.check_in_student(attdb.s2, device=terminal,
                                        date=attdb.monday, at_time="09:00")
        assert result.outcome == kiosk.MARKED

    def test_a_device_can_be_named_rather_than_passed(self, attdb, terminal,
                                                      card):
        result = kiosk.check_in(card.token, device="R1-door",
                                date=attdb.monday, at_time="09:00")
        assert result.outcome == kiosk.MARKED


# ── 5. The event log ───────────────────────────────────────────────

class TestEvents:

    def test_every_tap_is_logged(self, attdb, terminal, card):
        kiosk.check_in(card.token, device=terminal, date=attdb.monday,
                       at_time="09:00")
        kiosk.check_in("nonsense", device=terminal, date=attdb.monday,
                       at_time="09:01")
        assert len(kiosk.list_events(date=attdb.monday)) == 2

    def test_outcomes_are_counted(self, attdb, terminal, card):
        kiosk.check_in(card.token, device=terminal, date=attdb.monday,
                       at_time="09:00")
        kiosk.check_in("nonsense", device=terminal, date=attdb.monday,
                       at_time="09:01")
        breakdown = kiosk.outcome_breakdown(date=attdb.monday)
        assert breakdown[kiosk.MARKED] == 1
        assert breakdown[kiosk.UNKNOWN_TOKEN] == 1

    def test_unrecognised_cards_are_collected(self, attdb, terminal):
        kiosk.check_in("nonsense", device=terminal, date=attdb.monday,
                       at_time="09:00")
        assert len(kiosk.unrecognised_cards()) == 1

    def test_taps_can_be_traced_to_a_learner(self, attdb, terminal, card):
        kiosk.check_in(card.token, device=terminal, date=attdb.monday,
                       at_time="09:00")
        assert kiosk.student_taps(attdb.s1, date=attdb.monday)

    def test_an_unknown_outcome_filter_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Outcome must be"):
            kiosk.list_events(outcome="Vanished")
