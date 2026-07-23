from __future__ import annotations

import logging
from datetime import datetime, timedelta

from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.restaurant_context import (
    export_payroll_report,
    get_db_connection,
)
from education_system.post_18.university_system.core.i18n import get_text

def payroll_calculations():
    """Calculate staff payroll"""
    try:
        print("\n" + "="*50)
        print(get_text("restaurant.payroll.title"))
        print("="*50)

        print("\n" + get_text("restaurant.payroll.options_title"))
        print("1. " + get_text("restaurant.payroll.option_weekly"))
        print("2. " + get_text("restaurant.payroll.option_monthly"))
        print("3. " + get_text("restaurant.payroll.option_individual"))
        print("4. " + get_text("restaurant.payroll.option_export"))
        print("5. " + get_text("restaurant.payroll.option_return"))

        choice = input(get_text("restaurant.payroll.choose_option") + " ")

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
            print(get_text("restaurant.payroll.invalid_choice"))

    except Exception as e:
        logging.error(f"Error in payroll_calculations: {e}")
        print(get_text("restaurant.payroll.error_occurred", error=str(e)))

def calculate_weekly_payroll():
    """Calculate weekly payroll for all staff"""
    try:
        # Get week start date
        start_date = input(get_text("restaurant.payroll.weekly.enter_start_date") + " ")
        try:
            week_start = datetime.strptime(start_date, '%Y-%m-%d')
            week_end = week_start + timedelta(days=6)
        except ValueError:
            print(get_text("restaurant.payroll.weekly.invalid_date"))
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
            print(get_text("restaurant.payroll.weekly.no_data"))
            conn.close()
            return

        print("\n" + "="*100)
        print(get_text("restaurant.payroll.weekly.title", start=start_date, end=week_end.strftime('%Y-%m-%d')))
        print("="*100)
        print(f"{get_text('restaurant.payroll.weekly.header_staff_id'):<10} {get_text('restaurant.payroll.weekly.header_name'):<20} {get_text('restaurant.payroll.weekly.header_role'):<15} {get_text('restaurant.payroll.weekly.header_hours'):<8} {get_text('restaurant.payroll.weekly.header_rate'):<8} {get_text('restaurant.payroll.weekly.header_gross_pay'):<12}")
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
        print(f"{get_text('restaurant.payroll.weekly.totals'):<55} {total_hours:<8.1f} {'':<8} £{total_gross_pay:<11.2f}")
        print("="*100)

        conn.close()

    except Exception as e:
        logging.error(f"Error in calculate_weekly_payroll: {e}")
        print(get_text("restaurant.payroll.error_occurred", error=str(e)))

def calculate_monthly_payroll():
    """Calculate monthly payroll for all staff"""
    try:
        # Get month and year
        month = int(input(get_text("restaurant.payroll.monthly.enter_month") + " "))
        year = int(input(get_text("restaurant.payroll.monthly.enter_year") + " "))

        if month < 1 or month > 12:
            print(get_text("restaurant.payroll.monthly.invalid_month"))
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

        print("\n" + "="*120)
        print(get_text("restaurant.payroll.monthly.title", period=month_start.strftime('%B %Y')))
        print("="*120)
        print(f"{get_text('restaurant.payroll.weekly.header_staff_id'):<10} {get_text('restaurant.payroll.weekly.header_name'):<20} {get_text('restaurant.payroll.weekly.header_role'):<15} {get_text('restaurant.payroll.monthly.header_days'):<6} {get_text('restaurant.payroll.weekly.header_hours'):<8} {get_text('restaurant.payroll.weekly.header_rate'):<8} {get_text('restaurant.payroll.weekly.header_gross_pay'):<12}")
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
        print(f"{get_text('restaurant.payroll.weekly.totals'):<61} {total_hours:<8.1f} {'':<8} £{total_gross_pay:<11.2f}")
        print("="*120)

        conn.close()

    except ValueError:
        print(get_text("restaurant.payroll.monthly.invalid_input"))
    except Exception as e:
        logging.error(f"Error in calculate_monthly_payroll: {e}")
        print(get_text("restaurant.payroll.error_occurred", error=str(e)))

def calculate_individual_payroll():
    """Calculate payroll for individual staff member"""
    try:
        staff_id = input(get_text("restaurant.payroll.individual.enter_staff_id") + " ")
        start_date = input(get_text("restaurant.payroll.individual.enter_start_date") + " ")
        end_date = input(get_text("restaurant.payroll.individual.enter_end_date") + " ")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get staff info
        cursor.execute('SELECT name, role, hourly_rate FROM restaurant_staff WHERE staff_id = ?', (staff_id,))
        staff_info = cursor.fetchone()

        if not staff_info:
            print(get_text("restaurant.payroll.individual.staff_not_found"))
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
            print(get_text("restaurant.payroll.individual.no_schedule_data"))
            conn.close()
            return

        print("\n" + "="*100)
        print(get_text("restaurant.payroll.individual.title", name=staff_info[0], role=staff_info[1]))
        print(get_text("restaurant.payroll.individual.period", start=start_date, end=end_date))
        print("="*100)
        print(f"{get_text('restaurant.payroll.individual.header_date'):<12} {get_text('restaurant.payroll.individual.header_scheduled'):<18} {get_text('restaurant.payroll.individual.header_actual'):<18} {get_text('restaurant.payroll.weekly.header_hours'):<8} {get_text('restaurant.payroll.individual.header_pay'):<10}")
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
            actual_str = f"{schedule[3] or 'N/A'}-{schedule[4] or 'N/A'}" if schedule[3] else get_text("restaurant.payroll.individual.as_scheduled")

            print(f"{schedule[0]:<12} {scheduled_str:<18} {actual_str:<18} {net_hours:<8.1f} £{shift_pay:<9.2f}")

        print("-"*100)
        print(f"{get_text('restaurant.payroll.weekly.totals'):<48} {total_hours:<8.1f} £{total_pay:<9.2f}")
        print(get_text("restaurant.payroll.individual.hourly_rate", rate=f"{staff_info[2]:.2f}"))
        print("="*100)

        conn.close()

    except Exception as e:
        logging.error(f"Error in calculate_individual_payroll: {e}")
        print(get_text("restaurant.payroll.error_occurred", error=str(e)))
