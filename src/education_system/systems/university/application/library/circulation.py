"""Library circulation on physical copies.

Every screen used to write loans its own way: one marked the whole title
``checked_out`` (so a title with five copies could be lent once), one
decremented ``available_quantity`` into a table that does not exist, and no
return ever put the count back. Here a loan is of a *copy*
(``library_copies``), and a title's ``quantity`` / ``available_quantity`` /
``status`` are recomputed from its copies after every change
(:func:`sync_title`), so older screens that read them stay right.

Rules
-----
* **Borrower categories** — undergraduate, postgraduate (from the student's
  course level), staff (any non-student account), external and extended
  (``library_borrower_overrides``, e.g. extended loans as a reasonable
  adjustment). Each has a loan limit, loan length and renewal limit
  (``library_borrower_rules``, defaults below).
* **Item types** — standard; 24-hour and 3-day short loans (fined by the
  hour / day, not renewable / renewable); reference only (not lent).
* **Blocks** — a borrower with an overdue item or charges at or above the
  block threshold cannot borrow; leavers cannot borrow.
* **Holds and recalls** — a hold on a title with no copy on the shelf
  recalls the loan held longest: its due date comes forward to the later of
  ``recall_notice_days`` from now and ``recall_min_loan_days`` after it was
  borrowed (never later than it already was). A returned copy goes to the
  first person waiting (holds shelf) with a collect-by date.
* **Lost and damaged** — a lost item is charged at its replacement price plus
  an admin fee; found again, the replacement part is waived. Charges are
  added to the loan's ``fine_amount`` so the existing fine payment screens
  and Finance reporting collect them, and recorded in ``library_charges``.

Functions take an open connection and do not commit; the caller does.
Notices go to the Hub inbox in the same transaction; emails are returned
for the caller to send once committed (``timetable_occurrences.send_emails``).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.schemas import (
    library_catalogue_schema as schema,
)

BORROWER_DEFAULTS = {  # max_loans, loan_days, max_renewals, short_loans_allowed
    "undergraduate": (10, 21, 3, 1), "postgraduate": (15, 28, 5, 1),
    "staff": (25, 56, 10, 1), "external": (5, 21, 2, 0), "extended": (15, 42, 5, 1)}
ITEM_DEFAULTS = {  # loan_hours, loanable, renewable, fine_per_day, fine_per_hour
    "standard": (None, 1, 1, None, None), "short_24h": (24, 1, 0, None, 0.50),
    "short_3day": (72, 1, 1, 1.00, None), "reference": (None, 0, 0, None, None)}
SETTING_DEFAULTS = {"fine_per_day": 0.50, "fine_block_threshold": 10.0,
                    "reservation_period_days": 3, "recall_notice_days": 7,
                    "recall_min_loan_days": 14, "default_replacement_cost": 30.0,
                    "lost_admin_fee": 10.0, "hold_request_days": 90}
ON_LOAN = ("active", "overdue")
_LEFT = ("withdrawn", "graduated", "completed", "inactive", "suspended", "transferred")
_DEWEY = re.compile(r"^\d{3}(\.\d+)?(\s+[A-Z]{1,4})?$")
_LC = re.compile(r"^[A-Z]{1,3}\s?\d{1,4}(\.\d+)?(\s?\.?[A-Z]\d+)*(\s+\d{4})?$")


def ensure(conn):
    schema.apply_to_connection(conn)


def _now(now=None):
    return now or datetime.now()


def _fmt(when):
    return when.strftime("%Y-%m-%d %H:%M:%S")


def _parse(value):
    text = str(value or "")
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:len(datetime.now().strftime(pattern))], pattern)
        except ValueError:
            continue
    return None


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _one(conn, sql, params=()):
    rows = _dicts(conn.execute(sql, params))
    return rows[0] if rows else None


def setting(conn, name):
    default = SETTING_DEFAULTS[name]
    try:
        row = conn.execute("SELECT setting_value FROM library_settings WHERE setting_name = ?",
                           (name,)).fetchone()
    except Exception:
        return default
    try:
        return type(default)(row[0]) if row and row[0] not in (None, "") else default
    except (TypeError, ValueError):
        return default


SETTING_LABELS = {
    "fine_per_day": "Standard overdue fine per day (£)",
    "fine_block_threshold": "Borrowing stops when owed reaches (£)",
    "reservation_period_days": "Days to collect a held item",
    "recall_notice_days": "Recall notice (days)",
    "recall_min_loan_days": "Guaranteed loan before recall (days)",
    "default_replacement_cost": "Replacement cost when no price is known (£)",
    "lost_admin_fee": "Lost item admin fee (£)",
    "hold_request_days": "Requests lapse after (days)",
}


def set_setting(conn, name, value):
    if name not in SETTING_DEFAULTS:
        raise ValueError(f"Unknown setting {name}")
    try:
        number = type(SETTING_DEFAULTS[name])(value)
    except (TypeError, ValueError):
        raise ValueError(f"{SETTING_LABELS[name]} must be a number") from None
    if number < 0:
        raise ValueError(f"{SETTING_LABELS[name]} cannot be negative")
    kind = "integer" if isinstance(number, int) else "decimal"
    updated = conn.execute("UPDATE library_settings SET setting_value = ? WHERE setting_name = ?",
                           (str(number), name)).rowcount
    if not updated:
        conn.execute("INSERT INTO library_settings (setting_name, setting_value, description, "
                     "setting_type) VALUES (?, ?, ?, ?)",
                     (name, str(number), SETTING_LABELS[name], kind))


# ── rules ───────────────────────────────────────────────────────────────


def borrower_rules(conn, category) -> dict:
    ensure(conn)
    row = _one(conn, "SELECT max_loans, loan_days, max_renewals, short_loans_allowed "
                     "FROM library_borrower_rules WHERE category = ?", (category,))
    if row:
        return row
    return dict(zip(("max_loans", "loan_days", "max_renewals", "short_loans_allowed"),
                    BORROWER_DEFAULTS[category]))


def item_rules(conn, item_type) -> dict:
    ensure(conn)
    row = _one(conn, "SELECT loan_hours, loanable, renewable, fine_per_day, fine_per_hour "
                     "FROM library_item_rules WHERE item_type = ?", (item_type,))
    rules = row or dict(zip(("loan_hours", "loanable", "renewable", "fine_per_day",
                             "fine_per_hour"), ITEM_DEFAULTS[item_type]))
    if rules["fine_per_day"] is None and rules["fine_per_hour"] is None:
        rules = dict(rules, fine_per_day=setting(conn, "fine_per_day"))
    return rules


def set_borrower_rule(conn, category, max_loans, loan_days, max_renewals, short_loans_allowed):
    ensure(conn)
    if category not in schema.BORROWER_CATEGORIES:
        raise ValueError(f"Category is one of: {', '.join(schema.BORROWER_CATEGORIES)}")
    try:
        values = [int(v) for v in (max_loans, loan_days, max_renewals)]
    except (TypeError, ValueError):
        raise ValueError("Limits are whole numbers") from None
    if values[1] <= 0 or min(values) < 0:
        raise ValueError("Loan length must be at least a day; limits cannot be negative")
    conn.execute("INSERT OR REPLACE INTO library_borrower_rules VALUES (?, ?, ?, ?, ?)",
                 (category, *values, 1 if short_loans_allowed else 0))


def set_item_rule(conn, item_type, loan_hours, loanable, renewable, fine_per_day, fine_per_hour):
    ensure(conn)
    if item_type not in schema.ITEM_TYPES:
        raise ValueError(f"Item type is one of: {', '.join(schema.ITEM_TYPES)}")

    def number(v, cast=float):
        if v in (None, ""):
            return None
        try:
            n = cast(v)
        except (TypeError, ValueError):
            raise ValueError("Loan hours and fines must be numbers") from None
        if n < 0:
            raise ValueError("Loan hours and fines cannot be negative")
        return n
    conn.execute("INSERT OR REPLACE INTO library_item_rules VALUES (?, ?, ?, ?, ?, ?)",
                 (item_type, number(loan_hours, int) or None, 1 if loanable else 0,
                  1 if renewable else 0, number(fine_per_day), number(fine_per_hour)))


# ── borrowers ───────────────────────────────────────────────────────────


def _student_category(conn, course):
    from education_system.systems.university.application.programmes import (
        record as programme_record,
    )
    row = _one(conn, "SELECT level FROM courses WHERE ? IN (COALESCE(NULLIF(course_code, ''), "
                     "code), COALESCE(NULLIF(course_name, ''), name))", (course or "",))
    return "postgraduate" if row and programme_record.is_postgraduate(row) else "undergraduate"


def borrower(conn, ref) -> dict:
    """``{ref, kind, category, name, email, active}``. Students are identified
    by student ID, staff by username (a numeric account id is accepted)."""
    ensure(conn)
    ref = str(ref or "").strip()
    if not ref:
        raise ValueError("Say who is borrowing")
    override = _one(conn, "SELECT category, until FROM library_borrower_overrides "
                          "WHERE borrower_ref = ?", (ref,))
    if override and override["until"] and override["until"] < _fmt(_now())[:10]:
        override = None
    student = _one(conn, "SELECT student_id, TRIM(COALESCE(first_name, '') || ' ' || "
                         "COALESCE(last_name, '')) AS name, email_address AS email, course, "
                         "status, COALESCE(is_active, 1) AS is_active FROM students "
                         "WHERE student_id = ?", (ref,))
    if student:
        active = student["is_active"] and str(student["status"] or "").lower() not in _LEFT
        category = override["category"] if override else _student_category(conn, student["course"])
        return {"ref": student["student_id"], "kind": "student", "category": category,
                "name": student["name"], "email": student["email"], "active": bool(active)}
    user = _one(conn, "SELECT id, username, TRIM(COALESCE(first_name, '') || ' ' || "
                      "COALESCE(last_name, '')) AS name, email, role FROM users "
                      "WHERE username = ? OR CAST(id AS TEXT) = ?", (ref, ref))
    if user and str(user["role"] or "").lower() != "student":
        return {"ref": user["username"], "kind": "staff",
                "category": override["category"] if override else "staff",
                "name": user["name"], "email": user["email"], "active": True, "user_id": user["id"]}
    if override:
        return {"ref": ref, "kind": "external", "category": override["category"], "name": ref,
                "email": None, "active": True}
    raise ValueError(f"No student, staff account or registered external borrower {ref}")


def _refs(who) -> list[str]:
    """Every id a borrower's older loans may be filed under."""
    return [who["ref"]] + ([str(who["user_id"])] if who.get("user_id") is not None else [])


def set_override(conn, ref, category, reason, until=None, actor=None):
    ensure(conn)
    if category not in schema.BORROWER_CATEGORIES:
        raise ValueError(f"Category is one of: {', '.join(schema.BORROWER_CATEGORIES)}")
    if not (reason or "").strip():
        raise ValueError("Record why")
    conn.execute("INSERT OR REPLACE INTO library_borrower_overrides (borrower_ref, category, "
                 "reason, until, set_by) VALUES (?, ?, ?, ?, ?)",
                 (str(ref).strip(), category, reason.strip(), (until or "")[:10] or None, actor))


def open_charges(conn, who) -> float:
    refs = _refs(who)
    marks = ", ".join("?" for _ in refs)
    owed = conn.execute(f"SELECT COALESCE(SUM(fine_amount), 0) FROM book_loans WHERE user_id IN "
                        f"({marks}) AND COALESCE(fine_amount, 0) > 0 AND COALESCE(paid, '') "
                        "NOT IN ('1', 'yes', 'true', 'paid')", refs).fetchone()[0]
    return float(owed or 0)


def current_loans(conn, who) -> list[dict]:
    refs = _refs(who)
    return _dicts(conn.execute(
        "SELECT l.*, b.title, c.barcode, c.item_type FROM book_loans l "
        "LEFT JOIN books b ON b.book_id = l.book_id LEFT JOIN library_copies c "
        f"ON c.copy_id = l.copy_id WHERE l.user_id IN ({', '.join('?' for _ in refs)}) "
        "AND l.status IN ('active', 'overdue') ORDER BY l.due_date", refs))


def blocks(conn, who, now=None) -> list[str]:
    """Why this borrower cannot borrow now (empty when they can)."""
    out = []
    if not who["active"]:
        out.append("not a current student — library membership has ended")
    loans = current_loans(conn, who)
    stamp = _fmt(_now(now))
    if any(str(l["due_date"]) < stamp for l in loans):
        out.append("has an overdue item")
    owed, limit = open_charges(conn, who), setting(conn, "fine_block_threshold")
    if limit and owed >= limit:
        out.append(f"owes £{owed:.2f} (borrowing stops at £{limit:.2f})")
    return out


# ── titles and copies ───────────────────────────────────────────────────


def sync_title(conn, book_id):
    """Recompute a title's legacy count / status columns from its copies."""
    counts = dict(conn.execute("SELECT status, COUNT(*) FROM library_copies WHERE book_id = ? "
                               "GROUP BY status", (book_id,)).fetchall())
    total = sum(n for s, n in counts.items() if s not in ("withdrawn", "lost", "on_order"))
    available = counts.get("available", 0)
    status = ("available" if available else "reserved" if counts.get("hold_shelf")
              else "checked_out" if counts.get("on_loan") else
              "damaged" if counts.get("damaged") else "unavailable")
    conn.execute("UPDATE books SET quantity = ?, available_quantity = ?, status = ?, "
                 "last_updated = ? WHERE book_id = ?",
                 (total, available, status, _fmt(_now()), book_id))


def _copies_for_new_titles(conn):
    """Titles added by the older add-book screens arrive with a quantity but
    no copies; give them copies the first time they are handled."""
    schema._backfill_copies(conn.execute)


def copies(conn, book_id) -> list[dict]:
    ensure(conn)
    _copies_for_new_titles(conn)
    return _dicts(conn.execute(
        "SELECT c.*, (SELECT l.user_id FROM book_loans l WHERE l.copy_id = c.copy_id AND "
        "l.status IN ('active', 'overdue') LIMIT 1) AS borrower, (SELECT l.due_date FROM "
        "book_loans l WHERE l.copy_id = c.copy_id AND l.status IN ('active', 'overdue') "
        "LIMIT 1) AS due_date FROM library_copies c WHERE c.book_id = ? ORDER BY c.copy_id",
        (book_id,)))


def add_copies(conn, book_id, count=1, item_type="standard", location=None, price=None,
               status="available") -> list[str]:
    ensure(conn)
    if not conn.execute("SELECT 1 FROM books WHERE book_id = ?", (book_id,)).fetchone():
        raise ValueError(f"No title {book_id}")
    if item_type not in schema.ITEM_TYPES:
        raise ValueError(f"Item type is one of: {', '.join(schema.ITEM_TYPES)}")
    try:
        count = int(count)
        price = float(price) if str(price or "").strip() else None
    except (TypeError, ValueError):
        raise ValueError("Count and price must be numbers") from None
    if not 1 <= count <= 500:
        raise ValueError("Add between 1 and 500 copies")
    n = conn.execute("SELECT COUNT(*) FROM library_copies WHERE book_id = ?",
                     (book_id,)).fetchone()[0]
    made = []
    while len(made) < count:
        n += 1
        code = f"{book_id}-{n}"
        if conn.execute("SELECT 1 FROM library_copies WHERE barcode = ?", (code,)).fetchone():
            continue
        conn.execute("INSERT INTO library_copies (book_id, barcode, item_type, location, status, "
                     "price, acquired_date) VALUES (?, ?, ?, ?, ?, ?, date('now'))",
                     (book_id, code, item_type, location, status, price))
        made.append(code)
    sync_title(conn, book_id)
    return made


def update_copy(conn, copy_id, *, item_type=None, location=None, status=None, notes=None):
    copy = _one(conn, "SELECT * FROM library_copies WHERE copy_id = ?", (copy_id,))
    if not copy:
        raise ValueError("No such copy")
    if item_type and item_type not in schema.ITEM_TYPES:
        raise ValueError(f"Item type is one of: {', '.join(schema.ITEM_TYPES)}")
    if status:
        if status not in ("available", "damaged", "missing", "withdrawn"):
            raise ValueError("A copy can be set to available, damaged, missing or withdrawn here; "
                             "loans, holds and losses change through circulation")
        if copy["status"] in ("on_loan", "hold_shelf"):
            raise ValueError("That copy is on loan or on the holds shelf")
    conn.execute("UPDATE library_copies SET item_type = COALESCE(?, item_type), location = "
                 "COALESCE(?, location), status = COALESCE(?, status), condition_notes = "
                 "COALESCE(?, condition_notes) WHERE copy_id = ?",
                 (item_type, location, status, notes, copy_id))
    sync_title(conn, copy["book_id"])


def set_classmark(conn, book_id, classmark):
    ensure(conn)
    mark = " ".join(str(classmark or "").upper().split())
    if mark and not (_DEWEY.match(mark) or _LC.match(mark)):
        raise ValueError("Use a Dewey number (e.g. 005.133 SMI) or a Library of Congress "
                         "classmark (e.g. QA76.73 .P98)")
    if not conn.execute("UPDATE books SET classmark = ? WHERE book_id = ?",
                        (mark or None, book_id)).rowcount:
        raise ValueError(f"No title {book_id}")


def find_copy(conn, item) -> dict:
    """A copy by barcode, or the best copy of a title by book id / barcode."""
    ensure(conn)
    item = str(item or "").strip()
    copy = _one(conn, "SELECT * FROM library_copies WHERE barcode = ?", (item,))
    if copy:
        return copy
    book = _one(conn, "SELECT book_id FROM books WHERE book_id = ? OR barcode = ? OR isbn = ?",
                (item, item, item))
    if not book:
        raise ValueError(f"No copy or title {item}")
    _copies_for_new_titles(conn)
    copy = _one(conn, "SELECT * FROM library_copies WHERE book_id = ? AND status = 'available' "
                      "ORDER BY CASE item_type WHEN 'standard' THEN 0 WHEN 'short_3day' THEN 1 "
                      "WHEN 'short_24h' THEN 2 ELSE 3 END, copy_id LIMIT 1", (book["book_id"],))
    if not copy:
        raise ValueError("No copy of that title is on the shelf — place a hold instead")
    return copy


# ── notices ─────────────────────────────────────────────────────────────


def _notice(conn, who_ref, subject, body) -> list:
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    try:
        who = borrower(conn, who_ref)
    except ValueError:
        return []
    deliver_inbox_message_on(conn, who["ref"], subject, body)
    return [(who["email"], subject, body)] if who.get("email") and "@" in who["email"] else []


# ── checkout / renew / return ───────────────────────────────────────────


def _due(conn, who, copy, now):
    item = item_rules(conn, copy["item_type"])
    if item["loan_hours"]:
        return now + timedelta(hours=item["loan_hours"])
    return now + timedelta(days=borrower_rules(conn, who["category"])["loan_days"])


def _check_copy(conn, copy, who):
    item = item_rules(conn, copy["item_type"])
    if not item["loanable"]:
        raise ValueError("Reference-only item: it can be used in the library but not borrowed")
    if copy["item_type"].startswith("short") and \
            not borrower_rules(conn, who["category"])["short_loans_allowed"]:
        raise ValueError(f"{who['category'].title()} borrowers cannot borrow short-loan items")
    if copy["status"] == "hold_shelf":
        hold = _one(conn, "SELECT user_id FROM book_reservations WHERE copy_id = ? AND status = "
                          "'ready'", (copy["copy_id"],))
        if not hold or hold["user_id"] not in _refs(who):
            raise ValueError("That copy is on the holds shelf for someone else")
    elif copy["status"] != "available":
        raise ValueError(f"That copy is {copy['status'].replace('_', ' ')}")


def checkout(conn, item, borrower_ref, *, staff=None, method="desk", override=False,
             now=None) -> dict:
    """Lend a copy. *override* (staff) lends despite a block, never past the
    copy's own rules. Returns the loan with ``emails`` to send."""
    now = _now(now)
    who = borrower(conn, borrower_ref)
    copy = find_copy(conn, item)
    _check_copy(conn, copy, who)
    problems = blocks(conn, who, now)
    rules = borrower_rules(conn, who["category"])
    if len(current_loans(conn, who)) >= rules["max_loans"]:
        problems.append(f"already has {rules['max_loans']} items (the {who['category']} limit)")
    if problems and not override:
        raise ValueError(f"{who['name'] or who['ref']} cannot borrow: " + "; ".join(problems))
    due = _due(conn, who, copy, now)
    cur = conn.execute("INSERT INTO book_loans (book_id, copy_id, user_id, checkout_date, due_date, "
                       "status, fine_amount, renewal_count, checkout_method, staff_id) "
                       "VALUES (?, ?, ?, ?, ?, 'active', 0, 0, ?, ?)",
                       (copy["book_id"], copy["copy_id"], who["ref"], _fmt(now), _fmt(due),
                        method, staff))
    conn.execute("UPDATE book_reservations SET status = 'fulfilled' WHERE book_id = ? AND "
                 f"user_id IN ({', '.join('?' for _ in _refs(who))}) AND status IN "
                 "('active', 'ready')", (copy["book_id"], *_refs(who)))
    conn.execute("UPDATE library_copies SET status = 'on_loan', last_seen = ? WHERE copy_id = ?",
                 (_fmt(now), copy["copy_id"]))
    sync_title(conn, copy["book_id"])
    return {"loan_id": int(cur.lastrowid), "barcode": copy["barcode"], "due_date": _fmt(due),
            "borrower": who, "overridden": problems, "emails": []}


def _loan(conn, loan_or_item):
    key = str(loan_or_item).strip()
    loan = _one(conn, "SELECT l.*, c.item_type, c.barcode FROM book_loans l LEFT JOIN "
                      "library_copies c ON c.copy_id = l.copy_id WHERE l.status IN "
                      "('active', 'overdue') AND (CAST(l.loan_id AS TEXT) = ? OR c.barcode = ?)",
                (key, key))
    if not loan:
        raise ValueError(f"No current loan for {key}")
    if loan["copy_id"] is None:
        raise ValueError("That loan has no copy recorded; run the library schema update")
    return loan


def overdue_fine(conn, loan, now=None) -> float:
    due = _parse(loan["due_date"])
    now = _now(now)
    if not due or now <= due:
        return 0.0
    item = item_rules(conn, loan.get("item_type") or "standard")
    if item["fine_per_hour"]:
        return round(((now - due).total_seconds() // 3600 + 1) * item["fine_per_hour"], 2)
    days = (now.date() - due.date()).days
    return round(max(days, 1) * (item["fine_per_day"] or 0), 2)


def waiting_holds(conn, book_id) -> list[dict]:
    return _dicts(conn.execute("SELECT * FROM book_reservations WHERE book_id = ? AND status = "
                               "'active' ORDER BY COALESCE(priority_order, 0), reservation_date, "
                               "reservation_id", (book_id,)))


def _to_holds_shelf(conn, copy_id, book_id, now) -> list:
    """Give a free copy to the first person waiting. Returns emails."""
    queue = waiting_holds(conn, book_id)
    if not queue:
        conn.execute("UPDATE library_copies SET status = 'available' WHERE copy_id = ?", (copy_id,))
        return []
    hold = queue[0]
    collect_by = now + timedelta(days=setting(conn, "reservation_period_days"))
    conn.execute("UPDATE book_reservations SET status = 'ready', copy_id = ?, ready_at = ?, "
                 "collect_by = ? WHERE reservation_id = ?",
                 (copy_id, _fmt(now), _fmt(collect_by), hold["reservation_id"]))
    conn.execute("UPDATE library_copies SET status = 'hold_shelf' WHERE copy_id = ?", (copy_id,))
    title = conn.execute("SELECT title FROM books WHERE book_id = ?", (book_id,)).fetchone()
    return _notice(conn, hold["user_id"], "Your library request is ready",
                   f"'{title[0] if title else book_id}' is waiting for you at the library. "
                   f"Collect it by {collect_by:%A %d %B}.")


def return_item(conn, loan_or_item, *, condition="good", notes=None, staff=None,
                now=None) -> dict:
    """Check a copy back in: fine for lateness, route to the next hold or the
    shelf, or mark it damaged. Returns ``{loan_id, fine, hold, emails}``."""
    now = _now(now)
    loan = _loan(conn, loan_or_item)
    fine = overdue_fine(conn, loan, now)
    conn.execute("UPDATE book_loans SET status = 'returned', return_date = ?, fine_amount = "
                 "COALESCE(fine_amount, 0) + ?, notes = COALESCE(?, notes) WHERE loan_id = ?",
                 (_fmt(now), fine, notes, loan["loan_id"]))
    if fine:
        conn.execute("INSERT INTO library_charges (borrower_ref, loan_id, copy_id, kind, amount, "
                     "note, created_by) VALUES (?, ?, ?, 'overdue', ?, ?, ?)",
                     (loan["user_id"], loan["loan_id"], loan["copy_id"], fine,
                      f"returned {_fmt(now)[:10]}, due {str(loan['due_date'])[:10]}", staff))
    emails = []
    if condition == "damaged":
        conn.execute("UPDATE library_copies SET status = 'damaged', condition_notes = "
                     "COALESCE(condition_notes || '; ', '') || ? WHERE copy_id = ?",
                     (f"returned damaged {_fmt(now)[:10]}: {notes or ''}", loan["copy_id"]))
    else:
        emails = _to_holds_shelf(conn, loan["copy_id"], loan["book_id"], now)
    conn.execute("UPDATE library_copies SET last_seen = ? WHERE copy_id = ?",
                 (_fmt(now), loan["copy_id"]))
    sync_title(conn, loan["book_id"])
    return {"loan_id": loan["loan_id"], "borrower": loan["user_id"], "fine": fine,
            "held": bool(emails) or conn.execute(
                "SELECT status FROM library_copies WHERE copy_id = ?",
                (loan["copy_id"],)).fetchone()[0] == "hold_shelf", "emails": emails}


def renewal_refusal(conn, loan, who, now=None) -> str | None:
    if loan.get("recalled_at"):
        return "it has been recalled for another reader"
    if not item_rules(conn, loan.get("item_type") or "standard")["renewable"]:
        return "short-loan items of this kind cannot be renewed"
    if (loan["renewal_count"] or 0) >= borrower_rules(conn, who["category"])["max_renewals"]:
        return "the renewal limit has been reached"
    if waiting_holds(conn, loan["book_id"]) and not conn.execute(
            "SELECT 1 FROM library_copies WHERE book_id = ? AND status = 'available'",
            (loan["book_id"],)).fetchone():
        return "another reader is waiting for it"
    if not who["active"]:
        return "library membership has ended"
    return None


def renew(conn, loan_or_item, *, now=None) -> dict:
    now = _now(now)
    loan = _loan(conn, loan_or_item)
    who = borrower(conn, loan["user_id"])
    why = renewal_refusal(conn, loan, who, now)
    if why:
        raise ValueError(f"Cannot renew: {why}")
    copy = _one(conn, "SELECT * FROM library_copies WHERE copy_id = ?", (loan["copy_id"],))
    due = max(_due(conn, who, copy, now), _parse(loan["due_date"]) or now)
    conn.execute("UPDATE book_loans SET due_date = ?, renewal_count = COALESCE(renewal_count, "
                 "0) + 1, status = 'active' WHERE loan_id = ?", (_fmt(due), loan["loan_id"]))
    return {"loan_id": loan["loan_id"], "due_date": _fmt(due),
            "renewals_left": borrower_rules(conn, who["category"])["max_renewals"]
            - (loan["renewal_count"] or 0) - 1}


# ── holds and recalls ───────────────────────────────────────────────────


def _recall(conn, book_id, now) -> list:
    """Bring forward the loan held longest; returns emails."""
    loan = _one(conn, "SELECT l.*, c.item_type FROM book_loans l JOIN library_copies c ON "
                      "c.copy_id = l.copy_id WHERE l.book_id = ? AND l.status IN ('active', "
                      "'overdue') AND l.recalled_at IS NULL AND c.item_type = 'standard' "
                      "ORDER BY l.checkout_date LIMIT 1", (book_id,))
    if not loan:
        return []
    out = _parse(loan["checkout_date"]) or now
    new_due = max(now + timedelta(days=setting(conn, "recall_notice_days")),
                  out + timedelta(days=setting(conn, "recall_min_loan_days")))
    current = _parse(loan["due_date"]) or new_due
    if new_due >= current:
        return []
    conn.execute("UPDATE book_loans SET original_due_date = due_date, due_date = ?, "
                 "recalled_at = ? WHERE loan_id = ?", (_fmt(new_due), _fmt(now), loan["loan_id"]))
    title = conn.execute("SELECT title FROM books WHERE book_id = ?", (book_id,)).fetchone()
    return _notice(conn, loan["user_id"], "Library recall: please return early",
                   f"Another reader has requested '{title[0] if title else book_id}'. "
                   f"Please return it by {new_due:%A %d %B} (it was due "
                   f"{current:%d %B}). It cannot be renewed.")


def place_hold(conn, book_id, borrower_ref, now=None) -> dict:
    now = _now(now)
    ensure(conn)
    who = borrower(conn, borrower_ref)
    if not who["active"]:
        raise ValueError("Library membership has ended")
    if not conn.execute("SELECT 1 FROM books WHERE book_id = ?", (book_id,)).fetchone():
        raise ValueError(f"No title {book_id}")
    refs = _refs(who)
    marks = ", ".join("?" for _ in refs)
    if conn.execute(f"SELECT 1 FROM book_reservations WHERE book_id = ? AND user_id IN ({marks}) "
                    "AND status IN ('active', 'ready')", (book_id, *refs)).fetchone():
        raise ValueError("You already have a request for this title")
    if conn.execute(f"SELECT 1 FROM book_loans WHERE book_id = ? AND user_id IN ({marks}) AND "
                    "status IN ('active', 'overdue')", (book_id, *refs)).fetchone():
        raise ValueError("You already have a copy of this title")
    lendable = conn.execute("SELECT COUNT(*) FROM library_copies c LEFT JOIN library_item_rules r "
                            "ON r.item_type = c.item_type WHERE c.book_id = ? AND c.item_type <> "
                            "'reference' AND c.status NOT IN ('lost', 'withdrawn', 'missing')",
                            (book_id,)).fetchone()[0]
    if not lendable:
        raise ValueError("No copy of this title can be borrowed")
    position = conn.execute("SELECT COALESCE(MAX(priority_order), 0) + 1 FROM book_reservations "
                            "WHERE book_id = ? AND status = 'active'", (book_id,)).fetchone()[0]
    expires = now + timedelta(days=setting(conn, "hold_request_days"))
    cur = conn.execute("INSERT INTO book_reservations (book_id, user_id, reservation_date, "
                       "expiry_date, status, priority_order, notification_sent) "
                       "VALUES (?, ?, ?, ?, 'active', ?, 0)",
                       (book_id, who["ref"], _fmt(now), _fmt(expires), position))
    shelf = _one(conn, "SELECT copy_id FROM library_copies WHERE book_id = ? AND status = "
                       "'available' AND item_type <> 'reference' LIMIT 1", (book_id,))
    emails = _to_holds_shelf(conn, shelf["copy_id"], book_id, now) if shelf \
        else _recall(conn, book_id, now)
    sync_title(conn, book_id)
    return {"reservation_id": int(cur.lastrowid), "position": position,
            "ready": bool(shelf), "emails": emails}


def cancel_hold(conn, reservation_id, now=None) -> list:
    hold = _one(conn, "SELECT * FROM book_reservations WHERE reservation_id = ?",
                (reservation_id,))
    if not hold or hold["status"] not in ("active", "ready"):
        raise ValueError("That request is not open")
    conn.execute("UPDATE book_reservations SET status = 'cancelled' WHERE reservation_id = ?",
                 (reservation_id,))
    emails = _to_holds_shelf(conn, hold["copy_id"], hold["book_id"], _now(now)) \
        if hold["status"] == "ready" and hold["copy_id"] else []
    sync_title(conn, hold["book_id"])
    return emails


def expire_holds(conn, now=None) -> dict:
    """Uncollected holds past their collect-by date pass to the next reader;
    queued requests past their expiry date lapse."""
    now = _now(now)
    expired, emails = [], []
    for hold in _dicts(conn.execute("SELECT * FROM book_reservations WHERE status = 'ready' "
                                    "AND collect_by < ?", (_fmt(now),))):
        conn.execute("UPDATE book_reservations SET status = 'expired' WHERE reservation_id = ?",
                     (hold["reservation_id"],))
        if hold["copy_id"]:
            emails += _to_holds_shelf(conn, hold["copy_id"], hold["book_id"], now)
            sync_title(conn, hold["book_id"])
        expired.append(hold["reservation_id"])
    lapsed = conn.execute("UPDATE book_reservations SET status = 'expired' WHERE status = "
                          "'active' AND expiry_date IS NOT NULL AND expiry_date < ?",
                          (_fmt(now),)).rowcount
    return {"expired": expired, "lapsed": lapsed, "emails": emails}


def holds_shelf(conn) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute(
        "SELECT r.reservation_id, r.user_id, r.ready_at, r.collect_by, b.title, c.barcode "
        "FROM book_reservations r JOIN books b ON b.book_id = r.book_id LEFT JOIN "
        "library_copies c ON c.copy_id = r.copy_id WHERE r.status = 'ready' "
        "ORDER BY r.collect_by"))


# ── lost and damaged ────────────────────────────────────────────────────


def _charge(conn, loan, kind, amount, note, staff):
    conn.execute("INSERT INTO library_charges (borrower_ref, loan_id, copy_id, kind, amount, "
                 "note, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (loan["user_id"], loan["loan_id"], loan["copy_id"], kind, amount, note, staff))
    conn.execute("UPDATE book_loans SET fine_amount = COALESCE(fine_amount, 0) + ? "
                 "WHERE loan_id = ?", (amount, loan["loan_id"]))


def declare_lost(conn, loan_or_item, *, staff=None, now=None) -> dict:
    now = _now(now)
    loan = _loan(conn, loan_or_item)
    price = conn.execute("SELECT COALESCE(c.price, b.purchase_price, b.acquisition_cost) FROM "
                         "library_copies c JOIN books b ON b.book_id = c.book_id WHERE "
                         "c.copy_id = ?", (loan["copy_id"],)).fetchone()[0]
    replacement = float(price) if price else setting(conn, "default_replacement_cost")
    fee = setting(conn, "lost_admin_fee")
    overdue = overdue_fine(conn, loan, now)
    conn.execute("UPDATE book_loans SET status = 'lost', return_date = ? WHERE loan_id = ?",
                 (_fmt(now), loan["loan_id"]))
    _charge(conn, loan, "lost", replacement + fee,
            f"replacement £{replacement:.2f} + admin fee £{fee:.2f}", staff)
    if overdue:
        _charge(conn, loan, "overdue", overdue, "overdue until declared lost", staff)
    conn.execute("UPDATE library_copies SET status = 'lost' WHERE copy_id = ?", (loan["copy_id"],))
    sync_title(conn, loan["book_id"])
    emails = _notice(conn, loan["user_id"], "Library item charged as lost",
                     f"Item {loan['barcode']} has been recorded as lost. You have been charged "
                     f"£{replacement + fee:.2f} (replacement £{replacement:.2f} + admin fee "
                     f"£{fee:.2f}). If you find it, return it and the replacement charge will "
                     "be refunded.")
    return {"charged": replacement + fee + overdue, "emails": emails}


def found(conn, barcode, *, staff=None, now=None) -> dict:
    """A lost or missing copy turns up: back to the shelf (or a hold); a lost
    charge still unpaid has its replacement part waived."""
    now = _now(now)
    copy = _one(conn, "SELECT * FROM library_copies WHERE barcode = ?", (str(barcode).strip(),))
    if not copy or copy["status"] not in ("lost", "missing"):
        raise ValueError("That copy is not recorded as lost or missing")
    waived = 0.0
    charge = _one(conn, "SELECT * FROM library_charges WHERE copy_id = ? AND kind = 'lost' AND "
                        "status = 'open' ORDER BY charge_id DESC LIMIT 1", (copy["copy_id"],))
    if charge:
        waived = max(charge["amount"] - setting(conn, "lost_admin_fee"), 0)
        conn.execute("UPDATE library_charges SET amount = amount - ?, note = note || ?, "
                     "resolved_at = ? WHERE charge_id = ?",
                     (waived, f"; item found {_fmt(now)[:10]}, replacement waived", _fmt(now),
                      charge["charge_id"]))
        conn.execute("UPDATE book_loans SET fine_amount = MAX(COALESCE(fine_amount, 0) - ?, 0), "
                     "status = 'returned' WHERE loan_id = ?", (waived, charge["loan_id"]))
    emails = _to_holds_shelf(conn, copy["copy_id"], copy["book_id"], now)
    conn.execute("UPDATE library_copies SET last_seen = ? WHERE copy_id = ?",
                 (_fmt(now), copy["copy_id"]))
    sync_title(conn, copy["book_id"])
    return {"waived": waived, "emails": emails}


def charge_damage(conn, loan_id, amount, note, *, staff=None):
    loan = _one(conn, "SELECT * FROM book_loans WHERE loan_id = ?", (loan_id,))
    if not loan:
        raise ValueError("No such loan")
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise ValueError("The charge must be a number") from None
    if amount <= 0 or not (note or "").strip():
        raise ValueError("Give a positive amount and describe the damage")
    _charge(conn, loan, "damage", amount, note.strip(), staff)
    return _notice(conn, loan["user_id"], "Library damage charge",
                   f"You have been charged £{amount:.2f} for damage to a library item: {note}")


def waive_charge(conn, charge_id, reason, *, staff=None):
    charge = _one(conn, "SELECT * FROM library_charges WHERE charge_id = ? AND status = 'open'",
                  (charge_id,))
    if not charge:
        raise ValueError("That charge is not open")
    if not (reason or "").strip():
        raise ValueError("Record why it is waived")
    conn.execute("UPDATE library_charges SET status = 'waived', resolved_at = ?, note = "
                 "COALESCE(note, '') || ? WHERE charge_id = ?",
                 (_fmt(_now()), f"; waived by {staff}: {reason}", charge_id))
    if charge["loan_id"]:
        conn.execute("UPDATE book_loans SET fine_amount = MAX(COALESCE(fine_amount, 0) - ?, 0) "
                     "WHERE loan_id = ?", (charge["amount"], charge["loan_id"]))
