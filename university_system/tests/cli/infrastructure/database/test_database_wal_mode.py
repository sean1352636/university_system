"""
Comprehensive tests for SQLite Write-Ahead Logging (WAL) mode.

This module tests WAL mode configuration and behavior:
- WAL mode activation and verification
- Concurrent read/write operations
- WAL checkpointing behavior
- WAL file management
- Performance improvements from WAL
- PRAGMA settings validation
- WAL mode vs rollback journal comparison
"""

import pytest
import os
import tempfile
from university_system.infrastructure.database.db import sqlite3
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from university_system.infrastructure.database.db import (
    connect,
    get_connection,
    ConnectionPool,
    transaction
)
from university_system.infrastructure.database.constants import (
    PRAGMA_JOURNAL_MODE,
    PRAGMA_SYNCHRONOUS,
    PRAGMA_FOREIGN_KEYS
)

@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE wal_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            thread_id INTEGER,
            timestamp REAL
        )
    ''')
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup WAL files
    try:
        os.unlink(db_path)
        os.unlink(f"{db_path}-wal")
    except (OSError, IOError):
        pass
    try:
        os.unlink(f"{db_path}-shm")
    except (OSError, IOError):
        pass

class TestWALModeConfiguration:
    """Test WAL mode configuration and activation."""

    def test_wal_mode_enabled_by_default(self, temp_db):
        """Test that WAL mode is enabled by default in connections."""
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        conn.close()

        assert mode.upper() == "WAL", f"Expected WAL mode, got {mode}"

    def test_get_connection_uses_wal(self, temp_db):
        """Test that get_connection() enables WAL mode."""
        conn = get_connection(db_path=temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        conn.close()

        assert mode.upper() == "WAL"

    def test_connection_pool_uses_wal(self, temp_db):
        """Test that connection pool connections use WAL mode."""
        pool = ConnectionPool(db_path=temp_db, max_connections=3, min_connections=1)

        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        pool.release_connection(conn)
        pool.close_all()

        assert mode.upper() == "WAL"

    def test_wal_pragma_constant_matches(self):
        """Test that PRAGMA constant is set to WAL."""
        assert PRAGMA_JOURNAL_MODE.upper() == "WAL"

    def test_wal_files_created(self, temp_db):
        """Test that WAL files are created when WAL mode is active."""
        conn = connect(temp_db)
        cursor = conn.cursor()

        # Perform a write to create WAL files
        cursor.execute("INSERT INTO wal_test (data) VALUES ('test')")
        conn.commit()
        conn.close()

        # Check for WAL files
        wal_file = Path(f"{temp_db}-wal")
        shm_file = Path(f"{temp_db}-shm")

        # At least one should exist (depends on timing)
        assert wal_file.exists() or shm_file.exists(), "No WAL files created"

    def test_synchronous_pragma_setting(self, temp_db):
        """Test that synchronous mode is properly set."""
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA synchronous")
        sync_mode = cursor.fetchone()[0]
        conn.close()

        # NORMAL = 1, FULL = 2, OFF = 0
        assert sync_mode in [0, 1, 2], f"Invalid synchronous mode: {sync_mode}"

    def test_foreign_keys_pragma_setting(self, temp_db):
        """Test that foreign keys are enabled."""
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        fk_enabled = cursor.fetchone()[0]
        conn.close()

        assert fk_enabled == 1, "Foreign keys should be enabled"

class TestWALConcurrentReads:
    """Test WAL mode's concurrent read capabilities."""

    def test_concurrent_readers(self, temp_db):
        """Test that multiple readers can access database simultaneously."""
        # Populate database
        conn = connect(temp_db)
        cursor = conn.cursor()
        for i in range(100):
            cursor.execute("INSERT INTO wal_test (data) VALUES (?)", (f"record_{i}",))
        conn.commit()
        conn.close()

        read_results = []
        lock = threading.Lock()

        def concurrent_reader(reader_id):
            """Read from database."""
            conn = connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM wal_test")
            count = cursor.fetchone()[0]
            conn.close()

            with lock:
                read_results.append((reader_id, count))

        # Launch many concurrent readers
        threads = [threading.Thread(target=concurrent_reader, args=(i,)) for i in range(20)]
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        # All readers should succeed
        assert len(read_results) == 20
        # All should see the same count
        assert all(count == 100 for _, count in read_results)
        # Should complete quickly (concurrent, not sequential)
        assert elapsed < 2.0, f"Concurrent reads too slow: {elapsed:.2f}s"

    def test_read_while_write_in_progress(self, temp_db):
        """Test that reads can occur while write is in progress (WAL advantage)."""
        results = {"writer": None, "readers": []}

        def writer():
            """Perform slow write."""
            conn = connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            for i in range(50):
                cursor.execute("INSERT INTO wal_test (data) VALUES (?)", (f"write_{i}",))
                time.sleep(0.01)  # Slow write
            conn.commit()
            conn.close()
            results["writer"] = "done"

        def reader(reader_id):
            """Perform read during write."""
            time.sleep(0.1)  # Let writer start
            conn = connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM wal_test")
            count = cursor.fetchone()[0]
            conn.close()
            results["readers"].append((reader_id, count))

        # Start writer
        writer_thread = threading.Thread(target=writer)
        writer_thread.start()

        # Start readers while writer is running
        reader_threads = [threading.Thread(target=reader, args=(i,)) for i in range(5)]
        for t in reader_threads:
            t.start()

        for t in reader_threads:
            t.join()
        writer_thread.join()

        # Readers should complete (not blocked by writer in WAL mode)
        assert len(results["readers"]) == 5
        assert results["writer"] == "done"

class TestWALConcurrentWrites:
    """Test WAL mode's handling of concurrent writes."""

    def test_sequential_writes_succeed(self, temp_db):
        """Test that concurrent writes are serialized properly."""
        write_results = []

        def write_record(thread_id):
            """Write a record."""
            try:
                conn = connect(temp_db)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO wal_test (data, thread_id, timestamp) VALUES (?, ?, ?)",
                    (f"thread_{thread_id}", thread_id, time.time())
                )
                conn.commit()
                conn.close()
                write_results.append(("success", thread_id))
            except Exception as e:
                write_results.append(("error", str(e)))

        # Concurrent writers
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_record, i) for i in range(20)]
            for future in as_completed(futures):
                future.result()

        # All writes should succeed
        assert len(write_results) == 20
        success_count = sum(1 for status, _ in write_results if status == "success")
        assert success_count == 20, f"Only {success_count}/20 writes succeeded"

        # Verify data integrity
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM wal_test")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 20

    def test_wal_reduces_lock_contention(self, temp_db):
        """Test that WAL mode reduces lock contention vs rollback journal."""
        # This is a comparative test - WAL should have fewer lock errors

        lock_errors = []

        def quick_write(value):
            """Quick write operation."""
            try:
                with transaction(db_path=temp_db) as conn:
                    conn.execute("INSERT INTO wal_test (data) VALUES (?)", (f"val_{value}",))
            except sqlite3.OperationalError as e:
                if "locked" in str(e):
                    lock_errors.append(str(e))
                raise

        # Many concurrent quick writes
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(quick_write, i) for i in range(50)]
            for future in as_completed(futures):
                try:
                    future.result()
                except sqlite3.OperationalError:
                    pass  # Expected occasional locks

        # WAL mode should have minimal lock errors
        # (In rollback mode, this would have many more)
        lock_error_rate = len(lock_errors) / 50
        assert lock_error_rate < 0.3, f"Too many lock errors: {lock_error_rate:.1%}"

class TestWALCheckpointing:
    """Test WAL checkpointing behavior."""

    def test_wal_checkpoint_passive(self, temp_db):
        """Test passive WAL checkpoint."""
        conn = connect(temp_db)
        cursor = conn.cursor()

        # Generate WAL entries
        for i in range(100):
            cursor.execute("INSERT INTO wal_test (data) VALUES (?)", (f"data_{i}",))
        conn.commit()

        # Trigger passive checkpoint
        cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
        result = cursor.fetchone()
        conn.close()

        # Result is (busy, log, checkpointed)
        assert result is not None

    def test_wal_checkpoint_full(self, temp_db):
        """Test full WAL checkpoint."""
        conn = connect(temp_db)
        cursor = conn.cursor()

        # Generate WAL entries
        for i in range(50):
            cursor.execute("INSERT INTO wal_test (data) VALUES (?)", (f"data_{i}",))
        conn.commit()

        # Full checkpoint
        cursor.execute("PRAGMA wal_checkpoint(FULL)")
        result = cursor.fetchone()

        # Check result
        assert result is not None
        busy, log, checkpointed = result
        assert busy == 0, "Checkpoint should not be busy"

        conn.close()

    def test_wal_checkpoint_truncate(self, temp_db):
        """Test truncating WAL checkpoint."""
        conn = connect(temp_db)
        cursor = conn.cursor()

        # Generate WAL entries
        for i in range(30):
            cursor.execute("INSERT INTO wal_test (data) VALUES (?)", (f"data_{i}",))
        conn.commit()

        # Get WAL file size before
        wal_file = Path(f"{temp_db}-wal")
        size_before = wal_file.stat().st_size if wal_file.exists() else 0

        # Truncate checkpoint
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        # WAL file should be smaller or gone after truncate
        size_after = wal_file.stat().st_size if wal_file.exists() else 0

        conn.close()

        # After truncate, WAL should be smaller or zero
        assert size_after <= size_before

    def test_auto_checkpoint_threshold(self, temp_db):
        """Test WAL auto-checkpoint behavior."""
        conn = connect(temp_db)
        cursor = conn.cursor()

        # Check auto-checkpoint setting
        cursor.execute("PRAGMA wal_autocheckpoint")
        threshold = cursor.fetchone()[0]

        # Default is usually 1000 pages
        assert threshold > 0, "Auto-checkpoint should be enabled"

        # Set custom threshold
        cursor.execute("PRAGMA wal_autocheckpoint = 100")
        cursor.execute("PRAGMA wal_autocheckpoint")
        new_threshold = cursor.fetchone()[0]

        assert new_threshold == 100

        conn.close()

class TestWALPerformance:
    """Test performance characteristics of WAL mode."""

    def test_write_performance_comparison(self, temp_db):
        """Compare write performance (indicative test)."""
        def measure_writes(num_writes):
            """Measure time for num_writes."""
            conn = connect(temp_db)
            cursor = conn.cursor()
            start = time.time()

            cursor.execute("BEGIN TRANSACTION")
            for i in range(num_writes):
                cursor.execute("INSERT INTO wal_test (data) VALUES (?)", (f"perf_{i}",))
            conn.commit()

            elapsed = time.time() - start
            conn.close()
            return elapsed

        # Measure write performance
        writes = 500
        elapsed = measure_writes(writes)

        # Should complete in reasonable time
        assert elapsed < 5.0, f"Writes too slow: {elapsed:.2f}s for {writes} records"

        # Calculate throughput
        throughput = writes / elapsed
        assert throughput > 50, f"Throughput too low: {throughput:.1f} writes/sec"

    def test_concurrent_read_performance(self, temp_db):
        """Test concurrent read performance with WAL."""
        # Populate database
        conn = connect(temp_db)
        cursor = conn.cursor()
        for i in range(200):
            cursor.execute("INSERT INTO wal_test (data) VALUES (?)", (f"perf_{i}",))
        conn.commit()
        conn.close()

        def perform_reads(num_reads):
            """Perform multiple reads."""
            conn = connect(temp_db)
            cursor = conn.cursor()
            for _ in range(num_reads):
                cursor.execute("SELECT * FROM wal_test LIMIT 10")
                cursor.fetchall()
            conn.close()

        # Concurrent readers
        start = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(perform_reads, 20) for _ in range(10)]
            for future in as_completed(futures):
                future.result()
        elapsed = time.time() - start

        # 10 threads * 20 reads = 200 total reads
        # Should benefit from WAL concurrency
        assert elapsed < 5.0, f"Concurrent reads too slow: {elapsed:.2f}s"

class TestWALReliability:
    """Test WAL mode reliability and crash recovery."""

    def test_wal_survives_abrupt_close(self, temp_db):
        """Test that data is recoverable after abrupt connection close."""
        # Write data
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO wal_test (data) VALUES ('important_data')")
        conn.commit()
        # Abruptly close without explicit checkpoint
        conn.close()

        # Reopen and verify data
        conn2 = connect(temp_db)
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT COUNT(*) FROM wal_test WHERE data = 'important_data'")
        count = cursor2.fetchone()[0]
        conn2.close()

        assert count == 1, "Data should survive abrupt close"

    def test_wal_consistency_after_errors(self, temp_db):
        """Test database consistency after errors in WAL mode."""
        conn = connect(temp_db)
        cursor = conn.cursor()

        # Successful insert
        cursor.execute("INSERT INTO wal_test (data) VALUES ('before_error')")
        conn.commit()

        # Attempt invalid operation
        try:
            cursor.execute("INSERT INTO nonexistent_table (data) VALUES ('test')")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Expected

        # Verify database still works
        cursor.execute("INSERT INTO wal_test (data) VALUES ('after_error')")
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM wal_test")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 2

    def test_wal_mode_persists_across_connections(self, temp_db):
        """Test that WAL mode persists across connection cycles."""
        # Enable WAL
        conn1 = connect(temp_db)
        cursor1 = conn1.cursor()
        cursor1.execute("PRAGMA journal_mode = WAL")
        conn1.close()

        # New connection should still be in WAL mode
        conn2 = connect(temp_db)
        cursor2 = conn2.cursor()
        cursor2.execute("PRAGMA journal_mode")
        mode = cursor2.fetchone()[0]
        conn2.close()

        assert mode.upper() == "WAL"

class TestWALFileManagement:
    """Test WAL file management and cleanup."""

    def test_wal_file_exists_during_operation(self, temp_db):
        """Test that WAL files exist during active operations."""
        conn = connect(temp_db)
        cursor = conn.cursor()

        # Perform write
        cursor.execute("INSERT INTO wal_test (data) VALUES ('test')")
        conn.commit()

        # Check for WAL files
        wal_file = Path(f"{temp_db}-wal")
        exists = wal_file.exists()

        conn.close()

        # WAL file should have been created
        assert exists, "WAL file should exist during operations"

    def test_wal_cleanup_on_checkpoint(self, temp_db):
        """Test WAL cleanup after checkpoint."""
        conn = connect(temp_db)
        cursor = conn.cursor()

        # Generate WAL content
        for i in range(20):
            cursor.execute("INSERT INTO wal_test (data) VALUES (?)", (f"data_{i}",))
        conn.commit()

        wal_file = Path(f"{temp_db}-wal")
        size_before = wal_file.stat().st_size if wal_file.exists() else 0

        # Checkpoint and truncate
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        size_after = wal_file.stat().st_size if wal_file.exists() else 0

        conn.close()

        # WAL should be smaller after truncate checkpoint
        assert size_after <= size_before

class TestWALIntegration:
    """Test WAL integration with other database features."""

    def test_wal_with_transactions(self, temp_db):
        """Test WAL mode with transaction context manager."""
        # Use transaction context manager
        with transaction(db_path=temp_db) as conn:
            conn.execute("INSERT INTO wal_test (data) VALUES ('transactional')")

        # Verify in new connection
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM wal_test WHERE data = 'transactional'")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

    def test_wal_with_connection_pool(self, temp_db):
        """Test WAL mode with connection pooling."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=5,
            min_connections=2
        )

        # Concurrent operations through pool
        def pooled_write(value):
            """Write using pooled connection."""
            with pool.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO wal_test (data) VALUES (?)", (f"pooled_{value}",))
                conn.commit()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(pooled_write, i) for i in range(20)]
            for future in as_completed(futures):
                future.result()

        pool.close_all()

        # Verify all writes
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM wal_test WHERE data LIKE 'pooled_%'")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 20

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
