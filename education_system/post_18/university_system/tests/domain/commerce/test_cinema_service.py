"""
Tests for the cinema booking system service layer.

``CinemaService`` is the GUI-free, reusable surface for the cinema module
(commerce/cinema). It accepts a ``db_file`` argument so every test runs against
an isolated temporary database. Schema fidelity is preserved by building tables
with the module's own ``_init_database_tables``; the seeded sample rows are then
cleared so each test starts from a known, empty state.

Coverage: movie CRUD, screening management, seat generation/queries, the full
booking lifecycle, ticket validation, loyalty members, promo codes, staff auth
(PBKDF2 hashing), payments/refunds, report aggregations, gift cards, and the
audit log.
"""

import os
import sqlite3
import tempfile

import pytest

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import (
    _init_database_tables,
)
from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.constants import (
    MEMBERSHIP_TIERS,
    SNACKS_MENU,
)
from education_system.post_18.university_system.modules.domain.commerce.cinema.services.cinema_service import (
    CinemaService,
    _generate_booking_ref,
)

# Tables that hold seeded sample data we want gone before each test.
_SEEDED_TABLES = ("movies", "screenings", "seats", "promo_codes")


@pytest.fixture
def db_path():
    """A temp database with the full cinema schema and no seed rows."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    try:
        _init_database_tables(conn, conn.cursor())
    finally:
        conn.close()

    # Drop the sample movies/screenings/seats/promos the schema seeds in so
    # every test starts from an empty, deterministic state.
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        for table in _SEEDED_TABLES:
            cur.execute(f"DELETE FROM {table}")  # nosec B608 - fixed table list
        conn.commit()
    finally:
        conn.close()

    yield path

    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def svc(db_path):
    """A CinemaService bound to the temp database."""
    return CinemaService(db_file=db_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_screening(svc, *, price=10.0, screen_number=1, show_time="2026-06-01 19:00"):
    """Create a movie + screening and return (movie_id, screening_id, seats)."""
    movie_id = svc.add_movie("Test Movie", 120, genre="Action", rating="PG-13")
    screening_id = svc.add_screening(movie_id, screen_number, show_time, price)
    seats = svc.get_seats_for_screening(screening_id)
    return movie_id, screening_id, seats


def _book_one(svc, screening_id, seats, *, name="Alice", price=10.0, **kwargs):
    """Book the first available seat as an Adult ticket."""
    seat_id = seats[0][0]
    return svc.create_booking(
        screening_id,
        name,
        [seat_id],
        {seat_id: ("Adult", price)},
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestBookingRef:
    def test_length_and_charset(self):
        ref = _generate_booking_ref()
        assert len(ref) == 8
        assert ref.isalnum()
        assert ref.upper() == ref

    def test_refs_are_unique(self):
        refs = {_generate_booking_ref() for _ in range(200)}
        # Collisions are astronomically unlikely for 8-char alnum refs.
        assert len(refs) == 200


# ---------------------------------------------------------------------------
# Movie CRUD
# ---------------------------------------------------------------------------


class TestMovieCrud:
    def test_add_and_get_movie(self, svc):
        movie_id = svc.add_movie("Inception", 148, genre="Sci-Fi", director="Nolan")
        assert isinstance(movie_id, int)
        row = svc.get_movie(movie_id)
        assert row is not None
        assert row[1] == "Inception"
        assert row[2] == 148

    def test_get_missing_movie_returns_none(self, svc):
        assert svc.get_movie(99999) is None

    def test_list_movies_orders_by_id_desc(self, svc):
        first = svc.add_movie("First", 100)
        second = svc.add_movie("Second", 110)
        movies = svc.list_movies()
        ids = [m[0] for m in movies]
        assert ids == [second, first]

    def test_list_movies_active_only_excludes_inactive(self, svc):
        active = svc.add_movie("Active", 100)
        inactive = svc.add_movie("Inactive", 100)
        svc.update_movie(inactive, status="inactive")

        active_ids = [m[0] for m in svc.list_movies(active_only=True)]
        all_ids = [m[0] for m in svc.list_movies(active_only=False)]
        assert active in active_ids
        assert inactive not in active_ids
        assert inactive in all_ids

    def test_update_movie_changes_fields(self, svc):
        movie_id = svc.add_movie("Old Title", 100)
        assert svc.update_movie(movie_id, title="New Title", duration=130) is True
        row = svc.get_movie(movie_id)
        assert row[1] == "New Title"
        assert row[2] == 130

    def test_update_movie_no_fields_returns_false(self, svc):
        movie_id = svc.add_movie("Title", 100)
        assert svc.update_movie(movie_id) is False

    def test_update_missing_movie_returns_false(self, svc):
        assert svc.update_movie(99999, title="X") is False

    def test_delete_movie_removes_movie_and_screenings(self, svc):
        movie_id, screening_id, _ = _make_screening(svc)
        assert svc.delete_movie(movie_id) is True
        assert svc.get_movie(movie_id) is None
        assert svc.get_screening(screening_id) is None

    def test_delete_missing_movie_returns_false(self, svc):
        assert svc.delete_movie(99999) is False


# ---------------------------------------------------------------------------
# Screening management & seat generation
# ---------------------------------------------------------------------------


class TestScreenings:
    def test_add_screening_generates_default_seat_grid(self, svc):
        _, screening_id, seats = _make_screening(svc)
        # Default grid is rows A-H (8) x 12 seats = 96.
        assert len(seats) == 96
        rows = {s[2] for s in seats}
        assert rows == set("ABCDEFGH")

    def test_vip_seats_in_rows_a_and_b(self, svc):
        _, _, seats = _make_screening(svc)
        for _id, _sid, row, _num, seat_type, _status in seats:
            if row in ("A", "B"):
                assert seat_type == "vip"
            else:
                assert seat_type == "standard"

    def test_custom_rows_and_seats_per_row(self, svc):
        movie_id = svc.add_movie("Small", 90)
        screening_id = svc.add_screening(
            movie_id, 2, "2026-06-02 12:00", 8.0, rows=["A", "B"], seats_per_row=5
        )
        seats = svc.get_seats_for_screening(screening_id)
        assert len(seats) == 10

    def test_all_seats_start_available(self, svc):
        _, _, seats = _make_screening(svc)
        assert all(s[5] == "available" for s in seats)

    def test_list_screenings_reports_seat_counts(self, svc):
        movie_id, screening_id, seats = _make_screening(svc)
        _book_one(svc, screening_id, seats)
        rows = svc.list_screenings(movie_id=movie_id)
        assert len(rows) == 1
        (_sid, title, _screen, _time, _price, booked, available, _status) = rows[0]
        assert title == "Test Movie"
        assert booked == 1
        assert available == 95

    def test_list_screenings_filter_by_movie(self, svc):
        movie_a, screening_a, _ = _make_screening(svc, screen_number=1)
        movie_b = svc.add_movie("Other", 100)
        svc.add_screening(movie_b, 2, "2026-06-03 18:00", 9.0)
        rows = svc.list_screenings(movie_id=movie_a)
        assert all(r[0] == screening_a for r in rows)

    def test_update_screening_price(self, svc):
        _, screening_id, _ = _make_screening(svc, price=10.0)
        assert svc.update_screening(screening_id, price=15.5) is True
        # price is column index 4 in screenings (id, movie_id, screen_number,
        # show_time, price, status)
        assert svc.get_screening(screening_id)[4] == 15.5

    def test_update_screening_no_fields_returns_false(self, svc):
        _, screening_id, _ = _make_screening(svc)
        assert svc.update_screening(screening_id) is False

    def test_cancel_screening_releases_seats_and_bookings(self, svc):
        movie_id, screening_id, seats = _make_screening(svc)
        booking = _book_one(svc, screening_id, seats)

        svc.cancel_screening(screening_id)

        assert svc.get_screening(screening_id)[5] == "cancelled"
        # All seats released back to available.
        after = svc.get_seats_for_screening(screening_id)
        assert all(s[5] == "available" for s in after)
        # Booking marked cancelled.
        fetched = svc.get_booking_by_ref(booking["booking_ref"])
        assert fetched["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Booking lifecycle
# ---------------------------------------------------------------------------


class TestBookings:
    def test_create_booking_returns_ref_and_total(self, svc):
        _, screening_id, seats = _make_screening(svc)
        result = _book_one(svc, screening_id, seats, price=12.0)
        assert len(result["booking_ref"]) == 8
        assert result["total_amount"] == 12.0
        assert result["discount_amount"] == 0.0
        assert result["seats"] == [(seats[0][2], seats[0][3])]

    def test_create_booking_marks_seat_booked(self, svc):
        _, screening_id, seats = _make_screening(svc)
        seat_id = seats[0][0]
        _book_one(svc, screening_id, seats)
        after = {s[0]: s[5] for s in svc.get_seats_for_screening(screening_id)}
        assert after[seat_id] == "booked"

    def test_create_booking_with_snacks_adds_to_total(self, svc):
        _, screening_id, seats = _make_screening(svc)
        snack = "Popcorn (Large)"
        seat_id = seats[0][0]
        result = svc.create_booking(
            screening_id,
            "Bob",
            [seat_id],
            {seat_id: ("Adult", 10.0)},
            snacks={snack: 2},
        )
        expected = 10.0 + SNACKS_MENU[snack] * 2
        assert result["total_amount"] == pytest.approx(expected)

    def test_create_booking_applies_percentage_promo(self, svc):
        _, screening_id, seats = _make_screening(svc)
        svc.create_promo_code("TENOFF", "percentage", 10, min_purchase=0)
        seat_id = seats[0][0]
        result = svc.create_booking(
            screening_id,
            "Carol",
            [seat_id],
            {seat_id: ("Adult", 100.0)},
            promo_code="tenoff",  # lower-case to confirm normalisation
        )
        assert result["discount_amount"] == pytest.approx(10.0)
        assert result["total_amount"] == pytest.approx(90.0)

    def test_create_booking_applies_fixed_promo(self, svc):
        _, screening_id, seats = _make_screening(svc)
        svc.create_promo_code("FIVE", "fixed", 5, min_purchase=0)
        seat_id = seats[0][0]
        result = svc.create_booking(
            screening_id,
            "Dan",
            [seat_id],
            {seat_id: ("Adult", 20.0)},
            promo_code="FIVE",
        )
        assert result["discount_amount"] == pytest.approx(5.0)
        assert result["total_amount"] == pytest.approx(15.0)

    def test_promo_below_min_purchase_not_applied(self, svc):
        _, screening_id, seats = _make_screening(svc)
        svc.create_promo_code("BIG", "fixed", 5, min_purchase=100)
        seat_id = seats[0][0]
        result = svc.create_booking(
            screening_id,
            "Eve",
            [seat_id],
            {seat_id: ("Adult", 20.0)},
            promo_code="BIG",
        )
        assert result["discount_amount"] == 0.0
        assert result["total_amount"] == pytest.approx(20.0)

    def test_promo_usage_increments(self, svc):
        _, screening_id, seats = _make_screening(svc)
        promo_id = svc.create_promo_code("USE1", "fixed", 1, min_purchase=0)
        seat_id = seats[0][0]
        svc.create_booking(
            screening_id, "F", [seat_id], {seat_id: ("Adult", 10.0)}, promo_code="USE1"
        )
        # times_used is column index 6 in promo_codes.
        row = next(p for p in svc.list_promo_codes() if p[0] == promo_id)
        assert row[6] == 1

    def test_get_booking_by_ref_returns_details(self, svc):
        movie_id, screening_id, seats = _make_screening(svc)
        result = _book_one(svc, screening_id, seats, name="Grace")
        fetched = svc.get_booking_by_ref(result["booking_ref"])
        assert fetched["customer_name"] == "Grace"
        assert fetched["movie_title"] == "Test Movie"
        assert fetched["status"] == "active"
        assert len(fetched["seats"]) == 1
        assert fetched["seats"][0]["ticket_type"] == "Adult"

    def test_get_booking_by_ref_missing_returns_none(self, svc):
        assert svc.get_booking_by_ref("NOPE1234") is None

    def test_cancel_booking_releases_seats(self, svc):
        _, screening_id, seats = _make_screening(svc)
        seat_id = seats[0][0]
        result = _book_one(svc, screening_id, seats)
        # cancel_booking returns the ref by booking_id; look it up.
        booking = svc.get_booking_by_ref(result["booking_ref"])
        ref = svc.cancel_booking(booking["id"])
        assert ref == result["booking_ref"]
        after = {s[0]: s[5] for s in svc.get_seats_for_screening(screening_id)}
        assert after[seat_id] == "available"

    def test_cancel_booking_twice_raises(self, svc):
        _, screening_id, seats = _make_screening(svc)
        result = _book_one(svc, screening_id, seats)
        booking_id = svc.get_booking_by_ref(result["booking_ref"])["id"]
        svc.cancel_booking(booking_id)
        with pytest.raises(ValueError, match="already cancelled"):
            svc.cancel_booking(booking_id)

    def test_cancel_missing_booking_raises(self, svc):
        with pytest.raises(ValueError, match="not found"):
            svc.cancel_booking(99999)

    def test_reactivate_booking_restores_seats(self, svc):
        _, screening_id, seats = _make_screening(svc)
        seat_id = seats[0][0]
        result = _book_one(svc, screening_id, seats)
        booking_id = svc.get_booking_by_ref(result["booking_ref"])["id"]
        svc.cancel_booking(booking_id)

        svc.reactivate_booking(booking_id)
        after = {s[0]: s[5] for s in svc.get_seats_for_screening(screening_id)}
        assert after[seat_id] == "booked"
        assert svc.get_booking_by_ref(result["booking_ref"])["status"] == "active"

    def test_reactivate_active_booking_raises(self, svc):
        _, screening_id, seats = _make_screening(svc)
        result = _book_one(svc, screening_id, seats)
        booking_id = svc.get_booking_by_ref(result["booking_ref"])["id"]
        with pytest.raises(ValueError, match="already active"):
            svc.reactivate_booking(booking_id)

    def test_reactivate_when_seat_taken_raises(self, svc):
        _, screening_id, seats = _make_screening(svc)
        seat_id = seats[0][0]
        first = _book_one(svc, screening_id, seats)
        first_id = svc.get_booking_by_ref(first["booking_ref"])["id"]
        svc.cancel_booking(first_id)
        # Someone else books the freed seat.
        svc.create_booking(
            screening_id, "Squatter", [seat_id], {seat_id: ("Adult", 10.0)}
        )
        with pytest.raises(ValueError, match="no longer available"):
            svc.reactivate_booking(first_id)

    def test_delete_booking_removes_it_and_frees_seats(self, svc):
        _, screening_id, seats = _make_screening(svc)
        seat_id = seats[0][0]
        result = _book_one(svc, screening_id, seats)
        booking_id = svc.get_booking_by_ref(result["booking_ref"])["id"]
        ref = svc.delete_booking(booking_id)
        assert ref == result["booking_ref"]
        assert svc.get_booking_by_ref(result["booking_ref"]) is None
        after = {s[0]: s[5] for s in svc.get_seats_for_screening(screening_id)}
        assert after[seat_id] == "available"

    def test_update_booking_fields(self, svc):
        _, screening_id, seats = _make_screening(svc)
        result = _book_one(svc, screening_id, seats)
        booking_id = svc.get_booking_by_ref(result["booking_ref"])["id"]
        assert svc.update_booking(booking_id, customer_name="Renamed") is True
        assert svc.get_booking_by_ref(result["booking_ref"])["customer_name"] == "Renamed"

    def test_update_booking_no_fields_returns_false(self, svc):
        _, screening_id, seats = _make_screening(svc)
        result = _book_one(svc, screening_id, seats)
        booking_id = svc.get_booking_by_ref(result["booking_ref"])["id"]
        assert svc.update_booking(booking_id) is False

    def test_search_bookings_by_name(self, svc):
        _, screening_id, seats = _make_screening(svc)
        _book_one(svc, screening_id, seats, name="Findme Smith")
        results = svc.search_bookings(query="Findme")
        assert len(results) == 1
        assert results[0][2] == "Findme Smith"

    def test_search_bookings_filter_by_status(self, svc):
        _, screening_id, seats = _make_screening(svc)
        active = _book_one(svc, screening_id, seats, name="ActiveCust")
        # second seat
        seat2 = seats[1][0]
        cancelled = svc.create_booking(
            screening_id, "CancelledCust", [seat2], {seat2: ("Adult", 10.0)}
        )
        cid = svc.get_booking_by_ref(cancelled["booking_ref"])["id"]
        svc.cancel_booking(cid)

        active_only = svc.search_bookings(status="active")
        names = {r[2] for r in active_only}
        assert "ActiveCust" in names
        assert "CancelledCust" not in names


# ---------------------------------------------------------------------------
# Ticket validation
# ---------------------------------------------------------------------------


class TestTicketValidation:
    def test_valid_ticket(self, svc):
        _, screening_id, seats = _make_screening(svc)
        result = _book_one(svc, screening_id, seats)
        verdict = svc.validate_ticket(result["booking_ref"])
        assert verdict["valid"] is True
        assert verdict["booking"]["booking_ref"] == result["booking_ref"]

    def test_unknown_ref_invalid(self, svc):
        verdict = svc.validate_ticket("BADREF99")
        assert verdict["valid"] is False
        assert verdict["error"] == "Booking not found"

    def test_cancelled_ticket_invalid(self, svc):
        _, screening_id, seats = _make_screening(svc)
        result = _book_one(svc, screening_id, seats)
        booking_id = svc.get_booking_by_ref(result["booking_ref"])["id"]
        svc.cancel_booking(booking_id)
        verdict = svc.validate_ticket(result["booking_ref"])
        assert verdict["valid"] is False
        assert "cancelled" in verdict["error"]


# ---------------------------------------------------------------------------
# Loyalty members
# ---------------------------------------------------------------------------


class TestMembers:
    def test_register_and_lookup_member(self, svc):
        member_id = svc.register_member("Jane", "jane@example.com", phone="555")
        assert isinstance(member_id, int)
        row = svc.lookup_member("jane@example.com")
        assert row is not None
        assert row[2] == "Jane"  # name column

    def test_lookup_missing_member(self, svc):
        assert svc.lookup_member("nobody@example.com") is None

    def test_register_member_starts_bronze(self, svc):
        member_id = svc.register_member("Tom", "tom@example.com", initial_points=0)
        # tier column index 5 in members.
        assert svc.get_member(member_id)[5] == "Bronze"

    def test_add_points_promotes_tier(self, svc):
        member_id = svc.register_member("Up", "up@example.com", initial_points=0)
        tier = svc.add_member_points(member_id, MEMBERSHIP_TIERS["Silver"]["min_points"])
        assert tier == "Silver"
        assert svc.get_member(member_id)[5] == "Silver"

    def test_add_points_to_gold(self, svc):
        member_id = svc.register_member("G", "g@example.com", initial_points=0)
        tier = svc.add_member_points(member_id, 1500)
        assert tier == "Gold"

    def test_search_members_by_query(self, svc):
        svc.register_member("Searchable Person", "search@example.com")
        results = svc.search_members(query="Searchable")
        assert len(results) == 1
        assert results[0][1] == "Searchable Person"

    def test_update_member_loyalty_accumulates(self, svc):
        member_id = svc.register_member("Loyal", "loyal@example.com")
        svc.update_member_loyalty(member_id, spent=50.0, bookings_increment=2)
        svc.update_member_loyalty(member_id, spent=25.0, bookings_increment=1)
        row = svc.get_member(member_id)
        # total_spent index 6, bookings_count index 7.
        assert row[6] == pytest.approx(75.0)
        assert row[7] == 3

    def test_member_discount_reflects_tier(self, svc):
        member_id = svc.register_member("Disc", "disc@example.com", initial_points=0)
        svc.add_member_points(member_id, 1500)  # Gold -> 10% discount
        assert svc.get_member_discount("disc@example.com") == 10

    def test_member_discount_unknown_email_zero(self, svc):
        assert svc.get_member_discount("ghost@example.com") == 0

    def test_deactivate_member_zeroes_discount(self, svc):
        member_id = svc.register_member("Off", "off@example.com", initial_points=0)
        svc.add_member_points(member_id, 1500)
        svc.deactivate_member(member_id)
        # Inactive members get no discount (query filters status='active').
        assert svc.get_member_discount("off@example.com") == 0

    def test_member_booking_history(self, svc):
        _, screening_id, seats = _make_screening(svc)
        _book_one(
            svc, screening_id, seats, name="Hist", customer_email="hist@example.com"
        )
        history = svc.get_member_booking_history("hist@example.com")
        assert len(history) == 1
        assert history[0][1] == "Test Movie"


# ---------------------------------------------------------------------------
# Promo codes
# ---------------------------------------------------------------------------


class TestPromoCodes:
    def test_create_and_validate_promo(self, svc):
        svc.create_promo_code("SUMMER", "percentage", 15, min_purchase=10)
        row = svc.validate_promo_code("summer")  # case-insensitive
        assert row is not None
        assert row[1] == "SUMMER"

    def test_validate_unknown_promo_returns_none(self, svc):
        assert svc.validate_promo_code("NOSUCH") is None

    def test_expired_promo_invalid(self, svc):
        svc.create_promo_code(
            "OLD", "fixed", 5, min_purchase=0, valid_until="2000-01-01"
        )
        assert svc.validate_promo_code("OLD") is None

    def test_deactivate_promo(self, svc):
        promo_id = svc.create_promo_code("GONE", "fixed", 5)
        svc.deactivate_promo_code(promo_id)
        assert svc.validate_promo_code("GONE") is None

    def test_list_promo_codes(self, svc):
        svc.create_promo_code("A1", "fixed", 1)
        svc.create_promo_code("B2", "fixed", 2)
        codes = {p[1] for p in svc.list_promo_codes()}
        assert {"A1", "B2"} <= codes


# ---------------------------------------------------------------------------
# Staff management & authentication
# ---------------------------------------------------------------------------


class TestStaff:
    def test_add_staff_returns_id(self, svc):
        staff_id = svc.add_staff("manager1", "pw123", "Manager One", "manager")
        assert isinstance(staff_id, int)

    def test_password_is_not_stored_plaintext(self, svc):
        svc.add_staff("secure", "supersecret", "Secure User", "cashier")
        staff = next(s for s in svc.list_staff() if s[1] == "secure")
        # password_hash index 2 must not equal the raw password.
        assert staff[2] != "supersecret"
        assert len(staff[2]) > 20

    def test_verify_correct_password(self, svc):
        svc.add_staff("login1", "rightpw", "Login One", "usher")
        result = svc.verify_staff_password("login1", "rightpw")
        assert result is not None
        assert result[1] == "login1"

    def test_verify_wrong_password(self, svc):
        svc.add_staff("login2", "rightpw", "Login Two", "usher")
        assert svc.verify_staff_password("login2", "wrongpw") is None

    def test_verify_unknown_user(self, svc):
        assert svc.verify_staff_password("ghost", "whatever") is None

    def test_verify_updates_last_login(self, svc):
        svc.add_staff("login3", "pw", "Login Three", "manager")
        before = next(s for s in svc.list_staff() if s[1] == "login3")
        # last_login index 9 starts NULL.
        assert before[9] is None
        svc.verify_staff_password("login3", "pw")
        after = next(s for s in svc.list_staff() if s[1] == "login3")
        assert after[9] is not None


# ---------------------------------------------------------------------------
# Payments & refunds
# ---------------------------------------------------------------------------


class TestPaymentsRefunds:
    def test_record_payment_updates_booking(self, svc):
        _, screening_id, seats = _make_screening(svc)
        result = _book_one(svc, screening_id, seats)
        booking_id = svc.get_booking_by_ref(result["booking_ref"])["id"]
        svc.record_payment(booking_id, "Cash", 42.0)
        fetched = svc.get_booking_by_ref(result["booking_ref"])
        assert fetched["payment_status"] == "paid"
        assert fetched["payment_method"] == "Cash"
        assert fetched["total_amount"] == 42.0

    def test_refund_booking_returns_amount_and_cancels(self, svc):
        _, screening_id, seats = _make_screening(svc)
        seat_id = seats[0][0]
        result = _book_one(svc, screening_id, seats, price=18.0)
        booking_id = svc.get_booking_by_ref(result["booking_ref"])["id"]
        amount = svc.refund_booking(booking_id)
        assert amount == pytest.approx(18.0)
        fetched = svc.get_booking_by_ref(result["booking_ref"])
        assert fetched["payment_status"] == "refunded"
        assert fetched["status"] == "cancelled"
        after = {s[0]: s[5] for s in svc.get_seats_for_screening(screening_id)}
        assert after[seat_id] == "available"

    def test_refund_missing_booking_raises(self, svc):
        with pytest.raises(ValueError, match="not found"):
            svc.refund_booking(99999)


# ---------------------------------------------------------------------------
# Report aggregations
# ---------------------------------------------------------------------------


class TestReports:
    def _book_today(self, svc):
        """Create a screening dated today and book a seat so date-range
        report filters (which key off booking_time = now) include it."""
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        movie_id = svc.add_movie("Report Movie", 100)
        screening_id = svc.add_screening(movie_id, 1, f"{today} 19:00", 20.0)
        seats = svc.get_seats_for_screening(screening_id)
        _book_one(svc, screening_id, seats, price=20.0)
        return today, movie_id, screening_id

    def test_sales_summary(self, svc):
        today, _, _ = self._book_today(svc)
        summary = svc.report_sales_summary(today, today)
        assert summary["total_bookings"] == 1
        assert summary["active_bookings"] == 1
        assert summary["tickets_sold"] == 1
        assert summary["total_revenue"] == pytest.approx(20.0)

    def test_sales_summary_empty_range(self, svc):
        summary = svc.report_sales_summary("1999-01-01", "1999-12-31")
        assert summary["total_bookings"] == 0
        assert summary["total_revenue"] == 0

    def test_daily_sales(self, svc):
        today, _, _ = self._book_today(svc)
        rows = svc.report_daily_sales(today, today)
        assert len(rows) == 1
        assert rows[0][0] == today
        assert rows[0][1] == 1

    def test_revenue_by_movie(self, svc):
        today, _, _ = self._book_today(svc)
        rows = svc.report_revenue_by_movie(today, today)
        titles = {r[0] for r in rows}
        assert "Report Movie" in titles

    def test_occupancy_report(self, svc):
        today, _, _ = self._book_today(svc)
        rows = svc.report_occupancy(today, today)
        assert len(rows) == 1
        entry = rows[0]
        assert entry["movie"] == "Report Movie"
        assert entry["booked"] == 1
        assert entry["total"] == 96
        assert entry["occupancy_pct"] == pytest.approx(round(1 / 96 * 100, 1))

    def test_payment_methods_report(self, svc):
        today, _, _ = self._book_today(svc)
        rows = svc.report_payment_methods(today, today)
        # Default payment method is 'Credit Card'.
        assert any(r[0] == "Credit Card" and r[1] == 1 for r in rows)

    def test_booking_statuses_report(self, svc):
        today, _, _ = self._book_today(svc)
        rows = dict(svc.report_booking_statuses(today, today))
        assert rows.get("active") == 1


# ---------------------------------------------------------------------------
# Gift cards
# ---------------------------------------------------------------------------


class TestGiftCards:
    def test_create_gift_card_returns_code(self, svc):
        code = svc.create_gift_card(50.0, purchaser_name="Buyer")
        assert code.startswith("GC-")
        assert len(code) == 13  # "GC-" + 10 chars

    def test_gift_card_balance(self, svc):
        code = svc.create_gift_card(75.0)
        assert svc.get_gift_card_balance(code) == pytest.approx(75.0)

    def test_unknown_gift_card_balance_none(self, svc):
        assert svc.get_gift_card_balance("GC-NONEXIST") is None

    def test_expired_gift_card_balance_none(self, svc):
        code = svc.create_gift_card(20.0, expiry_days=-1)
        assert svc.get_gift_card_balance(code) is None


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_log_audit_persists_entry(self, svc, db_path):
        svc.log_audit(
            "staff",
            "delete_movie",
            user_id=1,
            user_name="admin",
            entity_type="movie",
            entity_id=5,
        )
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT user_type, action, entity_type, entity_id FROM audit_log"
            ).fetchall()
        finally:
            conn.close()
        assert rows == [("staff", "delete_movie", "movie", 5)]
