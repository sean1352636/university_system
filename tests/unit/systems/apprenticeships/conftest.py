"""Test fixtures for the apprenticeships system.

Every test in this package runs against a throwaway SQLite file. The
schema module holds its path in a module global and caches a "schema is
ready" flag, so both have to be reset — repointing the path alone would
leave the next ``init_db()`` short-circuiting on the stale flag and the
tests silently writing to the real database.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships.infrastructure.persistence import schema
from education_system.systems.apprenticeships.services.access import Actor


@pytest.fixture(autouse=True)
def platform_auth_db(tmp_path, monkeypatch):
    """Keep every platform write in this package off the live ``auth.db``.

    Creating an apprentice registers them on the platform (identity,
    enrolment, bus events) and links their login, and the account screens
    read the shared logins — all through ``auth.db.connect()``, which
    reads ``PLATFORM_AUTH_DB_FILE`` when called. Repointing that name
    moves them all. The cross-system modules cache "schema ready" under
    the default-path key, so those caches are reset too, or the new file
    would never get its tables. Autouse, so it is in place before ``db``
    or ``cohort`` create anything.
    """
    from education_system import paths
    from education_system.platform.cross_system import (
        destinations,
        enrolment_schema,
        identity_service,
        qualifications,
    )
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.identity.auth.schema import initialise_auth_db

    path = tmp_path / "platform_auth.db"
    for module, name in ((auth_db, "PLATFORM_AUTH_DB_FILE"), (auth_db, "AUTH_DB_FILE"),
                         (paths, "PLATFORM_AUTH_DB_FILE"), (paths, "PLATFORM_AUTH_DB")):
        value = str(path) if isinstance(getattr(module, name, None), str) else path
        monkeypatch.setattr(module, name, value, raising=False)
    for module in (identity_service, enrolment_schema, destinations, qualifications):
        monkeypatch.setattr(module, "_initialised", set())
    initialise_auth_db(str(path))
    yield str(path)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Point the system at an empty database for one test."""
    monkeypatch.setattr(schema, "DB_PATH", tmp_path / "apprenticeships.db")
    schema.reset_ready_flag()
    schema.init_db()
    yield schema.DB_PATH
    schema.reset_ready_flag()


@pytest.fixture
def admin() -> Actor:
    return Actor(username="admin5", role="admin", display_name="Admin")


@pytest.fixture
def assessor() -> Actor:
    return Actor(username="assessor1", role="end_point_assessor")


@pytest.fixture
def cohort(db, admin):
    """A programme, an employer, a tutor and one apprentice on programme.

    Returns a dict of ids plus ready-made scoped actors, so a test can
    go straight to the behaviour it cares about. The start date is well
    in the past so the minimum-practical-period gateway check passes.
    """
    from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
        staff_repository,
    )
    from education_system.systems.apprenticeships.services import (
        apprentice_service,
        employer_service,
        programme_service,
    )

    programme = programme_service.create_programme(admin, {
        "reference": "ST0119", "title": "Software Developer", "level": 4,
        "funding_band": 13, "duration_months": 24,
        "epa_methods": ["Knowledge test", "Project with report"],
    })
    for code, description in (("K1", "Programming"), ("S1", "Writes code"),
                              ("B1", "Works collaboratively")):
        programme_service.add_ksb(
            admin, programme.programme_id, {"code": code, "description": description}
        )
    programme_service.activate_programme(admin, programme.programme_id)

    employer = employer_service.create_employer(admin, {
        "name": "Acme Ltd", "headcount": 30, "paybill": 900_000.0, "status": "Active",
    })
    manager = employer_service.add_manager(admin, employer.employer_id, {
        "full_name": "Dana Reed", "username": "employer1",
    })
    employer_service.set_primary_manager(admin, employer.employer_id, manager.manager_id)

    tutor_id = staff_repository.create({
        "full_name": "Sam Okafor", "staff_role": "Tutor", "username": "tutor1",
    })

    apprentice = apprentice_service.create_apprentice(admin, {
        "given_name": "Jo", "family_name": "Bell", "uln": "1234567890",
        "date_of_birth": "2003-05-01", "username": "apprentice1",
        "programme_id": programme.programme_id, "employer_id": employer.employer_id,
        "tutor_id": tutor_id, "weekly_hours": 37.5,
    })
    start = (date.today() - timedelta(days=400)).isoformat()
    apprentice = apprentice_service.start_programme(
        admin, apprentice.apprentice_id, start_date=start
    )

    return {
        "programme": programme,
        "employer": employer,
        "tutor_id": tutor_id,
        "apprentice": apprentice,
        "apprentice_id": apprentice.apprentice_id,
        "start_date": start,
        "tutor": Actor(username="tutor1", role="staff", staff_id=tutor_id),
        "learner": Actor(
            username="apprentice1", role="apprentice",
            apprentice_id=apprentice.apprentice_id, employer_id=employer.employer_id,
        ),
        "employer_actor": Actor(
            username="employer1", role="employer", employer_id=employer.employer_id
        ),
        "outsider": Actor(username="rival", role="employer", employer_id=9999),
    }
