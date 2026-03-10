"""
Accessibility Services Portal Module

This module provides comprehensive accessibility services for students with disabilities,
ensuring FERPA compliance and privacy throughout all operations.

Features:
- Accommodation request workflow
- Real-time status tracking
- Document management for medical documentation
- Direct messaging with disability services staff
- Faculty notification system
- Accommodation renewal tracking

Submodules:
- services: Business logic and database operations
- cli: Command-line interface
- gui: Graphical user interface
"""

from education_system.university_system.modules.domain.accessibility.services.accessibility_service import AccessibilityService
from education_system.university_system.modules.domain.accessibility.cli.accessibility_cli import AccessibilityCLI
from education_system.university_system.modules.domain.accessibility.gui.accessibility_gui import AccessibilityGUI

__all__ = ['AccessibilityService', 'AccessibilityCLI', 'AccessibilityGUI']
