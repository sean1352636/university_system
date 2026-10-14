"""Technician roster, performance metrics and schedules."""

import logging
from datetime import date, datetime, timedelta

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

import education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.nailbar_cli as _pkg
from .helpers import format_currency, format_date, is_staff, print_subheader

logger = logging.getLogger(__name__)


def view_technicians():
    """View available nail technicians"""
    try:
        print_subheader("NAIL TECHNICIANS")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT technician_id, technician_name, specialization,
                       working_hours, max_capacity, status
                FROM nailbar_technicians
                WHERE status = 'active'
                ORDER BY technician_name
            ''')
            technicians = cursor.fetchall()

            if not technicians:
                print("\n❌ No technicians available")
            else:
                for tech in technicians:
                    try:
                        tech_id, name, spec, hours, capacity, status = tech
                        print(f"\n{'━' * 70}")
                        print(f"ID {tech_id}: {name}")
                        if spec:
                            print(f"  Specialization: {spec}")
                        if hours:
                            print(f"  Working Hours: {hours}")
                        print(f"  Daily Capacity: {capacity} appointments")

                        # Get today's appointments count
                        today = date.today()
                        cursor = conn.execute('''
                            SELECT COUNT(*) FROM nailbar_appointments
                            WHERE technician_id = ? AND appointment_date = ?
                            AND status IN ('scheduled', 'in_progress')
                        ''', (tech_id, str(today)))
                        today_count = cursor.fetchone()[0]

                        availability = capacity - today_count
                        print(f"  Today's Availability: {availability}/{capacity} slots")

                    except Exception as e:
                        logger.error(f"Error displaying technician: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing technicians: {e}")
        print(f"❌ Error viewing technicians: {e}")

    input("\nPress Enter to continue...")


def technician_performance():
    """View technician performance metrics (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("TECHNICIAN PERFORMANCE METRICS")

        # Date range selection
        print("\nSelect time period:")
        print("1. Today")
        print("2. This Week")
        print("3. This Month")
        print("4. Custom Range")

        period = input("\nChoice: ").strip()

        today = date.today()
        if period == "1":
            start_date = today
            end_date = today
        elif period == "2":
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif period == "3":
            start_date = today.replace(day=1)
            end_date = today
        elif period == "4":
            start_str = input("Start date (YYYY-MM-DD): ").strip()
            end_str = input("End date (YYYY-MM-DD): ").strip()
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid choice")
            input("\nPress Enter to continue...")
            return

        print(f"\nPeriod: {format_date(str(start_date))} to {format_date(str(end_date))}")
        print("━" * 70)

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT technician_id, technician_name
                FROM nailbar_technicians
                WHERE status = 'active'
                ORDER BY technician_name
            ''')
            technicians = cursor.fetchall()

            if not technicians:
                print("\n❌ No technicians found")
                input("\nPress Enter to continue...")
                return

            for tech_id, tech_name in technicians:
                try:
                    # Get appointments count
                    cursor = conn.execute('''
                        SELECT COUNT(*) FROM nailbar_appointments
                        WHERE technician_id = ?
                        AND appointment_date BETWEEN ? AND ?
                        AND status = 'completed'
                    ''', (tech_id, str(start_date), str(end_date)))
                    appt_count = cursor.fetchone()[0]

                    # Get revenue
                    cursor = conn.execute('''
                        SELECT COALESCE(SUM(total_amount), 0)
                        FROM nailbar_payments
                        WHERE technician_id = ?
                        AND DATE(payment_date) BETWEEN ? AND ?
                        AND status = 'completed'
                    ''', (tech_id, str(start_date), str(end_date)))
                    revenue = cursor.fetchone()[0]

                    # Get tips
                    cursor = conn.execute('''
                        SELECT COALESCE(SUM(tip_amount), 0)
                        FROM nailbar_payments
                        WHERE technician_id = ?
                        AND DATE(payment_date) BETWEEN ? AND ?
                        AND status = 'completed'
                    ''', (tech_id, str(start_date), str(end_date)))
                    tips = cursor.fetchone()[0]

                    print(f"\n{tech_name} (ID: {tech_id})")
                    print(f"  Completed Appointments: {appt_count}")
                    print(f"  Revenue Generated: {format_currency(revenue)}")
                    print(f"  Tips Received: {format_currency(tips)}")
                    if appt_count > 0:
                        avg_revenue = revenue / appt_count
                        print(f"  Average per Appointment: {format_currency(avg_revenue)}")

                except Exception as e:
                    logger.error(f"Error calculating metrics for technician {tech_id}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error viewing technician performance: {e}")
        print(f"❌ Error viewing technician performance: {e}")

    input("\nPress Enter to continue...")


def manage_technician_schedule():
    """Manage technician schedules (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("MANAGE TECHNICIAN SCHEDULES")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT technician_id, technician_name, working_hours, max_capacity
                FROM nailbar_technicians
                WHERE status = 'active'
                ORDER BY technician_name
            ''')
            technicians = cursor.fetchall()

            if not technicians:
                print("\n❌ No technicians found")
                input("\nPress Enter to continue...")
                return

            print("\nTechnicians:")
            for tech_id, name, hours, capacity in technicians:
                print(f"ID {tech_id}: {name} - {hours} (Capacity: {capacity})")

        tech_id = input("\nEnter technician ID (0 to cancel): ").strip()
        if tech_id == "0":
            return

        if not tech_id.isdigit():
            print("❌ Invalid technician ID")
            input("\nPress Enter to continue...")
            return

        # Get current details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT technician_name, working_hours, max_capacity
                FROM nailbar_technicians
                WHERE technician_id = ? AND status = 'active'
            ''', (tech_id,))
            current = cursor.fetchone()

            if not current:
                print("❌ Technician not found")
                input("\nPress Enter to continue...")
                return

            curr_name, curr_hours, curr_capacity = current

        print(f"\nCurrent schedule for {curr_name}:")
        print(f"Working Hours: {curr_hours}")
        print(f"Daily Capacity: {curr_capacity} appointments")

        print("\nEnter new values (press Enter to keep current):")

        new_hours = input(f"Working Hours [{curr_hours}]: ").strip() or curr_hours

        capacity_input = input(f"Daily Capacity [{curr_capacity}]: ").strip()
        try:
            new_capacity = int(capacity_input) if capacity_input else curr_capacity
        except ValueError:
            print("❌ Invalid capacity, keeping current")
            new_capacity = curr_capacity

        # Confirmation
        confirm = input("\nSave changes? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Cancelled")
            input("\nPress Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE nailbar_technicians
                SET working_hours = ?, max_capacity = ?, updated_at = ?
                WHERE technician_id = ?
            ''', (new_hours, new_capacity, datetime.now().isoformat(), tech_id))

        print("\n✅ Schedule updated successfully!")
        _pkg.log_activity('update', 'nailbar_technician', technician_id=tech_id,
                    changes={'working_hours': new_hours, 'capacity': new_capacity})
        logger.info(f"Technician schedule updated: ID {tech_id}")

    except Exception as e:
        logger.error(f"Error managing technician schedule: {e}")
        print(f"❌ Error managing technician schedule: {e}")

    input("\nPress Enter to continue...")


__all__ = [
    'view_technicians', 'technician_performance', 'manage_technician_schedule',
]
