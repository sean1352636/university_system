"""Component extracted from the legacy menu router."""
from __future__ import annotations

def display_transportation_parking_menu(auth):
    """Display the Transportation & Parking Management CLI menu"""
    # Redirect to parking management menu which now includes transportation
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.parking_management import display_parking_menu
    display_parking_menu()
