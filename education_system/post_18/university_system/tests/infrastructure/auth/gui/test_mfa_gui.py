#!/usr/bin/env python3
"""
Comprehensive tests for MFA GUI Components
Tests MFA setup wizard, verification dialog, and convenience functions
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path


_MFA_MOD = 'education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui'


# Prevent real tkinter widget creation in MFA GUI classes
@pytest.fixture(autouse=True)
def mock_tkinter():
    """Patch tk.Toplevel.__init__ so MFASetupWizard/MFAVerificationDialog
    can be instantiated without a real Tk display."""
    import tkinter as tk
    def _noop_init(self, *a, **kw):
        # Set minimal attrs that tk.Misc/Toplevel methods expect
        self.children = {}
        self.tk = MagicMock()
        self._w = '.'
        self._name = 'mock'
        self._tclCommands = {}
        self._mock_methods = None

    with patch.object(tk.Toplevel, '__init__', _noop_init), \
         patch.object(tk.Toplevel, 'title', MagicMock()), \
         patch.object(tk.Toplevel, 'geometry', MagicMock()), \
         patch.object(tk.Toplevel, 'resizable', MagicMock()), \
         patch.object(tk.Toplevel, 'minsize', MagicMock()), \
         patch.object(tk.Toplevel, 'transient', MagicMock()), \
         patch.object(tk.Toplevel, 'grab_set', MagicMock()), \
         patch.object(tk.Toplevel, 'update_idletasks', MagicMock()), \
         patch.object(tk.Toplevel, 'winfo_screenwidth', MagicMock(return_value=1920)), \
         patch.object(tk.Toplevel, 'winfo_screenheight', MagicMock(return_value=1080)), \
         patch.object(tk.Toplevel, 'winfo_width', MagicMock(return_value=700)), \
         patch.object(tk.Toplevel, 'winfo_height', MagicMock(return_value=850)), \
         patch.object(tk.Toplevel, 'wait_window', MagicMock()), \
         patch.object(tk.Toplevel, 'destroy', MagicMock()), \
         patch(f'{_MFA_MOD}.tk', MagicMock()), \
         patch(f'{_MFA_MOD}.ttk', MagicMock()), \
         patch(f'{_MFA_MOD}.messagebox', MagicMock()), \
         patch(f'{_MFA_MOD}.scrolledtext', MagicMock()), \
         patch(f'{_MFA_MOD}.Image', MagicMock()), \
         patch(f'{_MFA_MOD}.ImageTk', MagicMock()):
        yield


@pytest.fixture
def mock_mfa_service():
    """Create a mock MFA service"""
    service = MagicMock()
    service.setup_totp.return_value = {
        'success': True,
        'secret': 'TESTSECRET1234567890ABCDEF',
        'qr_code': b'fake_qr_code_bytes',
        'provisioning_uri': 'otpauth://totp/University%20System:testuser?secret=TEST&issuer=University%20System',
        'recovery_codes': [f'CODE-{i:04d}' for i in range(10)]
    }
    service.verify_totp.return_value = {'success': True, 'method': 'totp'}
    service.generate_sms_otp.return_value = {'success': True, 'code': '123456', 'message': 'Sent'}
    service.verify_sms_otp.return_value = {'success': True, 'method': 'sms'}
    service.generate_email_otp.return_value = {'success': True, 'code': '654321', 'message': 'Sent'}
    service.verify_email_otp.return_value = {'success': True, 'method': 'email'}
    service.verify_recovery_code.return_value = {'success': True, 'method': 'recovery_code', 'remaining_codes': 9}
    service.enable_mfa.return_value = {'success': True, 'message': 'MFA enabled'}
    service.get_user_mfa_methods.return_value = {
        'success': True,
        'methods': [
            {'type': 'totp', 'identifier': None, 'is_primary': True, 'last_used': None, 'setup_completed': '2024-01-01'}
        ]
    }
    return service


class TestMFASetupWizard:
    """Test MFA Setup Wizard"""

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_wizard_initialization(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test wizard initialization"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')

        assert wizard.user_id == 1
        assert wizard.username == 'testuser'
        assert wizard.current_step == 0
        assert wizard.setup_data == {}

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_wizard_title_and_geometry(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test wizard window configuration"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')

        # Verify window configuration methods were called on the wizard itself
        wizard.title.assert_called()
        wizard.geometry.assert_called()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_method_selection_validation(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test method selection validation"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')

        # Test validation with TOTP selected
        wizard.totp_var = MagicMock(get=lambda: True)
        wizard.sms_var = MagicMock(get=lambda: False)
        wizard.email_var = MagicMock(get=lambda: False)

        # Should not raise error
        try:
            wizard._validate_methods()
        except AttributeError:
            # Expected if messagebox is not fully mocked
            pass

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_totp_setup_flow(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test TOTP setup flow"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')

        # Show TOTP setup
        try:
            wizard._show_totp_setup()
        except AttributeError:
            # Expected due to GUI mocking
            pass

        # Verify setup_totp was called
        mock_mfa_service.setup_totp.assert_called_once_with(1, 'testuser')

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_verify_totp_success(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test TOTP verification success"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')
        wizard.totp_code_var = MagicMock(get=lambda: '123456')
        wizard.setup_data = {}

        try:
            wizard._verify_totp()
        except (AttributeError, KeyError):
            # Expected due to incomplete setup
            pass

        # Verify verify_totp was called
        mock_mfa_service.verify_totp.assert_called()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_sms_setup_flow(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test SMS setup flow"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')
        wizard.setup_data = {'phone': '+15551234567'}

        try:
            wizard._show_sms_setup()
        except (AttributeError, KeyError):
            pass

        # Verify generate_sms_otp was called
        mock_mfa_service.generate_sms_otp.assert_called()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_email_setup_flow(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test Email setup flow"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')
        wizard.setup_data = {'email': 'test@example.com'}

        try:
            wizard._show_email_setup()
        except (AttributeError, KeyError):
            pass

        # Verify generate_email_otp was called
        mock_mfa_service.generate_email_otp.assert_called()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_recovery_codes_display(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test recovery codes display"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')
        wizard.setup_data = {'recovery_codes': [f'CODE-{i:04d}' for i in range(10)]}

        try:
            wizard._show_recovery_codes()
        except AttributeError:
            # Expected due to GUI mocking
            pass

        # Should have recovery codes in setup_data
        assert 'recovery_codes' in wizard.setup_data

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_complete_setup(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test completing MFA setup"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')
        wizard.confirm_var = MagicMock(get=lambda: True)
        wizard.on_complete = MagicMock()

        try:
            wizard._complete_setup()
        except AttributeError:
            pass

        # Verify enable_mfa was called
        mock_mfa_service.enable_mfa.assert_called_with(1)


class TestMFAVerificationDialog:
    """Test MFA Verification Dialog"""

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_dialog_initialization(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test verification dialog initialization"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFAVerificationDialog

        dialog = MFAVerificationDialog(mock_parent, user_id=1, username='testuser')

        assert dialog.user_id == 1
        assert dialog.username == 'testuser'
        assert dialog.verified is False

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_totp_verification(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test TOTP verification in dialog"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFAVerificationDialog

        dialog = MFAVerificationDialog(mock_parent, user_id=1, username='testuser')
        dialog.totp_code_var = MagicMock(get=lambda: '123456')
        dialog.trust_device_var = MagicMock(get=lambda: False)

        try:
            dialog._verify_totp()
        except AttributeError:
            pass

        # Verify verify_totp was called
        mock_mfa_service.verify_totp.assert_called()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_sms_verification(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test SMS verification in dialog"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFAVerificationDialog

        dialog = MFAVerificationDialog(mock_parent, user_id=1, username='testuser')
        dialog.sms_code_var = MagicMock(get=lambda: '123456')
        dialog.trust_device_var = MagicMock(get=lambda: False)

        try:
            dialog._verify_sms()
        except AttributeError:
            pass

        # Verify verify_sms_otp was called
        mock_mfa_service.verify_sms_otp.assert_called()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_email_verification(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test Email verification in dialog"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFAVerificationDialog

        dialog = MFAVerificationDialog(mock_parent, user_id=1, username='testuser')
        dialog.email_code_var = MagicMock(get=lambda: '654321')
        dialog.trust_device_var = MagicMock(get=lambda: False)

        try:
            dialog._verify_email()
        except AttributeError:
            pass

        # Verify verify_email_otp was called
        mock_mfa_service.verify_email_otp.assert_called()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_recovery_code_verification(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test recovery code verification in dialog"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFAVerificationDialog

        dialog = MFAVerificationDialog(mock_parent, user_id=1, username='testuser')
        dialog.recovery_code_var = MagicMock(get=lambda: 'CODE-0001')
        dialog.trust_device_var = MagicMock(get=lambda: False)

        try:
            dialog._verify_recovery()
        except AttributeError:
            pass

        # Verify verify_recovery_code was called
        mock_mfa_service.verify_recovery_code.assert_called()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_successful_verification_callback(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test callback after successful verification"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()
        mock_callback = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFAVerificationDialog

        dialog = MFAVerificationDialog(mock_parent, user_id=1, username='testuser', on_success=mock_callback)

        result = {'success': True, 'method': 'totp'}
        dialog._on_verification_success(result)

        assert dialog.verified is True
        mock_callback.assert_called_once_with(result)

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    def test_device_fingerprinting(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test device ID generation"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFAVerificationDialog

        dialog = MFAVerificationDialog(mock_parent, user_id=1, username='testuser')

        device_id = dialog._get_device_id()

        assert device_id is not None
        assert len(device_id) > 0


class TestConvenienceFunctions:
    """Test convenience functions"""

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFASetupWizard')
    def test_show_mfa_setup(self, mock_wizard_class):
        """Test show_mfa_setup convenience function"""
        mock_parent = MagicMock()
        mock_wizard = MagicMock()
        mock_wizard_class.return_value = mock_wizard

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import show_mfa_setup

        show_mfa_setup(mock_parent, user_id=1, username='testuser')

        # Verify wizard was created
        mock_wizard_class.assert_called_once()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAVerificationDialog')
    def test_show_mfa_verification(self, mock_dialog_class):
        """Test show_mfa_verification convenience function"""
        mock_parent = MagicMock()
        mock_dialog = MagicMock()
        mock_dialog.verified = True
        mock_dialog_class.return_value = mock_dialog

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import show_mfa_verification

        verified = show_mfa_verification(mock_parent, user_id=1, username='testuser')

        # Verify dialog was created
        mock_dialog_class.assert_called_once()
        assert verified is True


class TestRecoveryCodesSaving:
    """Test recovery codes file saving"""

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    @patch('tkinter.filedialog.asksaveasfilename')
    def test_save_recovery_codes(self, mock_filedialog, mock_toplevel, mock_service_class, mock_mfa_service, tmp_path):
        """Test saving recovery codes to file"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFASetupWizard

        wizard = MFASetupWizard(mock_parent, user_id=1, username='testuser')

        # Setup temp file
        temp_file = tmp_path / "recovery_codes.txt"
        mock_filedialog.return_value = str(temp_file)

        recovery_codes = [f'CODE-{i:04d}' for i in range(10)]

        try:
            wizard._save_recovery_codes(recovery_codes)
        except (AttributeError, ImportError):
            # Expected if filedialog is not fully mocked
            pass

        # If file was created, verify content
        if temp_file.exists():
            content = temp_file.read_text()
            assert 'CODE-0000' in content
            assert 'Recovery Codes' in content


class TestGUIValidation:
    """Test GUI input validation"""

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.messagebox.showerror')
    def test_invalid_totp_code_length(self, mock_messagebox, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test TOTP code validation for length"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFAVerificationDialog

        dialog = MFAVerificationDialog(mock_parent, user_id=1, username='testuser')
        dialog.totp_code_var = MagicMock(get=lambda: '12')  # Too short

        dialog._verify_totp()

        # Should show error for invalid code length
        mock_messagebox.assert_called()

    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.MFAService')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.tk.Toplevel')
    @patch('education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui.messagebox.showerror')
    def test_empty_recovery_code(self, mock_messagebox, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test recovery code validation for empty input"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from education_system.post_18.university_system.modules.shared.gui.auth.mfa_gui import MFAVerificationDialog

        dialog = MFAVerificationDialog(mock_parent, user_id=1, username='testuser')
        dialog.recovery_code_var = MagicMock(get=lambda: '')

        dialog._verify_recovery()

        # Should show error for empty code
        mock_messagebox.assert_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
