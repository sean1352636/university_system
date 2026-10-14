"""Unit tests for registration periods and add/drop deadlines.

``academic_terms`` said when teaching ran; nothing said when *registration*
ran. These tests pin the two verdicts that now depend on the date — may an
enrolment be accepted, and is leaving a module a drop or a withdrawal — plus
the audit trail that records which deadline was applied.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.services.bus import registration_calendar as rc

# Autumn 2026: opens 08-01, add deadline 09-15, closes 09-30,
# drop deadline 10-15, withdrawal deadline 11-30.
PERIOD = dict(
    academic_year="2026/27", name="Autumn 2026",
    registration_opens="2026-08-01", registration_closes="2026-09-30",
    add_deadline="2026-09-15", drop_deadline="2026-10-15",
    withdraw_deadline="2026-11-30",
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "calendar.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        path,
    )
    conn = sqlite3.connect(path)
    conn.close()
    rc.ensure_schema()
    return path


@pytest.fixture()
def autumn(db):
    return rc.add_period(**PERIOD)


class TestUnconfigured:
    """With no periods defined, registration behaves as it did before."""

    def test_registration_is_open(self, db):
        state = rc.registration_state()
        assert state["open"] is True
        assert state["phase"] == rc.PHASE_UNCONFIGURED

    def test_drop_is_clean(self, db):
        verdict = rc.classify_drop()
        assert verdict["allowed"] is True
        assert verdict["status"] == rc.DROP_CLEAN
        assert verdict["on_transcript"] is False


class TestRegistrationState:

    @pytest.mark.parametrize("when,phase,is_open", [
        ("2026-07-20", rc.PHASE_BEFORE_OPEN, False),
        ("2026-08-01", rc.PHASE_OPEN, True),      # opening day counts as open
        ("2026-09-15", rc.PHASE_OPEN, True),      # the add deadline itself
        ("2026-09-16", rc.PHASE_CLOSED, False),   # the day after it
    ])
    def test_phases(self, autumn, when, phase, is_open):
        state = rc.registration_state(when=when)
        assert (state["phase"], state["open"]) == (phase, is_open)

    def test_reason_names_the_deadline(self, autumn):
        state = rc.registration_state(when="2026-10-05")
        assert "2026-09-15" in state["reason"]

    def test_late_add_extends_to_the_close_date(self, db):
        rc.add_period(**{**PERIOD, "late_add_allowed": True})
        late = rc.registration_state(when="2026-09-20")
        assert late["open"] is True
        assert late["phase"] == rc.PHASE_LATE_ADD
        # ...but not past the close date.
        assert rc.registration_state(when="2026-10-05")["open"] is False


class TestClassifyDrop:

    @pytest.mark.parametrize("when,status,allowed,transcript", [
        ("2026-09-20", rc.DROP_CLEAN, True, False),
        ("2026-10-15", rc.DROP_CLEAN, True, False),      # deadline day itself
        ("2026-10-16", rc.DROP_WITHDRAWN, True, True),   # the day after
        ("2026-11-30", rc.DROP_WITHDRAWN, True, True),
        ("2026-12-01", rc.DROP_REFUSED, False, True),
    ])
    def test_verdicts(self, autumn, when, status, allowed, transcript):
        verdict = rc.classify_drop(when=when)
        assert verdict["status"] == status
        assert verdict["allowed"] is allowed
        assert verdict["on_transcript"] is transcript

    def test_period_still_governs_after_its_last_deadline(self, autumn):
        """Regression: the period must not fall out of scope once it ends.

        Selecting only periods whose window *contained* the date meant that
        the day after the withdrawal deadline the calendar read as
        unconfigured, and a late withdrawal was waved through as a clean drop.
        """
        verdict = rc.classify_drop(when="2027-03-01")
        assert verdict["phase"] != rc.PHASE_UNCONFIGURED
        assert verdict["allowed"] is False

    def test_upcoming_period_governs_before_anything_has_started(self, autumn):
        assert rc.registration_state(when="2026-01-01")["phase"] == rc.PHASE_BEFORE_OPEN


class TestAudit:

    def test_change_records_the_deadline_context(self, autumn):
        verdict = rc.classify_drop(when="2026-10-20")
        change_id = rc.record_status_change(
            "S1", "CS201", verdict["status"], from_status="Enrolled",
            changed_by="registry", source="test", verdict=verdict,
        )
        assert change_id

        history = rc.history_for("S1", "CS201")
        assert len(history) == 1
        entry = history[0]
        assert entry["to_status"] == rc.DROP_WITHDRAWN
        assert entry["from_status"] == "Enrolled"
        assert entry["deadline_applied"] == "2026-11-30"
        assert entry["period_id"] == autumn
        assert entry["source"] == "test"

    def test_history_filters_by_module(self, db):
        rc.record_status_change("S1", "CS201", "Enrolled")
        rc.record_status_change("S1", "CS301", "Enrolled")
        assert len(rc.history_for("S1")) == 2
        assert len(rc.history_for("S1", "CS301")) == 1

    def test_unconfigured_change_still_records(self, db):
        rc.record_status_change("S1", "CS201", "Dropped",
                                verdict=rc.classify_drop())
        entry = rc.history_for("S1", "CS201")[0]
        assert entry["phase"] == rc.PHASE_UNCONFIGURED
        assert entry["period_id"] is None


class TestPeriodSelection:

    def test_most_recently_started_period_wins(self, db):
        rc.add_period(**PERIOD)
        spring = rc.add_period(
            academic_year="2026/27", name="Spring 2027",
            registration_opens="2027-01-05", registration_closes="2027-01-31",
            add_deadline="2027-01-20", drop_deadline="2027-02-20",
            withdraw_deadline="2027-04-01")
        assert rc.current_period(when="2027-01-10")["period_id"] == spring
        # Before spring opens, autumn is still the one in charge.
        assert rc.current_period(when="2026-12-10")["name"] == "Autumn 2026"

    def test_inactive_periods_are_ignored(self, db, tmp_path):
        period_id = rc.add_period(**PERIOD)
        conn = sqlite3.connect(str(tmp_path / "calendar.db"))
        conn.execute("UPDATE registration_periods SET is_active = 0 WHERE period_id = ?",
                     (period_id,))
        conn.commit()
        conn.close()
        assert rc.current_period(when="2026-08-15") is None
