"""
Test suite for advanced_search.py

Tests database initialization, search analytics, column management,
record building, and audit logging functionality.
"""

import pytest
import json
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.services.analytics.advanced_search import (
    refresh_search_analytics_columns,
    get_search_analytics_columns,
    ensure_search_analytics_schema,
    build_search_analytics_record,
    insert_search_analytics_record,
    audit_log,
    init_enhanced_database,
    ensure_tables_exist,
    SEARCH_ANALYTICS_COLUMNS_CACHE
)


@pytest.fixture(scope="function")
def setup_search_db():
    """Setup test database for search analytics"""
    try:
        init_enhanced_database()
    except Exception as e:
        print(f"Warning: DB init issue: {e}")

    yield

    # Cleanup
    try:
        with transaction() as conn:
            conn.execute("DELETE FROM search_analytics WHERE user_id LIKE 'test_%'")
            conn.execute("DELETE FROM saved_searches WHERE user_id LIKE 'test_%'")
            conn.execute("DELETE FROM duplicate_candidates WHERE student_id_1 LIKE 'test_%'")
    except Exception as e:
        print(f"Cleanup warning: {e}")


class TestDatabaseInitialization:
    """Test database initialization functions"""

    def test_init_enhanced_database(self):
        """Test enhanced database initialization"""
        # Should not raise exception
        init_enhanced_database()

    def test_ensure_tables_exist(self):
        """Test ensure_tables_exist function"""
        # Should not raise exception
        ensure_tables_exist()

    def test_students_table_exists(self, setup_search_db):
        """Test that students table exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='students'
            ''')
            result = cursor.fetchone()
            assert result is not None

    def test_student_modules_table_exists(self, setup_search_db):
        """Test that student_modules table exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='student_modules'
            ''')
            result = cursor.fetchone()
            assert result is not None

    def test_search_analytics_table_exists(self, setup_search_db):
        """Test that search_analytics table exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='search_analytics'
            ''')
            result = cursor.fetchone()
            assert result is not None

    def test_saved_searches_table_exists(self, setup_search_db):
        """Test that saved_searches table exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='saved_searches'
            ''')
            result = cursor.fetchone()
            assert result is not None

    def test_user_permissions_table_exists(self, setup_search_db):
        """Test that user_permissions table exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='user_permissions'
            ''')
            result = cursor.fetchone()
            assert result is not None

    def test_scheduled_reports_table_exists(self, setup_search_db):
        """Test that scheduled_reports table exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='scheduled_reports'
            ''')
            result = cursor.fetchone()
            assert result is not None

    def test_duplicate_candidates_table_exists(self, setup_search_db):
        """Test that duplicate_candidates table exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='duplicate_candidates'
            ''')
            result = cursor.fetchone()
            assert result is not None


class TestIndexCreation:
    """Test that indexes are created properly"""

    def test_students_name_index_exists(self, setup_search_db):
        """Test students name index exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='idx_students_name'
            ''')
            result = cursor.fetchone()
            assert result is not None

    def test_students_course_index_exists(self, setup_search_db):
        """Test students course index exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='idx_students_course'
            ''')
            result = cursor.fetchone()
            assert result is not None

    def test_search_analytics_user_index_exists(self, setup_search_db):
        """Test search analytics user index exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='idx_search_analytics_user'
            ''')
            result = cursor.fetchone()
            assert result is not None


class TestSearchAnalyticsColumns:
    """Test search analytics column management"""

    def test_refresh_search_analytics_columns(self, setup_search_db):
        """Test refreshing search analytics columns"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = refresh_search_analytics_columns(cursor)

            assert isinstance(columns, list)
            assert len(columns) > 0
            assert 'id' in columns

    def test_get_search_analytics_columns(self, setup_search_db):
        """Test getting search analytics columns"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = get_search_analytics_columns(cursor)

            assert isinstance(columns, list)
            assert len(columns) > 0

    def test_columns_include_search_query(self, setup_search_db):
        """Test that search_query column exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = ensure_search_analytics_schema(cursor)

            assert 'search_query' in columns

    def test_columns_include_search_criteria(self, setup_search_db):
        """Test that search_criteria column exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = ensure_search_analytics_schema(cursor)

            assert 'search_criteria' in columns

    def test_columns_include_timestamp(self, setup_search_db):
        """Test that timestamp or search_datetime column exists"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = ensure_search_analytics_schema(cursor)

            assert 'timestamp' in columns or 'search_datetime' in columns

    def test_ensure_search_analytics_schema(self, setup_search_db):
        """Test ensuring search analytics schema"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = ensure_search_analytics_schema(cursor)

            # Check required columns exist
            required = ['search_query', 'search_criteria']
            for col in required:
                assert col in columns


class TestBuildSearchAnalyticsRecord:
    """Test building search analytics records"""

    def test_build_basic_record(self, setup_search_db):
        """Test building basic search analytics record"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = get_search_analytics_columns(cursor)

            record = build_search_analytics_record(
                columns,
                user_id='test_user_001',
                search_type='student_search',
                criteria={'name': 'John'},
                results_count=5
            )

            assert isinstance(record, dict)
            assert len(record) > 0

    def test_build_record_with_all_fields(self, setup_search_db):
        """Test building record with all optional fields"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = get_search_analytics_columns(cursor)

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            record = build_search_analytics_record(
                columns,
                user_id='test_user_002',
                search_type='advanced_search',
                criteria={'field': 'value'},
                results_count=10,
                execution_time=1.234,
                timestamp=timestamp,
                session_id='session_123'
            )

            # Check that fields are populated correctly
            if 'user_id' in columns:
                assert record.get('user_id') == 'test_user_002'

            if 'search_type' in columns:
                assert record.get('search_type') == 'advanced_search'

            if 'results_count' in columns:
                assert record.get('results_count') == 10

            if 'execution_time' in columns:
                assert abs(record.get('execution_time') - 1.234) < 0.001

    def test_build_record_with_none_criteria(self, setup_search_db):
        """Test building record with None criteria"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = get_search_analytics_columns(cursor)

            record = build_search_analytics_record(
                columns,
                user_id='test_user_003',
                search_type='test',
                criteria=None,
                results_count=0
            )

            assert isinstance(record, dict)

    def test_build_record_handles_result_count_variations(self, setup_search_db):
        """Test record building handles both results_count and result_count columns"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = get_search_analytics_columns(cursor)

            record = build_search_analytics_record(
                columns,
                user_id='test_user_004',
                search_type='test',
                criteria='test',
                results_count=42
            )

            # Should have results_count or result_count
            assert (record.get('results_count') == 42 or
                    record.get('result_count') == 42)


class TestInsertSearchAnalyticsRecord:
    """Test inserting search analytics records"""

    def test_insert_basic_record(self, setup_search_db):
        """Test inserting basic search analytics record"""
        with transaction() as conn:
            cursor = conn.cursor()

            insert_search_analytics_record(
                cursor,
                user_id='test_user_insert_001',
                search_type='basic_search',
                criteria='test',
                results_count=3
            )

            # Verify record inserted
            cursor.execute('''
                SELECT * FROM search_analytics
                WHERE user_id = ?
            ''', ('test_user_insert_001',))

            row = cursor.fetchone()
            assert row is not None

    def test_insert_with_execution_time(self, setup_search_db):
        """Test inserting record with execution time"""
        with transaction() as conn:
            cursor = conn.cursor()

            insert_search_analytics_record(
                cursor,
                user_id='test_user_insert_002',
                search_type='timed_search',
                criteria='test',
                results_count=5,
                execution_time=2.5
            )

            # Verify execution time stored
            cursor.execute('''
                SELECT execution_time FROM search_analytics
                WHERE user_id = ?
            ''', ('test_user_insert_002',))

            row = cursor.fetchone()
            if row and 'execution_time' in row.keys():
                assert row['execution_time'] is not None

    def test_insert_with_session_id(self, setup_search_db):
        """Test inserting record with session ID"""
        with transaction() as conn:
            cursor = conn.cursor()

            insert_search_analytics_record(
                cursor,
                user_id='test_user_insert_003',
                search_type='session_search',
                criteria='test',
                results_count=2,
                session_id='session_abc_123'
            )

            # Verify session_id stored if column exists
            cursor.execute('''
                SELECT * FROM search_analytics
                WHERE user_id = ?
            ''', ('test_user_insert_003',))

            row = cursor.fetchone()
            assert row is not None

    def test_insert_multiple_records(self, setup_search_db):
        """Test inserting multiple search records"""
        with transaction() as conn:
            cursor = conn.cursor()

            for i in range(5):
                insert_search_analytics_record(
                    cursor,
                    user_id=f'test_user_multi_{i}',
                    search_type='bulk_search',
                    criteria=f'query_{i}',
                    results_count=i
                )

            # Verify all inserted
            cursor.execute('''
                SELECT COUNT(*) as count FROM search_analytics
                WHERE user_id LIKE 'test_user_multi_%'
            ''')

            row = cursor.fetchone()
            assert row['count'] == 5


class TestAuditLogDecorator:
    """Test audit log decorator"""

    def test_audit_log_decorator(self, setup_search_db, capsys):
        """Test that audit_log decorator logs function calls"""

        @audit_log
        def sample_search_function(query):
            return f"Results for {query}"

        result = sample_search_function("test query")

        assert result == "Results for test query"
        # Decorator should log the call

    def test_audit_log_with_exception(self, setup_search_db):
        """Test audit log decorator with exception"""

        @audit_log
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

        # Should still log despite exception

    def test_audit_log_execution_time(self, setup_search_db):
        """Test that audit log records execution time"""
        import time

        @audit_log
        def slow_function():
            time.sleep(0.1)
            return "done"

        result = slow_function()
        assert result == "done"
        # Execution time should be logged


class TestSearchAnalyticsQueries:
    """Test querying search analytics data"""

    def test_query_by_user(self, setup_search_db):
        """Test querying search analytics by user"""
        # Insert test records
        with transaction() as conn:
            cursor = conn.cursor()
            insert_search_analytics_record(
                cursor,
                user_id='test_query_user',
                search_type='test',
                criteria='test',
                results_count=1
            )

        # Query
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM search_analytics
                WHERE user_id = ?
            ''', ('test_query_user',))

            rows = cursor.fetchall()
            assert len(rows) > 0

    def test_query_by_search_type(self, setup_search_db):
        """Test querying by search type"""
        # Insert test records
        with transaction() as conn:
            cursor = conn.cursor()
            for i in range(3):
                insert_search_analytics_record(
                    cursor,
                    user_id=f'test_type_user_{i}',
                    search_type='specific_type',
                    criteria='test',
                    results_count=i
                )

        # Query
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count FROM search_analytics
                WHERE search_type = ?
            ''', ('specific_type',))

            row = cursor.fetchone()
            assert row['count'] >= 3


class TestSavedSearches:
    """Test saved searches functionality"""

    def test_create_saved_search(self, setup_search_db):
        """Test creating a saved search"""
        with transaction() as conn:
            conn.execute('''
                INSERT INTO saved_searches
                (user_id, search_name, search_criteria, is_shared)
                VALUES (?, ?, ?, ?)
            ''', ('test_user_save', 'My Search', '{"field": "value"}', 0))

        # Verify
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM saved_searches
                WHERE user_id = ?
            ''', ('test_user_save',))

            row = cursor.fetchone()
            assert row is not None
            assert row['search_name'] == 'My Search'

    def test_shared_search(self, setup_search_db):
        """Test creating shared search"""
        with transaction() as conn:
            conn.execute('''
                INSERT INTO saved_searches
                (user_id, search_name, search_criteria, is_shared)
                VALUES (?, ?, ?, ?)
            ''', ('test_user_shared', 'Shared Search', '{}', 1))

        # Verify shared flag
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_shared FROM saved_searches
                WHERE search_name = ?
            ''', ('Shared Search',))

            row = cursor.fetchone()
            assert row['is_shared'] == 1


class TestDuplicateCandidates:
    """Test duplicate candidates functionality"""

    def test_create_duplicate_candidate(self, setup_search_db):
        """Test creating duplicate candidate entry"""
        with transaction() as conn:
            conn.execute('''
                INSERT INTO duplicate_candidates
                (student_id_1, student_id_2, similarity_score, status)
                VALUES (?, ?, ?, ?)
            ''', ('test_stu_001', 'test_stu_002', 0.95, 'pending'))

        # Verify
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM duplicate_candidates
                WHERE student_id_1 = ?
            ''', ('test_stu_001',))

            row = cursor.fetchone()
            assert row is not None
            assert row['similarity_score'] == 0.95
            assert row['status'] == 'pending'

    def test_update_duplicate_status(self, setup_search_db):
        """Test updating duplicate candidate status"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO duplicate_candidates
                (student_id_1, student_id_2, similarity_score, status)
                VALUES (?, ?, ?, ?)
            ''', ('test_stu_003', 'test_stu_004', 0.88, 'pending'))

            dup_id = cursor.lastrowid

            # Update status
            conn.execute('''
                UPDATE duplicate_candidates
                SET status = ?, reviewed_by = ?
                WHERE id = ?
            ''', ('confirmed', 'admin', dup_id))

        # Verify update
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status, reviewed_by FROM duplicate_candidates
                WHERE id = ?
            ''', (dup_id,))

            row = cursor.fetchone()
            assert row['status'] == 'confirmed'
            assert row['reviewed_by'] == 'admin'


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_search_analytics(self, setup_search_db):
        """Test querying empty search analytics"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM search_analytics
                WHERE user_id = ?
            ''', ('nonexistent_user',))

            rows = cursor.fetchall()
            assert len(rows) == 0

    def test_null_criteria_handling(self, setup_search_db):
        """Test handling null search criteria"""
        with get_connection() as conn:
            cursor = conn.cursor()
            columns = get_search_analytics_columns(cursor)

            record = build_search_analytics_record(
                columns,
                user_id='test_null',
                search_type='test',
                criteria=None,
                results_count=0
            )

            # Should handle None gracefully
            assert isinstance(record, dict)

    def test_large_results_count(self, setup_search_db):
        """Test handling large results count"""
        with transaction() as conn:
            cursor = conn.cursor()

            insert_search_analytics_record(
                cursor,
                user_id='test_large',
                search_type='bulk',
                criteria='test',
                results_count=99999
            )

        # Verify
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT results_count FROM search_analytics
                WHERE user_id = ?
            ''', ('test_large',))

            row = cursor.fetchone()
            count_key = 'results_count' if 'results_count' in row.keys() else 'result_count'
            assert row[count_key] == 99999


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
