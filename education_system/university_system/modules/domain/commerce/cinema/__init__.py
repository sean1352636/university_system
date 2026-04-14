"""
Cinema Module

Provides campus cinema management including screenings,
bookings, concessions, and event scheduling.
"""

from education_system.university_system.modules.domain.commerce.cinema.services import CinemaService
from education_system.university_system.modules.domain.commerce.cinema.cli import CinemaCLI
from education_system.university_system.modules.domain.commerce.cinema.gui import CinemaApp

__all__ = ['CinemaService', 'CinemaCLI', 'CinemaApp']
