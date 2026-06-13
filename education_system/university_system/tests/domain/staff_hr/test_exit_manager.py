"""
Tests for Exit Manager

Tests for exit interview scheduling, checklist management, knowledge transfer,
and turnover analytics functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock


class TestExitInterviews:
    """Tests for exit interview functionality."""

    @pytest.fixture
    def mock_db(self):
        """Set up mock database connections."""
        with patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.get_connection') as mock_get, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.transaction') as mock_trans, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.log_activity'):

            mock_conn = MagicMock()
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            mock_trans.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_trans.return_value.__exit__ = MagicMock(return_value=False)

            yield mock_conn

    def test_create_exit_interview(self, mock_db):
        """Test creating an exit interview."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor

        interview_id = ExitManager.create_exit_interview(
            user_id='user123',
            interviewer_id='hr001',
            scheduled_date='2026-02-01',
            last_working_day='2026-02-15',
            department='Engineering',
            job_title='Software Developer'
        )

        assert interview_id == 1
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert 'INSERT INTO exit_interviews' in call_args[0][0]

    def test_get_exit_interview(self, mock_db):
        """Test retrieving an exit interview by ID."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['interview_id', 'user_id', 'status', 'department']
        mock_row.__iter__ = lambda self: iter([1, 'user123', 'scheduled', 'Engineering'])
        mock_row.__getitem__ = lambda self, key: {
            'interview_id': 1, 'user_id': 'user123',
            'status': 'scheduled', 'department': 'Engineering'
        }[key]
        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = ExitManager.get_exit_interview(1)

        assert result is not None
        assert result['interview_id'] == 1
        assert result['status'] == 'scheduled'

    def test_get_exit_interview_not_found(self, mock_db):
        """Test retrieving a non-existent exit interview."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_db.execute.return_value.fetchone.return_value = None

        result = ExitManager.get_exit_interview(999)

        assert result is None

    def test_get_pending_interviews(self, mock_db):
        """Test retrieving pending exit interviews."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['interview_id', 'user_id', 'status', 'scheduled_date']
        mock_row.__iter__ = lambda self: iter([1, 'user123', 'scheduled', '2026-02-01'])
        mock_row.__getitem__ = lambda self, key: {
            'interview_id': 1, 'user_id': 'user123',
            'status': 'scheduled', 'scheduled_date': '2026-02-01'
        }[key]
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_pending_interviews()

        assert len(result) == 1
        assert result[0]['status'] == 'scheduled'

    def test_get_pending_interviews_for_interviewer(self, mock_db):
        """Test retrieving pending interviews for a specific interviewer."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_db.execute.return_value.fetchall.return_value = []

        ExitManager.get_pending_interviews(interviewer_id='hr001')

        call_args = mock_db.execute.call_args
        assert 'interviewer_id = ?' in call_args[0][0]
        assert 'hr001' in call_args[0][1]

    def test_update_exit_interview(self, mock_db):
        """Test updating an exit interview."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.update_exit_interview(
            1,
            status='completed',
            interviewer_id='hr002'
        )

        assert result is True
        call_args = mock_db.execute.call_args
        assert 'UPDATE exit_interviews' in call_args[0][0]

    def test_update_exit_interview_no_data(self, mock_db):
        """Test updating an exit interview with no data."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.update_exit_interview(1)

        assert result is False

    def test_complete_exit_interview(self, mock_db):
        """Test completing an exit interview with feedback."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.complete_exit_interview(
            1,
            reason_for_leaving='Career advancement',
            reason_category='voluntary',
            overall_rating=4,
            would_recommend=True,
            suggestions='More growth opportunities'
        )

        assert result is True
        call_args = mock_db.execute.call_args
        assert "status = 'completed'" in call_args[0][0]

    def test_initiate_exit(self, mock_db):
        """Test initiating an exit process."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor
        mock_db.execute.return_value.fetchone.return_value = None

        with patch.object(ExitManager, 'create_user_checklist', return_value=[]):
            interview_id = ExitManager.initiate_exit(
                user_id='user123',
                exit_type='voluntary',
                last_working_day='2026-02-15',
                reason='New opportunity',
                department='Engineering'
            )

        assert interview_id == 1

    def test_schedule_interview_new(self, mock_db):
        """Test scheduling a new exit interview."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor
        mock_db.execute.return_value.fetchone.return_value = None

        interview_id = ExitManager.schedule_interview(
            user_id='user123',
            interviewer_id='hr001',
            interview_date='2026-02-10'
        )

        assert interview_id == 1

    def test_schedule_interview_existing(self, mock_db):
        """Test scheduling an interview when one already exists."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['interview_id', 'user_id']
        mock_row.__iter__ = lambda self: iter([5, 'user123'])
        mock_row.__getitem__ = lambda self, key: {'interview_id': 5, 'user_id': 'user123'}[key]
        mock_db.execute.return_value.fetchone.return_value = mock_row

        interview_id = ExitManager.schedule_interview(
            user_id='user123',
            interviewer_id='hr002',
            interview_date='2026-02-15'
        )

        assert interview_id == 5


class TestExitChecklistTemplates:
    """Tests for checklist template functionality."""

    @pytest.fixture
    def mock_db(self):
        """Set up mock database connections."""
        with patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.get_connection') as mock_get, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.transaction') as mock_trans, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.log_activity'):

            mock_conn = MagicMock()
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            mock_trans.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_trans.return_value.__exit__ = MagicMock(return_value=False)

            yield mock_conn

    def test_get_checklist_templates(self, mock_db):
        """Test retrieving checklist templates."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['template_id', 'name', 'is_default']
        mock_row.__iter__ = lambda self: iter([1, 'Standard Exit', True])
        mock_row.__getitem__ = lambda self, key: {
            'template_id': 1, 'name': 'Standard Exit', 'is_default': True
        }[key]
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_checklist_templates()

        assert len(result) == 1
        assert result[0]['name'] == 'Standard Exit'

    def test_get_checklist_templates_by_department(self, mock_db):
        """Test retrieving templates filtered by department."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_db.execute.return_value.fetchall.return_value = []

        ExitManager.get_checklist_templates(department='Engineering')

        call_args = mock_db.execute.call_args
        assert 'department = ?' in call_args[0][0] or 'department IS NULL' in call_args[0][0]

    def test_get_all_templates(self, mock_db):
        """Test retrieving all templates with item counts."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['template_id', 'name', 'item_count']
        mock_row.__iter__ = lambda self: iter([1, 'Standard', 5])
        mock_row.__getitem__ = lambda self, key: {
            'template_id': 1, 'name': 'Standard', 'item_count': 5
        }[key]
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_all_templates()

        assert len(result) == 1
        assert result[0]['item_count'] == 5

    def test_create_template(self, mock_db):
        """Test creating a new checklist template."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor

        template_id = ExitManager.create_template(
            name='IT Exit Template',
            description='Exit checklist for IT staff',
            department='IT',
            is_default=False
        )

        assert template_id == 1

    def test_add_template_item(self, mock_db):
        """Test adding an item to a template."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor

        item_id = ExitManager.add_template_item(
            template_id=1,
            task_name='Return laptop',
            description='Return company laptop to IT',
            responsible_party='IT',
            is_required=True,
            order=1
        )

        assert item_id == 1

    def test_get_template_items_with_aliases(self, mock_db):
        """Test that template items include CLI-compatible aliases."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['item_id', 'task_name', 'is_mandatory', 'order_index']
        mock_row.__iter__ = lambda self: iter([1, 'Return badge', True, 1])
        mock_row.__getitem__ = lambda self, key: {
            'item_id': 1, 'task_name': 'Return badge',
            'is_mandatory': True, 'order_index': 1
        }.get(key)
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_template_items(1)

        assert len(result) == 1
        assert 'is_required' in result[0]
        assert 'order' in result[0]
        assert result[0]['is_required'] == True
        assert result[0]['order'] == 1

    def test_update_template(self, mock_db):
        """Test updating a checklist template."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.update_template(
            template_id=1,
            name='Updated Template',
            description='Updated description'
        )

        assert result is True

    def test_delete_template(self, mock_db):
        """Test deleting a template and its items."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.delete_template(1)

        assert result is True
        # Should delete both items and template
        assert mock_db.execute.call_count >= 2


class TestUserExitChecklist:
    """Tests for user exit checklist functionality."""

    @pytest.fixture
    def mock_db(self):
        """Set up mock database connections."""
        with patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.get_connection') as mock_get, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.transaction') as mock_trans, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.log_activity'):

            mock_conn = MagicMock()
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            mock_trans.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_trans.return_value.__exit__ = MagicMock(return_value=False)

            yield mock_conn

    def test_create_user_checklist_from_template(self, mock_db):
        """Test creating a user checklist from a template."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor

        with patch.object(ExitManager, 'get_template_items') as mock_items:
            mock_items.return_value = [
                {'task_name': 'Return badge', 'days_before_exit': 0, 'description': 'Return ID badge'},
                {'task_name': 'Return laptop', 'days_before_exit': -1, 'description': 'Return company laptop'}
            ]

            checklist_ids = ExitManager.create_user_checklist(
                user_id='user123',
                last_working_day='2026-02-15',
                template_id=1
            )

        assert len(checklist_ids) == 2

    def test_get_user_checklist_with_aliases(self, mock_db):
        """Test that user checklist includes CLI-compatible aliases."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['checklist_id', 'task_name', 'is_mandatory', 'responsible_party']
        mock_row.__iter__ = lambda self: iter([1, 'Return badge', True, 'HR'])
        mock_row.__getitem__ = lambda self, key: {
            'checklist_id': 1, 'task_name': 'Return badge',
            'is_mandatory': True, 'responsible_party': 'HR'
        }.get(key)
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_user_checklist('user123')

        assert len(result) == 1
        assert 'is_required' in result[0]
        assert 'assigned_to' in result[0]
        assert result[0]['assigned_to'] == 'HR'

    def test_add_checklist_item(self, mock_db):
        """Test adding a custom checklist item for a user."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor

        item_id = ExitManager.add_checklist_item(
            user_id='user123',
            task_name='Knowledge transfer meeting',
            description='Conduct knowledge transfer with replacement',
            assigned_to='manager001',
            due_date='2026-02-10'
        )

        assert item_id == 1

    def test_assign_checklist_item(self, mock_db):
        """Test assigning a checklist item to someone."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.assign_checklist_item(
            checklist_id=1,
            assigned_to='hr002'
        )

        assert result is True
        call_args = mock_db.execute.call_args
        assert 'responsible_party = ?' in call_args[0][0]

    def test_complete_checklist_item(self, mock_db):
        """Test completing a checklist item."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.complete_checklist_item(
            checklist_id=1,
            completed_by='hr001',
            notes='Badge returned in good condition'
        )

        assert result is True

    def test_remove_checklist_item(self, mock_db):
        """Test removing a checklist item."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.remove_checklist_item(1)

        assert result is True
        call_args = mock_db.execute.call_args
        assert 'DELETE FROM exit_checklist' in call_args[0][0]

    def test_get_checklist_progress(self, mock_db):
        """Test getting checklist completion progress."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {'total': 10, 'completed': 7}[key]
        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = ExitManager.get_checklist_progress('user123')

        assert result['total'] == 10
        assert result['completed'] == 7
        assert result['remaining'] == 3
        assert result['percentage'] == 70.0

    def test_get_checklist_progress_empty(self, mock_db):
        """Test getting progress for empty checklist."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {'total': 0, 'completed': 0}[key]
        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = ExitManager.get_checklist_progress('user123')

        assert result['percentage'] == 0

    def test_apply_template(self, mock_db):
        """Test applying a template to a user's exit process."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor

        with patch.object(ExitManager, 'get_user_exit_interview') as mock_interview, \
             patch.object(ExitManager, 'get_template_items') as mock_items:
            mock_interview.return_value = {'last_working_day': '2026-02-15'}
            mock_items.return_value = [
                {'task_name': 'Task 1', 'days_before_exit': 0},
                {'task_name': 'Task 2', 'days_before_exit': 0}
            ]

            count = ExitManager.apply_template('user123', 1)

        assert count == 2


class TestKnowledgeTransfer:
    """Tests for knowledge transfer functionality."""

    @pytest.fixture
    def mock_db(self):
        """Set up mock database connections."""
        with patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.get_connection') as mock_get, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.transaction') as mock_trans, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.log_activity'):

            mock_conn = MagicMock()
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            mock_trans.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_trans.return_value.__exit__ = MagicMock(return_value=False)

            yield mock_conn

    def test_create_knowledge_transfer(self, mock_db):
        """Test creating a knowledge transfer record."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor

        transfer_id = ExitManager.create_knowledge_transfer(
            departing_user_id='user123',
            receiving_user_id='user456',
            topic='Project Documentation',
            description='Transfer all project docs',
            priority='high',
            scheduled_date='2026-02-05'
        )

        assert transfer_id == 1

    def test_get_knowledge_transfers_departing(self, mock_db):
        """Test retrieving knowledge transfers for departing user."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['transfer_id', 'topic', 'status']
        mock_row.__iter__ = lambda self: iter([1, 'Project Docs', 'pending'])
        mock_row.__getitem__ = lambda self, key: {
            'transfer_id': 1, 'topic': 'Project Docs', 'status': 'pending'
        }[key]
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_knowledge_transfers('user123', as_departing=True)

        assert len(result) == 1
        call_args = mock_db.execute.call_args
        assert 'departing_user_id = ?' in call_args[0][0]

    def test_get_knowledge_transfers_receiving(self, mock_db):
        """Test retrieving knowledge transfers for receiving user."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_db.execute.return_value.fetchall.return_value = []

        ExitManager.get_knowledge_transfers('user456', as_departing=False)

        call_args = mock_db.execute.call_args
        assert 'receiving_user_id = ?' in call_args[0][0]

    def test_complete_knowledge_transfer(self, mock_db):
        """Test completing a knowledge transfer."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.complete_knowledge_transfer(
            transfer_id=1,
            notes='Successfully transferred all documentation'
        )

        assert result is True
        call_args = mock_db.execute.call_args
        assert "status = 'completed'" in call_args[0][0]


class TestTurnoverAnalytics:
    """Tests for turnover analytics functionality."""

    @pytest.fixture
    def mock_db(self):
        """Set up mock database connections."""
        with patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.get_connection') as mock_get, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.transaction') as mock_trans, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.log_activity'):

            mock_conn = MagicMock()
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            mock_trans.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_trans.return_value.__exit__ = MagicMock(return_value=False)

            yield mock_conn

    def test_calculate_turnover(self, mock_db):
        """Test calculating turnover metrics."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            'total_exits': 15, 'voluntary': 10, 'involuntary': 3,
            'retirement': 2, 'avg_tenure': 36.5
        }[key]
        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = ExitManager.calculate_turnover(
            department='Engineering',
            period_start='2025-01-01',
            period_end='2025-12-31'
        )

        assert result['total_exits'] == 15
        assert result['voluntary'] == 10
        assert result['involuntary'] == 3
        assert result['retirement'] == 2
        assert result['avg_tenure_months'] == 36.5

    def test_get_exit_reasons_breakdown(self, mock_db):
        """Test getting breakdown of exit reasons."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['reason_category', 'reason_for_leaving', 'count']
        mock_row.__iter__ = lambda self: iter(['voluntary', 'Better opportunity', 5])
        mock_row.__getitem__ = lambda self, key: {
            'reason_category': 'voluntary',
            'reason_for_leaving': 'Better opportunity',
            'count': 5
        }[key]
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_exit_reasons_breakdown(period='2025')

        assert len(result) == 1
        assert result[0]['count'] == 5

    def test_get_satisfaction_trends(self, mock_db):
        """Test getting satisfaction rating trends."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['month', 'avg_overall', 'exit_count']
        mock_row.__iter__ = lambda self: iter(['2025-06', 3.5, 10])
        mock_row.__getitem__ = lambda self, key: {
            'month': '2025-06', 'avg_overall': 3.5, 'exit_count': 10
        }[key]
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_satisfaction_trends(period_months=12)

        assert len(result) == 1
        assert result[0]['exit_count'] == 10

    def test_get_department_turnover_comparison(self, mock_db):
        """Test comparing turnover across departments."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['department', 'exit_count', 'avg_tenure', 'avg_rating', 'recommend_pct']
        mock_row.__iter__ = lambda self: iter(['Engineering', 8, 24.5, 3.8, 75.0])
        mock_row.__getitem__ = lambda self, key: {
            'department': 'Engineering', 'exit_count': 8,
            'avg_tenure': 24.5, 'avg_rating': 3.8, 'recommend_pct': 75.0
        }[key]
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_department_turnover_comparison()

        assert len(result) == 1
        assert result[0]['department'] == 'Engineering'
        assert result[0]['exit_count'] == 8

    def test_store_turnover_analytics(self, mock_db):
        """Test storing turnover analytics for reporting."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor

        record_id = ExitManager.store_turnover_analytics(
            department='Engineering',
            period_start='2025-01-01',
            period_end='2025-12-31',
            headcount_start=50,
            headcount_end=48,
            voluntary_exits=5,
            turnover_rate=10.0
        )

        assert record_id == 1

    def test_get_retention_recommendations(self, mock_db):
        """Test generating retention recommendations."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            'salary_issues': 8, 'growth_issues': 12, 'balance_issues': 3,
            'management_issues': 6, 'culture_issues': 2, 'total': 20
        }[key]
        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = ExitManager.get_retention_recommendations()

        # Should return recommendations for factors > 30%
        assert isinstance(result, list)
        # Growth issues (60%) and salary issues (40%) should be flagged
        assert len(result) >= 1

    def test_get_exit_statistics(self, mock_db):
        """Test getting overall exit statistics."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            'count': 25, 'avg_rating': 3.7, 'recommend_pct': 68.0
        }.get(key, 0)
        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = ExitManager.get_exit_statistics()

        assert 'total_this_year' in result
        assert 'pending' in result
        assert 'completed' in result
        assert 'avg_rating' in result

    def test_get_turnover_analytics(self, mock_db):
        """Test getting turnover analytics for a year."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        # Mock the calculate_turnover call
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            'total_exits': 20, 'voluntary': 15, 'involuntary': 3,
            'retirement': 2, 'avg_tenure': 30.0,
            'month': '2025-06', 'count': 3,
            'department': 'Engineering', 'exits': 5,
            'reason_category': 'voluntary', 'avg': 28.5
        }.get(key, 0)
        mock_db.execute.return_value.fetchone.return_value = mock_row
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_turnover_analytics(2025)

        assert 'total_exits' in result
        assert 'monthly_exits' in result
        assert 'by_department' in result
        assert 'by_type' in result

    def test_get_exit_reasons_summary(self, mock_db):
        """Test getting exit reasons summary."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            'total': 30, 'reason_for_leaving': 'Career growth', 'count': 10,
            'job_satisfaction': 3.5, 'management': 3.2,
            'work_environment': 3.8, 'growth': 2.9,
            'rec_yes': 20, 'rec_no': 10, 'ret_yes': 18, 'ret_no': 12
        }.get(key, 0)
        mock_db.execute.return_value.fetchone.return_value = mock_row
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_exit_reasons_summary(period='2025')

        assert 'total_interviews' in result
        assert 'reasons' in result
        assert 'avg_ratings' in result
        assert 'would_recommend' in result
        assert 'would_return' in result

    def test_get_department_turnover_report(self, mock_db):
        """Test getting department turnover report."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['department', 'exits_12m', 'avg_tenure', 'reason_for_leaving']
        mock_row.__iter__ = lambda self: iter(['Engineering', 5, 24.0, 'Career growth'])
        mock_row.__getitem__ = lambda self, key: {
            'department': 'Engineering', 'exits_12m': 5,
            'avg_tenure': 24.0, 'reason_for_leaving': 'Career growth'
        }.get(key)
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.get_department_turnover_report()

        assert 'Engineering' in result
        assert result['Engineering']['exits_12m'] == 5


class TestSearchAndFiltering:
    """Tests for search and filtering functionality."""

    @pytest.fixture
    def mock_db(self):
        """Set up mock database connections."""
        with patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.get_connection') as mock_get, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.transaction') as mock_trans, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.log_activity'):

            mock_conn = MagicMock()
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            mock_trans.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_trans.return_value.__exit__ = MagicMock(return_value=False)

            yield mock_conn

    def test_search_exits_with_filters(self, mock_db):
        """Test searching exits with multiple filters."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['interview_id', 'user_id', 'department', 'status']
        mock_row.__iter__ = lambda self: iter([1, 'user123', 'Engineering', 'completed'])
        mock_row.__getitem__ = lambda self, key: {
            'interview_id': 1, 'user_id': 'user123',
            'department': 'Engineering', 'status': 'completed'
        }[key]
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        result = ExitManager.search_exits(
            exit_type='voluntary',
            department='Engineering',
            status='completed',
            start_date='2025-01-01',
            end_date='2025-12-31'
        )

        assert len(result) == 1
        call_args = mock_db.execute.call_args
        query = call_args[0][0]
        assert 'reason_category = ?' in query
        assert 'department = ?' in query
        assert 'status = ?' in query
        assert 'last_working_day >= ?' in query
        assert 'last_working_day <= ?' in query

    def test_get_all_exit_interviews_with_filters(self, mock_db):
        """Test getting all exit interviews with filters."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_db.execute.return_value.fetchall.return_value = []

        ExitManager.get_all_exit_interviews(
            status='completed',
            department='HR',
            from_date='2025-01-01',
            to_date='2025-06-30'
        )

        call_args = mock_db.execute.call_args
        query = call_args[0][0]
        assert 'status = ?' in query
        assert 'department = ?' in query
        assert 'last_working_day >= ?' in query
        assert 'last_working_day <= ?' in query

    def test_get_exit_record(self, mock_db):
        """Test getting exit record (alias method)."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.keys.return_value = ['interview_id', 'user_id']
        mock_row.__iter__ = lambda self: iter([1, 'user123'])
        mock_row.__getitem__ = lambda self, key: {'interview_id': 1, 'user_id': 'user123'}[key]
        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = ExitManager.get_exit_record('user123')

        assert result is not None
        assert result['user_id'] == 'user123'


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def mock_db(self):
        """Set up mock database connections."""
        with patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.get_connection') as mock_get, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.transaction') as mock_trans, \
             patch('education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager.log_activity'):

            mock_conn = MagicMock()
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            mock_trans.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_trans.return_value.__exit__ = MagicMock(return_value=False)

            yield mock_conn

    def test_update_template_no_data(self, mock_db):
        """Test updating template with no data."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.update_template(1)

        assert result is False

    def test_update_checklist_item_no_data(self, mock_db):
        """Test updating checklist item with no data."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        result = ExitManager.update_checklist_item(1)

        assert result is False

    def test_retention_recommendations_no_data(self, mock_db):
        """Test retention recommendations with no exit data."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: 0
        mock_db.execute.return_value.fetchone.return_value = mock_row

        result = ExitManager.get_retention_recommendations()

        assert result == []

    def test_create_user_checklist_no_template(self, mock_db):
        """Test creating user checklist without template."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        # No default template found
        mock_db.execute.return_value.fetchone.return_value = None
        mock_db.execute.return_value.fetchall.return_value = []

        checklist_ids = ExitManager.create_user_checklist(
            user_id='user123',
            last_working_day='2026-02-15'
        )

        assert checklist_ids == []

    def test_apply_template_no_interview(self, mock_db):
        """Test applying template when no interview exists."""
        from education_system.university_system.modules.domain.staff_hr.services.managers.exit_manager import ExitManager

        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_db.execute.return_value = mock_cursor

        with patch.object(ExitManager, 'get_user_exit_interview') as mock_interview, \
             patch.object(ExitManager, 'get_template_items') as mock_items:
            mock_interview.return_value = None  # No interview
            mock_items.return_value = [{'task_name': 'Task 1', 'days_before_exit': 0}]

            count = ExitManager.apply_template('user123', 1)

        # Should still work, using current date as default
        assert count == 1
