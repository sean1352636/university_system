"""Library: physical copies, loan rules, recalls, charges, module reading
lists, acquisitions, stocktake and e-resources.

Shared by migration ``f3c5e7a9b1d2`` and :func:`apply_to_connection`
(``university/application/library/``). Idempotent.

* ``library_copies`` — one row per physical item. A title (``books``) used to
  carry only ``quantity`` / ``available_quantity``; one checkout path marked
  the whole title checked out, another decremented the count and no return
  ever incremented it. Loans now name the copy (``book_loans.copy_id``) and
  the title's counts are derived from its copies.
* ``library_borrower_rules`` / ``library_item_rules`` — loans and limits by
  borrower category (undergraduate, postgraduate, staff, external, extended)
  and by item type (standard, 24-hour and 3-day short loan, reference only).
  ``library_borrower_overrides`` puts a person in a category (an external
  member, extended loans for a disabled student).
* ``book_loans.recalled_at`` / ``original_due_date`` — recalls;
  ``book_reservations.ready_at`` / ``collect_by`` / ``copy_id`` — the holds
  shelf.
* ``library_charges`` — lost and damaged item charges (the amount also lands
  on the loan's ``fine_amount`` so the existing fine payment and Finance
  reporting collect it).
* ``reading_lists.module_code`` and ``reading_list_items.importance`` —
  module reading lists.
* ``library_funds`` / ``library_orders`` — acquisitions against a budget.
* ``library_stocktakes`` / ``library_stocktake_scans`` — shelf checks.
* ``library_eresources`` / ``library_eresource_usage`` — subscriptions.
"""

from __future__ import annotations

ITEM_TYPES = ("standard", "short_24h", "short_3day", "reference")
COPY_STATUSES = ("available", "on_loan", "hold_shelf", "lost", "damaged", "missing",
                 "withdrawn", "on_order")
BORROWER_CATEGORIES = ("undergraduate", "postgraduate", "staff", "external", "extended")
IMPORTANCE = ("essential", "recommended", "further")

TABLES = (
    """CREATE TABLE IF NOT EXISTS library_copies (
        copy_id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id TEXT NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
        barcode TEXT NOT NULL UNIQUE,
        item_type TEXT NOT NULL DEFAULT 'standard'
            CHECK (item_type IN ('standard', 'short_24h', 'short_3day', 'reference')),
        location TEXT,
        status TEXT NOT NULL DEFAULT 'available'
            CHECK (status IN ('available', 'on_loan', 'hold_shelf', 'lost', 'damaged',
                              'missing', 'withdrawn', 'on_order')),
        condition_notes TEXT,
        price REAL CHECK (price IS NULL OR price >= 0),
        acquired_date TEXT,
        last_seen TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_library_copies_book ON library_copies(book_id, status)",
    """CREATE TABLE IF NOT EXISTS library_borrower_rules (
        category TEXT PRIMARY KEY
            CHECK (category IN ('undergraduate', 'postgraduate', 'staff', 'external', 'extended')),
        max_loans INTEGER NOT NULL CHECK (max_loans >= 0),
        loan_days INTEGER NOT NULL CHECK (loan_days > 0),
        max_renewals INTEGER NOT NULL CHECK (max_renewals >= 0),
        short_loans_allowed INTEGER NOT NULL DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS library_item_rules (
        item_type TEXT PRIMARY KEY
            CHECK (item_type IN ('standard', 'short_24h', 'short_3day', 'reference')),
        loan_hours INTEGER CHECK (loan_hours IS NULL OR loan_hours > 0),
        loanable INTEGER NOT NULL DEFAULT 1,
        renewable INTEGER NOT NULL DEFAULT 1,
        fine_per_day REAL CHECK (fine_per_day IS NULL OR fine_per_day >= 0),
        fine_per_hour REAL CHECK (fine_per_hour IS NULL OR fine_per_hour >= 0)
    )""",
    """CREATE TABLE IF NOT EXISTS library_borrower_overrides (
        borrower_ref TEXT PRIMARY KEY,
        category TEXT NOT NULL
            CHECK (category IN ('undergraduate', 'postgraduate', 'staff', 'external', 'extended')),
        reason TEXT NOT NULL,
        until TEXT,
        set_by TEXT,
        set_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS library_charges (
        charge_id INTEGER PRIMARY KEY AUTOINCREMENT,
        borrower_ref TEXT NOT NULL,
        loan_id INTEGER,
        copy_id INTEGER,
        kind TEXT NOT NULL CHECK (kind IN ('lost', 'damage', 'overdue')),
        amount REAL NOT NULL CHECK (amount >= 0),
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'paid', 'waived')),
        note TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        resolved_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_library_charges_borrower ON library_charges(borrower_ref, status)",
    """CREATE TABLE IF NOT EXISTS library_funds (
        fund_code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        department TEXT,
        academic_year TEXT NOT NULL,
        allocation REAL NOT NULL CHECK (allocation >= 0)
    )""",
    """CREATE TABLE IF NOT EXISTS library_orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        book_id TEXT,
        title TEXT NOT NULL,
        author TEXT,
        isbn TEXT,
        supplier TEXT NOT NULL,
        fund_code TEXT NOT NULL REFERENCES library_funds(fund_code),
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_price REAL NOT NULL CHECK (unit_price >= 0),
        item_type TEXT NOT NULL DEFAULT 'standard',
        status TEXT NOT NULL DEFAULT 'ordered'
            CHECK (status IN ('ordered', 'part_received', 'received', 'cancelled')),
        received_qty INTEGER NOT NULL DEFAULT 0,
        ordered_by TEXT,
        ordered_at TEXT NOT NULL DEFAULT (datetime('now')),
        received_at TEXT,
        cancelled_reason TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS library_stocktakes (
        stocktake_id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT NOT NULL,
        started_by TEXT,
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at TEXT,
        missing_marked INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS library_stocktake_scans (
        stocktake_id INTEGER NOT NULL REFERENCES library_stocktakes(stocktake_id),
        barcode TEXT NOT NULL,
        scanned_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (stocktake_id, barcode)
    )""",
    """CREATE TABLE IF NOT EXISTS library_eresources (
        resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        provider TEXT,
        resource_type TEXT,
        url TEXT,
        concurrent_users INTEGER CHECK (concurrent_users IS NULL OR concurrent_users > 0),
        annual_cost REAL CHECK (annual_cost IS NULL OR annual_cost >= 0),
        currency TEXT NOT NULL DEFAULT 'GBP',
        start_date TEXT,
        renewal_date TEXT,
        notice_days INTEGER NOT NULL DEFAULT 90,
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('trial', 'active', 'cancelled')),
        owner TEXT,
        notes TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS library_eresource_usage (
        resource_id INTEGER NOT NULL REFERENCES library_eresources(resource_id) ON DELETE CASCADE,
        period TEXT NOT NULL,
        uses INTEGER NOT NULL CHECK (uses >= 0),
        PRIMARY KEY (resource_id, period)
    )""",
)

COLUMNS = (
    ("books", "classmark", "TEXT"),
    ("book_loans", "copy_id", "INTEGER"),
    ("book_loans", "recalled_at", "TEXT"),
    ("book_loans", "original_due_date", "TEXT"),
    ("book_reservations", "copy_id", "INTEGER"),
    ("book_reservations", "ready_at", "TEXT"),
    ("book_reservations", "collect_by", "TEXT"),
    ("reading_lists", "module_code", "TEXT"),
    ("reading_list_items", "importance", "TEXT DEFAULT 'recommended'"),
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def _backfill_copies(execute):
    """One copy row per unit of each title's ``quantity`` (at least one),
    for titles that have none yet; active loans are attached to copies."""
    books = execute("SELECT b.book_id, COALESCE(NULLIF(b.quantity, 0), 1), b.barcode, b.location, "
                    "LOWER(COALESCE(b.status, 'available')), "
                    "COALESCE(b.purchase_price, b.acquisition_cost) FROM books b "
                    "WHERE NOT EXISTS (SELECT 1 FROM library_copies c "
                    "WHERE c.book_id = b.book_id)").fetchall()
    for book_id, quantity, barcode, location, status, price in books:
        loans = [r[0] for r in execute(
            "SELECT loan_id FROM book_loans WHERE book_id = ? AND copy_id IS NULL AND "
            "status IN ('active', 'overdue') ORDER BY loan_id", (book_id,)).fetchall()]
        for n in range(max(int(quantity or 1), len(loans))):
            code = barcode if n == 0 and barcode and not execute(
                "SELECT 1 FROM library_copies WHERE barcode = ?", (barcode,)).fetchone() \
                else f"{book_id}-{n + 1}"
            copy_status = "on_loan" if n < len(loans) else (
                status if status in ("damaged", "lost", "missing", "withdrawn") else "available")
            execute("INSERT INTO library_copies (book_id, barcode, location, status, price) "
                    "VALUES (?, ?, ?, ?, ?)", (book_id, code, location, copy_status, price))
            if n < len(loans):
                copy_id = execute("SELECT copy_id FROM library_copies WHERE barcode = ?",
                                  (code,)).fetchone()[0]
                execute("UPDATE book_loans SET copy_id = ? WHERE loan_id = ?",
                        (copy_id, loans[n]))


def apply(execute) -> None:
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in TABLES:
        execute(ddl)
    if _columns(execute, "books") and _columns(execute, "book_loans"):
        _backfill_copies(execute)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` on an open connection, once per database file.

    Inside a caller's open transaction it applies without committing (and is
    not remembered), so it can never commit half of someone else's work; the
    caller's commit or rollback decides. In-memory databases are never
    remembered: a connection id can be reused by a new database.
    """
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)
