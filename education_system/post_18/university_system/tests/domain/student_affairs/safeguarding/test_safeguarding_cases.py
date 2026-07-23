"""Tests for the safeguarding case-management service (lifecycle, notes,
action items, referrals, support plans, closure, export, merge, split)."""

import csv

import pytest

from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.analysis import (
    RiskCategory,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.cases import (
    OUTCOME_CODE_SET,
    add_action_item,
    add_case_note,
    add_referral,
    apply_support_plan_template,
    assign_case,
    close_case,
    complete_action_item,
    due_reviews,
    export_cases_csv,
    list_action_items,
    list_assignments,
    list_case_notes,
    list_referrals,
    merge_cases,
    schedule_review,
    set_lifecycle_state,
    split_case,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.submissions import (
    get_submission,
)


class TestLifecycle:
    def test_valid_transition_updates_and_logs_note(self, make_case):
        cid = make_case()
        set_lifecycle_state(cid, "Action", actor="dsl.jones")
        assert get_submission(cid)["lifecycle_state"] == "Action"
        notes = list_case_notes(cid)
        assert any("state changed to Action" in n[1] for n in notes)

    def test_invalid_state_rejected(self, make_case):
        cid = make_case()
        with pytest.raises(ValueError):
            set_lifecycle_state(cid, "Nonsense")


class TestAssignment:
    def test_assign_updates_row_and_audit_trail(self, make_case):
        cid = make_case()
        assign_case(cid, "dsl.smith", "admin", note="on-call handoff")
        assert get_submission(cid)["assigned_to"] == "dsl.smith"
        trail = list_assignments(cid)
        assert trail[-1][0] == "dsl.smith"
        assert trail[-1][1] == "admin"


class TestNotes:
    def test_notes_are_append_only_and_ordered(self, make_case):
        cid = make_case()
        add_case_note(cid, "a", "first")
        add_case_note(cid, "b", "second")
        notes = list_case_notes(cid)
        texts = [n[1] for n in notes]
        assert texts == ["first", "second"]


class TestActionItems:
    def test_add_list_and_complete(self, make_case):
        cid = make_case()
        add_action_item(cid, "Contact student", "dsl.jones", "2026-08-01")
        items = list_action_items(cid)
        assert len(items) == 1
        item_id, title, owner, due, status, completed = items[0]
        assert title == "Contact student"
        assert status == "Open"
        complete_action_item(item_id)
        done = list_action_items(cid)[0]
        assert done[4] == "Done"
        assert done[5] is not None


class TestReferrals:
    def test_add_and_list(self, make_case):
        cid = make_case()
        add_referral(cid, "Local Authority", "0123", "REF-9", note="urgent")
        refs = list_referrals(cid)
        assert len(refs) == 1
        assert refs[0][1] == "Local Authority"
        assert refs[0][5] == "Sent"  # default status


class TestSupportPlanTemplate:
    def test_known_category_creates_action_items(self, make_case):
        cid = make_case()
        count = apply_support_plan_template(cid, RiskCategory.SELF_HARM, owner="dsl.jones")
        assert count > 0
        assert len(list_action_items(cid)) == count

    def test_unknown_category_creates_nothing(self, make_case):
        cid = make_case()
        assert apply_support_plan_template(cid, "not-a-category") == 0
        assert list_action_items(cid) == []


class TestReviews:
    def test_scheduled_review_shows_up_as_due(self, make_case):
        cid = make_case()
        schedule_review(cid, days=-1)  # already overdue
        due_ids = {r[0] for r in due_reviews()}
        assert cid in due_ids

    def test_future_review_not_yet_due(self, make_case):
        cid = make_case()
        schedule_review(cid, days=30)
        assert cid not in {r[0] for r in due_reviews()}

    def test_closed_cases_are_never_due(self, make_case):
        cid = make_case()
        schedule_review(cid, days=-1)
        close_case(cid, "NFA", "resolved", actor="dsl.jones")
        assert cid not in {r[0] for r in due_reviews()}


class TestClosure:
    def test_close_sets_outcome_and_state(self, make_case):
        cid = make_case()
        close_case(cid, "SUPPORT", "internal support arranged", actor="dsl.jones")
        row = get_submission(cid)
        assert row["status"] == "Closed"
        assert row["lifecycle_state"] == "Closed"
        assert row["outcome_code"] == "SUPPORT"
        assert "SUPPORT" in OUTCOME_CODE_SET

    def test_invalid_outcome_code_rejected(self, make_case):
        cid = make_case()
        with pytest.raises(ValueError):
            close_case(cid, "BOGUS", "reason", actor="x")


class TestExportCsv:
    def test_writes_header_and_rows(self, make_case, tmp_path):
        make_case(severity="HIGH")
        make_case(severity="LOW")
        out = tmp_path / "export.csv"
        path, n = export_cases_csv(str(out))
        assert n == 2
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[0][0] == "id"  # header present
        assert len(rows) == 3  # header + 2 data rows

    def test_exclude_anonymous(self, make_case, tmp_path):
        make_case(severity="LOW")
        make_case(severity="LOW", anonymous=True)
        out = tmp_path / "export2.csv"
        _, n = export_cases_csv(str(out), include_anonymous=False)
        assert n == 1


class TestMerge:
    def test_merges_notes_and_closes_others(self, make_case):
        primary = make_case()
        other = make_case()
        add_case_note(other, "witness", "saw the incident")
        add_action_item(other, "follow up", "dsl", None)
        merged = merge_cases(primary, [other], actor="dsl.jones")
        assert merged == 1
        # The secondary case is closed as MERGED and points at the primary.
        other_row = get_submission(other)
        assert other_row["lifecycle_state"] == "Closed"
        assert other_row["outcome_code"] == "MERGED"
        # Its notes and action items now live on the primary.
        assert any("saw the incident" in n[1] for n in list_case_notes(primary))
        assert len(list_action_items(primary)) == 1

    def test_empty_other_ids_is_noop(self, make_case):
        primary = make_case()
        assert merge_cases(primary, [], actor="x") == 0

    def test_primary_id_skipped_if_in_others(self, make_case):
        primary = make_case()
        assert merge_cases(primary, [primary], actor="x") == 0


class TestSplit:
    def test_split_creates_derivative_case(self, make_case):
        cid = make_case(content="original combined report about two issues")
        new_id = split_case(cid, "I am also being harassed by a classmate", actor="dsl.jones")
        assert new_id is not None and new_id != cid
        new_row = get_submission(new_id)
        assert new_row is not None
        # Origin case records the split in its notes timeline.
        assert any("split" in n[1].lower() for n in list_case_notes(cid))

    def test_split_missing_case_returns_none(self):
        assert split_case(999999, "text", actor="x") is None
