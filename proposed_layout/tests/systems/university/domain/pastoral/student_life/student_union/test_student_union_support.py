"""
Tests for student union support systems module.
Tests peer support, academic support, and related functionality.
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from education_system.systems.university.domain.pastoral.student_life.student_union.services import support
from education_system.systems.university.infrastructure.database.db import get_connection

@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = Mock()
    cursor.fetchall = Mock(return_value=[])
    cursor.fetchone = Mock(return_value=None)
    cursor.execute = Mock()
    cursor.lastrowid = 1
    cursor.rowcount = 1
    return cursor

@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = Mock()
    conn.commit = Mock()
    conn.rollback = Mock()
    conn.close = Mock()
    return conn

@pytest.fixture
def mock_context():
    """Mock the context module."""
    ctx = Mock()
    ctx.auth = Mock()
    ctx.auth.current_user = {'id': 1, 'username': 'testuser'}
    ctx.auth.check_permission = Mock(return_value=False)
    return ctx

@pytest.fixture
def sample_support_groups():
    """Sample support group data."""
    return [
        (1, 'Stress Management', 'Group for managing academic stress', 'Academic Stress',
         'Jane', 'Doe', 5, 10, 'Thursdays 5pm', 'active'),
        (2, 'Social Skills', 'Building social confidence', 'Social Anxiety',
         'John', 'Smith', 3, 8, 'Tuesdays 6pm', 'active'),
    ]

@pytest.fixture
def sample_study_groups():
    """Sample study group data."""
    return [
        (1, 'Calculus', 'Integration techniques', 'S12345', 'Alice', 'Brown', 4, 8,
         '3pm-5pm', 'Library Room 1', '2024-12-20', 'open'),
        (2, 'Physics', 'Quantum mechanics', 'S12346', 'Bob', 'Green', 2, 6,
         '4pm-6pm', 'Science Building', '2024-12-22', 'open'),
    ]

class TestBrowseSupportGroups:
    """Tests for browse_support_groups function."""

    @patch('builtins.print')
    def test_browse_with_groups(self, mock_print, mock_cursor, sample_support_groups):
        """Test browsing when support groups exist."""
        mock_cursor.fetchall.return_value = sample_support_groups

        support.browse_support_groups(mock_cursor)

        # Verify groups are displayed
        assert any('Support Groups' in str(call) for call in mock_print.call_args_list)
        assert any('Stress Management' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_browse_no_groups(self, mock_print, mock_cursor):
        """Test browsing when no groups exist."""
        mock_cursor.fetchall.return_value = []

        support.browse_support_groups(mock_cursor)

        # Should indicate no groups available
        assert any('No support groups' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_browse_groups_by_type(self, mock_print, mock_cursor, sample_support_groups):
        """Test that groups are organized by type."""
        mock_cursor.fetchall.return_value = sample_support_groups

        support.browse_support_groups(mock_cursor)

        # Should show support type headers
        assert any('ACADEMIC STRESS' in str(call) or 'SUPPORT' in str(call)
                  for call in mock_print.call_args_list)

class TestJoinSupportGroup:
    """Tests for join_support_group function."""

    @patch('builtins.input', side_effect=['1', 'y'])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.browse_support_groups')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.auto_award_points')
    def test_join_group_success(self, mock_award, mock_browse, mock_print, mock_input,
                                mock_cursor, mock_conn):
        """Test successfully joining a support group."""
        # Mock group data
        mock_cursor.fetchone.side_effect = [
            ('Stress Management', 5, 10, 'active'),  # Group info
            (0,)  # Not already a member
        ]

        support.join_support_group('S12345', mock_cursor, mock_conn)

        # Verify group join was attempted
        assert any('INSERT INTO support_group_members' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_conn.commit.assert_called()
        # Should award points
        mock_award.assert_called_once()

    @patch('builtins.input', side_effect=['999'])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.browse_support_groups')
    def test_join_nonexistent_group(self, mock_browse, mock_print, mock_input,
                                    mock_cursor, mock_conn):
        """Test joining a group that doesn't exist."""
        mock_cursor.fetchone.return_value = None

        support.join_support_group('S12345', mock_cursor, mock_conn)

        # Should indicate group not found
        assert any('not found' in str(call).lower() for call in mock_print.call_args_list)
        mock_conn.commit.assert_not_called()

    @patch('builtins.input', side_effect=['1', 'y'])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.browse_support_groups')
    def test_join_full_group(self, mock_browse, mock_print, mock_input,
                            mock_cursor, mock_conn):
        """Test joining a group that is full."""
        mock_cursor.fetchone.side_effect = [
            ('Full Group', 10, 10, 'active'),  # Group is full
        ]

        support.join_support_group('S12345', mock_cursor, mock_conn)

        # Should indicate group is full
        assert any('full' in str(call).lower() for call in mock_print.call_args_list)
        mock_conn.commit.assert_not_called()

    @patch('builtins.input', side_effect=['1'])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.browse_support_groups')
    def test_join_already_member(self, mock_browse, mock_print, mock_input,
                                mock_cursor, mock_conn):
        """Test joining a group already a member of."""
        mock_cursor.fetchone.side_effect = [
            ('Test Group', 5, 10, 'active'),
            (1,)  # Already a member
        ]

        support.join_support_group('S12345', mock_cursor, mock_conn)

        # Should indicate already a member
        assert any('already a member' in str(call).lower() for call in mock_print.call_args_list)
        mock_conn.commit.assert_not_called()

    @patch('builtins.input', side_effect=['abc'])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.browse_support_groups')
    def test_join_invalid_id(self, mock_browse, mock_print, mock_input,
                            mock_cursor, mock_conn):
        """Test joining with invalid group ID."""
        support.join_support_group('S12345', mock_cursor, mock_conn)

        # Should indicate invalid ID
        assert any('Invalid' in str(call) for call in mock_print.call_args_list)

class TestViewMySupportGroups:
    """Tests for view_my_support_groups function."""

    @patch('builtins.print')
    def test_view_my_groups_with_data(self, mock_print, mock_cursor):
        """Test viewing support groups when student is a member."""
        groups = [
            ('Stress Management', 'Academic Stress', '2024-01-15', 'ABC123',
             'Thursdays 5pm', 'Jane', 'Doe'),
            ('Social Skills', 'Social Anxiety', '2024-02-01', 'XYZ789',
             'Tuesdays 6pm', 'John', 'Smith'),
        ]
        mock_cursor.fetchall.return_value = groups

        support.view_my_support_groups('S12345', mock_cursor)

        # Should display groups
        assert any('Support Groups' in str(call) for call in mock_print.call_args_list)
        assert any('Stress Management' in str(call) for call in mock_print.call_args_list)
        # Should show anonymous IDs
        assert any('ABC123' in str(call) or 'Anonymous ID' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_view_my_groups_no_data(self, mock_print, mock_cursor):
        """Test viewing when not a member of any groups."""
        mock_cursor.fetchall.return_value = []

        support.view_my_support_groups('S12345', mock_cursor)

        # Should indicate no membership
        assert any('not a member' in str(call).lower() for call in mock_print.call_args_list)

class TestCreateSupportGroup:
    """Tests for create_support_group function."""

    @patch('builtins.input', side_effect=[
        'Anxiety Support',  # group name
        'For students dealing with anxiety',  # description
        '1',  # support type choice
        '8',  # max members
        'Wednesdays 4pm'  # meeting schedule
    ])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.auto_award_points')
    def test_create_group_success(self, mock_award, mock_print, mock_input,
                                  mock_cursor, mock_conn):
        """Test successfully creating a support group."""
        mock_cursor.lastrowid = 5

        support.create_support_group('S12345', mock_cursor, mock_conn)

        # Verify group creation
        assert any('INSERT INTO peer_support_groups' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        # Verify facilitator added as member
        assert any('INSERT INTO support_group_members' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_conn.commit.assert_called()
        # Should award points
        mock_award.assert_called_once()

    @patch('builtins.input', side_effect=['', ''])
    @patch('builtins.print')
    def test_create_group_empty_name(self, mock_print, mock_input,
                                     mock_cursor, mock_conn):
        """Test creating group with empty name."""
        support.create_support_group('S12345', mock_cursor, mock_conn)

        # Should reject empty name
        assert any('cannot be empty' in str(call).lower() for call in mock_print.call_args_list)
        mock_conn.commit.assert_not_called()

    @patch('builtins.input', side_effect=[
        'Test Group',
        'Test description',
        '1',
        '25'  # Too many members
    ])
    @patch('builtins.print')
    def test_create_group_invalid_size(self, mock_print, mock_input,
                                       mock_cursor, mock_conn):
        """Test creating group with invalid size."""
        support.create_support_group('S12345', mock_cursor, mock_conn)

        # Should reject invalid size
        assert any('between 3 and 20' in str(call).lower() for call in mock_print.call_args_list)
        mock_conn.commit.assert_not_called()

class TestManageStudyGroups:
    """Tests for manage_study_groups function."""

    @patch('builtins.input', side_effect=['1', '5'])
    @patch('builtins.print')
    def test_browse_study_groups(self, mock_print, mock_input, mock_cursor, mock_conn,
                                 sample_study_groups):
        """Test browsing study groups."""
        mock_cursor.fetchall.return_value = sample_study_groups

        support.manage_study_groups('S12345', mock_cursor, mock_conn)

        # Should display study groups
        assert any('Calculus' in str(call) or 'Physics' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=[
        '2',  # Create study group
        'Mathematics',  # subject
        'Linear Algebra',  # topic
        '3pm-5pm',  # meeting time
        'Library',  # location
        '6',  # max members
        '5'  # exit
    ])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.auto_award_points')
    def test_create_study_group(self, mock_award, mock_print, mock_input,
                                mock_cursor, mock_conn):
        """Test creating a study group."""
        mock_cursor.lastrowid = 10

        support.manage_study_groups('S12345', mock_cursor, mock_conn)

        # Verify study group creation
        assert any('INSERT INTO study_groups' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_award.assert_called()

class TestManagePeerTutoring:
    """Tests for manage_peer_tutoring function."""

    @patch('builtins.input', side_effect=['1', '', '6'])
    @patch('builtins.print')
    def test_browse_tutoring_offers(self, mock_print, mock_input, mock_cursor, mock_conn):
        """Test browsing tutoring offers."""
        offers = [
            (1, 'Mathematics', 'Calculus', 'Alice', 'Brown', 15.00, 'Advanced', 4.5, 10),
            (2, 'Physics', 'Mechanics', 'Bob', 'Green', 0.00, 'Intermediate', 4.0, 5),
        ]
        mock_cursor.fetchall.return_value = offers

        support.manage_peer_tutoring('S12345', mock_cursor, mock_conn)

        # Should display offers
        assert any('Mathematics' in str(call) or 'Physics' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=[
        '2',  # Offer tutoring
        'Computer Science',  # subject
        'Python programming',  # topic
        '20',  # hourly rate
        '3',  # experience level
        'Weekends',  # availability
        'Experienced Python developer',  # description
        '6'  # exit
    ])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.auto_award_points')
    def test_offer_tutoring(self, mock_award, mock_print, mock_input,
                           mock_cursor, mock_conn):
        """Test offering tutoring services."""
        mock_cursor.lastrowid = 15

        support.manage_peer_tutoring('S12345', mock_cursor, mock_conn)

        # Verify tutoring offer creation
        assert any('INSERT INTO tutoring_offers' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_award.assert_called()

class TestManageSharedResources:
    """Tests for manage_shared_resources function."""

    @patch('builtins.input', side_effect=['1', '', '', '6'])
    @patch('builtins.print')
    def test_browse_resources(self, mock_print, mock_input, mock_cursor, mock_conn):
        """Test browsing shared resources."""
        resources = [
            (1, 'Calculus Notes', 'notes', 'Mathematics', 'Alice', 'Brown',
             '2024-01-15', 50, 4.5),
            (2, 'Physics Slides', 'slides', 'Physics', 'Bob', 'Green',
             '2024-01-20', 30, 4.0),
        ]
        mock_cursor.fetchall.return_value = resources

        support.manage_shared_resources('S12345', mock_cursor, mock_conn)

        # Should display resources
        assert any('Calculus' in str(call) or 'Physics' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=[
        '2',  # Upload resource
        'Linear Algebra Summary',  # title
        '1',  # resource type
        'Mathematics',  # subject
        '/path/to/file.pdf',  # file path
        'Comprehensive summary of linear algebra',  # description
        '6'  # exit
    ])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.auto_award_points')
    def test_upload_resource(self, mock_award, mock_print, mock_input,
                            mock_cursor, mock_conn):
        """Test uploading a shared resource."""
        mock_cursor.lastrowid = 20

        support.manage_shared_resources('S12345', mock_cursor, mock_conn)

        # Verify resource upload
        assert any('INSERT INTO shared_resources' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_award.assert_called()

    @patch('builtins.input', side_effect=['4', '5', '6'])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.auto_award_points')
    def test_download_resource(self, mock_award, mock_print, mock_input,
                               mock_cursor, mock_conn):
        """Test downloading a resource."""
        mock_cursor.fetchone.return_value = (
            'Calculus Notes', '/path/to/notes.pdf', 'S99999'  # Different uploader
        )

        support.manage_shared_resources('S12345', mock_cursor, mock_conn)

        # Should update download count
        assert any('UPDATE shared_resources' in str(call) and 'downloads' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        # Should award points to uploader
        mock_award.assert_called()

class TestViewWellnessResources:
    """Tests for view_wellness_resources function."""

    @patch('builtins.print')
    def test_display_wellness_resources(self, mock_print):
        """Test displaying wellness resources."""
        support.view_wellness_resources()

        # Should display various resources
        assert any('Wellness Resources' in str(call) for call in mock_print.call_args_list)
        assert any('CRISIS' in str(call) or '999' in str(call)
                  for call in mock_print.call_args_list)
        assert any('Counselling' in str(call) or 'SUPPORT' in str(call)
                  for call in mock_print.call_args_list)

class TestAnonymousPeerMatching:
    """Tests for anonymous_peer_matching function."""

    @patch('builtins.input', side_effect=['1', 'y'])
    @patch('builtins.print')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.auto_award_points')
    def test_anonymous_matching_signup(self, mock_award, mock_print, mock_input,
                                       mock_cursor, mock_conn):
        """Test signing up for anonymous peer matching."""
        support.anonymous_peer_matching('S12345', mock_cursor, mock_conn)

        # Should confirm signup
        assert any('matching queue' in str(call).lower() for call in mock_print.call_args_list)
        # Should award points
        mock_award.assert_called_once()

    @patch('builtins.input', side_effect=['10'])  # Invalid choice
    @patch('builtins.print')
    def test_anonymous_matching_invalid_choice(self, mock_print, mock_input,
                                               mock_cursor, mock_conn):
        """Test invalid selection in anonymous matching."""
        support.anonymous_peer_matching('S12345', mock_cursor, mock_conn)

        # Should indicate invalid selection
        assert any('Invalid' in str(call) for call in mock_print.call_args_list)

class TestIntegrationSupport:
    """Integration tests using real database."""

    @pytest.fixture
    def db_conn(self):
        """Create a test database connection."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Create required tables
        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE peer_support_groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT,
                description TEXT,
                support_type TEXT,
                facilitator_id TEXT,
                max_members INTEGER,
                current_members INTEGER,
                meeting_schedule TEXT,
                status TEXT,
                created_date TEXT,
                FOREIGN KEY (facilitator_id) REFERENCES students(student_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE support_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                student_id TEXT,
                join_date TEXT,
                anonymous_id TEXT,
                status TEXT,
                FOREIGN KEY (group_id) REFERENCES peer_support_groups(group_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE study_groups (
                study_group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                topic TEXT,
                organizer_id TEXT,
                max_members INTEGER,
                current_members INTEGER,
                meeting_time TEXT,
                location TEXT,
                study_date TEXT,
                status TEXT,
                description TEXT,
                FOREIGN KEY (organizer_id) REFERENCES students(student_id)
            )
        ''')

        # Insert test students
        cursor.execute("INSERT INTO students VALUES (?, ?, ?)", ('S12345', 'John', 'Doe'))
        cursor.execute("INSERT INTO students VALUES (?, ?, ?)", ('S12346', 'Jane', 'Smith'))

        conn.commit()
        yield conn
        conn.close()

    def test_browse_support_groups_integration(self, db_conn):
        """Test browsing support groups with real database."""
        cursor = db_conn.cursor()

        # Insert test support group
        cursor.execute('''
            INSERT INTO peer_support_groups (
                group_name, description, support_type, facilitator_id,
                max_members, current_members, meeting_schedule, status, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Test Group', 'Test description', 'Academic Stress', 'S12345',
              10, 5, 'Thursdays 5pm', 'active', '2024-01-01'))

        db_conn.commit()

        # Browse groups
        cursor.execute('''
            SELECT g.group_id, g.group_name, g.description, g.support_type,
                   s.first_name, s.last_name, g.current_members, g.max_members,
                   g.meeting_schedule, g.status
            FROM peer_support_groups g
            LEFT JOIN students s ON g.facilitator_id = s.student_id
            WHERE g.status = 'active' AND g.current_members < g.max_members
            ORDER BY g.support_type, g.group_name
        ''')

        groups = cursor.fetchall()
        assert len(groups) == 1
        assert groups[0][1] == 'Test Group'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
