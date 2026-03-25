"""
Cinema CLI for University Management System

Provides comprehensive cinema services including movie listings, ticket bookings,
seat selection, concessions, membership program, and admin panel with full error handling.
"""

from education_system.university_system.modules.services.cli.cinema_cli.menu import cinema_menu, launch_cinema_cli

__all__ = ['cinema_menu', 'launch_cinema_cli']
