"""
Comprehensive tests for the query_monitor module.

Tests QueryMetrics, QueryStats, QueryTimer, QueryMonitor,
and the global get_query_monitor / time_query functions.
"""

import time
import threading
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Suppress unrelated resource warnings
pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def monitor():
    """Create a fresh QueryMonitor."""
    from education_system.university_system.infrastructure.database.query_monitor import QueryMonitor
    return QueryMonitor(slow_threshold_ms=100.0, max_history=1000)


# ---------------------------------------------------------------------------
# Test QueryMetrics dataclass
# ---------------------------------------------------------------------------

class TestQueryMetrics:
    """Test the QueryMetrics dataclass."""

    def test_creation(self):
        """Test QueryMetrics creation with all fields."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryMetrics
        now = datetime.now()
        qm = QueryMetrics(
            query="SELECT * FROM users",
            duration_ms=50.0,
            timestamp=now,
            rows_affected=10,
            was_slow=False,
            params_hash="abc123",
        )
        assert qm.query == "SELECT * FROM users"
        assert qm.duration_ms == 50.0
        assert qm.timestamp == now
        assert qm.rows_affected == 10
        assert qm.was_slow is False
        assert qm.params_hash == "abc123"

    def test_defaults(self):
        """Test QueryMetrics default values."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryMetrics
        qm = QueryMetrics(query="SELECT 1", duration_ms=1.0, timestamp=datetime.now())
        assert qm.rows_affected == 0
        assert qm.was_slow is False
        assert qm.params_hash is None


# ---------------------------------------------------------------------------
# Test QueryStats dataclass
# ---------------------------------------------------------------------------

class TestQueryStats:
    """Test the QueryStats dataclass."""

    def test_creation(self):
        """Test QueryStats creation."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryStats
        qs = QueryStats(query_pattern="SELECT * FROM users WHERE id = ?")
        assert qs.query_pattern == "SELECT * FROM users WHERE id = ?"
        assert qs.total_executions == 0
        assert qs.total_time_ms == 0.0
        assert qs.min_time_ms == float('inf')
        assert qs.max_time_ms == 0.0
        assert qs.slow_count == 0
        assert qs.last_execution is None
        assert qs.execution_times == []

    def test_avg_time_ms_zero_executions(self):
        """Test avg_time_ms returns 0 when no executions."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryStats
        qs = QueryStats(query_pattern="test")
        assert qs.avg_time_ms == 0.0

    def test_avg_time_ms_calculated(self):
        """Test avg_time_ms is total/count."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryStats
        qs = QueryStats(query_pattern="test", total_executions=4, total_time_ms=200.0)
        assert qs.avg_time_ms == 50.0

    def test_slow_percentage_zero_executions(self):
        """Test slow_percentage returns 0 when no executions."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryStats
        qs = QueryStats(query_pattern="test")
        assert qs.slow_percentage == 0.0

    def test_slow_percentage_calculated(self):
        """Test slow_percentage is (slow/total)*100."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryStats
        qs = QueryStats(query_pattern="test", total_executions=10, slow_count=3)
        assert qs.slow_percentage == 30.0


# ---------------------------------------------------------------------------
# Test QueryTimer
# ---------------------------------------------------------------------------

class TestQueryTimer:
    """Test the QueryTimer context manager."""

    def test_measures_elapsed_time(self):
        """Test QueryTimer measures elapsed time."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        with QueryTimer("SELECT 1") as timer:
            time.sleep(0.01)
        assert timer.elapsed_ms > 0

    def test_slow_detection(self):
        """Test QueryTimer detects slow queries."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        # Very low threshold to guarantee slow detection
        with QueryTimer("SELECT 1", threshold_ms=0.001) as timer:
            time.sleep(0.01)
        assert timer.is_slow is True

    def test_fast_query_not_slow(self):
        """Test QueryTimer does not flag fast queries as slow."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        with QueryTimer("SELECT 1", threshold_ms=100000) as timer:
            pass  # Very fast
        assert timer.is_slow is False

    def test_default_threshold(self):
        """Test QueryTimer uses class-level default threshold."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        timer = QueryTimer("SELECT 1")
        assert timer.threshold_ms == QueryTimer.SLOW_QUERY_THRESHOLD_MS

    def test_custom_threshold(self):
        """Test QueryTimer accepts custom threshold."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        timer = QueryTimer("SELECT 1", threshold_ms=500.0)
        assert timer.threshold_ms == 500.0

    def test_does_not_suppress_exceptions(self):
        """Test QueryTimer does not suppress exceptions."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        with pytest.raises(ValueError, match="test"):
            with QueryTimer("SELECT 1"):
                raise ValueError("test")

    def test_records_to_monitor(self, monitor):
        """Test QueryTimer records to the provided monitor."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        with QueryTimer("SELECT * FROM t", monitor=monitor):
            pass
        stats = monitor.get_stats()
        assert stats['total_queries'] == 1

    def test_slow_query_logging(self):
        """Test slow query triggers logging."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        with patch('education_system.university_system.infrastructure.database.query_monitor.query_logger') as mock_logger:
            with QueryTimer("SELECT * FROM big_table", threshold_ms=0.001, log_slow=True):
                time.sleep(0.01)
            mock_logger.warning.assert_called()

    def test_no_logging_when_disabled(self):
        """Test no logging when log_slow=False."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        with patch('education_system.university_system.infrastructure.database.query_monitor.query_logger') as mock_logger:
            with QueryTimer("SELECT 1", threshold_ms=0.001, log_slow=False):
                time.sleep(0.01)
            mock_logger.warning.assert_not_called()

    def test_long_query_truncated_in_log(self):
        """Test that long queries are truncated in log messages."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryTimer
        long_query = "SELECT " + "x," * 200 + " FROM t"
        with patch('education_system.university_system.infrastructure.database.query_monitor.query_logger') as mock_logger:
            with QueryTimer(long_query, threshold_ms=0.001, log_slow=True):
                time.sleep(0.01)
            # The warning message should contain "..."
            call_args = mock_logger.warning.call_args[0][0]
            assert "..." in call_args


# ---------------------------------------------------------------------------
# Test QueryMonitor._normalize_query
# ---------------------------------------------------------------------------

class TestNormalizeQuery:
    """Test query normalization for pattern aggregation."""

    def test_replaces_numbers(self, monitor):
        """Test numbers are replaced with ?."""
        result = monitor._normalize_query("SELECT * FROM users WHERE id = 42")
        assert "42" not in result
        assert "?" in result

    def test_replaces_single_quoted_strings(self, monitor):
        """Test single-quoted strings are replaced."""
        result = monitor._normalize_query("SELECT * FROM users WHERE name = 'John'")
        assert "'John'" not in result
        assert "?" in result

    def test_replaces_double_quoted_strings(self, monitor):
        """Test double-quoted strings are replaced."""
        result = monitor._normalize_query('SELECT * FROM users WHERE name = "Jane"')
        assert '"Jane"' not in result
        assert "?" in result

    def test_normalizes_whitespace(self, monitor):
        """Test multiple spaces/newlines are collapsed."""
        result = monitor._normalize_query("SELECT  *\n  FROM   users")
        assert "\n" not in result
        assert "  " not in result

    def test_collapses_multiple_placeholders(self, monitor):
        """Test multiple ? are collapsed to single ?."""
        result = monitor._normalize_query("WHERE id IN (?, ?, ?)")
        # Should have at most individual ? separated by non-? chars
        assert "??" not in result


# ---------------------------------------------------------------------------
# Test QueryMonitor.record_query
# ---------------------------------------------------------------------------

class TestRecordQuery:
    """Test record_query method."""

    def test_records_query(self, monitor):
        """Test basic query recording."""
        monitor.record_query("SELECT * FROM users", 50.0)
        stats = monitor.get_stats()
        assert stats['total_queries'] == 1
        assert stats['total_time_ms'] == 50.0

    def test_slow_auto_detection(self, monitor):
        """Test slow query is auto-detected based on threshold."""
        monitor.record_query("SELECT * FROM big", 200.0)  # > 100ms threshold
        stats = monitor.get_stats()
        assert stats['slow_queries'] == 1

    def test_fast_not_marked_slow(self, monitor):
        """Test fast query is not marked slow."""
        monitor.record_query("SELECT 1", 5.0)
        stats = monitor.get_stats()
        assert stats['slow_queries'] == 0

    def test_manual_slow_override(self, monitor):
        """Test manual was_slow override."""
        monitor.record_query("SELECT 1", 5.0, was_slow=True)
        stats = monitor.get_stats()
        assert stats['slow_queries'] == 1

    def test_manual_not_slow_override(self, monitor):
        """Test manual was_slow=False override even for slow query."""
        monitor.record_query("SELECT * FROM big", 200.0, was_slow=False)
        stats = monitor.get_stats()
        assert stats['slow_queries'] == 0

    def test_rows_affected_tracked(self, monitor):
        """Test rows_affected is tracked in metrics."""
        monitor.record_query("UPDATE users SET name = ?", 10.0, rows_affected=5)
        slow = monitor.get_slow_queries()
        # Not slow so won't appear in slow queries, check history
        history = monitor._history
        assert history[-1].rows_affected == 5

    def test_history_size_limited(self):
        """Test history is capped at max_history."""
        from education_system.university_system.infrastructure.database.query_monitor import QueryMonitor
        m = QueryMonitor(max_history=50)
        for i in range(100):
            m.record_query(f"SELECT {i}", float(i))
        assert len(m._history) <= 50

    def test_pattern_stats_updated(self, monitor):
        """Test query pattern statistics are aggregated."""
        monitor.record_query("SELECT * FROM users WHERE id = 1", 10.0)
        monitor.record_query("SELECT * FROM users WHERE id = 2", 20.0)
        # Both should normalize to the same pattern
        query_stats = monitor.get_query_stats()
        # Should have at least one pattern
        assert len(query_stats) >= 1
        # The pattern should have 2 executions
        pattern = query_stats[0]
        assert pattern.total_executions == 2
        assert pattern.total_time_ms == 30.0

    def test_pattern_min_max_tracked(self, monitor):
        """Test min/max times are tracked per pattern."""
        monitor.record_query("SELECT * FROM t WHERE id = 1", 10.0)
        monitor.record_query("SELECT * FROM t WHERE id = 2", 50.0)
        monitor.record_query("SELECT * FROM t WHERE id = 3", 30.0)
        query_stats = monitor.get_query_stats()
        pattern = query_stats[0]
        assert pattern.min_time_ms == 10.0
        assert pattern.max_time_ms == 50.0

    def test_execution_times_capped_at_100(self, monitor):
        """Test execution_times list per pattern is capped at 100."""
        for i in range(150):
            monitor.record_query("SELECT * FROM t WHERE id = 1", float(i))
        query_stats = monitor.get_query_stats()
        assert len(query_stats[0].execution_times) <= 100


# ---------------------------------------------------------------------------
# Test QueryMonitor.get_slow_queries
# ---------------------------------------------------------------------------

class TestGetSlowQueries:
    """Test get_slow_queries method."""

    def test_returns_only_slow(self, monitor):
        """Test only slow queries are returned."""
        monitor.record_query("fast", 5.0)
        monitor.record_query("slow1", 150.0)
        monitor.record_query("slow2", 200.0)
        slow = monitor.get_slow_queries()
        assert len(slow) == 2
        assert all(q.was_slow for q in slow)

    def test_sorted_by_duration_desc(self, monitor):
        """Test slow queries are sorted by duration descending."""
        monitor.record_query("medium", 150.0)
        monitor.record_query("slowest", 500.0)
        monitor.record_query("slow", 200.0)
        slow = monitor.get_slow_queries()
        assert slow[0].duration_ms == 500.0
        assert slow[-1].duration_ms == 150.0

    def test_limit_parameter(self, monitor):
        """Test limit parameter limits results."""
        for i in range(10):
            monitor.record_query(f"slow{i}", 150.0 + i)
        slow = monitor.get_slow_queries(limit=3)
        assert len(slow) == 3

    def test_since_filter(self, monitor):
        """Test since parameter filters by time."""
        monitor.record_query("old_slow", 200.0)
        cutoff = datetime.now()
        time.sleep(0.01)
        monitor.record_query("new_slow", 300.0)
        slow = monitor.get_slow_queries(since=cutoff)
        assert len(slow) == 1
        assert slow[0].query == "new_slow"


# ---------------------------------------------------------------------------
# Test QueryMonitor.get_query_stats
# ---------------------------------------------------------------------------

class TestGetQueryStats:
    """Test get_query_stats method."""

    def test_returns_sorted_by_total_time(self, monitor):
        """Test stats are sorted by total time descending."""
        for _ in range(5):
            monitor.record_query("SELECT * FROM a", 10.0)
        for _ in range(3):
            monitor.record_query("SELECT * FROM b", 100.0)

        stats = monitor.get_query_stats()
        assert stats[0].total_time_ms >= stats[-1].total_time_ms

    def test_top_n_parameter(self, monitor):
        """Test top_n parameter limits results."""
        for i in range(20):
            monitor.record_query(f"query_{i}", float(i * 10))
        stats = monitor.get_query_stats(top_n=5)
        assert len(stats) <= 5


# ---------------------------------------------------------------------------
# Test QueryMonitor.get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    """Test get_stats method."""

    def test_returns_expected_keys(self, monitor):
        """Test get_stats returns expected keys."""
        stats = monitor.get_stats()
        expected_keys = [
            'total_queries', 'slow_queries', 'slow_percentage',
            'total_time_ms', 'avg_time_ms', 'unique_query_patterns',
            'history_size', 'slow_threshold_ms',
        ]
        for key in expected_keys:
            assert key in stats

    def test_avg_time_calculated(self, monitor):
        """Test average time is calculated correctly."""
        monitor.record_query("q1", 10.0)
        monitor.record_query("q2", 30.0)
        stats = monitor.get_stats()
        assert stats['avg_time_ms'] == 20.0

    def test_slow_percentage_calculated(self, monitor):
        """Test slow percentage is correct."""
        monitor.record_query("fast", 5.0)
        monitor.record_query("slow", 200.0)
        stats = monitor.get_stats()
        assert stats['slow_percentage'] == 50.0

    def test_zero_queries(self, monitor):
        """Test stats with zero queries."""
        stats = monitor.get_stats()
        assert stats['total_queries'] == 0
        assert stats['avg_time_ms'] == 0
        assert stats['slow_percentage'] == 0

    def test_threshold_reported(self, monitor):
        """Test slow threshold is reported in stats."""
        stats = monitor.get_stats()
        assert stats['slow_threshold_ms'] == 100.0


# ---------------------------------------------------------------------------
# Test QueryMonitor.get_percentile
# ---------------------------------------------------------------------------

class TestGetPercentile:
    """Test get_percentile method."""

    def test_empty_history(self, monitor):
        """Test percentile is 0 with empty history."""
        assert monitor.get_percentile(95.0) == 0.0

    def test_p50(self, monitor):
        """Test 50th percentile (median)."""
        for i in range(100):
            monitor.record_query(f"q{i}", float(i))
        p50 = monitor.get_percentile(50.0)
        assert p50 == 50.0

    def test_p95(self, monitor):
        """Test 95th percentile."""
        for i in range(100):
            monitor.record_query(f"q{i}", float(i))
        p95 = monitor.get_percentile(95.0)
        assert p95 == 95.0

    def test_p100(self, monitor):
        """Test 100th percentile (max)."""
        for i in range(100):
            monitor.record_query(f"q{i}", float(i))
        p100 = monitor.get_percentile(100.0)
        assert p100 == 99.0  # max value in range(100)

    def test_p0(self, monitor):
        """Test 0th percentile (min)."""
        for i in range(100):
            monitor.record_query(f"q{i}", float(i))
        p0 = monitor.get_percentile(0.0)
        assert p0 == 0.0


# ---------------------------------------------------------------------------
# Test QueryMonitor.reset
# ---------------------------------------------------------------------------

class TestReset:
    """Test reset method."""

    def test_clears_all_state(self, monitor):
        """Test reset clears all monitoring data."""
        monitor.record_query("q1", 10.0)
        monitor.record_query("q2", 200.0)

        monitor.reset()

        stats = monitor.get_stats()
        assert stats['total_queries'] == 0
        assert stats['slow_queries'] == 0
        assert stats['total_time_ms'] == 0.0
        assert stats['unique_query_patterns'] == 0
        assert stats['history_size'] == 0


# ---------------------------------------------------------------------------
# Test QueryMonitor.time_query
# ---------------------------------------------------------------------------

class TestTimeQuery:
    """Test time_query context manager on QueryMonitor."""

    def test_times_and_records_query(self, monitor):
        """Test time_query records the query to the monitor."""
        with monitor.time_query("SELECT * FROM test") as timer:
            time.sleep(0.01)

        assert timer.elapsed_ms > 0
        stats = monitor.get_stats()
        assert stats['total_queries'] == 1

    def test_custom_threshold(self, monitor):
        """Test time_query with custom threshold."""
        with monitor.time_query("SELECT 1", threshold_ms=0.001) as timer:
            time.sleep(0.01)
        assert timer.is_slow is True

    def test_does_not_suppress_exceptions(self, monitor):
        """Test time_query does not suppress exceptions."""
        with pytest.raises(RuntimeError):
            with monitor.time_query("SELECT 1"):
                raise RuntimeError("test")


# ---------------------------------------------------------------------------
# Test thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """Test thread safety of QueryMonitor."""

    def test_concurrent_record_query(self, monitor):
        """Test concurrent record_query calls."""
        errors = []

        def worker():
            try:
                for i in range(100):
                    monitor.record_query(f"SELECT {i}", float(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = monitor.get_stats()
        assert stats['total_queries'] == 1000

    def test_concurrent_mixed_operations(self, monitor):
        """Test concurrent mixed operations (record, stats, slow queries)."""
        errors = []

        def record_worker():
            try:
                for i in range(50):
                    monitor.record_query(f"q{i}", float(i * 5))
            except Exception as e:
                errors.append(e)

        def read_worker():
            try:
                for _ in range(50):
                    monitor.get_stats()
                    monitor.get_slow_queries()
                    monitor.get_percentile(95.0)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=record_worker))
            threads.append(threading.Thread(target=read_worker))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Test global get_query_monitor
# ---------------------------------------------------------------------------

class TestGetQueryMonitor:
    """Test the global get_query_monitor factory."""

    def test_returns_monitor(self):
        """Test get_query_monitor returns a QueryMonitor."""
        import education_system.university_system.infrastructure.database.query_monitor as mod
        old = mod._query_monitor
        mod._query_monitor = None
        try:
            m = mod.get_query_monitor(slow_threshold_ms=200.0)
            assert isinstance(m, mod.QueryMonitor)
            assert m.slow_threshold_ms == 200.0
        finally:
            mod._query_monitor = old

    def test_singleton(self):
        """Test get_query_monitor returns the same instance."""
        import education_system.university_system.infrastructure.database.query_monitor as mod
        old = mod._query_monitor
        mod._query_monitor = None
        try:
            m1 = mod.get_query_monitor()
            m2 = mod.get_query_monitor()
            assert m1 is m2
        finally:
            mod._query_monitor = old


# ---------------------------------------------------------------------------
# Test global time_query function
# ---------------------------------------------------------------------------

class TestGlobalTimeQuery:
    """Test the module-level time_query convenience function."""

    def test_returns_query_timer(self):
        """Test time_query returns a QueryTimer instance."""
        import education_system.university_system.infrastructure.database.query_monitor as mod
        old = mod._query_monitor
        mod._query_monitor = None
        try:
            timer = mod.time_query("SELECT 1")
            assert isinstance(timer, mod.QueryTimer)
            assert timer.query == "SELECT 1"
        finally:
            mod._query_monitor = old

    def test_custom_threshold(self):
        """Test time_query with custom threshold."""
        import education_system.university_system.infrastructure.database.query_monitor as mod
        old = mod._query_monitor
        mod._query_monitor = None
        try:
            timer = mod.time_query("SELECT 1", threshold_ms=500.0)
            assert timer.threshold_ms == 500.0
        finally:
            mod._query_monitor = old

    def test_uses_global_monitor(self):
        """Test time_query uses the global monitor."""
        import education_system.university_system.infrastructure.database.query_monitor as mod
        old = mod._query_monitor
        mod._query_monitor = None
        try:
            timer = mod.time_query("SELECT 1")
            assert timer.monitor is not None
            assert timer.monitor is mod.get_query_monitor()
        finally:
            mod._query_monitor = old


# ---------------------------------------------------------------------------
# Test __all__ exports
# ---------------------------------------------------------------------------

class TestModuleExports:
    """Test module __all__ exports."""

    def test_all_is_list(self):
        """Test __all__ is a list."""
        from education_system.university_system.infrastructure.database.query_monitor import __all__
        assert isinstance(__all__, list)

    def test_all_contains_expected(self):
        """Test __all__ has all expected names."""
        from education_system.university_system.infrastructure.database.query_monitor import __all__
        expected = [
            'QueryTimer', 'QueryMonitor', 'QueryMetrics',
            'QueryStats', 'get_query_monitor', 'time_query',
        ]
        for name in expected:
            assert name in __all__

    def test_all_names_accessible(self):
        """Test all names in __all__ are accessible."""
        import education_system.university_system.infrastructure.database.query_monitor as mod
        for name in mod.__all__:
            assert hasattr(mod, name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
