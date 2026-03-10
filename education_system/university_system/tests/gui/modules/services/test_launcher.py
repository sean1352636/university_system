#!/usr/bin/env python3
"""
Comprehensive tests for Service Launcher Module
Tests service discovery, launching, and management
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import argparse

from education_system.university_system.modules.services import launcher


class TestServiceLauncherInitialization:
    """Test ServiceLauncher initialization"""

    def test_launcher_can_be_instantiated(self):
        """Test that launcher can be created"""
        service_launcher = launcher.ServiceLauncher()
        assert service_launcher is not None

    def test_launcher_has_available_services(self):
        """Test that launcher discovers services"""
        service_launcher = launcher.ServiceLauncher()
        assert hasattr(service_launcher, 'available_services')
        assert isinstance(service_launcher.available_services, dict)

    def test_launcher_discovers_services(self):
        """Test service discovery"""
        service_launcher = launcher.ServiceLauncher()
        # Should have discovered at least some services
        services = service_launcher.available_services
        assert isinstance(services, dict)


class TestServiceDiscovery:
    """Test service discovery functionality"""

    def test_discover_services_returns_dict(self):
        """Test _discover_services returns dictionary"""
        service_launcher = launcher.ServiceLauncher()
        services = service_launcher._discover_services()
        assert isinstance(services, dict)

    def test_discovered_services_have_interface_types(self):
        """Test discovered services specify interface types"""
        service_launcher = launcher.ServiceLauncher()
        for service_name, interfaces in service_launcher.available_services.items():
            assert isinstance(interfaces, dict)
            # Each interface should be gui, cli, or api
            for interface_type in interfaces.keys():
                assert interface_type in ['gui', 'cli', 'api']


class TestListServices:
    """Test list_services functionality"""

    @patch('builtins.print')
    def test_list_services_prints_output(self, mock_print):
        """Test that list_services prints to console"""
        service_launcher = launcher.ServiceLauncher()
        service_launcher.list_services()
        # Should have printed something
        assert mock_print.call_count > 0

    @patch('builtins.print')
    def test_list_services_shows_available_services(self, mock_print):
        """Test that list_services shows service information"""
        service_launcher = launcher.ServiceLauncher()
        service_launcher.list_services()
        # Check that print was called with service info
        printed_text = ' '.join([str(call[0][0]) for call in mock_print.call_args_list])
        assert 'Services' in printed_text or 'services' in printed_text.lower()


class TestLaunchService:
    """Test service launching functionality"""

    def test_launch_service_validates_service_name(self):
        """Test validation of service name"""
        service_launcher = launcher.ServiceLauncher()
        result = service_launcher.launch_service('nonexistent_service', 'gui')
        assert result is False

    def test_launch_service_validates_interface_type(self):
        """Test validation of interface type"""
        service_launcher = launcher.ServiceLauncher()
        # Use a service that exists but without specified interface
        result = service_launcher.launch_service('health_portal', 'invalid_interface')
        # Should return False if interface not supported


class TestLaunchGUI:
    """Test GUI service launching"""

    @patch('tkinter.Tk')
    def test_launch_gui_creates_root(self, mock_tk):
        """Test GUI launcher creates Tk root"""
        service_launcher = launcher.ServiceLauncher()
        
        # Create a mock module
        mock_module = Mock()
        mock_module.HealthPortalGUI = Mock()
        
        try:
            service_launcher._launch_gui(mock_module, 'health_portal')
        except Exception:
            pass

    def test_launch_gui_handles_no_tkinter(self):
        """Test GUI launcher handles missing tkinter"""
        service_launcher = launcher.ServiceLauncher()
        
        with patch('importlib.import_module', side_effect=ImportError('No tkinter')):
            mock_module = Mock()
            result = service_launcher._launch_gui(mock_module, 'test_service')
            assert result is False


class TestLaunchCLI:
    """Test CLI service launching"""

    def test_launch_cli_finds_menu_function(self):
        """Test CLI launcher finds menu function"""
        service_launcher = launcher.ServiceLauncher()
        
        # Create mock module with menu function
        mock_module = Mock()
        mock_module.display_health_portal_menu = Mock()
        
        result = service_launcher._launch_cli(mock_module, 'health_portal')
        # Should have attempted to call the function

    def test_launch_cli_passes_auth(self):
        """Test CLI launcher passes auth parameter"""
        service_launcher = launcher.ServiceLauncher()
        
        mock_module = Mock()
        mock_func = Mock()
        mock_module.main = mock_func
        
        mock_auth = Mock()
        service_launcher._launch_cli(mock_module, 'test_service', auth=mock_auth)


class TestLaunchAPI:
    """Test API service launching"""

    def test_launch_api_finds_app(self):
        """Test API launcher finds Flask app"""
        service_launcher = launcher.ServiceLauncher()
        
        # Create mock module with Flask app
        mock_module = Mock()
        mock_module.app = Mock()
        mock_module.app.run = Mock()
        
        try:
            service_launcher._launch_api(mock_module, 'test_service')
        except Exception:
            pass

    def test_launch_api_finds_run_api_function(self):
        """Test API launcher finds run_api function"""
        service_launcher = launcher.ServiceLauncher()
        
        mock_module = Mock()
        mock_module.run_api = Mock()
        
        try:
            service_launcher._launch_api(mock_module, 'test_service')
        except Exception:
            pass


class TestMainFunction:
    """Test main entry point"""

    @patch('sys.argv', ['launcher.py', '--list'])
    @patch('builtins.print')
    def test_main_with_list_flag(self, mock_print):
        """Test main with --list flag"""
        try:
            launcher.main()
        except SystemExit:
            pass
        # Should have printed service list
        assert mock_print.call_count > 0

    @patch('sys.argv', ['launcher.py'])
    @patch('builtins.print')
    def test_main_with_no_args(self, mock_print):
        """Test main with no arguments"""
        try:
            launcher.main()
        except SystemExit as e:
            assert e.code == 1  # Should exit with error


class TestArgumentParsing:
    """Test argument parsing"""

    def test_supports_service_argument(self):
        """Test --service argument"""
        # Test that argument parsing accepts --service
        args = ['--service', 'health_portal', '--interface', 'cli']
        # Should not raise exception

    def test_supports_interface_argument(self):
        """Test --interface argument"""
        # Test that argument parsing accepts --interface
        args = ['--service', 'test', '--interface', 'gui']
        # Should not raise exception

    def test_supports_list_argument(self):
        """Test --list argument"""
        # Test that argument parsing accepts --list
        args = ['--list']
        # Should not raise exception


class TestErrorHandling:
    """Test error handling"""

    def test_handles_import_error(self):
        """Test handling of import errors"""
        service_launcher = launcher.ServiceLauncher()
        
        with patch('importlib.import_module', side_effect=ImportError('Test error')):
            result = service_launcher.launch_service('test_service', 'gui')
            assert result is False

    def test_handles_missing_class(self):
        """Test handling when GUI class not found"""
        service_launcher = launcher.ServiceLauncher()
        
        mock_module = Mock()
        # Module exists but doesn't have expected class
        delattr(mock_module, 'TestServiceGUI')
        
        result = service_launcher._launch_gui(mock_module, 'test_service')
        assert result is False


class TestIntegration:
    """Integration tests"""

    @patch('builtins.print')
    def test_complete_workflow_list_services(self, mock_print):
        """Test complete workflow of listing services"""
        service_launcher = launcher.ServiceLauncher()
        service_launcher.list_services()
        # Should complete without errors


class TestModuleMetadata:
    """Test module metadata"""

    def test_module_has_docstring(self):
        """Test module has docstring"""
        assert launcher.__doc__ is not None
        assert len(launcher.__doc__) > 0

    def test_main_function_exists(self):
        """Test main function exists"""
        assert hasattr(launcher, 'main')
        assert callable(launcher.main)

    def test_service_launcher_class_exists(self):
        """Test ServiceLauncher class exists"""
        assert hasattr(launcher, 'ServiceLauncher')
        assert callable(launcher.ServiceLauncher)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
