from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from . import config


def get_customer_analytics():
    """Get customer purchase analytics"""

    if not config.auth or not config.auth.current_user:
        return None

    if not config.auth.check_permission('generate_sales_reports'):
        return None

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get customer stats
        cursor.execute(
            '''
            SELECT
                COUNT(DISTINCT user_id) as total_customers,
                AVG(total_amount) as avg_order_value,
                COUNT(*) as total_orders,
                SUM(total_amount) as total_revenue
            FROM shop_transactions
            WHERE transaction_date >= date('now', '-30 days')
            '''
        )

        overview = cursor.fetchone()

        # Get top customers
        cursor.execute(
            '''
            SELECT u.username, u.student_id,
                   COUNT(t.transaction_id) as order_count,
                   SUM(t.total_amount) as total_spent,
                   AVG(t.total_amount) as avg_order
            FROM shop_transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.transaction_date >= date('now', '-30 days')
            GROUP BY u.id
            ORDER BY total_spent DESC
            LIMIT 10
            '''
        )

        top_customers = cursor.fetchall()

        # Get payment method preferences
        cursor.execute(
            '''
            SELECT payment_method,
                   COUNT(*) as usage_count,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM shop_transactions WHERE transaction_date >= date('now', '-30 days')), 1) as percentage
            FROM shop_transactions
            WHERE transaction_date >= date('now', '-30 days')
            GROUP BY payment_method
            ORDER BY usage_count DESC
            '''
        )

        payment_methods = cursor.fetchall()

        conn.close()

        return {
            'overview': dict(overview) if overview else {},
            'top_customers': [dict(customer) for customer in top_customers],
            'payment_methods': [dict(method) for method in payment_methods]
        }

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return None


def display_customer_analytics():
    """Display customer analytics dashboard"""

    if not config.auth or not config.auth.current_user:
        print("You must be logged in to view analytics.")
        return

    if not config.auth.check_permission('generate_sales_reports'):
        print("You don't have permission to view analytics.")
        return

    analytics = get_customer_analytics()

    if not analytics:
        print("Could not retrieve customer analytics.")
        return

    print("\n" + "="*60)
    print("CUSTOMER ANALYTICS (Last 30 Days)")
    print("="*60)

    overview = analytics['overview']
    if overview:
        print(f"\nOVERVIEW")
        print("-" * 20)
        print(f"Total Customers: {overview.get('total_customers', 0)}")
        print(f"Total Orders: {overview.get('total_orders', 0)}")
        print(f"Total Revenue: \u00a3{overview.get('total_revenue', 0):.2f}")
        print(f"Average Order Value: \u00a3{overview.get('avg_order_value', 0):.2f}")

    if analytics['top_customers']:
        print(f"\nTOP CUSTOMERS")
        print("-" * 50)
        print(f"{'Rank':<5} {'Username':<15} {'Student ID':<12} {'Orders':<8} {'Total Spent':<15} {'Avg Order'}")
        print("-" * 70)

        for i, customer in enumerate(analytics['top_customers'], 1):
            student_id = customer['student_id'] or 'N/A'
            print(f"{i:<5} {customer['username']:<15} {student_id:<12} {customer['order_count']:<8} \u00a3{customer['total_spent']:<14.2f} \u00a3{customer['avg_order']:.2f}")

    if analytics['payment_methods']:
        print(f"\nPAYMENT METHOD PREFERENCES")
        print("-" * 35)
        print(f"{'Method':<20} {'Usage':<8} {'Percentage'}")
        print("-" * 35)

        for method in analytics['payment_methods']:
            print(f"{method['payment_method']:<20} {method['usage_count']:<8} {method['percentage']}%")

    input("\nPress Enter to continue...")
