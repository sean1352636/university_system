"""Pure, dependency-free scheduling solver core.

This module contains **no** tkinter and **no** database access so it can be
unit-tested in isolation and reused from CLI, API, or GUI. The GUI adapter
(``auto_scheduler.py``) loads data from the database into these dataclasses,
runs the solver, and writes the chosen proposals back.

Implements the "Automated scheduling & optimization" feature set:

1. Auto-timetable generator  -> ``solve()`` places every unscheduled module.
2. Constraint solver (hard/soft, weighted, tunable) -> ``Weights`` + ``evaluate()``.
3. What-if simulation         -> ``solve()`` returns an in-memory ``SolveResult``;
                                 nothing is committed until the caller decides.
4. Optimization-goals selector-> ``weights_for_goal()`` maps a goal to a weight profile.
5. Heuristic re-balancer      -> ``_local_search()`` hill-climbs, spreading load off
                                 overloaded days.
6. Back-to-back detector      -> ``find_back_to_back()``.
7. Travel-time constraints    -> hard-blocked in feasibility + reported by
                                 ``find_travel_violations()``.
8. Forecast-aware capacity    -> ``ModuleReq.required_capacity`` uses the forecast
                                 headcount, not just current enrollment.

Times are handled as "HH:MM" 24-hour strings on the boundary and as integer
minutes-from-midnight internally.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# A very large penalty so any solution with a hard violation always sorts worse
# than any solution without one.
HARD_VIOLATION_PENALTY = 1_000_000.0


# --------------------------------------------------------------------------- #
# Time helpers
# --------------------------------------------------------------------------- #
def to_minutes(hhmm: str) -> int:
    """'09:30' -> 570. Raises ValueError on malformed input."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    """570 -> '09:30'."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def overlaps(s1: int, e1: int, s2: int, e2: int) -> bool:
    """Half-open interval overlap: [s1,e1) intersects [s2,e2)."""
    return s1 < e2 and s2 < e1


def generate_start_times(day_start: str, day_end: str, duration: int, step: int) -> list[str]:
    """Candidate start times such that start+duration fits within the working day."""
    start = to_minutes(day_start)
    end = to_minutes(day_end)
    out = []
    t = start
    while t + duration <= end:
        out.append(to_hhmm(t))
        t += step
    return out


# --------------------------------------------------------------------------- #
# Domain dataclasses
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Room:
    id: int
    building: str
    capacity: int
    room_type: str = ""


@dataclass(frozen=True)
class Instructor:
    id: int
    name: str
    preferred_days: frozenset[str] = frozenset()
    # preferred time windows as ("HH:MM", "HH:MM") pairs
    preferred_windows: tuple[tuple[str, str], ...] = ()
    max_minutes_per_week: int | None = None

    def prefers_day(self, day: str) -> bool:
        return not self.preferred_days or day in self.preferred_days

    def prefers_time(self, start: str) -> bool:
        if not self.preferred_windows:
            return True
        s = to_minutes(start)
        return any(to_minutes(a) <= s < to_minutes(b) for a, b in self.preferred_windows)


@dataclass(frozen=True)
class ModuleReq:
    """One session that needs a slot, room and instructor."""
    module_code: str
    session_type: str
    duration: int                 # minutes
    current_enrollment: int
    forecast_enrollment: int      # feature 8: forecast, not just current
    # Candidate instructor ids (empty = any). Room type requirement optional.
    allowed_instructor_ids: tuple[int, ...] = ()
    required_room_type: str = ""

    @property
    def required_capacity(self) -> int:
        # Forecast-aware: size the room for the larger of current / forecast.
        return max(self.current_enrollment, self.forecast_enrollment)


@dataclass(frozen=True)
class Assignment:
    module_code: str
    session_type: str
    day: str
    start: str
    end: str
    room_id: int
    instructor_id: int

    @property
    def start_min(self) -> int:
        return to_minutes(self.start)

    @property
    def end_min(self) -> int:
        return to_minutes(self.end)


@dataclass
class Weights:
    """Soft-constraint weights. Larger = stronger push. All tunable."""
    gap_per_hour: float = 1.0          # penalty per idle hour in an instructor's day
    room_underfill: float = 0.05       # penalty per empty seat
    instructor_pref_bonus: float = 8.0 # reward for honoring instructor preference
    day_balance: float = 2.0           # penalty for uneven load across the week
    back_to_back: float = 1.5          # penalty per too-tight (same-building) transition

    def as_dict(self) -> dict[str, float]:
        return {
            "gap_per_hour": self.gap_per_hour,
            "room_underfill": self.room_underfill,
            "instructor_pref_bonus": self.instructor_pref_bonus,
            "day_balance": self.day_balance,
            "back_to_back": self.back_to_back,
        }


# Feature 4: optimization-goal presets.
GOAL_PROFILES = {
    "balanced": Weights(),
    "room_utilization": Weights(
        gap_per_hour=0.5, room_underfill=0.5, instructor_pref_bonus=3.0,
        day_balance=1.0, back_to_back=0.5),
    "student_compactness": Weights(
        gap_per_hour=4.0, room_underfill=0.02, instructor_pref_bonus=3.0,
        day_balance=1.0, back_to_back=0.0),   # tight transitions are GOOD for compactness
    "instructor_preference": Weights(
        gap_per_hour=1.0, room_underfill=0.02, instructor_pref_bonus=20.0,
        day_balance=1.0, back_to_back=1.5),
}


def weights_for_goal(goal: str) -> Weights:
    """Return a copy of the preset weights for *goal* (defaults to balanced)."""
    return replace(GOAL_PROFILES.get(goal, GOAL_PROFILES["balanced"]))


@dataclass
class Options:
    day_start: str = "09:00"
    day_end: str = "18:00"
    step_minutes: int = 60
    # Minimum minutes between two consecutive sessions...
    same_building_transition: int = 0     # same building (soft-flagged if below)
    cross_building_travel: int = 15       # different buildings (hard-blocked if below)
    forecast_growth: float = 0.0          # extra % applied to enrollment (informational)
    max_local_search_passes: int = 20
    # Ordering of days used for tie-breaks and balance.
    days: tuple[str, ...] = tuple(DAYS_OF_WEEK)


@dataclass
class SolveResult:
    assignments: list[Assignment]
    unplaced: list[ModuleReq]
    total_cost: float
    breakdown: dict[str, float]
    hard_violations: int
    back_to_back: list[dict]
    travel_violations: list[dict]

    @property
    def placed_count(self) -> int:
        return len(self.assignments)


# --------------------------------------------------------------------------- #
# Feasibility helpers
# --------------------------------------------------------------------------- #
def _transition_gap(s1: int, e1: int, s2: int, e2: int) -> int | None:
    """Idle minutes between two non-overlapping intervals on the same day, or
    None if they overlap. 0 means back-to-back."""
    if overlaps(s1, e1, s2, e2):
        return None
    if e1 <= s2:
        return s2 - e1
    return s1 - e2


# --------------------------------------------------------------------------- #
# Cost / evaluation
# --------------------------------------------------------------------------- #
def evaluate(
    assignments: list[Assignment],
    rooms: dict[int, Room],
    instructors: dict[int, Instructor],
    reqs_by_key: dict[tuple[str, str], ModuleReq],
    weights: Weights,
    options: Options,
) -> tuple[float, dict[str, float], int]:
    """Total soft cost + breakdown + hard-violation count for a full solution."""
    breakdown = {"gaps": 0.0, "underfill": 0.0, "pref": 0.0,
                 "day_balance": 0.0, "back_to_back": 0.0}
    hard = 0

    # Per-instructor / per-day gap + back-to-back + travel.
    by_instr: dict[int, list[Assignment]] = {}
    for a in assignments:
        by_instr.setdefault(a.instructor_id, []).append(a)

    for instr_id, alist in by_instr.items():
        for day in options.days:
            day_sessions = sorted((a for a in alist if a.day == day),
                                  key=lambda a: a.start_min)
            for i in range(len(day_sessions) - 1):
                cur, nxt = day_sessions[i], day_sessions[i + 1]
                gap = nxt.start_min - cur.end_min
                if gap < 0:
                    hard += 1  # overlap (shouldn't happen via construction)
                    continue
                # gap penalty (idle time)
                breakdown["gaps"] += (gap / 60.0) * weights.gap_per_hour
                same_building = rooms[cur.room_id].building == rooms[nxt.room_id].building
                if same_building:
                    if gap < options.same_building_transition or gap == 0:
                        breakdown["back_to_back"] += weights.back_to_back
                else:
                    if gap < options.cross_building_travel:
                        hard += 1  # travel violation

    # Per-assignment underfill + preference.
    for a in assignments:
        room = rooms[a.room_id]
        req = reqs_by_key.get((a.module_code, a.session_type))
        need = req.required_capacity if req else 0
        if room.capacity < need:
            hard += 1
        underfill = max(0, room.capacity - need)
        breakdown["underfill"] += underfill * weights.room_underfill
        instr = instructors.get(a.instructor_id)
        if instr:
            if instr.prefers_day(a.day) and instr.prefers_time(a.start):
                breakdown["pref"] -= weights.instructor_pref_bonus

    # Day balance: penalize uneven distribution of sessions across the week.
    counts = [sum(1 for a in assignments if a.day == d) for d in options.days]
    if counts:
        mean = sum(counts) / len(counts)
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        breakdown["day_balance"] += variance * weights.day_balance

    soft_total = sum(breakdown.values())
    total = soft_total + hard * HARD_VIOLATION_PENALTY
    return total, breakdown, hard


# --------------------------------------------------------------------------- #
# Solver
# --------------------------------------------------------------------------- #
def solve(
    reqs: list[ModuleReq],
    rooms: list[Room],
    instructors: list[Instructor],
    existing: list[Assignment] | None = None,
    weights: Weights | None = None,
    options: Options | None = None,
) -> SolveResult:
    """Place every req into a (day, start, room, instructor) slot.

    Greedy construction (most-constrained-first) followed by a hill-climbing
    local search that re-balances overloaded days. ``existing`` assignments are
    treated as fixed occupancy (already-published schedule) and are never moved
    or returned in the result.
    """
    weights = weights or Weights()
    options = options or Options()
    existing = list(existing or [])
    rooms_by_id = {r.id: r for r in rooms}
    instr_by_id = {i.id: i for i in instructors}
    reqs_by_key = {(r.module_code, r.session_type): r for r in reqs}

    # Building-aware travel check bound to this room registry.
    def rooms_differ_building(room_id_a: int, room_id_b: int) -> bool:
        ra, rb = rooms_by_id.get(room_id_a), rooms_by_id.get(room_id_b)
        if ra is None or rb is None:
            return False
        return ra.building != rb.building

    def feasible(cand: Assignment, req: ModuleReq, room: Room,
                 placed: list[Assignment]) -> bool:
        if room.capacity < req.required_capacity:
            return False
        if (req.required_room_type and room.room_type
                and req.required_room_type != room.room_type):
            return False
        cs, ce = cand.start_min, cand.end_min
        for a in placed:
            if a.day != cand.day:
                continue
            if a.room_id == cand.room_id and overlaps(cs, ce, a.start_min, a.end_min):
                return False
            if a.instructor_id == cand.instructor_id:
                if overlaps(cs, ce, a.start_min, a.end_min):
                    return False
                gap = _transition_gap(cs, ce, a.start_min, a.end_min)
                if (gap is not None and gap < options.cross_building_travel
                        and rooms_differ_building(cand.room_id, a.room_id)):
                    return False
        return True

    # Most-constrained-first: bigger classes and longer sessions are hardest to
    # place, so seat them earliest while the timetable is empty.
    order = sorted(
        range(len(reqs)),
        key=lambda idx: (-reqs[idx].required_capacity, -reqs[idx].duration,
                         reqs[idx].module_code),
    )

    placed: list[Assignment] = list(existing)
    proposed: list[Assignment] = []
    unplaced: list[ModuleReq] = []

    for idx in order:
        req = reqs[idx]
        candidate_instructors = (
            [i for i in instructors if i.id in req.allowed_instructor_ids]
            if req.allowed_instructor_ids else instructors
        )
        if not candidate_instructors:
            candidate_instructors = instructors
        starts_cache: dict[int, list[str]] = {}
        best: Assignment | None = None
        best_cost = float("inf")
        for day in options.days:
            for room in rooms:
                if room.capacity < req.required_capacity:
                    continue
                starts = starts_cache.get(req.duration)
                if starts is None:
                    starts = generate_start_times(
                        options.day_start, options.day_end, req.duration,
                        options.step_minutes)
                    starts_cache[req.duration] = starts
                for start in starts:
                    end = to_hhmm(to_minutes(start) + req.duration)
                    for instr in candidate_instructors:
                        cand = Assignment(req.module_code, req.session_type, day,
                                          start, end, room.id, instr.id)
                        if not feasible(cand, req, room, placed):
                            continue
                        cost, _, _ = evaluate(
                            proposed + [cand], rooms_by_id, instr_by_id,
                            reqs_by_key, weights, options)
                        if cost < best_cost:
                            best_cost, best = cost, cand
        if best is None:
            unplaced.append(req)
        else:
            placed.append(best)
            proposed.append(best)

    # Feature 5: heuristic re-balancer (hill-climb).
    proposed = _local_search(
        proposed, existing, reqs_by_key, rooms, rooms_by_id, instr_by_id,
        instructors, weights, options, feasible)

    total, breakdown, hard = evaluate(
        proposed + existing, rooms_by_id, instr_by_id, reqs_by_key, weights, options)
    # Recompute breakdown over proposed+existing but hard/back-to-back reports
    # should include everything the user will see.
    all_assignments = proposed + existing
    return SolveResult(
        assignments=proposed,
        unplaced=unplaced,
        total_cost=total,
        breakdown=breakdown,
        hard_violations=hard,
        back_to_back=find_back_to_back(all_assignments, rooms_by_id, options),
        travel_violations=find_travel_violations(all_assignments, rooms_by_id, options),
    )


def _local_search(
    proposed: list[Assignment],
    existing: list[Assignment],
    reqs_by_key: dict[tuple[str, str], ModuleReq],
    rooms: list[Room],
    rooms_by_id: dict[int, Room],
    instr_by_id: dict[int, Instructor],
    instructors: list[Instructor],
    weights: Weights,
    options: Options,
    feasible: Callable,
) -> list[Assignment]:
    """Hill-climb: repeatedly relocate one proposed session to a slot that
    lowers total cost. Deterministic; stops when a full pass yields no
    improvement or ``max_local_search_passes`` is reached. Only proposed
    sessions move — ``existing`` stays fixed."""
    current = list(proposed)

    def total_of(assigns: list[Assignment]) -> float:
        t, _, _ = evaluate(assigns + existing, rooms_by_id, instr_by_id,
                           reqs_by_key, weights, options)
        return t

    best_total = total_of(current)
    for _ in range(options.max_local_search_passes):
        improved = False
        for i in range(len(current)):
            a = current[i]
            req = reqs_by_key.get((a.module_code, a.session_type))
            if req is None:
                continue
            others = current[:i] + current[i + 1:]
            starts = generate_start_times(
                options.day_start, options.day_end, req.duration, options.step_minutes)
            local_best = a
            local_best_total = best_total
            for day in options.days:
                for room in rooms:
                    if room.capacity < req.required_capacity:
                        continue
                    for start in starts:
                        end = to_hhmm(to_minutes(start) + req.duration)
                        instr_id = a.instructor_id
                        cand = Assignment(a.module_code, a.session_type, day,
                                          start, end, room.id, instr_id)
                        if cand == a:
                            continue
                        if not feasible(cand, req, room, others + existing):
                            continue
                        t = total_of(others + [cand])
                        if t < local_best_total - 1e-9:
                            local_best_total = t
                            local_best = cand
            if local_best is not a:
                current[i] = local_best
                best_total = local_best_total
                improved = True
        if not improved:
            break
    return current


# --------------------------------------------------------------------------- #
# Analysis / reporting (features 6 & 7)
# --------------------------------------------------------------------------- #
def find_back_to_back(
    assignments: list[Assignment],
    rooms_by_id: dict[int, Room],
    options: Options,
) -> list[dict]:
    """Flag instructor sessions with little/no transition time between them."""
    out = []
    by_instr: dict[int, list[Assignment]] = {}
    for a in assignments:
        by_instr.setdefault(a.instructor_id, []).append(a)
    for instr_id, alist in by_instr.items():
        for day in options.days:
            day_sessions = sorted((a for a in alist if a.day == day),
                                  key=lambda a: a.start_min)
            for i in range(len(day_sessions) - 1):
                cur, nxt = day_sessions[i], day_sessions[i + 1]
                gap = nxt.start_min - cur.end_min
                if gap < 0:
                    continue
                same_building = (rooms_by_id[cur.room_id].building
                                 == rooms_by_id[nxt.room_id].building)
                threshold = (options.same_building_transition if same_building
                             else options.cross_building_travel)
                if gap <= 0 or gap < threshold:
                    out.append({
                        "instructor_id": instr_id,
                        "day": day,
                        "gap_minutes": gap,
                        "same_building": same_building,
                        "first": f"{cur.module_code} {cur.start}-{cur.end}",
                        "second": f"{nxt.module_code} {nxt.start}-{nxt.end}",
                    })
    return out


def find_travel_violations(
    assignments: list[Assignment],
    rooms_by_id: dict[int, Room],
    options: Options,
) -> list[dict]:
    """Flag consecutive instructor sessions in different buildings whose gap is
    below the required travel time (a hard-constraint report)."""
    out = []
    by_instr: dict[int, list[Assignment]] = {}
    for a in assignments:
        by_instr.setdefault(a.instructor_id, []).append(a)
    for instr_id, alist in by_instr.items():
        for day in options.days:
            day_sessions = sorted((a for a in alist if a.day == day),
                                  key=lambda a: a.start_min)
            for i in range(len(day_sessions) - 1):
                cur, nxt = day_sessions[i], day_sessions[i + 1]
                gap = nxt.start_min - cur.end_min
                if gap < 0:
                    continue
                ba, bb = rooms_by_id[cur.room_id].building, rooms_by_id[nxt.room_id].building
                if ba != bb and gap < options.cross_building_travel:
                    out.append({
                        "instructor_id": instr_id,
                        "day": day,
                        "gap_minutes": gap,
                        "required": options.cross_building_travel,
                        "from_building": ba,
                        "to_building": bb,
                        "first": f"{cur.module_code} {cur.start}-{cur.end}",
                        "second": f"{nxt.module_code} {nxt.start}-{nxt.end}",
                    })
    return out
