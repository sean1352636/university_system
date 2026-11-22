"""The university's half of UCAS: seeing applicants, and deciding on them.

This is the module that writes an offer onto a real applicant's record and
emails them about it, and until now nothing tested any of it.

The tests are grouped by the question each answers rather than by the
function each calls, because the interesting behaviour is mostly about
which of the two systems is allowed to do what.
"""

from __future__ import annotations

import pytest



def _drain_as_sixth_form(monkeypatch):
    """Run the sixth form's UCAS consumers over the (temp) outbox.

    Notifications are captured rather than sent: they would reach the
    sixth form's messaging tables, which this fixture does not redirect.
    Returns the decision envelopes the handler saw.
    """
    from education_system.platform.integrations.external import (
        cross_system_bus,
    )
    from education_system.systems.sixth_form.domain.progression.university import (
        ucas_events,
    )
    seen = []
    monkeypatch.setattr(ucas_events, "_notify_decision",
                        lambda choice, payload: seen.append(payload))
    envelopes = []
    real = ucas_events.handle_decision_recorded

    def _capture(envelope):
        envelopes.append(envelope)
        real(envelope)

    unsubscribe = cross_system_bus.subscribe(
        ucas_events.EVENT_DECISION_RECORDED, _capture,
        handler_name="test.sixth_form.ucas.decision")
    try:
        cross_system_bus.poll_and_dispatch(
            "sixth_form", handler_names={"test.sixth_form.ucas.decision"})
    finally:
        unsubscribe()
    return envelopes

class TestListingApplicants:
    """Which sixth-form choices count as ours."""

    def test_only_choices_naming_this_university(self, ucas_env):
        rows = ucas_env.uni_ucas.list_applicants()
        assert [r.choice_id for r in rows] == [ucas_env.our_choice_id]
        assert rows[0].student_name == "Robin Fielding"
        assert rows[0].course_name == "Mechanical Engineering"

    def test_matches_the_institution_name_case_insensitively(self, ucas_env):
        """Nobody types an institution the same way twice."""
        rows = ucas_env.uni_ucas.list_applicants(
            university_name=ucas_env.home.upper())
        assert len(rows) == 1

    def test_carries_the_parent_application_and_student_context(self, ucas_env):
        row = ucas_env.uni_ucas.list_applicants()[0]
        assert row.ucas_id == "1234567890"
        assert row.app_status == "Submitted"
        assert row.student_email == "robin.fielding@example.test"
        assert row.student_dob == "2007-03-14"

    def test_filters_by_decision_status(self, ucas_env):
        assert ucas_env.uni_ucas.list_applicants(
            decision_status="Awaiting") != []
        assert ucas_env.uni_ucas.list_applicants(
            decision_status="Rejected") == []

    def test_rejects_a_decision_status_that_is_not_one(self, ucas_env):
        with pytest.raises(ucas_env.uni_ucas.UcasError):
            ucas_env.uni_ucas.list_applicants(decision_status="Maybe")

    def test_an_empty_university_name_is_refused_not_matched(self, ucas_env,
                                                              monkeypatch):
        """Matching on "" would silently return nothing, which reads as
        "no applicants" rather than "misconfigured"."""
        from education_system.systems.university.application.programmes import prospectus
        monkeypatch.setattr(prospectus, "institution_name", lambda: None)
        monkeypatch.setattr(ucas_env.uni_ucas, "UNIVERSITY_NAME", "")
        with pytest.raises(ucas_env.uni_ucas.UcasError):
            ucas_env.uni_ucas.list_applicants()


class TestFullApplication:
    def test_shows_every_choice_and_marks_ours(self, ucas_env):
        full = ucas_env.uni_ucas.get_full_application(ucas_env.application_id)
        assert full is not None
        assert len(full.choices) == 2
        assert full.our_choice_id == ucas_env.our_choice_id
        assert full.subjects == ["Mathematics", "Physics", "Chemistry"]

    def test_unknown_application_is_none_not_an_error(self, ucas_env):
        assert ucas_env.uni_ucas.get_full_application(99999) is None


class TestRecordingADecision:
    """The write-back, and everything it is supposed to record."""

    def test_an_offer_lands_on_the_sixth_forms_choice(self, ucas_env,
                                                      monkeypatch):
        """By event: the university no longer writes the sixth form's row;
        the sixth form applies ``ucas.decision.recorded`` itself."""
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB", terms={"reply_deadline": "2027-05-01"},
            issued_by="admissions.officer")
        # Not written across the boundary...
        assert ucas_env.sf_ucas.get_choice(
            ucas_env.our_choice_id).decision_status == "Awaiting"
        # ...until the sixth form drains its events.
        _drain_as_sixth_form(monkeypatch)
        choice = ucas_env.sf_ucas.get_choice(ucas_env.our_choice_id)
        assert choice.decision_status == "Conditional Offer"
        assert choice.offer_terms == "ABB"
        assert choice.reply_by == "2027-05-01"
        assert choice.decided_by == "admissions.officer"

    def test_redelivery_is_idempotent(self, ucas_env, monkeypatch):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB", issued_by="a.officer")
        events = _drain_as_sixth_form(monkeypatch)
        assert len(events) == 1
        before = ucas_env.sf_ucas.get_choice(ucas_env.our_choice_id)
        choice, changed = ucas_env.sf_ucas.apply_university_decision(
            events[0]["payload"])
        assert changed is False
        assert choice.decision_ref == before.decision_ref
        assert choice.decision_status == "Conditional Offer"

    def test_the_university_shows_its_decision_at_once(self, ucas_env):
        """No lag in the admissions screens while the event is in flight."""
        out = ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Unconditional Offer",
            issued_by="a.officer")
        assert out.decision_status == "Unconditional Offer"
        listed = {a.choice_id: a for a in ucas_env.uni_ucas.list_applicants()}
        assert listed[ucas_env.our_choice_id].decision_status == \
            "Unconditional Offer"
        assert listed[ucas_env.our_choice_id].sf_decision_status == "Awaiting"

    def test_a_conditional_offer_must_say_what_the_condition_is(self, ucas_env):
        with pytest.raises(ucas_env.uni_ucas.UcasError):
            ucas_env.uni_ucas.record_decision(
                ucas_env.our_choice_id, "Conditional Offer", offer_terms="  ")

    def test_an_unknown_decision_is_refused(self, ucas_env):
        with pytest.raises(ucas_env.uni_ucas.UcasError):
            ucas_env.uni_ucas.record_decision(ucas_env.our_choice_id, "Maybe")

    def test_the_decision_is_attributed(self, ucas_env):
        """The thing that had no answer before: who made this offer?"""
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Unconditional Offer",
            issued_by="a.officer")
        last = ucas_env.decision_log.last_decision(ucas_env.our_choice_id)
        assert last is not None
        assert last.decided_by == "a.officer"
        assert last.decision_status == "Unconditional Offer"
        assert last.sf_student_id == ucas_env.student_id
        assert last.decided_at

    def test_the_decision_is_audited(self, ucas_env):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Rejected", issued_by="a.officer")
        assert [d.decision_status for d in ucas_env.audit] == ["Rejected"]

    def test_every_decision_is_kept_not_overwritten(self, ucas_env):
        """A conditional offer later confirmed leaves both steps standing."""
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB", issued_by="first.officer")
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Unconditional Offer",
            issued_by="second.officer")
        history = ucas_env.decision_log.history_for_choice(
            ucas_env.our_choice_id)
        assert [d.decision_status for d in history] == [
            "Conditional Offer", "Unconditional Offer"]
        assert [d.decided_by for d in history] == [
            "first.officer", "second.officer"]

    def test_a_decision_opens_the_link(self, ucas_env):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB", issued_by="a.officer")
        link = ucas_env.links.get_link_by_choice(ucas_env.our_choice_id)
        assert link is not None
        assert link.sf_student_id == ucas_env.student_id
        # The column that was always NULL before.
        assert link.linked_by == "a.officer"

    def test_an_offer_opens_an_admissions_application(self, ucas_env,
                                                      monkeypatch):
        """The UCAS route used to run entirely beside the CRM."""
        opened = []
        monkeypatch.setattr(ucas_env.pipeline_link,
                            "ensure_application_for_link",
                            lambda link, **kw: opened.append(link.link_id))
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Unconditional Offer",
            issued_by="a.officer")
        assert len(opened) == 1

    def test_a_rejection_opens_nothing(self, ucas_env, monkeypatch):
        opened = []
        monkeypatch.setattr(ucas_env.pipeline_link,
                            "ensure_application_for_link",
                            lambda link, **kw: opened.append(link.link_id))
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Rejected", issued_by="a.officer")
        assert opened == []

    def test_a_failure_after_the_write_does_not_undo_the_decision(
            self, ucas_env, monkeypatch):
        """Everything after the sixth-form write is best-effort — an
        officer must not be told their offer failed because a side table
        was unavailable."""
        def _explode(*a, **kw):
            raise RuntimeError("link store unavailable")
        monkeypatch.setattr(ucas_env.links, "ensure_link_for_choice", _explode)

        out = ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Unconditional Offer",
            issued_by="a.officer")
        assert out.decision_status == "Unconditional Offer"
        assert ucas_env.decision_log.last_decision(
            ucas_env.our_choice_id).decision_status == "Unconditional Offer"


class TestOfferTerms:
    """The fields the sixth form used to type in from a letter."""

    def test_terms_are_stored_against_the_choice(self, ucas_env):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB",
            terms={
                "grade_requirement": "ABB",
                "reply_deadline": "2027-05-01",
                "scholarship": "Dean's Award",
                "accommodation_guaranteed": True,
            },
            issued_by="a.officer")
        issued = ucas_env.offer_terms.get_terms(ucas_env.our_choice_id)
        assert issued.grade_requirement == "ABB"
        assert issued.reply_deadline == "2027-05-01"
        assert issued.scholarship == "Dean's Award"
        assert issued.accommodation_guaranteed is True
        assert issued.issued_by == "a.officer"

    def test_a_mistyped_date_is_refused_before_anything_is_written(
            self, ucas_env):
        """Storing terms is best-effort; validating them is not, or the
        officer would never hear about the typo."""
        with pytest.raises(ucas_env.uni_ucas.UcasError):
            ucas_env.uni_ucas.record_decision(
                ucas_env.our_choice_id, "Conditional Offer",
                offer_terms="ABB",
                terms={"reply_deadline": "1st of May"},
                issued_by="a.officer")
        assert ucas_env.sf_ucas.get_choice(
            ucas_env.our_choice_id).decision_status == "Awaiting"

    def test_an_offer_cannot_expire_before_the_reply_is_due(self, ucas_env):
        with pytest.raises(ucas_env.uni_ucas.UcasError):
            ucas_env.uni_ucas.record_decision(
                ucas_env.our_choice_id, "Conditional Offer",
                offer_terms="ABB",
                terms={"reply_deadline": "2027-06-01",
                       "expiry_date": "2027-05-01"})

    def test_a_rejection_carries_no_terms(self, ucas_env):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Rejected",
            terms={"scholarship": "should be ignored"},
            issued_by="a.officer")
        assert ucas_env.offer_terms.get_terms(ucas_env.our_choice_id) is None

    def test_revising_an_offer_replaces_its_terms(self, ucas_env):
        ucas_env.offer_terms.save_terms(
            ucas_env.our_choice_id, {"reply_deadline": "2027-05-01"},
            issued_by="first.officer")
        ucas_env.offer_terms.save_terms(
            ucas_env.our_choice_id, {"reply_deadline": "2027-06-01"})
        issued = ucas_env.offer_terms.get_terms(ucas_env.our_choice_id)
        assert issued.reply_deadline == "2027-06-01"
        # An unnamed reviser does not erase who issued the offer.
        assert issued.issued_by == "first.officer"

    def test_terms_for_many_choices_come_back_keyed_by_choice(self, ucas_env):
        ucas_env.offer_terms.save_terms(ucas_env.our_choice_id,
                                        {"grade_requirement": "ABB"})
        got = ucas_env.offer_terms.terms_for_choices(
            [ucas_env.our_choice_id, ucas_env.their_choice_id])
        assert set(got) == {ucas_env.our_choice_id}


class TestTheSixthFormCannotDecide:
    """The guard, exercised through the sixth form's own data layer."""

    def test_the_school_cannot_type_an_offer_from_us(self, ucas_env):
        with pytest.raises(ucas_env.sf_ucas.UniversityOwnedFieldError):
            ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id, {
                "decision_status": "Unconditional Offer"})

    def test_the_school_can_still_edit_the_rest_of_our_choice(self, ucas_env):
        out = ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id, {
            "course_name": "Mechanical Engineering with Placement"})
        assert out.course_name == "Mechanical Engineering with Placement"

    def test_the_school_still_owns_decisions_from_other_universities(
            self, ucas_env):
        out = ucas_env.sf_ucas.update_choice(ucas_env.their_choice_id, {
            "decision_status": "Unconditional Offer"})
        assert out.decision_status == "Unconditional Offer"

    def test_the_school_still_records_the_learners_reply(self, ucas_env):
        """Firm / Insurance is the student's answer, not the university's."""
        out = ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id, {
            "final_decision": "Firm"})
        assert out.final_decision == "Firm"

    def test_a_new_choice_at_us_cannot_arrive_pre_decided(self, ucas_env):
        with pytest.raises(ucas_env.sf_ucas.UniversityOwnedFieldError):
            ucas_env.sf_ucas.create_choice(ucas_env.application_id, {
                "choice_order": 3,
                "university": ucas_env.home,
                "course_name": "Civil Engineering",
                "decision_status": "Unconditional Offer",
            })

    def test_switching_a_choice_onto_us_cannot_smuggle_an_offer(self, ucas_env):
        with pytest.raises(ucas_env.sf_ucas.UniversityOwnedFieldError):
            ucas_env.sf_ucas.update_choice(ucas_env.their_choice_id, {
                "university": ucas_env.home,
                "decision_status": "Conditional Offer",
                "offer_terms": "BBC",
            })

    def test_correcting_a_choice_off_us_keeps_its_decision(self, ucas_env):
        """Those fields belong to whoever the choice now names."""
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer", offer_terms="ABB")
        out = ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id, {
            "university": "Elsewhere University"})
        assert out.decision_status == "Conditional Offer"

    def test_a_standalone_sixth_form_keeps_every_field(self, ucas_env,
                                                       monkeypatch):
        """A college running without the university installed cannot
        establish who we are, and must not be locked out of its own data
        by an owner that will never claim it."""
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )
        monkeypatch.setattr(university_handover, "home_university_names",
                            set)
        out = ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id, {
            "decision_status": "Unconditional Offer"})
        assert out.decision_status == "Unconditional Offer"
