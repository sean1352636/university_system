"""Unit tests for closing a UCAS application once the applicant is admitted.

Nothing used to end a UCAS application when the applicant actually became a
student here, so they stayed in "Admit from UCAS" for ever. The first fix
deleted the sixth form's choice (and sometimes its application), which erased
the college's record of where the learner went and had the university writing
another system's data.

These tests pin the replacement: nothing is deleted. Our own link row is
stamped with the student and archived (our record that the choice was
placed), and ``university.student.enrolled`` is published once per choice for
the sixth form to mark its own choice *Placed*.
"""

from unittest.mock import MagicMock

import pytest

from education_system.platform.integrations.external import cross_system_bus
from education_system.systems.university.domains.admissions.domain.ucas import (
    post_admission,
)


class _Applicant:
    """The shape ``ucas.list_applicants`` returns, reduced to what is read."""

    def __init__(self, student_id, choice_id, application_id, course_code="CS",
                 placed=False):
        self.student_id = student_id
        self.choice_id = choice_id
        self.application_id = application_id
        self.course_code = course_code
        self.placed = placed


class _Link:
    def __init__(self, link_id):
        self.link_id = link_id


@pytest.fixture()
def published(monkeypatch):
    """Capture bus publishes instead of writing the live auth database."""
    events = []

    def _publish(event_name, **kwargs):
        events.append((event_name, kwargs))
        return f"evt-{len(events)}"

    monkeypatch.setattr(cross_system_bus, "publish_cross_system", _publish)
    monkeypatch.setattr(post_admission, "_university_student",
                        lambda uni_id: {"start_date": "2026-09-21",
                                        "course": "Computing"} if uni_id else {})
    monkeypatch.setattr(post_admission, "_journey_for", lambda sid: "J-1")
    return events


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
    def _choices(sid, university_name=None, include_placed=False):
        return [{"choice_id": r.choice_id,
                 "application_id": r.application_id,
                 "university": None,
                 "course_code": r.course_code,
                 "course_name": "Computing",
                 "entry_year": 2027,
                 "journey_id": None}
                for r in rows
                if r.student_id == sid and (include_placed or not r.placed)]
    monkeypatch.setattr(post_admission, "choices_for_applicant", _choices)


class TestClearAfterAdmission:

    def test_choice_is_placed_not_deleted(self, monkeypatch, published, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])

        summary = post_admission.clear_after_admission("C1", "U1", actor="tester")

        assert summary["choices_placed"] == 1
        assert summary["choices_removed"] == 0
        assert summary["application_removed"] is None
        assert not summary["errors"]
        assert [name for name, _kw in published] == ["university.student.enrolled"]

    def test_event_payload(self, monkeypatch, published, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        post_admission.clear_after_admission("C1", "U1")
        _name, kw = published[0]
        assert kw["target_system"] == "sixth_form"
        assert kw["journey_id"] == "J-1"
        assert kw["sf_student_id"] == "C1"
        assert kw["sf_choice_id"] == 11
        assert kw["university_student_id"] == "U1"
        assert kw["course_code"] == "CS"
        assert kw["entry_year"] == 2027
        assert kw["start_date"] == "2026-09-21"
        assert kw["enrolled_on"]
        assert kw["idempotency_key"].endswith(":U1:11")

    def test_link_is_archived_with_the_student(self, monkeypatch, published, links):
        """Our link row is our record that the choice was placed."""
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])

        summary = post_admission.clear_after_admission("C1", "U1")

        assert links.archived == [(111, "archived")]
        assert links.students == {111: "U1"}
        assert summary["links_archived"] == [111]

    def test_dry_run_changes_nothing(self, monkeypatch, published, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])

        summary = post_admission.clear_after_admission(
            "C1", "U1", delete_choices=False)

        assert published == []
        assert links.archived == []
        assert summary["choices_placed"] == 0
        assert summary["choices"]           # still reports what it found

    def test_applicant_with_no_ucas_record_is_still_announced(
            self, monkeypatch, published, links):
        """Someone admitted by another route has no choice to place, but
        the sixth form's destinations still want to hear where they went."""
        _applicants(monkeypatch, [])
        summary = post_admission.clear_after_admission("C1", "U1")
        assert summary["choices"] == []
        assert len(published) == 1
        assert published[0][1]["sf_choice_id"] is None

    def test_already_placed_is_not_announced_again(self, monkeypatch, published, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10, placed=True)])
        summary = post_admission.clear_after_admission("C1", "U1")
        assert published == []
        assert post_admission.describe(summary) == "No open UCAS application to clear."

    def test_blank_student_id_is_a_no_op(self, monkeypatch, published, links):
        assert post_admission.clear_after_admission("", "U1")["choices"] == []
        assert published == []

    def test_several_choices_at_this_university(self, monkeypatch, published, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10),
                                  _Applicant("C1", 12, 10)])
        summary = post_admission.clear_after_admission("C1", "U1")
        assert summary["choices_placed"] == 2
        assert sorted(kw["sf_choice_id"] for _n, kw in published) == [11, 12]


class TestFailureHandling:

    def test_publish_failure_is_reported_not_raised(self, monkeypatch, published, links):
        """The student already exists; a tidy-up failure must not look fatal."""
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])

        def _boom(*_a, **_k):
            raise RuntimeError("bus offline")

        monkeypatch.setattr(cross_system_bus, "publish_cross_system", _boom)
        summary = post_admission.clear_after_admission("C1", "U1")

        assert summary["choices_placed"] == 0
        assert summary["errors"]
        assert "bus offline" in summary["errors"][0]

    def test_link_failure_does_not_stop_the_event(self, monkeypatch, published, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        links.set_link_status.side_effect = RuntimeError("link table locked")

        summary = post_admission.clear_after_admission("C1", "U1")

        assert summary["choices_placed"] == 1
        assert summary["errors"]

    def test_unknown_student_on_the_link_is_survivable(self, monkeypatch, published, links):
        """attach_uni_student refuses an id that is not a student here."""
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        links.attach_uni_student.side_effect = RuntimeError("No uni student")

        summary = post_admission.clear_after_admission("C1", "U1")

        assert links.archived == [(111, "archived")]   # archived anyway
        assert summary["choices_placed"] == 1


class TestDescribe:

    def test_summarises_what_happened(self, monkeypatch, published, links):
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])
        text = post_admission.describe(
            post_admission.clear_after_admission("C1", "U1"))
        assert "1 UCAS choice(s) marked placed" in text
        assert "removed" not in text

    def test_nothing_found(self):
        assert post_admission.describe({"choices": []}) == \
            "No open UCAS application to clear."


class TestBusPort:
    """The GUI calls the bus port, not the domain module directly.

    Learners must not reach into Admissions — its allow-list is the largest
    in the university and is meant to shrink — so the student CRUD GUI goes
    through ``services.bus.ucas_bus``.
    """

    def test_forwards_to_the_domain_module(self, monkeypatch, published, links):
        from education_system.systems.university.services.bus import ucas_bus
        _applicants(monkeypatch, [_Applicant("C1", 11, 10)])

        summary = ucas_bus.clear_after_admission("C1", "U1", actor="gui")

        assert summary["choices_placed"] == 1
        assert published

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
