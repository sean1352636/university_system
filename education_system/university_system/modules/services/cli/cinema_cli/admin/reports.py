"""Cinema CLI admin reports and analytics functions."""

import logging

from education_system.university_system.infrastructure.database.db import get_connection

from ..utils import print_subheader

logger = logging.getLogger(__name__)


def admin_booking_reports():
    """View booking reports"""
    try:
        print_subheader("BOOKING REPORTS")

        print("\n1. Today's Bookings")
        print("2. This Week's Bookings")
        print("3. This Month's Bookings")
        print("4. All Bookings")

        choice = input("\nEnter choice: ").strip()

        _DATE_FILTERS = {
            "1": "AND DATE(booking_date) = DATE('now')",
            "2": "AND DATE(booking_date) >= DATE('now', '-7 days')",
            "3": "AND DATE(booking_date) >= DATE('now', 'start of month')",
        }
        date_filter = _DATE_FILTERS.get(choice, "")

        with get_connection() as conn:
            cursor = conn.execute(f'''
                SELECT booking_ref, user_name, movie_title, screening_date,
                       num_tickets, total_amount, status, booking_date
                FROM cinema_bookings
                WHERE 1=1 {date_filter}
                ORDER BY booking_date DESC
                LIMIT 100
            ''')
            bookings = cursor.fetchall()

            if not bookings:
                print("\n❌ No bookings found")
            else:
                total_revenue = sum(float(b[5]) for b in bookings)
                total_tickets = sum(int(b[4]) for b in bookings)

                print(f"\n📊 BOOKING SUMMARY:")
                print(f"   Total Bookings: {len(bookings)}")
                print(f"   Total Tickets: {total_tickets}")
                print(f"   Total Revenue: £{total_revenue:.2f}")
                print(f"   Average Order: £{total_revenue/len(bookings):.2f}")

                print(f"\n📋 BOOKINGS:")
                print("="*70)

                for booking in bookings[:20]:  # Show first 20
                    ref, user, movie, date, tickets, amount, status, booked = booking
                    print(f"\n{ref} | {user}")
                    print(f"   {movie} on {date}")
                    print(f"   {tickets} tickets | £{float(amount):.2f} | {status}")
                    print(f"   Booked: {booked}")

    except Exception as e:
        logger.error(f"Error viewing booking reports: {e}", exc_info=True)
        print(f"❌ Error viewing booking reports: {e}")

    input("\n📌 Press Enter to continue...")


def admin_revenue_analytics():
    """View revenue analytics"""
    try:
        print_subheader("REVENUE ANALYTICS")

        with get_connection() as conn:
            # Total revenue
            cursor = conn.execute('''
                SELECT
                    SUM(total_amount) as total_revenue,
                    SUM(ticket_total) as ticket_revenue,
                    SUM(snacks_total) as snacks_revenue,
                    COUNT(*) as total_bookings
                FROM cinema_bookings
                WHERE status = 'confirmed'
            ''')
            totals = cursor.fetchone()

            total_rev, ticket_rev, snacks_rev, bookings = totals

            print(f"\n💰 OVERALL REVENUE:")
            print(f"   Total Revenue: £{float(total_rev or 0):.2f}")
            print(f"   Ticket Sales: £{float(ticket_rev or 0):.2f} ({float(ticket_rev or 0)/float(total_rev or 1)*100:.1f}%)")
            print(f"   Snacks Sales: £{float(snacks_rev or 0):.2f} ({float(snacks_rev or 0)/float(total_rev or 1)*100:.1f}%)")
            print(f"   Total Bookings: {bookings}")

            # Revenue by movie
            cursor = conn.execute('''
                SELECT movie_title, SUM(total_amount) as revenue, COUNT(*) as bookings
                FROM cinema_bookings
                WHERE status = 'confirmed'
                GROUP BY movie_title
                ORDER BY revenue DESC
                LIMIT 10
            ''')
            by_movie = cursor.fetchall()

            if by_movie:
                print(f"\n🎬 TOP MOVIES BY REVENUE:")
                for movie, rev, book_count in by_movie:
                    print(f"   {movie}: £{float(rev):.2f} ({book_count} bookings)")

            # Revenue by date
            cursor = conn.execute('''
                SELECT DATE(booking_date) as date, SUM(total_amount) as revenue
                FROM cinema_bookings
                WHERE status = 'confirmed' AND DATE(booking_date) >= DATE('now', '-7 days')
                GROUP BY DATE(booking_date)
                ORDER BY date DESC
            ''')
            by_date = cursor.fetchall()

            if by_date:
                print(f"\n📅 REVENUE BY DATE (Last 7 Days):")
                for date, rev in by_date:
                    print(f"   {date}: £{float(rev):.2f}")

            # Membership stats
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as member_bookings,
                    SUM(total_amount) as member_revenue,
                    SUM(member_discount) as total_discounts
                FROM cinema_bookings
                WHERE status = 'confirmed' AND member_discount > 0
            ''')
            member_stats = cursor.fetchone()

            if member_stats and member_stats[0] > 0:
                mem_bookings, mem_rev, discounts = member_stats
                print(f"\n💳 MEMBERSHIP IMPACT:")
                print(f"   Member Bookings: {mem_bookings}")
                print(f"   Member Revenue: £{float(mem_rev or 0):.2f}")
                print(f"   Total Discounts: £{float(discounts or 0):.2f}")

    except Exception as e:
        logger.error(f"Error viewing revenue analytics: {e}", exc_info=True)
        print(f"❌ Error viewing revenue analytics: {e}")

    input("\n📌 Press Enter to continue...")


def admin_occupancy_report():
    """View screening occupancy rates"""
    try:
        print_subheader("OCCUPANCY REPORT")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT
                    movie_title,
                    screening_date,
                    screening_time,
                    total_seats,
                    available_seats,
                    screen_number,
                    status
                FROM cinema_screenings
                WHERE screening_date >= DATE('now', '-7 days')
                ORDER BY screening_date DESC, screening_time DESC
                LIMIT 50
            ''')
            screenings = cursor.fetchall()

            if not screenings:
                print("\n❌ No screenings found")
            else:
                print(f"\n📊 SHOWING {len(screenings)} SCREENING(S):")
                print("="*70)

                total_capacity = 0
                total_sold = 0

                current_date = None
                for screening in screenings:
                    movie, date, time, total, avail, screen, status = screening

                    if date != current_date:
                        print(f"\n📅 {date}:")
                        current_date = date

                    sold = total - avail
                    occupancy = (sold / total * 100) if total > 0 else 0

                    total_capacity += total
                    total_sold += sold

                    # Color code occupancy
                    if occupancy >= 90:
                        icon = "🔴"
                    elif occupancy >= 70:
                        icon = "🟡"
                    elif occupancy >= 50:
                        icon = "🟢"
                    else:
                        icon = "⚪"

                    print(f"  {icon} {time} - {movie}")
                    print(f"      Screen {screen} | {sold}/{total} seats ({occupancy:.0f}% full) | {status}")

                overall_occupancy = (total_sold / total_capacity * 100) if total_capacity > 0 else 0
                print(f"\n📊 OVERALL OCCUPANCY: {overall_occupancy:.1f}%")
                print(f"   Total Capacity: {total_capacity} seats")
                print(f"   Total Sold: {total_sold} seats")
                print(f"   Available: {total_capacity - total_sold} seats")

    except Exception as e:
        logger.error(f"Error viewing occupancy report: {e}", exc_info=True)
        print(f"❌ Error viewing occupancy report: {e}")

    input("\n📌 Press Enter to continue...")


def admin_member_statistics():
    """View membership statistics"""
    try:
        print_subheader("MEMBERSHIP STATISTICS")

        with get_connection() as conn:
            # Total members
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(points_balance), SUM(total_spent)
                FROM cinema_memberships
                WHERE status = 'active'
            ''')
            stats = cursor.fetchone()

            if stats:
                total_members, total_points, total_spent = stats

                print(f"\n💳 MEMBERSHIP OVERVIEW:")
                print(f"   Active Members: {total_members or 0}")
                print(f"   Total Points in Circulation: {total_points or 0}")
                print(f"   Total Member Spending: £{float(total_spent or 0):.2f}")

                if total_members and total_members > 0:
                    avg_points = (total_points or 0) / total_members
                    avg_spent = (total_spent or 0) / total_members
                    print(f"   Avg Points per Member: {avg_points:.0f}")
                    print(f"   Avg Spending per Member: £{avg_spent:.2f}")

            # Top members
            cursor = conn.execute('''
                SELECT user_name, total_points_earned, total_spent, points_balance
                FROM cinema_memberships
                WHERE status = 'active'
                ORDER BY total_spent DESC
                LIMIT 10
            ''')
            top_members = cursor.fetchall()

            if top_members:
                print(f"\n🏆 TOP MEMBERS BY SPENDING:")
                for name, points_earned, spent, balance in top_members:
                    print(f"   {name}: £{float(spent):.2f} spent | {points_earned} points earned | {balance} balance")

            # Recent joins
            cursor = conn.execute('''
                SELECT user_name, join_date, points_balance
                FROM cinema_memberships
                WHERE status = 'active'
                ORDER BY join_date DESC
                LIMIT 5
            ''')
            recent = cursor.fetchall()

            if recent:
                print(f"\n🆕 RECENT MEMBERS:")
                for name, join_date, balance in recent:
                    print(f"   {name} joined {join_date} | {balance} points")

    except Exception as e:
        logger.error(f"Error viewing member statistics: {e}", exc_info=True)
        print(f"❌ Error viewing member statistics: {e}")

    input("\n📌 Press Enter to continue...")
