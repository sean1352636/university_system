"""Shared fixture for the Sixth Form calendar tests.

Points every calendar module at one temporary SQLite file so nothing
touches the real ``sixthform.db``. The academic-year DB is isolated
too: :mod:`calendar_terms` reads term dates and closures through it,
so leaving it alone would have the tests reading — and the term
fixture writing — the live year. The ``caldb`` fixture returns a
small namespace with the path and a couple of seeded events the
read-side tests share.
"""

from __future__ import annotations

import datetime as _dt
from types import SimpleNamespace

import pytest

from education_system.systems.sixth_form.domain.academics.academic_year import (  # noqa: E501
    academic_year as year_core,
)
from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
    calendar_bookings as bookings,
    calendar_clashes as clashes,
    calendar_exchange as exchange,
    calendar_governance as governance,
    calendar_ics as ics,
    calendar_notifications as notifications,
    calendar_portal as portal,
    calendar_recurrence as recurrence,
    calendar_taxonomy as taxonomy,
    calendar_terms as terms,
    calendar_trips as trips,
)

_MODULES = (core, bookings, governance, ics, notifications,
            recurrence, taxonomy, trips)
# clashes / terms / exchange / portal have no DB of their own; they
# read through core. Imported above so a syntax error in any of them
# fails collection loudly rather than at first use.
_ = (clashes, terms, exchange, portal)


@pytest.fixture
def caldb(tmp_path, monkeypatch):
    db_path = str(tmp_path / "sixthform.db")
    for mod in _MODULES:
        monkeypatch.setattr(mod, "DB_PATH", db_path, raising=False)
        monkeypatch.setattr(mod, "_DB_READY", False, raising=False)
    core.init_db()

    # calendar_terms asks the academic year about terms, breaks and
    # closed days. Redirect it as well — its init_db() caches on the
    # DB path, so the set must be cleared, not just the path.
    monkeypatch.setattr(year_core, "DB_PATH",
                        str(tmp_path / "academic_year.db"),
                        raising=False)
    monkeypatch.setattr(year_core, "_DB_READY", set(), raising=False)
    year_core.init_db()

    today = _dt.date.today()
    return SimpleNamespace(
        path=db_path,
        today=today.isoformat(),
        next_week=(today + _dt.timedelta(days=7)).isoformat(),
    )


@pytest.fixture
def one_event(caldb):
    """A plain timed event on a fixed date."""
    return core.create_event({
        "title": "Parents' Evening",
        "event_type": "Parents' Evening",
        "start_date": "2026-10-08",
        "start_time": "16:30",
        "end_time": "19:00",
        "location": "Main Hall",
        "organiser": "P Jones",
        "audience": "Parents",
        "visibility": "Public",
    }, actor="jsmith")
