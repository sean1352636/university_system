"""Tests for ``progression.handover_eligibility`` — the gate that decides
whether a sixth-form leaver may be handed over to the university.

Every test stubs the two source-side reads (``build_record`` and
``resolve``) and the journey registry, so nothing here touches a database.
That is deliberate: the gate's job is to turn a record into a verdict, and
the record's own assembly is ``university_handover``'s test.

The distinction under test throughout is **blocking vs advisory**. A
blocking failure is something the platform can positively disprove; an
advisory one is something it merely cannot confirm. Getting that backwards
in either direction is a real bug — too strict and a college without the
full UCAS stack can transfer nobody, too lax and the original
enrol-anybody picker is back.
"""

from __future__ import annotations

import datetime as _dt
from types import SimpleNamespace

import pytest

from education_system.systems.sixth_form.domain.progression import (
    handover_eligibility as he,
    university_handover as uh,
)


def _student(**overrides):
    base = dict(
        student_id="SF-1",
        first_name="Ada",
        middle_name=None,
        last_name="Lovelace",
        date_of_birth="2007-12-10",
        title="Ms",
        gender="female",
        email="ada@sixthform.ac.uk",
        phone=None,
        transferred_at=None,
        subject_1="Mathematics",
        subject_2="Physics",
        subject_3=None,
    )
    base.update(overrides)
    student = SimpleNamespace(**base)
    student.transfer_complete = bool(base["transferred_at"])
    student.full_name = f"{base['first_name']} {base['last_name']}"
    student.subjects = [s for s in (base["subject_1"], base["subject_2"],
                                     base["subject_3"]) if s]
    return student


def _firm(decision_status="Unconditional Offer", university="Teesside"):
    return {
        "choice_id": 1,
        "choice_order": 1,
        "university": university,
        "course_code": "CS",
        "course_name": "Computer Science",
        "entry_year": 2027,
        "decision_status": decision_status,
        "offer_terms": None,
        "final_decision": "Firm",
    }


def _record(**overrides):
    """A record that passes every check, before the test spoils one."""
    base = {
        "student_identity": {
            "sixth_form_student_id": "SF-1",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "2007-12-10",
        },
        "ucas_application": {"application_id": 5, "ucas_id": "UC-9",
                             "status": "Confirmed"},
        "confirmed_destination": {"university": "Teesside",
                                  "course_code": "CS",
                                  "course_name": "Computer Science",
                                  "entry_year": 2027},
        "achieved_qualifications": [
            {"subject": "Mathematics", "grade": "A"},
            {"subject": "Physics", "grade": "B"},
        ],
        "handover_consent": {"consent_id": 3, "purpose": "university_handover",
                             "granted_date": "2027-05-01",
                             "expires_date": None},
    }
    base.update(overrides)
    return base


@pytest.fixture()
def gate(monkeypatch):
    """Assess a student against a canned record / destination / journey.

    Returns a callable so each test states only what it is varying.
    """
    def _run(*, student=None, record=None, firm=None, destination=None,
             journey=None, home_names=("teesside",)):
        student = student or _student()
        record = _record() if record is None else record
        firm = _firm() if firm is None else firm
        if destination is None:
            destination = uh.Destination(
                system="university", institution="Teesside",
                firm_choice=firm, reason="Firm UCAS choice: Teesside")

        monkeypatch.setattr(uh, "build_record", lambda _s: record)
        monkeypatch.setattr(uh, "resolve", lambda _s: destination)
        monkeypatch.setattr(uh, "home_university_names",
                            lambda: set(home_names))

        class _FakeIdentity:
            # SYSTEM_SLOTS is left as the real module's — it is a static
            # mapping of column names, not something worth faking.
            @staticmethod
            def find_by_student(system, student_id):
                # The production lookup returns the complete journey row;
                # preserve that contract so existing destination slots are
                # visible to the duplicate-enrolment gate.
                return journey

            @staticmethod
            def get(journey_id):
                return journey

        import education_system.platform.cross_system.identity_service as ids
        for name in ("find_by_student", "get"):
            monkeypatch.setattr(ids, name, getattr(_FakeIdentity, name))
        return he.assess(student)
    return _run


class TestHappyPath:
    def test_a_complete_candidate_is_ready(self, gate):
        readiness = gate()
        assert readiness.blockers == ()
        assert readiness.warnings == ()
        assert readiness.ready is True
        assert readiness.clean is True
        assert readiness.status_label == "Ready"
        assert readiness.summary() == ""

    def test_right_to_study_is_not_a_source_side_check(self, gate):
        """The sixth form holds no immigration evidence at all.

        A check here could only ever answer "cannot tell", and one that
        fails for every learner in every deployment trains people to
        ignore the column it sits in. It lives on the destination — as an
        ``admission_requirements`` row the conversion gate gate consults,
        and as the acknowledgement the import picker demands.
        """
        readiness = gate()
        assert readiness.get("right_to_study") is None
        assert he.RIGHT_TO_STUDY_NOTE

    def test_destination_course_is_reported(self, gate):
        readiness = gate()
        assert he.destination_course(readiness) == "Computer Science (CS)"


class TestDestination:
    def test_a_firm_choice_elsewhere_blocks(self, gate):
        elsewhere = uh.Destination(
            system="external", institution="Durham", firm_choice=_firm(
                university="Durham"),
            reason="Firm UCAS choice is Durham")
        readiness = gate(destination=elsewhere)
        check = readiness.get("destination")
        assert check.blocking and not check.passed
        assert "Durham" in check.detail

    def test_no_firm_choice_blocks(self, gate):
        """``resolve`` routes a leaver here by default when no Firm choice is
        recorded. Routing a leaver and admitting a student are different
        decisions, and only the second one needs evidence."""
        no_firm = uh.Destination(
            system="university", institution=None, firm_choice=None,
            reason="No Firm UCAS choice recorded")
        readiness = gate(destination=no_firm, firm=None,
                         record=_record(confirmed_destination=None))
        check = readiness.get("destination")
        assert check.blocking and not check.passed
        assert "No Firm UCAS choice" in check.detail

    def test_unconfigured_home_institution_warns_but_does_not_block(self, gate):
        """A platform that cannot say what it calls itself must not conclude
        that some other name is a different place — nor stop transferring."""
        readiness = gate(home_names=())
        check = readiness.get("destination")
        assert not check.passed
        assert check.blocking is False
        assert check in readiness.warnings
        assert readiness.ready is True


class TestOfferAndConditions:
    def test_awaiting_a_decision_blocks(self, gate):
        firm = _firm(decision_status="Awaiting")
        readiness = gate(firm=firm, destination=uh.Destination(
            system="university", institution="Teesside", firm_choice=firm,
            reason="Firm"))
        offer = readiness.get("offer")
        assert offer.blocking and not offer.passed
        assert "Awaiting" in offer.detail

    def test_rejected_offer_blocks(self, gate):
        firm = _firm(decision_status="Rejected")
        readiness = gate(firm=firm, destination=uh.Destination(
            system="university", institution="Teesside", firm_choice=firm,
            reason="Firm"))
        assert not readiness.get("offer").passed
        assert readiness.ready is False

    def test_unconditional_offer_needs_no_conditions(self, gate):
        readiness = gate(record=_record(
            ucas_application={"application_id": 5, "status": "Replied"}))
        conditions = readiness.get("conditions")
        assert conditions.passed
        assert "no conditions" in conditions.detail

    def test_unmet_conditional_offer_blocks(self, gate):
        firm = _firm(decision_status="Conditional Offer")
        readiness = gate(
            firm=firm,
            destination=uh.Destination(system="university",
                                       institution="Teesside",
                                       firm_choice=firm, reason="Firm"),
            record=_record(ucas_application={"application_id": 5,
                                             "status": "Replied"}))
        conditions = readiness.get("conditions")
        assert conditions.blocking and not conditions.passed
        assert "not yet confirmed" in conditions.detail

    @pytest.mark.parametrize("status", ["Confirmed", "Clearing"])
    def test_a_settled_application_discharges_a_conditional_offer(
        self, gate, status
    ):
        firm = _firm(decision_status="Conditional Offer")
        readiness = gate(
            firm=firm,
            destination=uh.Destination(system="university",
                                       institution="Teesside",
                                       firm_choice=firm, reason="Firm"),
            record=_record(ucas_application={"application_id": 5,
                                             "status": status}))
        assert readiness.get("conditions").passed
        assert readiness.ready is True

    def test_conditions_are_not_double_reported_when_there_is_no_offer(
        self, gate
    ):
        """``offer`` already blocks on "no offer"; the conditions check must
        not restate it as a second, separate problem."""
        firm = _firm(decision_status="Awaiting")
        readiness = gate(
            firm=firm,
            destination=uh.Destination(system="university",
                                       institution="Teesside",
                                       firm_choice=firm, reason="Firm"),
            record=_record(ucas_application={"application_id": 5,
                                             "status": "Submitted"}))
        assert [c.key for c in readiness.blockers] == ["offer"]


class TestResults:
    def test_missing_results_block_a_conditional_offer(self, gate):
        firm = _firm(decision_status="Conditional Offer")
        readiness = gate(
            firm=firm,
            destination=uh.Destination(system="university",
                                       institution="Teesside",
                                       firm_choice=firm, reason="Firm"),
            record=_record(achieved_qualifications=None,
                           ucas_application={"application_id": 5,
                                             "status": "Confirmed"}))
        results = readiness.get("results")
        assert results.blocking and not results.passed
        assert "evidence" in results.detail

    def test_missing_results_only_warn_behind_an_unconditional_offer(self, gate):
        readiness = gate(record=_record(achieved_qualifications=None))
        results = readiness.get("results")
        assert not results.passed
        assert results.blocking is False
        assert readiness.ready is True


class TestConsent:
    def test_absent_consent_blocks(self, gate):
        readiness = gate(record=_record(handover_consent=None))
        consent = readiness.get("consent")
        assert consent.blocking and not consent.passed
        assert "university_handover" in consent.detail

    def test_expired_consent_blocks(self, gate):
        yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
        readiness = gate(record=_record(handover_consent={
            "consent_id": 3, "granted_date": "2020-01-01",
            "expires_date": yesterday}))
        consent = readiness.get("consent")
        assert consent.blocking and not consent.passed
        assert yesterday in consent.detail

    def test_future_expiry_is_fine(self, gate):
        tomorrow = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
        readiness = gate(record=_record(handover_consent={
            "consent_id": 3, "granted_date": "2027-01-01",
            "expires_date": tomorrow}))
        assert readiness.get("consent").passed


class TestExistingRecords:
    def test_already_a_university_student_blocks(self, gate):
        readiness = gate(journey={"journey_id": "J-1",
                                  "university_student_id": "1234567"})
        check = readiness.get("not_already_here")
        assert check.blocking and not check.passed
        assert "1234567" in check.detail

    def test_a_journey_without_a_university_slot_passes(self, gate):
        readiness = gate(journey={"journey_id": "J-1",
                                  "university_student_id": None})
        assert readiness.get("not_already_here").passed

    def test_no_journey_at_all_passes(self, gate):
        readiness = gate(journey=None)
        assert readiness.get("not_already_here").passed

    def test_a_completed_transfer_blocks(self, gate):
        readiness = gate(student=_student(transferred_at="2027-08-20 09:00"))
        check = readiness.get("not_transferred")
        assert check.blocking and not check.passed
        assert "2027-08-20" in check.detail


class TestIdentity:
    def test_a_missing_dob_blocks(self, gate):
        readiness = gate(student=_student(date_of_birth=None))
        check = readiness.get("identity")
        assert check.blocking and not check.passed
        assert "date of birth" in check.detail


class TestRobustness:
    def test_a_source_that_raises_does_not_take_the_gate_down(
        self, monkeypatch
    ):
        """A college with a broken UCAS module gets a verdict, not a
        traceback out of the middle of a list-building loop."""
        def _boom(_student):
            raise RuntimeError("ucas.db is locked")

        monkeypatch.setattr(uh, "build_record", _boom)
        monkeypatch.setattr(uh, "resolve", _boom)
        monkeypatch.setattr(uh, "home_university_names", lambda: {"teesside"})
        import education_system.platform.cross_system.identity_service as ids
        monkeypatch.setattr(ids, "find_by_student", lambda *a, **k: None)

        readiness = he.assess(_student())
        assert readiness.ready is False
        assert readiness.summary()
        assert readiness.status_label == "Blocked"

    def test_summary_lists_blockers_before_warnings(self, gate):
        readiness = gate(record=_record(handover_consent=None,
                                        achieved_qualifications=None),
                         home_names=())
        lines = readiness.summary().splitlines()
        assert lines[0].startswith("✗")
        assert lines[-1].startswith("!")
        assert readiness.status_label == "Blocked"
