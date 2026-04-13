"""
Cinema Booking System CLI Interface

Provides command-line interface for cinema management including:
- Movie management (add, list, update, delete)
- Screening management (add, list, update, cancel)
- Booking operations (create, cancel, search, refund)
- Member/loyalty programme management
- Staff management
- Promo code management
- Reports and analytics
"""

from datetime import datetime

from education_system.university_system.modules.domain.cinema.services.cinema_service import (
    CinemaService,
)


class CinemaCLI:
    """Command-line interface for the Cinema Booking System."""

    def __init__(self):
        """Initialize the Cinema CLI and database."""
        self.service = CinemaService()
        self.service.init_cinema_db()

    def run(self):
        """Run the cinema CLI main loop."""
        while True:
            self._display_main_menu()
            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                print("\nReturning to main menu...")
                break
            elif choice == '1':
                self._movies_menu()
            elif choice == '2':
                self._screenings_menu()
            elif choice == '3':
                self._bookings_menu()
            elif choice == '4':
                self._members_menu()
            elif choice == '5':
                self._staff_menu()
            elif choice == '6':
                self._promos_menu()
            elif choice == '7':
                self._reports_menu()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    # ========== Main Menu ==========

    def _display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 70)
        print("  CINEMA BOOKING SYSTEM".center(70))
        print("=" * 70)
        print("\n  1. Movies")
        print("  2. Screenings")
        print("  3. Bookings")
        print("  4. Members & Loyalty")
        print("  5. Staff")
        print("  6. Promo Codes")
        print("  7. Reports")
        print("  0. Back to Main Menu")

    # ========== Movies ==========

    def _movies_menu(self):
        """Movies sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  MOVIES MANAGEMENT")
            print("-" * 50)
            print("  1. Add Movie")
            print("  2. List Movies")
            print("  3. View Movie Details")
            print("  4. Update Movie")
            print("  5. Delete Movie")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._add_movie()
                elif choice == '2':
                    self._list_movies()
                elif choice == '3':
                    self._view_movie()
                elif choice == '4':
                    self._update_movie()
                elif choice == '5':
                    self._delete_movie()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _add_movie(self):
        """Add a new movie."""
        print("\n--- Add New Movie ---")
        title = input("Title: ").strip()
        if not title:
            print("Title is required.")
            return
        duration = int(input("Duration (minutes): ").strip())
        genre = input("Genre (optional): ").strip() or None
        rating = input("Rating (optional, e.g. PG, 12A, 15, 18): ").strip() or None
        director = input("Director (optional): ").strip() or None
        description = input("Description (optional): ").strip() or None
        release_date = input("Release date (YYYY-MM-DD, optional): ").strip() or None

        movie_id = self.service.add_movie(
            title=title, duration=duration, genre=genre, rating=rating,
            director=director, description=description, release_date=release_date,
        )
        print(f"\nMovie added successfully (ID: {movie_id})")

    def _list_movies(self):
        """List all movies."""
        show_all = input("Include inactive movies? (y/n) [n]: ").strip().lower() == 'y'
        movies = self.service.list_movies(active_only=not show_all)
        if not movies:
            print("\nNo movies found.")
            return
        print(f"\n{'ID':<6}{'Title':<30}{'Duration':<10}{'Genre':<15}{'Rating':<8}{'Status'}")
        print("-" * 85)
        for m in movies:
            print(f"{m[0]:<6}{m[1]:<30}{m[2]:<10}{(m[3] or ''):<15}{(m[4] or ''):<8}{m[6]}")

    def _view_movie(self):
        """View movie details."""
        movie_id = int(input("Movie ID: ").strip())
        movie = self.service.get_movie(movie_id)
        if not movie:
            print("Movie not found.")
            return
        print(f"\nID: {movie[0]}")
        print(f"Title: {movie[1]}")
        print(f"Duration: {movie[2]} min")
        print(f"Genre: {movie[3] or 'N/A'}")
        print(f"Rating: {movie[4] or 'N/A'}")
        print(f"Director: {movie[5] or 'N/A'}")
        print(f"Description: {movie[6] or 'N/A'}")

    def _update_movie(self):
        """Update a movie."""
        movie_id = int(input("Movie ID to update: ").strip())
        movie = self.service.get_movie(movie_id)
        if not movie:
            print("Movie not found.")
            return
        print(f"Updating: {movie[1]} (leave blank to keep current value)")
        title = input(f"Title [{movie[1]}]: ").strip() or None
        dur = input(f"Duration [{movie[2]}]: ").strip()
        duration = int(dur) if dur else None
        genre = input(f"Genre [{movie[3]}]: ").strip() or None
        rating = input(f"Rating [{movie[4]}]: ").strip() or None
        director = input(f"Director [{movie[5]}]: ").strip() or None
        status = input("Status (active/inactive) [keep]: ").strip() or None

        updated = self.service.update_movie(
            movie_id, title=title, duration=duration, genre=genre,
            rating=rating, director=director, status=status,
        )
        print("Movie updated." if updated else "No changes made.")

    def _delete_movie(self):
        """Delete a movie."""
        movie_id = int(input("Movie ID to delete: ").strip())
        confirm = input(f"Delete movie {movie_id} and all its screenings? (y/n): ").strip().lower()
        if confirm == 'y':
            deleted = self.service.delete_movie(movie_id)
            print("Movie deleted." if deleted else "Movie not found.")

    # ========== Screenings ==========

    def _screenings_menu(self):
        """Screenings sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  SCREENING MANAGEMENT")
            print("-" * 50)
            print("  1. Add Screening")
            print("  2. List Screenings")
            print("  3. View Screening Details")
            print("  4. Update Screening")
            print("  5. Cancel Screening")
            print("  6. View Seats for Screening")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._add_screening()
                elif choice == '2':
                    self._list_screenings()
                elif choice == '3':
                    self._view_screening()
                elif choice == '4':
                    self._update_screening()
                elif choice == '5':
                    self._cancel_screening()
                elif choice == '6':
                    self._view_seats()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _add_screening(self):
        """Add a new screening."""
        print("\n--- Add New Screening ---")
        movie_id = int(input("Movie ID: ").strip())
        screen_number = int(input("Screen number: ").strip())
        show_time = input("Show time (YYYY-MM-DD HH:MM): ").strip()
        price = float(input("Ticket price: ").strip())

        screening_id = self.service.add_screening(
            movie_id=movie_id, screen_number=screen_number,
            show_time=show_time, price=price,
        )
        print(f"\nScreening added (ID: {screening_id})")

    def _list_screenings(self):
        """List screenings."""
        mid = input("Filter by Movie ID (blank for all): ").strip()
        movie_id = int(mid) if mid else None
        screenings = self.service.list_screenings(movie_id=movie_id)
        if not screenings:
            print("\nNo screenings found.")
            return
        print(f"\n{'ID':<6}{'Movie':<25}{'Screen':<8}{'Show Time':<20}{'Price':<8}{'Booked':<8}{'Avail':<8}{'Status'}")
        print("-" * 95)
        for s in screenings:
            print(f"{s[0]:<6}{s[1]:<25}{s[2]:<8}{s[3]:<20}{s[4]:<8.2f}{s[5]:<8}{s[6]:<8}{s[7]}")

    def _view_screening(self):
        """View screening details."""
        screening_id = int(input("Screening ID: ").strip())
        screening = self.service.get_screening(screening_id)
        if not screening:
            print("Screening not found.")
            return
        print(f"\nScreening ID: {screening[0]}")
        print(f"Movie ID: {screening[1]}")
        print(f"Screen: {screening[2]}")
        print(f"Show Time: {screening[3]}")
        print(f"Price: {screening[4]}")

    def _update_screening(self):
        """Update a screening."""
        screening_id = int(input("Screening ID: ").strip())
        print("Leave blank to keep current value:")
        sn = input("Screen number: ").strip()
        screen_number = int(sn) if sn else None
        pr = input("Price: ").strip()
        price = float(pr) if pr else None
        status = input("Status (active/cancelled): ").strip() or None

        updated = self.service.update_screening(
            screening_id, screen_number=screen_number, price=price, status=status,
        )
        print("Screening updated." if updated else "No changes made.")

    def _cancel_screening(self):
        """Cancel a screening."""
        screening_id = int(input("Screening ID to cancel: ").strip())
        confirm = input("Cancel this screening and all its bookings? (y/n): ").strip().lower()
        if confirm == 'y':
            self.service.cancel_screening(screening_id)
            print("Screening cancelled.")

    def _view_seats(self):
        """View seats for a screening."""
        screening_id = int(input("Screening ID: ").strip())
        seats = self.service.get_seats_for_screening(screening_id)
        if not seats:
            print("No seats found.")
            return
        print(f"\n{'ID':<6}{'Row':<6}{'Seat':<6}{'Type':<12}{'Status'}")
        print("-" * 40)
        for s in seats:
            print(f"{s[0]:<6}{s[2]:<6}{s[3]:<6}{s[4]:<12}{s[5]}")

    # ========== Bookings ==========

    def _bookings_menu(self):
        """Bookings sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  BOOKING OPERATIONS")
            print("-" * 50)
            print("  1. Create Booking")
            print("  2. Search Bookings")
            print("  3. Lookup Booking by Reference")
            print("  4. Update Booking")
            print("  5. Cancel Booking")
            print("  6. Reactivate Booking")
            print("  7. Delete Booking")
            print("  8. Refund Booking")
            print("  9. Validate Ticket")
            print(" 10. Create Gift Card")
            print(" 11. Check Gift Card Balance")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._create_booking()
                elif choice == '2':
                    self._search_bookings()
                elif choice == '3':
                    self._lookup_booking()
                elif choice == '4':
                    self._update_booking()
                elif choice == '5':
                    self._cancel_booking()
                elif choice == '6':
                    self._reactivate_booking()
                elif choice == '7':
                    self._delete_booking()
                elif choice == '8':
                    self._refund_booking()
                elif choice == '9':
                    self._validate_ticket()
                elif choice == '10':
                    self._create_gift_card()
                elif choice == '11':
                    self._check_gift_card()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _create_booking(self):
        """Create a new booking."""
        print("\n--- Create Booking ---")
        screening_id = int(input("Screening ID: ").strip())
        customer_name = input("Customer name: ").strip()
        customer_email = input("Customer email (optional): ").strip() or None
        customer_phone = input("Customer phone (optional): ").strip() or None
        payment_method = input("Payment method [Credit Card]: ").strip() or "Credit Card"
        promo_code = input("Promo code (optional): ").strip() or None

        # Show available seats
        seats = self.service.get_seats_for_screening(screening_id)
        available = [s for s in seats if s[5] == 'available']
        if not available:
            print("No available seats.")
            return

        print(f"\nAvailable seats ({len(available)}):")
        for s in available[:20]:
            print(f"  ID: {s[0]}  Row {s[2]} Seat {s[3]} ({s[4]})")
        if len(available) > 20:
            print(f"  ... and {len(available) - 20} more")

        seat_input = input("\nSeat IDs (comma-separated): ").strip()
        seat_ids = [int(x.strip()) for x in seat_input.split(",")]

        # Build ticket types
        ticket_types = {}
        for sid in seat_ids:
            tt = input(f"  Ticket type for seat {sid} (Adult/Child/Senior/Student) [Adult]: ").strip() or "Adult"
            price = float(input(f"  Price for seat {sid}: ").strip())
            ticket_types[sid] = (tt, price)

        # Snacks
        snacks = None
        add_snacks = input("Add snacks? (y/n) [n]: ").strip().lower()
        if add_snacks == 'y':
            snacks = {}
            while True:
                item = input("  Snack name (blank to finish): ").strip()
                if not item:
                    break
                qty = int(input(f"  Quantity of {item}: ").strip())
                snacks[item] = qty

        result = self.service.create_booking(
            screening_id=screening_id, customer_name=customer_name,
            seat_ids=seat_ids, ticket_types=ticket_types,
            customer_email=customer_email, customer_phone=customer_phone,
            payment_method=payment_method, promo_code=promo_code, snacks=snacks,
        )
        print(f"\nBooking created!")
        print(f"  Reference: {result['booking_ref']}")
        print(f"  Total: {result['total_amount']:.2f}")
        if result['discount_amount'] > 0:
            print(f"  Discount: {result['discount_amount']:.2f}")
        print(f"  Seats: {result['seats']}")

    def _search_bookings(self):
        """Search bookings."""
        query = input("Search (name/email/ref, blank for all): ").strip() or None
        status = input("Status filter (active/cancelled/all) [all]: ").strip() or None
        bookings = self.service.search_bookings(query=query, status=status)
        if not bookings:
            print("\nNo bookings found.")
            return
        print(f"\n{'ID':<6}{'Ref':<12}{'Customer':<20}{'Movie':<20}{'Seats':<7}{'Total':<10}{'Status'}")
        print("-" * 85)
        for b in bookings:
            print(f"{b[0]:<6}{b[1]:<12}{b[2]:<20}{b[4]:<20}{b[6]:<7}{b[7]:<10.2f}{b[8]}")

    def _lookup_booking(self):
        """Lookup booking by reference."""
        ref = input("Booking reference: ").strip()
        booking = self.service.get_booking_by_ref(ref)
        if not booking:
            print("Booking not found.")
            return
        print(f"\nBooking: {booking['booking_ref']}")
        print(f"Customer: {booking['customer_name']}")
        print(f"Email: {booking.get('customer_email', 'N/A')}")
        print(f"Movie: {booking['movie_title']}")
        print(f"Show Time: {booking['show_time']}")
        print(f"Screen: {booking['screen_number']}")
        print(f"Total: {booking['total_amount']:.2f}")
        print(f"Payment: {booking['payment_status']} ({booking['payment_method']})")
        print(f"Status: {booking['status']}")
        if booking.get('seats'):
            print("Seats:")
            for s in booking['seats']:
                print(f"  Row {s['row']} Seat {s['seat_number']} ({s['ticket_type']})")

    def _update_booking(self):
        """Update booking details."""
        booking_id = int(input("Booking ID: ").strip())
        print("Leave blank to keep current value:")
        name = input("Customer name: ").strip() or None
        email = input("Customer email: ").strip() or None
        phone = input("Customer phone: ").strip() or None
        payment_method = input("Payment method: ").strip() or None
        payment_status = input("Payment status: ").strip() or None
        notes = input("Notes: ").strip() or None

        updated = self.service.update_booking(
            booking_id, customer_name=name, customer_email=email,
            customer_phone=phone, payment_method=payment_method,
            payment_status=payment_status, notes=notes,
        )
        print("Booking updated." if updated else "No changes made.")

    def _cancel_booking(self):
        """Cancel a booking."""
        booking_id = int(input("Booking ID: ").strip())
        ref = self.service.cancel_booking(booking_id)
        print(f"Booking {ref} cancelled.")

    def _reactivate_booking(self):
        """Reactivate a cancelled booking."""
        booking_id = int(input("Booking ID: ").strip())
        ref = self.service.reactivate_booking(booking_id)
        print(f"Booking {ref} reactivated.")

    def _delete_booking(self):
        """Permanently delete a booking."""
        booking_id = int(input("Booking ID: ").strip())
        confirm = input("Permanently delete this booking? (y/n): ").strip().lower()
        if confirm == 'y':
            ref = self.service.delete_booking(booking_id)
            print(f"Booking {ref} deleted permanently.")

    def _refund_booking(self):
        """Refund a booking."""
        booking_id = int(input("Booking ID: ").strip())
        amount = self.service.refund_booking(booking_id)
        print(f"Refunded {amount:.2f}")

    def _validate_ticket(self):
        """Validate a ticket."""
        ref = input("Booking reference: ").strip()
        result = self.service.validate_ticket(ref)
        if result['valid']:
            print("\nTicket is VALID")
            b = result['booking']
            print(f"  Customer: {b['customer_name']}")
            print(f"  Movie: {b['movie_title']}")
            print(f"  Show Time: {b['show_time']}")
        else:
            print(f"\nTicket is INVALID: {result['error']}")

    def _create_gift_card(self):
        """Create a gift card."""
        print("\n--- Create Gift Card ---")
        value = float(input("Value: ").strip())
        purchaser_name = input("Purchaser name (optional): ").strip() or None
        purchaser_email = input("Purchaser email (optional): ").strip() or None
        recipient_name = input("Recipient name (optional): ").strip() or None
        recipient_email = input("Recipient email (optional): ").strip() or None
        message = input("Message (optional): ").strip() or None

        code = self.service.create_gift_card(
            value=value, purchaser_name=purchaser_name,
            purchaser_email=purchaser_email, recipient_name=recipient_name,
            recipient_email=recipient_email, message=message,
        )
        print(f"\nGift card created: {code}")

    def _check_gift_card(self):
        """Check gift card balance."""
        code = input("Gift card code: ").strip()
        balance = self.service.get_gift_card_balance(code)
        if balance is not None:
            print(f"Balance: {balance:.2f}")
        else:
            print("Gift card not found, expired, or inactive.")

    # ========== Members ==========

    def _members_menu(self):
        """Members & loyalty sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  MEMBERS & LOYALTY")
            print("-" * 50)
            print("  1. Register Member")
            print("  2. Search Members")
            print("  3. View Member Details")
            print("  4. Lookup Member by Email")
            print("  5. Add Loyalty Points")
            print("  6. View Member Booking History")
            print("  7. Get Member Discount")
            print("  8. Deactivate Member")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._register_member()
                elif choice == '2':
                    self._search_members()
                elif choice == '3':
                    self._view_member()
                elif choice == '4':
                    self._lookup_member()
                elif choice == '5':
                    self._add_points()
                elif choice == '6':
                    self._member_history()
                elif choice == '7':
                    self._member_discount()
                elif choice == '8':
                    self._deactivate_member()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _register_member(self):
        """Register a new member."""
        print("\n--- Register New Member ---")
        name = input("Name: ").strip()
        email = input("Email: ").strip()
        phone = input("Phone (optional): ").strip() or None
        birthday = input("Birthday (YYYY-MM-DD, optional): ").strip() or None

        member_id = self.service.register_member(
            name=name, email=email, phone=phone, birthday=birthday,
        )
        print(f"\nMember registered (ID: {member_id}) with 100 welcome points")

    def _search_members(self):
        """Search members."""
        query = input("Search (name/email, blank for all): ").strip() or None
        members = self.service.search_members(query=query)
        if not members:
            print("\nNo members found.")
            return
        print(f"\n{'ID':<6}{'Name':<25}{'Email':<30}{'Tier':<10}{'Points':<10}{'Status'}")
        print("-" * 90)
        for m in members:
            print(f"{m[0]:<6}{m[1]:<25}{m[2]:<30}{m[3]:<10}{m[4]:<10}{m[7]}")

    def _view_member(self):
        """View member details."""
        member_id = int(input("Member ID: ").strip())
        member = self.service.get_member(member_id)
        if not member:
            print("Member not found.")
            return
        print(f"\nID: {member[0]}")
        print(f"Name: {member[1]}")
        print(f"Email: {member[2]}")
        print(f"Phone: {member[3] or 'N/A'}")
        print(f"Tier: {member[5] if len(member) > 5 else 'N/A'}")
        print(f"Points: {member[6] if len(member) > 6 else 'N/A'}")

    def _lookup_member(self):
        """Lookup member by email."""
        email = input("Email: ").strip()
        member = self.service.lookup_member(email)
        if not member:
            print("Member not found.")
            return
        print(f"\nID: {member[0]}, Name: {member[1]}, Tier: {member[5] if len(member) > 5 else 'N/A'}")

    def _add_points(self):
        """Add loyalty points."""
        member_id = int(input("Member ID: ").strip())
        points = int(input("Points to add: ").strip())
        new_tier = self.service.add_member_points(member_id, points)
        print(f"Points added. Current tier: {new_tier}")

    def _member_history(self):
        """View member booking history."""
        email = input("Member email: ").strip()
        history = self.service.get_member_booking_history(email)
        if not history:
            print("\nNo booking history found.")
            return
        print(f"\n{'Ref':<12}{'Movie':<25}{'Show Time':<20}{'Amount':<10}{'Status'}")
        print("-" * 75)
        for h in history:
            print(f"{h[0]:<12}{h[1]:<25}{h[2]:<20}{h[3]:<10.2f}{h[4]}")

    def _member_discount(self):
        """Get member discount."""
        email = input("Member email: ").strip()
        discount = self.service.get_member_discount(email)
        print(f"Discount: {discount}%")

    def _deactivate_member(self):
        """Deactivate a member."""
        member_id = int(input("Member ID: ").strip())
        confirm = input("Deactivate this member? (y/n): ").strip().lower()
        if confirm == 'y':
            self.service.deactivate_member(member_id)
            print("Member deactivated.")

    # ========== Staff ==========

    def _staff_menu(self):
        """Staff sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  STAFF MANAGEMENT")
            print("-" * 50)
            print("  1. Add Staff Member")
            print("  2. List Staff")
            print("  3. Verify Staff Login")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._add_staff()
                elif choice == '2':
                    self._list_staff()
                elif choice == '3':
                    self._verify_staff()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _add_staff(self):
        """Add a staff member."""
        print("\n--- Add Staff Member ---")
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        name = input("Full name: ").strip()
        role = input("Role (manager/cashier/projectionist/usher): ").strip()
        email = input("Email (optional): ").strip() or None
        phone = input("Phone (optional): ").strip() or None

        staff_id = self.service.add_staff(
            username=username, password=password, name=name,
            role=role, email=email, phone=phone,
        )
        print(f"\nStaff member added (ID: {staff_id})")

    def _list_staff(self):
        """List all staff."""
        staff = self.service.list_staff()
        if not staff:
            print("\nNo staff found.")
            return
        print(f"\n{'ID':<6}{'Username':<15}{'Name':<25}{'Role':<15}{'Status'}")
        print("-" * 70)
        for s in staff:
            print(f"{s[0]:<6}{s[1]:<15}{s[4]:<25}{s[6]:<15}{s[8] if len(s) > 8 else ''}")

    def _verify_staff(self):
        """Verify staff login."""
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        staff = self.service.verify_staff_password(username, password)
        if staff:
            print(f"\nLogin successful - {staff[4]} ({staff[6]})")
        else:
            print("\nLogin failed.")

    # ========== Promo Codes ==========

    def _promos_menu(self):
        """Promo codes sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  PROMO CODE MANAGEMENT")
            print("-" * 50)
            print("  1. Create Promo Code")
            print("  2. List Promo Codes")
            print("  3. Validate Promo Code")
            print("  4. Deactivate Promo Code")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._create_promo()
                elif choice == '2':
                    self._list_promos()
                elif choice == '3':
                    self._validate_promo()
                elif choice == '4':
                    self._deactivate_promo()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _create_promo(self):
        """Create a promo code."""
        print("\n--- Create Promo Code ---")
        code = input("Code: ").strip()
        discount_type = input("Discount type (percentage/fixed): ").strip()
        discount_value = float(input("Discount value: ").strip())
        min_purchase = float(input("Minimum purchase [0]: ").strip() or "0")
        max_uses_input = input("Max uses (blank for unlimited): ").strip()
        max_uses = int(max_uses_input) if max_uses_input else None
        valid_until = input("Valid until (YYYY-MM-DD, optional): ").strip() or None

        promo_id = self.service.create_promo_code(
            code=code, discount_type=discount_type, discount_value=discount_value,
            min_purchase=min_purchase, max_uses=max_uses, valid_until=valid_until,
        )
        print(f"\nPromo code created (ID: {promo_id})")

    def _list_promos(self):
        """List all promo codes."""
        promos = self.service.list_promo_codes()
        if not promos:
            print("\nNo promo codes found.")
            return
        print(f"\n{'ID':<6}{'Code':<15}{'Type':<12}{'Value':<10}{'Uses':<8}{'Status'}")
        print("-" * 60)
        for p in promos:
            print(f"{p[0]:<6}{p[1]:<15}{p[2]:<12}{p[3]:<10}{p[7] if len(p) > 7 else '':<8}{p[8] if len(p) > 8 else ''}")

    def _validate_promo(self):
        """Validate a promo code."""
        code = input("Promo code: ").strip()
        result = self.service.validate_promo_code(code)
        if result:
            print(f"\nPromo code is valid: {result[1]} - {result[2]} {result[3]}")
        else:
            print("\nPromo code is invalid or expired.")

    def _deactivate_promo(self):
        """Deactivate a promo code."""
        promo_id = int(input("Promo ID: ").strip())
        self.service.deactivate_promo_code(promo_id)
        print("Promo code deactivated.")

    # ========== Reports ==========

    def _reports_menu(self):
        """Reports sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  REPORTS & ANALYTICS")
            print("-" * 50)
            print("  1. Sales Summary")
            print("  2. Daily Sales Report")
            print("  3. Revenue by Movie")
            print("  4. Seat Occupancy")
            print("  5. Payment Methods Breakdown")
            print("  6. Booking Status Distribution")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._sales_summary()
                elif choice == '2':
                    self._daily_sales()
                elif choice == '3':
                    self._revenue_by_movie()
                elif choice == '4':
                    self._occupancy_report()
                elif choice == '5':
                    self._payment_methods()
                elif choice == '6':
                    self._booking_statuses()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _get_date_range(self):
        """Prompt for date range."""
        today = datetime.now().strftime("%Y-%m-%d")
        from_date = input(f"From date (YYYY-MM-DD) [{today}]: ").strip() or today
        to_date = input(f"To date (YYYY-MM-DD) [{today}]: ").strip() or today
        return from_date, to_date

    def _sales_summary(self):
        """Show sales summary."""
        from_date, to_date = self._get_date_range()
        summary = self.service.report_sales_summary(from_date, to_date)
        print(f"\n--- Sales Summary ({from_date} to {to_date}) ---")
        print(f"Total Bookings: {summary['total_bookings']}")
        print(f"Active Bookings: {summary['active_bookings']}")
        print(f"Cancelled Bookings: {summary['cancelled_bookings']}")
        print(f"Tickets Sold: {summary['tickets_sold']}")
        print(f"Total Revenue: {summary['total_revenue']:.2f}")
        print(f"Avg Booking Value: {summary['avg_booking_value']:.2f}")

    def _daily_sales(self):
        """Show daily sales."""
        from_date, to_date = self._get_date_range()
        data = self.service.report_daily_sales(from_date, to_date)
        if not data:
            print("\nNo data for this period.")
            return
        print(f"\n{'Date':<15}{'Bookings':<12}{'Revenue'}")
        print("-" * 35)
        for row in data:
            print(f"{row[0]:<15}{row[1]:<12}{row[2]:.2f}")

    def _revenue_by_movie(self):
        """Show revenue by movie."""
        from_date, to_date = self._get_date_range()
        data = self.service.report_revenue_by_movie(from_date, to_date)
        if not data:
            print("\nNo data for this period.")
            return
        print(f"\n{'Movie':<30}{'Bookings':<12}{'Revenue'}")
        print("-" * 50)
        for row in data:
            print(f"{row[0]:<30}{row[1]:<12}{row[2]:.2f}")

    def _occupancy_report(self):
        """Show seat occupancy."""
        from_date, to_date = self._get_date_range()
        data = self.service.report_occupancy(from_date, to_date)
        if not data:
            print("\nNo data for this period.")
            return
        print(f"\n{'Movie':<25}{'Booked':<10}{'Available':<12}{'Total':<10}{'Occupancy'}")
        print("-" * 65)
        for d in data:
            print(f"{d['movie']:<25}{d['booked']:<10}{d['available']:<12}{d['total']:<10}{d['occupancy_pct']}%")

    def _payment_methods(self):
        """Show payment methods breakdown."""
        from_date, to_date = self._get_date_range()
        data = self.service.report_payment_methods(from_date, to_date)
        if not data:
            print("\nNo data for this period.")
            return
        print(f"\n{'Method':<20}{'Count':<10}{'Revenue'}")
        print("-" * 40)
        for row in data:
            print(f"{row[0]:<20}{row[1]:<10}{row[2]:.2f}")

    def _booking_statuses(self):
        """Show booking status distribution."""
        from_date, to_date = self._get_date_range()
        data = self.service.report_booking_statuses(from_date, to_date)
        if not data:
            print("\nNo data for this period.")
            return
        print(f"\n{'Status':<20}{'Count'}")
        print("-" * 30)
        for row in data:
            print(f"{row[0]:<20}{row[1]}")


def main():
    """Entry point for the Cinema CLI."""
    cli = CinemaCLI()
    cli.run()


if __name__ == "__main__":
    main()
