"""Campus Navigation GUI tab mixins."""

from education_system.university_system.modules.domain.campus.campus_navigation.gui.tabs.directory import DirectoryTabMixin
from education_system.university_system.modules.domain.campus.campus_navigation.gui.tabs.route import RouteTabMixin
from education_system.university_system.modules.domain.campus.campus_navigation.gui.tabs.nearest import NearestTabMixin
from education_system.university_system.modules.domain.campus.campus_navigation.gui.tabs.favorites import FavoritesTabMixin

__all__ = [
    'DirectoryTabMixin',
    'RouteTabMixin',
    'NearestTabMixin',
    'FavoritesTabMixin',
]
