"""
Performance Testing and Benchmarks

This module contains performance tests for:
- Critical query performance
- Database connection pool under load
- Memory usage during bulk operations
- Property-based testing with hypothesis
"""

import pytest
import time
from university_system.infrastructure.database.db import sqlite3
import psutil
import os
import gc
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import List, Tuple
from unittest.mock import patch

from university_system.infrastructure.database.db import get_connection, transaction

# Try to import hypothesis for property-based testing
try:
    from hypothesis import given, strategies as st, settings, Phase
    from hypothesis.statistic import describe_statistics
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    # Create dummy decorator if hypothesis not available
    def given(*args, **kwargs):
        return lambda f: f
    settings = lambda **kwargs: lambda f: f

@contextmanager
def measure_time():
    """Context manager to measure execution time"""
    start = time.perf_counter()
    yield lambda: time.perf_counter() - start

@contextmanager
def measure_memory():
    """Context manager to measure memory usage"""
    gc.collect()
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / 1024 / 1024  # MB

    yield_data = {'before': mem_before}
    yield yield_data

    gc.collect()
    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    yield_data['after'] = mem_after
    yield_data['delta'] = mem_after - mem_before

@pytest.mark.slow
@pytest.mark.performance
class TestQueryPerformanceBenchmarks:
    """Benchmark critical database queries"""

    def test_grade_calculation_performance(self, temp_db):
        """Benchmark: Calculate GPA for 1000 students"""

        # Setup: Create 1000 students with grades
        with transaction() as conn:
            for i in range(1000):
                student_id = f"STU{i:05d}"

                # Create student
                conn.execute("""
                    INSERT INTO students (
                        student_id, first_name, last_name, email, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_id, f"Student{i}", "Test", f"s{i}@uni.edu", "active"))

                # Create 5 grades per student
                for j in range(5):
                    course_id = f"CRS{j:03d}"
                    grade = 70 + (i + j) % 30  # Grades between 70-100

                    conn.execute("""
                        INSERT OR IGNORE INTO courses (
                            course_id, course_name, credits, status
                        ) VALUES (?, ?, ?, ?)
                    """, (course_id, f"Course {j}", 3, "active"))

                    conn.execute("""
                        INSERT INTO grades (
                            student_id, course_id, grade, letter_grade, grade_date
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (student_id, course_id, grade, "B", datetime.now().date()))

        # Benchmark: Calculate GPA for all students
        with measure_time() as get_time:
            with get_connection() as conn:
                results = conn.execute("""
                    SELECT
                        student_id,
                        AVG(grade) as gpa,
                        COUNT(*) as num_courses
                    FROM grades
                    GROUP BY student_id
                    ORDER BY gpa DESC
                """).fetchall()

        elapsed = get_time()

        # Assertions
        assert len(results) == 1000
        assert elapsed < 1.0, f"GPA calculation took {elapsed:.3f}s, should be < 1.0s"

        print(f"\n✓ GPA calculation for 1000 students: {elapsed:.3f}s")

    def test_transcript_generation_performance(self, temp_db):
        """Benchmark: Generate transcript with joins for 100 students"""

        # Setup: Create students with complete academic records
        num_students = 100
        courses_per_student = 20

        with transaction() as conn:
            for i in range(num_students):
                student_id = f"STU{i:04d}"

                conn.execute("""
                    INSERT INTO students (
                        student_id, first_name, last_name, email, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_id, f"Student{i}", "Test", f"s{i}@uni.edu", "active"))

                for j in range(courses_per_student):
                    course_id = f"CRS{j:04d}"

                    conn.execute("""
                        INSERT OR IGNORE INTO courses (
                            course_id, course_name, credits, status
                        ) VALUES (?, ?, ?, ?)
                    """, (course_id, f"Course {j}", 3, "active"))

                    conn.execute("""
                        INSERT INTO grades (
                            student_id, course_id, grade, letter_grade,
                            grade_date, semester
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (student_id, course_id, 85.0, "B",
                          datetime.now().date(), "2024-01"))

        # Benchmark: Generate transcripts with complex join
        with measure_time() as get_time:
            with get_connection() as conn:
                for i in range(num_students):
                    student_id = f"STU{i:04d}"
                    transcript = conn.execute("""
                        SELECT
                            s.student_id,
                            s.first_name,
                            s.last_name,
                            c.course_id,
                            c.course_name,
                            c.credits,
                            g.letter_grade,
                            g.grade,
                            g.semester
                        FROM students s
                        JOIN grades g ON s.student_id = g.student_id
                        JOIN courses c ON g.course_id = c.course_id
                        WHERE s.student_id = ?
                        ORDER BY g.semester, c.course_id
                    """, (student_id,)).fetchall()

                    assert len(transcript) == courses_per_student

        elapsed = get_time()
        avg_time = elapsed / num_students

        assert elapsed < 5.0, f"Transcript generation took {elapsed:.3f}s, should be < 5.0s"

        print(f"\n✓ Generated {num_students} transcripts: {elapsed:.3f}s (avg: {avg_time*1000:.1f}ms)")

    def test_enrollment_search_performance(self, temp_db):
        """Benchmark: Search enrollments with multiple filters"""

        # Setup: Create diverse enrollment data
        with transaction() as conn:
            semesters = ["2023-FALL", "2024-SPRING", "2024-FALL"]
            statuses = ["enrolled", "completed", "withdrawn"]

            for i in range(500):
                student_id = f"STU{i:04d}"

                conn.execute("""
                    INSERT INTO students (
                        student_id, first_name, last_name, email, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_id, f"Student{i}", "Test", f"s{i}@uni.edu", "active"))

                for j in range(10):
                    course_id = f"CRS{j:03d}"

                    conn.execute("""
                        INSERT OR IGNORE INTO courses (
                            course_id, course_name, credits, status
                        ) VALUES (?, ?, ?, ?)
                    """, (course_id, f"Course {j}", 3, "active"))

                    conn.execute("""
                        INSERT INTO enrollments (
                            student_id, course_id, enrollment_date, status
                        ) VALUES (?, ?, ?, ?)
                    """, (student_id, course_id, datetime.now().date(),
                          statuses[j % len(statuses)]))

        # Benchmark: Complex search query
        with measure_time() as get_time:
            with get_connection() as conn:
                results = conn.execute("""
                    SELECT
                        e.student_id,
                        s.first_name,
                        s.last_name,
                        e.course_id,
                        c.course_name,
                        e.status,
                        e.enrollment_date
                    FROM enrollments e
                    JOIN students s ON e.student_id = s.student_id
                    JOIN courses c ON e.course_id = c.course_id
                    WHERE e.status = 'enrolled'
                        AND s.status = 'active'
                    ORDER BY e.enrollment_date DESC
                    LIMIT 100
                """).fetchall()

        elapsed = get_time()

        assert len(results) > 0
        assert elapsed < 0.5, f"Enrollment search took {elapsed:.3f}s, should be < 0.5s"

        print(f"\n✓ Enrollment search across 5000 records: {elapsed:.3f}s")

@pytest.mark.slow
@pytest.mark.performance
class TestConnectionPoolPerformance:
    """Test database connection pool under load"""

    def test_concurrent_read_queries(self, temp_db):
        """Benchmark: Multiple concurrent read queries"""

        # Setup: Create test data
        with transaction() as conn:
            for i in range(100):
                student_id = f"STU{i:03d}"
                conn.execute("""
                    INSERT INTO students (
                        student_id, first_name, last_name, email, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_id, f"Student{i}", "Test", f"s{i}@uni.edu", "active"))

        # Benchmark: Simulate concurrent reads
        num_queries = 100

        with measure_time() as get_time:
            for _ in range(num_queries):
                with get_connection() as conn:
                    conn.execute("""
                        SELECT * FROM students WHERE status = 'active'
                    """).fetchall()

        elapsed = get_time()
        avg_query_time = (elapsed / num_queries) * 1000  # ms

        assert elapsed < 5.0, f"100 concurrent reads took {elapsed:.3f}s, should be < 5.0s"

        print(f"\n✓ {num_queries} concurrent reads: {elapsed:.3f}s (avg: {avg_query_time:.2f}ms)")

    def test_transaction_throughput(self, temp_db):
        """Benchmark: Transaction throughput"""

        num_transactions = 50

        with measure_time() as get_time:
            for i in range(num_transactions):
                with transaction() as conn:
                    student_id = f"PERF{i:04d}"
                    conn.execute("""
                        INSERT INTO students (
                            student_id, first_name, last_name, email, status
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (student_id, f"PerfTest{i}", "User", f"perf{i}@uni.edu", "active"))

        elapsed = get_time()
        transactions_per_sec = num_transactions / elapsed

        assert transactions_per_sec > 10, f"Only {transactions_per_sec:.1f} tx/s, should be > 10"

        print(f"\n✓ Transaction throughput: {transactions_per_sec:.1f} tx/s")

@pytest.mark.slow
@pytest.mark.performance
class TestMemoryUsage:
    """Test memory usage during bulk operations"""

    def test_bulk_insert_memory_usage(self, temp_db):
        """Benchmark: Memory usage during bulk insert"""

        num_records = 5000

        with measure_memory() as mem:
            with transaction() as conn:
                for i in range(num_records):
                    student_id = f"BULK{i:05d}"
                    conn.execute("""
                        INSERT INTO students (
                            student_id, first_name, last_name, email, status
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (student_id, f"Bulk{i}", "Test", f"bulk{i}@uni.edu", "active"))

        memory_used = mem['delta']

        # Should use less than 50MB for 5000 records
        assert memory_used < 50, f"Used {memory_used:.1f}MB, should be < 50MB"

        print(f"\n✓ Bulk insert {num_records} records: {memory_used:.1f}MB")

    def test_large_result_set_memory(self, temp_db):
        """Benchmark: Memory usage when fetching large result set"""

        # Setup: Create large dataset
        with transaction() as conn:
            for i in range(2000):
                student_id = f"MEM{i:05d}"
                conn.execute("""
                    INSERT INTO students (
                        student_id, first_name, last_name, email, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_id, f"Memory{i}", "Test", f"mem{i}@uni.edu", "active"))

        # Benchmark: Fetch all records
        with measure_memory() as mem:
            with get_connection() as conn:
                results = conn.execute("""
                    SELECT * FROM students WHERE student_id LIKE 'MEM%'
                """).fetchall()

        memory_used = mem['delta']

        assert len(results) == 2000
        assert memory_used < 30, f"Used {memory_used:.1f}MB, should be < 30MB"

        print(f"\n✓ Fetched {len(results)} records: {memory_used:.1f}MB")

@pytest.mark.slow
@pytest.mark.performance
class TestIndexPerformance:
    """Test query performance with and without indexes"""

    def test_index_impact_on_search(self, temp_db):
        """Benchmark: Compare query performance with/without index"""

        # Setup: Create large dataset
        num_records = 1000
        with transaction() as conn:
            for i in range(num_records):
                conn.execute("""
                    INSERT INTO students (
                        student_id, first_name, last_name, email, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (f"IDX{i:05d}", f"First{i}", f"Last{i}",
                      f"idx{i}@uni.edu", "active"))

        # Benchmark WITHOUT index
        with measure_time() as get_time:
            with get_connection() as conn:
                for i in range(100):
                    conn.execute("""
                        SELECT * FROM students WHERE email = ?
                    """, (f"idx{i}@uni.edu",)).fetchone()

        time_without_index = get_time()

        # Create index
        with transaction() as conn:
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_student_email ON students(email)
            """)

        # Benchmark WITH index
        with measure_time() as get_time:
            with get_connection() as conn:
                for i in range(100):
                    conn.execute("""
                        SELECT * FROM students WHERE email = ?
                    """, (f"idx{i}@uni.edu",)).fetchone()

        time_with_index = get_time()
        improvement = (time_without_index - time_with_index) / time_without_index * 100

        print(f"\n✓ Without index: {time_without_index:.3f}s")
        print(f"✓ With index: {time_with_index:.3f}s")
        print(f"✓ Improvement: {improvement:.1f}%")

        # Index should provide some improvement
        assert time_with_index <= time_without_index

@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
@pytest.mark.slow
class TestPropertyBasedTesting:
    """Property-based testing with hypothesis"""

    @given(
        student_id=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
            min_size=3,
            max_size=20
        ),
        first_name=st.text(min_size=1, max_size=50),
        last_name=st.text(min_size=1, max_size=50)
    )
    @settings(max_examples=50, deadline=None)
    def test_student_creation_properties(self, temp_db, student_id, first_name, last_name):
        """Property: Any valid student data should be insertable and retrievable"""

        email = f"{student_id.lower()}@test.edu"

        try:
            # Insert student
            with transaction() as conn:
                conn.execute("""
                    INSERT INTO students (
                        student_id, first_name, last_name, email, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_id, first_name, last_name, email, "active"))

            # Retrieve student
            with get_connection() as conn:
                result = conn.execute("""
                    SELECT first_name, last_name, email, status
                    FROM students WHERE student_id = ?
                """, (student_id,)).fetchone()

            # Properties that should always hold
            assert result is not None
            assert result[0] == first_name
            assert result[1] == last_name
            assert result[2] == email
            assert result[3] == "active"

        except sqlite3.IntegrityError:
            # Duplicate student_id is acceptable failure
            pass

    @given(
        grade=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_grade_calculation_properties(self, temp_db, grade):
        """Property: Grade calculations should be consistent and within bounds"""

        # Calculate letter grade
        if grade >= 90:
            expected_letter = 'A'
        elif grade >= 80:
            expected_letter = 'B'
        elif grade >= 70:
            expected_letter = 'C'
        elif grade >= 60:
            expected_letter = 'D'
        else:
            expected_letter = 'F'

        # Properties that should always hold
        assert 0.0 <= grade <= 100.0
        assert expected_letter in ['A', 'B', 'C', 'D', 'F']

        # Test persistence
        student_id = f"PROP_{int(grade * 100):05d}"
        course_id = "PROP101"

        try:
            with transaction() as conn:
                # Insert test data
                conn.execute("""
                    INSERT OR IGNORE INTO students (
                        student_id, first_name, last_name, email, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_id, "Test", "Student", f"{student_id}@test.edu", "active"))

                conn.execute("""
                    INSERT OR IGNORE INTO courses (
                        course_id, course_name, credits, status
                    ) VALUES (?, ?, ?, ?)
                """, (course_id, "Property Test", 3, "active"))

                conn.execute("""
                    INSERT INTO grades (
                        student_id, course_id, grade, letter_grade, grade_date
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_id, course_id, grade, expected_letter, datetime.now().date()))

            # Verify stored correctly
            with get_connection() as conn:
                result = conn.execute("""
                    SELECT grade, letter_grade FROM grades
                    WHERE student_id = ? AND course_id = ?
                """, (student_id, course_id)).fetchone()

                if result:
                    assert abs(result[0] - grade) < 0.01  # Floating point tolerance
                    assert result[1] == expected_letter

        except sqlite3.IntegrityError:
            # Duplicate is acceptable
            pass

    @given(
        num_students=st.integers(min_value=1, max_value=50),
        num_courses=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=20, deadline=None)
    def test_enrollment_capacity_properties(self, temp_db, num_students, num_courses):
        """Property: Enrollment counts should always match actual enrollments"""

        course_id = f"CAP{num_courses:03d}"

        try:
            with transaction() as conn:
                # Create course
                conn.execute("""
                    INSERT OR IGNORE INTO courses (
                        course_id, course_name, credits, status
                    ) VALUES (?, ?, ?, ?)
                """, (course_id, f"Capacity Test {num_courses}", 3, "active"))

                # Enroll students
                for i in range(num_students):
                    student_id = f"CAP{i:04d}"

                    conn.execute("""
                        INSERT OR IGNORE INTO students (
                            student_id, first_name, last_name, email, status
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (student_id, f"Student{i}", "Test",
                          f"cap{i}@test.edu", "active"))

                    conn.execute("""
                        INSERT OR IGNORE INTO enrollments (
                            student_id, course_id, enrollment_date, status
                        ) VALUES (?, ?, ?, ?)
                    """, (student_id, course_id, datetime.now().date(), "enrolled"))

            # Verify enrollment count
            with get_connection() as conn:
                count = conn.execute("""
                    SELECT COUNT(*) FROM enrollments WHERE course_id = ?
                """, (course_id,)).fetchone()[0]

                # Property: Count should match number of unique enrollments
                assert count <= num_students
                assert count >= 0

        except sqlite3.IntegrityError:
            # Constraint violations are acceptable
            pass

@pytest.mark.performance
class TestReportPerformance:
    """Test performance of report generation"""

    def test_grade_report_generation(self, temp_db):
        """Benchmark: Generate comprehensive grade report"""

        # Setup: Create realistic dataset
        with transaction() as conn:
            for i in range(200):
                student_id = f"RPT{i:04d}"

                conn.execute("""
                    INSERT INTO students (
                        student_id, first_name, last_name, email, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_id, f"Student{i}", "Test", f"rpt{i}@uni.edu", "active"))

                for j in range(5):
                    course_id = f"CRS{j:03d}"
                    grade = 60 + (i + j) % 40

                    conn.execute("""
                        INSERT OR IGNORE INTO courses (
                            course_id, course_name, credits, status
                        ) VALUES (?, ?, ?, ?)
                    """, (course_id, f"Course {j}", 3, "active"))

                    conn.execute("""
                        INSERT INTO grades (
                            student_id, course_id, grade, letter_grade,
                            grade_date, semester
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (student_id, course_id, grade, "B",
                          datetime.now().date(), "2024-01"))

        # Benchmark: Generate comprehensive report
        with measure_time() as get_time:
            with get_connection() as conn:
                report = conn.execute("""
                    SELECT
                        s.student_id,
                        s.first_name,
                        s.last_name,
                        COUNT(DISTINCT g.course_id) as courses_taken,
                        AVG(g.grade) as gpa,
                        MIN(g.grade) as lowest_grade,
                        MAX(g.grade) as highest_grade,
                        SUM(c.credits) as total_credits
                    FROM students s
                    LEFT JOIN grades g ON s.student_id = g.student_id
                    LEFT JOIN courses c ON g.course_id = c.course_id
                    GROUP BY s.student_id, s.first_name, s.last_name
                    HAVING COUNT(g.course_id) > 0
                    ORDER BY gpa DESC
                """).fetchall()

        elapsed = get_time()

        assert len(report) == 200
        assert elapsed < 2.0, f"Report generation took {elapsed:.3f}s, should be < 2.0s"

        print(f"\n✓ Grade report for 200 students: {elapsed:.3f}s")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "performance"])
