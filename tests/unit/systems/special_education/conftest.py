"""Every SEND test gets its own empty database (never the live one)."""

from __future__ import annotations

import pytest

from education_system.systems.special_education.app import routing
from education_system.systems.special_education.infrastructure import database

routing.load_areas()


@pytest.fixture(autouse=True)
def send_db(tmp_path):
    database.use_database(tmp_path / "special_education.db")
    yield tmp_path / "special_education.db"
    database.use_database(None)


@pytest.fixture
def learner():
    from education_system.systems.special_education.core import records as r
    from education_system.systems.special_education.modules import learners
    return r.save(learners.LEARNERS, {"first_name": "Amy", "last_name": "Smith",
                                      "dob": "2015-03-12", "year_group": "Year 5"})
