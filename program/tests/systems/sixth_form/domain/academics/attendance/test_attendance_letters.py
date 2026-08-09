"""Tests for attendance letters.

The rule that does the most work: one letter per stage per year, and the
ladder only climbs. Without it, a learner at 87% receives letter 2 every
time anybody runs the report.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_letters as letters,
    attendance_thresholds as thresholds,
)


def mark_at(attdb, student_id: str, *, attended: int, total: int) -> None:
    """Give a learner a known percentage over the recent window.

    ``allow_retro`` because the run reaches back further than the
    retro-marking window: this is a fixture back-filling history, which
    is exactly what that flag is for.
    """
    import datetime as _dt
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    for index in range(total):
        date = (monday - _dt.timedelta(days=index)).isoformat()
        code = "/" if index < attended else "O"
        core.save_register(attdb.slot, date, {student_id: {"code": code}},
                           allow_retro=True)


# ── 1. Templates ───────────────────────────────────────────────────

class TestTemplates:

    def test_the_three_letters_are_seeded(self, attdb):
        assert len(letters.list_templates()) == 3

    def test_templates_are_in_ladder_order(self, attdb):
        assert [t.stage_key for t in letters.list_templates()] == \
            list(letters.STAGE_KEYS)

    def test_a_template_can_be_edited(self, attdb):
        out = letters.set_template(thresholds.LETTER_1,
                                   subject="About {student_name}",
                                   actor="head")
        assert out.subject == "About {student_name}"

    def test_an_unknown_placeholder_is_rejected(self, attdb):
        # Discovered here, not at three hundred letters.
        with pytest.raises(core.ValidationError, match="Unknown placeholder"):
            letters.set_template(thresholds.LETTER_1,
                                 body="Dear {favourite_colour},")

    def test_stage_keys_accept_a_number(self, attdb):
        assert letters.validate_stage("2") == thresholds.LETTER_2

    def test_an_unknown_stage_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Stage must be"):
            letters.validate_stage("letter 9")


# ── 2. Who is due one ──────────────────────────────────────────────

class TestDue:

    def test_a_learner_above_every_threshold_is_not_due(self, attdb):
        mark_at(attdb, attdb.s1, attended=10, total=10)
        assert [c.student_id for c in letters.due()] == []

    def test_a_learner_below_the_first_threshold_is_due_letter_one(self,
                                                                   attdb):
        mark_at(attdb, attdb.s1, attended=9, total=10)      # 90%
        candidates = {c.student_id: c for c in letters.due()}
        assert candidates[attdb.s1].stage_key == thresholds.LETTER_1

    def test_a_worse_figure_earns_the_worse_letter(self, attdb):
        mark_at(attdb, attdb.s1, attended=8, total=10)      # 80%
        candidates = {c.student_id: c for c in letters.due()}
        assert candidates[attdb.s1].stage_key == thresholds.LETTER_3

    def test_a_letter_already_sent_is_not_repeated(self, attdb):
        mark_at(attdb, attdb.s1, attended=9, total=10)
        letter = letters.draft(attdb.s1, thresholds.LETTER_1)
        letters.issue(letter.letter_id, issued_by="head")
        assert [c.student_id for c in letters.due()] == []

    def test_a_worse_figure_still_climbs_the_ladder(self, attdb):
        mark_at(attdb, attdb.s1, attended=9, total=10)
        letter = letters.draft(attdb.s1, thresholds.LETTER_1)
        letters.issue(letter.letter_id, issued_by="head")
        # Now the figure falls further.
        mark_at(attdb, attdb.s1, attended=0, total=6)
        candidates = {c.student_id: c for c in letters.due()}
        assert candidates[attdb.s1].stage_key in (thresholds.LETTER_2,
                                                  thresholds.LETTER_3)

    def test_a_draft_does_not_block_the_next_run(self, attdb):
        # Only an issued letter counts as having been sent.
        mark_at(attdb, attdb.s1, attended=9, total=10)
        letters.draft(attdb.s1, thresholds.LETTER_1)
        assert [c.student_id for c in letters.due()] == [attdb.s1]

    def test_the_highest_sent_is_reported(self, attdb):
        mark_at(attdb, attdb.s1, attended=9, total=10)
        letter = letters.draft(attdb.s1, thresholds.LETTER_1)
        letters.issue(letter.letter_id, issued_by="head")
        assert letters.highest_sent(attdb.s1) == thresholds.LETTER_1

    def test_candidates_are_worst_first(self, attdb):
        mark_at(attdb, attdb.s1, attended=9, total=10)       # 90%
        mark_at(attdb, attdb.s2, attended=7, total=10)       # 70%
        stages = [c.stage_key for c in letters.due()]
        assert stages[0] == thresholds.LETTER_3


# ── 3. Drafting ────────────────────────────────────────────────────

class TestDrafting:

    def test_a_draft_renders_the_figures(self, attdb):
        mark_at(attdb, attdb.s1, attended=8, total=10)
        letter = letters.draft(attdb.s1, thresholds.LETTER_1)
        assert "Ada Test" in letter.body
        assert "80.0%" in letter.body
        assert letter.state == letters.DRAFT

    def test_the_subject_is_rendered_too(self, attdb):
        mark_at(attdb, attdb.s1, attended=8, total=10)
        letter = letters.draft(attdb.s1, thresholds.LETTER_1)
        assert "Ada Test" in letter.subject

    def test_the_sender_details_land_in_the_body(self, attdb):
        mark_at(attdb, attdb.s1, attended=8, total=10)
        letter = letters.draft(attdb.s1, thresholds.LETTER_1,
                               sender_name="J Smith",
                               sender_role="Head of Year 12",
                               sender_contact="jsmith@example.test")
        assert "J Smith" in letter.body
        assert "jsmith@example.test" in letter.body

    def test_a_run_drafts_everybody_due(self, attdb):
        mark_at(attdb, attdb.s1, attended=8, total=10)
        mark_at(attdb, attdb.s2, attended=9, total=10)
        result = letters.run()
        assert result.drafted == 2

    def test_a_run_reports_who_has_no_address(self, attdb):
        mark_at(attdb, attdb.s1, attended=8, total=10)
        result = letters.run()
        assert attdb.s1 in result.no_recipient

    def test_preview_renders_without_storing(self, attdb):
        mark_at(attdb, attdb.s1, attended=8, total=10)
        body = letters.preview(thresholds.LETTER_1, attdb.s1)
        assert "Ada" in body
        assert letters.list_letters() == []


# ── 4. Issuing ─────────────────────────────────────────────────────

class TestIssuing:

    @pytest.fixture
    def drafted(self, attdb):
        mark_at(attdb, attdb.s1, attended=8, total=10)
        return letters.draft(attdb.s1, thresholds.LETTER_1)

    def test_issuing_records_it(self, attdb, drafted):
        out = letters.issue(drafted.letter_id, issued_by="head")
        assert out.state == letters.ISSUED
        assert out.issued_by == "head"

    def test_issuing_twice_is_refused(self, attdb, drafted):
        letters.issue(drafted.letter_id, issued_by="head")
        with pytest.raises(core.ValidationError, match="already been issued"):
            letters.issue(drafted.letter_id, issued_by="head")

    def test_emailing_without_an_address_is_refused(self, attdb, drafted):
        with pytest.raises(core.ValidationError, match="no email address"):
            letters.issue(drafted.letter_id, send=True)

    def test_a_sender_can_be_supplied(self, attdb, drafted):
        sent: list[int] = []
        # Give it an address so the send path is reachable.
        import sqlite3
        conn = sqlite3.connect(attdb.db)
        conn.execute("UPDATE attendance_letters SET recipient = ? "
                     "WHERE letter_id = ?",
                     ("parent@example.test", drafted.letter_id))
        conn.commit()
        conn.close()
        letters.issue(drafted.letter_id, issued_by="head", send=True,
                      sender=lambda letter: sent.append(letter.letter_id))
        assert sent == [drafted.letter_id]

    def test_a_draft_can_be_cancelled(self, attdb, drafted):
        out = letters.cancel(drafted.letter_id, reason="Figure was wrong")
        assert out.state == letters.CANCELLED

    def test_cancelling_needs_a_reason(self, attdb, drafted):
        with pytest.raises(core.ValidationError, match="reason is required"):
            letters.cancel(drafted.letter_id, reason="  ")

    def test_an_issued_letter_cannot_be_cancelled(self, attdb, drafted):
        letters.issue(drafted.letter_id, issued_by="head")
        with pytest.raises(core.ValidationError, match="already gone"):
            letters.cancel(drafted.letter_id, reason="Oops")

    def test_a_batch_can_be_issued_at_once(self, attdb):
        mark_at(attdb, attdb.s1, attended=8, total=10)
        mark_at(attdb, attdb.s2, attended=8, total=10)
        letters.run()
        assert letters.issue_all(issued_by="head") == 2

    def test_stage_counts_report_the_year(self, attdb, drafted):
        letters.issue(drafted.letter_id, issued_by="head")
        assert letters.stage_counts()[thresholds.LETTER_1] == 1

    def test_a_familys_history_is_readable(self, attdb, drafted):
        assert len(letters.history_for(attdb.s1)) == 1
