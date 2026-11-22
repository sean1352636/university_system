"""Onboarding (domain.learners.pupils.onboarding.onboarding): the new-pupil checklist."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.learners.pupils.onboarding import onboarding as OB

ALL_STEPS = ("parent_contacts_done", "photo_on_file", "safeguarding_consent",
             "medical_info", "home_visit_done", "induction_done")


def _pupil(first="Ada", year="R"):
    return P.create_pupil({"first_name": first, "last_name": "Test", "year_group": year})


# ── steps ────────────────────────────────────────────────────────────

def test_six_steps_with_labels():
    assert OB.STEP_KEYS == ALL_STEPS
    assert OB.STEP_LABELS["home_visit_done"] == "Home visit completed"
    assert len(OB.STEP_LABELS) == 6


def test_new_pupil_has_a_blank_record_without_a_row():
    p = _pupil()
    rec = OB.get_record(p.pupil_id)
    assert rec.pupil_id == p.pupil_id
    assert rec.steps == {k: False for k in ALL_STEPS}
    assert rec.updated_at is None
    assert (rec.done_count, rec.total, rec.complete) == (0, 6, False)


def test_set_step_ticks_one_step_and_stamps_the_time():
    p = _pupil()
    rec = OB.set_step(p.pupil_id, "photo_on_file", True)
    assert rec.steps["photo_on_file"] is True
    assert [k for k, v in rec.steps.items() if v] == ["photo_on_file"]
    assert rec.done_count == 1 and not rec.complete
    assert rec.updated_at


def test_set_step_can_untick():
    p = _pupil()
    OB.set_step(p.pupil_id, "medical_info", True)
    rec = OB.set_step(p.pupil_id, "medical_info", False)
    assert rec.steps["medical_info"] is False and rec.done_count == 0


def test_every_step_ticked_is_complete():
    p = _pupil()
    for k in ALL_STEPS:
        rec = OB.set_step(p.pupil_id, k, True)
    assert rec.complete and rec.done_count == 6


def test_unknown_step_is_refused():
    p = _pupil()
    with pytest.raises(P.ValidationError, match="Unknown onboarding step"):
        OB.set_step(p.pupil_id, "pupil_id", True)


def test_unknown_pupil_is_refused_everywhere():
    for call in (lambda: OB.get_record("P0000000"),
                 lambda: OB.set_step("P0000000", "photo_on_file", True),
                 lambda: OB.mark_all("P0000000", True)):
        with pytest.raises(P.ValidationError, match="No pupil with id P0000000"):
            call()


def test_mark_all_done_then_reset():
    p = _pupil()
    assert OB.mark_all(p.pupil_id, True).complete
    rec = OB.mark_all(p.pupil_id, False)
    assert rec.done_count == 0 and rec.updated_at


def test_record_goes_when_the_pupil_is_deleted():
    p = _pupil()
    OB.mark_all(p.pupil_id, True)
    P.delete_pupil(p.pupil_id)
    with P._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM pupil_onboarding").fetchone()[0] == 0


# ── listing and summary ──────────────────────────────────────────────

def test_empty_school_lists_nothing_and_zero_summary():
    assert OB.list_records() == []
    assert OB.progress_summary() == {"total": 0, "complete": 0, "started": 0, "pending": 0}


def test_list_records_covers_every_pupil_on_roll_with_blank_records():
    a, b = _pupil("Al"), _pupil("Bo", "1")
    gone = _pupil("Gus")
    OB.mark_all(gone.pupil_id, True)
    P.set_roll_status(gone.pupil_id, "left")
    OB.set_step(b.pupil_id, "photo_on_file", True)
    rows = {p.pupil_id: rec for p, rec in OB.list_records()}
    assert set(rows) == {a.pupil_id, b.pupil_id}
    assert rows[a.pupil_id].done_count == 0 and rows[b.pupil_id].done_count == 1


def test_list_records_filters_pending_and_year():
    done, part, none = _pupil("Done"), _pupil("Part"), _pupil("None", "2")
    OB.mark_all(done.pupil_id, True)
    OB.set_step(part.pupil_id, "induction_done", True)
    assert {p.pupil_id for p, _ in OB.list_records(pending_only=True)} == {
        part.pupil_id, none.pupil_id}
    assert {p.pupil_id for p, _ in OB.list_records(year_group="R")} == {
        done.pupil_id, part.pupil_id}
    assert [p.pupil_id for p, _ in OB.list_records(pending_only=True, year_group="2")] == [
        none.pupil_id]


def test_progress_summary_counts_complete_started_and_pending():
    pupils = [_pupil(f"P{i}") for i in range(5)]
    OB.mark_all(pupils[0].pupil_id, True)
    OB.mark_all(pupils[1].pupil_id, True)
    OB.set_step(pupils[2].pupil_id, "photo_on_file", True)
    OB.mark_all(pupils[3].pupil_id, False)       # row exists, nothing done
    assert OB.progress_summary() == {"total": 5, "complete": 2, "started": 1, "pending": 2}
