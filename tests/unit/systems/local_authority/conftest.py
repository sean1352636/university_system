"""Every Local Authority Education test gets its own empty database (never the live one)."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from education_system.systems.local_authority.app import routing
from education_system.systems.local_authority.infrastructure import database

routing.load_areas()


@pytest.fixture(autouse=True)
def la_db(tmp_path):
    database.use_database(tmp_path / "local_authority.db")
    yield tmp_path / "local_authority.db"
    database.use_database(None)


@pytest.fixture
def make_child():
    """make_child(first, last, age=10, **fields) -> id: at school if a school_id is given,
    otherwise not in education."""
    from education_system.systems.local_authority.core import records as r
    from education_system.systems.local_authority.modules import children

    def make(first: str = "Ben", last: str = "Cole", age: int = 10, **extra) -> int:
        today = date.today()
        dob = date(today.year - age, 5, 5) if (today.month, today.day) >= (5, 5) else \
            date(today.year - age - 1, 5, 5)
        extra.setdefault("education", "At school" if extra.get("school_id") else
                         "Not in education")
        return r.save(children.CHILDREN, {"first_name": first, "last_name": last,
                                          "dob": dob.isoformat(), **extra})
    return make


@pytest.fixture
def world():
    """Four schools: Oak Primary (community, PAN 1), Elm Primary (PAN 30), High
    School (secondary) and Brook Special."""
    from education_system.systems.local_authority.core import records as r
    from education_system.systems.local_authority.modules import schools
    w = SimpleNamespace()
    w.oak = r.save(schools.SCHOOLS, {"name": "Oak Primary", "urn": "100001", "phase": "Primary",
                                     "school_type": "Community", "pan": 1, "capacity": 210,
                                     "on_roll": 200})
    w.elm = r.save(schools.SCHOOLS, {"name": "Elm Primary", "urn": "100002",
                                     "phase": "Primary", "pan": 30, "capacity": 210})
    w.high = r.save(schools.SCHOOLS, {"name": "High School", "urn": "100003",
                                      "phase": "Secondary", "pan": 180, "capacity": 900})
    w.special = r.save(schools.SCHOOLS, {"name": "Brook Special", "urn": "100004",
                                         "phase": "Special", "school_type": "Community"})
    return w


def days(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()
