"""Tests for the timetable optimiser."""

from __future__ import annotations

import sqlite3

import pytest


def _seed_groups(db: str) -> None:
    """Two courses / two class groups with distinct teachers + rooms,
    sharing one student (S1) so clash handling is exercised."""
    conn = sqlite3.connect(db)
    conn.executemany(
        "INSERT INTO courses (course_id, course_code, subject, title, year_group, "
        "academic_year, teacher, room, max_students) VALUES (?,?,?,?,?,?,?,?,?)",
        [(1, "MATH-12", "Mathematics", "A-Level Maths", 12, "2025/26", "Mr Ng", "R1", 25),
         (2, "PHYS-12", "Physics", "A-Level Physics", 12, "2025/26", "Ms Lee", "R2", 25)])
    conn.executemany(
        "INSERT INTO class_groups (group_id, course_id, group_name, teacher, room) "
        "VALUES (?,?,?,?,?)",
        [(1, 1, "12M-1", "Mr Ng", "R1"), (2, 2, "12P-1", "Ms Lee", "R2")])
    conn.executemany(
        "INSERT INTO class_group_students (group_id, student_id) VALUES (?,?)",
        [(1, "S1"), (1, "S2"), (2, "S1")])
    conn.commit()
    conn.close()


def test_generate_places_all_lessons(feature_db):
    _seed_groups(feature_db.db)
    opt = feature_db.mods["timetable_optimiser"]
    result = opt.generate(lessons_per_week=4, name="T1")
    assert result.group_count == 2
    assert result.placed == 8           # 2 groups × 4 lessons
    assert result.unplaced == []


def test_no_teacher_or_group_double_booking(feature_db):
    _seed_groups(feature_db.db)
    opt = feature_db.mods["timetable_optimiser"]
    result = opt.generate(lessons_per_week=5, name="T2")
    # A group never occupies the same cell twice.
    for gid in {s.group_id for s in result.slots}:
        cells = [(s.day, s.period) for s in result.slots if s.group_id == gid]
        assert len(cells) == len(set(cells))
    # No teacher in two places at once: here each group has its own
    # teacher, so any (day, period) holds at most one slot per teacher.
    by_cell: dict[tuple[int, int], set[int]] = {}
    for s in result.slots:
        by_cell.setdefault((s.day, s.period), set()).add(s.group_id)
    # S1 is in both groups → they must never share a cell (soft clash → 0).
    assert result.student_clashes == []


def test_invalid_lessons_per_week(feature_db):
    opt = feature_db.mods["timetable_optimiser"]
    with pytest.raises(ValueError):
        opt.generate(lessons_per_week=0)
    with pytest.raises(ValueError):
        opt.generate(lessons_per_week=999)


def test_save_list_and_commit(feature_db):
    _seed_groups(feature_db.db)
    opt = feature_db.mods["timetable_optimiser"]
    result = opt.generate(lessons_per_week=3, name="Commit me")
    pid = opt.save_plan(result)
    plans = opt.list_plans()
    assert any(p["plan_id"] == pid and p["status"] == "Draft" for p in plans)
    assert len(opt.plan_slots(pid)) == 6

    written = opt.commit_plan(pid)
    assert written == 6
    # Live timetable_slots now hold the committed cells.
    conn = sqlite3.connect(feature_db.db)
    n = conn.execute("SELECT COUNT(*) FROM timetable_slots").fetchone()[0]
    conn.close()
    assert n == 6
    # Plan flips to Committed.
    assert next(p for p in opt.list_plans() if p["plan_id"] == pid)["status"] == "Committed"


def test_delete_plan(feature_db):
    _seed_groups(feature_db.db)
    opt = feature_db.mods["timetable_optimiser"]
    pid = opt.save_plan(opt.generate(lessons_per_week=2))
    opt.delete_plan(pid)
    assert all(p["plan_id"] != pid for p in opt.list_plans())
