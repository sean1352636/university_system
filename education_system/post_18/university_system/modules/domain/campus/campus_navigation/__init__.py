"""
Campus Navigation Module

Provides interactive campus maps, accessible route planning, and location finding
for students, staff, and visitors.

Features:
- Building directory with search and filtering
- Interactive campus map visualization
- Route planning with accessible route options
- "Find nearest" functionality for amenities
- Points of interest (POI) database
- User favorites for frequently visited locations
- Navigation history tracking
- Accessibility features reporting

Sub-modules:
- services: Navigation service layer with pathfinding algorithms
- cli: Command-line interface
- gui: Graphical user interface with interactive map
"""

from education_system.post_18.university_system.modules.domain.campus.campus_navigation.services.navigation_service import NavigationService
from education_system.post_18.university_system.modules.domain.campus.campus_navigation.cli.navigation_cli import NavigationCLI
from education_system.post_18.university_system.modules.domain.campus.campus_navigation.gui.navigation_gui import NavigationGUI

__all__ = [
    'NavigationService',
    'NavigationCLI',
    'NavigationGUI'
]

__version__ = '1.0.0'
