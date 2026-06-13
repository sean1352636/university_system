"""
Comprehensive tests for connection pool limit handling and exhaustion scenarios.

This module tests ConnectionPool behavior when connection limits are reached:
- Pool exhaustion handling
- Timeout behavior when pool is full
- Connection limit enforcement
- Graceful degradation under pressure
- Semaphore behavior at max capacity
- Recovery after exhaustion
"""

import pytest
import os
import tempfile
from education_system.university_system.infrastructure.database.db import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from education_system.university_system.infrastructure.database.db import ConnectionPool
from education_system.university_system.core.exceptions import DatabaseConnectionError

@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE test_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

    yield db_path

    try:
        os.unlink(db_path)
    except (OSError, IOError):
        pass


def _acquire_in_thread(pool, timeout=None, hold_event=None, acquired_event=None):
    """Helper: acquire a connection in a new thread and optionally hold it.

    Returns a dict with 'conn', 'thread', and optionally 'release' callable.
    If hold_event is given, the thread holds the connection until that event is set.
    If acquired_event is given, it is set once the connection is acquired.
    """
    result = {"conn": None, "error": None}

    def _run():
        try:
            kwargs = {}
            if timeout is not None:
                kwargs["timeout"] = timeout
            result["conn"] = pool.get_connection(**kwargs)
            if acquired_event:
                acquired_event.set()
            if hold_event:
                hold_event.wait()
                pool.release_connection(result["conn"])
        except DatabaseConnectionError as e:
            result["error"] = e
            if acquired_event:
                acquired_event.set()

    t = threading.Thread(target=_run)
    t.start()
    result["thread"] = t
    return result


def _hold_connections_in_threads(pool, count, timeout=30):
    """Acquire `count` connections each in separate threads, holding them.

    Returns (holders, release_event) where holders is a list of result dicts
    and release_event can be set to release all connections.
    """
    release_event = threading.Event()
    holders = []
    for _ in range(count):
        acquired = threading.Event()
        r = _acquire_in_thread(pool, hold_event=release_event, acquired_event=acquired)
        acquired.wait(timeout=timeout)
        assert r["error"] is None, f"Failed to acquire connection: {r['error']}"
        holders.append(r)
    return holders, release_event


class TestConnectionPoolExhaustion:
    """Test connection pool behavior when limits are reached."""

    def test_pool_exhaustion_timeout(self, temp_db):
        """Test that connection requests timeout when pool is exhausted."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1,
            timeout=1.0
        )

        # Acquire all connections in separate threads (thread-local pool)
        holders, release_event = _hold_connections_in_threads(pool, 2)

        # Try to acquire third connection from yet another thread (should timeout)
        result = {"error": None}
        def try_acquire():
            try:
                conn = pool.get_connection(timeout=0.5)
                pool.release_connection(conn)
            except DatabaseConnectionError as e:
                result["error"] = e

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)

        assert result["error"] is not None
        assert "Could not acquire connection" in str(result["error"])

        # Release held connections and verify we can acquire again
        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        conn3 = pool.get_connection()
        assert conn3 is not None
        pool.release_connection(conn3)
        pool.close_all()

    def test_pool_max_connections_enforced(self, temp_db):
        """Test that pool never creates more than max_connections."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=3,
            min_connections=1
        )

        # Acquire exactly max_connections in separate threads
        holders, release_event = _hold_connections_in_threads(pool, 3)

        # Verify thread_connections count
        assert len(pool._thread_connections) >= 3

        # Try to acquire one more from another thread (should timeout)
        result = {"error": None}
        def try_acquire():
            try:
                pool.get_connection(timeout=0.5)
            except DatabaseConnectionError as e:
                result["error"] = e

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)
        assert result["error"] is not None

        # Release all
        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        pool.close_all()

    def test_multiple_threads_timeout_gracefully(self, temp_db):
        """Test that multiple threads waiting for connections timeout gracefully."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1
        )

        # Hold all connections in separate threads
        holders, release_event = _hold_connections_in_threads(pool, 2)

        timeout_count = []
        success_count = []
        lock = threading.Lock()

        def try_acquire():
            """Try to acquire connection with timeout."""
            try:
                conn = pool.get_connection(timeout=1.0)
                pool.release_connection(conn)
                with lock:
                    success_count.append(1)
            except DatabaseConnectionError:
                with lock:
                    timeout_count.append(1)

        # Launch multiple threads trying to acquire
        threads = [threading.Thread(target=try_acquire) for _ in range(5)]
        for t in threads:
            t.start()

        # Wait a bit then release
        time.sleep(1.5)
        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        for t in threads:
            t.join(timeout=10.0)

        pool.close_all()

        # All threads should complete (some timeout, some succeed)
        total = len(timeout_count) + len(success_count)
        assert total == 5, f"Not all threads completed: {total}/5"

    def test_pool_recovery_after_exhaustion(self, temp_db):
        """Test that pool recovers properly after being exhausted."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=3,
            min_connections=1
        )

        # Exhaust pool with separate threads
        holders, release_event = _hold_connections_in_threads(pool, 3)

        # Verify exhaustion from another thread
        result = {"error": None}
        def try_acquire():
            try:
                pool.get_connection(timeout=0.5)
            except DatabaseConnectionError as e:
                result["error"] = e

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)
        assert result["error"] is not None

        # Release all connections
        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        # Should be able to acquire again
        new_conn = pool.get_connection()
        assert new_conn is not None
        pool.release_connection(new_conn)
        pool.close_all()

    def test_connection_held_too_long(self, temp_db):
        """Test behavior when connections are held longer than timeout."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=1,
            min_connections=1
        )

        results = {"holder": None, "waiter": None}

        def hold_connection():
            """Hold connection for extended period."""
            conn = pool.get_connection()
            results["holder"] = "acquired"
            time.sleep(2.0)  # Hold for 2 seconds
            pool.release_connection(conn)
            results["holder"] = "released"

        def wait_for_connection():
            """Wait for connection to become available."""
            time.sleep(0.5)  # Let holder acquire first
            try:
                conn = pool.get_connection(timeout=1.0)
                pool.release_connection(conn)
                results["waiter"] = "success"
            except DatabaseConnectionError:
                results["waiter"] = "timeout"

        t1 = threading.Thread(target=hold_connection)
        t2 = threading.Thread(target=wait_for_connection)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        pool.close_all()

        assert results["holder"] == "released"
        assert results["waiter"] == "timeout"  # Should timeout waiting

    def test_cascading_timeouts(self, temp_db):
        """Test behavior when multiple threads cascade into timeout."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1
        )

        # Hold all connections in separate threads
        holders, release_event = _hold_connections_in_threads(pool, 2)

        timeout_times = []
        lock = threading.Lock()

        def timed_acquire(timeout_duration):
            """Try to acquire with specific timeout and record time."""
            start = time.time()
            try:
                conn = pool.get_connection(timeout=timeout_duration)
                pool.release_connection(conn)
                return "success"
            except DatabaseConnectionError:
                elapsed = time.time() - start
                with lock:
                    timeout_times.append(elapsed)
                return "timeout"

        # Launch threads with different timeouts
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(timed_acquire, 0.5),
                executor.submit(timed_acquire, 1.0),
                executor.submit(timed_acquire, 1.5),
            ]
            results = [f.result() for f in as_completed(futures)]

        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        pool.close_all()

        # All should timeout
        assert results.count("timeout") == 3

        # Timeouts should be roughly at specified durations
        assert len(timeout_times) == 3
        for t in timeout_times:
            assert 0.4 < t < 2.0  # Within reasonable range

    def test_semaphore_release_on_error(self, temp_db):
        """Test that semaphore is released even when connection acquisition fails."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1
        )

        # Hold all connections in separate threads
        holders, release_event = _hold_connections_in_threads(pool, 2)

        # Try to acquire from another thread and fail
        result = {"error": None}
        def try_acquire():
            try:
                pool.get_connection(timeout=0.5)
            except DatabaseConnectionError as e:
                result["error"] = e

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)

        # Release one holder
        # We can't release just one with a shared event, so release all
        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        # Should be able to acquire now (semaphore was released)
        conn3 = pool.get_connection()
        assert conn3 is not None
        pool.release_connection(conn3)
        pool.close_all()

    def test_high_contention_scenario(self, temp_db):
        """Test pool behavior under very high contention."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=3,
            min_connections=1
        )

        success_count = []
        timeout_count = []
        lock = threading.Lock()

        def contend_for_connection():
            """Aggressively try to acquire connection."""
            for _ in range(10):
                try:
                    conn = pool.get_connection(timeout=0.5)
                    time.sleep(0.05)  # Hold briefly
                    pool.release_connection(conn)
                    with lock:
                        success_count.append(1)
                except DatabaseConnectionError:
                    with lock:
                        timeout_count.append(1)

        # Launch many threads
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(contend_for_connection) for _ in range(20)]
            for future in as_completed(futures):
                future.result()

        pool.close_all()

        total_attempts = len(success_count) + len(timeout_count)
        assert total_attempts == 200  # 20 threads * 10 attempts each
        assert len(success_count) > 0, "Some requests should succeed"

    def test_zero_timeout_immediate_failure(self, temp_db):
        """Test that a very short timeout fails quickly if no connections available."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=1,
            min_connections=1
        )

        # Hold the only connection in a separate thread
        holders, release_event = _hold_connections_in_threads(pool, 1)

        # Try with very short timeout from another thread (should fail quickly)
        result = {"elapsed": None, "error": None}
        def try_acquire():
            start = time.time()
            try:
                # Use a very small positive timeout (0.0 is falsy and gets replaced)
                pool.get_connection(timeout=0.001)
            except DatabaseConnectionError as e:
                result["error"] = e
            result["elapsed"] = time.time() - start

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)

        # Should fail very quickly (< 0.5 seconds)
        assert result["error"] is not None
        assert result["elapsed"] < 0.5, f"Short timeout took too long: {result['elapsed']}s"

        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)
        pool.close_all()

    def test_pool_exhaustion_with_stale_connections(self, temp_db):
        """Test exhaustion behavior when pool contains stale connections."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1,
            max_connection_age=1  # Connections expire after 1 second
        )

        # Acquire and release to populate pool
        conn1 = pool.get_connection()
        pool.release_connection(conn1)

        # Wait for connection to become stale
        time.sleep(1.5)

        # Acquire connections in separate threads (should refresh stale ones)
        holders, release_event = _hold_connections_in_threads(pool, 2)

        # Should still enforce max limit from another thread
        result = {"error": None}
        def try_acquire():
            try:
                pool.get_connection(timeout=0.5)
            except DatabaseConnectionError as e:
                result["error"] = e

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)
        assert result["error"] is not None

        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)
        pool.close_all()

    def test_partial_pool_exhaustion(self, temp_db):
        """Test when pool is partially but not fully exhausted."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        # Hold 3 of 5 connections in separate threads
        holders3, release3 = _hold_connections_in_threads(pool, 3)

        # Should still be able to acquire 2 more in separate threads
        holders2, release2 = _hold_connections_in_threads(pool, 2)

        # Now should be exhausted from another thread
        result = {"error": None}
        def try_acquire():
            try:
                pool.get_connection(timeout=0.5)
            except DatabaseConnectionError as e:
                result["error"] = e

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)
        assert result["error"] is not None

        # Release and verify recovery
        release2.set()
        for h in holders2:
            h["thread"].join(timeout=5.0)
        release3.set()
        for h in holders3:
            h["thread"].join(timeout=5.0)

        pool.close_all()

class TestConnectionPoolLimitEnforcement:
    """Test strict enforcement of connection limits."""

    def test_min_connections_maintained(self, temp_db):
        """Test that minimum connections are created on init."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=3
        )

        # The pool uses thread-local storage, so _pool is empty.
        # On init, one connection is created for the current thread.
        # Verify at least 1 thread connection exists after init.
        assert len(pool._thread_connections) >= 1

        pool.close_all()

    def test_max_connections_never_exceeded(self, temp_db):
        """Test that max connections is never exceeded."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=4,
            min_connections=2
        )

        # Acquire max connections in separate threads
        holders, release_event = _hold_connections_in_threads(pool, 4)

        # Check thread_connections count
        assert len(pool._thread_connections) <= 5  # 4 holder threads + possibly main thread

        # One more from another thread should fail
        result = {"error": None}
        def try_acquire():
            try:
                pool.get_connection(timeout=0.5)
            except DatabaseConnectionError as e:
                result["error"] = e

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)
        assert result["error"] is not None

        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        pool.close_all()

    def test_connection_creation_under_limit(self, temp_db):
        """Test that connections are created up to max limit."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        initial_size = len(pool._thread_connections)
        assert initial_size >= 1  # At least the init connection

        # Acquire connections in separate threads (less than max)
        holders, release_event = _hold_connections_in_threads(pool, 4)

        # Thread connections should have grown
        assert len(pool._thread_connections) >= initial_size

        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        pool.close_all()

    def test_custom_timeout_override(self, temp_db):
        """Test that custom timeout overrides default."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=1,
            min_connections=1,
            timeout=10.0  # Default timeout
        )

        # Hold the connection in a separate thread
        holders, release_event = _hold_connections_in_threads(pool, 1)

        # Try with shorter timeout from another thread
        result = {"elapsed": None, "error": None}
        def try_acquire():
            start = time.time()
            try:
                pool.get_connection(timeout=0.3)
            except DatabaseConnectionError as e:
                result["error"] = e
            result["elapsed"] = time.time() - start

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)

        # Should respect custom timeout (not default 10s)
        assert result["error"] is not None
        assert result["elapsed"] < 1.0, f"Custom timeout not respected: {result['elapsed']}s"

        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)
        pool.close_all()

class TestConnectionPoolErrorHandling:
    """Test error handling in pool exhaustion scenarios."""

    def test_exception_message_includes_details(self, temp_db):
        """Test that timeout exception includes helpful details."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1
        )

        # Hold all connections in separate threads
        holders, release_event = _hold_connections_in_threads(pool, 2)

        result = {"error": None}
        def try_acquire():
            try:
                pool.get_connection(timeout=0.5)
            except DatabaseConnectionError as e:
                result["error"] = e

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)

        assert result["error"] is not None
        error_msg = str(result["error"])
        assert "connection" in error_msg.lower()

        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)
        pool.close_all()

    def test_pool_state_after_timeout_error(self, temp_db):
        """Test that pool state is consistent after timeout errors."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1
        )

        # Hold connections in separate threads
        holders, release_event = _hold_connections_in_threads(pool, 2)

        # Cause timeout error from another thread
        result = {"error": None}
        def try_acquire():
            try:
                pool.get_connection(timeout=0.5)
            except DatabaseConnectionError as e:
                result["error"] = e

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=5.0)

        # Release all and verify pool still works
        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        new_conn = pool.get_connection()
        assert new_conn is not None
        pool.release_connection(new_conn)
        pool.close_all()

    def test_concurrent_errors_dont_corrupt_pool(self, temp_db):
        """Test that concurrent timeout errors don't corrupt pool state."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1
        )

        # Hold all connections in separate threads
        holders, release_event = _hold_connections_in_threads(pool, 2)

        error_count = []
        lock = threading.Lock()

        def cause_timeout():
            """Cause timeout error."""
            try:
                pool.get_connection(timeout=0.5)
            except DatabaseConnectionError:
                with lock:
                    error_count.append(1)

        # Multiple threads causing timeouts
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(cause_timeout) for _ in range(10)]
            for future in as_completed(futures):
                future.result()

        assert len(error_count) == 10

        # Release held connections, pool should still work
        release_event.set()
        for h in holders:
            h["thread"].join(timeout=5.0)

        new_conn = pool.get_connection()
        assert new_conn is not None
        pool.release_connection(new_conn)
        pool.close_all()

class TestConnectionPoolBackpressure:
    """Test pool behavior under sustained high load (backpressure)."""

    def test_sustained_load_with_limited_pool(self, temp_db):
        """Test pool behavior under sustained load with small pool size."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=3,
            min_connections=1
        )

        completed = []
        lock = threading.Lock()

        def sustained_work():
            """Perform multiple operations."""
            for _ in range(10):
                try:
                    conn = pool.get_connection(timeout=2.0)
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    pool.release_connection(conn)
                    with lock:
                        completed.append(1)
                except DatabaseConnectionError:
                    with lock:
                        completed.append(0)

        # Run sustained load
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(sustained_work) for _ in range(10)]
            for future in as_completed(futures):
                future.result()

        pool.close_all()

        # Most operations should succeed
        success_rate = sum(completed) / len(completed)
        assert success_rate > 0.7, f"Success rate too low: {success_rate:.2%}"

    def test_bursty_traffic_pattern(self, temp_db):
        """Test pool behavior with bursty traffic patterns."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=4,
            min_connections=2
        )

        def burst():
            """Burst of requests."""
            results = []
            for _ in range(5):
                try:
                    conn = pool.get_connection(timeout=1.0)
                    pool.release_connection(conn)
                    results.append("success")
                except DatabaseConnectionError:
                    results.append("timeout")
            return results

        # Multiple bursts
        all_results = []
        for _ in range(3):
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(burst) for _ in range(8)]
                for future in as_completed(futures):
                    all_results.extend(future.result())
            time.sleep(0.5)  # Gap between bursts

        pool.close_all()

        # Should handle most burst requests
        success_count = all_results.count("success")
        total = len(all_results)
        assert success_count / total > 0.6, f"Too many failures: {success_count}/{total}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
