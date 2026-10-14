"""
Cinema domain service layer.

Provides reusable business-logic and data-access functions that are independent
of any GUI framework (tkinter, Flask, CLI, etc.).
"""

from education_system.systems.university.plugins.campus_commerce.domain.cinema.services.cinema_service import (
    CinemaService,
)

__all__ = ["CinemaService"]
