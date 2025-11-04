"""
Unified University System Services Launcher

This module provides a centralized entry point for launching any
university system service in any interface mode (GUI, CLI, or API).

Features:
- Auto-discovery of available services
- Consistent launching interface
- Error handling and fallbacks
- Service validation and health checks

Usage Examples:
    # Launch health portal GUI
    python -m university_system.services.launcher --service health_portal --interface gui

    # Launch library CLI
    python -m university_system.services.launcher --service library --interface cli

    # List all available services
    python -m university_system.services.launcher --list
"""

import sys
import argparse
import importlib
import os
from pathlib import Path
from typing import Dict, List, Optional


class ServiceLauncher:
    """Central launcher for all university system services."""

    def __init__(self):
        self.available_services = self._discover_services()

    def _discover_services(self) -> Dict[str, Dict[str, str]]:
        """Discover all available services across all interface types."""
        services = {}
        base_path = Path(__file__).parent

        for interface_type in ['gui', 'cli', 'api']:
            interface_path = base_path / interface_type
            if interface_path.exists():
                for service_file in interface_path.glob('*.py'):
                    if service_file.name != '__init__.py':
                        service_name = service_file.stem
                        if service_name not in services:
                            services[service_name] = {}
                        services[service_name][interface_type] = str(service_file)

        return services

    def list_services(self) -> None:
        """List all available services and their supported interfaces."""
        print("\\nAvailable University System Services:")
        print("=" * 50)

        for service_name, interfaces in self.available_services.items():
            print(f"\\n📋 {service_name}")
            for interface_type in ['gui', 'cli', 'api']:
                status = "✅" if interface_type in interfaces else "❌"
                print(f"  {status} {interface_type.upper()}")

        print(f"\\nTotal Services: {len(self.available_services)}")
        print("\\nUsage: python -m university_system.services.launcher --service <name> --interface <type>")

    def launch_service(self, service_name: str, interface_type: str, **kwargs) -> bool:
        """Launch a specific service with the specified interface."""
        if service_name not in self.available_services:
            print(f"❌ Service '{service_name}' not found.")
            print("Run with --list to see available services.")
            return False

        if interface_type not in self.available_services[service_name]:
            print(f"❌ Interface '{interface_type}' not available for service '{service_name}'.")
            available = list(self.available_services[service_name].keys())
            print(f"Available interfaces: {', '.join(available)}")
            return False

        try:
            module_path = f"university_system.services.{interface_type}.{service_name}"
            module = importlib.import_module(module_path)

            if interface_type == 'gui':
                return self._launch_gui(module, service_name, **kwargs)
            elif interface_type == 'cli':
                return self._launch_cli(module, service_name, **kwargs)
            elif interface_type == 'api':
                return self._launch_api(module, service_name, **kwargs)

        except ImportError as e:
            print(f"❌ Failed to import {service_name} {interface_type}: {e}")
            return False
        except Exception as e:
            print(f"❌ Failed to launch {service_name} {interface_type}: {e}")
            return False

    def _launch_gui(self, module, service_name: str, **kwargs) -> bool:
        """Launch a GUI service."""
        try:
            import tkinter as tk

            # Create root window
            root = tk.Tk()

            # Find and instantiate the GUI class
            class_name = f"{service_name.title().replace('_', '')}GUI"
            if hasattr(module, class_name):
                gui_class = getattr(module, class_name)
                app = gui_class(root)

                print(f"🚀 Launching {service_name} GUI...")
                root.mainloop()
                return True
            else:
                print(f"❌ GUI class '{class_name}' not found in {service_name}")
                return False

        except ImportError:
            print("❌ tkinter not available. Cannot launch GUI services.")
            return False
        except Exception as e:
            print(f"❌ Failed to launch GUI: {e}")
            return False

    def _launch_cli(self, module, service_name: str, **kwargs) -> bool:
        """Launch a CLI service."""
        try:
            # Look for main menu function
            menu_functions = [
                f"display_{service_name}_menu",
                f"{service_name}_menu",
                f"main_menu",
                "main"
            ]

            for func_name in menu_functions:
                if hasattr(module, func_name):
                    func = getattr(module, func_name)
                    print(f"🚀 Launching {service_name} CLI...")

                    # Pass auth if available
                    if 'auth' in kwargs:
                        func(kwargs['auth'])
                    else:
                        func()
                    return True

            print(f"❌ No main function found for {service_name} CLI")
            print(f"Available functions: {[name for name in dir(module) if not name.startswith('_')]}")
            return False

        except Exception as e:
            print(f"❌ Failed to launch CLI: {e}")
            return False

    def _launch_api(self, module, service_name: str, **kwargs) -> bool:
        """Launch an API service."""
        try:
            # Look for Flask app or API runner
            if hasattr(module, 'app'):
                app = module.app
                print(f"🚀 Launching {service_name} API on http://localhost:5000...")
                app.run(debug=True, **kwargs)
                return True
            elif hasattr(module, 'run_api'):
                func = module.run_api
                print(f"🚀 Launching {service_name} API...")
                func(**kwargs)
                return True
            else:
                print(f"❌ No API runner found for {service_name}")
                return False

        except ImportError:
            print("❌ Flask not available. Cannot launch API services.")
            return False
        except Exception as e:
            print(f"❌ Failed to launch API: {e}")
            return False


def main():
    """Main entry point for the service launcher."""
    parser = argparse.ArgumentParser(
        description="University System Services Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--service', '-s',
        help='Name of the service to launch'
    )

    parser.add_argument(
        '--interface', '-i',
        choices=['gui', 'cli', 'api'],
        help='Interface type to use'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available services'
    )

    args = parser.parse_args()

    launcher = ServiceLauncher()

    if args.list:
        launcher.list_services()
        return

    if not args.service or not args.interface:
        print("❌ Both --service and --interface are required")
        print("Use --list to see available services")
        parser.print_help()
        sys.exit(1)

    success = launcher.launch_service(args.service, args.interface)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()