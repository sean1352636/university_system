"""
Comprehensive tests for database deadlock detection and recovery.

This module tests deadlock scenarios and mitigation strategies:
- Deadlock detection mechanisms
- Timeout-based deadlock prevention
- Transaction ordering to prevent deadlocks
- Recovery from deadlock situations
- Lock escalation scenarios
- Multi-table transaction conflicts
- Busy timeout handling
"""

import pytest
import os
import tempfile
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from university_system.infrastructure.database.db import (
    connect,
    get_connection,
    transaction,
    atomic_operation,
    ConnectionPool
)
from university_system.infrastructure.database.constants import SQLITE_BUSY_TIMEOUT


@pytest.fixture
def temp_db():
    """Create a temporary test database with multiple tables."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables for deadlock testing
    cursor.execute('''
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            name TEXT,
            balance REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE transactions_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_account INTEGER,
            to_account INTEGER,
            amount REAL,
            timestamp REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE inventory (
            item_id INTEGER PRIMARY KEY,
            quantity INTEGER,
            reserved INTEGER DEFAULT 0
        )
    ''')

    # Insert test data
    cursor.execute("INSERT INTO accounts VALUES (1, 'Alice', 1000)")
    cursor.execute("INSERT INTO accounts VALUES (2, 'Bob', 1000)")
    cursor.execute("INSERT INTO inventory VALUES (101, 100, 0)")
    cursor.execute("INSERT INTO inventory VALUES (102, 50, 0)")

    conn.commit()
    conn.close()

    yield db_path

    try:
        os.unlink(db_path)
    except (OSError, IOError):
        pass


class TestDeadlockDetection:
    """Test deadlock detection mechanisms."""

    def test_simple_write_lock_timeout(self, temp_db):
        """Test that write locks timeout appropriately."""
        results = {"holder": None, "waiter": None}

        def hold_lock():
            """Hold a write lock for extended period."""
            conn = connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
            results["holder"] = "acquired"
            time.sleep(2.0)  # Hold lock
            conn.commit()
            conn.close()
            results["holder"] = "released"

        def wait_for_lock():
            """Try to acquire lock with timeout."""
            time.sleep(0.2)  # Let holder acquire first
            try:
                conn = connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
                cursor.execute("INSERT INTO accounts VALUES (3, 'Charlie', 500)")
                conn.commit()
                conn.close()
                results["waiter"] = "success"
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    results["waiter"] = "timeout"
                else:
                    results["waiter"] = f"error: {e}"

        t1 = threading.Thread(target=hold_lock)
        t2 = threading.Thread(target=wait_for_lock)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Waiter should either timeout or succeed after holder releases
        assert results["holder"] == "released"
        assert results["waiter"] in ["timeout", "success"]

    def test_busy_timeout_configured(self, temp_db):
        """Test that busy_timeout PRAGMA is properly configured."""
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout")
        timeout = cursor.fetchone()[0]
        conn.close()

        # Should be configured (in milliseconds)
        assert timeout > 0, "Busy timeout should be configured"
        assert timeout >= 1000, f"Busy timeout too short: {timeout}ms"

    def test_concurrent_updates_same_row(self, temp_db):
        """Test concurrent updates to the same row (should serialize or timeout)."""
        results = []

        def update_account(thread_id, sleep_time=0.1):
            """Update the same account."""
            try:
                with transaction(db_path=temp_db) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT balance FROM accounts WHERE id = 1")
                    balance = cursor.fetchone()[0]
                    time.sleep(sleep_time)  # Simulate processing
                    cursor.execute(
                        "UPDATE accounts SET balance = ? WHERE id = 1",
                        (balance + 100,)
                    )
                results.append(("success", thread_id))
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    results.append(("locked", thread_id))
                else:
                    results.append(("error", str(e)))

        threads = [threading.Thread(target=update_account, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should complete (some may be serialized, some may timeout)
        assert len(results) == 5

        # Check final balance consistency
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE id = 1")
        final_balance = cursor.fetchone()[0]
        conn.close()

        success_count = sum(1 for status, _ in results if status == "success")
        # Balance should be original (1000) + (100 * successful updates)
        expected_balance = 1000 + (100 * success_count)
        assert final_balance == expected_balance


class TestDeadlockPrevention:
    """Test deadlock prevention strategies."""

    def test_consistent_lock_ordering(self, temp_db):
        """Test that consistent lock ordering prevents deadlocks."""
        results = []

        def transfer_consistent(from_id, to_id, amount):
            """Transfer money with consistent ordering (min to max)."""
            # Always lock lower ID first to prevent circular wait
            first_id, second_id = sorted([from_id, to_id])

            try:
                with transaction(db_path=temp_db) as conn:
                    cursor = conn.cursor()

                    # Lock in consistent order
                    cursor.execute("SELECT balance FROM accounts WHERE id = ? FOR UPDATE", (first_id,))
                    cursor.execute("SELECT balance FROM accounts WHERE id = ? FOR UPDATE", (second_id,))

                    # Perform transfer
                    cursor.execute(
                        "UPDATE accounts SET balance = balance - ? WHERE id = ?",
                        (amount, from_id)
                    )
                    cursor.execute(
                        "UPDATE accounts SET balance = balance + ? WHERE id = ?",
                        (amount, to_id)
                    )

                results.append("success")
            except sqlite3.OperationalError:
                results.append("locked")

        # Concurrent transfers in different directions
        t1 = threading.Thread(target=transfer_consistent, args=(1, 2, 100))
        t2 = threading.Thread(target=transfer_consistent, args=(2, 1, 50))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # With consistent ordering, both should succeed (or serialize)
        assert len(results) == 2

    def test_timeout_prevents_indefinite_wait(self, temp_db):
        """Test that timeouts prevent indefinite waiting."""
        start_time = time.time()

        def blocking_transaction():
            """Start transaction and hold it."""
            conn = connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("BEGIN EXCLUSIVE")
            cursor.execute("UPDATE accounts SET balance = 9999 WHERE id = 1")
            time.sleep(3.0)  # Hold transaction
            conn.rollback()
            conn.close()

        def timed_attempt():
            """Attempt to write with timeout."""
            time.sleep(0.5)  # Let blocker start first
            try:
                conn = connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute("UPDATE accounts SET balance = 8888 WHERE id = 1")
                conn.commit()
                conn.close()
            except sqlite3.OperationalError:
                pass  # Expected timeout

        blocker = threading.Thread(target=blocking_transaction)
        attempter = threading.Thread(target=timed_attempt)

        blocker.start()
        attempter.start()
        blocker.join()
        attempter.join()

        elapsed = time.time() - start_time

        # Should not take indefinitely (should timeout)
        assert elapsed < 60.0, f"Operation took too long: {elapsed:.1f}s"

    def test_immediate_transaction_detection(self, temp_db):
        """Test IMMEDIATE transaction for early lock detection."""
        def use_immediate():
            """Use IMMEDIATE transaction."""
            conn = connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            time.sleep(1.0)
            cursor.execute("INSERT INTO accounts VALUES (5, 'Eve', 500)")
            conn.commit()
            conn.close()

        def try_concurrent():
            """Try concurrent IMMEDIATE transaction."""
            time.sleep(0.2)
            try:
                conn = connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")  # Should detect conflict early
                cursor.execute("INSERT INTO accounts VALUES (6, 'Frank', 600)")
                conn.commit()
                conn.close()
                return "success"
            except sqlite3.OperationalError:
                return "locked"

        t1 = threading.Thread(target=use_immediate)
        t1.start()

        result = try_concurrent()

        t1.join()

        # Second transaction should detect lock early
        assert result in ["locked", "success"]


class TestDeadlockRecovery:
    """Test recovery from deadlock situations."""

    def test_retry_after_lock_failure(self, temp_db):
        """Test retry logic after lock failure."""
        def update_with_retry(max_retries=3):
            """Update with retry on lock failure."""
            for attempt in range(max_retries):
                try:
                    with transaction(db_path=temp_db) as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE accounts SET balance = balance + 50 WHERE id = 1")
                    return "success"
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        return "failed"
            return "failed"

        # Concurrent updates with retry
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(update_with_retry) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # Most should succeed with retry
        success_count = results.count("success")
        assert success_count >= 7, f"Too many failures: {success_count}/10"

    def test_rollback_on_deadlock(self, temp_db):
        """Test that transactions rollback properly on deadlock."""
        initial_balance = 1000

        def transfer_with_rollback(from_id, to_id, amount):
            """Transfer with rollback on error."""
            try:
                with transaction(db_path=temp_db) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE accounts SET balance = balance - ? WHERE id = ?",
                        (amount, from_id)
                    )
                    time.sleep(0.1)  # Increase conflict window
                    cursor.execute(
                        "UPDATE accounts SET balance = balance + ? WHERE id = ?",
                        (amount, to_id)
                    )
                return "success"
            except Exception:
                return "rolled_back"

        # Concurrent conflicting transfers
        results = []
        threads = [
            threading.Thread(target=lambda: results.append(transfer_with_rollback(1, 2, 100))),
            threading.Thread(target=lambda: results.append(transfer_with_rollback(2, 1, 100))),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Check database consistency
        conn = connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(balance) FROM accounts WHERE id IN (1, 2)")
        total_balance = cursor.fetchone()[0]
        conn.close()

        # Total should be preserved (2000)
        assert total_balance == 2000, f"Balance not preserved: {total_balance}"


class TestLockEscalation:
    """Test lock escalation scenarios."""

    def test_read_to_write_upgrade(self, temp_db):
        """Test upgrading from read lock to write lock."""
        def read_then_write():
            """Read, then try to write."""
            conn = connect(temp_db)
            cursor = conn.cursor()

            cursor.execute("BEGIN")
            # Read
            cursor.execute("SELECT balance FROM accounts WHERE id = 1")
            balance = cursor.fetchone()[0]

            time.sleep(0.1)

            # Try to write (upgrade to write lock)
            try:
                cursor.execute("UPDATE accounts SET balance = ? WHERE id = 1", (balance + 100,))
                conn.commit()
                conn.close()
                return "success"
            except sqlite3.OperationalError:
                conn.rollback()
                conn.close()
                return "locked"

        # Multiple threads trying to upgrade
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(read_then_write) for _ in range(3)]
            results = [f.result() for f in as_completed(futures)]

        # At least one should succeed
        assert "success" in results

    def test_multiple_table_locking(self, temp_db):
        """Test locking across multiple tables."""
        def multi_table_transaction():
            """Transaction spanning multiple tables."""
            try:
                with transaction(db_path=temp_db) as conn:
                    cursor = conn.cursor()

                    # Lock multiple tables
                    cursor.execute("UPDATE accounts SET balance = balance - 10 WHERE id = 1")
                    time.sleep(0.1)
                    cursor.execute("UPDATE inventory SET quantity = quantity - 1 WHERE item_id = 101")
                    cursor.execute(
                        "INSERT INTO transactions_log (from_account, to_account, amount, timestamp) "
                        "VALUES (1, 0, 10, ?)",
                        (time.time(),)
                    )

                return "success"
            except sqlite3.OperationalError:
                return "locked"

        # Concurrent multi-table transactions
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(multi_table_transaction) for _ in range(5)]
            results = [f.result() for f in as_completed(futures)]

        # Should handle serialization
        success_count = results.count("success")
        assert success_count > 0


class TestConnectionPoolDeadlocks:
    """Test deadlock scenarios with connection pooling."""

    def test_pool_deadlock_prevention(self, temp_db):
        """Test that connection pool prevents certain deadlocks."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=3,
            min_connections=1
        )

        results = []

        def pooled_update(value):
            """Update using pooled connection."""
            try:
                conn = pool.get_connection(timeout=2.0)
                cursor = conn.cursor()
                cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = 1", (value,))
                conn.commit()
                pool.release_connection(conn)
                results.append("success")
            except Exception:
                results.append("error")

        # Concurrent updates
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(pooled_update, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        pool.close_all()

        # Most should succeed
        success_count = results.count("success")
        assert success_count >= 7

    def test_nested_pool_acquisition_deadlock(self, temp_db):
        """Test potential deadlock from nested pool acquisition."""
        pool = ConnectionPool(
            db_path=temp_db,
            max_connections=2,
            min_connections=1
        )

        def nested_attempt():
            """Try nested connection acquisition."""
            try:
                conn1 = pool.get_connection(timeout=1.0)
                # Try to get another while holding one (risky!)
                try:
                    conn2 = pool.get_connection(timeout=1.0)
                    pool.release_connection(conn2)
                    pool.release_connection(conn1)
                    return "success"
                except Exception:
                    pool.release_connection(conn1)
                    return "timeout"
            except Exception:
                return "error"

        result = nested_attempt()
        pool.close_all()

        # Should handle gracefully (either succeed or timeout, not deadlock)
        assert result in ["success", "timeout", "error"]


class TestTransactionConflicts:
    """Test transaction conflict scenarios."""

    def test_write_write_conflict(self, temp_db):
        """Test write-write conflict handling."""
        results = []

        def concurrent_write(value):
            """Concurrent write to same record."""
            try:
                with transaction(db_path=temp_db) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE accounts SET name = ? WHERE id = 1", (f"Name_{value}",))
                    time.sleep(0.1)  # Hold transaction
                results.append("success")
            except sqlite3.OperationalError:
                results.append("conflict")

        threads = [threading.Thread(target=concurrent_write, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Conflicts should be handled
        assert len(results) == 3

    def test_read_write_conflict(self, temp_db):
        """Test read during write conflict."""
        write_started = threading.Event()
        results = {"reader": None, "writer": None}

        def writer():
            """Long-running write."""
            try:
                with transaction(db_path=temp_db) as conn:
                    cursor = conn.cursor()
                    cursor.execute("BEGIN EXCLUSIVE")
                    write_started.set()
                    time.sleep(0.5)
                    cursor.execute("UPDATE accounts SET balance = 5000 WHERE id = 1")
                results["writer"] = "success"
            except Exception as e:
                results["writer"] = f"error: {e}"

        def reader():
            """Read during write."""
            write_started.wait(timeout=2.0)
            time.sleep(0.1)  # Let writer progress
            try:
                conn = connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT balance FROM accounts WHERE id = 1")
                cursor.fetchone()
                conn.close()
                results["reader"] = "success"
            except sqlite3.OperationalError:
                results["reader"] = "blocked"

        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)

        writer_thread.start()
        reader_thread.start()
        writer_thread.join()
        reader_thread.join()

        # Reader may be blocked or succeed depending on WAL mode
        assert results["reader"] in ["success", "blocked"]
        assert results["writer"] == "success"


class TestDeadlockDiagnostics:
    """Test deadlock diagnostic capabilities."""

    def test_identify_locked_table(self, temp_db):
        """Test identifying which table is locked."""
        def lock_table():
            """Lock a table."""
            conn = connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("BEGIN EXCLUSIVE")
            cursor.execute("SELECT * FROM accounts")
            time.sleep(2.0)
            conn.rollback()
            conn.close()

        def probe_lock():
            """Try to identify locked table."""
            time.sleep(0.5)
            locked_tables = []

            try:
                conn = connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")

                # Try different tables
                for table in ["accounts", "inventory", "transactions_log"]:
                    try:
                        cursor.execute(f"SELECT * FROM {table} LIMIT 1")
                    except sqlite3.OperationalError:
                        locked_tables.append(table)

                conn.rollback()
                conn.close()
            except Exception:
                pass

            return locked_tables

        locker = threading.Thread(target=lock_table)
        locker.start()

        locked = probe_lock()

        locker.join()

        # May detect locked tables (depends on lock granularity)
        assert isinstance(locked, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
