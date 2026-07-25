"""
Cinema Module

Provides campus cinema management including screenings,
bookings, concessions, and event scheduling.
"""

from education_system.systems.university.domain.operations.commerce.cinema.services import CinemaService
from education_system.systems.university.interfaces.cli.operations.commerce.cinema import CinemaCLI
from education_system.systems.university.interfaces.gui.operations.commerce.cinema import CinemaApp

__all__ = ['CinemaService', 'CinemaCLI', 'CinemaApp']
