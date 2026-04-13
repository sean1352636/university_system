"""
Cinema Module

Provides campus cinema management including screenings,
bookings, concessions, and event scheduling.
"""

from education_system.university_system.modules.domain.cinema.services import CinemaService
from education_system.university_system.modules.domain.cinema.cli import CinemaCLI
from education_system.university_system.modules.domain.cinema.gui import CinemaApp

__all__ = ['CinemaService', 'CinemaCLI', 'CinemaApp']
