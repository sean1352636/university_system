"""Textbook service — database operations and business logic for the textbook store."""

import logging

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


def init_db():
    """Create textbook tables and seed sample data when the table is empty."""
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS textbooks (
            textbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn TEXT DEFAULT '',
            title TEXT NOT NULL,
            author TEXT DEFAULT '',
            edition TEXT DEFAULT '',
            publisher TEXT DEFAULT '',
            year INTEGER,
            module_code TEXT DEFAULT '',
            required INTEGER DEFAULT 1,
            price REAL DEFAULT 0.0,
            description TEXT DEFAULT ''
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS textbook_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            textbook_id INTEGER,
            seller_id TEXT NOT NULL,
            condition TEXT DEFAULT 'good',
            price REAL NOT NULL,
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'available',
            listed_date TEXT DEFAULT (date('now')),
            FOREIGN KEY (textbook_id) REFERENCES textbooks(textbook_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS textbook_orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER,
            buyer_id TEXT NOT NULL,
            seller_id TEXT NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            order_date TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (listing_id) REFERENCES textbook_listings(listing_id)
        )""")
        # Seed sample textbooks when empty
        count = conn.execute("SELECT COUNT(*) FROM textbooks").fetchone()[0]
        if count == 0:
            samples = [
                ("978-0132350884", "Clean Code", "Robert C. Martin", "1st", "Prentice Hall", 2008, "CS101", 1, 35.99, "A Handbook of Agile Software Craftsmanship"),
                ("978-0201633610", "Design Patterns", "Gang of Four", "1st", "Addison-Wesley", 1994, "CS201", 1, 45.00, "Elements of Reusable Object-Oriented Software"),
                ("978-0262033848", "Introduction to Algorithms", "Cormen et al.", "3rd", "MIT Press", 2009, "CS102", 1, 80.00, "Comprehensive algorithms textbook"),
                ("978-0134685991", "Effective Java", "Joshua Bloch", "3rd", "Addison-Wesley", 2018, "CS201", 0, 40.00, "Best practices for Java"),
                ("978-1449355739", "Learning Python", "Mark Lutz", "5th", "O'Reilly", 2013, "CS101", 0, 55.00, "Comprehensive Python guide"),
                ("978-0321125217", "Domain-Driven Design", "Eric Evans", "1st", "Addison-Wesley", 2003, "CS301", 1, 50.00, "Tackling Complexity in the Heart of Software"),
                ("978-0596517748", "JavaScript: The Good Parts", "Douglas Crockford", "1st", "O'Reilly", 2008, "WEB101", 0, 25.00, "Essential JavaScript concepts"),
                ("978-1491950357", "Designing Data-Intensive Applications", "Martin Kleppmann", "1st", "O'Reilly", 2017, "DS201", 1, 45.00, "Big ideas behind reliable systems"),
            ]
            for s in samples:
                conn.execute(
                    "INSERT INTO textbooks (isbn, title, author, edition, publisher, year, module_code, required, price, description) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    s,
                )
            conn.commit()


# ---------------------------------------------------------------------------
# Textbook queries
# ---------------------------------------------------------------------------

def search_textbooks(search_term="", module_code=None):
    """Search the textbook catalogue.

    Parameters
    ----------
    search_term : str
        Free-text search across title, author, and ISBN (LIKE match).
    module_code : str or None
        Pass ``None`` or ``"All"`` for no module filter.

    Returns
    -------
    list[sqlite3.Row]
    """
    from education_system.systems.university.infrastructure.sql_safety import escape_like

    with get_connection() as conn:
        query = "SELECT * FROM textbooks WHERE 1=1"
        params = []
        if search_term:
            query += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
            s = f"%{escape_like(search_term)}%"
            params.extend([s, s, s])
        if module_code and module_code != "All":
            query += " AND module_code = ?"
            params.append(module_code)
        query += " ORDER BY title"
        return conn.execute(query, params).fetchall()


def get_all_module_codes():
    """Return a sorted list of distinct module codes present in the catalogue."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT module_code FROM textbooks WHERE module_code != '' ORDER BY module_code"
        ).fetchall()
        return [r[0] for r in rows]


def get_textbook(textbook_id):
    """Return the textbook row for the given id, or ``None``."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM textbooks WHERE textbook_id = ?", (textbook_id,)
        ).fetchone()


def get_course_textbooks(student_id):
    """Return textbooks required/recommended for the student's enrolled modules.

    Each row includes a ``used_count`` column indicating how many used copies
    are currently available on the exchange.
    """
    with get_connection() as conn:
        return conn.execute(
            """SELECT t.*,
                      (SELECT COUNT(*) FROM textbook_listings tl
                       WHERE tl.textbook_id = t.textbook_id AND tl.status = 'available') as used_count
               FROM textbooks t
               WHERE t.module_code IN (SELECT module_code FROM student_modules WHERE student_id = ?)
               ORDER BY t.required DESC, t.module_code, t.title""",
            (student_id,),
        ).fetchall()


def get_all_textbooks_for_combo():
    """Return a list of (textbook_id, title, author) for all textbooks."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT textbook_id, title, author FROM textbooks ORDER BY title"
        ).fetchall()


# ---------------------------------------------------------------------------
# Used-book exchange (listings)
# ---------------------------------------------------------------------------

def get_available_listings(textbook_id=None):
    """Return available used-book listings, optionally filtered to a single textbook.

    Parameters
    ----------
    textbook_id : int or None
        If given, only listings for that textbook are returned (sorted by price).
        Otherwise all available listings are returned (sorted by date desc).
    """
    with get_connection() as conn:
        if textbook_id is not None:
            return conn.execute(
                """SELECT tl.*, t.title FROM textbook_listings tl
                   JOIN textbooks t ON tl.textbook_id = t.textbook_id
                   WHERE tl.textbook_id = ? AND tl.status = 'available'
                   ORDER BY tl.price ASC""",
                (textbook_id,),
            ).fetchall()
        return conn.execute(
            """SELECT tl.*, t.title FROM textbook_listings tl
               JOIN textbooks t ON tl.textbook_id = t.textbook_id
               WHERE tl.status = 'available'
               ORDER BY tl.listed_date DESC"""
        ).fetchall()


def create_listing(textbook_id, seller_id, condition, price, notes=""):
    """List a textbook for sale on the exchange.

    Parameters
    ----------
    textbook_id : int
    seller_id : str
    condition : str
        One of ``"like_new"``, ``"good"``, ``"fair"``, ``"poor"``.
    price : float
    notes : str
    """
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO textbook_listings
                (textbook_id, seller_id, condition, price, notes, status)
                VALUES (?, ?, ?, ?, ?, 'available')""",
            (textbook_id, seller_id, condition, float(price), notes),
        )
        conn.commit()


def find_textbook_by_isbn(isbn):
    """Return the textbook_id for the given ISBN, or ``None``."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT textbook_id FROM textbooks WHERE isbn = ?", (isbn,)
        ).fetchone()
        return row["textbook_id"] if row else None


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def get_orders(user_id):
    """Return orders where *user_id* is the buyer or the seller."""
    with get_connection() as conn:
        return conn.execute(
            """SELECT o.*, t.title FROM textbook_orders o
               JOIN textbook_listings tl ON o.listing_id = tl.listing_id
               JOIN textbooks t ON tl.textbook_id = t.textbook_id
               WHERE o.buyer_id = ? OR o.seller_id = ?
               ORDER BY o.order_date DESC""",
            (user_id, user_id),
        ).fetchall()


def buy_listing(listing_id, buyer_id):
    """Purchase a used-book listing.

    Creates an order, marks the listing as sold, and commits.

    Raises
    ------
    ValueError
        If the listing is unavailable or the buyer is the seller.
    """
    with get_connection() as conn:
        listing = conn.execute(
            "SELECT * FROM textbook_listings WHERE listing_id = ?", (listing_id,)
        ).fetchone()
        if not listing or listing["status"] != "available":
            raise ValueError("Listing is no longer available.")
        if listing["seller_id"] == buyer_id:
            raise ValueError("You cannot buy your own listing.")

        conn.execute(
            "INSERT INTO textbook_orders (listing_id, buyer_id, seller_id, price, status) VALUES (?, ?, ?, ?, 'pending')",
            (listing_id, buyer_id, listing["seller_id"], listing["price"]),
        )
        conn.execute(
            "UPDATE textbook_listings SET status='sold' WHERE listing_id=?",
            (listing_id,),
        )
        conn.commit()
