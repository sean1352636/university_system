import pytest
from university_system.infrastructure.database.db import sqlite3
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from university_system.modules.domain.academics.grading.common_utilities import (
    _table_exists,
    _cols,
    _first_table,
    _first_col,
    select_assessment
)

class TestTableExists:
    """Test the _table_exists function"""

    def test_table_exists_true(self):
        """Test when table exists"""
        cursor = Mock()
        cursor.execute.return_value.fetchone.return_value = (1,)

        result = _table_exists(cursor, 'students')

        assert result is True
        cursor.execute.assert_called_once()

    def test_table_exists_false(self):
        """Test when table doesn't exist"""
        cursor = Mock()
        cursor.execute.return_value.fetchone.return_value = None

        result = _table_exists(cursor, 'nonexistent_table')

        assert result is False

    def test_table_exists_exception(self):
        """Test when database query raises exception"""
        cursor = Mock()
        cursor.execute.side_effect = Exception("Database error")

        result = _table_exists(cursor, 'students')

        assert result is False

class TestCols:
    """Test the _cols function"""

    def test_cols_success(self):
        """Test getting column names successfully"""
        cursor = Mock()
        cursor.execute.return_value.fetchall.return_value = [
            (0, 'student_id', 'TEXT', 0, None, 1),
            (1, 'first_name', 'TEXT', 0, None, 0),
            (2, 'last_name', 'TEXT', 0, None, 0),
        ]

        result = _cols(cursor, 'students')

        assert result == {'student_id', 'first_name', 'last_name'}

    def test_cols_empty_table(self):
        """Test with table that has no columns (shouldn't happen in practice)"""
        cursor = Mock()
        cursor.execute.return_value.fetchall.return_value = []

        result = _cols(cursor, 'empty_table')

        assert result == set()

    def test_cols_exception(self):
        """Test when database query raises exception"""
        cursor = Mock()
        cursor.execute.side_effect = Exception("Database error")

        result = _cols(cursor, 'students')

        assert result == set()

class TestFirstTable:
    """Test the _first_table function"""

    @patch('university_system.modules.domain.academics.grading.common_utilities._table_exists')
    def test_first_table_finds_first(self, mock_exists):
        """Test finding the first existing table"""
        mock_exists.side_effect = [True, False, False]  # First table exists
        cursor = Mock()

        result = _first_table(cursor, ['assessments', 'exams', 'tests'])

        assert result == 'assessments'

    @patch('university_system.modules.domain.academics.grading.common_utilities._table_exists')
    def test_first_table_finds_middle(self, mock_exists):
        """Test finding a table in the middle of the list"""
        mock_exists.side_effect = [False, True, False]  # Second table exists
        cursor = Mock()

        result = _first_table(cursor, ['assessments', 'exams', 'tests'])

        assert result == 'exams'

    @patch('university_system.modules.domain.academics.grading.common_utilities._table_exists')
    def test_first_table_none_exist(self, mock_exists):
        """Test when no tables exist"""
        mock_exists.return_value = False
        cursor = Mock()

        result = _first_table(cursor, ['assessments', 'exams', 'tests'])

        assert result is None

    @patch('university_system.modules.domain.academics.grading.common_utilities._table_exists')
    def test_first_table_empty_list(self, mock_exists):
        """Test with empty candidate list"""
        cursor = Mock()

        result = _first_table(cursor, [])

        assert result is None
        mock_exists.assert_not_called()

class TestFirstCol:
    """Test the _first_col function"""

    @patch('university_system.modules.domain.academics.grading.common_utilities._cols')
    def test_first_col_finds_first(self, mock_cols):
        """Test finding the first existing column"""
        mock_cols.return_value = {'assessment_id', 'name', 'date'}
        cursor = Mock()

        result = _first_col(cursor, 'assessments', ['assessment_id', 'id', 'exam_id'])

        assert result == 'assessment_id'

    @patch('university_system.modules.domain.academics.grading.common_utilities._cols')
    def test_first_col_finds_middle(self, mock_cols):
        """Test finding a column in the middle of the list"""
        mock_cols.return_value = {'id', 'name', 'date'}
        cursor = Mock()

        result = _first_col(cursor, 'assessments', ['assessment_id', 'id', 'exam_id'])

        assert result == 'id'

    @patch('university_system.modules.domain.academics.grading.common_utilities._cols')
    def test_first_col_none_exist(self, mock_cols):
        """Test when no columns exist"""
        mock_cols.return_value = {'other_col', 'another_col'}
        cursor = Mock()

        result = _first_col(cursor, 'assessments', ['assessment_id', 'id', 'exam_id'])

        assert result is None

    @patch('university_system.modules.domain.academics.grading.common_utilities._cols')
    def test_first_col_empty_candidates(self, mock_cols):
        """Test with empty candidate list"""
        mock_cols.return_value = {'assessment_id', 'name'}
        cursor = Mock()

        result = _first_col(cursor, 'assessments', [])

        assert result is None

class TestSelectAssessment:
    """Test the select_assessment function"""

    @pytest.fixture
    def mock_cursor_with_assessments(self):
        """Create mock cursor with assessment data"""
        cursor = Mock()
        cursor.execute.return_value.fetchall.return_value = [
            (1, 'Midterm Exam', '2025-01-15'),
            (2, 'Final Exam', '2025-02-20'),
            (3, 'Quiz 1', '2025-01-10'),
        ]
        return cursor

    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_col')
    @patch('builtins.input', return_value='1')
    def test_select_assessment_valid_choice(
        self, mock_input, mock_first_col, mock_first_table, mock_cursor_with_assessments
    ):
        """Test selecting a valid assessment"""
        mock_first_table.return_value = 'assessments'
        mock_first_col.side_effect = ['assessment_id', 'name', 'date']

        result = select_assessment(cursor=mock_cursor_with_assessments)

        assert result is not None
        assert result['id'] == 1
        assert result['name'] == 'Midterm Exam'
        assert result['date'] == '2025-01-15'
        assert result['table'] == 'assessments'

    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    def test_select_assessment_no_table(self, mock_first_table):
        """Test when no assessments table exists"""
        mock_first_table.return_value = None
        cursor = Mock()

        with patch('builtins.print') as mock_print:
            result = select_assessment(cursor=cursor)

        assert result is None
        mock_print.assert_called()

    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_col')
    def test_select_assessment_missing_columns(
        self, mock_first_col, mock_first_table
    ):
        """Test when required columns are missing"""
        mock_first_table.return_value = 'assessments'
        mock_first_col.side_effect = [None, None]  # No id or name column
        cursor = Mock()

        with patch('builtins.print') as mock_print:
            result = select_assessment(cursor=cursor)

        assert result is None
        mock_print.assert_called()

    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_col')
    def test_select_assessment_no_assessments(
        self, mock_first_col, mock_first_table
    ):
        """Test when no assessments are available"""
        mock_first_table.return_value = 'assessments'
        mock_first_col.side_effect = ['assessment_id', 'name', 'date']

        cursor = Mock()
        cursor.execute.return_value.fetchall.return_value = []

        with patch('builtins.print') as mock_print:
            result = select_assessment(cursor=cursor)

        assert result is None
        mock_print.assert_called_with("No assessments available.")

    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_col')
    @patch('builtins.input', return_value='q')
    def test_select_assessment_cancel(
        self, mock_input, mock_first_col, mock_first_table, mock_cursor_with_assessments
    ):
        """Test cancelling assessment selection"""
        mock_first_table.return_value = 'assessments'
        mock_first_col.side_effect = ['assessment_id', 'name', 'date']

        result = select_assessment(
            cursor=mock_cursor_with_assessments,
            allow_cancel=True
        )

        assert result is None

    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_col')
    @patch('builtins.input', side_effect=['invalid', '1'])
    def test_select_assessment_invalid_then_valid(
        self, mock_input, mock_first_col, mock_first_table, mock_cursor_with_assessments
    ):
        """Test invalid input followed by valid input"""
        mock_first_table.return_value = 'assessments'
        mock_first_col.side_effect = ['assessment_id', 'name', 'date']

        with patch('builtins.print'):
            result = select_assessment(cursor=mock_cursor_with_assessments)

        assert result is not None
        assert result['id'] == 1

    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_col')
    @patch('builtins.input', side_effect=['0', '1'])
    def test_select_assessment_out_of_range(
        self, mock_input, mock_first_col, mock_first_table, mock_cursor_with_assessments
    ):
        """Test out of range selection"""
        mock_first_table.return_value = 'assessments'
        mock_first_col.side_effect = ['assessment_id', 'name', 'date']

        with patch('builtins.print'):
            result = select_assessment(cursor=mock_cursor_with_assessments)

        assert result is not None
        assert result['id'] == 1

    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_col')
    @patch('builtins.input', return_value='3')
    def test_select_assessment_last_item(
        self, mock_input, mock_first_col, mock_first_table, mock_cursor_with_assessments
    ):
        """Test selecting the last assessment"""
        mock_first_table.return_value = 'assessments'
        mock_first_col.side_effect = ['assessment_id', 'name', 'date']

        result = select_assessment(cursor=mock_cursor_with_assessments)

        assert result is not None
        assert result['id'] == 3
        assert result['name'] == 'Quiz 1'

    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_col')
    @patch('builtins.input', return_value='1')
    def test_select_assessment_without_date_column(
        self, mock_input, mock_first_col, mock_first_table
    ):
        """Test when assessment table has no date column"""
        mock_first_table.return_value = 'assessments'
        mock_first_col.side_effect = ['assessment_id', 'name', None]  # No date column

        cursor = Mock()
        cursor.execute.return_value.fetchall.return_value = [
            (1, 'Midterm Exam'),
            (2, 'Final Exam'),
        ]

        result = select_assessment(cursor=cursor)

        assert result is not None
        assert result['id'] == 1
        assert result['date'] is None

    @patch('university_system.modules.domain.academics.grading.common_utilities.get_connection')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_table')
    @patch('university_system.modules.domain.academics.grading.common_utilities._first_col')
    @patch('builtins.input', return_value='1')
    def test_select_assessment_with_connection_management(
        self, mock_input, mock_first_col, mock_first_table, mock_get_conn
    ):
        """Test that connection is properly managed when not provided"""
        mock_first_table.return_value = 'assessments'
        mock_first_col.side_effect = ['assessment_id', 'name', 'date']

        conn = Mock()
        cursor = Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor
        cursor.execute.return_value.fetchall.return_value = [
            (1, 'Midterm Exam', '2025-01-15'),
        ]

        result = select_assessment()

        assert result is not None
        conn.close.assert_called_once()

class TestIntegration:
    """Integration tests for common utilities"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with test data"""
        db_path = tempfile.mktemp(suffix='.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create assessments table
        cursor.execute('''
            CREATE TABLE assessments (
                assessment_id INTEGER PRIMARY KEY,
                assessment_name TEXT,
                module_code TEXT,
                assessment_date TEXT
            )
        ''')

        # Insert test data
        cursor.execute(
            "INSERT INTO assessments VALUES (1, 'Midterm', 'CS101', '2025-01-15')"
        )
        cursor.execute(
            "INSERT INTO assessments VALUES (2, 'Final', 'CS101', '2025-02-20')"
        )

        conn.commit()

        yield conn

        conn.close()
        os.unlink(db_path)

    def test_table_exists_integration(self, temp_db):
        """Test _table_exists with real database"""
        cursor = temp_db.cursor()

        assert _table_exists(cursor, 'assessments') is True
        assert _table_exists(cursor, 'nonexistent') is False

    def test_cols_integration(self, temp_db):
        """Test _cols with real database"""
        cursor = temp_db.cursor()

        columns = _cols(cursor, 'assessments')

        assert 'assessment_id' in columns
        assert 'assessment_name' in columns
        assert 'module_code' in columns
        assert 'assessment_date' in columns

    def test_first_table_integration(self, temp_db):
        """Test _first_table with real database"""
        cursor = temp_db.cursor()

        result = _first_table(cursor, ['exams', 'assessments', 'tests'])

        assert result == 'assessments'

    def test_first_col_integration(self, temp_db):
        """Test _first_col with real database"""
        cursor = temp_db.cursor()

        result = _first_col(
            cursor,
            'assessments',
            ['id', 'assessment_id', 'exam_id']
        )

        assert result == 'assessment_id'

    @patch('builtins.input', return_value='1')
    def test_select_assessment_integration(self, mock_input, temp_db):
        """Test select_assessment with real database"""
        cursor = temp_db.cursor()

        result = select_assessment(cursor=cursor, allow_cancel=False)

        assert result is not None
        assert result['id'] == 1
        assert result['name'] == 'Midterm'
        assert result['table'] == 'assessments'
        assert result['id_col'] == 'assessment_id'
        assert result['name_col'] == 'assessment_name'

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
