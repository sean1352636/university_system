"""Car Rental System Core Services Module"""

from education_system.systems.university.infrastructure.database.db import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from education_system.systems.university.infrastructure.database.db import get_db_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608

logger = logging.getLogger(__name__)

# Vehicle categories
VEHICLE_CATEGORIES = [
    'economy', 'compact', 'midsize', 'fullsize', 'luxury', 'suv',
    'minivan', 'pickup', 'convertible', 'electric', 'hybrid'
]

# Rental statuses
RENTAL_STATUSES = ['reserved', 'active', 'completed', 'cancelled', 'overdue']

# Vehicle statuses
VEHICLE_STATUSES = ['available', 'rented', 'maintenance', 'unavailable']

def init_carrental_db():
    """Initialize car rental database tables"""
    try:
        with transaction() as conn:
            # Vehicles table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS carrental_vehicles (
                    vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    registration_number TEXT UNIQUE NOT NULL,
                    make TEXT NOT NULL,
                    model TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    color TEXT,
                    seats INTEGER DEFAULT 5,
                    transmission TEXT DEFAULT 'automatic',
                    fuel_type TEXT DEFAULT 'petrol',
                    daily_rate DECIMAL(10,2) NOT NULL,
                    mileage INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'available',
                    image_path TEXT,
                    features TEXT,
                    insurance_info TEXT,
                    last_service_date TEXT,
                    next_service_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Rentals table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS carrental_rentals (
                    rental_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_number TEXT UNIQUE NOT NULL,
                    vehicle_id INTEGER NOT NULL,
                    customer_id TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    customer_email TEXT,
                    customer_phone TEXT,
                    license_number TEXT NOT NULL,
                    pickup_date TEXT NOT NULL,
                    pickup_time TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    return_time TEXT NOT NULL,
                    actual_return_date TEXT,
                    actual_return_time TEXT,
                    pickup_location TEXT,
                    return_location TEXT,
                    daily_rate DECIMAL(10,2) NOT NULL,
                    total_days INTEGER NOT NULL,
                    subtotal DECIMAL(10,2) NOT NULL,
                    insurance_fee DECIMAL(10,2) DEFAULT 0,
                    fuel_fee DECIMAL(10,2) DEFAULT 0,
                    late_fee DECIMAL(10,2) DEFAULT 0,
                    damage_fee DECIMAL(10,2) DEFAULT 0,
                    total_amount DECIMAL(10,2) NOT NULL,
                    deposit_amount DECIMAL(10,2) DEFAULT 0,
                    payment_status TEXT DEFAULT 'pending',
                    payment_method TEXT,
                    status TEXT DEFAULT 'reserved',
                    pickup_mileage INTEGER,
                    return_mileage INTEGER,
                    fuel_level_pickup TEXT,
                    fuel_level_return TEXT,
                    condition_notes TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vehicle_id) REFERENCES carrental_vehicles(vehicle_id)
                )
            ''')

            # Car rental transactions now use unified 'transactions' table with source_type='car_rental'

            # Maintenance records
            conn.execute('''
                CREATE TABLE IF NOT EXISTS carrental_maintenance (
                    maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL,
                    maintenance_type TEXT NOT NULL,
                    description TEXT,
                    cost DECIMAL(10,2) DEFAULT 0,
                    service_date TEXT NOT NULL,
                    next_service_date TEXT,
                    mileage_at_service INTEGER,
                    performed_by TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vehicle_id) REFERENCES carrental_vehicles(vehicle_id)
                )
            ''')

            # Insurance policies
            conn.execute('''
                CREATE TABLE IF NOT EXISTS carrental_insurance (
                    insurance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    daily_rate DECIMAL(10,2) NOT NULL,
                    coverage_type TEXT,
                    max_coverage DECIMAL(10,2),
                    deductible DECIMAL(10,2) DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        logger.info("Car rental database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize car rental database: {e}")
        return False

class VehicleManager:
    """Manages vehicle operations"""

    @staticmethod
    def add_vehicle(registration_number: str, make: str, model: str, year: int,
                   category: str, daily_rate: float, **kwargs) -> Optional[int]:
        """Add a new vehicle to the fleet"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO carrental_vehicles
                    (registration_number, make, model, year, category, daily_rate,
                     color, seats, transmission, fuel_type, mileage, features, insurance_info)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    registration_number, make, model, year, category, daily_rate,
                    kwargs.get('color'), kwargs.get('seats', 5),
                    kwargs.get('transmission', 'automatic'),
                    kwargs.get('fuel_type', 'petrol'),
                    kwargs.get('mileage', 0),
                    kwargs.get('features'),
                    kwargs.get('insurance_info')
                ))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to add vehicle: {e}")
            return None

    @staticmethod
    def update_vehicle(vehicle_id: int, **kwargs) -> bool:
        """Update vehicle details"""
        try:
            updates = []
            values = []
            for key, value in kwargs.items():
                if value is not None:
                    updates.append(validate_identifier(key, "column") + " = ?")
                    values.append(value)

            if not updates:
                return False

            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.append(vehicle_id)

            with transaction() as conn:
                conn.execute(
                    "UPDATE carrental_vehicles"
                    " SET " + ", ".join(updates) +
                    " WHERE vehicle_id = ?",
                    values)
            return True
        except Exception as e:
            logger.error(f"Failed to update vehicle: {e}")
            return False

    @staticmethod
    def get_vehicle(vehicle_id: int) -> Optional[Dict]:
        """Get vehicle by ID"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM carrental_vehicles WHERE vehicle_id = ?',
                    (vehicle_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get vehicle: {e}")
            return None

    @staticmethod
    def get_available_vehicles(category: str = None, pickup_date: str = None,
                               return_date: str = None) -> List[Dict]:
        """Get available vehicles with optional filters"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                query = "SELECT * FROM carrental_vehicles WHERE status = 'available'"
                params = []

                if category:
                    query += " AND category = ?"
                    params.append(category)

                query += " ORDER BY category, make, model"
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get available vehicles: {e}")
            return []

    @staticmethod
    def get_all_vehicles() -> List[Dict]:
        """Get all vehicles"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM carrental_vehicles ORDER BY make, model'
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get all vehicles: {e}")
            return []

    @staticmethod
    def update_vehicle_status(vehicle_id: int, status: str) -> bool:
        """Update vehicle status"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE carrental_vehicles
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE vehicle_id = ?
                ''', (status, vehicle_id))
            return True
        except Exception as e:
            logger.error(f"Failed to update vehicle status: {e}")
            return False

class RentalManager:
    """Manages rental operations"""

    @staticmethod
    def generate_rental_number() -> str:
        """Generate unique rental number"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"RNT-{timestamp}"

    @staticmethod
    def create_rental(vehicle_id: int, customer_id: str, customer_name: str,
                     license_number: str, pickup_date: str, pickup_time: str,
                     return_date: str, return_time: str, daily_rate: float,
                     **kwargs) -> Optional[int]:
        """Create a new rental reservation"""
        try:
            rental_number = RentalManager.generate_rental_number()

            # Calculate total days
            pickup = datetime.strptime(pickup_date, '%Y-%m-%d')
            return_dt = datetime.strptime(return_date, '%Y-%m-%d')
            total_days = max(1, (return_dt - pickup).days)

            subtotal = daily_rate * total_days
            insurance_fee = kwargs.get('insurance_fee', 0)
            total_amount = subtotal + insurance_fee

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO carrental_rentals
                    (rental_number, vehicle_id, customer_id, customer_name, customer_email,
                     customer_phone, license_number, pickup_date, pickup_time, return_date,
                     return_time, pickup_location, return_location, daily_rate, total_days,
                     subtotal, insurance_fee, total_amount, deposit_amount, status, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?)
                ''', (
                    rental_number, vehicle_id, customer_id, customer_name,
                    kwargs.get('customer_email'), kwargs.get('customer_phone'),
                    license_number, pickup_date, pickup_time, return_date, return_time,
                    kwargs.get('pickup_location'), kwargs.get('return_location'),
                    daily_rate, total_days, subtotal, insurance_fee, total_amount,
                    kwargs.get('deposit_amount', 0), kwargs.get('created_by')
                ))

                # Mark vehicle as rented
                conn.execute('''
                    UPDATE carrental_vehicles SET status = 'rented', updated_at = CURRENT_TIMESTAMP
                    WHERE vehicle_id = ?
                ''', (vehicle_id,))

                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create rental: {e}")
            return None

    @staticmethod
    def get_rental(rental_id: int) -> Optional[Dict]:
        """Get rental by ID"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT r.*, v.registration_number, v.make, v.model, v.category
                    FROM carrental_rentals r
                    JOIN carrental_vehicles v ON r.vehicle_id = v.vehicle_id
                    WHERE r.rental_id = ?
                ''', (rental_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get rental: {e}")
            return None

    @staticmethod
    def get_rentals_by_status(status: str = None) -> List[Dict]:
        """Get rentals filtered by status"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                if status:
                    cursor = conn.execute('''
                        SELECT r.*, v.registration_number, v.make, v.model
                        FROM carrental_rentals r
                        JOIN carrental_vehicles v ON r.vehicle_id = v.vehicle_id
                        WHERE r.status = ?
                        ORDER BY r.pickup_date DESC
                    ''', (status,))
                else:
                    cursor = conn.execute('''
                        SELECT r.*, v.registration_number, v.make, v.model
                        FROM carrental_rentals r
                        JOIN carrental_vehicles v ON r.vehicle_id = v.vehicle_id
                        ORDER BY r.pickup_date DESC
                    ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get rentals: {e}")
            return []

    @staticmethod
    def start_rental(rental_id: int, pickup_mileage: int, fuel_level: str,
                    condition_notes: str = None) -> bool:
        """Start a rental (vehicle pickup)"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE carrental_rentals
                    SET status = 'active', pickup_mileage = ?, fuel_level_pickup = ?,
                        condition_notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE rental_id = ?
                ''', (pickup_mileage, fuel_level, condition_notes, rental_id))
            return True
        except Exception as e:
            logger.error(f"Failed to start rental: {e}")
            return False

    @staticmethod
    def complete_rental(rental_id: int, return_mileage: int, fuel_level: str,
                       late_fee: float = 0, damage_fee: float = 0,
                       fuel_fee: float = 0) -> bool:
        """Complete a rental (vehicle return)"""
        try:
            now = datetime.now()
            with transaction() as conn:
                # Get rental details
                cursor = conn.execute(
                    'SELECT vehicle_id, total_amount FROM carrental_rentals WHERE rental_id = ?',
                    (rental_id,)
                )
                rental = cursor.fetchone()
                if not rental:
                    return False

                vehicle_id, current_total = rental
                new_total = current_total + late_fee + damage_fee + fuel_fee

                conn.execute('''
                    UPDATE carrental_rentals
                    SET status = 'completed', actual_return_date = ?, actual_return_time = ?,
                        return_mileage = ?, fuel_level_return = ?, late_fee = ?,
                        damage_fee = ?, fuel_fee = ?, total_amount = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rental_id = ?
                ''', (
                    now.strftime('%Y-%m-%d'), now.strftime('%H:%M'),
                    return_mileage, fuel_level, late_fee, damage_fee, fuel_fee,
                    new_total, rental_id
                ))

                # Update vehicle mileage and status
                conn.execute('''
                    UPDATE carrental_vehicles
                    SET status = 'available', mileage = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE vehicle_id = ?
                ''', (return_mileage, vehicle_id))

            return True
        except Exception as e:
            logger.error(f"Failed to complete rental: {e}")
            return False

    @staticmethod
    def cancel_rental(rental_id: int, reason: str = None) -> bool:
        """Cancel a rental"""
        try:
            with transaction() as conn:
                # Get vehicle ID
                cursor = conn.execute(
                    'SELECT vehicle_id FROM carrental_rentals WHERE rental_id = ?',
                    (rental_id,)
                )
                result = cursor.fetchone()
                if not result:
                    return False

                vehicle_id = result[0]

                conn.execute('''
                    UPDATE carrental_rentals
                    SET status = 'cancelled', condition_notes = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rental_id = ?
                ''', (reason, rental_id))

                # Make vehicle available again
                conn.execute('''
                    UPDATE carrental_vehicles
                    SET status = 'available', updated_at = CURRENT_TIMESTAMP
                    WHERE vehicle_id = ?
                ''', (vehicle_id,))

            return True
        except Exception as e:
            logger.error(f"Failed to cancel rental: {e}")
            return False

class TransactionManager:
    """Manages payment transactions.

    This is the single Finance posting point for car rental: the GUI and
    both CLIs call ``record_payment`` / ``record_refund`` /
    ``refund_transaction`` and never post to Finance themselves. The local
    write always commits first; a Finance posting failure is logged and
    never rolls the local sale back.
    """

    FINANCE_SOURCE = 'CarRental'

    @staticmethod
    def _rental_context(rental_id: int, customer_id: Optional[str]) -> Dict[str, Any]:
        rental = RentalManager.get_rental(rental_id) or {}
        return {
            'rental': rental,
            'ref': rental.get('rental_number') or str(rental_id),
            'student_id': customer_id or rental.get('customer_id') or 'EXTERNAL',
            'vehicle': f"{rental.get('make', '')} {rental.get('model', '')}".strip(),
        }

    @staticmethod
    def record_payment(rental_id: int, customer_id: str, amount: float,
                      payment_method: str, processed_by: str = None,
                      description: str = None) -> Optional[int]:
        """Record a rental payment locally and post it to Finance.

        ``payment_method='finance_account'`` debits the student's finance
        account first (that debit is itself the Finance posting); if the
        debit fails nothing is written locally and ``None`` is returned.
        Any other method writes the local transaction and then posts the
        cash-in via ``record_payment_to_finance``.
        """
        try:
            import random
            ctx = TransactionManager._rental_context(rental_id, customer_id)
            student_id = ctx['student_id']
            ref_number = f"PAY-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

            if payment_method == 'finance_account':
                from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
                    process_student_finance_account_payment,
                )
                result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=amount,
                    description=description or f"Car rental payment - {ctx['ref']}",
                    transaction_source=TransactionManager.FINANCE_SOURCE,
                    transaction_ref=ctx['ref'],
                    processed_by=processed_by or 'System',
                )
                if not result.get('success'):
                    logger.warning(
                        "Car rental finance-account payment refused for rental %s: %s",
                        rental_id, result.get('message'),
                    )
                    return None

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO transactions
                    (source_type, reference_id, reference_type, customer_id, amount, transaction_type, payment_method,
                     reference_number, status, processed_by)
                    VALUES ('car_rental', ?, 'rental', ?, ?, 'payment', ?, ?, 'completed', ?)
                ''', (rental_id, customer_id, amount, payment_method, ref_number, processed_by))
                txn_id = cursor.lastrowid

                # Update rental payment status
                conn.execute('''
                    UPDATE carrental_rentals
                    SET payment_status = 'paid', payment_method = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rental_id = ?
                ''', (payment_method, rental_id))

            if payment_method != 'finance_account':
                try:
                    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
                        record_payment_to_finance,
                    )
                    payment_id = record_payment_to_finance(
                        student_id=student_id,
                        amount=amount,
                        payment_method=payment_method,
                        transaction_source=TransactionManager.FINANCE_SOURCE,
                        transaction_ref=ctx['ref'],
                        notes=f"Car rental: {ctx['vehicle']}",
                        created_by=processed_by,
                    )
                    if payment_id:
                        logger.info(f"Revenue recorded to finance: \u00a3{amount:.2f} for rental {ctx['ref']}")
                    else:
                        logger.warning("Finance posting returned no id for car rental %s", rental_id)
                except Exception:
                    logger.exception("Finance posting failed for car rental payment (rental %s)", rental_id)

            return txn_id
        except Exception as e:
            logger.error(f"Failed to record payment: {e}")
            return None

    @staticmethod
    def _post_refund(rental_id: Optional[int], customer_id: Optional[str], amount: float,
                     reason: str, refund_method: str, refund_ref: str,
                     processed_by: str = None, original_transaction_id=None) -> Optional[int]:
        """Post a refund to Finance (unified_refunds + GL). Never raises."""
        try:
            from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
                record_refund_to_finance,
            )
            ctx = TransactionManager._rental_context(rental_id, customer_id) if rental_id else {
                'ref': refund_ref, 'student_id': customer_id or 'EXTERNAL', 'vehicle': ''}
            return record_refund_to_finance(
                student_id=ctx['student_id'],
                refund_amount=amount,
                original_payment_id=None,
                refund_reason=reason or 'Car rental refund',
                refund_type='full',
                transaction_source='Car Rental',
                transaction_ref=refund_ref,
                refund_method=refund_method,
                requested_by=processed_by,
                notes=(f"Rental {ctx['ref']}" + (f"; transaction {original_transaction_id}" if original_transaction_id else "")),
            )
        except Exception:
            logger.exception("Finance posting failed for car rental refund %s", refund_ref)
            return None

    @staticmethod
    def record_refund(rental_id: int, customer_id: str, amount: float,
                     reason: str, processed_by: str = None,
                     refund_method: str = 'cash') -> Optional[int]:
        """Record a refund transaction locally and post it to Finance."""
        try:
            import random
            ref_number = f"REF-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO transactions
                    (source_type, reference_id, reference_type, customer_id, amount, transaction_type, payment_method,
                     reference_number, status, notes, processed_by)
                    VALUES ('car_rental', ?, 'rental', ?, ?, 'refund', 'refund', ?, 'completed', ?, ?)
                ''', (rental_id, customer_id, amount, ref_number, reason, processed_by))
                txn_id = cursor.lastrowid

            TransactionManager._post_refund(
                rental_id, customer_id, amount, reason, refund_method, ref_number, processed_by,
            )
            return txn_id
        except Exception as e:
            logger.error(f"Failed to record refund: {e}")
            return None

    @staticmethod
    def refund_transaction(transaction_id: int, amount: float, refund_method: str,
                          customer_id: str = None, processed_by: str = None,
                          reason: str = None) -> Optional[Dict[str, Any]]:
        """Refund an existing car-rental payment transaction.

        Marks the local ``transactions`` row refunded, posts the refund to
        Finance, and for ``refund_method='student_account'`` credits the
        student's finance account. Returns ``{'refund_ref', 'refund_id',
        'new_balance'}`` or ``None`` if the local write failed.
        """
        refund_ref = f"CARRENTAL-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            with transaction() as conn:
                row = conn.execute(
                    "SELECT customer_id, reference_id FROM transactions "
                    "WHERE transaction_id = ? AND source_type = 'car_rental'",
                    (transaction_id,),
                ).fetchone()
                if row:
                    customer_id = customer_id or row[0]
                    rental_id = row[1]
                else:
                    rental_id = None
                conn.execute('''
                    UPDATE transactions
                    SET status = 'refunded',
                        reference_number = ?
                    WHERE transaction_id = ? AND source_type = 'car_rental'
                ''', (refund_ref, transaction_id))
        except Exception as e:
            logger.error(f"Failed to refund car rental transaction {transaction_id}: {e}")
            return None

        new_balance = None
        if refund_method == 'student_account' and customer_id:
            try:
                from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
                    top_up_student_finance_account,
                )
                credit = top_up_student_finance_account(
                    student_id=customer_id,
                    amount=amount,
                    payment_method='Refund',
                    processed_by=processed_by or 'System',
                    description=f'Car rental refund - {refund_ref}',
                )
                if credit.get('success'):
                    new_balance = credit.get('new_balance')
                else:
                    logger.warning("Car rental refund %s: student account credit failed: %s",
                                   refund_ref, credit.get('message'))
            except Exception:
                logger.exception("Car rental refund %s: student account credit failed", refund_ref)

        try:
            rental_id_int = int(rental_id) if rental_id is not None else None
        except (TypeError, ValueError):
            rental_id_int = None
        refund_id = TransactionManager._post_refund(
            rental_id_int, customer_id, amount, reason, refund_method, refund_ref,
            processed_by, original_transaction_id=transaction_id,
        )
        return {'refund_ref': refund_ref, 'refund_id': refund_id, 'new_balance': new_balance}

    @staticmethod
    def get_transactions(rental_id: int = None) -> List[Dict]:
        """Get transactions"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                if rental_id:
                    cursor = conn.execute(
                        'SELECT * FROM transactions WHERE source_type = ? AND reference_id = ? AND reference_type = ? ORDER BY created_at DESC',
                        ('car_rental', rental_id, 'rental')
                    )
                else:
                    cursor = conn.execute(
                        'SELECT * FROM transactions WHERE source_type = ? ORDER BY created_at DESC LIMIT 100',
                        ('car_rental',)
                    )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            return []

class ReportManager:
    """Manages reports and analytics"""

    @staticmethod
    def get_fleet_summary() -> Dict:
        """Get fleet summary statistics"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        COUNT(*) as total_vehicles,
                        SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
                        SUM(CASE WHEN status = 'rented' THEN 1 ELSE 0 END) as rented,
                        SUM(CASE WHEN status = 'maintenance' THEN 1 ELSE 0 END) as maintenance
                    FROM carrental_vehicles
                ''')
                return dict(cursor.fetchone())
        except Exception as e:
            logger.error(f"Failed to get fleet summary: {e}")
            return {}

    @staticmethod
    def get_revenue_report(start_date: str = None, end_date: str = None) -> Dict:
        """Get revenue report"""
        try:
            with get_db_connection() as conn:
                query = '''
                    SELECT
                        COUNT(*) as total_rentals,
                        SUM(total_amount) as total_revenue,
                        AVG(total_amount) as avg_rental_value,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_rentals
                    FROM carrental_rentals
                    WHERE payment_status = 'paid'
                '''
                params = []

                if start_date and end_date:
                    query += " AND created_at BETWEEN ? AND ?"
                    params.extend([start_date, end_date])

                cursor = conn.execute(query, params)
                return dict(cursor.fetchone())
        except Exception as e:
            logger.error(f"Failed to get revenue report: {e}")
            return {}

    @staticmethod
    def get_popular_vehicles(limit: int = 10) -> List[Dict]:
        """Get most popular vehicles by rental count"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT v.vehicle_id, v.make, v.model, v.category,
                           COUNT(r.rental_id) as rental_count,
                           SUM(r.total_amount) as total_revenue
                    FROM carrental_vehicles v
                    LEFT JOIN carrental_rentals r ON v.vehicle_id = r.vehicle_id
                    GROUP BY v.vehicle_id
                    ORDER BY rental_count DESC
                    LIMIT ?
                ''', (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get popular vehicles: {e}")
            return []

    @staticmethod
    def generate_admin_report() -> str:
        """Generate comprehensive admin report"""
        try:
            fleet = ReportManager.get_fleet_summary()
            revenue = ReportManager.get_revenue_report()
            popular = ReportManager.get_popular_vehicles(5)

            report = f"""
CAR RENTAL SYSTEM - ADMIN REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 50}

FLEET SUMMARY
-------------
Total Vehicles: {fleet.get('total_vehicles', 0)}
Available: {fleet.get('available', 0)}
Currently Rented: {fleet.get('rented', 0)}
In Maintenance: {fleet.get('maintenance', 0)}

REVENUE SUMMARY
---------------
Total Rentals: {revenue.get('total_rentals', 0)}
Completed Rentals: {revenue.get('completed_rentals', 0)}
Total Revenue: £{revenue.get('total_revenue', 0):.2f}
Average Rental Value: £{revenue.get('avg_rental_value', 0):.2f}

TOP 5 VEHICLES BY RENTALS
-------------------------
"""
            for i, v in enumerate(popular, 1):
                report += f"{i}. {v['make']} {v['model']} - {v['rental_count']} rentals (£{v['total_revenue'] or 0:.2f})\n"

            return report
        except Exception as e:
            logger.error(f"Failed to generate admin report: {e}")
            return "Error generating report"
