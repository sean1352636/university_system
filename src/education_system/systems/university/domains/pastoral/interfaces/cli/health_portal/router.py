"""Health portal CLI workflow extracted from the legacy module."""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from education_system.systems.university.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    get_connection,
)
from education_system import paths

logger = logging.getLogger(__name__)

# Preserve the legacy optional domain-portal discovery path.
current_dir = os.path.dirname(os.path.abspath(__file__))
domain_health_dir = os.path.join(current_dir, "..", "domain", "health", "portal")
if os.path.exists(domain_health_dir) and domain_health_dir not in sys.path:
    sys.path.insert(0, domain_health_dir)
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.appointments import schedule_appointment
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.backups import backup_management_menu
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.emergency_contacts import manage_emergency_contacts
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.exports import data_export_menu
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.medical_history import view_medical_history
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.records import view_health_records
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.reports.menu import advanced_reports_menu, generate_health_reports
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.security import security_audit_menu
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.vaccinations import view_vaccination_records

def display_health_portal_menu(auth):
    """Display the health portal menu."""
    if not auth.check_session():
        print("Please log in to access the health portal.")
        return

    try:
        # Try to import from the domain health portal
        from education_system.systems.university.domains.pastoral.domain.health.portal.health_portal_core import display_health_portal_menu
        display_health_portal_menu(auth)
    except ImportError as e:
        logger.warning(f"Could not import health portal core: {e}")
        # Fallback implementation
        display_basic_health_menu(auth)

def display_basic_health_menu(auth):
    """Basic health portal menu implementation."""
    while True:
        print("\n" + "="*100)
        print("                    HEALTH PORTAL SYSTEM")
        print("="*100)

        print("\nBASIC FEATURES:")
        print(f"{'1.  Health Records':<25} {'2.  Schedule Appointment':<25} {'3.  Medical History':<25} {'4.  Emergency Contacts':<25}")
        print(f"{'5.  Health Reports':<25} {'6.  Vaccination Records':<25}")

        print("\nADVANCED FEATURES:")
        print(f"{'7.  Data Export/Backup':<25} {'8.  Security & Audit':<25} {'9.  Backup Management':<25} {'10. Population Reports':<25}")

        print("\n0.  Return to Main Menu")
        print("="*100)

        choice = input("Enter your choice (0-10): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            view_health_records(auth)
        elif choice == '2':
            schedule_appointment(auth)
        elif choice == '3':
            view_medical_history(auth)
        elif choice == '4':
            manage_emergency_contacts(auth)
        elif choice == '5':
            generate_health_reports(auth)
        elif choice == '6':
            view_vaccination_records(auth)
        elif choice == '7':
            data_export_menu(auth)
        elif choice == '8':
            security_audit_menu(auth)
        elif choice == '9':
            backup_management_menu(auth)
        elif choice == '10':
            advanced_reports_menu(auth)
        else:
            print("Invalid choice. Please try again.")
