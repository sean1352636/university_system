"""
Tests for student union sustainability/green initiatives module.
Tests carbon footprint tracking, waste reduction, and green transport.
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from education_system.post_18.university_system.modules.domain.student_affairs.student_union.services import sustainability

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
def sample_events():
    """Sample event data for carbon tracking."""
    return [
        (1, 'Tech Conference', 'Tech Society', '2024-11-01', 100),
        (2, 'Music Festival', 'Music Club', '2024-11-05', 200),
    ]

class TestTrackCarbonFootprint:
    """Tests for track_carbon_footprint function."""

    @patch('builtins.input', side_effect=[
        '1',  # Select event
        '20', '5',  # walking: 20 people, 5km
        '30', '3',  # cycling: 30 people, 3km
        '40', '10',  # public_transport: 40 people, 10km
        '10', '15',  # car: 10 people, 15km
        '0', '0',  # taxi: 0
        '3',  # Event duration hours
        '50',  # vegan meals
        '30',  # vegetarian meals
        '20',  # meat meals
        '5',  # waste kg
        'Used reusable materials'  # notes
    ])
    @patch('builtins.print')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.sustainability.auto_award_points')
    def test_track_footprint_success(self, mock_award, mock_print, mock_input,
                                     mock_cursor, mock_conn, sample_events):
        """Test successfully tracking carbon footprint."""
        mock_cursor.fetchall.return_value = sample_events
        mock_cursor.fetchone.side_effect = [
            (0,),  # No existing tracking
        ]

        sustainability.track_carbon_footprint('S12345', mock_cursor, mock_conn)

        # Verify sustainability tracking was created
        assert any('INSERT INTO sustainability_tracking' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_conn.commit.assert_called()
        # Should award points
        mock_award.assert_called()

    @patch('builtins.print')
    def test_track_footprint_no_events(self, mock_print, mock_cursor, mock_conn):
        """Test tracking when no events available."""
        mock_cursor.fetchall.return_value = []

        sustainability.track_carbon_footprint('S12345', mock_cursor, mock_conn)

        # Should indicate no events
        assert any('No recent events' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['999'])
    @patch('builtins.print')
    def test_track_footprint_invalid_selection(self, mock_print, mock_input,
                                               mock_cursor, mock_conn, sample_events):
        """Test invalid event selection."""
        mock_cursor.fetchall.return_value = sample_events

        sustainability.track_carbon_footprint('S12345', mock_cursor, mock_conn)

        # Should indicate invalid selection
        assert any('Invalid' in str(call) for call in mock_print.call_args_list)

class TestWasteReductionTracking:
    """Tests for waste_reduction_tracking function."""

    @patch('builtins.input', side_effect=['1', '1', '10', '8'])
    @patch('builtins.print')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.sustainability.auto_award_points')
    def test_log_waste_data_success(self, mock_award, mock_print, mock_input,
                                    mock_cursor, mock_conn):
        """Test logging waste data successfully."""
        mock_cursor.fetchall.return_value = [
            (1, 'Test Event', '2024-11-15')
        ]
        mock_cursor.rowcount = 0  # No existing record

        sustainability.waste_reduction_tracking('S12345', mock_cursor, mock_conn)

        # Should insert waste data
        assert any('INSERT INTO sustainability_tracking' in str(call)
                  for call in mock_cursor.execute.call_args_list)
        mock_award.assert_called()

    @patch('builtins.input', side_effect=['2'])
    @patch('builtins.print')
    def test_view_waste_statistics(self, mock_print, mock_input, mock_cursor, mock_conn):
        """Test viewing waste statistics."""
        mock_cursor.fetchone.return_value = (10, 500.0, 400.0, 80.0)
        mock_cursor.fetchall.return_value = [
            ('2024-11', 100.0, 80.0),
            ('2024-10', 150.0, 120.0),
        ]

        sustainability.waste_reduction_tracking('S12345', mock_cursor, mock_conn)

        # Should display statistics
        assert any('Statistics' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['3'])
    @patch('builtins.print')
    def test_waste_reduction_challenges(self, mock_print, mock_input, mock_cursor, mock_conn):
        """Test viewing waste reduction challenges."""
        sustainability.waste_reduction_tracking('S12345', mock_cursor, mock_conn)

        # Should display challenges
        assert any('Challenges' in str(call) or 'Zero Waste' in str(call)
                  for call in mock_print.call_args_list)

class TestGreenTransportTracking:
    """Tests for green_transport_tracking function."""

    @patch('builtins.input', side_effect=['1', '1', '5'])  # Log walking 5km
    @patch('builtins.print')
    @patch('education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.sustainability.auto_award_points')
    def test_log_sustainable_transport(self, mock_award, mock_print, mock_input,
                                       mock_cursor, mock_conn):
        """Test logging sustainable transport."""
        sustainability.green_transport_tracking('S12345', mock_cursor, mock_conn)

        # Should award points for green transport
        mock_award.assert_called()
        # Should show carbon saved
        assert any('Carbon saved' in str(call) or 'saved' in str(call).lower()
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['2'])
    @patch('builtins.print')
    def test_view_transport_challenges(self, mock_print, mock_input, mock_cursor, mock_conn):
        """Test viewing transport challenges."""
        sustainability.green_transport_tracking('S12345', mock_cursor, mock_conn)

        # Should display challenges
        assert any('Challenges' in str(call) or 'Bike to Work' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['4'])
    @patch('builtins.print')
    def test_view_public_transport_info(self, mock_print, mock_input, mock_cursor, mock_conn):
        """Test viewing public transport information."""
        sustainability.green_transport_tracking('S12345', mock_cursor, mock_conn)

        # Should display transport info
        assert any('Bus routes' in str(call) or 'Transport' in str(call)
                  for call in mock_print.call_args_list)

class TestViewEcoSuppliers:
    """Tests for view_eco_suppliers function."""

    @patch('builtins.print')
    def test_display_eco_suppliers(self, mock_print, mock_cursor):
        """Test displaying eco-friendly suppliers."""
        sustainability.view_eco_suppliers(mock_cursor)

        # Should display supplier information
        assert any('Supplier' in str(call) or 'Green Events' in str(call)
                  for call in mock_print.call_args_list)
        # Should show certifications
        assert any('Certification' in str(call) or 'Organic' in str(call)
                  for call in mock_print.call_args_list)

class TestGreenCertificationSystem:
    """Tests for green_certification_system function."""

    @patch('builtins.input', side_effect=['1'])
    @patch('builtins.print')
    def test_event_certification_levels(self, mock_print, mock_input,
                                        mock_cursor, mock_conn):
        """Test displaying event certification levels."""
        sustainability.green_certification_system('S12345', mock_cursor, mock_conn)

        # Should show certification levels
        assert any('Bronze' in str(call) or 'Silver' in str(call) or 'Gold' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['2'])
    @patch('builtins.print')
    def test_club_sustainability_rating(self, mock_print, mock_input,
                                        mock_cursor, mock_conn):
        """Test club sustainability rating."""
        mock_cursor.fetchall.return_value = [
            ('Green Club', 92.5, 5),
            ('Eco Society', 85.0, 4),
        ]

        sustainability.green_certification_system('S12345', mock_cursor, mock_conn)

        # Should show club rankings
        assert any('Rankings' in str(call) or 'Green Club' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['3'])
    @patch('builtins.print')
    def test_individual_eco_champion_status(self, mock_print, mock_input,
                                            mock_cursor, mock_conn):
        """Test individual eco-champion status."""
        mock_cursor.fetchone.return_value = (150,)  # 150 green points

        sustainability.green_certification_system('S12345', mock_cursor, mock_conn)

        # Should show eco-champion status
        assert any('Eco-Champion' in str(call) or 'status' in str(call).lower()
                  for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['4'])
    @patch('builtins.print')
    def test_certification_standards(self, mock_print, mock_input,
                                     mock_cursor, mock_conn):
        """Test viewing certification standards."""
        sustainability.green_certification_system('S12345', mock_cursor, mock_conn)

        # Should show standards
        assert any('Standards' in str(call) or 'Carbon footprint' in str(call)
                  for call in mock_print.call_args_list)

class TestIntegrationSustainability:
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
            CREATE TABLE student_clubs (
                club_id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_name TEXT,
                president_id TEXT,
                treasurer_id TEXT,
                secretary_id TEXT,
                FOREIGN KEY (president_id) REFERENCES students(student_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE union_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                organizer_id INTEGER,
                event_date TEXT,
                current_attendees INTEGER,
                FOREIGN KEY (organizer_id) REFERENCES student_clubs(club_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE sustainability_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                carbon_footprint REAL,
                sustainability_score REAL,
                waste_generated REAL,
                waste_recycled REAL,
                notes TEXT,
                recorded_date TEXT,
                FOREIGN KEY (event_id) REFERENCES union_events(event_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE student_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                points_earned INTEGER,
                activity_type TEXT,
                activity_description TEXT,
                earned_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')

        # Insert test data
        cursor.execute("INSERT INTO students VALUES (?, ?, ?)", ('S12345', 'John', 'Doe'))
        cursor.execute("INSERT INTO student_clubs VALUES (?, ?, ?, ?, ?)",
                      (1, 'Green Club', 'S12345', 'S12345', 'S12345'))
        cursor.execute("INSERT INTO union_events VALUES (?, ?, ?, ?, ?)",
                      (1, 'Eco Fair', 1, '2024-11-20', 100))

        conn.commit()
        yield conn
        conn.close()

    def test_carbon_footprint_integration(self, db_conn):
        """Test carbon footprint tracking with real database."""
        cursor = db_conn.cursor()

        # Insert sustainability tracking
        cursor.execute('''
            INSERT INTO sustainability_tracking (
                event_id, carbon_footprint, sustainability_score, notes, recorded_date
            ) VALUES (?, ?, ?, ?, ?)
        ''', (1, 150.5, 75.0, 'Good event', '2024-11-20 10:00:00'))

        db_conn.commit()

        # Verify data was inserted
        cursor.execute('SELECT * FROM sustainability_tracking WHERE event_id = ?', (1,))
        row = cursor.fetchone()
        assert row is not None
        assert row[2] == 150.5  # carbon_footprint
        assert row[3] == 75.0   # sustainability_score

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
