"""Tests for OfflineSyncService."""

import json
import time

import pytest

from education_system.shared.offline.sync_service import OfflineSyncService


@pytest.fixture
def svc(tmp_path):
    db = str(tmp_path / "offline_sync.db")
    return OfflineSyncService(db_path=db)


# ── cache_set / cache_get roundtrip ──────────────────────────────────

class TestCacheOperations:
    def test_set_and_get(self, svc):
        data = {"name": "Alice", "score": 95}
        svc.cache_set("student:1", data, "secondary", "student")
        result = svc.cache_get("student:1")
        assert result == data

    def test_get_missing_key_returns_none(self, svc):
        assert svc.cache_get("nonexistent") is None

    def test_overwrite_existing_key(self, svc):
        svc.cache_set("key1", {"v": 1}, "primary", "student")
        svc.cache_set("key1", {"v": 2}, "primary", "student")
        assert svc.cache_get("key1") == {"v": 2}

    def test_expired_cache_returns_none(self, svc):
        # Set with 1-second TTL, then wait for expiry
        svc.cache_set("expiring", {"x": 1}, "sixth_form", "grade", ttl_seconds=1)
        time.sleep(1.5)
        assert svc.cache_get("expiring") is None

    def test_cache_invalidate_by_key(self, svc):
        svc.cache_set("k1", {"a": 1}, "primary", "student")
        svc.cache_set("k2", {"b": 2}, "primary", "student")
        svc.cache_invalidate(cache_key="k1")
        assert svc.cache_get("k1") is None
        assert svc.cache_get("k2") is not None

    def test_cache_invalidate_by_system(self, svc):
        svc.cache_set("s1", {"a": 1}, "primary", "student")
        svc.cache_set("s2", {"b": 2}, "secondary", "student")
        svc.cache_invalidate(system_key="primary")
        assert svc.cache_get("s1") is None
        assert svc.cache_get("s2") is not None

    def test_cache_invalidate_all(self, svc):
        svc.cache_set("x1", {"a": 1}, "primary", "student")
        svc.cache_set("x2", {"b": 2}, "secondary", "grade")
        svc.cache_invalidate()
        assert svc.cache_get("x1") is None
        assert svc.cache_get("x2") is None


# ── mutation queue ───────────────────────────────────────────────────

class TestMutationQueue:
    def test_queue_and_retrieve(self, svc):
        mid = svc.queue_mutation(
            "create", "student", "secondary",
            {"name": "Bob", "year": 8}, entity_id="SEC0001",
        )
        assert isinstance(mid, int)

        pending = svc.get_pending_mutations()
        assert len(pending) == 1
        assert pending[0]["operation"] == "create"
        assert pending[0]["entity_type"] == "student"
        assert json.loads(pending[0]["payload"]) == {"name": "Bob", "year": 8}

    def test_filter_by_system(self, svc):
        svc.queue_mutation("create", "student", "primary", {"n": 1})
        svc.queue_mutation("update", "grade", "secondary", {"n": 2})

        primary_only = svc.get_pending_mutations(system_key="primary")
        assert len(primary_only) == 1
        assert primary_only[0]["system_key"] == "primary"

    def test_mark_synced(self, svc):
        mid = svc.queue_mutation("create", "student", "sixth_form", {"n": 1})
        svc.mark_synced(mid)

        pending = svc.get_pending_mutations()
        assert len(pending) == 0

    def test_mark_failed(self, svc):
        mid = svc.queue_mutation("update", "grade", "university", {"n": 1})
        svc.mark_failed(mid, "Connection refused")

        pending = svc.get_pending_mutations()
        assert len(pending) == 0  # failed is no longer pending

        status = svc.get_sync_status()
        assert status["failed"] == 1

    def test_mark_conflict(self, svc):
        mid = svc.queue_mutation("update", "student", "secondary", {"n": 1})
        svc.mark_conflict(mid, "Version mismatch")

        status = svc.get_sync_status()
        assert status["conflicts"] == 1


# ── sync state ───────────────────────────────────────────────────────

class TestSyncState:
    def test_no_state_returns_none(self, svc):
        assert svc.get_sync_state("primary", "student") is None

    def test_update_and_get(self, svc):
        svc.update_sync_state("secondary", "grade", sync_token="tok-123")
        state = svc.get_sync_state("secondary", "grade")
        assert state is not None
        assert state["last_sync_token"] == "tok-123"
        assert state["last_sync_at"] is not None

    def test_overwrite_state(self, svc):
        svc.update_sync_state("sixth_form", "student", sync_token="a")
        svc.update_sync_state("sixth_form", "student", sync_token="b")
        state = svc.get_sync_state("sixth_form", "student")
        assert state["last_sync_token"] == "b"


# ── get_sync_status ──────────────────────────────────────────────────

class TestSyncStatus:
    def test_empty_status(self, svc):
        status = svc.get_sync_status()
        assert status["pending_mutations"] == 0
        assert status["conflicts"] == 0
        assert status["failed"] == 0
        assert status["cached_items"] == 0

    def test_status_reflects_data(self, svc):
        svc.queue_mutation("create", "student", "primary", {"n": 1})
        svc.cache_set("c1", {"v": 1}, "primary", "student")

        status = svc.get_sync_status()
        assert status["pending_mutations"] == 1
        assert status["cached_items"] == 1


# ── cleanup_expired_cache ────────────────────────────────────────────

class TestCleanupExpiredCache:
    def test_cleanup_removes_expired(self, svc, tmp_path):
        """Insert a cache row with an already-past expires_at, then clean up."""
        import sqlite3 as _sqlite3
        svc.cache_set("fresh", {"x": 1}, "primary", "student", ttl_seconds=3600)
        # Directly insert a row that is already expired (past timestamp)
        conn = _sqlite3.connect(str(tmp_path / "offline_sync.db"))
        conn.execute(
            "INSERT OR REPLACE INTO sync_cache "
            "(cache_key, data, system_key, entity_type, expires_at) "
            "VALUES ('stale', '{\"y\":2}', 'primary', 'student', '2000-01-01T00:00:00')"
        )
        conn.commit()
        conn.close()

        removed = svc.cleanup_expired_cache()
        assert removed >= 1
        assert svc.cache_get("fresh") is not None
        assert svc.cache_get("stale") is None

    def test_cleanup_with_nothing_expired(self, svc):
        svc.cache_set("ok", {"z": 3}, "secondary", "grade", ttl_seconds=3600)
        removed = svc.cleanup_expired_cache()
        assert removed == 0
