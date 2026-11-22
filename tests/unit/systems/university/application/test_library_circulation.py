"""Library circulation on copies, loan rules, holds/recalls, lost items and
the services around them. In-memory database built here."""

import sqlite3
from datetime import datetime, timedelta

import pytest

from education_system.systems.university.application.library import circulation as circ
from education_system.systems.university.application.library import services

SCHEMA = [
    """CREATE TABLE books (book_id TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT,
        isbn TEXT UNIQUE, status TEXT DEFAULT 'available', barcode TEXT, location TEXT,
        quantity INTEGER DEFAULT 1, available_quantity INTEGER, purchase_price REAL,
        acquisition_cost REAL, last_updated TEXT, added_date TEXT, supplier TEXT,
        purchase_date TEXT)""",
    """CREATE TABLE book_loans (loan_id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT,
        user_id TEXT, checkout_date TEXT, due_date TEXT, return_date TEXT,
        status TEXT DEFAULT 'active', fine_amount REAL DEFAULT 0, renewal_count INTEGER DEFAULT 0,
        checkout_method TEXT, staff_id TEXT, notes TEXT, paid TEXT)""",
    """CREATE TABLE book_reservations (reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id TEXT, user_id TEXT, reservation_date TEXT, expiry_date TEXT NOT NULL,
        status TEXT, priority_order INTEGER, notification_sent INTEGER)""",
    """CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT,
        email_address TEXT, course TEXT, status TEXT, is_active INTEGER DEFAULT 1)""",
    """CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        last_name TEXT, email TEXT, role TEXT, student_id TEXT)""",
    """CREATE TABLE courses (code TEXT, name TEXT, course_code TEXT, course_name TEXT,
        level TEXT)""",
    """CREATE TABLE library_settings (setting_name TEXT PRIMARY KEY, setting_value TEXT,
        description TEXT, setting_type TEXT)""",
    """CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER,
        subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)""",
    """CREATE TABLE reading_lists (list_id INTEGER PRIMARY KEY, name TEXT)""",
    """CREATE TABLE reading_list_items (item_id INTEGER PRIMARY KEY, list_id INTEGER,
        book_id TEXT, order_index INTEGER)""",
    "CREATE TABLE modules (module_code TEXT)",
    "CREATE TABLE student_modules (student_id TEXT, module_code TEXT, status TEXT)",
    """CREATE TABLE book_requests (request_id INTEGER PRIMARY KEY, user_id TEXT, title TEXT,
        author TEXT, isbn TEXT, reason TEXT, status TEXT, priority TEXT, requested_date TEXT,
        processed_date TEXT, processed_by TEXT)""",
]
T0 = datetime(2026, 10, 1, 10, 0)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.execute("INSERT INTO books (book_id, title, author, quantity, purchase_price) "
              "VALUES ('B1', 'Algorithms', 'Knuth', 2, 40)")
    c.executemany("INSERT INTO students (student_id, first_name, course, status) VALUES (?, ?, ?, ?)",
                  [("S1", "Ann", "CS", "Active"), ("S2", "Bob", "MSC", "Active"),
                   ("S3", "Cy", "CS", "Withdrawn")])
    c.executemany("INSERT INTO courses (code, name, level) VALUES (?, ?, ?)",
                  [("CS", "Computer Science", "Undergraduate"), ("MSC", "Data MSc", "Postgraduate")])
    c.executemany("INSERT INTO users (id, username, role, student_id) VALUES (?, ?, ?, ?)",
                  [(1, "admin", "admin", None), (2, "lib", "staff", None), (3, "S1", "student", "S1")])
    circ.ensure(c)
    c.commit()
    yield c
    c.close()


def _status(c, barcode):
    return c.execute("SELECT status FROM library_copies WHERE barcode = ?", (barcode,)).fetchone()[0]


def test_backfill_makes_copies_and_title_counts_follow(conn):
    assert [r[0] for r in conn.execute("SELECT barcode FROM library_copies")] == ["B1-1", "B1-2"]
    circ.checkout(conn, "B1", "S1", now=T0)
    assert conn.execute("SELECT quantity, available_quantity, status FROM books").fetchone() == \
        (2, 1, "available")
    circ.checkout(conn, "B1", "S2", now=T0)
    assert conn.execute("SELECT available_quantity, status FROM books").fetchone() == \
        (0, "checked_out")


def test_categories_set_loan_length(conn):
    assert circ.borrower(conn, "S1")["category"] == "undergraduate"
    assert circ.borrower(conn, "S2")["category"] == "postgraduate"
    assert circ.borrower(conn, "lib")["category"] == "staff"
    assert circ.borrower(conn, "2")["ref"] == "lib"            # numeric account id accepted
    loan = circ.checkout(conn, "B1", "S2", now=T0)
    assert loan["due_date"] == "2026-10-29 10:00:00"              # 28 days
    circ.set_override(conn, "S1", "extended", "reasonable adjustment")
    assert circ.checkout(conn, "B1", "S1", now=T0)["due_date"] == "2026-11-12 10:00:00"


def test_blocks_leavers_overdues_and_charges(conn):
    with pytest.raises(ValueError, match="membership has ended"):
        circ.checkout(conn, "B1", "S3", now=T0)
    circ.checkout(conn, "B1-1", "S1", now=T0)
    with pytest.raises(ValueError, match="overdue"):
        circ.checkout(conn, "B1-2", "S1", now=T0 + timedelta(days=30))
    assert circ.checkout(conn, "B1-2", "S1", now=T0 + timedelta(days=30),
                         override=True)["overridden"]


def test_short_loan_and_reference_items(conn):
    circ.update_copy(conn, conn.execute("SELECT copy_id FROM library_copies WHERE barcode = "
                                        "'B1-2'").fetchone()[0], item_type="short_24h")
    loan = circ.checkout(conn, "B1-2", "S1", now=T0)
    assert loan["due_date"] == "2026-10-02 10:00:00"
    late = {"due_date": loan["due_date"], "item_type": "short_24h"}
    assert circ.overdue_fine(conn, late, now=T0 + timedelta(hours=26, minutes=10)) == 1.5
    with pytest.raises(ValueError, match="cannot be renewed"):
        circ.renew(conn, "B1-2", now=T0)
    circ.add_copies(conn, "B1", 1, "reference")
    with pytest.raises(ValueError, match="Reference-only"):
        circ.checkout(conn, "B1-3", "S1", now=T0)


def test_hold_recalls_longest_loan_and_return_goes_to_holds_shelf(conn):
    circ.checkout(conn, "B1-1", "S1", now=T0)
    circ.checkout(conn, "B1-2", "S2", now=T0 + timedelta(days=1))
    hold = circ.place_hold(conn, "B1", "lib", now=T0 + timedelta(days=2))
    assert hold["ready"] is False and hold["emails"] == []      # S1 has no email
    due, original = conn.execute("SELECT due_date, original_due_date FROM book_loans "
                                 "WHERE user_id = 'S1'").fetchone()
    assert (due, original) == ("2026-10-15 10:00:00", "2026-10-22 10:00:00")
    with pytest.raises(ValueError, match="recalled"):
        circ.renew(conn, "B1-1", now=T0 + timedelta(days=3))
    returned = circ.return_item(conn, "B1-1", now=T0 + timedelta(days=5))
    assert returned["held"] and _status(conn, "B1-1") == "hold_shelf"
    with pytest.raises(ValueError, match="holds shelf for someone else"):
        circ.checkout(conn, "B1-1", "S2", now=T0 + timedelta(days=5))
    circ.checkout(conn, "B1-1", "lib", now=T0 + timedelta(days=6))
    assert conn.execute("SELECT status FROM book_reservations").fetchone()[0] == "fulfilled"


def test_uncollected_hold_passes_on(conn):
    circ.place_hold(conn, "B1", "S1", now=T0)
    circ.place_hold(conn, "B1", "S2", now=T0)
    circ.place_hold(conn, "B1", "lib", now=T0)               # 2 copies, 3 readers
    result = circ.expire_holds(conn, now=T0 + timedelta(days=4))
    assert len(result["expired"]) == 2
    assert conn.execute("SELECT user_id FROM book_reservations WHERE status = 'ready'"
                        ).fetchall() == [("lib",)]


def test_lost_charge_and_found_waives_replacement(conn):
    circ.checkout(conn, "B1-1", "S1", now=T0)
    lost = circ.declare_lost(conn, "B1-1", staff="lib", now=T0 + timedelta(days=5))
    assert lost["charged"] == 50.0                             # £40 price + £10 fee
    assert conn.execute("SELECT fine_amount, status FROM book_loans").fetchone() == (50.0, "lost")
    assert circ.found(conn, "B1-1")["waived"] == 40.0
    assert conn.execute("SELECT fine_amount FROM book_loans").fetchone()[0] == 10.0
    assert _status(conn, "B1-1") == "available"


def test_classmark_validation(conn):
    circ.set_classmark(conn, "B1", "005.133 smi")
    circ.set_classmark(conn, "B1", "QA76.73 .P98")
    with pytest.raises(ValueError):
        circ.set_classmark(conn, "B1", "not a classmark!")


def test_reading_list_holdings_and_shortfall_request(conn):
    conn.execute("INSERT INTO modules VALUES ('CS101')")
    conn.executemany("INSERT INTO student_modules VALUES (?, 'CS101', 'Enrolled')",
                     [(f"X{i}",) for i in range(25)])
    conn.execute("INSERT INTO reading_lists VALUES (1, 'Week 1')")
    conn.execute("INSERT INTO reading_list_items (item_id, list_id, book_id) VALUES (1, 1, 'B1')")
    services.link_list(conn, 1, "CS101")
    services.set_importance(conn, 1, "essential")
    (item,) = services.holdings_check(conn, 1)["items"]
    assert (item["lendable"], item["needed"], item["shortfall"]) == (2, 3, 1)
    assert services.request_shortfall(conn, 1, "lib") == 1
    assert services.request_shortfall(conn, 1, "lib") == 0      # not duplicated


def test_order_against_fund_then_receive(conn):
    services.set_fund(conn, "cs", "Computing", "2026/27", 100)
    with pytest.raises(ValueError, match="Over budget"):
        services.place_order(conn, supplier="Blackwell", fund_code="CS", quantity=3,
                             unit_price=40, book_id="B1")
    order = services.place_order(conn, supplier="Blackwell", fund_code="CS", quantity=2,
                                 unit_price=40, book_id="B1")
    assert services.fund_position(conn)[0]["remaining"] == 20
    assert services.receive(conn, order, 2, "Main") == ["B1-3", "B1-4"]
    fund = services.fund_position(conn)[0]
    assert (fund["committed"], fund["spent"]) == (0, 80)


def test_stocktake_marks_unseen_copies_missing(conn):
    conn.execute("UPDATE library_copies SET location = 'Main'")
    take = services.start_stocktake(conn, "Main", "lib")
    assert services.scan(conn, take, "B1-1").endswith("OK")
    assert "unknown" in services.scan(conn, take, "ZZZ")
    assert services.finish_stocktake(conn, take)["missing"] == ["B1-2"]
    assert _status(conn, "B1-2") == "missing"


def test_leavers_and_notice(conn):
    circ.checkout(conn, "B1-1", "S1", now=T0)
    conn.execute("UPDATE students SET status = 'Withdrawn' WHERE student_id = 'S1'")
    assert [r["student_id"] for r in services.leavers(conn)] == ["S1"]
    services.notify_leaver(conn, "S1")
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE recipient_id = 3").fetchone()[0] == 1


def test_eresource_cost_per_use_and_renewal_flag(conn):
    renewal = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    rid = services.save_eresource(conn, {"title": "IEEE", "annual_cost": "12000",
                                         "renewal_date": renewal})
    services.record_usage(conn, rid, datetime.now().strftime("%Y-%m"), 600)
    (row,) = services.eresources(conn)
    assert (row["cost_per_use"], row["decision_due"]) == (20.0, True)
