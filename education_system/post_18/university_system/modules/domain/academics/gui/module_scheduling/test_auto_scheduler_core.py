"""Unit tests for the pure scheduling solver core."""
import pytest

from education_system.post_18.university_system.modules.domain.academics.gui.module_scheduling.auto_scheduler_core import (
    Assignment, Instructor, ModuleReq, Options, Room, Weights,
    evaluate, find_back_to_back, find_travel_violations, generate_start_times,
    overlaps, solve, to_hhmm, to_minutes, weights_for_goal,
)


# --------------------------------------------------------------------------- #
# Time helpers
# --------------------------------------------------------------------------- #
def test_time_roundtrip():
    assert to_minutes("09:30") == 570
    assert to_hhmm(570) == "09:30"
    assert to_hhmm(to_minutes("13:45")) == "13:45"


def test_overlaps_half_open():
    assert overlaps(540, 600, 570, 630)      # 9-10 vs 9:30-10:30
    assert not overlaps(540, 600, 600, 660)  # 9-10 vs 10-11 (touching, no overlap)
    assert not overlaps(600, 660, 540, 600)


def test_generate_start_times_fits_day():
    starts = generate_start_times("09:00", "12:00", 60, 60)
    assert starts == ["09:00", "10:00", "11:00"]  # 12:00 end excluded (would end 13:00)
    assert generate_start_times("09:00", "10:00", 90, 30) == []  # nothing fits


# --------------------------------------------------------------------------- #
# Solver basics
# --------------------------------------------------------------------------- #
def _basic_setup(n_modules=3, capacity=50):
    rooms = [Room(id=1, building="A", capacity=capacity, room_type="")]
    instructors = [Instructor(id=1, name="Dr X")]
    reqs = [
        ModuleReq(f"M{i}", "Lecture", 60, current_enrollment=10,
                  forecast_enrollment=10)
        for i in range(n_modules)
    ]
    return reqs, rooms, instructors


def test_places_all_when_capacity_allows():
    reqs, rooms, instructors = _basic_setup(n_modules=3)
    result = solve(reqs, rooms, instructors, options=Options())
    assert result.placed_count == 3
    assert result.unplaced == []
    assert result.hard_violations == 0
    # No two placements collide on the same room+time.
    seen = set()
    for a in result.assignments:
        key = (a.room_id, a.day, a.start)
        assert key not in seen
        seen.add(key)


def test_reports_unplaceable_when_capacity_too_small():
    # Room seats 5 but every module forecasts 40 -> nothing can be placed.
    rooms = [Room(id=1, building="A", capacity=5)]
    instructors = [Instructor(id=1, name="Dr X")]
    reqs = [ModuleReq("BIG", "Lecture", 60, 40, 40)]
    result = solve(reqs, rooms, instructors)
    assert result.placed_count == 0
    assert len(result.unplaced) == 1


def test_forecast_capacity_drives_placement():
    # Current enrollment 10 fits a 20-seat room, but forecast 30 does not.
    rooms = [Room(id=1, building="A", capacity=20)]
    instructors = [Instructor(id=1, name="Dr X")]
    reqs = [ModuleReq("GROW", "Lecture", 60, current_enrollment=10,
                      forecast_enrollment=30)]
    result = solve(reqs, rooms, instructors)
    assert result.placed_count == 0        # forecast blocks it
    assert reqs[0].required_capacity == 30


def test_no_double_booking_single_room_single_instructor():
    # 4 modules, one room, one instructor: all get distinct time slots.
    reqs, rooms, instructors = _basic_setup(n_modules=4)
    result = solve(reqs, rooms, instructors)
    assert result.placed_count == 4
    # Every (day,start) pair distinct because one room + one instructor.
    slots = {(a.day, a.start) for a in result.assignments}
    assert len(slots) == 4


def test_existing_schedule_is_fixed_occupancy():
    rooms = [Room(id=1, building="A", capacity=50)]
    instructors = [Instructor(id=1, name="Dr X")]
    existing = [Assignment("OLD", "Lecture", "Monday", "09:00", "10:00", 1, 1)]
    reqs = [ModuleReq("NEW", "Lecture", 60, 10, 10)]
    result = solve(reqs, rooms, instructors, existing=existing)
    assert result.placed_count == 1
    new = result.assignments[0]
    # New session must not collide with the existing Monday 09:00 booking.
    assert not (new.day == "Monday" and new.start == "09:00")


# --------------------------------------------------------------------------- #
# Travel-time (feature 7)
# --------------------------------------------------------------------------- #
def test_travel_time_blocks_tight_cross_building():
    # Two buildings far apart; instructor cannot teach back-to-back across them.
    rooms = [Room(id=1, building="A", capacity=50),
             Room(id=2, building="B", capacity=50)]
    instructors = [Instructor(id=1, name="Dr X")]
    existing = [Assignment("A1", "Lecture", "Monday", "09:00", "10:00", 1, 1)]
    # A 60-min module that could go Monday 10:00 in building B would violate a
    # 15-min travel requirement (0-min gap). Force day to Monday only + one slot.
    opts = Options(day_start="10:00", day_end="11:00", step_minutes=60,
                   cross_building_travel=15, days=("Monday",))
    reqs = [ModuleReq("B1", "Lecture", 60, 10, 10, required_room_type="")]
    result = solve(reqs, rooms, instructors, existing=existing, options=opts)
    # Only Monday 10:00 exists; room 1 (building A) is free then and legal,
    # room 2 (building B) is illegal (0-min cross-building gap). Solver must
    # pick room 1, never room 2.
    assert result.placed_count == 1
    assert result.assignments[0].room_id == 1
    assert result.travel_violations == []


def test_travel_violation_detected_in_existing_data():
    rooms_by_id = {1: Room(1, "A", 50), 2: Room(2, "B", 50)}
    opts = Options(cross_building_travel=15)
    assigns = [
        Assignment("A1", "Lecture", "Monday", "09:00", "10:00", 1, 1),
        Assignment("B1", "Lecture", "Monday", "10:00", "11:00", 2, 1),  # 0-min gap, diff building
    ]
    viols = find_travel_violations(assigns, rooms_by_id, opts)
    assert len(viols) == 1
    assert viols[0]["from_building"] == "A"
    assert viols[0]["to_building"] == "B"


# --------------------------------------------------------------------------- #
# Back-to-back detector (feature 6)
# --------------------------------------------------------------------------- #
def test_back_to_back_flagged_same_building_zero_gap():
    rooms_by_id = {1: Room(1, "A", 50)}
    opts = Options(same_building_transition=10)
    assigns = [
        Assignment("A1", "Lecture", "Tuesday", "09:00", "10:00", 1, 1),
        Assignment("A2", "Lecture", "Tuesday", "10:00", "11:00", 1, 1),  # 0-min gap
    ]
    flags = find_back_to_back(assigns, rooms_by_id, opts)
    assert len(flags) == 1
    assert flags[0]["gap_minutes"] == 0
    assert flags[0]["same_building"] is True


# --------------------------------------------------------------------------- #
# Goal profiles (feature 4) + weights (feature 2)
# --------------------------------------------------------------------------- #
def test_goal_profiles_differ():
    util = weights_for_goal("room_utilization")
    compact = weights_for_goal("student_compactness")
    assert util.room_underfill > compact.room_underfill
    assert compact.gap_per_hour > util.gap_per_hour
    # Unknown goal falls back to balanced.
    assert weights_for_goal("nonsense").as_dict() == weights_for_goal("balanced").as_dict()


def test_room_utilization_goal_prefers_tighter_room():
    # Two rooms, same building; a 20-student class should prefer the 25-seat
    # room over the 100-seat room when optimizing utilization.
    rooms = [Room(id=1, building="A", capacity=100),
             Room(id=2, building="A", capacity=25)]
    instructors = [Instructor(id=1, name="Dr X")]
    reqs = [ModuleReq("M", "Lecture", 60, 20, 20)]
    result = solve(reqs, rooms, instructors,
                   weights=weights_for_goal("room_utilization"))
    assert result.assignments[0].room_id == 2  # the snug room


# --------------------------------------------------------------------------- #
# Re-balancer (feature 5)
# --------------------------------------------------------------------------- #
def test_rebalancer_spreads_load_across_days():
    # Enough rooms that all 5 modules *could* pile onto one day; the day-balance
    # weight + local search should spread them out instead.
    rooms = [Room(id=r, building="A", capacity=50) for r in range(1, 6)]
    instructors = [Instructor(id=i, name=f"I{i}") for i in range(1, 6)]
    reqs = [ModuleReq(f"M{i}", "Lecture", 60, 10, 10) for i in range(5)]
    w = Weights(day_balance=50.0, gap_per_hour=0.0, room_underfill=0.0,
                instructor_pref_bonus=0.0, back_to_back=0.0)
    result = solve(reqs, rooms, instructors, weights=w)
    assert result.placed_count == 5
    days_used = {a.day for a in result.assignments}
    # With a strong balance weight, the 5 sessions should not all land on 1 day.
    assert len(days_used) >= 4


# --------------------------------------------------------------------------- #
# Evaluate breakdown
# --------------------------------------------------------------------------- #
def test_evaluate_counts_hard_capacity_violation():
    rooms_by_id = {1: Room(1, "A", 5)}
    instr_by_id = {1: Instructor(1, "X")}
    reqs_by_key = {("M", "Lecture"): ModuleReq("M", "Lecture", 60, 40, 40)}
    assigns = [Assignment("M", "Lecture", "Monday", "09:00", "10:00", 1, 1)]
    total, breakdown, hard = evaluate(assigns, rooms_by_id, instr_by_id,
                                      reqs_by_key, Weights(), Options())
    assert hard >= 1
    # Hard penalty dominates (soft bonuses/penalties only nudge it by tens).
    assert total >= 999_000
