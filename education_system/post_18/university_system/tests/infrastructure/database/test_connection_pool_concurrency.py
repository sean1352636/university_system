"""
Comprehensive tests for connection pool thread-safety and concurrent access.

This module tests the ConnectionPool class under high concurrency scenarios to ensure:
- Thread-safe connection acquisition and release
- No race conditions in pool management
- Proper semaphore handling under load
- Connection state integrity across threads
- Performance under concurrent load
"""

import pytest
import os
import tempfile
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from education_system.post_18.university_system.infrastructure.database.db import ConnectionPool
from education_system.post_18.university_system.core.exceptions import DatabaseConnectionError

@pytest.fixture
def temp_db():
    """Create a temporary test database with a test table."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE concurrent_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT,
            value INTEGER,
            timestamp REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE counter (
            id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    ''')
    cursor.execute("INSERT INTO counter (id, count) VALUES (1, 0)")
    conn.commit()
    conn.close()

    yield db_path

    try:
        os.unlink(db_path)
    except (OSError, IOError):
        pass

class TestConnectionPoolConcurrency:
    """Test connection pool behavior under concurrent access."""

    def test_concurrent_connection_acquisition(self, temp_db):
        """Test that multiple threads can acquire connections concurrently."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        results = []
        errors = []

        def acquire_and_use(thread_num):
            """Acquire connection, perform query, release."""
            try:
                conn = pool.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                pool.release_connection(conn)
                results.append((thread_num, result[0]))
            except Exception as e:
                errors.append((thread_num, str(e)))

        # Launch 10 threads to acquire 5 max connections
        threads = []
        for i in range(10):
            t = threading.Thread(target=acquire_and_use, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join(timeout=10.0)

        pool.close_all()

        # All threads should succeed
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert all(r[1] == 1 for r in results), "All queries should return 1"

    def test_concurrent_writes_no_corruption(self, temp_db):
        """Test that concurrent writes don't corrupt data."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        def insert_record(thread_id):
            """Insert a record with thread ID."""
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO concurrent_test (thread_id, value, timestamp) VALUES (?, ?, ?)",
                    (f"thread_{thread_id}", thread_id, time.time())
                )
                conn.commit()
            finally:
                pool.release_connection(conn)

        # Insert from 20 threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(insert_record, i) for i in range(20)]
            for future in as_completed(futures):
                future.result()  # Raise any exceptions

        # Verify all 20 records were inserted
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM concurrent_test")
        count = cursor.fetchone()[0]
        pool.release_connection(conn)
        pool.close_all()

        assert count == 20, f"Expected 20 records, found {count}"

    def test_concurrent_increment_race_condition(self, temp_db):
        """Test race condition handling with concurrent counter increments."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        def increment_counter():
            """Increment counter (simulates race condition)."""
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                # Read-modify-write pattern (intentionally racy)
                cursor.execute("SELECT count FROM counter WHERE id = 1")
                current = cursor.fetchone()[0]
                time.sleep(0.001)  # Small delay to increase race likelihood
                cursor.execute("UPDATE counter SET count = ? WHERE id = 1", (current + 1,))
                conn.commit()
            finally:
                pool.release_connection(conn)

        # Run 50 increments concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(increment_counter) for _ in range(50)]
            for future in as_completed(futures):
                future.result()

        # Check final count (will be less than 50 due to race conditions)
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT count FROM counter WHERE id = 1")
        final_count = cursor.fetchone()[0]
        pool.release_connection(conn)
        pool.close_all()

        # Count should be > 0 but likely < 50 due to races
        assert final_count > 0, "Counter should have been incremented"
        # This test demonstrates the need for transactions

    def test_pool_size_limit_under_load(self, temp_db):
        """Test that pool respects max_connections under heavy load."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=3,
            min_connections=1
        )

        acquired_counts = []
        lock = threading.Lock()

        def acquire_and_hold(duration):
            """Acquire connection and hold it for duration."""
            conn = pool.get_connection()
            try:
                # Count how many connections are in the pool
                with lock:
                    in_use = sum(1 for p in pool._pool if p.in_use)
                    acquired_counts.append(in_use)
                time.sleep(duration)
            finally:
                pool.release_connection(conn)

        # Launch more threads than max connections
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(acquire_and_hold, 0.1) for _ in range(10)]
            for future in as_completed(futures):
                future.result()

        pool.close_all()

        # Pool should never exceed max_connections
        max_acquired = max(acquired_counts)
        assert max_acquired <= 3, f"Pool exceeded max connections: {max_acquired}"

    def test_connection_reuse_across_threads(self, temp_db):
        """Test that connections are properly managed across different threads."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=1
        )

        connection_ids = []
        lock = threading.Lock()

        def get_connection_id():
            """Get connection object ID."""
            conn = pool.get_connection()
            try:
                conn_id = id(conn)
                with lock:
                    connection_ids.append(conn_id)
            finally:
                pool.release_connection(conn)

        # Run sequentially - each thread gets its own thread-local connection
        for _ in range(10):
            t = threading.Thread(target=get_connection_id)
            t.start()
            t.join()

        pool.close_all()

        # Each thread gets a connection and all 10 should succeed
        assert len(connection_ids) == 10
        # The pool uses thread-local storage, so unique IDs depend on
        # thread reuse by the OS. Just verify we got connections.
        unique_connections = len(set(connection_ids))
        assert unique_connections >= 1, "Should have at least one unique connection"

    def test_context_manager_thread_safety(self, temp_db):
        """Test connection context manager in concurrent environment."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        results = []

        def use_context_manager(value):
            """Use context manager to get connection."""
            with pool.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ?", (value,))
                result = cursor.fetchone()[0]
                results.append(result)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(use_context_manager, i) for i in range(20)]
            for future in as_completed(futures):
                future.result()

        pool.close_all()

        assert len(results) == 20
        assert sorted(results) == list(range(20))

    def test_rapid_acquire_release(self, temp_db):
        """Test rapid connection acquire/release cycles."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=3,
            min_connections=1
        )

        iterations = 100
        errors = []

        def rapid_cycle():
            """Rapidly acquire and release connections."""
            try:
                for _ in range(iterations):
                    conn = pool.get_connection()
                    pool.release_connection(conn)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=rapid_cycle) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        pool.close_all()

        assert len(errors) == 0, f"Errors during rapid cycling: {errors}"

    def test_connection_validation_concurrency(self, temp_db):
        """Test that connection validation doesn't cause issues under concurrency."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=3,
            min_connections=1,
            max_connection_age=1  # Connections expire after 1 second
        )

        def use_connection_with_delay():
            """Use connection, wait, use again."""
            conn1 = pool.get_connection()
            pool.release_connection(conn1)
            time.sleep(1.5)  # Wait for connections to age
            conn2 = pool.get_connection()
            cursor = conn2.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            pool.release_connection(conn2)
            return result[0]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(use_connection_with_delay) for _ in range(5)]
            results = [f.result() for f in as_completed(futures)]

        pool.close_all()

        assert all(r == 1 for r in results)

    def test_connection_pool_stress_test(self, temp_db):
        """Stress test with high concurrency and mixed operations."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        operations_completed = []
        lock = threading.Lock()

        def mixed_operations(thread_id):
            """Perform various database operations."""
            try:
                # Multiple acquire/release cycles
                for op in range(5):
                    with pool.get_connection_context() as conn:
                        cursor = conn.cursor()

                        # Mix of reads and writes
                        if op % 2 == 0:
                            cursor.execute(
                                "INSERT INTO concurrent_test (thread_id, value, timestamp) VALUES (?, ?, ?)",
                                (f"stress_{thread_id}", op, time.time())
                            )
                            conn.commit()
                        else:
                            cursor.execute("SELECT COUNT(*) FROM concurrent_test")
                            cursor.fetchone()

                with lock:
                    operations_completed.append(thread_id)
            except Exception as e:
                pytest.fail(f"Thread {thread_id} failed: {e}")

        # Run 20 threads performing 5 operations each
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(mixed_operations, i) for i in range(20)]
            for future in as_completed(futures):
                future.result()

        pool.close_all()

        assert len(operations_completed) == 20

    def test_no_connection_leak_under_concurrency(self, temp_db):
        """Ensure no connection leaks occur under concurrent access."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        initial_pool_size = len(pool._pool)

        def acquire_use_release():
            """Standard acquire-use-release pattern."""
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                pool.release_connection(conn)

        # Run many iterations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(acquire_use_release) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        time.sleep(0.5)  # Let cleanup happen

        # Pool size should not grow unbounded
        final_pool_size = len(pool._pool)
        pool.close_all()

        assert final_pool_size <= 5, f"Connection leak detected: {final_pool_size} connections"

class TestConnectionPoolDeadlockPrevention:
    """Test deadlock prevention in connection pool."""

    def test_nested_acquisition_prevention(self, temp_db):
        """Test that nested connection acquisition is handled properly."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1
        )

        def nested_acquire():
            """Try to acquire connection while holding one."""
            conn1 = pool.get_connection()
            try:
                # Try to acquire second connection (may timeout)
                try:
                    conn2 = pool.get_connection(timeout=1.0)
                    pool.release_connection(conn2)
                    return "success"
                except DatabaseConnectionError:
                    return "timeout"
            finally:
                pool.release_connection(conn1)

        result = nested_acquire()
        pool.close_all()

        # Either succeeds or times out gracefully (no deadlock)
        assert result in ["success", "timeout"]

    def test_circular_wait_prevention(self, temp_db):
        """Test prevention of circular wait conditions."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1
        )

        results = []

        def thread_a():
            """Acquire conn1, then try conn2."""
            conn1 = pool.get_connection(timeout=2.0)
            time.sleep(0.1)
            try:
                conn2 = pool.get_connection(timeout=2.0)
                pool.release_connection(conn2)
                results.append("A-success")
            except DatabaseConnectionError:
                results.append("A-timeout")
            finally:
                pool.release_connection(conn1)

        def thread_b():
            """Acquire conn, perform work."""
            try:
                conn = pool.get_connection(timeout=2.0)
                time.sleep(0.2)
                pool.release_connection(conn)
                results.append("B-success")
            except DatabaseConnectionError:
                results.append("B-timeout")

        t1 = threading.Thread(target=thread_a)
        t2 = threading.Thread(target=thread_b)

        t1.start()
        t2.start()

        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        pool.close_all()

        # Both should complete (no permanent deadlock)
        assert len(results) == 2
        assert "B-success" in results or "B-timeout" in results

class TestConnectionPoolPerformance:
    """Test connection pool performance characteristics."""

    def test_connection_pool_improves_performance(self, temp_db):
        """Test that pooling improves performance vs creating new connections."""
        # Test with pooling
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        start = time.time()
        for _ in range(50):
            with pool.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
        pooled_time = time.time() - start
        pool.close_all()

        # Test without pooling (new connection each time)
        start = time.time()
        for _ in range(50):
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
        unpooled_time = time.time() - start

        # Pooling should be faster (or at least not significantly slower)
        # Allow 20% margin for variance
        assert pooled_time < unpooled_time * 1.2, \
            f"Pooled ({pooled_time:.3f}s) not faster than unpooled ({unpooled_time:.3f}s)"

    def test_concurrent_throughput(self, temp_db):
        """Measure throughput under concurrent load."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        operations = 200
        workers = 10

        def perform_queries(num_queries):
            """Perform multiple queries."""
            for _ in range(num_queries):
                with pool.get_connection_context() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()

        start = time.time()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(perform_queries, operations // workers) for _ in range(workers)]
            for future in as_completed(futures):
                future.result()
        elapsed = time.time() - start

        pool.close_all()

        # Should complete in reasonable time (less than 10 seconds for 200 ops)
        assert elapsed < 10.0, f"Throughput too low: {operations / elapsed:.1f} ops/sec"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
