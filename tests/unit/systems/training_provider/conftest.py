"""Every Training Provider test gets its own empty database (never the live one)."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from education_system.systems.training_provider.app import routing
from education_system.systems.training_provider.infrastructure import database

routing.load_areas()


def _day(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


@pytest.fixture(autouse=True)
def tp_db(tmp_path):
    database.use_database(tmp_path / "training_provider.db")
    yield tmp_path / "training_provider.db"
    database.use_database(None)


@pytest.fixture
def make_learner():
    """make_learner(first, last, **fields) -> id: an adult, self-funded learner."""
    from education_system.systems.training_provider.core import records as r
    from education_system.systems.training_provider.modules import learners

    def make(first: str = "Ann", last: str = "Lee", **extra) -> int:
        return r.save(learners.LEARNERS, {"first_name": first, "last_name": last,
                                          "dob": "1990-05-01", **extra})
    return make


@pytest.fixture
def world():
    """A client (PO needed, 10% contract), an accredited 3-day course (max 3,
    min age 16, pass mark 70, 36-month certificate), a CPD course, an
    approved assessor-trainer, an IQA, a 2-place room, an online venue and a
    confirmed FAW session that started 10 days ago online."""
    from education_system.systems.training_provider.core import records as r
    from education_system.systems.training_provider.modules import clients, courses, sessions
    w = SimpleNamespace()
    w.client = r.save(clients.CLIENTS, {"name": "Acme Ltd", "po_required": 1,
                                        "credit_limit": 1000})
    r.save(clients.CONTRACTS, {"client_id": w.client, "title": "Framework",
                               "start_date": _day(-30), "end_date": _day(300),
                               "discount_pct": 10, "status": "Active"})
    w.faw = r.save(courses.COURSES, {
        "code": "faw", "title": "First Aid at Work", "category": "First aid",
        "kind": courses.KINDS[0], "awarding_body": "Qualsafe", "duration_days": 3,
        "max_delegates": 3, "min_delegates": 2, "min_age": 16, "price": 300,
        "pass_mark": 70, "valid_months": 36})
    w.cpd = r.save(courses.COURSES, {"code": "CS1", "title": "Customer care",
                                     "category": "Customer service", "price": 100,
                                     "max_delegates": 10})
    w.trainer = r.save(courses.TRAINERS, {"name": "Tina", "assessor_qualified": 1,
                                          "dbs_date": _day(-400)})
    w.iqa = r.save(courses.TRAINERS, {"name": "Ian", "iqa_qualified": 1})
    for course in (w.faw, w.cpd):
        r.save(courses.APPROVALS, {"trainer_id": w.trainer, "course_id": course,
                                   "approved_on": _day(-500)})
    w.room = r.save(courses.VENUES, {"name": "Room 1", "capacity": 2})
    w.online = r.save(courses.VENUES, {"name": "Zoom", "kind": "Online"})
    w.session = r.save(sessions.SESSIONS, {"course_id": w.faw, "start_date": _day(-10),
                                           "venue_id": w.online, "trainer_id": w.trainer,
                                           "status": "Confirmed"})
    return w
