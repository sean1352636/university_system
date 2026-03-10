"""Campus Navigation GUI tab mixins."""

from .directory import DirectoryTabMixin
from .route import RouteTabMixin
from .nearest import NearestTabMixin
from .favorites import FavoritesTabMixin

__all__ = [
    'DirectoryTabMixin',
    'RouteTabMixin',
    'NearestTabMixin',
    'FavoritesTabMixin',
]
