"""Nail bar database bootstrap.

Prefers ``nailbar_core``; falls back to the schema the CLI queries are written
against when the core service is unavailable.
"""

import logging

from education_system.systems.university.infrastructure.database.db import transaction

from .constants import NAIL_TREATMENTS as _FALLBACK_TREATMENTS

NAIL_TREATMENTS = _FALLBACK_TREATMENTS

# Import nailbar core services
try:
    from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import (
        init_nailbar_db
    )
    NAILBAR_CORE_AVAILABLE = True
except ImportError:
    NAILBAR_CORE_AVAILABLE = False

    def init_nailbar_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                # Treatments table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS nailbar_treatments (
                        treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        treatment_name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        price REAL NOT NULL,
                        duration_minutes INTEGER NOT NULL,
                        description TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Technicians table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS nailbar_technicians (
                        technician_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        technician_name TEXT NOT NULL,
                        specialization TEXT,
                        working_hours TEXT,
                        max_capacity INTEGER DEFAULT 8,
                        availability TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Appointments table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS nailbar_appointments (
                        appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        booking_ref TEXT UNIQUE NOT NULL,
                        user_id TEXT NOT NULL,
                        user_name TEXT,
                        user_email TEXT,
                        treatment_ids TEXT,
                        treatment_names TEXT,
                        technician_id INTEGER,
                        technician_name TEXT,
                        appointment_date DATE NOT NULL,
                        appointment_time TEXT NOT NULL,
                        total_duration INTEGER,
                        total_price REAL NOT NULL,
                        status TEXT DEFAULT 'scheduled',
                        notes TEXT,
                        completion_notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (technician_id) REFERENCES nailbar_technicians(technician_id)
                    )
                ''')

                # Payments table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS nailbar_payments (
                        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        booking_ref TEXT NOT NULL,
                        appointment_id INTEGER,
                        amount REAL NOT NULL,
                        tip_amount REAL DEFAULT 0.0,
                        total_amount REAL NOT NULL,
                        payment_method TEXT NOT NULL,
                        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        technician_id INTEGER,
                        technician_name TEXT,
                        receipt_number TEXT UNIQUE NOT NULL,
                        status TEXT DEFAULT 'completed',
                        FOREIGN KEY (appointment_id) REFERENCES nailbar_appointments(appointment_id),
                        FOREIGN KEY (technician_id) REFERENCES nailbar_technicians(technician_id)
                    )
                ''')

                # Insert default treatments if none exist
                cursor = conn.execute('SELECT COUNT(*) FROM nailbar_treatments')
                if cursor.fetchone()[0] == 0:
                    for key, treatment in NAIL_TREATMENTS.items():
                        conn.execute('''
                            INSERT INTO nailbar_treatments
                            (treatment_name, category, price, duration_minutes, description, status)
                            VALUES (?, ?, ?, ?, ?, 'active')
                        ''', (
                            treatment['name'],
                            treatment.get('category', 'general'),
                            treatment['price'],
                            treatment['duration'],
                            f"Professional {treatment['name'].lower()} service"
                        ))

                # Insert default technicians if none exist
                cursor = conn.execute('SELECT COUNT(*) FROM nailbar_technicians')
                if cursor.fetchone()[0] == 0:
                    default_technicians = [
                        ('Sarah Johnson', 'Manicure, Gel Nails', 'Mon-Fri: 9:00-17:00', 8),
                        ('Emily Chen', 'Pedicure, Spa Treatments', 'Mon-Sat: 10:00-18:00', 10),
                        ('Maria Garcia', 'Nail Art, Extensions', 'Tue-Sat: 11:00-19:00', 6),
                        ('Sophie Williams', 'All Treatments', 'Mon-Fri: 8:00-16:00', 8),
                    ]
                    for name, spec, hours, capacity in default_technicians:
                        conn.execute('''
                            INSERT INTO nailbar_technicians
                            (technician_name, specialization, working_hours, max_capacity, status)
                            VALUES (?, ?, ?, ?, 'active')
                        ''', (name, spec, hours, capacity))

            return True
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            return False


__all__ = ['init_nailbar_db', 'NAIL_TREATMENTS', 'NAILBAR_CORE_AVAILABLE']
