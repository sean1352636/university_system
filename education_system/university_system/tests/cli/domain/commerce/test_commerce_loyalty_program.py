"""
Tests for the Commerce Loyalty Program module.
Tests customer creation, viewing, updating, feedback, and loyalty management.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from education_system.university_system.modules.domain.commerce.services.restaurant.customer import loyalty_program

@pytest.fixture
def mock_auth():
    """Create a mock authentication instance."""
    auth = Mock()
    auth.current_user = {
        'id': 'USER001',
        'username': 'testuser',
        'role': 'admin'
    }
    auth.check_permission = Mock(return_value=True)
    auth.is_logged_in = Mock(return_value=True)
    return auth

@pytest.fixture
def mock_db_connection(tmp_path):
    """Create a temporary in-memory database for testing."""
    db_path = tmp_path / "test_restaurant.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create necessary tables
    cursor.execute('''
        CREATE TABLE restaurant_customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            dietary_restrictions TEXT,
            loyalty_points INTEGER DEFAULT 0,
            loyalty_tier TEXT DEFAULT 'Bronze',
            birthday TEXT,
            registration_date TEXT,
            last_visit TEXT,
            total_spent REAL DEFAULT 0,
            visit_count INTEGER DEFAULT 0,
            preferences TEXT,
            address TEXT,
            emergency_contact TEXT,
            notes TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            table_id TEXT,
            order_time TEXT,
            total_price REAL,
            status TEXT,
            payment_method TEXT,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_customer_feedback (
            feedback_id TEXT PRIMARY KEY,
            customer_id TEXT,
            order_id TEXT,
            item_id TEXT,
            rating INTEGER,
            feedback_text TEXT,
            feedback_date TEXT,
            response_text TEXT,
            response_date TEXT,
            category TEXT,
            FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE menu_items (
            item_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            price REAL,
            category TEXT,
            allergens TEXT,
            vegetarian INTEGER DEFAULT 0,
            vegan INTEGER DEFAULT 0,
            available INTEGER DEFAULT 1,
            creation_date TEXT,
            calories INTEGER,
            protein REAL,
            carbs REAL,
            fat REAL,
            prep_time INTEGER,
            cost_price REAL,
            image_url TEXT,
            popularity_score INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_customer_favorites (
            customer_id TEXT,
            item_id TEXT,
            frequency INTEGER DEFAULT 1,
            last_ordered TEXT,
            PRIMARY KEY (customer_id, item_id),
            FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id),
            FOREIGN KEY (item_id) REFERENCES menu_items(item_id)
        )
    ''')

    conn.commit()
    return conn

class TestCustomerCreation:
    """Tests for customer creation functionality."""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.get_db_connection')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.backup_before_operation')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.log_audit_action')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.send_confirmation_email')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.render_template')
    @patch('builtins.input')
    def test_create_customer_success(self, mock_input, mock_render, mock_email,
                                     mock_audit, mock_backup, mock_get_conn,
                                     mock_db_connection, mock_auth):
        """Test successful customer creation."""
        # Setup
        loyalty_program.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        mock_render.return_value = ("Welcome", "Welcome message")

        # Mock user inputs
        mock_input.side_effect = [
            'John Doe',  # name
            'john@example.com',  # email
            '1234567890',  # phone
            '2',  # dietary restrictions (Vegetarian)
            '1990-01-15',  # birthday
            '123 Main St',  # address
            'Jane Doe 9876543210'  # emergency contact
        ]

        # Execute
        loyalty_program.create_customer()

        # Verify
        cursor = mock_db_connection.cursor()
        cursor.execute("SELECT * FROM restaurant_customers WHERE name = 'John Doe'")
        customer = cursor.fetchone()

        assert customer is not None
        assert customer[1] == 'John Doe'
        assert customer[2] == 'john@example.com'
        assert customer[6] == 'Bronze'  # loyalty_tier
        assert customer[5] == 0  # loyalty_points
        mock_audit.assert_called_once()
        mock_email.assert_called_once()

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.get_db_connection')
    @patch('builtins.input')
    def test_create_customer_invalid_email(self, mock_input, mock_get_conn,
                                          mock_db_connection, mock_auth, capsys):
        """Test customer creation with invalid email format."""
        # Setup
        loyalty_program.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection

        # Mock user inputs
        mock_input.side_effect = [
            'John Doe',  # name
            'invalid-email',  # invalid email
        ]

        # Execute
        loyalty_program.create_customer()

        # Verify
        captured = capsys.readouterr()
        assert "Invalid email format" in captured.out

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.get_db_connection')
    @patch('builtins.input')
    def test_create_customer_duplicate_email(self, mock_input, mock_get_conn,
                                             mock_db_connection, mock_auth, capsys):
        """Test customer creation with duplicate email."""
        # Setup
        loyalty_program.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection

        # Insert existing customer
        cursor = mock_db_connection.cursor()
        cursor.execute('''
            INSERT INTO restaurant_customers
            (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
             loyalty_tier, birthday, registration_date, last_visit, total_spent,
             visit_count, preferences, address, emergency_contact, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('CUST000001', 'Existing Customer', 'john@example.com', '1234567890',
              'None', 0, 'Bronze', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              None, 0, 0, None, None, None, None))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = [
            'John Doe',  # name
            'john@example.com',  # duplicate email
        ]

        # Execute
        loyalty_program.create_customer()

        # Verify
        captured = capsys.readouterr()
        assert "Email already exists" in captured.out

class TestLoyaltyManagement:
    """Tests for loyalty program management."""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.get_db_connection')
    def test_view_loyalty_tiers(self, mock_get_conn, mock_db_connection, capsys):
        """Test viewing loyalty tier information."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test customers with different tiers
        test_customers = [
            ('CUST000001', 'Bronze Customer', 100, 'Bronze'),
            ('CUST000002', 'Silver Customer', 600, 'Silver'),
            ('CUST000003', 'Gold Customer', 1500, 'Gold'),
            ('CUST000004', 'Platinum Customer', 2500, 'Platinum'),
        ]

        for cust_id, name, points, tier in test_customers:
            cursor.execute('''
                INSERT INTO restaurant_customers
                (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
                 loyalty_tier, birthday, registration_date, last_visit, total_spent,
                 visit_count, preferences, address, emergency_contact, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (cust_id, name, f'{name.lower().replace(" ", "")}@example.com',
                  '1234567890', 'None', points, tier, None,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None, 0, 0,
                  None, None, None, None))
        mock_db_connection.commit()

        # Execute
        loyalty_program.view_loyalty_tiers()

        # Verify
        captured = capsys.readouterr()
        assert "LOYALTY TIER INFORMATION" in captured.out
        assert "Bronze" in captured.out
        assert "Silver" in captured.out
        assert "Gold" in captured.out
        assert "Platinum" in captured.out

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.get_db_connection')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.backup_before_operation')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.log_audit_action')
    @patch('builtins.input')
    def test_update_loyalty_points_add(self, mock_input, mock_audit, mock_backup,
                                       mock_get_conn, mock_db_connection, mock_auth):
        """Test adding loyalty points to customer."""
        # Setup
        loyalty_program.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test customer
        cursor.execute('''
            INSERT INTO restaurant_customers
            (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
             loyalty_tier, birthday, registration_date, last_visit, total_spent,
             visit_count, preferences, address, emergency_contact, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('CUST000001', 'Test Customer', 'test@example.com', '1234567890',
              'None', 400, 'Bronze', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              None, 0, 0, None, None, None, None))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = [
            'CUST000001',  # customer_id
            '1',  # Add points
            '200'  # points to add
        ]

        # Execute
        loyalty_program.update_loyalty_points()

        # Verify
        cursor.execute("SELECT loyalty_points, loyalty_tier FROM restaurant_customers WHERE customer_id = 'CUST000001'")
        points, tier = cursor.fetchone()
        assert points == 600  # 400 + 200
        assert tier == 'Silver'  # Should upgrade from Bronze to Silver
        mock_audit.assert_called_once()

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.get_db_connection')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.backup_before_operation')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.log_audit_action')
    @patch('builtins.input')
    def test_award_bonus_points_to_tier(self, mock_input, mock_audit, mock_backup,
                                        mock_get_conn, mock_db_connection, mock_auth):
        """Test awarding bonus points to all customers in a tier."""
        # Setup
        loyalty_program.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test customers
        for i in range(3):
            cursor.execute('''
                INSERT INTO restaurant_customers
                (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
                 loyalty_tier, birthday, registration_date, last_visit, total_spent,
                 visit_count, preferences, address, emergency_contact, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (f'CUST00000{i+1}', f'Customer {i+1}', f'customer{i+1}@example.com',
                  '1234567890', 'None', 100, 'Bronze', None,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None, 0, 0,
                  None, None, None, None))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = [
            '2',  # Award to all in tier
            '100',  # bonus points
            'Special promotion',  # reason
            'Bronze'  # tier
        ]

        # Execute
        loyalty_program.award_bonus_points()

        # Verify
        cursor.execute("SELECT loyalty_points FROM restaurant_customers WHERE loyalty_tier = 'Bronze'")
        results = cursor.fetchall()
        assert len(results) == 3
        for (points,) in results:
            assert points == 200  # 100 + 100
        mock_audit.assert_called_once()

class TestFeedbackManagement:
    """Tests for customer feedback management."""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.get_db_connection')
    def test_view_recent_feedback(self, mock_get_conn, mock_db_connection, capsys):
        """Test viewing recent customer feedback."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test customer
        cursor.execute('''
            INSERT INTO restaurant_customers
            (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
             loyalty_tier, birthday, registration_date, last_visit, total_spent,
             visit_count, preferences, address, emergency_contact, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('CUST000001', 'Test Customer', 'test@example.com', '1234567890',
              'None', 0, 'Bronze', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              None, 0, 0, None, None, None, None))

        # Add test menu item
        cursor.execute('''
            INSERT INTO menu_items
            (item_id, name, description, price, category, allergens, vegetarian,
             vegan, available, creation_date, calories, protein, carbs, fat,
             prep_time, cost_price, image_url, popularity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('M001', 'Test Item', 'Test Description', 10.99, 'Main', 'None',
              0, 0, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 500,
              20, 30, 10, 15, 5.0, None, 0))

        # Add test feedback
        cursor.execute('''
            INSERT INTO restaurant_customer_feedback
            (feedback_id, customer_id, order_id, item_id, rating, feedback_text,
             feedback_date, response_text, response_date, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('FB001', 'CUST000001', 'ORD001', 'M001', 5, 'Excellent food!',
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None, None, 'Food'))
        mock_db_connection.commit()

        # Execute
        loyalty_program.view_recent_feedback()

        # Verify
        captured = capsys.readouterr()
        assert "RECENT CUSTOMER FEEDBACK" in captured.out
        assert "Test Customer" in captured.out
        assert "Excellent food!" in captured.out
        assert "⭐⭐⭐⭐⭐" in captured.out

    def test_export_feedback_report_csv(self, mock_db_connection, tmp_path):
        """Test exporting feedback to CSV."""
        # Setup
        with patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.get_db_connection') as mock_get_conn:
            mock_get_conn.return_value = mock_db_connection
            cursor = mock_db_connection.cursor()

            # Add test data
            cursor.execute('''
                INSERT INTO restaurant_customers
                (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
                 loyalty_tier, birthday, registration_date, last_visit, total_spent,
                 visit_count, preferences, address, emergency_contact, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('CUST000001', 'Test Customer', 'test@example.com', '1234567890',
                  'None', 0, 'Bronze', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  None, 0, 0, None, None, None, None))

            cursor.execute('''
                INSERT INTO restaurant_customer_feedback
                (feedback_id, customer_id, order_id, item_id, rating, feedback_text,
                 feedback_date, response_text, response_date, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('FB001', 'CUST000001', 'ORD001', None, 4, 'Good service',
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None, None, 'Service'))
            mock_db_connection.commit()

            # Execute
            filename = loyalty_program.export_feedback_report(days=90)

            # Verify
            assert filename is not None
            assert filename.endswith('.csv')
            assert 'feedback_report_' in filename

class TestCustomerAnalytics:
    """Tests for customer analytics functions."""

    def test_loyalty_analytics(self, mock_db_connection, capsys):
        """Test loyalty program analytics."""
        # Setup
        with patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.loyalty_program.get_db_connection') as mock_get_conn:
            mock_get_conn.return_value = mock_db_connection
            cursor = mock_db_connection.cursor()

            # Add test customers with varying loyalty
            customers = [
                ('CUST000001', 'Bronze Customer', 100, 'Bronze', 50.0),
                ('CUST000002', 'Silver Customer', 600, 'Silver', 150.0),
                ('CUST000003', 'Gold Customer', 1500, 'Gold', 400.0),
                ('CUST000004', 'Platinum Customer', 2500, 'Platinum', 800.0),
            ]

            for cust_id, name, points, tier, spent in customers:
                cursor.execute('''
                    INSERT INTO restaurant_customers
                    (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
                     loyalty_tier, birthday, registration_date, last_visit, total_spent,
                     visit_count, preferences, address, emergency_contact, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (cust_id, name, f'{name.lower().replace(" ", "")}@example.com',
                      '1234567890', 'None', points, tier, None,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None, spent, 0,
                      None, None, None, None))
            mock_db_connection.commit()

            # Execute
            loyalty_program.loyalty_analytics()

            # Verify
            captured = capsys.readouterr()
            assert "LOYALTY PROGRAM ANALYTICS" in captured.out
            assert "Total Customers: 4" in captured.out
            assert "Bronze" in captured.out
            assert "Platinum" in captured.out

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
