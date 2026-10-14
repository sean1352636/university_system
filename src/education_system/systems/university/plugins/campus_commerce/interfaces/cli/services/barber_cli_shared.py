"""Shared imports and module state for the split implementation."""

import logging

from datetime import datetime, timedelta

from typing import Optional, List, Dict

import secrets

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

from education_system.systems.university.infrastructure.shared_context import get_auth

try:
    from education_system.systems.university.plugins.campus_commerce.domain.barber.services.barber_core import (
        init_barber_db, init_extended_barber_db,
        ServiceManager, StaffManager, AppointmentManager, TransactionManager,
        ReportManager, CustomerManager, AnalyticsManager,
        TIME_SLOTS, APPOINTMENT_STATUSES
    )
    BARBER_CORE_AVAILABLE = True
except ImportError:
    BARBER_CORE_AVAILABLE = False
    TIME_SLOTS = [
        '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
        '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
        '15:00', '15:30', '16:00', '16:30', '17:00', '17:30'
    ]
    APPOINTMENT_STATUSES = ['scheduled', 'checked_in', 'in_progress', 'completed', 'cancelled', 'no_show']

    def init_barber_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS barber_services (
                        service_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        service_name TEXT NOT NULL,
                        price REAL NOT NULL,
                        duration_minutes INTEGER NOT NULL,
                        description TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS barber_staff (
                        staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staff_name TEXT NOT NULL,
                        specialization TEXT,
                        availability TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS barber_appointments (
                        appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        booking_ref TEXT UNIQUE NOT NULL,
                        user_id TEXT NOT NULL,
                        user_name TEXT,
                        user_email TEXT,
                        service_id INTEGER,
                        service_name TEXT,
                        staff_id INTEGER,
                        staff_name TEXT,
                        appointment_date DATE NOT NULL,
                        appointment_time TEXT NOT NULL,
                        duration_minutes INTEGER,
                        price REAL NOT NULL,
                        status TEXT DEFAULT 'scheduled',
                        payment_status TEXT DEFAULT 'pending',
                        payment_method TEXT,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (service_id) REFERENCES barber_services(service_id),
                        FOREIGN KEY (staff_id) REFERENCES barber_staff(staff_id)
                    )
                ''')

                # Barber transactions now use unified 'transactions' table with source_type='barber'
            return True
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            return False

    def init_extended_barber_db():
        """Extended database initialization"""
        pass

try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOG_AVAILABLE = True
except ImportError:
    ACTIVITY_LOG_AVAILABLE = False

logger = logging.getLogger(__name__)

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
