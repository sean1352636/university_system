"""Tests for ``progression.university_progression`` — the sixth form's half
of the University Progression board.

Every source is stubbed, so nothing here touches a database. What the
board is *for* is turning four scattered facts into one ordered list, and
the two things that must not regress are the ordering rule (trouble
first) and the refusal rule (a blocked learner is not submitted by
accident, and a bulk run reports every failure).

The stranded case gets the most attention. It is the state the whole
board exists to surface: a learner marked Left whose announcement never
landed has gone from the sixth-form roll without arriving anywhere, and
they are invisible to the Year 13 cohort query that feeds everything else.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from education_system.systems.sixth_form.domain.progression import (
    handover_eligibility as he,
    university_handover as uh,
)
from education_system.systems.sixth_form.domain.progression.university import (
    board as up,
)


def _student(student_id, name, **overrides):
    first, _, last = name.partition(" ")
    base = dict(
        student_id=student_id, first_name=first, middle_name=None,
        last_name=last or first, date_of_birth="2007-05-01", title="Mx",
        gender="other", email=f"{student_id}@sixthform.ac.uk", phone=None,
        transferred_at=None, status="Active",
    )
    base.update(overrides)
    student = SimpleNamespace(**base)
    student.transfer_complete = bool(base["transferred_at"])
    student.full_name = name
    student.subjects = ["Mathematics"]
    return student


_FIRM = {
    "choice_id": 1, "university": "Teesside", "course_code": "CS",
    "course_name": "Computer Science", "entry_year": 2027,
    "decision_status": "Unconditional Offer", "final_decision": "Firm",
}


def _record(**overrides):
    base = {
        "student_identity": {"first_name": "A", "last_name": "B",
                             "date_of_birth": "2007-05-01"},
        "ucas_application": {"application_id": 1, "ucas_id": "UC1",
                             "status": "Confirmed"},
        "confirmed_destination": dict(_FIRM),
        "achieved_qualifications": [{"subject": "Mathematics", "grade": "A"}],
        "handover_consent": {"consent_id": 1, "granted_date": "2027-05-01",
                             "expires_date": None},
    }
    base.update(overrides)
    return base


READY = _student("SF-READY", "Ready Learner")
BLOCKED = _student("SF-BLOCK", "Blocked Learner")
STRANDED = _student("SF-STRAND", "Stranded Learner", status="Left")
HERE = _student("SF-HERE", "Enrolled Learner")
DONE = _student("SF-DONE", "Done Learner", status="Left",
                transferred_at="2027-08-18 09:00")
#: On the roll and holding a UCAS application, but with no Year 13
#: enrolment row — deliberately absent from ``state.cohort``.
APPLIED = _student("SF-APPLIED", "Applied Learner")

_ALL = {s.student_id: s
        for s in (READY, BLOCKED, STRANDED, HERE, DONE, APPLIED)}


@pytest.fixture()
def sources(monkeypatch):
    """Stub the students table, the handover assembly and the registry."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sd,
    )
    from education_system.systems.sixth_form.domain.progression.university import ucas as ucas_data
    state = SimpleNamespace(
        cohort=[READY, BLOCKED, HERE],
        incomplete=[STRANDED],
        applications=[],
        records={"SF-BLOCK": _record(handover_consent=None)},
        journeys={"SF-HERE": {"journey_id": "J-HERE",
                              "university_student_id": "1234567"}},
        transferred=[],
    )

    # Stubbed even where a test does not care about UCAS: the board reads
    # applications to build its cohort, and an unstubbed read would go to
    # the real sixth-form database and put whoever happens to live there
    # on the board.
    monkeypatch.setattr(ucas_data, "list_applications",
                        lambda **kw: state.applications)

    monkeypatch.setattr(sd, "list_year_13_students", lambda: state.cohort)
    monkeypatch.setattr(sd, "list_incomplete_transfers",
                        lambda: state.incomplete)
    monkeypatch.setattr(sd, "get_student", lambda sid: _ALL.get(sid))

    def _transferred(sid, moved_by=None):
        state.transferred.append((sid, moved_by))
        return DONE

    monkeypatch.setattr(sd, "mark_transferred", _transferred)
    monkeypatch.setattr(uh, "build_record",
                        lambda s: state.records.get(s.student_id, _record()))
    monkeypatch.setattr(
        uh, "resolve",
        lambda s: uh.Destination("university", "Teesside", "Firm", dict(_FIRM)))
    monkeypatch.setattr(uh, "home_university_names", lambda: {"teesside"})
    monkeypatch.setattr(he, "journeys_for", lambda ids: state.journeys)
    return state


class TestBoard:
    def test_every_state_is_recognised(self, sources):
        board = up.board()
        assert board.get("SF-STRAND").state == up.STRANDED
        assert board.get("SF-BLOCK").state == up.BLOCKED
        assert board.get("SF-READY").state == up.READY
        assert board.get("SF-HERE").state == up.ENROLLED

    def test_trouble_sorts_to_the_top(self, sources):
        """On results day the useful screen is not an alphabetical roll."""
        assert up.board().rows[0].state == up.STRANDED

    def test_stranded_leavers_are_included_though_they_left_the_cohort(
        self, sources
    ):
        """They were marked Left, so the Year 13 query cannot see them —
        and they are exactly who the board is for."""
        assert "SF-STRAND" not in {s.student_id for s in sources.cohort}
        assert up.board().get("SF-STRAND") is not None

    def test_a_stranded_row_says_what_went_wrong(self, sources):
        row = up.board().get("SF-STRAND")
        assert row.warnings
        assert "never" in " ".join(row.warnings).lower()

    def test_an_enrolled_learner_outranks_their_eligibility_verdict(
        self, sources
    ):
        """A learner demonstrably enrolled at the university did not fail to
        get there, whatever the checks now say about them."""
        row = up.board().get("SF-HERE")
        assert row.state == up.ENROLLED
        assert row.university_student_id == "1234567"

    def test_a_ucas_applicant_outside_the_cohort_is_on_the_board(
        self, sources
    ):
        """The gap this closes.

        Every verdict on this board is a UCAS verdict — the destination is
        the Firm choice, the checks are offer, conditions and results — but
        the cohort came from the Year 13 *enrolment* table alone. A learner
        with an application and no enrolment row was reasoned about by
        nothing and shown by nothing.
        """
        sources.applications.append(
            SimpleNamespace(application_id=9, student_id="SF-APPLIED",
                            cycle_year=2027, status="Submitted"))
        assert "SF-APPLIED" not in {s.student_id for s in sources.cohort}
        assert "SF-APPLIED" not in {s.student_id
                                    for s in sources.incomplete}
        row = up.board().get("SF-APPLIED")
        assert row is not None
        assert row.full_name == "Applied Learner"

    def test_an_applicant_already_on_the_board_is_not_duplicated(
        self, sources
    ):
        """Most applicants are enrolled Year 13s — that is the normal case,
        not a collision to be surprised by."""
        sources.applications.append(
            SimpleNamespace(application_id=1, student_id="SF-READY",
                            cycle_year=2027, status="Submitted"))
        rows = [r for r in up.board().rows if r.student_id == "SF-READY"]
        assert len(rows) == 1

    def test_several_applications_for_one_learner_add_them_once(
        self, sources
    ):
        """A re-applicant has one row per cycle, and one place on a board
        that is about people rather than about applications."""
        sources.applications.extend([
            SimpleNamespace(application_id=9, student_id="SF-APPLIED",
                            cycle_year=2026, status="Submitted"),
            SimpleNamespace(application_id=10, student_id="SF-APPLIED",
                            cycle_year=2027, status="Draft"),
        ])
        rows = [r for r in up.board().rows if r.student_id == "SF-APPLIED"]
        assert len(rows) == 1

    def test_a_draft_application_still_counts(self, sources):
        """A draft that never went anywhere is not noise on a board about
        what is stopping people — it is the answer."""
        sources.applications.append(
            SimpleNamespace(application_id=9, student_id="SF-APPLIED",
                            cycle_year=2027, status="Draft"))
        assert up.board().get("SF-APPLIED") is not None

    def test_an_applicant_whose_student_row_is_gone_is_skipped(
        self, sources
    ):
        """Only reachable mid-delete — the FK cascades. Skipping is right
        either way: there is no learner left to progress."""
        sources.applications.append(
            SimpleNamespace(application_id=9, student_id="SF-VANISHED",
                            cycle_year=2027, status="Submitted"))
        assert up.board().get("SF-VANISHED") is None

    def test_a_college_without_ucas_still_gets_its_board(
        self, sources, monkeypatch
    ):
        """The UCAS source is additive, never load-bearing."""
        from education_system.systems.sixth_form.domain.progression.university import ucas as ucas_data

        def _boom(**_kw):
            raise RuntimeError("no UCAS module here")

        monkeypatch.setattr(ucas_data, "list_applications", _boom)
        board = up.board()
        assert board.get("SF-READY") is not None
        assert board.get("SF-STRAND") is not None

    def test_only_the_right_rows_offer_submit(self, sources):
        board = up.board()
        assert board.get("SF-READY").can_submit
        assert board.get("SF-STRAND").can_submit      # a retry
        assert not board.get("SF-BLOCK").can_submit
        assert not board.get("SF-HERE").can_submit

    def test_destination_and_course_are_carried(self, sources):
        row = up.board().get("SF-READY")
        assert row.destination == "Teesside"
        assert row.course == "Computer Science (CS)"

    def test_counts_and_summary(self, sources):
        board = up.board()
        assert board.counts()[up.STRANDED] == 1
        assert "1 stranded" in board.summary_line()

    def test_a_broken_cohort_query_yields_an_empty_board_not_a_crash(
        self, sources, monkeypatch
    ):
        from education_system.systems.sixth_form.domain.learners.students import (
            students as sd,
        )

        def _boom():
            raise RuntimeError("sixthform.db is locked")

        monkeypatch.setattr(sd, "list_year_13_students", _boom)
        monkeypatch.setattr(sd, "list_incomplete_transfers", _boom)
        assert up.board().rows == []


class TestPrepare:
    @pytest.fixture(autouse=True)
    def _released(self, monkeypatch):
        class _Result:
            boundary = "sixth_form->university"
            included = ["student_identity", "ucas_application"]
            withheld_no_consent = ["reference"]
            withheld_restricted = ["safeguarding_reference"]
            missing_required = []
            payload = {"student_identity": {}, "ucas_application": {},
                       "offer_conditions": {}, "handover_consent": {}}

        monkeypatch.setattr(uh, "build", lambda s, **k: _Result())

    def test_reports_what_would_cross(self, sources):
        prepared = up.prepare("SF-READY")
        assert prepared.ok
        assert "student_identity" in prepared.included
        assert "reference" in prepared.withheld_no_consent
        assert "safeguarding_reference" in prepared.withheld_restricted

    def test_sends_nothing(self, sources):
        """The whole point: the release decision becomes reviewable without
        performing it."""
        up.prepare("SF-READY")
        assert sources.transferred == []

    def test_a_blocked_learner_reports_blockers(self, sources):
        prepared = up.prepare("SF-BLOCK")
        assert not prepared.ok
        assert any("consent" in b.lower() for b in prepared.blockers)

    def test_unknown_student(self, sources):
        assert not up.prepare("SF-NOBODY").ok

    def test_describe_is_readable(self, sources):
        text = up.prepare("SF-READY").describe()
        assert "Included (2)" in text and "Withheld — no consent (1)" in text


class TestSubmit:
    def test_a_blocked_learner_is_refused_and_nothing_runs(self, sources):
        result = up.submit("SF-BLOCK")
        assert not result.ok
        assert "Blocked" in result.detail
        assert sources.transferred == []

    def test_force_overrides(self, sources):
        result = up.submit("SF-BLOCK", force=True, moved_by="registrar")
        assert result.ok
        assert sources.transferred == [("SF-BLOCK", "registrar")]

    def test_delegates_rather_than_reimplementing(self, sources):
        """``mark_transferred`` already ends the enrolment, revokes access,
        records the transition and publishes. Any second implementation of
        that is a second thing to keep correct."""
        up.submit("SF-READY", moved_by="office")
        assert sources.transferred == [("SF-READY", "office")]

    def test_an_announcement_that_did_not_land_is_a_failure(
        self, sources, monkeypatch
    ):
        """mark_transferred is best-effort and leaves transferred_at unset
        when the bus write failed. That unset column is the honest answer,
        so it must not be reported as a success with a caveat."""
        from education_system.systems.sixth_form.domain.learners.students import (
            students as sd,
        )
        monkeypatch.setattr(sd, "mark_transferred",
                            lambda sid, moved_by=None: STRANDED)
        result = up.submit("SF-READY")
        assert not result.ok
        assert result.state == up.STRANDED

    def test_an_exception_becomes_a_result(self, sources, monkeypatch):
        from education_system.systems.sixth_form.domain.learners.students import (
            students as sd,
        )

        def _boom(sid, moved_by=None):
            raise RuntimeError("bus down")

        monkeypatch.setattr(sd, "mark_transferred", _boom)
        result = up.submit("SF-READY")
        assert not result.ok and "bus down" in result.detail


class TestBulk:
    def test_one_failure_does_not_end_the_batch(self, sources, monkeypatch):
        """Results day is the point of this function, and a run that aborts
        halfway leaves an operator with no idea which half went."""
        from education_system.systems.sixth_form.domain.learners.students import (
            students as sd,
        )

        def _flaky(sid, moved_by=None):
            if sid == "SF-BLOCK":
                raise RuntimeError("db locked")
            return DONE

        monkeypatch.setattr(sd, "mark_transferred", _flaky)
        results = up.submit_many(["SF-READY", "SF-BLOCK", "SF-HERE"],
                                 force=True)
        assert len(results) == 3
        assert [r.ok for r in results] == [True, False, True]
        assert "db locked" in next(r for r in results if not r.ok).detail

    def test_retry_stranded_forces_and_covers_the_incomplete_list(
        self, sources
    ):
        results = up.retry_stranded(moved_by="office")
        assert [r.student_id for r in results] == ["SF-STRAND"]
        assert sources.transferred == [("SF-STRAND", "office")]

    def test_retry_stranded_with_nothing_to_do(self, sources):
        sources.incomplete = []
        assert up.retry_stranded() == []
