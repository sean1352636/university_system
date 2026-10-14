"""Tests for ``progression.destination_courses`` and the UCAS course picker.

The module's job is to offer this university's real course catalogue where
a UCAS choice used to be three free-text boxes, without taking away the
free text — four of a learner's five choices are at institutions this
platform does not run.

The catalogue read itself is stubbed throughout. What matters here is the
lookup behaviour (what matches, and just as importantly what does not) and
the graceful degradation when the university is not installed at all,
because that is the case a sixth form running on its own hits every time.
"""

from __future__ import annotations

import builtins

import pytest

from education_system.systems.sixth_form.domain.progression import (
    destination_courses as dc,
)

_CATALOGUE = [
    dc.CourseOption(code="CS", name="Computer Science", min_tariff=112),
    dc.CourseOption(code="DS", name="Data Science", min_tariff=104),
    dc.CourseOption(code="BUS", name="Business Management"),
    # A name with its own brackets — the reason lookups are by whole label
    # rather than by splitting the display string apart again.
    dc.CourseOption(code="BUSP", name="Business (with Placement)"),
]


class TestCourseOption:
    def test_label_pairs_name_and_code(self):
        assert _CATALOGUE[0].label == "Computer Science (CS)"


class TestHomeCourses:
    def test_maps_the_university_catalogue(self, monkeypatch):
        rows = [{"code": "CS", "name": "Computer Science",
                 "min_tariff": 112, "duration": "3 years"}]
        import education_system.systems.university.domains.academics.domain.services.admissions_selection as sel
        monkeypatch.setattr(sel, "list_active_courses", lambda: rows)

        out = dc.home_courses()
        assert [o.code for o in out] == ["CS"]
        assert out[0].name == "Computer Science"
        assert out[0].min_tariff == 112
        assert out[0].duration == "3 years"

    def test_rows_without_a_code_are_dropped(self, monkeypatch):
        import education_system.systems.university.domains.academics.domain.services.admissions_selection as sel
        monkeypatch.setattr(sel, "list_active_courses",
                            lambda: [{"code": "", "name": "Nameless"},
                                     {"code": "CS", "name": "Computer Science"}])
        assert [o.code for o in dc.home_courses()] == ["CS"]

    def test_a_missing_university_degrades_to_an_empty_list(self, monkeypatch):
        """A sixth form running without the university installed keeps its
        plain text fields; it does not get a traceback opening a dialog."""
        import education_system.systems.university.domains.academics.domain.services.admissions_selection as sel

        def _boom():
            raise RuntimeError("university not installed")

        monkeypatch.setattr(sel, "list_active_courses", _boom)
        assert dc.home_courses() == []


class TestLookups:
    def test_by_label_round_trips(self):
        assert dc.by_label(_CATALOGUE, "Data Science (DS)").code == "DS"

    def test_by_label_handles_a_name_containing_brackets(self):
        """Splitting the label on '(' would return 'with Placement)' here."""
        option = dc.by_label(_CATALOGUE, "Business (with Placement) (BUSP)")
        assert option is not None and option.code == "BUSP"

    def test_by_label_miss_is_none(self):
        assert dc.by_label(_CATALOGUE, "Aeronautics (AERO)") is None

    @pytest.mark.parametrize("code", ["CS", "cs", " cs "])
    def test_by_code_is_case_and_space_insensitive(self, code):
        assert dc.by_code(_CATALOGUE, code).name == "Computer Science"

    def test_by_code_empty_is_none(self):
        assert dc.by_code(_CATALOGUE, "") is None

    def test_by_name_matches_a_typed_course(self):
        assert dc.by_name(_CATALOGUE, "  computer   science ").code == "CS"

    def test_by_name_does_not_guess(self):
        """An abbreviation is not a match. Attaching the wrong course code
        to somebody's firm choice is worse than leaving it unset."""
        assert dc.by_name(_CATALOGUE, "Comp Sci") is None

    def test_resolve_prefers_the_code(self):
        assert dc.resolve(_CATALOGUE, code="DS",
                          name="Computer Science").code == "DS"

    def test_resolve_falls_back_to_the_name(self):
        """Choices recorded before the picker existed often carry a course
        name and no code at all."""
        assert dc.resolve(_CATALOGUE, code="",
                          name="Business Management").code == "BUS"

    def test_resolve_miss_is_none(self):
        assert dc.resolve(_CATALOGUE, code="XX", name="Something") is None


class TestCliPicker:
    """``ucas_cli._pick_course`` — the terminal half of the same feature."""

    @pytest.fixture(autouse=True)
    def _catalogue(self, monkeypatch):
        from education_system.systems.sixth_form.domain.progression.university.cli import ucas as ucas_cli
        monkeypatch.setattr(ucas_cli.destination_courses, "home_courses",
                            lambda: _CATALOGUE)
        monkeypatch.setattr(ucas_cli.destination_courses,
                            "home_institution_name", lambda: "Teesside")
        return ucas_cli

    @staticmethod
    def _answers(monkeypatch, *replies):
        it = iter(replies)
        monkeypatch.setattr(builtins, "input", lambda _p="": next(it))

    def test_picking_a_number_returns_name_code_and_institution(
        self, _catalogue, monkeypatch
    ):
        self._answers(monkeypatch, "2")
        assert _catalogue._pick_course() == ("Data Science", "DS", "Teesside")

    def test_zero_falls_through_to_typing(self, _catalogue, monkeypatch):
        self._answers(monkeypatch, "0")
        assert _catalogue._pick_course() is None

    def test_bad_input_re_prompts(self, _catalogue, monkeypatch):
        self._answers(monkeypatch, "abc", "99", "1")
        assert _catalogue._pick_course()[1] == "CS"

    def test_an_existing_course_is_the_default(self, _catalogue, monkeypatch):
        self._answers(monkeypatch, "")          # accept the default
        assert _catalogue._pick_course(current_code="BUS")[1] == "BUS"

    def test_a_course_elsewhere_defaults_to_typing(
        self, _catalogue, monkeypatch
    ):
        self._answers(monkeypatch, "")
        assert _catalogue._pick_course(current_code="DUR7") is None

    def test_no_catalogue_means_no_prompt_at_all(
        self, _catalogue, monkeypatch
    ):
        monkeypatch.setattr(_catalogue.destination_courses, "home_courses",
                            lambda: [])

        def _must_not_prompt(_p=""):  # pragma: no cover - guard
            raise AssertionError("prompted with nothing to offer")

        monkeypatch.setattr(builtins, "input", _must_not_prompt)
        assert _catalogue._pick_course() is None
