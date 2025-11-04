from __future__ import annotations

import logging
from datetime import datetime, timedelta

from university_system.modules.core.services.restaurant_misc.restaurant_context import (
    export_payroll_report,
    get_db_connection,
)

def payroll_calculations():
    """Calculate staff payroll"""
    try:
        print("\n" + "="*50)
        print("PAYROLL CALCULATIONS")
        print("="*50)

        print("\nOptions:")
        print("1. Calculate weekly payroll")
        print("2. Calculate monthly payroll")
        print("3. Individual payroll calculation")
        print("4. Export payroll report")
        print("5. Return to staff menu")

        choice = input("Choose an option (1-5): ")

        if choice == '1':
            calculate_weekly_payroll()
        elif choice == '2':
            calculate_monthly_payroll()
        elif choice == '3':
            calculate_individual_payroll()
        elif choice == '4':
            export_payroll_report()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in payroll_calculations: {e}")
        print(f"An error occurred: {e}")

def calculate_weekly_payroll():
    """Calculate weekly payroll for all staff"""
    try:
        # Get week start date
        start_date = input("Enter week start date (YYYY-MM-DD): ")
        try:
            week_start = datetime.strptime(start_date, '%Y-%m-%d')
            week_end = week_start + timedelta(days=6)
        except ValueError:
            print("Invalid date format.")
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get staff schedules for the week
        cursor.execute('''
            SELECT s.staff_id, s.name, s.role, s.hourly_rate,
                   SUM(CASE 
                       WHEN ss.actual_end IS NOT NULL AND ss.actual_start IS NOT NULL 
                       THEN (strftime('%s', ss.actual_end) - strftime('%s', ss.actual_start)) / 3600.0
                       ELSE (strftime('%s', ss.end_time) - strftime('%s', ss.start_time)) / 3600.0
                   END) as total_hours
            FROM restaurant_staff s
            LEFT JOIN restaurant_staff_schedules ss ON s.staff_id = ss.staff_id
                AND ss.date BETWEEN ? AND ?
                AND ss.status != 'Cancelled'
            WHERE s.status = 'Active'
            GROUP BY s.staff_id, s.name, s.role, s.hourly_rate
        ''', (start_date, week_end.strftime('%Y-%m-%d')))

        payroll_data = cursor.fetchall()

        if not payroll_data:
            print("No payroll data found for this week.")
            conn.close()
            return

        print(f"\n" + "="*100)
        print(f"WEEKLY PAYROLL ({start_date} to {week_end.strftime('%Y-%m-%d')})")
        print("="*100)
        print(f"{'Staff ID':<10} {'Name':<20} {'Role':<15} {'Hours':<8} {'Rate':<8} {'Gross Pay':<12}")
        print("-"*100)

        total_gross_pay = 0
        total_hours = 0

        for staff in payroll_data:
            hours = staff[4] or 0
            hourly_rate = staff[3] or 0
            gross_pay = hours * hourly_rate

            total_hours += hours
            total_gross_pay += gross_pay

            print(f"{staff[0]:<10} {staff[1]:<20} {staff[2]:<15} {hours:<8.1f} £{hourly_rate:<7.2f} £{gross_pay:<11.2f}")

        print("-"*100)
        print(f"{'TOTALS':<55} {total_hours:<8.1f} {'':<8} £{total_gross_pay:<11.2f}")
        print("="*100)

        conn.close()

    except Exception as e:
        logging.error(f"Error in calculate_weekly_payroll: {e}")
        print(f"An error occurred: {e}")

def calculate_monthly_payroll():
    """Calculate monthly payroll for all staff"""
    try:
        # Get month and year
        month = int(input("Enter month (1-12): "))
        year = int(input("Enter year (YYYY): "))

        if month < 1 or month > 12:
            print("Invalid month.")
            return

        # Calculate month start and end dates
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1) - timedelta(days=1)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT s.staff_id, s.name, s.role, s.hourly_rate,
                   SUM(CASE 
                       WHEN ss.actual_end IS NOT NULL AND ss.actual_start IS NOT NULL 
                       THEN (strftime('%s', ss.actual_end) - strftime('%s', ss.actual_start)) / 3600.0
                       ELSE (strftime('%s', ss.end_time) - strftime('%s', ss.start_time)) / 3600.0
                   END) as total_hours,
                   COUNT(ss.schedule_id) as days_worked
            FROM restaurant_staff s
            LEFT JOIN restaurant_staff_schedules ss ON s.staff_id = ss.staff_id
                AND ss.date BETWEEN ? AND ?
                AND ss.status != 'Cancelled'
            WHERE s.status = 'Active'
            GROUP BY s.staff_id, s.name, s.role, s.hourly_rate
        ''', (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))

        payroll_data = cursor.fetchall()

        print(f"\n" + "="*120)
        print(f"MONTHLY PAYROLL ({month_start.strftime('%B %Y')})")
        print("="*120)
        print(f"{'Staff ID':<10} {'Name':<20} {'Role':<15} {'Days':<6} {'Hours':<8} {'Rate':<8} {'Gross Pay':<12}")
        print("-"*120)

        total_gross_pay = 0
        total_hours = 0

        for staff in payroll_data:
            hours = staff[4] or 0
            days = staff[5] or 0
            hourly_rate = staff[3] or 0
            gross_pay = hours * hourly_rate

            total_hours += hours
            total_gross_pay += gross_pay

            print(f"{staff[0]:<10} {staff[1]:<20} {staff[2]:<15} {days:<6} {hours:<8.1f} £{hourly_rate:<7.2f} £{gross_pay:<11.2f}")

        print("-"*120)
        print(f"{'TOTALS':<61} {total_hours:<8.1f} {'':<8} £{total_gross_pay:<11.2f}")
        print("="*120)

        conn.close()

    except ValueError:
        print("Invalid month or year.")
    except Exception as e:
        logging.error(f"Error in calculate_monthly_payroll: {e}")
        print(f"An error occurred: {e}")

def calculate_individual_payroll():
    """Calculate payroll for individual staff member"""
    try:
        staff_id = input("Enter staff ID: ")
        start_date = input("Enter start date (YYYY-MM-DD): ")
        end_date = input("Enter end date (YYYY-MM-DD): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get staff info
        cursor.execute('SELECT name, role, hourly_rate FROM restaurant_staff WHERE staff_id = ?', (staff_id,))
        staff_info = cursor.fetchone()

        if not staff_info:
            print("Staff member not found.")
            conn.close()
            return

        # Get schedule data
        cursor.execute('''
            SELECT date, start_time, end_time, actual_start, actual_end, break_duration
            FROM restaurant_staff_schedules
            WHERE staff_id = ? AND date BETWEEN ? AND ?
            AND status != 'Cancelled'
            ORDER BY date
        ''', (staff_id, start_date, end_date))

        schedules = cursor.fetchall()

        if not schedules:
            print("No schedule data found for this period.")
            conn.close()
            return

        print(f"\n" + "="*100)
        print(f"INDIVIDUAL PAYROLL: {staff_info[0]} ({staff_info[1]})")
        print(f"Period: {start_date} to {end_date}")
        print("="*100)
        print(f"{'Date':<12} {'Scheduled':<18} {'Actual':<18} {'Hours':<8} {'Pay':<10}")
        print("-"*100)

        total_hours = 0
        total_pay = 0

        for schedule in schedules:
            # Calculate hours worked
            if schedule[3] and schedule[4]:  # actual times
                start_time = datetime.strptime(f"{schedule[0]} {schedule[3]}", '%Y-%m-%d %H:%M:%S')
                end_time = datetime.strptime(f"{schedule[0]} {schedule[4]}", '%Y-%m-%d %H:%M:%S')
            else:  # scheduled times
                start_time = datetime.strptime(f"{schedule[0]} {schedule[1]}", '%Y-%m-%d %H:%M')
                end_time = datetime.strptime(f"{schedule[0]} {schedule[2]}", '%Y-%m-%d %H:%M')

            hours_worked = (end_time - start_time).total_seconds() / 3600
            break_hours = (schedule[5] or 0) / 60  # convert minutes to hours
            net_hours = max(0, hours_worked - break_hours)

            shift_pay = net_hours * staff_info[2]
            total_hours += net_hours
            total_pay += shift_pay

            scheduled_str = f"{schedule[1]}-{schedule[2]}"
            actual_str = f"{schedule[3] or 'N/A'}-{schedule[4] or 'N/A'}" if schedule[3] else "As Scheduled"

            print(f"{schedule[0]:<12} {scheduled_str:<18} {actual_str:<18} {net_hours:<8.1f} £{shift_pay:<9.2f}")

        print("-"*100)
        print(f"{'TOTALS':<48} {total_hours:<8.1f} £{total_pay:<9.2f}")
        print(f"Hourly Rate: £{staff_info[2]:.2f}")
        print("="*100)

        conn.close()

    except Exception as e:
        logging.error(f"Error in calculate_individual_payroll: {e}")
        print(f"An error occurred: {e}")
