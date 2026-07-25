"""Performance metrics CLI functions."""

import time
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH as _DB_PATH
from education_system.systems.university.infrastructure.database.db import sqlite3


def performance_metrics_menu(log_manager, auth):
    """Performance metrics menu"""
    print("\n\U0001f4c8 PERFORMANCE METRICS")
    print("="*24)

    print("1. Query performance test")
    print("2. Insert performance test")
    print("3. System resource usage")
    print("4. Database response times")
    print("5. Return")

    choice = input("Choose metric: ")

    if choice == '1':
        test_query_performance(log_manager)
    elif choice == '2':
        test_insert_performance(log_manager)
    elif choice == '3':
        show_system_resources()
    elif choice == '4':
        test_database_response_times(log_manager)


def test_query_performance(log_manager):
    """Test query performance"""
    print("\n\U0001f50d QUERY PERFORMANCE TEST")
    print("="*27)

    queries = [
        ("Simple select", "SELECT COUNT(*) FROM logs"),
        ("Date filter", "SELECT COUNT(*) FROM logs WHERE date(timestamp) >= date('now', '-7 days')"),
        ("User filter", "SELECT COUNT(*) FROM logs WHERE user_id = 'admin'"),
        ("Complex filter", "SELECT COUNT(*) FROM logs WHERE action = 'login' AND status = 'success'")
    ]

    conn = sqlite3.connect(str(_DB_PATH))
    try:

        print("Running performance tests...")
        print(f"{'Query':<20} {'Time (ms)':<12} {'Result':<10}")
        print("-" * 45)

        for name, query in queries:
            start_time = time.time()

            try:
                cursor = conn.cursor()
                cursor.execute(query)
                result = cursor.fetchone()[0]

                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000

                print(f"{name:<20} {duration_ms:<11.2f} {result:<10}")

            except Exception as e:
                print(f"{name:<20} ERROR: {e}")

    finally:
        conn.close()
    input("\nPress Enter to continue...")


def test_insert_performance(log_manager):
    """Test insert performance"""
    print("\n\U0001f4dd INSERT PERFORMANCE TEST")
    print("="*28)

    print("This will insert test log entries to measure performance.")
    test_count = input("Number of test entries to insert (default: 100): ")

    try:
        test_count = int(test_count) if test_count else 100
    except ValueError:
        test_count = 100

    confirm = input(f"Insert {test_count} test entries? (y/n): ")
    if confirm.lower() != 'y':
        return

    print(f"Inserting {test_count} test entries...")

    start_time = time.time()

    for i in range(test_count):
        test_log = {
            'timestamp': datetime.now().isoformat(),
            'user_id': f'test_user_{i}',
            'username': f'testuser{i}',
            'role': 'test',
            'action': 'test_action',
            'module': 'performance_test',
            'details': f'Test entry {i}',
            'status': 'success'
        }

        log_manager.db.insert_log(test_log)

        if (i + 1) % 50 == 0:
            print(f"  Inserted {i + 1}/{test_count}")

    end_time = time.time()
    duration = end_time - start_time

    print("\nPerformance Results:")
    print(f"Total time: {duration:.2f} seconds")
    print(f"Average per insert: {(duration/test_count)*1000:.2f} ms")
    print(f"Inserts per second: {test_count/duration:.1f}")

    # Cleanup test entries
    cleanup = input("\nCleanup test entries? (y/n): ")
    if cleanup.lower() == 'y':
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM logs WHERE module = 'performance_test'")
            deleted = cursor.rowcount
            conn.commit()
        finally:
            conn.close()
        print(f"Deleted {deleted} test entries")

    input("\nPress Enter to continue...")


def show_system_resources():
    """Show system resource usage"""
    print("\n\U0001f4bb SYSTEM RESOURCE USAGE")
    print("="*26)

    try:
        import psutil

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        print(f"CPU Usage: {cpu_percent}%")

        # Memory usage
        memory = psutil.virtual_memory()
        print(f"Memory Usage: {memory.percent}%")
        print(f"Available Memory: {memory.available / (1024**3):.2f} GB")
        print(f"Total Memory: {memory.total / (1024**3):.2f} GB")

        # Disk usage
        disk = psutil.disk_usage('/')
        print(f"Disk Usage: {(disk.used / disk.total) * 100:.1f}%")
        print(f"Free Disk Space: {disk.free / (1024**3):.2f} GB")

        # Process info
        process = psutil.Process()
        print("\nCurrent Process:")
        print(f"Memory Usage: {process.memory_info().rss / (1024**2):.2f} MB")
        print(f"CPU Usage: {process.cpu_percent()}%")

    except ImportError:
        print("psutil library not available.")
        print("Install with: pip install psutil")
    except Exception as e:
        print(f"Error retrieving system info: {e}")

    input("\nPress Enter to continue...")


def test_database_response_times(log_manager):
    """Test database response times"""
    print("\n\u23f1\ufe0f DATABASE RESPONSE TIMES")
    print("="*28)

    print("Testing database response times...")

    # Test different types of operations
    tests = [
        ("Connection", lambda: sqlite3.connect(str(_DB_PATH))),
        ("Simple Query", lambda: test_simple_query(log_manager)),
        ("Complex Query", lambda: test_complex_query(log_manager)),
        ("Insert Operation", lambda: test_insert_operation(log_manager))
    ]

    results = []

    for test_name, test_func in tests:
        times = []

        # Run each test 5 times
        for _ in range(5):
            start_time = time.time()
            try:
                result = test_func()
                if hasattr(result, 'close'):
                    result.close()
                end_time = time.time()
                times.append((end_time - start_time) * 1000)  # Convert to ms
            except Exception as e:
                print(f"Error in {test_name}: {e}")
                times.append(float('inf'))

        # Calculate statistics
        if times and all(t != float('inf') for t in times):
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            results.append((test_name, avg_time, min_time, max_time))

    # Display results
    print(f"\n{'Test':<20} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10}")
    print("-" * 55)

    for test_name, avg_time, min_time, max_time in results:
        print(f"{test_name:<20} {avg_time:<9.2f} {min_time:<9.2f} {max_time:<9.2f}")

    input("\nPress Enter to continue...")


def test_simple_query(log_manager):
    """Helper function for simple query test"""
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM logs LIMIT 1")
        result = cursor.fetchone()
    finally:
        conn.close()
    return result


def test_complex_query(log_manager):
    """Helper function for complex query test"""
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, COUNT(*) as count
            FROM logs
            WHERE date(timestamp) >= date('now', '-7 days')
            GROUP BY username
            ORDER BY count DESC
            LIMIT 10
        """)
        result = cursor.fetchall()
    finally:
        conn.close()
    return result


def test_insert_operation(log_manager):
    """Helper function for insert operation test"""
    test_log = {
        'timestamp': datetime.now().isoformat(),
        'user_id': 'perf_test',
        'username': 'performance_test',
        'role': 'test',
        'action': 'test',
        'module': 'test',
        'details': 'Performance test entry',
        'status': 'success'
    }

    log_manager.db.insert_log(test_log)

    # Clean up immediately
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs WHERE username = 'performance_test'")
        conn.commit()
    finally:
        conn.close()
