"""Conflict detection and availability queries for the Exam Scheduling System."""

from typing import List, Optional

from education_system.post_18.university_system.modules.domain.academics.gui.exam_management.models import Exam, Room


def check_conflict(exams: List[Exam], date: str, start_time: str, end_time: str,
                   room: str, exclude_id: Optional[int] = None) -> bool:
    """Check if there's a scheduling conflict."""
    for exam in exams:
        if exclude_id and exam.id == exclude_id:
            continue
        if exam.date == date and exam.room == room:
            # Check time overlap
            if not (end_time <= exam.start_time or start_time >= exam.end_time):
                return True
    return False


def get_conflicting_exams(exams: List[Exam], date: str, start_time: str, end_time: str,
                          room: str, exclude_id: Optional[int] = None) -> List[Exam]:
    """Get list of conflicting exams for a given date/time/room."""
    conflicts = []
    for exam in exams:
        if exclude_id and exam.id == exclude_id:
            continue
        if exam.date == date and exam.room == room:
            # Check time overlap
            if not (end_time <= exam.start_time or start_time >= exam.end_time):
                conflicts.append(exam)
    return conflicts


def check_instructor_conflict(exams: List[Exam], date: str, start_time: str, end_time: str,
                              instructor_id: Optional[int], exclude_id: Optional[int] = None) -> List[Exam]:
    """Check if instructor has conflicting exams at the same time."""
    if not instructor_id:
        return []

    conflicts = []
    for exam in exams:
        if exclude_id and exam.id == exclude_id:
            continue
        if exam.date == date and exam.instructor_id == instructor_id:
            # Check time overlap
            if not (end_time <= exam.start_time or start_time >= exam.end_time):
                conflicts.append(exam)
    return conflicts


def get_available_rooms(exams: List[Exam], rooms: List[Room], date: str, start_time: str, end_time: str,
                        min_capacity: int = 0, exclude_id: Optional[int] = None) -> List[Room]:
    """Get list of rooms available for a specific date/time with optional capacity filter."""
    available = []
    for room in rooms:
        # Check capacity requirement
        if min_capacity > 0 and room.capacity < min_capacity:
            continue

        # Check if room is free during this time
        has_conflict = False
        for exam in exams:
            if exclude_id and exam.id == exclude_id:
                continue
            if exam.date == date and exam.room == room.name:
                # Check time overlap
                if not (end_time <= exam.start_time or start_time >= exam.end_time):
                    has_conflict = True
                    break

        if not has_conflict:
            available.append(room)

    return available


def get_exams_by_date_range(exams: List[Exam], start_date: str, end_date: str) -> List[Exam]:
    """Get exams within a date range."""
    filtered = []
    for exam in exams:
        if start_date <= exam.date <= end_date:
            filtered.append(exam)
    return sorted(filtered, key=lambda x: (x.date, x.start_time))


def get_exams_by_instructor(exams: List[Exam], instructor_id: int) -> List[Exam]:
    """Get all exams for a specific instructor."""
    return [e for e in exams if e.instructor_id == instructor_id]


def get_exams_by_room(exams: List[Exam], room_name: str) -> List[Exam]:
    """Get all exams in a specific room."""
    return [e for e in exams if e.room == room_name]
