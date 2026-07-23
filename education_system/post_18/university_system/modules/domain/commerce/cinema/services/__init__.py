"""
Cinema domain service layer.

Provides reusable business-logic and data-access functions that are independent
of any GUI framework (tkinter, Flask, CLI, etc.).
"""

from education_system.post_18.university_system.modules.domain.commerce.cinema.services.cinema_service import (
    CinemaService,
)

__all__ = ["CinemaService"]
