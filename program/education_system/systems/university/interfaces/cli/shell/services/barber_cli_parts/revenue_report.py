"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def revenue_report():
    """View revenue reports (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("REVENUE REPORT")

        print("\nSelect period:")
        print("  1. Today")
        print("  2. This Week")
        print("  3. This Month")
        print("  4. Custom Range")

        choice = input("\nEnter choice (1-4): ").strip()

        if choice == "1":
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = start_date
            period_name = "Today"
        elif choice == "2":
            today = datetime.now()
            start_date = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            period_name = "This Week"
        elif choice == "3":
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            period_name = "This Month"
        elif choice == "4":
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')
                period_name = f"{start_date} to {end_date}"
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid choice")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            # Overall revenue
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as transactions,
                    SUM(amount) as revenue,
                    SUM(tip_amount) as tips,
                    SUM(amount + tip_amount) as total,
                    AVG(amount) as avg_transaction
                FROM transactions
                WHERE source_type = 'barber' AND DATE(created_at) BETWEEN ? AND ?
                AND status = 'completed'
            ''', (start_date, end_date))
            summary = cursor.fetchone()

            print(f"\n{'='*60}")
            print(f"REVENUE REPORT - {period_name}")
            print(f"{'='*60}")

            if summary and summary[0] > 0:
                trans_count, revenue, tips, total, avg_trans = summary
                print(f"\nTransactions:     {trans_count}")
                print(f"Service Revenue:  GBP {float(revenue or 0):.2f}")
                print(f"Tips:             GBP {float(tips or 0):.2f}")
                print(f"Total Revenue:    GBP {float(total or 0):.2f}")
                print(f"Avg Transaction:  GBP {float(avg_trans or 0):.2f}")

                # By payment method
                cursor = conn.execute('''
                    SELECT payment_method, COUNT(*), SUM(amount + tip_amount)
                    FROM transactions
                    WHERE source_type = 'barber' AND DATE(created_at) BETWEEN ? AND ?
                    AND status = 'completed'
                    GROUP BY payment_method
                ''', (start_date, end_date))
                by_method = cursor.fetchall()

                if by_method:
                    print("\nBy Payment Method:")
                    for method, count, amount in by_method:
                        print(f"  {method.replace('_', ' ').title():<20} {count:>3} transactions  GBP {float(amount):.2f}")

                # By service
                cursor = conn.execute('''
                    SELECT a.service_name, COUNT(*), SUM(t.amount)
                    FROM transactions t
                    JOIN barber_appointments a ON t.reference_id = a.appointment_id AND t.reference_type = 'appointment'
                    WHERE t.source_type = 'barber' AND DATE(t.created_at) BETWEEN ? AND ?
                    AND t.status = 'completed'
                    GROUP BY a.service_name
                    ORDER BY SUM(t.amount) DESC
                ''', (start_date, end_date))
                by_service = cursor.fetchall()

                if by_service:
                    print("\nTop Services:")
                    for i, (service, count, amount) in enumerate(by_service[:5], 1):
                        print(f"  {i}. {service:<25} {count:>3} bookings  GBP {float(amount):.2f}")

            else:
                print("\nNo transactions in this period")

    except Exception as e:
        logger.error(f"Error generating revenue report: {e}")
        print(f"❌ Error generating revenue report: {e}")

    input("\nPress Enter to continue...")
