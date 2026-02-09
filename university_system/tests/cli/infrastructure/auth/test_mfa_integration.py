#!/usr/bin/env python3
"""
Comprehensive tests for MFA Integration Module
Tests integration between MFA and authentication system, including device trust and enforcement
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from university_system.infrastructure.auth.mfa_integration import (
    MFAIntegration,
    integrate_mfa_check,
    create_mfa_patch_for_user_auth,
    show_mfa_for_login,
    show_mfa_setup_for_login,
    INTEGRATION_EXAMPLE
)


class TestMFAIntegration:
    """Test MFAIntegration class"""

    def test_init(self):
        """Test MFAIntegration initialization"""
        with patch('university_system.infrastructure.auth.mfa_integration.MFAService'):
            integration = MFAIntegration()

            assert integration.mfa_service is not None

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_check_mfa_requirement_not_required(self, mock_service_class):
        """Test MFA check when not required"""
        mock_service = MagicMock()
        mock_service.check_mfa_required.return_value = {
            'success': True,
            'required': False
        }
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        result = integration.check_mfa_requirement(user_id=1, role='student')

        assert result['required'] is False
        assert result['enabled'] is False
        assert result['needs_setup'] is False
        assert result['must_verify'] is False

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_check_mfa_requirement_bypassed(self, mock_service_class):
        """Test MFA check when bypassed"""
        mock_service = MagicMock()
        mock_service.check_mfa_required.return_value = {
            'success': True,
            'bypassed': True
        }
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        result = integration.check_mfa_requirement(user_id=1, role='admin')

        assert result['required'] is False
        assert result['bypassed'] is True
        assert result['must_verify'] is False

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_check_mfa_requirement_already_enabled(self, mock_service_class):
        """Test MFA check when already enabled"""
        mock_service = MagicMock()
        mock_service.check_mfa_required.return_value = {
            'success': True,
            'already_enabled': True
        }
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        result = integration.check_mfa_requirement(user_id=1, role='admin')

        assert result['enabled'] is True
        assert result['must_verify'] is True
        assert result['needs_setup'] is False

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_check_mfa_requirement_grace_period(self, mock_service_class):
        """Test MFA check during grace period"""
        mock_service = MagicMock()
        mock_service.check_mfa_required.return_value = {
            'success': True,
            'grace_period': True,
            'deadline': '2024-12-31',
            'required': True
        }
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        result = integration.check_mfa_requirement(user_id=1, role='admin')

        assert result['required'] is True
        assert result['grace_period'] is True
        assert result['needs_setup'] is True
        assert result['must_verify'] is False
        assert result['grace_deadline'] == '2024-12-31'

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_check_mfa_requirement_setup_required(self, mock_service_class):
        """Test MFA check when setup is required"""
        mock_service = MagicMock()
        mock_service.check_mfa_required.return_value = {
            'success': True,
            'required': True
        }
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        result = integration.check_mfa_requirement(user_id=1, role='admin')

        assert result['required'] is True
        assert result['setup_required'] is True
        assert result['needs_setup'] is True
        assert result['must_verify'] is False

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_check_mfa_requirement_error(self, mock_service_class):
        """Test MFA check when service returns error"""
        mock_service = MagicMock()
        mock_service.check_mfa_required.return_value = {
            'success': False,
            'error': 'Database error'
        }
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        result = integration.check_mfa_requirement(user_id=1, role='admin')

        assert result['required'] is False
        assert result['enabled'] is False
        assert result['needs_setup'] is False
        assert result['must_verify'] is False
        assert 'error' in result

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_check_device_trust_trusted(self, mock_service_class):
        """Test device trust check for trusted device"""
        mock_service = MagicMock()
        mock_service.verify_trusted_device.return_value = {
            'success': True,
            'trusted': True
        }
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        is_trusted = integration.check_device_trust(
            user_id=1,
            device_id='device123',
            trust_token='token123'
        )

        assert is_trusted is True

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_check_device_trust_not_trusted(self, mock_service_class):
        """Test device trust check for untrusted device"""
        mock_service = MagicMock()
        mock_service.verify_trusted_device.return_value = {
            'success': True,
            'trusted': False
        }
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        is_trusted = integration.check_device_trust(
            user_id=1,
            device_id='device123',
            trust_token='wrong_token'
        )

        assert is_trusted is False

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_check_device_trust_missing_params(self, mock_service_class):
        """Test device trust check with missing parameters"""
        integration = MFAIntegration()

        # Missing user_id
        is_trusted = integration.check_device_trust(None, 'device123', 'token123')
        assert is_trusted is False

        # Missing device_id
        is_trusted = integration.check_device_trust(1, None, 'token123')
        assert is_trusted is False

        # Missing trust_token
        is_trusted = integration.check_device_trust(1, 'device123', None)
        assert is_trusted is False

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_is_mfa_locked_true(self, mock_service_class):
        """Test MFA lock check when locked"""
        mock_service = MagicMock()
        mock_service.is_mfa_locked.return_value = True
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        is_locked, reason = integration.is_mfa_locked(user_id=1)

        assert is_locked is True
        assert reason is not None
        assert 'locked' in reason.lower()

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_is_mfa_locked_false(self, mock_service_class):
        """Test MFA lock check when not locked"""
        mock_service = MagicMock()
        mock_service.is_mfa_locked.return_value = False
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        is_locked, reason = integration.is_mfa_locked(user_id=1)

        assert is_locked is False
        assert reason is None

    @patch('university_system.infrastructure.auth.mfa_integration.MFAService')
    def test_get_user_mfa_methods(self, mock_service_class):
        """Test getting user MFA methods"""
        mock_service = MagicMock()
        mock_service.get_user_mfa_methods.return_value = {
            'success': True,
            'methods': [
                {'type': 'totp', 'is_primary': True},
                {'type': 'sms', 'is_primary': False}
            ]
        }
        mock_service_class.return_value = mock_service

        integration = MFAIntegration()
        result = integration.get_user_mfa_methods(user_id=1)

        assert result['success'] is True
        assert len(result['methods']) == 2


class TestIntegrateMFACheck:
    """Test integrate_mfa_check function"""

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_integrate_mfa_check_locked(self, mock_integration_class):
        """Test MFA check when account is locked"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (True, "Account locked")
        mock_integration_class.return_value = mock_integration

        result = integrate_mfa_check(user_id=1, role='admin')

        assert result['action'] == 'locked'
        assert 'locked' in result['message'].lower()

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_integrate_mfa_check_trusted_device(self, mock_integration_class):
        """Test MFA check with trusted device"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (False, None)
        mock_integration.check_device_trust.return_value = True
        mock_integration_class.return_value = mock_integration

        result = integrate_mfa_check(
            user_id=1,
            role='admin',
            device_id='device123',
            trust_token='token123'
        )

        assert result['action'] == 'allow'
        assert 'trusted device' in result['message']
        assert result['data']['trusted_device'] is True

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_integrate_mfa_check_require_mfa(self, mock_integration_class):
        """Test MFA check requiring verification"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (False, None)
        mock_integration.check_device_trust.return_value = False
        mock_integration.check_mfa_requirement.return_value = {
            'must_verify': True
        }
        mock_integration.get_user_mfa_methods.return_value = {
            'success': True,
            'methods': [{'type': 'totp'}]
        }
        mock_integration_class.return_value = mock_integration

        result = integrate_mfa_check(user_id=1, role='admin')

        assert result['action'] == 'require_mfa'
        assert 'verification' in result['message'].lower()
        assert 'user_id' in result['data']
        assert 'methods' in result['data']

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_integrate_mfa_check_require_setup(self, mock_integration_class):
        """Test MFA check requiring setup"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (False, None)
        mock_integration.check_device_trust.return_value = False
        mock_integration.check_mfa_requirement.return_value = {
            'setup_required': True
        }
        mock_integration_class.return_value = mock_integration

        result = integrate_mfa_check(user_id=1, role='admin')

        assert result['action'] == 'require_setup'
        assert 'required' in result['message'].lower()
        assert result['data']['required'] is True

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_integrate_mfa_check_grace_period(self, mock_integration_class):
        """Test MFA check in grace period"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (False, None)
        mock_integration.check_device_trust.return_value = False
        mock_integration.check_mfa_requirement.return_value = {
            'grace_period': True,
            'grace_deadline': '2024-12-31',
            'required': True
        }
        mock_integration_class.return_value = mock_integration

        result = integrate_mfa_check(user_id=1, role='admin')

        assert result['action'] == 'grace'
        assert '2024-12-31' in result['message']
        assert result['data']['deadline'] == '2024-12-31'
        assert result['data']['required'] is True

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_integrate_mfa_check_allow(self, mock_integration_class):
        """Test MFA check allowing login"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (False, None)
        mock_integration.check_device_trust.return_value = False
        mock_integration.check_mfa_requirement.return_value = {}
        mock_integration_class.return_value = mock_integration

        result = integrate_mfa_check(user_id=1, role='student')

        assert result['action'] == 'allow'
        assert 'successful' in result['message'].lower()

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_integrate_mfa_check_error(self, mock_integration_class):
        """Test MFA check with error"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (False, None)
        mock_integration.check_device_trust.return_value = False
        mock_integration.check_mfa_requirement.return_value = {
            'error': 'Database error'
        }
        mock_integration_class.return_value = mock_integration

        result = integrate_mfa_check(user_id=1, role='admin')

        assert result['action'] == 'allow'  # Allow on error but log
        assert 'mfa_check_failed' in result['data']
        assert result['data']['error'] == 'Database error'


class TestCreateMFAPatch:
    """Test create_mfa_patch_for_user_auth function"""

    def test_create_mfa_patch_returns_function(self):
        """Test that create_mfa_patch_for_user_auth returns a function"""
        patch_func = create_mfa_patch_for_user_auth()

        assert callable(patch_func)

    @patch('university_system.infrastructure.auth.mfa_integration.integrate_mfa_check')
    def test_mfa_patch_calls_integrate_mfa_check(self, mock_integrate):
        """Test that MFA patch calls integrate_mfa_check"""
        mock_integrate.return_value = {'action': 'allow', 'message': 'Success', 'data': {}}

        patch_func = create_mfa_patch_for_user_auth()
        result = patch_func(user_id=1, role='student')

        assert result['action'] == 'allow'
        mock_integrate.assert_called_once_with(1, 'student', None, None)

    @patch('university_system.infrastructure.auth.mfa_integration.integrate_mfa_check')
    def test_mfa_patch_with_device_params(self, mock_integrate):
        """Test MFA patch with device parameters"""
        mock_integrate.return_value = {'action': 'allow', 'message': 'Success', 'data': {}}

        patch_func = create_mfa_patch_for_user_auth()
        result = patch_func(
            user_id=1,
            role='admin',
            device_id='device123',
            trust_token='token123'
        )

        mock_integrate.assert_called_once_with(1, 'admin', 'device123', 'token123')


class TestGUIIntegrationHelpers:
    """Test GUI integration helper functions"""

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    @patch('university_system.infrastructure.auth.mfa_integration.show_mfa_verification')
    def test_show_mfa_for_login_success(self, mock_show_verification, mock_integration_class):
        """Test show_mfa_for_login with successful verification"""
        # Setup mock integration
        mock_integration = MagicMock()
        mock_integration.get_user_mfa_methods.return_value = {
            'success': True,
            'methods': [{'type': 'totp'}]
        }
        mock_integration_class.return_value = mock_integration

        # Setup mock verification dialog
        mock_show_verification.return_value = True

        # Mock parent window
        mock_parent = MagicMock()

        verified, trust_token = show_mfa_for_login(mock_parent, user_id=1, username='testuser')

        assert verified is True

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_show_mfa_for_login_no_methods(self, mock_integration_class):
        """Test show_mfa_for_login when no MFA methods configured"""
        # Setup mock integration
        mock_integration = MagicMock()
        mock_integration.get_user_mfa_methods.return_value = {
            'success': True,
            'methods': []
        }
        mock_integration_class.return_value = mock_integration

        # Mock parent window
        mock_parent = MagicMock()

        verified, trust_token = show_mfa_for_login(mock_parent, user_id=1, username='testuser')

        assert verified is False
        assert trust_token is None

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_show_mfa_for_login_error(self, mock_integration_class):
        """Test show_mfa_for_login when service returns error"""
        # Setup mock integration
        mock_integration = MagicMock()
        mock_integration.get_user_mfa_methods.return_value = {
            'success': False
        }
        mock_integration_class.return_value = mock_integration

        # Mock parent window
        mock_parent = MagicMock()

        verified, trust_token = show_mfa_for_login(mock_parent, user_id=1, username='testuser')

        assert verified is False

    @patch('university_system.infrastructure.auth.mfa_integration.show_mfa_setup')
    def test_show_mfa_setup_for_login_success(self, mock_show_setup):
        """Test show_mfa_setup_for_login with successful setup"""
        # Mock setup dialog
        def mock_setup_func(parent, user_id, username, on_complete):
            # Call the on_complete callback
            on_complete()

        mock_show_setup.side_effect = mock_setup_func

        # Mock parent window
        mock_parent = MagicMock()

        completed = show_mfa_setup_for_login(mock_parent, user_id=1, username='testuser', required=True)

        assert completed is True

    @patch('university_system.infrastructure.auth.mfa_integration.show_mfa_setup')
    def test_show_mfa_setup_for_login_cancelled(self, mock_show_setup):
        """Test show_mfa_setup_for_login when user cancels"""
        # Mock setup dialog - don't call on_complete
        mock_show_setup.return_value = None

        # Mock parent window
        mock_parent = MagicMock()

        completed = show_mfa_setup_for_login(mock_parent, user_id=1, username='testuser', required=False)

        assert completed is False

    @patch('university_system.infrastructure.auth.mfa_integration.show_mfa_setup')
    def test_show_mfa_setup_for_login_error(self, mock_show_setup):
        """Test show_mfa_setup_for_login when error occurs"""
        # Mock setup dialog to raise exception
        mock_show_setup.side_effect = Exception("GUI error")

        # Mock parent window
        mock_parent = MagicMock()

        completed = show_mfa_setup_for_login(mock_parent, user_id=1, username='testuser')

        assert completed is False


class TestIntegrationExample:
    """Test that integration example code is present"""

    def test_integration_example_exists(self):
        """Test that INTEGRATION_EXAMPLE contains helpful example code"""
        assert INTEGRATION_EXAMPLE is not None
        assert len(INTEGRATION_EXAMPLE) > 0
        assert 'class UserAuth' in INTEGRATION_EXAMPLE
        assert 'def login' in INTEGRATION_EXAMPLE
        assert 'integrate_mfa_check' in INTEGRATION_EXAMPLE


class TestEdgeCases:
    """Test edge cases and error handling"""

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_integrate_mfa_check_none_params(self, mock_integration_class):
        """Test integrate_mfa_check with None parameters"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (False, None)
        mock_integration.check_device_trust.return_value = False
        mock_integration.check_mfa_requirement.return_value = {}
        mock_integration_class.return_value = mock_integration

        result = integrate_mfa_check(user_id=None, role=None)

        # Should still return a valid response
        assert 'action' in result
        assert 'message' in result
        assert 'data' in result

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_device_trust_without_device_id(self, mock_integration_class):
        """Test device trust check without device_id"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (False, None)
        mock_integration.check_mfa_requirement.return_value = {}
        mock_integration_class.return_value = mock_integration

        # Should not call check_device_trust without both device_id and trust_token
        result = integrate_mfa_check(user_id=1, role='student', device_id='device123')

        assert result['action'] == 'allow'

    @patch('university_system.infrastructure.auth.mfa_integration.MFAIntegration')
    def test_device_trust_without_trust_token(self, mock_integration_class):
        """Test device trust check without trust_token"""
        mock_integration = MagicMock()
        mock_integration.is_mfa_locked.return_value = (False, None)
        mock_integration.check_mfa_requirement.return_value = {}
        mock_integration_class.return_value = mock_integration

        # Should not call check_device_trust without both device_id and trust_token
        result = integrate_mfa_check(user_id=1, role='student', trust_token='token123')

        assert result['action'] == 'allow'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
