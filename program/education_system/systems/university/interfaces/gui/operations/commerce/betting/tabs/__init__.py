"""Betting shop notebook tab mixins."""

from .account import AccountTabMixin
from .admin import AdminTabMixin
from .casino import CasinoTabMixin
from .predictions import PredictionsTabMixin
from .sports import SportsTabMixin

__all__ = [
    "AccountTabMixin", "AdminTabMixin", "CasinoTabMixin",
    "PredictionsTabMixin", "SportsTabMixin",
]
