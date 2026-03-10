"""
Comprehensive tests for the pool_metrics module.

Tests PoolMetrics, ConnectionEvent, PoolMetricsCollector, and
the global get_pool_metrics factory.
"""

import threading
import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

# Suppress unrelated resource warnings
pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def collector():
    """Create a fresh PoolMetricsCollector."""
    from education_system.university_system.infrastructure.database.pool_metrics import PoolMetricsCollector
    c = PoolMetricsCollector(pool_max_size=10, pool_min_size=2, history_size=100)
    yield c


# ---------------------------------------------------------------------------
# Test PoolMetrics dataclass
# ---------------------------------------------------------------------------

class TestPoolMetrics:
    """Test the PoolMetrics dataclass."""

    def test_default_values(self):
        """Test PoolMetrics has correct default values."""
        from education_system.university_system.infrastructure.database.pool_metrics import PoolMetrics
        pm = PoolMetrics()
        assert pm.total_connections == 0
        assert pm.active_connections == 0
        assert pm.idle_connections == 0
        assert pm.wait_count == 0
        assert pm.avg_wait_time_ms == 0.0
        assert pm.max_wait_time_ms == 0.0
        assert pm.connections_created == 0
        assert pm.connections_closed == 0
        assert pm.connection_errors == 0
        assert pm.pool_exhausted_count == 0
        assert isinstance(pm.timestamp, datetime)

    def test_custom_values(self):
        """Test PoolMetrics with custom values."""
        from education_system.university_system.infrastructure.database.pool_metrics import PoolMetrics
        pm = PoolMetrics(
            total_connections=5,
            active_connections=3,
            idle_connections=2,
            wait_count=1,
            avg_wait_time_ms=10.5,
        )
        assert pm.total_connections == 5
        assert pm.active_connections == 3
        assert pm.idle_connections == 2
        assert pm.wait_count == 1
        assert pm.avg_wait_time_ms == 10.5


# ---------------------------------------------------------------------------
# Test ConnectionEvent dataclass
# ---------------------------------------------------------------------------

class TestConnectionEvent:
    """Test the ConnectionEvent dataclass."""

    def test_creation(self):
        """Test ConnectionEvent creation."""
        from education_system.university_system.infrastructure.database.pool_metrics import ConnectionEvent
        now = datetime.now()
        event = ConnectionEvent(
            timestamp=now,
            event_type='acquire',
            wait_time_ms=5.0,
            connection_id=1,
            details='test',
        )
        assert event.timestamp == now
        assert event.event_type == 'acquire'
        assert event.wait_time_ms == 5.0
        assert event.connection_id == 1
        assert event.details == 'test'

    def test_defaults(self):
        """Test ConnectionEvent default values."""
        from education_system.university_system.infrastructure.database.pool_metrics import ConnectionEvent
        event = ConnectionEvent(timestamp=datetime.now(), event_type='release')
        assert event.wait_time_ms == 0.0
        assert event.connection_id is None
        assert event.details is None


# ---------------------------------------------------------------------------
# Test PoolMetricsCollector initialization
# ---------------------------------------------------------------------------

class TestCollectorInit:
    """Test PoolMetricsCollector initialization."""

    def test_default_init(self):
        """Test collector initializes with defaults."""
        from education_system.university_system.infrastructure.database.pool_metrics import PoolMetricsCollector
        c = PoolMetricsCollector()
        assert c.pool_max_size == 10
        assert c.pool_min_size == 2
        assert c.history_size == 1000

    def test_custom_init(self):
        """Test collector initializes with custom values."""
        from education_system.university_system.infrastructure.database.pool_metrics import PoolMetricsCollector
        c = PoolMetricsCollector(pool_max_size=50, pool_min_size=5, history_size=500)
        assert c.pool_max_size == 50
        assert c.pool_min_size == 5
        assert c.history_size == 500


# ---------------------------------------------------------------------------
# Test record_acquire
# ---------------------------------------------------------------------------

class TestRecordAcquire:
    """Test record_acquire method."""

    def test_increments_active_connections(self, collector):
        """Test that recording acquire increments active connections."""
        collector.record_acquire(wait_time_ms=5.0)
        metrics = collector.get_metrics()
        assert metrics.active_connections == 1

    def test_tracks_wait_time(self, collector):
        """Test that wait time is tracked."""
        collector.record_acquire(wait_time_ms=10.0)
        collector.record_acquire(wait_time_ms=20.0)
        metrics = collector.get_metrics()
        assert metrics.avg_wait_time_ms == 15.0
        assert metrics.max_wait_time_ms == 20.0

    def test_adds_event(self, collector):
        """Test that acquire event is added to history."""
        collector.record_acquire(wait_time_ms=5.0, connection_id=42)
        events = collector.get_recent_events(event_type='acquire')
        assert len(events) == 1
        assert events[0].event_type == 'acquire'
        assert events[0].connection_id == 42

    def test_multiple_acquires(self, collector):
        """Test multiple acquire operations."""
        for i in range(5):
            collector.record_acquire(wait_time_ms=float(i))
        metrics = collector.get_metrics()
        assert metrics.active_connections == 5

    def test_wait_times_capped_at_1000(self, collector):
        """Test wait_times list is capped at 1000 entries."""
        for i in range(1100):
            collector.record_acquire(wait_time_ms=float(i))
        assert len(collector._wait_times) <= 1000


# ---------------------------------------------------------------------------
# Test record_release
# ---------------------------------------------------------------------------

class TestRecordRelease:
    """Test record_release method."""

    def test_decrements_active_connections(self, collector):
        """Test that release decrements active connections."""
        collector.record_acquire()
        collector.record_acquire()
        collector.record_release()
        metrics = collector.get_metrics()
        assert metrics.active_connections == 1

    def test_does_not_go_below_zero(self, collector):
        """Test active connections cannot go below zero."""
        collector.record_release()
        metrics = collector.get_metrics()
        assert metrics.active_connections == 0

    def test_adds_release_event(self, collector):
        """Test release event is recorded."""
        collector.record_release(connection_id=7)
        events = collector.get_recent_events(event_type='release')
        assert len(events) == 1
        assert events[0].connection_id == 7


# ---------------------------------------------------------------------------
# Test record_create
# ---------------------------------------------------------------------------

class TestRecordCreate:
    """Test record_create method."""

    def test_increments_total_connections(self, collector):
        """Test create increments total connections."""
        collector.record_create()
        metrics = collector.get_metrics()
        assert metrics.total_connections == 1
        assert metrics.connections_created == 1

    def test_returns_connection_id(self, collector):
        """Test create returns an assigned connection ID."""
        cid = collector.record_create()
        assert cid >= 1

    def test_auto_increment_ids(self, collector):
        """Test auto-incremented IDs are unique and increasing."""
        id1 = collector.record_create()
        id2 = collector.record_create()
        assert id2 > id1

    def test_custom_connection_id(self, collector):
        """Test providing a custom connection ID."""
        cid = collector.record_create(connection_id=999)
        assert cid == 999


# ---------------------------------------------------------------------------
# Test record_close
# ---------------------------------------------------------------------------

class TestRecordClose:
    """Test record_close method."""

    def test_decrements_total_connections(self, collector):
        """Test close decrements total connections."""
        collector.record_create()
        collector.record_create()
        collector.record_close()
        metrics = collector.get_metrics()
        assert metrics.total_connections == 1
        assert metrics.connections_closed == 1

    def test_does_not_go_below_zero(self, collector):
        """Test total connections cannot go below zero on close."""
        collector.record_close()
        metrics = collector.get_metrics()
        assert metrics.total_connections == 0

    def test_adds_close_event(self, collector):
        """Test close event is recorded."""
        collector.record_close(connection_id=5)
        events = collector.get_recent_events(event_type='close')
        assert len(events) == 1


# ---------------------------------------------------------------------------
# Test record_error
# ---------------------------------------------------------------------------

class TestRecordError:
    """Test record_error method."""

    def test_increments_error_count(self, collector):
        """Test error recording increments error count."""
        collector.record_error(details="connection failed")
        metrics = collector.get_metrics()
        assert metrics.connection_errors == 1

    def test_stores_details(self, collector):
        """Test error event stores details."""
        collector.record_error(details="timeout", connection_id=3)
        events = collector.get_recent_events(event_type='error')
        assert len(events) == 1
        assert events[0].details == "timeout"
        assert events[0].connection_id == 3


# ---------------------------------------------------------------------------
# Test record_timeout
# ---------------------------------------------------------------------------

class TestRecordTimeout:
    """Test record_timeout method."""

    def test_increments_timeout_and_exhausted(self, collector):
        """Test timeout increments both counters."""
        collector.record_timeout(wait_time_ms=5000.0)
        metrics = collector.get_metrics()
        assert metrics.pool_exhausted_count == 1
        stats = collector.get_stats()
        assert stats['cumulative']['total_timeouts'] == 1

    def test_adds_timeout_event(self, collector):
        """Test timeout event is recorded."""
        collector.record_timeout(wait_time_ms=3000.0)
        events = collector.get_recent_events(event_type='timeout')
        assert len(events) == 1
        assert events[0].wait_time_ms == 3000.0


# ---------------------------------------------------------------------------
# Test record_waiter_start / record_waiter_end
# ---------------------------------------------------------------------------

class TestWaiters:
    """Test waiter tracking methods."""

    def test_waiter_start(self, collector):
        """Test waiter start increments counter."""
        collector.record_waiter_start()
        metrics = collector.get_metrics()
        assert metrics.wait_count == 1

    def test_waiter_end(self, collector):
        """Test waiter end decrements counter."""
        collector.record_waiter_start()
        collector.record_waiter_start()
        collector.record_waiter_end()
        metrics = collector.get_metrics()
        assert metrics.wait_count == 1

    def test_waiter_end_does_not_go_below_zero(self, collector):
        """Test waiter end cannot go below zero."""
        collector.record_waiter_end()
        metrics = collector.get_metrics()
        assert metrics.wait_count == 0


# ---------------------------------------------------------------------------
# Test get_metrics
# ---------------------------------------------------------------------------

class TestGetMetrics:
    """Test get_metrics method."""

    def test_returns_pool_metrics_instance(self, collector):
        """Test get_metrics returns a PoolMetrics."""
        from education_system.university_system.infrastructure.database.pool_metrics import PoolMetrics
        metrics = collector.get_metrics()
        assert isinstance(metrics, PoolMetrics)

    def test_idle_connections_calculated(self, collector):
        """Test idle = total - active."""
        collector.record_create()
        collector.record_create()
        collector.record_acquire()
        metrics = collector.get_metrics()
        assert metrics.idle_connections == metrics.total_connections - metrics.active_connections

    def test_avg_wait_time_with_no_data(self, collector):
        """Test avg wait time is 0 with no data."""
        metrics = collector.get_metrics()
        assert metrics.avg_wait_time_ms == 0.0

    def test_max_wait_time_with_no_data(self, collector):
        """Test max wait time is 0 with no data."""
        metrics = collector.get_metrics()
        assert metrics.max_wait_time_ms == 0.0


# ---------------------------------------------------------------------------
# Test get_utilization
# ---------------------------------------------------------------------------

class TestGetUtilization:
    """Test get_utilization method."""

    def test_zero_when_empty(self, collector):
        """Test utilization is 0% when no active connections."""
        assert collector.get_utilization() == 0.0

    def test_correct_percentage(self, collector):
        """Test utilization percentage is calculated correctly."""
        # pool_max_size=10, acquire 5 -> 50%
        for _ in range(5):
            collector.record_acquire()
        assert collector.get_utilization() == 50.0

    def test_full_utilization(self, collector):
        """Test 100% utilization."""
        for _ in range(10):
            collector.record_acquire()
        assert collector.get_utilization() == 100.0

    def test_zero_max_size(self):
        """Test utilization is 0 when max_size is 0."""
        from education_system.university_system.infrastructure.database.pool_metrics import PoolMetricsCollector
        c = PoolMetricsCollector(pool_max_size=0)
        assert c.get_utilization() == 0.0


# ---------------------------------------------------------------------------
# Test get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    """Test get_stats method."""

    def test_returns_expected_structure(self, collector):
        """Test get_stats returns expected keys."""
        stats = collector.get_stats()
        assert 'current' in stats
        assert 'cumulative' in stats
        assert 'wait_times' in stats
        assert 'config' in stats

    def test_current_section(self, collector):
        """Test current section has expected keys."""
        stats = collector.get_stats()
        current = stats['current']
        assert 'total_connections' in current
        assert 'active_connections' in current
        assert 'idle_connections' in current
        assert 'waiting_threads' in current
        assert 'utilization_percent' in current

    def test_cumulative_section(self, collector):
        """Test cumulative section tracks totals."""
        collector.record_acquire()
        collector.record_release()
        collector.record_create()
        collector.record_close()
        collector.record_error()
        collector.record_timeout()

        stats = collector.get_stats()
        cumul = stats['cumulative']
        assert cumul['total_acquires'] == 1
        assert cumul['total_releases'] == 1
        assert cumul['total_creates'] == 1
        assert cumul['total_closes'] == 1
        assert cumul['total_errors'] == 1
        assert cumul['total_timeouts'] == 1

    def test_wait_time_percentiles(self, collector):
        """Test wait time percentiles are calculated."""
        for i in range(100):
            collector.record_acquire(wait_time_ms=float(i))

        stats = collector.get_stats()
        wt = stats['wait_times']
        assert 'p50_ms' in wt
        assert 'p95_ms' in wt
        assert 'p99_ms' in wt
        assert wt['p50_ms'] == 50.0  # Median of 0..99
        assert wt['p95_ms'] == 95.0

    def test_wait_time_percentiles_empty(self, collector):
        """Test percentiles are 0 when no data."""
        stats = collector.get_stats()
        wt = stats['wait_times']
        assert wt['p50_ms'] == 0.0
        assert wt['p95_ms'] == 0.0
        assert wt['p99_ms'] == 0.0

    def test_config_section(self, collector):
        """Test config section has pool size info."""
        stats = collector.get_stats()
        assert stats['config']['max_size'] == 10
        assert stats['config']['min_size'] == 2


# ---------------------------------------------------------------------------
# Test get_recent_events
# ---------------------------------------------------------------------------

class TestGetRecentEvents:
    """Test get_recent_events method."""

    def test_returns_all_events(self, collector):
        """Test all events are returned without filter."""
        collector.record_acquire()
        collector.record_release()
        collector.record_create()
        events = collector.get_recent_events()
        assert len(events) == 3

    def test_filter_by_event_type(self, collector):
        """Test filtering events by type."""
        collector.record_acquire()
        collector.record_release()
        collector.record_acquire()
        events = collector.get_recent_events(event_type='acquire')
        assert len(events) == 2
        assert all(e.event_type == 'acquire' for e in events)

    def test_limit_events(self, collector):
        """Test limiting the number of events returned."""
        for _ in range(20):
            collector.record_acquire()
        events = collector.get_recent_events(limit=5)
        assert len(events) == 5

    def test_returns_most_recent(self, collector):
        """Test that most recent events are returned."""
        for i in range(10):
            collector.record_acquire(wait_time_ms=float(i))
        events = collector.get_recent_events(limit=3)
        # Should be the last 3
        assert events[-1].wait_time_ms == 9.0


# ---------------------------------------------------------------------------
# Test event history size limit
# ---------------------------------------------------------------------------

class TestEventHistoryLimit:
    """Test event history is capped at history_size."""

    def test_history_capped(self):
        """Test events are trimmed to history_size."""
        from education_system.university_system.infrastructure.database.pool_metrics import PoolMetricsCollector
        c = PoolMetricsCollector(history_size=50)
        for _ in range(100):
            c.record_acquire()
        events = c.get_recent_events()
        assert len(events) <= 50


# ---------------------------------------------------------------------------
# Test take_snapshot
# ---------------------------------------------------------------------------

class TestTakeSnapshot:
    """Test take_snapshot method."""

    def test_returns_pool_metrics(self, collector):
        """Test take_snapshot returns PoolMetrics."""
        from education_system.university_system.infrastructure.database.pool_metrics import PoolMetrics
        snapshot = collector.take_snapshot()
        assert isinstance(snapshot, PoolMetrics)

    def test_snapshot_stored_in_history(self, collector):
        """Test snapshot is added to metrics history."""
        collector.take_snapshot()
        collector.take_snapshot()
        history = collector.get_metrics_history()
        assert len(history) == 2

    def test_snapshot_history_capped(self, collector):
        """Test metrics history is capped at 1440."""
        for _ in range(1500):
            collector.take_snapshot()
        history = collector.get_metrics_history()
        assert len(history) <= 1440


# ---------------------------------------------------------------------------
# Test get_metrics_history
# ---------------------------------------------------------------------------

class TestGetMetricsHistory:
    """Test get_metrics_history method."""

    def test_returns_all_snapshots(self, collector):
        """Test returns all stored snapshots."""
        for _ in range(5):
            collector.take_snapshot()
        history = collector.get_metrics_history()
        assert len(history) == 5

    def test_filter_by_since(self, collector):
        """Test filtering by time."""
        collector.take_snapshot()
        cutoff = datetime.now()
        time.sleep(0.01)
        collector.take_snapshot()
        history = collector.get_metrics_history(since=cutoff)
        assert len(history) == 1

    def test_limit_results(self, collector):
        """Test limiting history results."""
        for _ in range(10):
            collector.take_snapshot()
        history = collector.get_metrics_history(limit=3)
        assert len(history) == 3


# ---------------------------------------------------------------------------
# Test reset
# ---------------------------------------------------------------------------

class TestReset:
    """Test reset method."""

    def test_resets_all_counters(self, collector):
        """Test reset clears all state."""
        collector.record_acquire(wait_time_ms=10.0)
        collector.record_create()
        collector.record_error()
        collector.record_timeout()
        collector.record_waiter_start()
        collector.take_snapshot()

        collector.reset()

        metrics = collector.get_metrics()
        assert metrics.active_connections == 0
        assert metrics.total_connections == 0
        assert metrics.connections_created == 0
        assert metrics.connection_errors == 0
        assert metrics.pool_exhausted_count == 0
        assert metrics.avg_wait_time_ms == 0.0
        assert metrics.wait_count == 0

        assert len(collector.get_recent_events()) == 0
        assert len(collector.get_metrics_history()) == 0


# ---------------------------------------------------------------------------
# Test thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """Test thread safety of PoolMetricsCollector."""

    def test_concurrent_operations(self, collector):
        """Test concurrent acquire/release operations."""
        errors = []

        def worker():
            try:
                for _ in range(100):
                    collector.record_acquire(wait_time_ms=1.0)
                    collector.record_release()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All should be released (net zero active)
        metrics = collector.get_metrics()
        assert metrics.active_connections == 0


# ---------------------------------------------------------------------------
# Test global get_pool_metrics
# ---------------------------------------------------------------------------

class TestGetPoolMetrics:
    """Test the global get_pool_metrics factory."""

    def test_returns_collector(self):
        """Test get_pool_metrics returns a PoolMetricsCollector."""
        import education_system.university_system.infrastructure.database.pool_metrics as mod
        old = mod._pool_metrics
        mod._pool_metrics = None
        try:
            collector = mod.get_pool_metrics(pool_max_size=20, pool_min_size=3)
            assert isinstance(collector, mod.PoolMetricsCollector)
            assert collector.pool_max_size == 20
        finally:
            mod._pool_metrics = old

    def test_singleton(self):
        """Test get_pool_metrics returns the same instance."""
        import education_system.university_system.infrastructure.database.pool_metrics as mod
        old = mod._pool_metrics
        mod._pool_metrics = None
        try:
            c1 = mod.get_pool_metrics()
            c2 = mod.get_pool_metrics()
            assert c1 is c2
        finally:
            mod._pool_metrics = old


# ---------------------------------------------------------------------------
# Test __all__ exports
# ---------------------------------------------------------------------------

class TestModuleExports:
    """Test module __all__ exports."""

    def test_all_is_list(self):
        """Test __all__ is a list."""
        from education_system.university_system.infrastructure.database.pool_metrics import __all__
        assert isinstance(__all__, list)

    def test_all_contains_expected(self):
        """Test __all__ has all expected names."""
        from education_system.university_system.infrastructure.database.pool_metrics import __all__
        expected = ['PoolMetrics', 'PoolMetricsCollector', 'ConnectionEvent', 'get_pool_metrics']
        for name in expected:
            assert name in __all__

    def test_all_names_accessible(self):
        """Test all names in __all__ are accessible."""
        import education_system.university_system.infrastructure.database.pool_metrics as mod
        for name in mod.__all__:
            assert hasattr(mod, name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
