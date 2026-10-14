"""Complaints: the route a complaint takes, its deadlines, and who sees it.

The rules are tested pure. Raising and handling run through the services
on the conftest's throwaway database, because the promise that matters —
a complainant sees their own complaint and nobody else's — is a property
of the service's scoping, not of any one screen.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.quality import complaints as rules
from education_system.systems.apprenticeships.domain.quality.complaints import Complaint
from education_system.systems.apprenticeships.services import complaint_service
from education_system.systems.apprenticeships.services.access import PermissionDenied

TODAY = date(2026, 9, 10)


def _complaint(**overrides) -> Complaint:
    received = overrides.pop("received", TODAY)
    ack_due, response_due = rules.deadlines(received)
    fields = dict(
        complaint_id=1, reference="CMP-0001", raised_by="apprentice1", raised_role="apprentice",
        category="Assessment", subject="Late marking", description="Six weeks",
        received_at=received.isoformat(), ack_due_on=ack_due, response_due_on=response_due,
    )
    fields.update(overrides)
    return Complaint(**fields)


def _raise(actor, **overrides):
    payload = {"category": "Assessment", "subject": "Late marking",
               "description": "My unit 3 work has waited six weeks for marking."}
    payload.update(overrides)
    return complaint_service.raise_complaint(actor, payload)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestTransitions:
    @pytest.mark.parametrize(("current", "new"), [
        ("Received", "Acknowledged"),
        ("Acknowledged", "Investigating"),
        ("Acknowledged", "Resolved"),
        ("Investigating", "Resolved"),
        ("Investigating", "Escalated"),
        ("Resolved", "Closed"),
        ("Resolved", "Escalated"),
        ("Escalated", "Closed"),
    ])
    def test_the_route_a_complaint_may_take(self, current, new):
        rules.require_transition(current, new)

    @pytest.mark.parametrize(("current", "new"), [
        ("Received", "Investigating"),   # the acknowledgement cannot be skipped
        ("Received", "Resolved"),
        ("Received", "Closed"),          # nor can a complaint be closed unanswered
        ("Acknowledged", "Closed"),
        ("Resolved", "Investigating"),
        ("Escalated", "Resolved"),
    ])
    def test_everything_else_is_refused(self, current, new):
        with pytest.raises(ValidationError, match="cannot go from"):
            rules.require_transition(current, new)

    def test_a_closed_complaint_is_final(self):
        with pytest.raises(ValidationError, match="cannot change status"):
            rules.require_transition("Closed", "Received")

    def test_allowed_next_follows_the_process_order(self):
        assert _complaint(status="Acknowledged").allowed_next() == ("Investigating", "Resolved")
        assert _complaint(status="Closed").allowed_next() == ()

    def test_resolving_needs_an_outcome_and_escalating_needs_a_body(self):
        with pytest.raises(ValidationError, match="outcome"):
            rules.require_status_details("Resolved", outcome="  ", escalated_to=None)
        with pytest.raises(ValidationError, match="escalated to"):
            rules.require_status_details("Escalated", outcome="Done", escalated_to=None)
        rules.require_status_details("Resolved", outcome="Apologised", escalated_to=None)

    def test_category_is_matched_ignoring_case(self):
        assert rules.validate_category("staff CONDUCT") == "Staff conduct"
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_category("Parking")


class TestDeadlines:
    def test_deadlines_run_from_receipt(self):
        ack, respond = rules.deadlines(TODAY)
        assert ack == (TODAY + timedelta(days=config.COMPLAINT_ACK_DAYS)).isoformat()
        assert respond == (TODAY + timedelta(days=config.COMPLAINT_RESPONSE_DAYS)).isoformat()

    def test_an_unacknowledged_complaint_goes_late_first(self):
        late_ack = TODAY + timedelta(days=config.COMPLAINT_ACK_DAYS + 1)
        complaint = _complaint()
        assert complaint.ack_overdue(late_ack)
        assert not complaint.response_overdue(late_ack)
        assert complaint.overdue_label(late_ack) == "Acknowledgement overdue"
        assert complaint.rag(late_ack) == "Red"

    def test_an_acknowledged_complaint_can_still_miss_its_response(self):
        late = TODAY + timedelta(days=config.COMPLAINT_RESPONSE_DAYS + 1)
        complaint = _complaint(status="Investigating")
        assert not complaint.ack_overdue(late)
        assert complaint.response_overdue(late)
        assert complaint.overdue_label(late) == "Response overdue"

    def test_an_answered_complaint_is_never_late(self):
        complaint = _complaint(status="Resolved")
        far_future = TODAY + timedelta(days=365)
        assert not complaint.is_overdue(far_future)
        assert complaint.rag(far_future) is None

    def test_a_deadline_close_by_shows_amber(self):
        complaint = _complaint()
        assert complaint.rag(TODAY + timedelta(days=config.COMPLAINT_ACK_DAYS - 1)) == "Amber"


# ═════════════════════════════════════════════════════════════════════
# Through the services
# ═════════════════════════════════════════════════════════════════════

class TestRaising:
    def test_an_apprentices_complaint_is_about_their_own_apprenticeship(self, cohort):
        complaint = _raise(cohort["learner"], apprentice_id=9999)
        assert complaint.reference == "CMP-0001"
        assert (complaint.apprentice_id, complaint.employer_id) == (
            cohort["apprentice_id"], cohort["employer"].employer_id,
        )
        assert (complaint.status, complaint.raised_by, complaint.raised_role) == (
            "Received", "apprentice1", "apprentice",
        )
        assert complaint.ack_due_on == rules.deadlines(date.today())[0]

    def test_the_complainant_is_told_the_deadlines(self, cohort):
        complaint = _raise(cohort["learner"])
        (first,) = complaint_service.list_updates(cohort["learner"], complaint.complaint_id)
        assert complaint.ack_due_on in first.note and complaint.response_due_on in first.note

    def test_an_employer_cannot_name_somebody_elses_apprentice(self, cohort):
        with pytest.raises(PermissionDenied):
            _raise(cohort["outsider"], apprentice_id=cohort["apprentice_id"])

    def test_only_a_handler_may_backdate_receipt(self, cohort, admin):
        earlier = (date.today() - timedelta(days=3)).isoformat()
        assert _raise(admin, received_at=earlier).received_at == earlier
        assert _raise(cohort["tutor"], received_at=earlier).received_at == date.today().isoformat()

    def test_a_complaint_needs_a_description(self, cohort):
        with pytest.raises(ValidationError, match="description"):
            _raise(cohort["learner"], description="  ")


class TestWhoSeesWhat:
    def test_complainants_see_only_their_own(self, cohort, admin):
        mine = _raise(cohort["learner"])
        theirs = _raise(cohort["employer_actor"], category="Communication")
        tutors = _raise(cohort["tutor"], category="Facilities")

        assert [c.complaint_id for c in complaint_service.list_complaints(cohort["learner"])] \
            == [mine.complaint_id]
        assert [c.complaint_id for c in complaint_service.list_complaints(
            cohort["employer_actor"])] == [theirs.complaint_id]
        assert {c.complaint_id for c in complaint_service.list_complaints(admin)} == {
            mine.complaint_id, theirs.complaint_id, tutors.complaint_id,
        }

    def test_raised_by_cannot_widen_a_complainants_view(self, cohort):
        _raise(cohort["employer_actor"])
        assert complaint_service.list_complaints(cohort["learner"], raised_by="employer1") == []

    def test_opening_someone_elses_complaint_is_refused(self, cohort):
        theirs = _raise(cohort["employer_actor"])
        with pytest.raises(PermissionDenied):
            complaint_service.get_complaint(cohort["learner"], theirs.complaint_id)
        with pytest.raises(PermissionDenied):
            complaint_service.add_update(cohort["learner"], theirs.complaint_id, "Me too")

    def test_internal_notes_stay_with_the_provider(self, cohort, admin):
        complaint = _raise(cohort["learner"])
        complaint_service.add_update(admin, complaint.complaint_id, "Tutor disputes this",
                                     visible=False)
        complaint_service.add_update(admin, complaint.complaint_id, "We are looking into it",
                                     visible=True)
        seen = [u.note for u in complaint_service.list_updates(cohort["learner"],
                                                               complaint.complaint_id)]
        assert "We are looking into it" in seen
        assert "Tutor disputes this" not in seen
        assert "Tutor disputes this" in [
            u.note for u in complaint_service.list_updates(admin, complaint.complaint_id)
        ]

    def test_a_complainants_own_comment_is_always_shared(self, cohort):
        complaint = _raise(cohort["learner"])
        entry = complaint_service.add_update(cohort["learner"], complaint.complaint_id,
                                             "Still waiting", visible=False)
        assert entry.visible_to_complainant

    def test_only_a_handler_moves_a_complaint(self, cohort):
        complaint = _raise(cohort["learner"])
        with pytest.raises(PermissionDenied):
            complaint_service.acknowledge(cohort["learner"], complaint.complaint_id)


class TestHandling:
    def test_the_whole_route_with_satisfaction(self, cohort, admin):
        complaint = _raise(cohort["learner"])
        cid = complaint.complaint_id

        acknowledged = complaint_service.acknowledge(admin, cid)
        assert acknowledged.acknowledged_at == date.today().isoformat()
        assert acknowledged.handler == "admin5"

        complaint_service.change_status(admin, cid, "Investigating")
        with pytest.raises(ValidationError, match="outcome"):
            complaint_service.change_status(admin, cid, "Resolved")
        resolved = complaint_service.change_status(admin, cid, "Resolved",
                                                   outcome="Work marked; apology sent")
        assert resolved.outcome == "Work marked; apology sent"

        rated = complaint_service.record_satisfaction(cohort["learner"], cid, True)
        assert rated.satisfied is True

        closed = complaint_service.change_status(admin, cid, "Closed")
        assert closed.closed_at == date.today().isoformat()
        with pytest.raises(ValidationError, match="closed"):
            complaint_service.add_update(cohort["learner"], cid, "One more thing")

    def test_the_service_refuses_an_illegal_move(self, cohort, admin):
        complaint = _raise(cohort["learner"])
        with pytest.raises(ValidationError, match="cannot go from Received to Closed"):
            complaint_service.change_status(admin, complaint.complaint_id, "Closed")

    def test_escalation_records_where_it_went(self, cohort, admin):
        cid = _raise(cohort["learner"]).complaint_id
        complaint_service.acknowledge(admin, cid)
        complaint_service.change_status(admin, cid, "Resolved", outcome="Explained")
        escalated = complaint_service.change_status(admin, cid, "Escalated",
                                                    escalated_to="Ofsted")
        assert (escalated.status, escalated.escalated_to) == ("Escalated", "Ofsted")

    def test_satisfaction_waits_for_an_answer(self, cohort):
        complaint = _raise(cohort["learner"])
        with pytest.raises(ValidationError, match="answered"):
            complaint_service.record_satisfaction(cohort["learner"], complaint.complaint_id,
                                                  False)

    def test_status_moves_are_audited(self, cohort, admin):
        from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (  # noqa: E501
            compliance_repository,
        )

        complaint = _raise(cohort["learner"])
        complaint_service.acknowledge(admin, complaint.complaint_id)
        trail = compliance_repository.list_audit(entity="complaint",
                                                 entity_id=complaint.complaint_id)
        assert {e.action for e in trail} == {"create", "update"}


class TestWhatIsWaiting:
    def test_overdue_filters_find_the_late_ones(self, cohort, admin):
        old = _raise(admin, received_at=(date.today() - timedelta(days=10)).isoformat())
        fresh = _raise(cohort["learner"])

        assert [c.complaint_id for c in complaint_service.list_complaints(
            admin, overdue_only=True)] == [old.complaint_id]
        assert [c.complaint_id for c in complaint_service.list_complaints(
            admin, ack_overdue_only=True)] == [old.complaint_id]

        complaint_service.acknowledge(admin, old.complaint_id)
        complaint_service.acknowledge(admin, fresh.complaint_id)
        assert complaint_service.list_complaints(admin, ack_overdue_only=True) == []
        # Acknowledged, but the response is not yet late.
        assert complaint_service.list_complaints(admin, overdue_only=True) == []
        # The day after the old one's response was due, the fresh one
        # still has time.
        later = date.fromisoformat(old.response_due_on) + timedelta(days=1)
        assert [c.complaint_id for c in complaint_service.list_complaints(
            admin, overdue_only=True, today=later)] == [old.complaint_id]

    def test_filter_by_apprentice_and_status(self, cohort, admin):
        mine = _raise(cohort["learner"])
        _raise(admin, category="Facilities")
        found = complaint_service.list_complaints(
            admin, apprentice_id=cohort["apprentice_id"], status="Received",
        )
        assert [c.complaint_id for c in found] == [mine.complaint_id]

    def test_counts_for_the_screen(self, cohort, admin):
        _raise(admin, received_at=(date.today() - timedelta(days=10)).isoformat())
        _raise(cohort["learner"])
        assert complaint_service.counts(admin) == {
            "total": 2, "open": 2, "overdue": 1, "awaiting_ack": 2,
        }
