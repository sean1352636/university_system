"""Cinema CLI membership program functions."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

from education_system.systems.university.interfaces.cli.shell.services.cinema_cli.constants import (
    MEMBERSHIP_PRICE, POINTS_PER_POUND, MEMBER_DISCOUNT,
    ACTIVITY_LOGGING,
)
from education_system.systems.university.interfaces.cli.shell.services.cinema_cli.utils import print_header, print_subheader, get_current_user

logger = logging.getLogger(__name__)


def get_user_membership(user_id: str) -> Optional[Dict]:
    """Get user's membership details"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT membership_id, membership_type, points_balance, total_points_earned,
                       total_spent, join_date, renewal_date, status
                FROM cinema_memberships
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))
            row = cursor.fetchone()

            if row:
                return {
                    'membership_id': row[0],
                    'membership_type': row[1],
                    'points_balance': row[2],
                    'total_points_earned': row[3],
                    'total_spent': row[4],
                    'join_date': row[5],
                    'renewal_date': row[6],
                    'status': row[7]
                }
    except Exception as e:
        logger.error(f"Error fetching membership: {e}")
    return None


def calculate_points_earned(amount: float) -> int:
    """Calculate points earned from purchase amount"""
    return int(amount * POINTS_PER_POUND)


def award_points(user_id: str, points: int, booking_ref: str, description: str):
    """Award points to user's membership"""
    try:
        with transaction() as conn:
            # Update points balance
            conn.execute('''
                UPDATE cinema_memberships
                SET points_balance = points_balance + ?,
                    total_points_earned = total_points_earned + ?,
                    last_activity = ?
                WHERE user_id = ?
            ''', (points, points, datetime.now().isoformat(), user_id))

            # Record transaction
            conn.execute('''
                INSERT INTO cinema_points_transactions
                (user_id, booking_ref, transaction_type, points, description)
                VALUES (?, ?, 'earned', ?, ?)
            ''', (user_id, booking_ref, points, description))

        logger.info(f"Awarded {points} points to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error awarding points: {e}")
        return False


def redeem_points(user_id: str, points: int, description: str) -> bool:
    """Redeem points from user's membership"""
    try:
        membership = get_user_membership(user_id)
        if not membership or membership['points_balance'] < points:
            return False

        with transaction() as conn:
            # Deduct points
            conn.execute('''
                UPDATE cinema_memberships
                SET points_balance = points_balance - ?,
                    last_activity = ?
                WHERE user_id = ?
            ''', (points, datetime.now().isoformat(), user_id))

            # Record transaction
            conn.execute('''
                INSERT INTO cinema_points_transactions
                (user_id, transaction_type, points, description)
                VALUES (?, 'redeemed', ?, ?)
            ''', (user_id, -points, description))

        logger.info(f"Redeemed {points} points for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error redeeming points: {e}")
        return False


def membership_menu():
    """Membership program menu"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access membership features")
        input("\n📌 Press Enter to continue...")
        return

    while True:
        try:
            print_header("CINEMA MEMBERSHIP PROGRAM")

            membership = get_user_membership(user.get('username'))

            if membership:
                print(f"\n💳 MEMBERSHIP STATUS: {membership['status'].upper()}")
                print(f"Member Since: {membership['join_date']}")
                print(f"Renewal Date: {membership['renewal_date']}")
                print(f"\n⭐ Points Balance: {membership['points_balance']}")
                print(f"   Total Points Earned: {membership['total_points_earned']}")
                print(f"   Total Spent: £{membership['total_spent']:.2f}")

                print("\n🎁 MEMBER BENEFITS:")
                print(f"   • {int(MEMBER_DISCOUNT * 100)}% discount on all tickets")
                print(f"   • Earn {POINTS_PER_POUND} point per £1 spent")
                print("   • Redeem points for free tickets and snacks")
                print("   • Access to member-exclusive screenings")
                print("   • Priority booking")
            else:
                print("\n📋 NOT A MEMBER YET")
                print(f"\nJoin for only £{MEMBERSHIP_PRICE:.2f}/month!")
                print("\n🎁 MEMBERSHIP BENEFITS:")
                print(f"   • {int(MEMBER_DISCOUNT * 100)}% discount on all tickets")
                print(f"   • Earn {POINTS_PER_POUND} point per £1 spent")
                print("   • Redeem points for free tickets and snacks")
                print("   • Access to member-exclusive screenings")
                print("   • Priority booking")

            print("\n" + "="*70)

            if membership:
                print("\n1. View Points History")
                print("2. Redeem Points")
                print("3. View Exclusive Screenings")
                print("4. Membership Details")
                print("5. Cancel Membership")
            else:
                print("\n1. Join Membership")

            print("\n0. Back to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if membership:
                if choice == "1":
                    view_points_history()
                elif choice == "2":
                    redeem_points_menu()
                elif choice == "3":
                    view_exclusive_screenings()
                elif choice == "4":
                    view_membership_details()
                elif choice == "5":
                    cancel_membership()
                elif choice == "0":
                    break
                else:
                    print("❌ Invalid choice")
                    input("\n📌 Press Enter to continue...")
            else:
                if choice == "1":
                    join_membership()
                elif choice == "0":
                    break
                else:
                    print("❌ Invalid choice")
                    input("\n📌 Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in membership menu: {e}", exc_info=True)
            print(f"❌ An error occurred: {e}")
            input("\n📌 Press Enter to continue...")


def join_membership():
    """Join cinema membership"""
    user = get_current_user()
    if not user:
        return

    try:
        # Check if already a member
        if get_user_membership(user.get('username')):
            print("❌ You are already a member!")
            input("\n📌 Press Enter to continue...")
            return

        print_subheader("JOIN CINEMA MEMBERSHIP")

        print(f"\n💳 Membership Fee: £{MEMBERSHIP_PRICE:.2f}/month")
        print("\n🎁 Benefits:")
        print(f"   • {int(MEMBER_DISCOUNT * 100)}% discount on all tickets")
        print(f"   • Earn {POINTS_PER_POUND} point per £1 spent")
        print("   • Redeem points for rewards")
        print("   • Access to exclusive screenings")

        confirm = input("\n✅ Join now? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("❌ Membership signup cancelled")
            input("\n📌 Press Enter to continue...")
            return

        # Process membership
        with transaction() as conn:
            join_date = datetime.now()
            renewal_date = join_date + timedelta(days=30)

            conn.execute('''
                INSERT INTO cinema_memberships
                (user_id, user_name, user_email, membership_type, points_balance,
                 join_date, renewal_date, status)
                VALUES (?, ?, ?, 'standard', 0, ?, ?, 'active')
            ''', (user.get('username'), user.get('full_name', user.get('username')),
                  user.get('email', ''), join_date.isoformat(),
                  renewal_date.date().isoformat()))

            # Award welcome bonus points
            conn.execute('''
                INSERT INTO cinema_points_transactions
                (user_id, transaction_type, points, description)
                VALUES (?, 'bonus', 100, 'Welcome bonus')
            ''', (user.get('username'),))

            conn.execute('''
                UPDATE cinema_memberships
                SET points_balance = 100
                WHERE user_id = ?
            ''', (user.get('username'),))

        print("\n✅ MEMBERSHIP ACTIVATED!")
        print(f"   Join Date: {join_date.date()}")
        print(f"   Renewal Date: {renewal_date.date()}")
        print("   🎁 Welcome Bonus: 100 points")
        print("\n   Start enjoying your benefits today!")

        if ACTIVITY_LOGGING:
            from education_system.systems.university.interfaces.cli.shell.services.cinema_cli.constants import log_activity
            log_activity('create', 'cinema_membership',
                       user_id=user.get('username'),
                       details={'membership_type': 'standard'})

        logger.info(f"User {user.get('username')} joined cinema membership")

    except Exception as e:
        logger.error(f"Error joining membership: {e}", exc_info=True)
        print(f"❌ Error joining membership: {e}")

    input("\n📌 Press Enter to continue...")


def view_points_history():
    """View points transaction history"""
    user = get_current_user()
    if not user:
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT transaction_type, points, description, transaction_date
                FROM cinema_points_transactions
                WHERE user_id = ?
                ORDER BY transaction_date DESC
                LIMIT 50
            ''', (user.get('username'),))
            transactions = cursor.fetchall()

            if not transactions:
                print("\n❌ No points history found")
            else:
                print_subheader("POINTS HISTORY")

                for trans in transactions:
                    trans_type, points, desc, date = trans

                    sign = "+" if points > 0 else ""
                    icon = "⭐" if points > 0 else "🎁"

                    print(f"\n{icon} {sign}{points} points - {trans_type.upper()}")
                    print(f"   {desc}")
                    print(f"   Date: {date}")

    except Exception as e:
        logger.error(f"Error viewing points history: {e}", exc_info=True)
        print(f"❌ Error viewing points history: {e}")

    input("\n📌 Press Enter to continue...")


def redeem_points_menu():
    """Points redemption menu"""
    user = get_current_user()
    if not user:
        return

    try:
        membership = get_user_membership(user.get('username'))
        if not membership:
            print("❌ Membership not found")
            input("\n📌 Press Enter to continue...")
            return

        print_subheader("REDEEM POINTS")
        print(f"\n⭐ Your Points Balance: {membership['points_balance']}")

        print("\n🎁 REDEMPTION OPTIONS:")
        print("1. £5 Discount - 100 points")
        print("2. £10 Discount - 200 points")
        print("3. £25 Discount - 500 points")
        print("4. Free Small Popcorn - 50 points")
        print("5. Free Medium Drink - 30 points")
        print("\n0. Cancel")

        choice = input("\nEnter choice: ").strip()

        redemptions = {
            '1': (100, '£5 discount voucher'),
            '2': (200, '£10 discount voucher'),
            '3': (500, '£25 discount voucher'),
            '4': (50, 'Free Small Popcorn'),
            '5': (30, 'Free Medium Drink'),
        }

        if choice == '0':
            return

        if choice not in redemptions:
            print("❌ Invalid choice")
            input("\n📌 Press Enter to continue...")
            return

        points_needed, reward = redemptions[choice]

        if membership['points_balance'] < points_needed:
            print(f"❌ Insufficient points. You need {points_needed} points but have {membership['points_balance']}")
            input("\n📌 Press Enter to continue...")
            return

        confirm = input(f"\nRedeem {points_needed} points for {reward}? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("❌ Redemption cancelled")
            input("\n📌 Press Enter to continue...")
            return

        # Redeem points
        if redeem_points(user.get('username'), points_needed, f"Redeemed for {reward}"):
            new_balance = membership['points_balance'] - points_needed
            print(f"\n✅ Successfully redeemed {points_needed} points for {reward}")
            print(f"   New Balance: {new_balance} points")
            print("\n   Your reward will be available on your next booking")
        else:
            print("❌ Redemption failed")

    except Exception as e:
        logger.error(f"Error redeeming points: {e}", exc_info=True)
        print(f"❌ Error redeeming points: {e}")

    input("\n📌 Press Enter to continue...")


def view_exclusive_screenings():
    """View member-exclusive screenings"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT e.screening_id, e.movie_title, e.screening_date,
                       e.screening_time, e.description, s.available_seats
                FROM cinema_exclusive_screenings e
                JOIN cinema_screenings s ON e.screening_id = s.screening_id
                WHERE s.screening_date >= date('now') AND s.status = 'available'
                ORDER BY s.screening_date, s.screening_time
            ''')
            exclusives = cursor.fetchall()

            if not exclusives:
                print("\n❌ No exclusive screenings available at this time")
            else:
                print_subheader("MEMBER-EXCLUSIVE SCREENINGS")
                print(f"\n👑 {len(exclusives)} exclusive screening(s) available:")

                for exc in exclusives:
                    scr_id, movie, date, time, desc, seats = exc
                    print(f"\n🎬 {movie}")
                    print(f"   📅 {date} at {time}")
                    print(f"   💺 {seats} seats available")
                    print(f"   Screening ID: {scr_id}")
                    if desc:
                        print(f"   ℹ️  {desc}")

    except Exception as e:
        logger.error(f"Error viewing exclusive screenings: {e}", exc_info=True)
        print(f"❌ Error viewing exclusive screenings: {e}")

    input("\n📌 Press Enter to continue...")


def view_membership_details():
    """View detailed membership information"""
    user = get_current_user()
    if not user:
        return

    try:
        membership = get_user_membership(user.get('username'))
        if not membership:
            print("❌ Membership not found")
            input("\n📌 Press Enter to continue...")
            return

        print_subheader("MEMBERSHIP DETAILS")

        print(f"\n💳 Member ID: {membership['membership_id']}")
        print(f"👤 Name: {user.get('full_name', user.get('username'))}")
        print(f"📧 Email: {user.get('email', 'N/A')}")
        print(f"🎫 Membership Type: {membership['membership_type'].title()}")
        print(f"📊 Status: {membership['status'].upper()}")

        print("\n📅 Membership Dates:")
        print(f"   Join Date: {membership['join_date']}")
        print(f"   Renewal Date: {membership['renewal_date']}")
        print(f"   Last Activity: {membership.get('last_activity', 'N/A')}")

        print("\n⭐ Points Summary:")
        print(f"   Current Balance: {membership['points_balance']}")
        print(f"   Total Earned: {membership['total_points_earned']}")
        print(f"   Total Spent: £{membership['total_spent']:.2f}")

        # Calculate savings
        savings = membership['total_spent'] * MEMBER_DISCOUNT
        print(f"\n💰 Total Savings: £{savings:.2f}")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) FROM cinema_bookings
                WHERE user_id = ? AND member_discount > 0
            ''', (user.get('username'),))
            booking_count = cursor.fetchone()[0]
            print(f"   Bookings with Discount: {booking_count}")

    except Exception as e:
        logger.error(f"Error viewing membership details: {e}", exc_info=True)
        print(f"❌ Error viewing membership details: {e}")

    input("\n📌 Press Enter to continue...")


def cancel_membership():
    """Cancel cinema membership"""
    user = get_current_user()
    if not user:
        return

    try:
        membership = get_user_membership(user.get('username'))
        if not membership:
            print("❌ Membership not found")
            input("\n📌 Press Enter to continue...")
            return

        print_subheader("CANCEL MEMBERSHIP")

        print("\n⚠️  WARNING: You are about to cancel your membership")
        print(f"\n   Current Points Balance: {membership['points_balance']}")
        print("   These points will be forfeited upon cancellation")
        print("\n   You will lose access to:")
        print(f"   • {int(MEMBER_DISCOUNT * 100)}% ticket discount")
        print("   • Points earning and redemption")
        print("   • Exclusive screenings")

        confirm = input("\n❌ Are you sure you want to cancel? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("✅ Cancellation aborted")
            input("\n📌 Press Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE cinema_memberships
                SET status = 'cancelled'
                WHERE user_id = ?
            ''', (user.get('username'),))

        print("\n✅ Membership cancelled successfully")
        print("   We're sorry to see you go!")
        print("   You can rejoin anytime.")

        if ACTIVITY_LOGGING:
            from education_system.systems.university.interfaces.cli.shell.services.cinema_cli.constants import log_activity
            log_activity('delete', 'cinema_membership',
                       user_id=user.get('username'),
                       details={'reason': 'user_requested'})

        logger.info(f"User {user.get('username')} cancelled cinema membership")

    except Exception as e:
        logger.error(f"Error cancelling membership: {e}", exc_info=True)
        print(f"❌ Error cancelling membership: {e}")

    input("\n📌 Press Enter to continue...")
