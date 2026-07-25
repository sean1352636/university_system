"""
Tests for student union context module.
Tests the shared context and helper functions.
"""

import pytest
from unittest.mock import Mock, patch

from education_system.systems.university.domain.pastoral.student_life.student_union.services import union_context


class TestHelperFunctions:
    """Tests for helper functions that delegate to other modules."""

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.points.auto_award_points')
    def test_auto_award_points(self, mock_func):
        """Test auto award points helper."""
        mock_func.return_value = True

        result = union_context.auto_award_points()

        mock_func.assert_called_once()
        assert result is True

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.manage_peer_support_system')
    def test_manage_peer_support_system(self, mock_func):
        """Test manage peer support system helper."""
        auth_obj = Mock()
        union_context.manage_peer_support_system(auth_obj)

        mock_func.assert_called_once_with(auth_obj)

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.support.manage_academic_support')
    def test_manage_academic_support(self, mock_func):
        """Test manage academic support helper."""
        auth_obj = Mock()
        union_context.manage_academic_support(auth_obj)

        mock_func.assert_called_once_with(auth_obj)

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.sustainability.manage_green_initiatives')
    def test_manage_green_initiatives(self, mock_func):
        """Test manage green initiatives helper."""
        auth_obj = Mock()
        union_context.manage_green_initiatives(auth_obj)

        mock_func.assert_called_once_with(auth_obj)

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.voting.manage_enhanced_voting')
    def test_manage_enhanced_voting(self, mock_func):
        """Test manage enhanced voting helper."""
        auth_obj = Mock()
        union_context.manage_enhanced_voting(auth_obj)

        mock_func.assert_called_once_with(auth_obj)


class TestAuthContext:
    """Tests for auth context functionality."""

    def test_auth_initially_none(self):
        """Test that auth is initially None."""
        # Reset auth to None
        union_context.auth = None
        assert union_context.auth is None

    def test_auth_can_be_set(self):
        """Test that auth can be set."""
        mock_auth = Mock()
        union_context.auth = mock_auth
        assert union_context.auth == mock_auth

        # Reset for other tests
        union_context.auth = None


class TestModuleDelegation:
    """Tests that verify proper delegation to other modules."""

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.analytics.learning_analytics_dashboard')
    def test_learning_analytics_dashboard_delegates(self, mock_func):
        """Test that learning_analytics_dashboard properly delegates."""
        union_context.learning_analytics_dashboard()
        mock_func.assert_called_once()

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.analytics.generate_advanced_analytics')
    def test_generate_advanced_analytics_delegates(self, mock_func):
        """Test that generate_advanced_analytics properly delegates."""
        auth_obj = Mock()
        union_context.generate_advanced_analytics(auth_obj)
        mock_func.assert_called_once_with(auth_obj)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
