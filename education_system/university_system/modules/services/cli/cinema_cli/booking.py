"""Cinema CLI ticket booking functions."""

import logging
import random
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection, transaction

from education_system.university_system.modules.services.cli.cinema_cli.constants import (
    TICKET_TYPES, MEMBER_DISCOUNT, ACTIVITY_LOGGING, EMAIL_AVAILABLE,
)
from education_system.university_system.modules.services.cli.cinema_cli.utils import print_subheader, get_current_user
from education_system.university_system.modules.services.cli.cinema_cli.screenings import view_screenings
from education_system.university_system.modules.services.cli.cinema_cli.seats import select_seats, auto_select_seats, mark_seats_as_booked
from education_system.university_system.modules.services.cli.cinema_cli.snacks import suggest_combo_for_party, add_snacks_to_order
from education_system.university_system.modules.services.cli.cinema_cli.membership import get_user_membership, calculate_points_earned, award_points, redeem_points

logger = logging.getLogger(__name__)


def send_booking_confirmation_email(user_email: str, booking_details: dict):
    """Send booking confirmation email"""
    if not EMAIL_AVAILABLE or not user_email:
        return False

    try:
        from education_system.university_system.modules.services.cli.cinema_cli.constants import send_email

        subject = f"Cinema Booking Confirmation - {booking_details['booking_ref']}"

        body = f"""
Dear {booking_details['user_name']},

Your cinema booking has been confirmed!

Booking Reference: {booking_details['booking_ref']}
Movie: {booking_details['movie_title']}
Date: {booking_details['screening_date']}
Time: {booking_details['screening_time']}
Tickets: {booking_details['num_tickets']}x {booking_details['ticket_type']}

Total Amount: £{booking_details['total_amount']:.2f}

Please arrive 15 minutes before the screening starts.
Show this confirmation at the entrance.

Enjoy the show!

University Cinema
"""

        send_email(
            to_email=user_email,
            subject=subject,
            body=body,
            template_name='cinema_booking_confirmation'
        )
        return True
    except Exception as e:
        logger.error(f"Error sending confirmation email: {e}")
        return False


def book_tickets():
    """Book movie tickets with full features"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to book tickets")
        input("\n📌 Press Enter to continue...")
        return

    try:
        # Check membership
        membership = get_user_membership(user.get('username'))
        if membership:
            print(f"\n💳 Member Benefits Active!")
            print(f"   Points Balance: {membership['points_balance']}")
            print(f"   Member Discount: {int(MEMBER_DISCOUNT * 100)}% off tickets")

        view_screenings()

        screening_id = input("\n🎟️  Enter screening ID to book (0 to cancel): ").strip()
        if screening_id == "0":
            return

        if not screening_id.isdigit():
            print("❌ Invalid screening ID")
            input("\n📌 Press Enter to continue...")
            return

        # Get screening details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT movie_title, screening_date, screening_time, screen_number,
                       available_seats, ticket_price, screen_type
                FROM cinema_screenings
                WHERE screening_id = ? AND status = 'available'
            ''', (screening_id,))
            screening = cursor.fetchone()

            if not screening:
                print("❌ Screening not found or not available")
                input("\n📌 Press Enter to continue...")
                return

            movie_title, date, time, screen, available, base_price, screen_type = screening

            print_subheader(f"BOOKING: {movie_title}")
            print(f"\n🎬 Movie: {movie_title}")
            print(f"📅 Date: {date}")
            print(f"🕐 Time: {time}")
            print(f"📺 Screen: {screen}" + (" (PREMIUM)" if screen_type == 'premium' else ""))
            print(f"💺 Available Seats: {available}")

            # Get number of tickets
            num_tickets_str = input(f"\nEnter number of tickets (1-{min(available, 10)}): ").strip()

            try:
                num_tickets = int(num_tickets_str)
            except ValueError:
                print("❌ Invalid number of tickets")
                input("\n📌 Press Enter to continue...")
                return

            if num_tickets < 1 or num_tickets > min(available, 10):
                print(f"❌ Number of tickets must be between 1 and {min(available, 10)}")
                input("\n📌 Press Enter to continue...")
                return

            # Select ticket type
            print("\n🎫 TICKET TYPES:")
            for idx, (ttype, tprice) in enumerate(TICKET_TYPES.items(), 1):
                # Apply member discount if applicable
                final_price = tprice * (1 - MEMBER_DISCOUNT) if membership else tprice
                discount_label = f" (Member: £{final_price:.2f})" if membership else ""
                print(f"{idx}. {ttype} - £{tprice:.2f}{discount_label}")

            ticket_choice = input("\nSelect ticket type (1-4): ").strip()
            ticket_types_list = list(TICKET_TYPES.items())

            try:
                ticket_idx = int(ticket_choice) - 1
                if ticket_idx < 0 or ticket_idx >= len(ticket_types_list):
                    raise ValueError
                ticket_type, ticket_price = ticket_types_list[ticket_idx]
            except (ValueError, IndexError):
                print("❌ Invalid ticket type")
                input("\n📌 Press Enter to continue...")
                return

            # Apply member discount
            member_discount_amount = 0.0
            if membership:
                member_discount_amount = ticket_price * num_tickets * MEMBER_DISCOUNT
                ticket_price = ticket_price * (1 - MEMBER_DISCOUNT)

            ticket_total = num_tickets * ticket_price

            # Seat selection
            print("\n💺 SEAT SELECTION")
            use_seat_selection = input("Select specific seats? (yes/no, default: auto): ").strip().lower()

            if use_seat_selection == 'yes':
                selected_seats = select_seats(int(screening_id), num_tickets)
                if not selected_seats:
                    print("❌ Seat selection cancelled")
                    input("\n📌 Press Enter to continue...")
                    return
            else:
                # Auto-assign seats
                selected_seats = auto_select_seats(int(screening_id), num_tickets)
                if selected_seats:
                    print(f"✅ Auto-assigned seats: {', '.join(selected_seats)}")
                else:
                    selected_seats = [f"Auto-{i+1}" for i in range(num_tickets)]

            # Snacks
            snacks_total = 0.0
            snacks_list = []

            suggest_combo_for_party(num_tickets)
            add_snacks = input("\n🍿 Add snacks to your order? (yes/no): ").strip().lower()

            if add_snacks == 'yes':
                snacks_total, snacks_list = add_snacks_to_order()

            # Points redemption
            points_redeemed = 0
            points_discount = 0.0

            if membership and membership['points_balance'] >= 100:
                print(f"\n⭐ You have {membership['points_balance']} points")
                print("   100 points = £5 off | 200 points = £10 off | 500 points = £25 off")

                redeem = input("Redeem points? (yes/no): ").strip().lower()
                if redeem == 'yes':
                    points_to_redeem = input("Enter points to redeem (100/200/500): ").strip()

                    if points_to_redeem in ['100', '200', '500']:
                        points_val = int(points_to_redeem)
                        if membership['points_balance'] >= points_val:
                            points_redeemed = points_val
                            points_discount = points_val / 20  # 100 points = £5
                            print(f"✅ Redeeming {points_redeemed} points for £{points_discount:.2f} off")

            total_amount = ticket_total + snacks_total - member_discount_amount - points_discount

            # Generate booking reference
            booking_ref = f"CINEMA-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"

            # Booking summary
            print_subheader("BOOKING SUMMARY")
            print(f"\n🎬 Movie: {movie_title}")
            print(f"📅 Date/Time: {date} at {time}")
            print(f"💺 Seats: {', '.join(selected_seats)}")
            print(f"🎟️  Tickets: {num_tickets}x {ticket_type} @ £{TICKET_TYPES[ticket_type]:.2f} = £{num_tickets * TICKET_TYPES[ticket_type]:.2f}")

            if member_discount_amount > 0:
                print(f"   💳 Member Discount ({int(MEMBER_DISCOUNT * 100)}%): -£{member_discount_amount:.2f}")
                print(f"   Ticket Total: £{ticket_total:.2f}")

            if snacks_list:
                print("\n🍿 Snacks:")
                for snack in snacks_list:
                    combo_label = " [COMBO]" if snack.get('is_combo') else ""
                    print(f"   {snack['quantity']}x {snack['name']}{combo_label} @ £{snack['price']:.2f} = £{snack['subtotal']:.2f}")
                print(f"   Snacks Total: £{snacks_total:.2f}")

            if points_redeemed > 0:
                print(f"\n⭐ Points Redeemed: {points_redeemed} points (-£{points_discount:.2f})")

            print(f"\n💰 TOTAL AMOUNT: £{total_amount:.2f}")

            # Calculate points to be earned
            points_to_earn = calculate_points_earned(total_amount) if membership else 0
            if points_to_earn > 0:
                print(f"   ⭐ Points to earn: {points_to_earn}")

            confirm = input("\n✅ Confirm booking? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Booking cancelled")
                input("\n📌 Press Enter to continue...")
                return

            # Create booking
            with transaction() as conn_tx:
                conn_tx.execute('''
                    INSERT INTO cinema_bookings
                    (booking_ref, user_id, user_name, user_email, screening_id, movie_title,
                     screening_date, screening_time, num_tickets, ticket_type, seat_numbers,
                     ticket_total, snacks_total, member_discount, total_amount,
                     points_earned, points_redeemed, status, booking_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?)
                ''', (booking_ref, user.get('username'), user.get('full_name', user.get('username')),
                      user.get('email', ''), screening_id, movie_title, date, time,
                      num_tickets, ticket_type, ','.join(selected_seats),
                      ticket_total, snacks_total, member_discount_amount, total_amount,
                      points_to_earn, points_redeemed, datetime.now().isoformat()))

                booking_id = conn_tx.execute('SELECT last_insert_rowid()').fetchone()[0]

                # Add snacks
                for snack in snacks_list:
                    conn_tx.execute('''
                        INSERT INTO cinema_snacks_orders
                        (booking_id, booking_ref, user_id, snack_item, quantity, unit_price, subtotal, is_combo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (booking_id, booking_ref, user.get('username'), snack['name'],
                          snack['quantity'], snack['price'], snack['subtotal'],
                          snack.get('is_combo', False)))

                # Update available seats
                conn_tx.execute('''
                    UPDATE cinema_screenings
                    SET available_seats = available_seats - ?
                    WHERE screening_id = ?
                ''', (num_tickets, screening_id))

                # Mark seats as booked
                mark_seats_as_booked(int(screening_id), selected_seats, booking_ref)

                # Handle membership points
                if membership:
                    if points_redeemed > 0:
                        redeem_points(user.get('username'), points_redeemed,
                                    f"Redeemed for booking {booking_ref}")

                    if points_to_earn > 0:
                        award_points(user.get('username'), points_to_earn, booking_ref,
                                   f"Earned from booking {booking_ref}")

                    # Update total spent
                    conn_tx.execute('''
                        UPDATE cinema_memberships
                        SET total_spent = total_spent + ?
                        WHERE user_id = ?
                    ''', (total_amount, user.get('username')))

            print_subheader("BOOKING CONFIRMED!")
            print(f"\n✅ Booking Reference: {booking_ref}")
            print(f"🎬 Movie: {movie_title}")
            print(f"📅 Date: {date} at {time}")
            print(f"💺 Seats: {', '.join(selected_seats)}")
            print(f"💰 Total Paid: £{total_amount:.2f}")

            if points_to_earn > 0:
                new_balance = membership['points_balance'] - points_redeemed + points_to_earn
                print(f"⭐ New Points Balance: {new_balance}")

            print("\n📧 Confirmation email sent (if email configured)")
            print("\n⚠️  Please arrive 15 minutes before the screening")
            print("    Show this booking reference at the entrance")

            # Send confirmation email
            booking_details = {
                'booking_ref': booking_ref,
                'user_name': user.get('full_name', user.get('username')),
                'movie_title': movie_title,
                'screening_date': date,
                'screening_time': time,
                'num_tickets': num_tickets,
                'ticket_type': ticket_type,
                'total_amount': total_amount
            }
            send_booking_confirmation_email(user.get('email', ''), booking_details)

            # Log activity
            if ACTIVITY_LOGGING:
                from education_system.university_system.modules.services.cli.cinema_cli.constants import log_activity
                log_activity('create', 'cinema_booking',
                           booking_ref=booking_ref,
                           details={'movie': movie_title, 'amount': total_amount})

            logger.info(f"User {user.get('username')} booked cinema tickets {booking_ref} for £{total_amount:.2f}")

    except Exception as e:
        logger.error(f"Error booking tickets: {e}", exc_info=True)
        print(f"❌ Error booking tickets: {e}")

    input("\n📌 Press Enter to continue...")


def view_my_bookings():
    """View user's booking history with detailed information"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view bookings")
        input("\n📌 Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT booking_ref, movie_title, screening_date, screening_time,
                       num_tickets, ticket_type, seat_numbers, total_amount,
                       points_earned, status, booking_date
                FROM cinema_bookings
                WHERE user_id = ?
                ORDER BY booking_date DESC
                LIMIT 50
            ''', (user.get('username'),))
            bookings = cursor.fetchall()

            if not bookings:
                print("\n❌ No bookings found")
            else:
                print_subheader(f"YOUR BOOKINGS ({len(bookings)} found)")

                for booking in bookings:
                    try:
                        (ref, movie, date, time, tickets, ttype, seats,
                         total, points, status, booked) = booking

                        print(f"\n{'='*70}")
                        print(f"🎟️  Booking: {ref}")
                        print(f"🎬 Movie: {movie}")
                        print(f"📅 Date/Time: {date} at {time}")
                        print(f"💺 Seats: {seats}")
                        print(f"🎫 Tickets: {tickets}x {ttype}")
                        print(f"💰 Total: £{float(total):.2f}")
                        if points > 0:
                            print(f"⭐ Points Earned: {points}")
                        print(f"📊 Status: {status.upper()}")
                        print(f"📆 Booked: {booked}")

                        # Show snacks if any
                        snacks_cursor = conn.execute('''
                            SELECT snack_item, quantity, subtotal, is_combo
                            FROM cinema_snacks_orders
                            WHERE booking_ref = ?
                        ''', (ref,))
                        snacks = snacks_cursor.fetchall()

                        if snacks:
                            print("🍿 Snacks:")
                            for snack_item, qty, subtotal, is_combo in snacks:
                                combo_label = " [COMBO]" if is_combo else ""
                                print(f"   {qty}x {snack_item}{combo_label} - £{float(subtotal):.2f}")

                    except Exception as e:
                        logger.error(f"Error displaying booking: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing bookings: {e}", exc_info=True)
        print(f"❌ Error viewing bookings: {e}")

    input("\n📌 Press Enter to continue...")
