"""Every Alternative Provision test gets its own empty database (never the live one)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.alternative_provision.app import routing
from education_system.systems.alternative_provision.infrastructure import database

routing.load_areas()

TODAY = date.today()


def ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


def _pupil(first: str, last: str, **extra) -> int:
    from education_system.systems.alternative_provision.core import records as r
    from education_system.systems.alternative_provision.modules import learners
    dob = date(TODAY.year - 14, 3, 12)
    return r.save(learners.LEARNERS, {"first_name": first, "last_name": last,
                                      "dob": dob.isoformat(), "gender": "Male",
                                      "year_group": learners.year_group_for(dob, TODAY),
                                      **extra})


@pytest.fixture(autouse=True)
def ap_db(tmp_path):
    database.use_database(tmp_path / "alternative_provision.db")
    yield tmp_path / "alternative_provision.db"
    database.use_database(None)


@pytest.fixture
def make_pupil():
    """make_pupil(first, last, **fields) -> id: a 14-year-old in the right year group."""
    return _pupil


@pytest.fixture
def pupil():
    return _pupil("Sam", "Jones")


@pytest.fixture
def second_pupil():
    return _pupil("Ana", "Lee", status="On roll", start_date=ago(60))


@pytest.fixture
def make_provider():
    from education_system.systems.alternative_provision.core import records as r
    from education_system.systems.alternative_provision.modules import placements

    def make(name: str = "Northside PRU", kind: str = "Pupil referral unit", **extra) -> int:
        return r.save(placements.PROVIDERS, {"name": name, "kind": kind, "daily_rate": "120",
                                             **extra})
    return make


@pytest.fixture
def placement(pupil, make_provider):
    """An active 15-hour (part-time) placement that started two weeks ago."""
    from education_system.systems.alternative_provision.core import records as r
    from education_system.systems.alternative_provision.modules import placements
    return r.save(placements.PLACEMENTS, {
        "learner_id": pupil, "provider_id": make_provider(), "hours_per_week": 15,
        "part_time_reason": "anxiety", "start_date": ago(14), "status": "Active",
        "commissioner": "Oak High"})
