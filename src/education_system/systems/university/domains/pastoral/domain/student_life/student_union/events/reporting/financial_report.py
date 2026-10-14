"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.context import auth

def generate_event_financial_report(event_id, event_name, cursor):
    """Generate detailed financial report for an event"""
    try:
        print(f"\n{'='*60}")
        print(f"FINANCIAL REPORT - {event_name}")
        print(f"{'='*60}")

        # Revenue breakdown
        cursor.execute('''
        SELECT revenue_type, SUM(amount) as total_amount
        FROM event_finances
        WHERE event_id = ? AND amount > 0
        GROUP BY revenue_type
        ORDER BY total_amount DESC
        ''', (event_id,))

        revenues = cursor.fetchall()
        total_revenue = sum(rev[1] for rev in revenues)

        print("\nREVENUE BREAKDOWN:")
        print("-" * 30)
        for revenue in revenues:
            print(f"{revenue[0]:<20} £{revenue[1]:.2f}")
        print("-" * 30)
        print(f"{'TOTAL REVENUE:':<20} £{total_revenue:.2f}")

        # Expense breakdown
        cursor.execute('''
        SELECT expense_type, SUM(ABS(amount)) as total_amount
        FROM event_finances
        WHERE event_id = ? AND amount < 0
        GROUP BY expense_type
        ORDER BY total_amount DESC
        ''', (event_id,))

        expenses = cursor.fetchall()
        total_expenses = sum(exp[1] for exp in expenses)

        print("\nEXPENSE BREAKDOWN:")
        print("-" * 30)
        for expense in expenses:
            print(f"{expense[0]:<20} £{expense[1]:.2f}")
        print("-" * 30)
        print(f"{'TOTAL EXPENSES:':<20} £{total_expenses:.2f}")

        # Profit/Loss calculation
        profit_loss = total_revenue - total_expenses

        print("\nPROFIT/LOSS ANALYSIS:")
        print("-" * 30)
        print(f"{'Total Revenue:':<20} £{total_revenue:.2f}")
        print(f"{'Total Expenses:':<20} £{total_expenses:.2f}")
        print(f"{'Net Profit/Loss:':<20} £{profit_loss:.2f}")

        if total_revenue > 0:
            profit_margin = (profit_loss / total_revenue) * 100
            print(f"{'Profit Margin:':<20} {profit_margin:.1f}%")

        # Budget vs Actual (if budget was set)
        cursor.execute('''
        SELECT description FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') WHERE event_id = ?
        ''', (event_id,))

        event_details = cursor.fetchone()

        print("\nEVENT PERFORMANCE:")
        print("-" * 30)

        if profit_loss > 0:
            print("✓ Event was profitable")
        elif profit_loss == 0:
            print("= Event broke even")
        else:
            print("✗ Event had a loss")

        # Recommendations
        print("\nRECOMMENDations:")
        print("-" * 30)

        if total_expenses > total_revenue * 0.8:
            print("• Consider reducing expenses for future events")

        if revenues:
            top_revenue_source = max(revenues, key=lambda x: x[1])
            print(f"• Top revenue source: {top_revenue_source[0]} (£{top_revenue_source[1]:.2f})")

        if expenses:
            top_expense = max(expenses, key=lambda x: x[1])
            print(f"• Largest expense: {top_expense[0]} (£{top_expense[1]:.2f})")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
