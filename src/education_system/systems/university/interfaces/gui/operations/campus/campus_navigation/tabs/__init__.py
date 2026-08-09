"""Campus Navigation GUI tab mixins."""

from education_system.systems.university.interfaces.gui.operations.campus.campus_navigation.tabs.directory import DirectoryTabMixin
from education_system.systems.university.interfaces.gui.operations.campus.campus_navigation.tabs.route import RouteTabMixin
from education_system.systems.university.interfaces.gui.operations.campus.campus_navigation.tabs.nearest import NearestTabMixin
from education_system.systems.university.interfaces.gui.operations.campus.campus_navigation.tabs.favorites import FavoritesTabMixin

__all__ = [
    'DirectoryTabMixin',
    'RouteTabMixin',
    'NearestTabMixin',
    'FavoritesTabMixin',
]
