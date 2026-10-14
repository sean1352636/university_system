"""Unit tests for closing a UCAS application once the applicant is admitted.

Nothing used to end a UCAS application when the applicant actually became a
student here, so they stayed in "Admit from UCAS" for ever: listed as
*Enrolled*, and refused by Admit as an existing student — a dead end the
screen gave no way to clear.

These tests pin what gets removed (this university's choice, and the parent
application only when it was the last one) and what does not (choices at other
universities, and our own link row, which is the audit trail).
"""

from unittest.mock import MagicMock

import pytest

from education_system.systems.university.domains.admissions.domain.ucas import (
    post_admission,
)


class _Applicant:
    """The shape ``ucas.list_applicants`` returns, reduced to what is read."""

    def __init__(self, student_id, choice_id, application_id, course_code="CS"):
        self.student_id = student_id
        self.choice_id = choice_id
        self.application_id = application_id
        self.course_code = course_code


class _Link:
    def __init__(self, link_id):
        self.link_id = link_id


@pytest.fixture()
def sf(monkeypatch):
    """A stub sixth-form UCAS API recording what was deleted."""
    api = MagicMock()
    api.deleted_choices = []
    api.deleted_applications = []
    api.remaining = {}

    def _delete_choice(choice_id):
        api.deleted_choices.append(choice_id)
        return True

    def _delete_application(application_id):
        api.deleted_applications.append(application_id)
        return True

    def _list_choices(application_id):
        return api.remaining.get(application_id, [])

    api.delete_choice.side_effect = _delete_choice
    api.delete_application.side_effect = _delete_application
    api.list_choices.side_effect = _list_choices
    monkeypatch.setattr(post_admission, "_sf_ucas", lambda: api)
    return api


@pytest.fixture()
def links(monkeypatch):
    """A stub link table recording archive calls."""
    module = MagicMock()
    module.archived = []
    module.students = {}
    module.get_link_by_choice.side_effect = lambda cid: _Link(100 + cid)
    module.set_link_status.side_effect = (
        lambda link_id, status: module.archived.append((link_id, status)))
    module.attach_uni_student.side_effect = (
        lambda link_id, sid: module.students.update({link_id: sid}))

    import sys
    monkeypatch.setitem(
        sys.modules,
        "education_system.systems.university.domains.admissions.domain.ucas.ucas_links",
        module)
    return module


def _applicants(monkeypatch, rows):
    """Point ``choices_for_applicant`` at a fixed applicant list."""
    monkeypatch.setattr(post_admission, "choices_for_applicant",
                        lambda sid, university_name=None: [
                            {"choice_id": r.choice_id,
                             "application_id": r.application_id,
                             "university": None,
                             "course_code": r.course_code}
                            for r in rows if r.student_id == sid])


class TestClearAfterAdmission:

    def test_single_choice_is_removed_with_its_application(self, monkeypatch, sf, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        sf.remaining[10] = []           # nothing left after the choice goes

        summary = post_admission.clear_after_admission("C1", "U1", actor="tester")

        assert sf.deleted_choices == [11]
        assert sf.deleted_applications == [10]
        assert summary["choices_removed"] == 1
        assert summary["application_removed"] == 10
        assert not summary["errors"]

    def test_other_universities_choices_survive(self, monkeypatch, sf, links):
        """Only the choice naming us is ours to remove."""
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        sf.remaining[10] = [object()]   # a choice elsewhere is still there

        summary = post_admission.clear_after_admission("C1", "U1")

        assert sf.deleted_choices == [11]
        assert sf.deleted_applications == []
        assert summary["application_removed"] is None

    def test_link_is_archived_not_deleted(self, monkeypatch, sf, links):
        """Our link row is the audit trail of what we decided."""
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        sf.remaining[10] = []

        summary = post_admission.clear_after_admission("C1", "U1")

        assert links.archived == [(111, "archived")]
        assert links.students == {111: "U1"}
        assert summary["links_archived"] == [111]

    def test_dry_run_changes_nothing(self, monkeypatch, sf, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])

        summary = post_admission.clear_after_admission(
            "C1", "U1", delete_choices=False)

        assert sf.deleted_choices == []
        assert links.archived == []
        assert summary["choices_removed"] == 0
        assert summary["choices"]           # still reports what it found

    def test_applicant_with_no_ucas_record(self, monkeypatch, sf, links):
        """Someone admitted by another route has nothing to clear."""
        _applicants(monkeypatch, [])
        summary = post_admission.clear_after_admission("C1", "U1")
        assert summary["choices"] == []
        assert sf.deleted_choices == []
        assert post_admission.describe(summary) == "No UCAS application to clear."

    def test_blank_student_id_is_a_no_op(self, monkeypatch, sf, links):
        assert post_admission.clear_after_admission("", "U1")["choices"] == []

    def test_several_choices_at_this_university(self, monkeypatch, sf, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10),
                                  _Applicant("C1", 12, 10)])
        sf.remaining[10] = []
        summary = post_admission.clear_after_admission("C1", "U1")
        assert sorted(sf.deleted_choices) == [11, 12]
        assert summary["choices_removed"] == 2
        # The application is removed once, not once per choice.
        assert sf.deleted_applications == [10]


class TestFailureHandling:

    def test_delete_failure_is_reported_not_raised(self, monkeypatch, sf, links):
        """The student already exists; a tidy-up failure must not look fatal."""
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        sf.delete_choice.side_effect = RuntimeError("sixth form offline")

        summary = post_admission.clear_after_admission("C1", "U1")

        assert summary["choices_removed"] == 0
        assert summary["errors"]
        assert "sixth form offline" in summary["errors"][0]

    def test_missing_sixth_form_api_is_reported(self, monkeypatch, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])

        def _boom():
            raise ImportError("no sixth form installed")

        monkeypatch.setattr(post_admission, "_sf_ucas", _boom)
        summary = post_admission.clear_after_admission("C1", "U1")
        assert summary["errors"] and "no sixth form" in summary["errors"][0]

    def test_link_failure_does_not_stop_the_delete(self, monkeypatch, sf, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        sf.remaining[10] = []
        links.set_link_status.side_effect = RuntimeError("link table locked")

        summary = post_admission.clear_after_admission("C1", "U1")

        assert sf.deleted_choices == [11]
        assert summary["errors"]

    def test_unknown_student_on_the_link_is_survivable(self, monkeypatch, sf, links):
        """attach_uni_student refuses an id that is not a student here."""
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        sf.remaining[10] = []
        links.attach_uni_student.side_effect = RuntimeError("No uni student")

        summary = post_admission.clear_after_admission("C1", "U1")

        assert links.archived == [(111, "archived")]   # archived anyway
        assert summary["choices_removed"] == 1


class TestDescribe:

    def test_summarises_what_happened(self, monkeypatch, sf, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        sf.remaining[10] = []
        text = post_admission.describe(
            post_admission.clear_after_admission("C1", "U1"))
        assert "1 UCAS choice(s) removed" in text
        assert "#10 removed" in text

    def test_nothing_found(self):
        assert post_admission.describe({"choices": []}) == \
            "No UCAS application to clear."


class TestBusPort:
    """The GUI calls the bus port, not the domain module directly.

    Learners must not reach into Admissions — its allow-list is the largest
    in the university and is meant to shrink — so the student CRUD GUI goes
    through ``services.bus.ucas_bus``.
    """

    def test_forwards_to_the_domain_module(self, monkeypatch, sf, links):
        from education_system.systems.university.services.bus import ucas_bus
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        sf.remaining[10] = []

        summary = ucas_bus.clear_after_admission("C1", "U1", actor="gui")

        assert summary["choices_removed"] == 1
        assert sf.deleted_choices == [11]

    def test_blank_applicant_is_a_no_op(self):
        from education_system.systems.university.services.bus import ucas_bus
        assert ucas_bus.clear_after_admission("", "U1") is None

    def test_never_raises_into_a_successful_admission(self, monkeypatch):
        """The student already exists by the time this runs."""
        from education_system.systems.university.services.bus import ucas_bus

        def _boom():
            raise RuntimeError("admissions module missing")

        monkeypatch.setattr(ucas_bus, "_post_admission", _boom)
        assert ucas_bus.clear_after_admission("C1", "U1") is None
        assert ucas_bus.describe(None) == "The UCAS application could not be cleared."


class TestApplicantListExcludesArrivals:
    """A completed handover is not an application any more.

    The picker merges UCAS choices with cross-system handover transitions.
    Clearing the UCAS half left the applicant listed by the other half, so
    somebody admitted weeks ago still sat in "Admit from UCAS" as *expected*,
    where Admit can only refuse them.
    """

    @staticmethod
    def _rows(monkeypatch, statuses):
        from education_system.systems.university.domains.admissions.domain.ucas import (
            applicants as applicants_mod,
        )
        rows = [{"transition_id": f"t{i}", "journey_id": f"j{i}",
                 "source_system": "sixth_form", "status": status,
                 "choices": [], "application_reference": None}
                for i, status in enumerate(statuses)]

        fake = MagicMock()
        fake.list_applications.return_value = rows
        import sys
        monkeypatch.setitem(
            sys.modules,
            "education_system.platform.cross_system.university_applications", fake)
        monkeypatch.setattr(
            applicants_mod, "_identities_for",
            lambda rs: {r["transition_id"]: (f"S{r['transition_id']}", "Someone")
                        for r in rs})
        return applicants_mod

    def test_completed_and_cancelled_are_dropped(self, monkeypatch):
        mod = self._rows(monkeypatch, ["expected", "completed", "cancelled"])
        listed = mod._from_transitions()
        assert [a.decision_status for a in listed] == ["expected"]

    def test_in_flight_handovers_still_list(self, monkeypatch):
        mod = self._rows(monkeypatch, ["expected", "admitted", "offer_made"])
        assert len(mod._from_transitions()) == 3

    def test_status_matching_is_case_insensitive(self, monkeypatch):
        mod = self._rows(monkeypatch, ["Completed", "COMPLETED", "expected"])
        assert len(mod._from_transitions()) == 1
