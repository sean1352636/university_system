"""Tests for the calendar core: schema migration, CRUD, the archive
and the read filters — especially the multi-day overlap semantics,
which every view, feed and export sits on."""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)


# ── Migration ──────────────────────────────────────────────────────

class TestMigration:

    _ORIGINAL = """
        CREATE TABLE calendar_events (
            event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            title         TEXT NOT NULL,
            event_type    TEXT NOT NULL DEFAULT 'Meeting',
            description   TEXT,
            start_date    TEXT NOT NULL,
            end_date      TEXT NOT NULL,
            start_time    TEXT,
            end_time      TEXT,
            all_day       INTEGER NOT NULL DEFAULT 0,
            location      TEXT,
            organiser     TEXT,
            audience      TEXT NOT NULL DEFAULT 'All',
            status        TEXT NOT NULL DEFAULT 'Scheduled',
            capacity      INTEGER,
            rsvp_required INTEGER NOT NULL DEFAULT 0,
            cost          REAL,
            notes         TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO calendar_events (title, start_date, end_date)
        VALUES ('Legacy row', '2026-09-01', '2026-09-01');
    """

    def test_existing_table_gains_the_new_columns(self, tmp_path,
                                                  monkeypatch):
        db = str(tmp_path / "old.db")
        conn = sqlite3.connect(db)
        conn.executescript(self._ORIGINAL)
        conn.close()
        monkeypatch.setattr(core, "DB_PATH", db)
        monkeypatch.setattr(core, "_DB_READY", False)
        core.init_db()
        cols = {r[1] for r in sqlite3.connect(db).execute(
            "PRAGMA table_info(calendar_events)")}
        assert {"department", "visibility", "created_by",
                "updated_by", "deleted_at"} <= cols

    def test_legacy_rows_survive_with_defaults(self, tmp_path,
                                               monkeypatch):
        db = str(tmp_path / "old.db")
        conn = sqlite3.connect(db)
        conn.executescript(self._ORIGINAL)
        conn.close()
        monkeypatch.setattr(core, "DB_PATH", db)
        monkeypatch.setattr(core, "_DB_READY", False)
        core.init_db()
        rows = core.list_events()
        assert len(rows) == 1
        assert rows[0].title == "Legacy row"
        assert rows[0].visibility == core.DEFAULT_VISIBILITY

    def test_migration_is_idempotent(self, tmp_path, monkeypatch):
        db = str(tmp_path / "old.db")
        conn = sqlite3.connect(db)
        conn.executescript(self._ORIGINAL)
        conn.close()
        monkeypatch.setattr(core, "DB_PATH", db)
        for _ in range(2):
            monkeypatch.setattr(core, "_DB_READY", False)
            core.init_db()          # second pass must not blow up


# ── CRUD ───────────────────────────────────────────────────────────

class TestCrud:

    def test_create_stamps_the_actor(self, one_event):
        assert one_event.created_by == "jsmith"
        assert one_event.updated_by == "jsmith"

    def test_update_restamps_only_updated_by(self, one_event):
        after = core.update_event(one_event.event_id,
                                  {"location": "Gym"},
                                  actor="head")
        assert after.created_by == "jsmith"
        assert after.updated_by == "head"

    def test_bad_visibility_is_rejected(self, caldb):
        with pytest.raises(core.ValidationError, match="Visibility"):
            core.create_event({"title": "x",
                               "start_date": "2026-09-01",
                               "visibility": "Sneaky"})

    def test_end_before_start_is_rejected(self, caldb):
        with pytest.raises(core.ValidationError,
                           match="before start"):
            core.create_event({"title": "x",
                               "start_date": "2026-09-02",
                               "end_date": "2026-09-01"})


# ── Archive ────────────────────────────────────────────────────────

class TestArchive:

    def test_delete_is_soft(self, one_event):
        assert core.delete_event(one_event.event_id) is True
        assert core.list_events() == []
        got = core.get_event(one_event.event_id)
        assert got is not None and got.is_deleted

    def test_archived_events_leave_every_read(self, one_event):
        core.delete_event(one_event.event_id)
        assert core.events_on(one_event.start_date) == []
        assert core.list_events(include_deleted=True) != []

    def test_restore_brings_it_back(self, one_event):
        core.delete_event(one_event.event_id)
        assert core.restore_event(one_event.event_id) is True
        assert len(core.list_events()) == 1

    def test_double_archive_reports_false(self, one_event):
        assert core.delete_event(one_event.event_id) is True
        assert core.delete_event(one_event.event_id) is False

    def test_purge_is_final(self, one_event):
        assert core.purge_event(one_event.event_id) is True
        assert core.get_event(one_event.event_id) is None
        assert core.list_events(include_deleted=True) == []

    def test_summary_counts_the_archive(self, one_event):
        core.delete_event(one_event.event_id)
        summ = core.summary()
        assert summ.total == 0
        assert summ.archived == 1


# ── Filters and overlap ────────────────────────────────────────────

class TestFilters:

    @pytest.fixture
    def spanning(self, caldb):
        """A three-day residential: the overlap edge cases live on
        multi-day rows."""
        return core.create_event({
            "title": "Residential", "event_type": "Trip",
            "start_date": "2026-10-05", "end_date": "2026-10-07",
            "all_day": True,
        })

    def test_overlap_catches_a_window_inside_the_event(self, spanning):
        rows = core.list_events(date_from="2026-10-06",
                                date_to="2026-10-06")
        assert [e.event_id for e in rows] == [spanning.event_id]

    def test_overlap_catches_a_window_straddling_the_start(
            self, spanning):
        rows = core.list_events(date_from="2026-10-01",
                                date_to="2026-10-05")
        assert len(rows) == 1

    def test_overlap_misses_an_adjacent_window(self, spanning):
        assert core.list_events(date_from="2026-10-08",
                                date_to="2026-10-31") == []

    def test_strict_mode_filters_on_start_date_only(self, spanning):
        rows = core.list_events(date_from="2026-10-06",
                                date_to="2026-10-09",
                                overlapping=False)
        assert rows == []

    def test_events_on_covers_every_day_of_a_span(self, spanning):
        for day in ("2026-10-05", "2026-10-06", "2026-10-07"):
            assert len(core.events_on(day)) == 1
        assert core.events_on("2026-10-08") == []

    def test_events_in_week_uses_monday_to_sunday(self, spanning):
        # 2026-10-05 is a Monday; anchoring on the Sunday before
        # must miss it, anchoring on any weekday must catch it.
        assert core.events_in_week("2026-10-04") == []
        assert len(core.events_in_week("2026-10-09")) == 1

    def test_text_like_searches_notes_and_description(self, caldb):
        core.create_event({"title": "Plain", "start_date": "2026-09-01",
                           "notes": "bring wellies"})
        assert len(core.list_events(text_like="wellies")) == 1
        assert core.list_events(title_like="wellies") == []

    def test_department_filter(self, caldb):
        core.create_event({"title": "x", "start_date": "2026-09-01",
                           "department": "Science"})
        assert len(core.list_events(department="Science")) == 1
        assert core.list_events(department="Maths") == []

    def test_limit(self, caldb):
        for i in range(5):
            core.create_event({"title": f"e{i}",
                               "start_date": "2026-09-01"})
        assert len(core.list_events(limit=3)) == 3
