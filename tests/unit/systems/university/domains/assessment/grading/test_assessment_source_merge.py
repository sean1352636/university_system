"""Tests for _merge_assessment_sources (grade tracking Assessments/Exams view).

The view used to have two "Load from …" buttons that *copied* rows between
tables — assignments into assessments, exams into assessments. Copying is what
produced the duplicates: one exam could end up as an exams row, an assessments
row and an assignments row, none of them recording where it came from.

The buttons are gone. The three tables are read live and merged here instead,
so nothing is written and nothing can drift. These tests pin that merge.

Headless on purpose — the function is pure and takes no widgets, so unlike
``test_assessment_manager.py`` (which is ``pytest.mark.gui``) this needs no
display and runs in the default suite.
"""
from __future__ import annotations

from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.assessment_manager import (
    _merge_assessment_sources,
)

# Row shape the view works in:
# (assessment_id, name, type, module_code, max_points, weight, due_date)
EXAM = ("E9", "Financial Accounting Exam", "exam", "ACC-Y1-1", 100, 0, "2026-06-17")
ASSESSMENT = ("6", "Financial Accounting Exam", "exam", "ACC-Y1-1", 100, 25,
              "2026-06-17 09:00")
ASSIGNMENT = ("A6", "Financial Accounting Exam", "assignment", "ACC-Y1-1", 100, 0,
              "2026-06-17 09:00")


class TestCollapsesDuplicates:
    def test_the_same_item_from_three_tables_becomes_one_row(self):
        merged = _merge_assessment_sources([ASSESSMENT], [ASSIGNMENT], [EXAM])

        assert len(merged) == 1

    def test_the_exam_wins(self):
        """Furthest from the copy is most authoritative."""
        merged = _merge_assessment_sources([ASSESSMENT], [ASSIGNMENT], [EXAM])

        assert merged[0] == EXAM

    def test_assessment_wins_over_assignment_when_there_is_no_exam(self):
        merged = _merge_assessment_sources([ASSESSMENT], [ASSIGNMENT], [])

        assert merged[0] == ASSESSMENT

    def test_time_of_day_does_not_prevent_a_match(self):
        """The same item is '2026-06-17' in one table and '... 09:00' in another."""
        merged = _merge_assessment_sources([ASSESSMENT], [], [EXAM])

        assert len(merged) == 1

    def test_matching_ignores_case_and_padding_in_the_title(self):
        untidy = ("7", "  FINANCIAL ACCOUNTING EXAM ", "exam", "ACC-Y1-1",
                  100, 25, "2026-06-17")
        merged = _merge_assessment_sources([untidy], [], [EXAM])

        assert len(merged) == 1


class TestKeepsDistinctWork:
    def test_different_titles_stay_separate(self):
        other = ("2", "Coursework 1", "coursework", "ACC-Y1-1", 100, 25,
                 "2026-06-17")
        merged = _merge_assessment_sources([ASSESSMENT, other], [], [EXAM])

        assert len(merged) == 2

    def test_same_title_in_a_different_module_stays_separate(self):
        other_module = ("8", "Financial Accounting Exam", "exam", "ACC-Y2-1",
                        100, 25, "2026-06-17")
        merged = _merge_assessment_sources([ASSESSMENT, other_module], [], [EXAM])

        assert len(merged) == 2

    def test_same_title_on_a_different_date_stays_separate(self):
        resit = ("9", "Financial Accounting Exam", "exam", "ACC-Y1-1", 100, 25,
                 "2026-08-20")
        merged = _merge_assessment_sources([ASSESSMENT, resit], [], [EXAM])

        assert len(merged) == 2

    def test_unrelated_rows_from_every_source_all_survive(self):
        merged = _merge_assessment_sources(
            [("1", "Essay", "coursework", "CS101", 100, 40, "2026-05-01")],
            [("A2", "Lab report", "assignment", "CS102", 100, 0, "2026-05-02")],
            [("E3", "CS103 exam", "exam", "CS103", 100, 0, "2026-05-03")],
        )

        assert len(merged) == 3


class TestEdges:
    def test_no_sources_gives_no_rows(self):
        assert _merge_assessment_sources([], [], []) == []

    def test_a_missing_due_date_does_not_crash_and_still_matches(self):
        no_date_a = ("1", "Mystery", "exam", "CS101", 100, 0, None)
        no_date_b = ("A1", "Mystery", "assignment", "CS101", 100, 0, "")
        merged = _merge_assessment_sources([no_date_a], [no_date_b], [])

        assert len(merged) == 1

    def test_input_order_is_preserved_within_the_result(self):
        first = ("1", "Alpha", "coursework", "CS101", 100, 10, "2026-01-01")
        second = ("2", "Beta", "coursework", "CS101", 100, 10, "2026-02-01")
        merged = _merge_assessment_sources([first, second], [], [])

        assert [row[1] for row in merged] == ["Alpha", "Beta"]

    def test_exams_are_listed_before_the_other_sources(self):
        """Exams are scanned first, so they lead the merged list."""
        coursework = ("1", "Essay", "coursework", "CS101", 100, 40, "2026-05-01")
        merged = _merge_assessment_sources([coursework], [], [EXAM])

        assert merged[0] == EXAM
