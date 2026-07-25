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

from education_system.systems.university.domain.operations.campus.accessibility.services.accessibility_service import AccessibilityService
from education_system.systems.university.interfaces.cli.operations.campus.accessibility.accessibility_cli import AccessibilityCLI
from education_system.systems.university.interfaces.gui.operations.campus.accessibility.accessibility_gui import AccessibilityGUI

__all__ = ['AccessibilityService', 'AccessibilityCLI', 'AccessibilityGUI']
