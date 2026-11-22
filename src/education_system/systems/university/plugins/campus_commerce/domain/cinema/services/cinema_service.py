"""
Cinema Booking System - Service Layer

Extracts all database and business-logic operations from the GUI code so they
can be reused by CLI, REST API, tests, and other interfaces without depending
on tkinter.

Uses the same database file and connection pattern as the existing GUI code.
"""
import logging

logger = logging.getLogger(__name__)

import hashlib
import hmac
import json
import os
import random
import secrets

import bcrypt
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.sql_safety import (
    escape_like,
    validate_identifier,
    validate_table_name,
)

# Database path - mirrors database.py
try:
    from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

    DB_FILE = str(UNIVERSITY_DEFAULT_DB_PATH)
except ImportError:
    DB_FILE = os.path.join(
        os.path.dirname(__file__), "../../../../data/db_files/student_records.db"
    )

# Constants from the GUI constants module
from education_system.systems.university.plugins.campus_commerce.interfaces.gui.cinema.cinema_gui.constants import (
    MEMBERSHIP_TIERS,
    TICKET_TYPES,
    SNACKS_MENU,
    SEAT_TYPES,
    STAFF_ROLES,
    SEASON_PASSES,
)


def _get_connection(db_file: str = None) -> sqlite3.Connection:
    """Open a connection to the cinema database."""
    return sqlite3.connect(db_file or DB_FILE)


def _generate_booking_ref() -> str:
    """Generate a unique 8-character booking reference."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


# ---------------------------------------------------------------------------
# Finance posting (shared by the cinema GUI and both CLIs)
# ---------------------------------------------------------------------------

FINANCE_SOURCE = "Cinema"
_STUDENT_ACCOUNT_METHODS = {"student account", "student_account", "finance_account", "student finance account"}


def is_student_account_method(payment_method: Optional[str]) -> bool:
    """True when a payment/refund method means the student's finance account."""
    return (payment_method or "").strip().lower() in _STUDENT_ACCOUNT_METHODS


def post_booking_payment_to_finance(
    booking_ref: str,
    amount: float,
    payment_method: str,
    *,
    student_id: Optional[str] = None,
    description: Optional[str] = None,
    processed_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Post a cinema booking payment to Finance. Never raises.

    Student-account bookings are debited from the finance account (which
    records its own payments row) — call this *before* writing the booking
    so an insufficient balance blocks the sale. Every other method is
    recorded as a completed payment after the booking is written. Returns
    ``{'success', 'payment_id', 'message'}``; a failed cash/card posting is
    logged and reported but must not roll back the booking.
    """
    description = description or f"Cinema booking {booking_ref}"
    try:
        from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
            process_student_finance_account_payment,
            record_payment_to_finance,
        )

        if is_student_account_method(payment_method):
            if not student_id:
                return {"success": False, "payment_id": None,
                        "message": "Student ID required for student account payment"}
            result = process_student_finance_account_payment(
                student_id=student_id,
                amount=amount,
                description=description,
                transaction_source=FINANCE_SOURCE,
                transaction_ref=booking_ref,
                processed_by=processed_by or "System",
            )
            if not result.get("success"):
                logger.warning("Cinema booking %s: student account payment not posted: %s",
                               booking_ref, result.get("message"))
            return {"success": bool(result.get("success")),
                    "payment_id": result.get("payment_id"),
                    "message": result.get("message", "")}

        payment_id = record_payment_to_finance(
            student_id=student_id or "GUEST",
            amount=amount,
            payment_method=payment_method,
            transaction_source=FINANCE_SOURCE,
            transaction_ref=booking_ref,
            currency="GBP",
            status="completed",
            notes=description,
            created_by=processed_by,
        )
        if payment_id is None:
            logger.warning("Cinema booking %s: payment not posted to finance", booking_ref)
            return {"success": False, "payment_id": None, "message": "Finance posting failed"}
        return {"success": True, "payment_id": payment_id, "message": ""}
    except Exception as e:
        logger.exception("Cinema booking %s: finance posting failed", booking_ref)
        return {"success": False, "payment_id": None, "message": str(e)}


def post_booking_refund_to_finance(
    booking_ref: str,
    amount: float,
    refund_method: str,
    *,
    student_id: Optional[str] = None,
    customer_email: Optional[str] = None,
    reason: str = "Cinema booking refund",
    processed_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Post a cinema refund to Finance. Never raises.

    Writes the ``unified_refunds`` row (and GL journal) through
    ``record_refund_to_finance``; a ``student_account`` refund also credits
    the student's finance account. Returns ``{'success', 'refund_id',
    'refund_ref', 'new_balance', 'message'}``.
    """
    refund_ref = f"REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    out: Dict[str, Any] = {"success": False, "refund_id": None,
                           "refund_ref": f"{FINANCE_SOURCE.upper()}-{refund_ref}",
                           "new_balance": None, "message": ""}
    try:
        from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
            ensure_student_finance_account_exists,
            record_refund_to_finance,
            top_up_student_finance_account,
        )

        to_student_account = is_student_account_method(refund_method)
        if to_student_account and not student_id:
            out["message"] = "Student ID required for student account refund"
            return out

        refund_id = record_refund_to_finance(
            student_id=student_id,
            refund_amount=amount,
            original_payment_id=None,
            refund_reason=reason,
            refund_type="full",
            transaction_source=FINANCE_SOURCE,
            transaction_ref=refund_ref,
            refund_method="student_account" if to_student_account else refund_method,
            requested_by=processed_by,
            notes=f"Booking {booking_ref}" + (f"; customer {customer_email}" if customer_email else ""),
        )
        if refund_id is None:
            logger.warning("Cinema booking %s: refund not posted to finance", booking_ref)
            out["message"] = "Finance refund posting failed"
            return out
        out["refund_id"] = refund_id

        if to_student_account:
            ensure_student_finance_account_exists(student_id)
            topup = top_up_student_finance_account(
                student_id=student_id,
                amount=amount,
                payment_method="cinema_refund",
                processed_by=processed_by or "System",
                description=f"Cinema refund - {out['refund_ref']}",
            )
            if not topup.get("success"):
                logger.error("Cinema refund %s recorded but student account %s not credited: %s",
                             out["refund_ref"], student_id, topup.get("message"))
                out["message"] = topup.get("message", "Student account credit failed")
                return out
            out["new_balance"] = topup.get("new_balance")

        out["success"] = True
        return out
    except Exception as e:
        logger.exception("Cinema booking %s: refund posting failed", booking_ref)
        out["message"] = str(e)
        return out


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------


class CinemaService:
    """Stateless service that wraps all cinema business-logic operations.

    Every public method opens and closes its own database connection so callers
    never need to manage connections themselves.  An optional *db_file* can be
    passed to the constructor for testing against an alternative database.
    """

    def __init__(self, db_file: str = None):
        self.db_file = db_file or DB_FILE

    def _conn(self) -> sqlite3.Connection:
        return _get_connection(self.db_file)

    # ------------------------------------------------------------------
    # Database initialisation (mirrors database.py init_database)
    # ------------------------------------------------------------------

    def init_cinema_db(self) -> None:
        """Create all cinema tables if they do not already exist and seed
        sample data when the tables are empty.  Identical to
        ``database.init_database`` but callable without a GUI."""
        from education_system.systems.university.plugins.campus_commerce.interfaces.gui.cinema.cinema_gui.database import (
            init_database,
        )

        init_database()

    # ==================================================================
    # Movie CRUD
    # ==================================================================

    def add_movie(
        self,
        title: str,
        duration: int,
        genre: str = None,
        rating: str = None,
        director: str = None,
        description: str = None,
        release_date: str = None,
        poster_url: str = None,
    ) -> int:
        """Insert a new movie and return its id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO movies
                    (title, duration, genre, rating, director, description,
                     release_date, poster_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, duration, genre, rating, director, description,
                 release_date, poster_url),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def list_movies(self, active_only: bool = True) -> List[Tuple]:
        """Return movies ordered by id descending.

        Each row: (id, title, duration, genre, rating, director, status).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            if active_only:
                cursor.execute(
                    """
                    SELECT id, title, duration, genre, rating, director,
                           COALESCE(status, 'active')
                    FROM movies
                    WHERE status = 'active' OR status IS NULL
                    ORDER BY id DESC
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT id, title, duration, genre, rating, director,
                           COALESCE(status, 'active')
                    FROM movies ORDER BY id DESC
                    """
                )
            return cursor.fetchall()
        finally:
            conn.close()

    def get_movie(self, movie_id: int) -> Optional[Tuple]:
        """Return the full row for a single movie, or *None*."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
            return cursor.fetchone()
        finally:
            conn.close()

    def update_movie(
        self,
        movie_id: int,
        title: str = None,
        duration: int = None,
        genre: str = None,
        rating: str = None,
        director: str = None,
        description: str = None,
        status: str = None,
    ) -> bool:
        """Update fields on an existing movie.  Only non-None arguments are
        written.  Returns *True* if a row was updated."""
        fields: List[str] = []
        values: List[Any] = []
        for col, val in [
            ("title", title),
            ("duration", duration),
            ("genre", genre),
            ("rating", rating),
            ("director", director),
            ("description", description),
            ("status", status),
        ]:
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)
        if not fields:
            return False
        values.append(movie_id)
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE movies SET {', '.join(fields)} WHERE id = ?", values
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_movie(self, movie_id: int) -> bool:
        """Delete a movie and its associated screenings.  Returns *True* if
        the movie existed."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            # Remove dependents from the bottom of the FK chain upward
            # (booked_seats -> bookings/seats -> screenings -> movie).
            screening_subq = "SELECT id FROM screenings WHERE movie_id = ?"
            # db-audit: ignore[DBW001] - string literal
            cursor.execute(
                f"DELETE FROM booked_seats WHERE seat_id IN "
                f"(SELECT id FROM seats WHERE screening_id IN ({screening_subq}))",
                (movie_id,),
            )
            # db-audit: ignore[DBW001] - string literal
            cursor.execute(
                f"DELETE FROM booked_seats WHERE booking_id IN "
                f"(SELECT id FROM bookings WHERE screening_id IN ({screening_subq}))",
                (movie_id,),
            )
            # db-audit: ignore[DBW001] - string literal
            cursor.execute(
                f"DELETE FROM bookings WHERE screening_id IN ({screening_subq})",
                (movie_id,),
            )
            # db-audit: ignore[DBW001] - string literal
            cursor.execute(
                f"DELETE FROM seats WHERE screening_id IN ({screening_subq})",
                (movie_id,),
            )
            cursor.execute(
                "DELETE FROM screenings WHERE movie_id = ?", (movie_id,)
            )
            cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
            existed = cursor.rowcount > 0
            conn.commit()
            return existed
        finally:
            conn.close()

    # ==================================================================
    # Screening management
    # ==================================================================

    def add_screening(
        self,
        movie_id: int,
        screen_number: int,
        show_time: str,
        price: float,
        rows: List[str] = None,
        seats_per_row: int = 12,
        event_type: str = None,
    ) -> int:
        """Create a screening and generate its seat grid.  Returns the
        screening id.

        *rows* defaults to ``['A'..'H']`` and *seats_per_row* to 12, matching
        the existing GUI behaviour.
        """
        if rows is None:
            rows = ["A", "B", "C", "D", "E", "F", "G", "H"]
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO screenings (movie_id, screen_number, show_time, price)
                VALUES (?, ?, ?, ?)
                """,
                (movie_id, screen_number, show_time, price),
            )
            screening_id = cursor.lastrowid
            for row in rows:
                for seat_num in range(1, seats_per_row + 1):
                    seat_type = "vip" if row in ["A", "B"] else "standard"
                    cursor.execute(
                        """
                        INSERT INTO seats
                            (screening_id, row, seat_number, seat_type, status)
                        VALUES (?, ?, ?, ?, 'available')
                        """,
                        (screening_id, row, seat_num, seat_type),
                    )
            conn.commit()

            # Cross-domain: a screening tagged as a movie-night
            # publishes itself onto the academic calendar via the SU
            # bus. Same plumbing SU events / H&S drills already use,
            # so it shows up everywhere subscribed to
            # EVENT_CALENDAR_CHANGED.
            if event_type and event_type.lower() == "movie_night":
                try:
                    cursor.execute(
                        "SELECT title FROM movies WHERE id = ?",
                        (movie_id,),
                    )
                    row = cursor.fetchone()
                    title = row[0] if row else f"Movie #{movie_id}"
                    from education_system.systems.university.services.bus import (
                        student_union_bus,
                    )
                    student_union_bus.publish_event(
                        name=f"Movie night: {title}",
                        when=show_time,
                        location=f"Cinema screen {screen_number}",
                        description="Cinema movie night — tickets at door",
                    )
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            return screening_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_screenings(
        self,
        movie_id: int = None,
        limit: int = 100,
    ) -> List[Tuple]:
        """Return screenings with booking counts.

        Each row: (screening_id, movie_title, screen_number, show_time, price,
                    booked_seats, available_seats, status).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = """
                SELECT s.id, m.title, s.screen_number, s.show_time, s.price,
                       (SELECT COUNT(*) FROM seats
                        WHERE screening_id = s.id AND status = 'booked'),
                       (SELECT COUNT(*) FROM seats
                        WHERE screening_id = s.id AND status = 'available'),
                       COALESCE(s.status, 'active')
                FROM screenings s
                JOIN movies m ON s.movie_id = m.id
            """
            params: List[Any] = []
            if movie_id is not None:
                sql += " WHERE s.movie_id = ?"
                params.append(movie_id)
            sql += " ORDER BY s.show_time DESC LIMIT ?"
            params.append(limit)
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            conn.close()

    def get_screening(self, screening_id: int) -> Optional[Tuple]:
        """Return the full row for a single screening."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM screenings WHERE id = ?", (screening_id,)
            )
            return cursor.fetchone()
        finally:
            conn.close()

    def update_screening(
        self,
        screening_id: int,
        screen_number: int = None,
        price: float = None,
        status: str = None,
    ) -> bool:
        """Update screening fields.  Returns *True* if a row was updated."""
        fields: List[str] = []
        values: List[Any] = []
        for col, val in [
            ("screen_number", screen_number),
            ("price", price),
            ("status", status),
        ]:
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)
        if not fields:
            return False
        values.append(screening_id)
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE screenings SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def cancel_screening(self, screening_id: int) -> None:
        """Cancel a screening, release its seats, and cancel all bookings."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE screenings SET status = 'cancelled' WHERE id = ?",
                (screening_id,),
            )
            cursor.execute(
                "UPDATE seats SET status = 'available' WHERE screening_id = ?",
                (screening_id,),
            )
            cursor.execute(
                "UPDATE bookings SET status = 'cancelled' WHERE screening_id = ?",
                (screening_id,),
            )
            conn.commit()
        finally:
            conn.close()

    # ==================================================================
    # Seat queries
    # ==================================================================

    def get_seats_for_screening(self, screening_id: int) -> List[Tuple]:
        """Return all seats for a screening.

        Each row: (id, screening_id, row, seat_number, seat_type, status).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, screening_id, row, seat_number, seat_type, status
                FROM seats
                WHERE screening_id = ?
                ORDER BY row, seat_number
                """,
                (screening_id,),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    # ==================================================================
    # Booking operations
    # ==================================================================

    def create_booking(
        self,
        screening_id: int,
        customer_name: str,
        seat_ids: List[int],
        ticket_types: Dict[int, Tuple[str, float]],
        customer_email: str = None,
        customer_phone: str = None,
        payment_method: str = "Credit Card",
        promo_code: str = None,
        snacks: Dict[str, int] = None,
        student_id: str = None,
        processed_by: str = None,
    ) -> Dict[str, Any]:
        """Create a complete booking and post the payment to Finance.

        *ticket_types* maps ``seat_id -> (type_name, price)``.
        *snacks* maps ``item_name -> quantity``.

        Returns a dict with ``booking_ref``, ``booking_id``, ``total_amount``,
        ``discount_amount``, and ``seats`` (list of ``(row, seat_number)``).
        """
        subtotal = sum(price for _, price in ticket_types.values())
        snacks_total = (
            sum(SNACKS_MENU.get(item, 0) * qty for item, qty in snacks.items())
            if snacks
            else 0.0
        )
        discount_amount = 0.0
        applied_promo_id = None

        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Validate promo code
            if promo_code:
                cursor.execute(
                    """
                    SELECT id, discount_type, discount_value, min_purchase
                    FROM promo_codes
                    WHERE code = ? AND status = 'active'
                      AND (valid_from IS NULL OR valid_from <= date('now'))
                      AND (valid_until IS NULL OR valid_until >= date('now'))
                      AND (max_uses IS NULL OR times_used < max_uses)
                    """,
                    (promo_code.upper(),),
                )
                promo = cursor.fetchone()
                if promo:
                    promo_id, discount_type, discount_value, min_purchase = promo
                    if subtotal + snacks_total >= min_purchase:
                        if discount_type == "percentage":
                            discount_amount = (subtotal + snacks_total) * (
                                discount_value / 100
                            )
                        else:
                            discount_amount = discount_value
                        applied_promo_id = promo_id

            total_amount = subtotal + snacks_total - discount_amount

            # Cross-domain: stack institution-wide SU/tier discounts on
            # top of any cinema-local promo code, when we know who's
            # booking. ``commerce_bus.price_for`` returns final price +
            # breakdown; we treat the delta as additional discount.
            if student_id and total_amount > 0:
                try:
                    from education_system.systems.university.services.bus import (
                        commerce_bus,
                    )
                    final, brk = commerce_bus.price_for(
                        student_id, total_amount, source="cinema",
                    )
                    extra = max(0.0, total_amount - final)
                    if extra > 0:
                        discount_amount += extra
                        total_amount = final
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            booking_ref = _generate_booking_ref()

            # Student-account bookings are debited before the booking is
            # written so an insufficient balance blocks the sale.
            payment_id = None
            charged_to_account = False
            if is_student_account_method(payment_method) and total_amount > 0:
                charge = post_booking_payment_to_finance(
                    booking_ref, total_amount, payment_method,
                    student_id=student_id, processed_by=processed_by,
                )
                if not charge["success"]:
                    raise ValueError(
                        f"Student account payment failed: {charge['message']}"
                    )
                payment_id = charge["payment_id"]
                charged_to_account = True

            ticket_types_json = json.dumps(
                {str(k): v for k, v in ticket_types.items()}
            )
            snacks_json = json.dumps(snacks) if snacks else None

            cursor.execute(
                """
                INSERT INTO bookings
                    (booking_ref, customer_name, customer_email, customer_phone,
                     screening_id, ticket_types, subtotal, discount_amount,
                     promo_code, snacks_total, snacks_items, total_amount,
                     payment_status, payment_method, booking_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'paid', ?, ?)
                """,
                (
                    booking_ref,
                    customer_name,
                    customer_email,
                    customer_phone,
                    screening_id,
                    ticket_types_json,
                    subtotal,
                    discount_amount,
                    promo_code.upper() if promo_code else None,
                    snacks_total,
                    snacks_json,
                    total_amount,
                    payment_method,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            booking_id = cursor.lastrowid

            # Book seats
            for seat_id in seat_ids:
                cursor.execute(
                    "UPDATE seats SET status = 'booked' WHERE id = ?",
                    (seat_id,),
                )
                tt = ticket_types.get(seat_id, ("Adult", 0))
                cursor.execute(
                    "INSERT INTO booked_seats (booking_id, seat_id, ticket_type) "
                    "VALUES (?, ?, ?)",
                    (booking_id, seat_id, tt[0]),
                )

            # Update promo usage
            if applied_promo_id:
                cursor.execute(
                    "UPDATE promo_codes SET times_used = times_used + 1 "
                    "WHERE id = ?",
                    (applied_promo_id,),
                )

            conn.commit()

            # Fetch booked seat details
            cursor.execute(
                """
                SELECT se.row, se.seat_number
                FROM booked_seats bs
                JOIN seats se ON bs.seat_id = se.id
                WHERE bs.booking_id = ?
                """,
                (booking_id,),
            )
            seat_list = cursor.fetchall()

            # Cross-domain: post the sale through the unified bus so
            # the Finance GUI ledger and loyalty tier track this
            # booking. Walk-ins (no student_id) are skipped.
            sale_meta: Dict[str, Any] = {}
            if student_id and total_amount > 0:
                try:
                    from education_system.systems.university.services.bus import (
                        commerce_bus,
                    )
                    sale_meta = commerce_bus.post_sale(
                        student_id,
                        source="cinema",
                        amount=total_amount,
                        description=f"Cinema booking {booking_ref}",
                        reference_id=booking_ref,
                    )
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            # Cash/card: record the completed payment now the booking exists.
            if not charged_to_account and total_amount > 0:
                payment_id = post_booking_payment_to_finance(
                    booking_ref, total_amount, payment_method,
                    student_id=student_id, processed_by=processed_by,
                )["payment_id"]

            return {
                "booking_ref": booking_ref,
                "booking_id": booking_id,
                "total_amount": total_amount,
                "discount_amount": discount_amount,
                "seats": seat_list,
                "loyalty": sale_meta,
                "payment_id": payment_id,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def cancel_booking(self, booking_id: int) -> str:
        """Cancel a booking and release its seats.  Returns the booking ref."""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT booking_ref, status FROM bookings WHERE id = ?",
                (booking_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Booking {booking_id} not found")
            booking_ref, current_status = row
            if current_status == "cancelled":
                raise ValueError(f"Booking {booking_ref} is already cancelled")

            cursor.execute(
                "SELECT seat_id FROM booked_seats WHERE booking_id = ?",
                (booking_id,),
            )
            for (seat_id,) in cursor.fetchall():
                cursor.execute(
                    "UPDATE seats SET status = 'available' WHERE id = ?",
                    (seat_id,),
                )

            cursor.execute(
                "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
                (booking_id,),
            )
            conn.commit()
            return booking_ref
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def reactivate_booking(self, booking_id: int) -> str:
        """Reactivate a cancelled booking if its seats are still free.

        Returns the booking ref.  Raises ``ValueError`` if seats are taken.
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT booking_ref, status FROM bookings WHERE id = ?",
                (booking_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Booking {booking_id} not found")
            booking_ref, current_status = row
            if current_status == "active":
                raise ValueError(f"Booking {booking_ref} is already active")

            cursor.execute(
                "SELECT seat_id FROM booked_seats WHERE booking_id = ?",
                (booking_id,),
            )
            seat_ids = [r[0] for r in cursor.fetchall()]

            if seat_ids:
                placeholders = ",".join("?" * len(seat_ids))
                # db-audit: ignore[DBW001] - join of placeholders
                cursor.execute(
                    "SELECT COUNT(*) FROM seats"
                    f" WHERE id IN ({placeholders}) AND status != 'available'",
                    seat_ids,
                )
                unavailable = cursor.fetchone()[0]
                if unavailable > 0:
                    raise ValueError(
                        f"{unavailable} seat(s) are no longer available"
                    )
                for seat_id in seat_ids:
                    cursor.execute(
                        "UPDATE seats SET status = 'booked' WHERE id = ?",
                        (seat_id,),
                    )

            cursor.execute(
                "UPDATE bookings SET status = 'active' WHERE id = ?",
                (booking_id,),
            )
            conn.commit()
            return booking_ref
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_booking(self, booking_id: int) -> str:
        """Permanently delete a booking and release its seats.  Returns the
        booking ref."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT booking_ref FROM bookings WHERE id = ?",
                (booking_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Booking {booking_id} not found")
            booking_ref = row[0]

            cursor.execute(
                "SELECT seat_id FROM booked_seats WHERE booking_id = ?",
                (booking_id,),
            )
            for (seat_id,) in cursor.fetchall():
                cursor.execute(
                    "UPDATE seats SET status = 'available' WHERE id = ?",
                    (seat_id,),
                )

            cursor.execute(
                "DELETE FROM booked_seats WHERE booking_id = ?", (booking_id,)
            )
            cursor.execute(
                "DELETE FROM bookings WHERE id = ?", (booking_id,)
            )
            conn.commit()
            return booking_ref
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_booking_by_ref(self, booking_ref: str) -> Optional[Dict[str, Any]]:
        """Fetch a booking with its movie, screening, and seat details."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT b.*, m.title, s.show_time, s.screen_number
                FROM bookings b
                JOIN screenings s ON b.screening_id = s.id
                JOIN movies m ON s.movie_id = m.id
                WHERE b.booking_ref = ?
                """,
                (booking_ref,),
            )
            booking = cursor.fetchone()
            if not booking:
                return None

            cursor.execute(
                """
                SELECT se.row, se.seat_number, bs.ticket_type
                FROM booked_seats bs
                JOIN seats se ON bs.seat_id = se.id
                WHERE bs.booking_id = ?
                """,
                (booking[0],),
            )
            seats = cursor.fetchall()

            return {
                "id": booking[0],
                "booking_ref": booking[1],
                "customer_name": booking[2],
                "customer_email": booking[3],
                "customer_phone": booking[4],
                "screening_id": booking[5],
                "total_amount": booking[12],
                "payment_status": booking[13],
                "payment_method": booking[14],
                "status": booking[16],
                "movie_title": booking[-3],
                "show_time": booking[-2],
                "screen_number": booking[-1],
                "seats": [
                    {"row": s[0], "seat_number": s[1], "ticket_type": s[2]}
                    for s in seats
                ],
            }
        finally:
            conn.close()

    def search_bookings(
        self,
        query: str = None,
        status: str = None,
        limit: int = 100,
    ) -> List[Tuple]:
        """Search bookings by ref, customer name, or email.

        Each row: (id, booking_ref, customer_name, customer_email,
                    movie_title, show_time, seat_count, total_amount, status).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = """
                SELECT b.id, b.booking_ref, b.customer_name, b.customer_email,
                       m.title, s.show_time,
                       (SELECT COUNT(*) FROM booked_seats WHERE booking_id = b.id),
                       b.total_amount, b.status
                FROM bookings b
                JOIN screenings s ON b.screening_id = s.id
                JOIN movies m ON s.movie_id = m.id
                WHERE 1=1
            """
            params: List[Any] = []
            if query:
                safe = f"%{escape_like(query)}%"
                sql += (
                    " AND (b.booking_ref LIKE ? OR b.customer_name LIKE ?"
                    " OR b.customer_email LIKE ?)"
                )
                params.extend([safe, safe, safe])
            if status and status != "all":
                sql += " AND b.status = ?"
                params.append(status)
            sql += " ORDER BY b.booking_time DESC LIMIT ?"
            params.append(limit)
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            conn.close()

    def update_booking(
        self,
        booking_id: int,
        customer_name: str = None,
        customer_email: str = None,
        customer_phone: str = None,
        payment_method: str = None,
        payment_status: str = None,
        notes: str = None,
    ) -> bool:
        """Update editable booking fields.  Returns *True* if a row was
        updated."""
        fields: List[str] = []
        values: List[Any] = []
        for col, val in [
            ("customer_name", customer_name),
            ("customer_email", customer_email),
            ("customer_phone", customer_phone),
            ("payment_method", payment_method),
            ("payment_status", payment_status),
            ("notes", notes),
        ]:
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)
        if not fields:
            return False
        values.append(booking_id)
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE bookings SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # Ticket / validation helpers
    # ==================================================================

    def validate_ticket(self, booking_ref: str) -> Dict[str, Any]:
        """Validate a ticket by its booking reference.

        Returns a dict with ``valid`` (bool) and booking details when valid,
        or an ``error`` message when not.
        """
        booking = self.get_booking_by_ref(booking_ref)
        if not booking:
            return {"valid": False, "error": "Booking not found"}
        if booking["status"] != "active":
            return {
                "valid": False,
                "error": f"Booking is {booking['status']}",
                "booking": booking,
            }
        if booking["payment_status"] != "paid":
            return {
                "valid": False,
                "error": f"Payment status: {booking['payment_status']}",
                "booking": booking,
            }
        return {"valid": True, "booking": booking}

    # ==================================================================
    # Customer / member management (loyalty programme)
    # ==================================================================

    def register_member(
        self,
        name: str,
        email: str,
        phone: str = None,
        birthday: str = None,
        initial_points: int = 100,
    ) -> int:
        """Register a new loyalty member.  Returns the member id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO members (name, email, phone, birthday, points, tier)
                VALUES (?, ?, ?, ?, ?, 'Bronze')
                """,
                (name, email, phone, birthday, initial_points),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def lookup_member(self, email: str) -> Optional[Tuple]:
        """Find a member by email.  Returns the full row or *None*."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM members WHERE email = ?", (email,)
            )
            return cursor.fetchone()
        finally:
            conn.close()

    def search_members(
        self, query: str = None, limit: int = 100
    ) -> List[Tuple]:
        """Search members by name or email.

        Each row: (id, name, email, tier, points, total_spent,
                    bookings_count, status).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            if query:
                safe = f"%{escape_like(query)}%"
                cursor.execute(
                    """
                    SELECT id, name, email, tier, points, total_spent,
                           bookings_count, status
                    FROM members WHERE name LIKE ? OR email LIKE ?
                    ORDER BY points DESC
                    """,
                    (safe, safe),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, name, email, tier, points, total_spent,
                           bookings_count, status
                    FROM members ORDER BY points DESC LIMIT ?
                    """,
                    (limit,),
                )
            return cursor.fetchall()
        finally:
            conn.close()

    def get_member(self, member_id: int) -> Optional[Tuple]:
        """Return full member row by id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM members WHERE id = ?", (member_id,)
            )
            return cursor.fetchone()
        finally:
            conn.close()

    def add_member_points(self, member_id: int, points: int) -> str:
        """Add loyalty points and recalculate the member's tier.

        Returns the new tier name.
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE members SET points = points + ? WHERE id = ?",
                (points, member_id),
            )
            cursor.execute(
                "SELECT points FROM members WHERE id = ?", (member_id,)
            )
            new_points = cursor.fetchone()[0]

            new_tier = "Bronze"
            for tier, info in MEMBERSHIP_TIERS.items():
                if new_points >= info["min_points"]:
                    new_tier = tier

            cursor.execute(
                "UPDATE members SET tier = ? WHERE id = ?",
                (new_tier, member_id),
            )
            conn.commit()
            return new_tier
        finally:
            conn.close()

    def update_member_loyalty(
        self, member_id: int, spent: float = 0, bookings_increment: int = 0
    ) -> None:
        """Increment total_spent and bookings_count for a member."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE members
                SET total_spent = total_spent + ?,
                    bookings_count = bookings_count + ?
                WHERE id = ?
                """,
                (spent, bookings_increment, member_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_member_discount(self, email: str) -> float:
        """Return the percentage discount for a member (0 if not found)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT tier FROM members WHERE email = ? AND status = 'active'",
                (email,),
            )
            result = cursor.fetchone()
        finally:
            conn.close()
        if result:
            return MEMBERSHIP_TIERS.get(result[0], {}).get("discount", 0)
        return 0

    def deactivate_member(self, member_id: int) -> None:
        """Set a member's status to inactive."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE members SET status = 'inactive' WHERE id = ?",
                (member_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_member_booking_history(
        self, email: str, limit: int = 10
    ) -> List[Tuple]:
        """Return recent bookings for a member by email.

        Each row: (booking_ref, movie_title, show_time, total_amount, status).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT b.booking_ref, m.title, s.show_time,
                       b.total_amount, b.status
                FROM bookings b
                JOIN screenings s ON b.screening_id = s.id
                JOIN movies m ON s.movie_id = m.id
                WHERE b.customer_email = ?
                ORDER BY b.booking_time DESC LIMIT ?
                """,
                (email, limit),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    # ==================================================================
    # Promo code management
    # ==================================================================

    def create_promo_code(
        self,
        code: str,
        discount_type: str,
        discount_value: float,
        min_purchase: float = 0,
        max_uses: int = None,
        valid_until: str = None,
    ) -> int:
        """Create a promo code.  Returns its id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO promo_codes
                    (code, discount_type, discount_value, min_purchase,
                     max_uses, valid_until)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    code.upper(),
                    discount_type,
                    discount_value,
                    min_purchase,
                    max_uses,
                    valid_until,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def validate_promo_code(self, code: str) -> Optional[Tuple]:
        """Check if a promo code is valid right now.  Returns the row or
        *None*."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM promo_codes
                WHERE code = ? AND status = 'active'
                  AND (valid_from IS NULL OR valid_from <= date('now'))
                  AND (valid_until IS NULL OR valid_until >= date('now'))
                  AND (max_uses IS NULL OR times_used < max_uses)
                """,
                (code.upper(),),
            )
            return cursor.fetchone()
        finally:
            conn.close()

    def list_promo_codes(self) -> List[Tuple]:
        """Return all promo codes ordered by id descending."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM promo_codes ORDER BY id DESC")
            return cursor.fetchall()
        finally:
            conn.close()

    def deactivate_promo_code(self, promo_id: int) -> None:
        """Set a promo code to inactive."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE promo_codes SET status = 'inactive' WHERE id = ?",
                (promo_id,),
            )
            conn.commit()
        finally:
            conn.close()

    # ==================================================================
    # Staff management
    # ==================================================================

    def add_staff(
        self,
        username: str,
        password: str,
        name: str,
        role: str,
        email: str = None,
        phone: str = None,
    ) -> int:
        """Create a new staff account with PBKDF2-hashed password.
        Returns the staff id."""
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 1_000_000, dklen=64
        )
        pw_hash = key.hex()

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO staff
                    (username, password_hash, salt, name, email, role, hire_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    pw_hash,
                    salt,
                    name,
                    email,
                    role,
                    datetime.now().strftime("%Y-%m-%d"),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def list_staff(self) -> List[Tuple]:
        """Return all staff accounts ordered by name (rows read by position
        or by column name — the column order differs between databases)."""
        conn = self._conn()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM staff ORDER BY name")
            return cursor.fetchall()
        finally:
            conn.close()

    def verify_staff_password(
        self, username: str, password: str
    ) -> Optional[Tuple]:
        """Verify a staff login.  Returns the staff row (by position or by
        column name) on success or *None*.

        Columns are read by name: ``staff`` is the shared university table,
        whose ``salt`` column was added last, so its position is not fixed.
        A salted row holds a PBKDF2 hash made by :meth:`create_staff`; an
        unsalted one holds bcrypt (``$2b$``/``$2a$``/``$2y$``) or the legacy
        unsalted PBKDF2, which is upgraded to bcrypt on success. ``'!'`` (or
        anything else) means no cinema password."""
        if not username or not password:
            return None
        conn = self._conn()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM staff WHERE username = ? AND status = 'active'",
                (username,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            staff = row
            fields = row.keys()
            stored_hash = str(row["password_hash"] or "")
            salt = row["salt"] if "salt" in fields else None
            ok = False
            if salt:
                key = hashlib.pbkdf2_hmac(
                    "sha256", password.encode(), str(salt).encode(), 1_000_000, dklen=64
                )
                ok = hmac.compare_digest(key.hex(), stored_hash)
            elif stored_hash.startswith(("$2b$", "$2a$", "$2y$")):
                try:
                    ok = bcrypt.checkpw(password.encode(), stored_hash.encode())
                except (ValueError, AttributeError):
                    ok = False
            elif len(stored_hash) == 64:
                # Legacy unsalted PBKDF2 — rehash to bcrypt on success.
                legacy_hash = hashlib.pbkdf2_hmac(
                    "sha256", password.encode(), b"legacy-cinema-salt", 100_000
                ).hex()
                if hmac.compare_digest(legacy_hash, stored_hash):
                    ok = True
                    cursor.execute(
                        "UPDATE staff SET password_hash = ? WHERE id = ?",
                        (bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                         row["id"]),
                    )
            if not ok:
                return None
            cursor.execute(
                "UPDATE staff SET last_login = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["id"]),
            )
            conn.commit()
            return staff
        finally:
            conn.close()

    # ==================================================================
    # Payment / refund helpers
    # ==================================================================

    def record_payment(
        self, booking_id: int, payment_method: str, amount: float
    ) -> None:
        """Mark a booking as paid."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE bookings
                SET payment_status = 'paid', payment_method = ?, total_amount = ?
                WHERE id = ?
                """,
                (payment_method, amount, booking_id),
            )
            conn.commit()
        finally:
            conn.close()

    def refund_booking(
        self,
        booking_id: int,
        refund_method: str = "original_payment_method",
        student_id: str = None,
        processed_by: str = None,
    ) -> float:
        """Refund a booking: set payment_status to 'refunded' and cancel.

        The refund is posted to Finance via
        :func:`post_booking_refund_to_finance` once the local update commits
        (a ``student_account`` refund also credits the finance account).
        Returns the refunded amount.
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT total_amount, booking_ref, customer_email FROM bookings WHERE id = ?",
                (booking_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Booking {booking_id} not found")
            amount, booking_ref, customer_email = row

            cursor.execute(
                "UPDATE bookings SET payment_status = 'refunded', "
                "status = 'cancelled' WHERE id = ?",
                (booking_id,),
            )

            # Release seats
            cursor.execute(
                "SELECT seat_id FROM booked_seats WHERE booking_id = ?",
                (booking_id,),
            )
            for (seat_id,) in cursor.fetchall():
                cursor.execute(
                    "UPDATE seats SET status = 'available' WHERE id = ?",
                    (seat_id,),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        if amount and amount > 0:
            post_booking_refund_to_finance(
                booking_ref, amount, refund_method,
                student_id=student_id, customer_email=customer_email,
                processed_by=processed_by,
            )
        return amount

    # ==================================================================
    # Report data queries (no GUI rendering)
    # ==================================================================

    def report_sales_summary(
        self, from_date: str, to_date: str
    ) -> Dict[str, Any]:
        """Return an aggregated sales summary for the given date range.

        Keys: total_bookings, active_bookings, cancelled_bookings,
              tickets_sold, total_revenue, avg_booking_value.
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_bookings,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END),
                    COALESCE(SUM(CASE WHEN status = 'active'
                                 THEN total_amount ELSE 0 END), 0),
                    COALESCE(AVG(CASE WHEN status = 'active'
                                 THEN total_amount END), 0)
                FROM bookings
                WHERE date(booking_time) BETWEEN ? AND ?
                """,
                (from_date, to_date),
            )
            s = cursor.fetchone()

            cursor.execute(
                """
                SELECT COUNT(bs.id)
                FROM booked_seats bs
                JOIN bookings b ON bs.booking_id = b.id
                WHERE b.status = 'active'
                  AND date(b.booking_time) BETWEEN ? AND ?
                """,
                (from_date, to_date),
            )
            tickets_sold = cursor.fetchone()[0] or 0
        finally:
            conn.close()

        return {
            "total_bookings": s[0] or 0,
            "active_bookings": s[1] or 0,
            "cancelled_bookings": s[2] or 0,
            "total_revenue": s[3],
            "avg_booking_value": s[4],
            "tickets_sold": tickets_sold,
        }

    def report_daily_sales(
        self, from_date: str, to_date: str
    ) -> List[Tuple]:
        """Return daily sales data.

        Each row: (date, bookings_count, revenue).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT date(booking_time) as date,
                       COUNT(*) as bookings,
                       COALESCE(SUM(CASE WHEN status = 'active'
                                    THEN total_amount ELSE 0 END), 0)
                FROM bookings
                WHERE date(booking_time) BETWEEN ? AND ?
                GROUP BY date(booking_time)
                ORDER BY date(booking_time)
                """,
                (from_date, to_date),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def report_revenue_by_movie(
        self, from_date: str, to_date: str
    ) -> List[Tuple]:
        """Return revenue breakdown by movie.

        Each row: (movie_title, bookings_count, revenue).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.title,
                       COUNT(b.id) as bookings,
                       COALESCE(SUM(CASE WHEN b.status = 'active'
                                    THEN b.total_amount ELSE 0 END), 0)
                FROM movies m
                LEFT JOIN screenings s ON m.id = s.movie_id
                LEFT JOIN bookings b ON s.id = b.screening_id
                     AND date(b.booking_time) BETWEEN ? AND ?
                GROUP BY m.id, m.title
                ORDER BY bookings DESC
                """,
                (from_date, to_date),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def report_occupancy(
        self, from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        """Return seat occupancy stats per movie.

        Each entry: {movie, booked, available, total, occupancy_pct}.
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.title,
                       COUNT(CASE WHEN seats.status = 'booked' THEN 1 END),
                       COUNT(CASE WHEN seats.status = 'available' THEN 1 END),
                       COUNT(seats.id)
                FROM movies m
                JOIN screenings s ON m.id = s.movie_id
                JOIN seats ON s.id = seats.screening_id
                WHERE date(s.show_time) BETWEEN ? AND ?
                GROUP BY m.id, m.title
                """,
                (from_date, to_date),
            )
            results = []
            for row in cursor.fetchall():
                occ = (row[1] / row[3] * 100) if row[3] > 0 else 0
                results.append(
                    {
                        "movie": row[0],
                        "booked": row[1],
                        "available": row[2],
                        "total": row[3],
                        "occupancy_pct": round(occ, 1),
                    }
                )
            return results
        finally:
            conn.close()

    def report_payment_methods(
        self, from_date: str, to_date: str
    ) -> List[Tuple]:
        """Return payment method breakdown.

        Each row: (payment_method, count, total_revenue).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(payment_method, 'Unknown'),
                       COUNT(*),
                       COALESCE(SUM(total_amount), 0)
                FROM bookings
                WHERE status = 'active'
                  AND date(booking_time) BETWEEN ? AND ?
                GROUP BY payment_method
                ORDER BY COUNT(*) DESC
                """,
                (from_date, to_date),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def report_booking_statuses(
        self, from_date: str, to_date: str
    ) -> List[Tuple]:
        """Return booking status distribution.

        Each row: (status, count).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT status, COUNT(*)
                FROM bookings
                WHERE date(booking_time) BETWEEN ? AND ?
                GROUP BY status
                """,
                (from_date, to_date),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    # ==================================================================
    # Gift card helpers
    # ==================================================================

    def create_gift_card(
        self,
        value: float,
        purchaser_name: str = None,
        purchaser_email: str = None,
        recipient_name: str = None,
        recipient_email: str = None,
        message: str = None,
        expiry_days: int = 365,
    ) -> str:
        """Create a gift card and return its code."""
        code = "GC-" + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=10)
        )
        expiry = (datetime.now() + timedelta(days=expiry_days)).strftime(
            "%Y-%m-%d"
        )
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO gift_cards
                    (code, initial_value, current_balance, purchaser_name,
                     purchaser_email, recipient_name, recipient_email,
                     message, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    value,
                    value,
                    purchaser_name,
                    purchaser_email,
                    recipient_name,
                    recipient_email,
                    message,
                    expiry,
                ),
            )
            conn.commit()
            return code
        finally:
            conn.close()

    def get_gift_card_balance(self, code: str) -> Optional[float]:
        """Return the current balance of a gift card, or *None* if not
        found / expired / inactive."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT current_balance FROM gift_cards
                WHERE code = ? AND status = 'active'
                  AND (expiry_date IS NULL OR expiry_date >= date('now'))
                """,
                (code,),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    # ==================================================================
    # Audit log
    # ==================================================================

    def log_audit(
        self,
        user_type: str,
        action: str,
        user_id: int = None,
        user_name: str = None,
        entity_type: str = None,
        entity_id: int = None,
        old_value: str = None,
        new_value: str = None,
    ) -> None:
        """Write an entry to the cinema audit log."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_log
                    (user_type, user_id, user_name, action,
                     entity_type, record_id, old_value, new_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_type,
                    user_id,
                    user_name,
                    action,
                    entity_type,
                    entity_id,
                    old_value,
                    new_value,
                ),
            )
            conn.commit()
        finally:
            conn.close()
