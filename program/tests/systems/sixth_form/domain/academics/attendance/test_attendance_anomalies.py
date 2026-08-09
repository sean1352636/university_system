"""Tests for marking-anomaly detection.

Every finding is a shape with a confidence, never a conclusion: the
usual explanation is a teacher under time pressure.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_anomalies as anomalies,
)


def registers(attdb, *, count: int, absences: int = 0,
              vary: bool = False) -> tuple[str, str]:
    """``count`` registers on consecutive days, some with absences."""
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    for index in range(count):
        date = (monday - _dt.timedelta(days=index)).isoformat()
        payload = {}
        for position, student_id in enumerate(attdb.students):
            if index < absences and position == 0:
                payload[student_id] = {"code": "O"}
            elif vary and position == (index % 3):
                payload[student_id] = {"code": "L", "minutes_late": 7}
            else:
                payload[student_id] = {"code": "/"}
        core.save_register(attdb.slot, date, payload, allow_retro=True)
    return ((monday - _dt.timedelta(days=count - 1)).isoformat(),
            attdb.prev_monday)


# ── 1. Profiling ───────────────────────────────────────────────────

class TestProfile:

    def test_a_slot_profile_counts_its_registers(self, attdb):
        date_from, date_to = registers(attdb, count=5)
        profile = anomalies.profile_slot(attdb.slot, date_from=date_from,
                                         date_to=date_to)
        assert profile.registers == 5
        assert profile.marks == 15

    def test_absences_are_counted(self, attdb):
        date_from, date_to = registers(attdb, count=5, absences=2)
        profile = anomalies.profile_slot(attdb.slot, date_from=date_from,
                                         date_to=date_to)
        assert profile.absences == 2
        assert profile.absence_rate is not None

    def test_identical_registers_show_low_variety(self, attdb):
        date_from, date_to = registers(attdb, count=5)
        profile = anomalies.profile_slot(attdb.slot, date_from=date_from,
                                         date_to=date_to)
        assert profile.distinct_digests == 1
        assert profile.repetition_rate == 80.0

    def test_varied_registers_show_variety(self, attdb):
        date_from, date_to = registers(attdb, count=5, vary=True)
        profile = anomalies.profile_slot(attdb.slot, date_from=date_from,
                                         date_to=date_to)
        assert profile.distinct_digests > 1

    def test_an_unmarked_slot_profiles_as_empty(self, attdb):
        profile = anomalies.profile_slot(attdb.pm_slot,
                                         date_from=attdb.prev_monday,
                                         date_to=attdb.prev_monday)
        assert profile.registers == 0
        assert profile.absence_rate is None


# ── 2. Detectors ───────────────────────────────────────────────────

class TestDetectors:

    def test_a_slot_that_never_records_absence_is_flagged(self, attdb):
        date_from, date_to = registers(attdb, count=6)
        findings = anomalies.all_present_slots(date_from=date_from,
                                               date_to=date_to,
                                               min_registers=3)
        assert [f.slot_id for f in findings] == [attdb.slot]
        assert findings[0].pattern == anomalies.ALL_PRESENT

    def test_a_slot_that_records_absence_is_not(self, attdb):
        date_from, date_to = registers(attdb, count=6, absences=1)
        findings = anomalies.all_present_slots(date_from=date_from,
                                               date_to=date_to,
                                               min_registers=3)
        assert findings == []

    def test_too_few_registers_says_nothing(self, attdb):
        # Below the minimum, everything looks anomalous.
        date_from, date_to = registers(attdb, count=2)
        assert anomalies.all_present_slots(date_from=date_from,
                                           date_to=date_to,
                                           min_registers=8) == []

    def test_identical_registers_are_flagged(self, attdb):
        date_from, date_to = registers(attdb, count=6)
        findings = anomalies.identical_registers(date_from=date_from,
                                                 date_to=date_to,
                                                 min_registers=3)
        assert [f.slot_id for f in findings] == [attdb.slot]

    def test_a_slot_recording_absence_but_never_lateness_is_noted(self,
                                                                  attdb):
        date_from, date_to = registers(attdb, count=6, absences=2)
        findings = anomalies.no_lateness_slots(date_from=date_from,
                                               date_to=date_to,
                                               min_registers=3)
        assert [f.slot_id for f in findings] == [attdb.slot]
        assert findings[0].confidence == anomalies.LOW

    def test_round_late_minutes_are_noted(self, attdb):
        monday = _dt.date.fromisoformat(attdb.prev_monday)
        for index in range(12):
            date = (monday - _dt.timedelta(days=index)).isoformat()
            core.save_register(attdb.slot, date,
                               {attdb.s1: {"code": "L",
                                           "minutes_late": 10}},
                               allow_retro=True)
        findings = anomalies.round_late_minutes(
            date_from=(monday - _dt.timedelta(days=11)).isoformat(),
            date_to=attdb.prev_monday, minimum=5)
        assert [f.slot_id for f in findings] == [attdb.slot]

    def test_bulk_saves_are_detected(self, attdb):
        # A term marked in one minute is a catch-up session, and those
        # registers are memory rather than observation.
        date_from, date_to = registers(attdb, count=8)
        findings = anomalies.bulk_saves(date_from=date_from,
                                        date_to=date_to, minimum=5)
        assert findings
        assert findings[0].pattern == anomalies.BULK_SAVE


# ── 3. The sweep ───────────────────────────────────────────────────

class TestSweep:

    def test_the_sweep_gathers_every_detector(self, attdb):
        registers(attdb, count=10)
        report = anomalies.sweep(min_registers=3)
        patterns = {f.pattern for f in report.findings}
        assert anomalies.ALL_PRESENT in patterns
        assert anomalies.IDENTICAL in patterns

    def test_findings_are_ordered_by_confidence(self, attdb):
        registers(attdb, count=10)
        report = anomalies.sweep(min_registers=3)
        ranks = [f.rank for f in report.findings]
        assert ranks == sorted(ranks)

    def test_a_clean_college_reports_nothing_much(self, attdb):
        registers(attdb, count=10, absences=4, vary=True)
        report = anomalies.sweep(min_registers=3)
        assert anomalies.ALL_PRESENT not in {f.pattern
                                             for f in report.findings}

    def test_the_summary_reads_sensibly(self, attdb):
        report = anomalies.sweep(min_registers=3)
        assert "examined" in report.summary

    def test_findings_can_be_grouped_by_person(self, attdb):
        from education_system.systems.sixth_form.domain.academics.class_groups \
            import class_groups as cg
        cg.update_group(attdb.group, {"course_id": 1, "group_name": "12A",
                                      "teacher": "Mr Patel"})
        registers(attdb, count=10)
        grouped = anomalies.by_owner(anomalies.sweep(min_registers=3))
        assert "Mr Patel" in grouped

    def test_one_slot_can_be_examined_on_its_own(self, attdb):
        registers(attdb, count=10)
        health = anomalies.slot_health(attdb.slot)
        assert health["slot_id"] == attdb.slot
        assert health["profile"].registers == 10
        assert health["looks_healthy"] is False
