"""Employer contacts, the contact log and commitments.

Scoping matters most here: a tutor keeps in touch with the employers of
their own caseload, not with every employer the provider works with.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.employers import contacts as rules
from education_system.systems.apprenticeships.domain.employers.contacts import (
    ContactLogEntry,
    EmployerCommitment,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.employers import (
    employer_contact_service,
    employer_service,
)
from education_system.systems.apprenticeships.application.security.access import Actor, PermissionDenied

TODAY = date.today()


def _days(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


def _commitment(**overrides) -> EmployerCommitment:
    fields = dict(commitment_id=1, employer_id=1, commitment="Release on Fridays",
                  due_date=_days(-1))
    fields.update(overrides)
    return EmployerCommitment(**fields)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestRules:
    def test_channels_and_roles_come_from_the_lists(self):
        assert rules.validate_channel("video CALL") == "Video call"
        assert rules.validate_contact_role("levy account holder") == "Levy account holder"
        assert rules.validate_contact_role("") is None
        with pytest.raises(ValidationError, match="Say how"):
            rules.validate_channel("")
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_contact_role("Chief of Vibes")

    def test_a_commitment_category_defaults_to_other(self):
        assert rules.validate_category(None) == "Other"

    def test_escalation_stops_at_the_top_level(self):
        assert rules.next_escalation_level(_commitment(escalation_level=2)) == 3
        with pytest.raises(ValidationError, match="as far as it goes"):
            rules.next_escalation_level(_commitment(escalation_level=3))
        with pytest.raises(ValidationError, match="only an open one"):
            rules.next_escalation_level(_commitment(status="Met"))

    def test_a_commitment_closes_once_as_met_or_withdrawn(self):
        assert rules.validate_closure(_commitment(), "met") == "Met"
        with pytest.raises(ValidationError, match="Met or Withdrawn"):
            rules.validate_closure(_commitment(), "Escalated")
        with pytest.raises(ValidationError, match="already"):
            rules.validate_closure(_commitment(status="Withdrawn"), "Met")


class TestFlags:
    def test_only_an_outstanding_commitment_is_overdue(self):
        assert _commitment().is_overdue(TODAY)
        assert _commitment(status="Escalated").is_overdue(TODAY)
        assert not _commitment(status="Met").is_overdue(TODAY)
        assert not _commitment(due_date=_days(3)).is_overdue(TODAY)

    def test_commitment_rag(self):
        assert _commitment().rag(TODAY) == "Red"
        assert _commitment(due_date=_days(5), escalation_level=1).rag(TODAY) == "Amber"
        assert _commitment(due_date=_days(5)).rag(TODAY) is None
        assert _commitment(status="Met").rag(TODAY) == "Green"

    def test_follow_up_rag(self):
        entry = ContactLogEntry(log_id=1, employer_id=1, contacted_on=_days(-5), channel="Phone",
                                summary="s", logged_by="u", follow_up_date=_days(-1))
        assert entry.follow_up_rag(TODAY) == "Red"
        entry.follow_up_date = _days(2)
        assert entry.follow_up_rag(TODAY) == "Amber"
        entry.follow_up_done_at = _days(0)
        assert entry.follow_up_rag(TODAY) is None


# ═════════════════════════════════════════════════════════════════════
# Scope
# ═════════════════════════════════════════════════════════════════════

@pytest.fixture
def other_employer(cohort, admin):
    return employer_service.create_employer(admin, {"name": "Rival Ltd", "status": "Active"})


class TestScope:
    def test_a_tutor_sees_only_their_caseloads_employers(self, cohort, other_employer):
        seen = employer_contact_service.list_employers(cohort["tutor"])
        assert [e.employer.employer_id for e in seen] == [cohort["employer"].employer_id]
        with pytest.raises(PermissionDenied):
            employer_contact_service.list_contacts(cohort["tutor"], other_employer.employer_id)

    def test_an_admin_sees_every_employer(self, cohort, admin, other_employer):
        assert len(employer_contact_service.list_employers(admin)) == 2

    def test_a_tutor_with_no_staff_record_sees_nobody(self, cohort):
        unlinked = Actor(username="newbie", role="staff")
        assert employer_contact_service.list_employers(unlinked) == []

    def test_apprentices_and_employers_do_not_keep_the_contact_log(self, cohort):
        for actor in (cohort["learner"], cohort["employer_actor"]):
            with pytest.raises(PermissionDenied):
                employer_contact_service.list_employers(actor)


# ═════════════════════════════════════════════════════════════════════
# Contacts
# ═════════════════════════════════════════════════════════════════════

class TestContacts:
    def test_a_contact_carries_a_role(self, cohort, admin):
        added = employer_service.add_manager(admin, cohort["employer"].employer_id, {
            "full_name": "Pat", "contact_role": "finance",
        })
        assert added.contact_role == "Finance"

    def test_staff_add_contacts_but_cannot_link_a_login(self, cohort):
        added = employer_contact_service.add_contact(
            cohort["tutor"], cohort["employer"].employer_id,
            {"full_name": "Lee", "contact_role": "Line manager / Supervisor",
             "username": "lee", "is_primary": True},
        )
        assert (added.contact_role, added.username, added.is_primary) == (
            "Line manager / Supervisor", None, False,
        )

    def test_an_admin_may_link_a_login(self, cohort, admin):
        added = employer_contact_service.add_contact(
            admin, cohort["employer"].employer_id, {"full_name": "Kim", "username": "kim"}
        )
        assert added.username == "kim"

    def test_a_contact_role_is_updated(self, cohort):
        added = employer_contact_service.add_contact(
            cohort["tutor"], cohort["employer"].employer_id, {"full_name": "Lee"}
        )
        updated = employer_contact_service.update_contact(
            cohort["tutor"], added.manager_id, {"contact_role": "HR"}
        )
        assert (updated.contact_role, updated.full_name) == ("HR", "Lee")


# ═════════════════════════════════════════════════════════════════════
# The contact log
# ═════════════════════════════════════════════════════════════════════

def _log(cohort, **overrides):
    payload = {"channel": "Phone", "summary": "Checked on release for training",
               "contacted_on": _days(-2)}
    payload.update(overrides)
    return employer_contact_service.log_contact(
        cohort["tutor"], cohort["employer"].employer_id, payload
    )


class TestContactLog:
    def test_a_conversation_is_logged_with_who_and_about_whom(self, cohort):
        manager = employer_service.list_managers(
            Actor(username="admin5", role="admin"), cohort["employer"].employer_id)[0]
        entry = _log(cohort, contact_id=manager.manager_id,
                     apprentice_id=cohort["apprentice_id"], channel="visit")
        assert (entry.channel, entry.contact_name, entry.apprentice_name, entry.logged_by) == (
            "Visit", "Dana Reed", "Jo Bell", "tutor1",
        )

    def test_the_apprentice_must_work_for_the_employer(self, cohort, admin):
        stranger = apprentice_service.create_apprentice(
            admin, {"given_name": "Sam", "family_name": "Else"}
        )
        with pytest.raises(ValidationError, match="does not work for"):
            _log(cohort, apprentice_id=stranger.apprentice_id)

    def test_the_contact_must_belong_to_the_employer(self, cohort, admin, other_employer):
        theirs = employer_service.add_manager(
            admin, other_employer.employer_id, {"full_name": "Rival Person"}
        )
        with pytest.raises(ValidationError, match="different employer"):
            _log(cohort, contact_id=theirs.manager_id)

    def test_dates_must_make_sense(self, cohort):
        with pytest.raises(ValidationError, match="future"):
            _log(cohort, contacted_on=_days(1))
        with pytest.raises(ValidationError, match="before the contact"):
            _log(cohort, follow_up_date=_days(-3))

    def test_follow_ups_are_found_by_date_and_closed(self, cohort):
        late = _log(cohort, follow_up_date=_days(-1))
        soon = _log(cohort, follow_up_date=_days(5))
        _log(cohort)
        tutor = cohort["tutor"]
        assert [e.log_id for e in employer_contact_service.follow_ups(tutor)] == [
            late.log_id, soon.log_id,
        ]
        assert [e.log_id for e in employer_contact_service.follow_ups(
            tutor, overdue_only=True)] == [late.log_id]
        assert [e.log_id for e in employer_contact_service.follow_ups(
            tutor, due_by=_days(2))] == [late.log_id]

        done = employer_contact_service.complete_follow_up(tutor, late.log_id)
        assert (done.follow_up_done_by, done.follow_up_open) == ("tutor1", False)
        with pytest.raises(ValidationError, match="no open follow-up"):
            employer_contact_service.complete_follow_up(tutor, late.log_id)

    def test_the_log_filters_by_apprentice(self, cohort):
        _log(cohort, apprentice_id=cohort["apprentice_id"])
        _log(cohort)
        mine = employer_contact_service.list_contact_log(
            cohort["tutor"], apprentice_id=cohort["apprentice_id"]
        )
        assert len(mine) == 1


# ═════════════════════════════════════════════════════════════════════
# Commitments
# ═════════════════════════════════════════════════════════════════════

def _commit(cohort, actor=None, **overrides):
    payload = {"commitment": "Release Jo every Friday",
               "category": "Release for off-the-job training", "due_date": _days(-3),
               "apprentice_id": cohort["apprentice_id"]}
    payload.update(overrides)
    return employer_contact_service.add_commitment(
        actor or cohort["tutor"], cohort["employer"].employer_id, payload
    )


class TestCommitments:
    def test_an_overdue_commitment_is_flagged(self, cohort):
        late = _commit(cohort)
        _commit(cohort, commitment="Mentor", category="Mentoring", due_date=_days(10))
        overdue = employer_contact_service.list_commitments(cohort["tutor"], overdue_only=True)
        assert [c.commitment_id for c in overdue] == [late.commitment_id]
        assert (late.status, late.escalation_level, late.created_by) == ("Open", 0, "tutor1")

    def test_escalating_records_who_and_why(self, cohort, admin):
        commitment = _commit(cohort)
        once = employer_contact_service.escalate_commitment(
            cohort["tutor"], commitment.commitment_id, reason="Not released twice"
        )
        assert (once.status, once.escalation_level, once.escalated_by,
                once.escalation_reason, once.escalated_at) == (
            "Escalated", 1, "tutor1", "Not released twice", TODAY.isoformat(),
        )
        employer_contact_service.escalate_commitment(admin, commitment.commitment_id, reason="b")
        top = employer_contact_service.escalate_commitment(
            admin, commitment.commitment_id, reason="c"
        )
        assert top.escalation_level == 3 and "Not released twice" in (top.notes or "")
        with pytest.raises(ValidationError, match="as far as it goes"):
            employer_contact_service.escalate_commitment(admin, commitment.commitment_id,
                                                         reason="d")

    def test_escalating_needs_a_reason(self, cohort):
        commitment = _commit(cohort)
        with pytest.raises(ValidationError, match="reason"):
            employer_contact_service.escalate_commitment(
                cohort["tutor"], commitment.commitment_id, reason=" "
            )

    def test_a_met_commitment_is_closed(self, cohort):
        commitment = _commit(cohort)
        met = employer_contact_service.close_commitment(
            cohort["tutor"], commitment.commitment_id, status="Met"
        )
        assert (met.status, met.closed_at, met.is_overdue(TODAY)) == ("Met", TODAY.isoformat(),
                                                                       False)
        with pytest.raises(ValidationError, match="can no longer change"):
            employer_contact_service.update_commitment(
                cohort["tutor"], commitment.commitment_id, {"commitment": "x"}
            )

    def test_withdrawing_needs_a_reason(self, cohort):
        commitment = _commit(cohort)
        with pytest.raises(ValidationError, match="why"):
            employer_contact_service.close_commitment(
                cohort["tutor"], commitment.commitment_id, status="Withdrawn"
            )

    def test_the_employer_can_read_their_own_commitments_but_not_add_them(self, cohort):
        _commit(cohort)
        employer = cohort["employer_actor"]
        assert len(employer_contact_service.list_commitments(employer)) == 1
        with pytest.raises(PermissionDenied):
            _commit(cohort, actor=employer)
        with pytest.raises(PermissionDenied):
            employer_contact_service.list_commitments(
                cohort["outsider"], cohort["employer"].employer_id
            )

    def test_commitments_filter_by_due_date_and_apprentice(self, cohort):
        _commit(cohort, due_date=_days(-3))
        _commit(cohort, commitment="Later", due_date=_days(20), apprentice_id=None)
        tutor = cohort["tutor"]
        assert len(employer_contact_service.list_commitments(
            tutor, due_from=_days(0), due_to=_days(30))) == 1
        assert len(employer_contact_service.list_commitments(
            tutor, apprentice_id=cohort["apprentice_id"])) == 1
