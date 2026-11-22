"""Every Adult Education test gets its own empty database (never the live one)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.adult_education.app import routing
from education_system.systems.adult_education.infrastructure import database

routing.load_areas()


@pytest.fixture(autouse=True)
def adult_db(tmp_path):
    database.use_database(tmp_path / "adult_education.db")
    yield tmp_path / "adult_education.db"
    database.use_database(None)


@pytest.fixture
def learner():
    from education_system.systems.adult_education.core import records as r
    from education_system.systems.adult_education.modules import learners
    return r.save(learners.LEARNERS, {"first_name": "Jo", "last_name": "Bloggs",
                                      "dob": "1980-03-12", "gender": "Female"})


@pytest.fixture
def second_learner():
    from education_system.systems.adult_education.core import records as r
    from education_system.systems.adult_education.modules import learners
    return r.save(learners.LEARNERS, {"first_name": "Ann", "last_name": "Lee",
                                      "dob": "1990-01-01", "gender": "Female"})


@pytest.fixture
def course():
    from education_system.systems.adult_education.core import records as r
    from education_system.systems.adult_education.modules import courses
    return r.save(courses.COURSES, {"code": "eng 1", "title": "English L1",
                                    "subject": "English", "level": "Level 1", "fee": "200"})


@pytest.fixture
def make_class(course):
    from education_system.systems.adult_education.core import records as r
    from education_system.systems.adult_education.modules import courses

    def make(capacity: int = 10, start_time: str = "18:30") -> int:
        return r.save(courses.CLASSES, {
            "course_id": course,
            "start_date": (date.today() - timedelta(days=30)).isoformat(),
            "end_date": (date.today() + timedelta(days=60)).isoformat(),
            "day": "Tuesday", "start_time": start_time, "end_time": "20:30",
            "capacity": capacity, "status": "Running"})
    return make
