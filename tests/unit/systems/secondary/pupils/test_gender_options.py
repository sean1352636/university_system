"""Five gender options on the secondary pupil record, the same as every other
system: validation, spreadsheet spellings, the census F/M mapping, and the
one-off widening of an existing database's Female/Male-only rule. Temporary
databases only."""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.secondary.infrastructure.database import connection as db
from education_system.systems.secondary.modules.pupils.domain import bulk_import as BI
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.modules.reporting.domain import census

FIVE = ("Female", "Male", "Non-binary", "Other", "Prefer not to say")


def test_same_five_options_as_fe_college():
    from education_system.systems.fe_college import config as fe

    assert P.GENDERS == FIVE == fe.GENDERS


@pytest.mark.parametrize("raw, expected", [
    ("female", "Female"), ("MALE", "Male"), ("non-binary", "Non-binary"),
    ("  prefer   not to say ", "Prefer not to say"), ("other", "Other"),
    ("Robot", "Robot"),  # passed through for the rules to refuse
])
def test_gender_choice(raw, expected):
    assert P.gender_choice(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("F", "Female"), ("boy", "Male"), ("nb", "Non-binary"), ("Nonbinary", "Non-binary"),
    ("not stated", "Prefer not to say"), ("other", "Other"),
])
def test_spreadsheet_spellings(raw, expected):
    assert BI.normalise("gender", raw) == expected


@pytest.mark.parametrize("gender, code", [
    ("Female", "F"), ("Male", "M"), ("Non-binary", ""), ("Other", ""),
    ("Prefer not to say", ""), (None, ""),
])
def test_census_takes_f_or_m_only(gender, code):
    assert census.census_gender(gender) == code


def test_report_groups_have_an_other_bucket():
    from types import SimpleNamespace

    from education_system.systems.secondary.modules.reporting.domain import report_common

    groups = dict(report_common.GROUPS)
    pupil = SimpleNamespace(gender="Non-binary")
    assert groups["Other / not stated"](pupil)
    assert not groups["Female"](pupil) and not groups["Male"](pupil)


_INSERT = ("INSERT INTO pupils (legal_first_name, legal_last_name, date_of_birth, gender, "
           "year_group, admission_date) VALUES (?, 'Test', '2012-01-01', ?, 8, '2023-09-01')")


@pytest.fixture
def old_database(tmp_path):
    """A secondary.db made before the five options: Female/Male-only CHECK,
    one pupil, and another table with a foreign key to them."""
    path = tmp_path / "old.db"
    old = P._GENDER_CHECK
    ddl = P._SCHEMA.replace(
        "CHECK (gender IN ('Female', 'Male', 'Non-binary', 'Other',\n"
        "                                                  'Prefer not to say'))",
        "CHECK (gender IN ('Female', 'Male'))")
    assert ddl != P._SCHEMA and old
    with sqlite3.connect(path) as conn:
        conn.executescript(ddl)
        conn.execute("CREATE TABLE linked (id INTEGER PRIMARY KEY, pupil_id INTEGER "
                     "REFERENCES pupils(pupil_id) ON DELETE CASCADE)")
        conn.execute(_INSERT, ("Ada", "Female"))
        conn.execute("INSERT INTO linked (pupil_id) VALUES (1)")
    db.use_database(path)
    yield path
    db.use_database(None)


def test_old_database_is_widened_keeping_rows_links_and_indexes(old_database):
    with db.connect() as conn:
        conn.execute(_INSERT, ("Bo", "Non-binary"))
        assert [tuple(r) for r in conn.execute("SELECT legal_first_name, gender FROM pupils "
                                                "ORDER BY pupil_id")] == [
            ("Ada", "Female"), ("Bo", "Non-binary")]
        assert conn.execute("SELECT COUNT(*) FROM linked").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'pupils'")}
        assert {"ix_pupils_name", "ix_pupils_year"} <= names
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, ("Cy", "Robot"))


def test_widening_runs_once(old_database):
    with db.connect() as conn:
        P._widen_gender_check(conn)  # already widened: nothing to do
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'pupils'").fetchone()[0]
    assert sql.count("Prefer not to say") == 1
