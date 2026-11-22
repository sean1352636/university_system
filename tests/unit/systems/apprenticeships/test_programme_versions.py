"""Programme versions: a revision is a new row sharing the reference.

Apprentices on the old version keep it and still see it; new enrolments
are only offered the active version. The table rebuild that lets two
versions share a reference is tested against an old-shaped database.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.programmes import versions as rules
from education_system.systems.apprenticeships.infrastructure.persistence import (
    programme_versions_migration as migration,
)
from education_system.systems.apprenticeships.infrastructure.persistence import schema
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.programmes import programme_service
from education_system.systems.apprenticeships.application.security.access import Actor

# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════


class TestVersionRules:
    @pytest.mark.parametrize(("current", "expected"), [
        ("1.0", "1.1"), ("1.9", "1.10"), ("2", "2.1"), ("1.2.3", "1.2.4"), (None, "1.1"),
    ])
    def test_the_next_version_is_the_next_minor(self, current, expected):
        assert rules.next_version(current) == expected

    def test_versions_sort_numerically(self):
        assert rules.version_key("1.10") > rules.version_key("1.9")

    def test_a_new_version_must_come_after(self):
        assert rules.require_newer("v2.0", "1.3") == "2.0"
        with pytest.raises(ValidationError, match="after 1.1"):
            rules.require_newer("1.1", "1.1")
        with pytest.raises(ValidationError, match="after 1.1"):
            rules.require_newer("1.0", "1.1")

    def test_a_version_is_dotted_numbers(self):
        with pytest.raises(ValidationError, match="separated by dots"):
            rules.validate_version("one")

    def test_superseded_is_a_programme_status(self):
        assert "Superseded" in config.PROGRAMME_STATUSES


# ═════════════════════════════════════════════════════════════════════
# Cutting a new version
# ═════════════════════════════════════════════════════════════════════

class TestNewVersion:
    def test_it_copies_ksbs_duties_and_curriculum(self, cohort, admin):
        old_id = cohort["programme"].programme_id
        programme_service.add_duty(admin, old_id, {"code": "D1", "description": "Build"})
        programme_service.add_module(admin, old_id, {"title": "Coding", "stage": "Year 1"})
        newer = programme_service.new_version(admin, old_id, reason="IfATE revision")

        assert (newer.reference, newer.version, newer.supersedes_programme_id) == (
            "ST0119", "1.1", old_id,
        )
        assert [k.code for k in programme_service.list_ksbs(admin, newer.programme_id)] == [
            "K1", "S1", "B1",
        ]
        assert [d.code for d in programme_service.list_duties(admin, newer.programme_id)] == ["D1"]
        assert [m.title for m in programme_service.list_modules(admin, newer.programme_id)] == [
            "Coding",
        ]

    def test_the_old_version_is_superseded_and_the_new_one_active(self, cohort, admin):
        old_id = cohort["programme"].programme_id
        newer = programme_service.new_version(admin, old_id)
        assert programme_service.get_programme(admin, old_id).status == "Superseded"
        assert newer.status == "Active"

    def test_a_draft_stays_a_draft(self, db, admin):
        draft = programme_service.create_programme(admin, {
            "reference": "ST0500", "title": "Draft thing", "level": 3,
            "funding_band": 5, "duration_months": 12,
        })
        newer = programme_service.new_version(admin, draft.programme_id, version="2.0")
        assert (newer.status, newer.version) == ("Draft", "2.0")

    def test_existing_apprentices_keep_their_version_and_still_display(self, cohort, admin):
        old_id = cohort["programme"].programme_id
        programme_service.new_version(admin, old_id)
        summary = apprentice_service.get_apprentice(admin, cohort["apprentice_id"])
        assert summary.apprentice.programme_id == old_id
        assert (summary.programme_reference, summary.programme_title) == (
            "ST0119", "Software Developer",
        )

    def test_new_enrolments_are_offered_the_active_version_only(self, cohort, admin):
        old_id = cohort["programme"].programme_id
        newer = programme_service.new_version(admin, old_id)
        offered = programme_service.list_programmes(admin, active_only=True)
        assert [p.programme_id for p in offered] == [newer.programme_id]
        assert [p.programme_id for p in programme_service.enrolment_options(admin)] == [
            newer.programme_id,
        ]
        # Editing someone already on the old version keeps it on offer for them.
        kept = programme_service.enrolment_options(admin, keep_programme_id=old_id)
        assert {p.programme_id for p in kept} == {old_id, newer.programme_id}
        # Still in delivery, e.g. for the timetable.
        delivering = programme_service.list_programmes(admin, in_delivery=True)
        assert {p.programme_id for p in delivering} == {old_id, newer.programme_id}

    def test_a_superseded_version_cannot_be_reactivated(self, cohort, admin):
        old_id = cohort["programme"].programme_id
        programme_service.new_version(admin, old_id)
        with pytest.raises(ValidationError, match="superseded"):
            programme_service.activate_programme(admin, old_id)

    def test_only_the_latest_version_can_be_revised(self, cohort, admin):
        old_id = cohort["programme"].programme_id
        programme_service.new_version(admin, old_id)
        with pytest.raises(ValidationError):
            programme_service.new_version(admin, old_id)

    def test_the_version_number_must_move_forward(self, cohort, admin):
        with pytest.raises(ValidationError, match="after 1.0"):
            programme_service.new_version(admin, cohort["programme"].programme_id, version="0.9")

    def test_a_reference_is_added_once_and_then_revised(self, cohort, admin):
        with pytest.raises(ValidationError, match="New version"):
            programme_service.create_programme(admin, {
                "reference": "st0119", "title": "Again", "level": 4,
                "funding_band": 13, "duration_months": 24,
            })

    def test_the_history_lists_every_version_with_its_apprentices(self, cohort, admin):
        old_id = cohort["programme"].programme_id
        newer = programme_service.new_version(admin, old_id)
        history = programme_service.version_history(admin, newer.programme_id)
        assert [(h.programme.version, h.programme.status, h.apprentices) for h in history] == [
            ("1.0", "Superseded", 1), ("1.1", "Active", 0),
        ]
        assert [h.is_current for h in history] == [False, True]

    def test_a_superseded_version_with_nobody_left_can_be_withdrawn(self, db, admin):
        programme = programme_service.create_programme(admin, {
            "reference": "ST0600", "title": "Quiet", "level": 3,
            "funding_band": 5, "duration_months": 12, "epa_methods": ["Knowledge test"],
        })
        programme_service.add_ksb(admin, programme.programme_id, {"code": "K1", "description": "k"})
        programme_service.activate_programme(admin, programme.programme_id)
        programme_service.new_version(admin, programme.programme_id)
        withdrawn = programme_service.withdraw_programme(
            admin, programme.programme_id, reason="Nobody left on 1.0"
        )
        assert withdrawn.status == "Withdrawn"

    def test_only_programme_managers_cut_versions(self, cohort):
        with pytest.raises(PermissionError):
            programme_service.new_version(cohort["tutor"], cohort["programme"].programme_id)


# ═════════════════════════════════════════════════════════════════════
# The table rebuild
# ═════════════════════════════════════════════════════════════════════

_OLD_SCHEMA = """
CREATE TABLE programmes (
    programme_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference TEXT NOT NULL UNIQUE, title TEXT NOT NULL, level INTEGER NOT NULL,
    funding_band INTEGER NOT NULL, duration_months INTEGER NOT NULL, epa_methods TEXT,
    sector TEXT, description TEXT, status TEXT NOT NULL DEFAULT 'Draft',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE programme_ksbs (
    ksb_id INTEGER PRIMARY KEY AUTOINCREMENT, programme_id INTEGER NOT NULL,
    code TEXT NOT NULL, ksb_type TEXT NOT NULL, description TEXT NOT NULL, duty_ref TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE,
    UNIQUE (programme_id, code));
INSERT INTO programmes (reference, title, level, funding_band, duration_months,
                        epa_methods, status)
    VALUES ('ST0001', 'Legacy', 3, 5, 12, 'Knowledge test', 'Active');
INSERT INTO programme_ksbs (programme_id, code, ksb_type, description)
    VALUES (1, 'K1', 'Knowledge', 'Knows things');
"""


@pytest.fixture
def old_db(tmp_path, monkeypatch):
    """A database made before programmes had versions."""
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(_OLD_SCHEMA)
    conn.close()
    monkeypatch.setattr(schema, "DB_PATH", path)
    schema.reset_ready_flag()
    yield path
    schema.reset_ready_flag()


class TestRebuild:
    def test_an_old_database_keeps_every_row_and_gains_versions(self, old_db):
        schema.init_db()
        conn = sqlite3.connect(old_db)
        try:
            assert conn.execute(
                "SELECT reference, version, status FROM programmes"
            ).fetchall() == [("ST0001", "1.0", "Active")]
            assert conn.execute("SELECT COUNT(*) FROM programme_ksbs").fetchone()[0] == 1
            assert not migration.reference_is_unique_alone(conn)
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn.close()

    def test_after_the_rebuild_two_versions_share_a_reference(self, old_db):
        schema.init_db()
        admin = Actor(username="admin5", role="admin")
        newer = programme_service.new_version(admin, 1)
        assert (newer.reference, newer.version) == ("ST0001", "1.1")
        assert len(programme_service.list_ksbs(admin, newer.programme_id)) == 1

    def test_running_it_again_changes_nothing(self, old_db):
        schema.init_db()
        schema.reset_ready_flag()
        schema.init_db()
        conn = sqlite3.connect(old_db)
        try:
            assert conn.execute("SELECT COUNT(*) FROM programmes").fetchone()[0] == 1
        finally:
            conn.close()

    def test_the_rebuilt_table_matches_the_schema(self, db):
        with schema.connect() as conn:
            fresh = [r[1] for r in conn.execute("PRAGMA table_info(programmes)").fetchall()]
        scratch = sqlite3.connect(":memory:")
        try:
            scratch.execute(migration._PROGRAMMES_DDL)
            rebuilt = [
                r[1] for r in scratch.execute(
                    f"PRAGMA table_info({migration._TEMP_TABLE})"
                ).fetchall()
            ]
        finally:
            scratch.close()
        assert rebuilt == fresh
