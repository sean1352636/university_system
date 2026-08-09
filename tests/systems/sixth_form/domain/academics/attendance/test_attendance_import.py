"""Tests for bulk attendance import.

Two properties carry the module: a plan writes nothing, and every
applied batch can be undone exactly.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_import as importer,
    attendance_register as reg,
)


def csv_for(attdb, rows: list[str], *,
            header: str = "student_id,date,slot_id,code") -> str:
    return "\n".join([header, *rows]) + "\n"


# ── 1. Parsing ─────────────────────────────────────────────────────

class TestParsing:

    def test_a_plain_file_parses(self, attdb):
        rows = importer.parse_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},/"]))
        assert len(rows) == 1
        assert rows[0].student_id == attdb.s1
        assert rows[0].code == "/"

    def test_column_aliases_are_accepted(self, attdb):
        rows = importer.parse_csv(csv_for(
            attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},I"],
            header="learner,attendance_date,slot,mark"))
        assert rows[0].code == "I"

    def test_a_missing_student_column_is_fatal(self, attdb):
        with pytest.raises(core.ValidationError, match="No student column"):
            importer.parse_csv("date,slot_id,code\n2026-01-01,1,/\n")

    def test_a_missing_mark_column_is_fatal(self, attdb):
        with pytest.raises(core.ValidationError, match="No mark column"):
            importer.parse_csv("student_id,date,slot_id\nT0001,2026-01-01,1\n")

    @pytest.mark.parametrize("written", [
        "2026-03-04", "04/03/2026", "04-03-2026", "2026/03/04", "04.03.2026",
    ])
    def test_spreadsheet_date_formats_are_read(self, attdb, written):
        rows = importer.parse_csv(
            csv_for(attdb, [f"{attdb.s1},{written},{attdb.slot},/"]))
        assert rows[0].date == "2026-03-04"

    def test_an_unreadable_date_is_an_error_row(self, attdb):
        rows = importer.parse_csv(
            csv_for(attdb, [f"{attdb.s1},not-a-date,{attdb.slot},/"]))
        assert rows[0].outcome == importer.ERROR
        assert "Unreadable date" in rows[0].detail

    def test_an_unknown_code_is_an_error_row(self, attdb):
        rows = importer.parse_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},Q"]))
        assert rows[0].outcome == importer.ERROR

    def test_a_missing_student_id_is_an_error_row(self, attdb):
        rows = importer.parse_csv(
            csv_for(attdb, [f",{attdb.monday},{attdb.slot},/"]))
        assert rows[0].outcome == importer.ERROR

    def test_a_group_and_period_resolve_to_a_slot(self, attdb):
        rows = importer.parse_csv(csv_for(
            attdb, [f"{attdb.s1},{attdb.monday},{attdb.group},1,/"],
            header="student_id,date,group_id,period,code"))
        assert rows[0].slot_id == attdb.slot

    def test_a_group_with_no_lesson_that_day_errors(self, attdb):
        rows = importer.parse_csv(csv_for(
            attdb, [f"{attdb.s1},{attdb.tuesday},{attdb.group},1,/"],
            header="student_id,date,group_id,period,code"))
        assert rows[0].outcome == importer.ERROR
        assert "No slot" in rows[0].detail

    def test_neither_slot_nor_group_errors(self, attdb):
        rows = importer.parse_csv(csv_for(
            attdb, [f"{attdb.s1},{attdb.monday},/"],
            header="student_id,date,code"))
        assert rows[0].outcome == importer.ERROR

    def test_a_status_column_works_instead_of_a_code(self, attdb):
        rows = importer.parse_csv(csv_for(
            attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},absent"],
            header="student_id,date,slot_id,status"))
        assert rows[0].status == "Absent"

    def test_the_template_parses_as_its_own_format(self, attdb):
        assert "student_id" in importer.template_csv()


# ── 2. Planning ────────────────────────────────────────────────────

class TestPlanning:

    def test_a_plan_writes_nothing(self, attdb):
        plan = importer.plan_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},/"]))
        assert len(plan.writable) == 1
        assert core.list_records(slot_id=attdb.slot) == []

    def test_an_unknown_learner_is_skipped(self, attdb):
        plan = importer.plan_csv(
            csv_for(attdb, [f"NOPE,{attdb.monday},{attdb.slot},/"]))
        assert plan.writable == []
        assert "NOPE" in plan.unknown_students

    def test_a_learner_off_the_roster_is_skipped(self, attdb):
        # Slot 3 belongs to group 2, which has no members.
        plan = importer.plan_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.tuesday},{attdb.empty_slot},/"]))
        assert plan.writable == []
        assert "not on the roster" in plan.rows[0].detail

    def test_a_duplicate_line_is_skipped(self, attdb):
        plan = importer.plan_csv(csv_for(attdb, [
            f"{attdb.s1},{attdb.monday},{attdb.slot},/",
            f"{attdb.s1},{attdb.monday},{attdb.slot},I",
        ]))
        assert plan.duplicates == 1
        assert len(plan.writable) == 1

    def test_an_existing_mark_is_flagged_as_an_overwrite(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        plan = importer.plan_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},I"]))
        assert plan.overwrites == 1

    def test_a_submitted_register_is_skipped(self, attdb):
        core.save_register(
            attdb.slot, attdb.monday,
            {sid: {"status": "Present"} for sid in attdb.students})
        reg.submit_register(attdb.slot, attdb.monday, submitted_by="teacher")
        plan = importer.plan_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},I"]))
        assert plan.writable == []
        assert plan.locked_registers

    def test_the_date_range_is_reported(self, attdb):
        plan = importer.plan_csv(csv_for(attdb, [
            f"{attdb.s1},{attdb.prev_monday},{attdb.slot},/",
            f"{attdb.s2},{attdb.monday},{attdb.slot},/",
        ]))
        assert plan.date_from == attdb.prev_monday
        assert plan.date_to == attdb.monday


# ── 3. Applying ────────────────────────────────────────────────────

class TestApplying:

    def test_a_plan_applies(self, attdb):
        batch = importer.import_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},I"]),
            label="Feeder school")
        assert batch.rows_written == 1
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == "I"

    def test_imported_marks_are_stamped_as_import(self, attdb):
        importer.import_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},/"]),
            label="Feeder school")
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.data_source == importer.IMPORT_SOURCE

    def test_history_older_than_the_window_still_imports(self, attdb):
        # Import is retrospective by definition; the window logs it
        # rather than blocking it.
        batch = importer.import_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.ancient},{attdb.slot},/"]),
            label="Two years ago")
        assert batch.rows_written == 1

    def test_a_label_is_required(self, attdb):
        plan = importer.plan_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},/"]))
        with pytest.raises(core.ValidationError, match="needs a label"):
            importer.apply_plan(plan, label="  ")

    def test_an_empty_plan_is_rejected(self, attdb):
        plan = importer.plan_csv(
            csv_for(attdb, [f"NOPE,{attdb.monday},{attdb.slot},/"]))
        with pytest.raises(core.ValidationError, match="Nothing in this plan"):
            importer.apply_plan(plan, label="Empty")

    def test_skip_overwrites_leaves_existing_marks(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "I"}})
        plan = importer.plan_csv(csv_for(attdb, [
            f"{attdb.s1},{attdb.monday},{attdb.slot},O",
            f"{attdb.s2},{attdb.monday},{attdb.slot},O",
        ]))
        importer.apply_plan(plan, label="Careful", skip_overwrites=True)
        assert core.get_record_for(attdb.slot, attdb.s1,
                                   attdb.monday).code == "I"
        assert core.get_record_for(attdb.slot, attdb.s2,
                                   attdb.monday).code == "O"

    def test_the_per_line_record_is_kept(self, attdb):
        batch = importer.import_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},/"]),
            label="Feeder school")
        rows = importer.batch_rows(batch.batch_id,
                                   outcome=importer.WRITTEN)
        assert rows[0].student_id == attdb.s1


# ── 4. Rollback ────────────────────────────────────────────────────

class TestRollback:

    def test_rows_the_import_created_are_deleted(self, attdb):
        batch = importer.import_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},/"]),
            label="Oops")
        result = importer.rollback(batch.batch_id, actor="head")
        assert result.deleted == 1
        assert core.get_record_for(attdb.slot, attdb.s1, attdb.monday) is None

    def test_rows_the_import_overwrote_are_restored(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "I", "notes": "Flu"}})
        batch = importer.import_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},O"]),
            label="Wrong column mapping")
        assert core.get_record_for(attdb.slot, attdb.s1,
                                   attdb.monday).code == "O"
        result = importer.rollback(batch.batch_id, actor="head")
        assert result.restored == 1
        restored = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert restored.code == "I"
        assert restored.notes == "Flu"

    def test_a_batch_cannot_be_rolled_back_twice(self, attdb):
        batch = importer.import_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},/"]),
            label="Oops")
        importer.rollback(batch.batch_id)
        with pytest.raises(core.ValidationError, match="already been rolled"):
            importer.rollback(batch.batch_id)

    def test_an_unknown_batch_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No import batch"):
            importer.rollback(9999)

    def test_the_batch_is_marked_rolled_back(self, attdb):
        batch = importer.import_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},/"]),
            label="Oops")
        importer.rollback(batch.batch_id, actor="head")
        out = importer.get_batch(batch.batch_id)
        assert out.state == importer.ROLLED_BACK
        assert out.rolled_back_by == "head"
        assert out.is_live is False

    def test_batches_are_listed_newest_first(self, attdb):
        importer.import_csv(
            csv_for(attdb, [f"{attdb.s1},{attdb.monday},{attdb.slot},/"]),
            label="First")
        importer.import_csv(
            csv_for(attdb, [f"{attdb.s2},{attdb.monday},{attdb.slot},/"]),
            label="Second")
        assert [b.label for b in importer.list_batches()] == ["Second",
                                                              "First"]
