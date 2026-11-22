"""Library services beyond the issue desk: a borrower's own account, module
reading lists and whether stock meets them, acquisitions against funds,
stocktakes, leavers' clearance and e-resource subscriptions.

* **My library** — loans with due dates, recalls and whether each can be
  renewed; requests and their place in the queue; history; charges.
* **Module reading lists** — a reading list can belong to a module
  (``reading_lists.module_code``) and each item is essential, recommended or
  further reading. Holdings are checked against the module's enrolment:
  one lendable copy per ``ESSENTIAL_RATIO`` students for essential items, per
  ``RECOMMENDED_RATIO`` for recommended. A shortfall becomes a purchase
  request for acquisitions.
* **Acquisitions** — orders against a fund; committed (ordered, not yet
  received) and spent (received) are both counted against the allocation,
  so a fund cannot be overspent without saying so. Receiving creates the
  title if new and its copies.
* **Stocktake** — scan the shelves of a location; at the end, copies that
  should be there and were not scanned become *missing*.
* **Leavers** — anyone whose studies have ended with items or money still
  owed; the student is sent a notice when they are withdrawn.
* **E-resources** — subscriptions with cost, licence, renewal date and notice
  period; usage per month gives cost per use.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta

from education_system.systems.university.application.library import circulation as circ

ESSENTIAL_RATIO = 10
RECOMMENDED_RATIO = 25


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _one(conn, sql, params=()):
    rows = _dicts(conn.execute(sql, params))
    return rows[0] if rows else None


# ── my library ──────────────────────────────────────────────────────────


def my_library(conn, ref) -> dict:
    who = circ.borrower(conn, ref)
    refs = circ._refs(who)
    marks = ", ".join("?" for _ in refs)
    loans = circ.current_loans(conn, who)
    now = circ._fmt(datetime.now())
    for loan in loans:
        loan["overdue"] = str(loan["due_date"]) < now
        loan["renewal_blocked"] = circ.renewal_refusal(conn, loan, who)
    holds = _dicts(conn.execute(
        "SELECT r.reservation_id, r.book_id, b.title, r.status, r.priority_order, r.ready_at, "
        "r.collect_by, (SELECT COUNT(*) FROM book_reservations x WHERE x.book_id = r.book_id "
        "AND x.status = 'active' AND (COALESCE(x.priority_order, 0) < COALESCE(r.priority_order, "
        "0) OR (COALESCE(x.priority_order, 0) = COALESCE(r.priority_order, 0) AND "
        "x.reservation_id < r.reservation_id))) + 1 AS position FROM book_reservations r "
        f"JOIN books b ON b.book_id = r.book_id WHERE r.user_id IN ({marks}) AND r.status IN "
        "('active', 'ready') ORDER BY r.status DESC, r.reservation_date", refs))
    history = _dicts(conn.execute(
        "SELECT l.loan_id, b.title, l.checkout_date, l.return_date, l.status, l.fine_amount "
        f"FROM book_loans l LEFT JOIN books b ON b.book_id = l.book_id WHERE l.user_id IN "
        f"({marks}) AND l.status NOT IN ('active', 'overdue') ORDER BY l.checkout_date DESC "
        "LIMIT 50", refs))
    charges = _dicts(conn.execute(
        "SELECT charge_id, kind, amount, status, note, created_at FROM library_charges "
        f"WHERE borrower_ref IN ({marks}) ORDER BY created_at DESC", refs))
    rules = circ.borrower_rules(conn, who["category"])
    return {"borrower": who, "rules": rules, "loans": loans, "holds": holds, "history": history,
            "charges": charges, "owed": circ.open_charges(conn, who),
            "blocks": circ.blocks(conn, who)}


def search_titles(conn, text, limit=50) -> list[dict]:
    like = f"%{str(text or '').strip()}%"
    return _dicts(conn.execute(
        "SELECT b.book_id, b.title, b.author, b.classmark, (SELECT COUNT(*) FROM library_copies c "
        "WHERE c.book_id = b.book_id AND c.status = 'available') AS on_shelf, (SELECT COUNT(*) "
        "FROM library_copies c WHERE c.book_id = b.book_id AND c.status NOT IN ('withdrawn', "
        "'lost')) AS copies FROM books b WHERE b.title LIKE ? OR b.author LIKE ? OR b.isbn = ? "
        "ORDER BY b.title LIMIT ?", (like, like, str(text or "").strip(), limit)))


# ── module reading lists ────────────────────────────────────────────────


def module_lists(conn, module_code=None) -> list[dict]:
    circ.ensure(conn)
    sql = ("SELECT list_id, name, module_code, (SELECT COUNT(*) FROM reading_list_items i "
           "WHERE i.list_id = r.list_id) AS items FROM reading_lists r")
    params = []
    if module_code:
        sql += " WHERE module_code = ?"
        params.append(module_code)
    return _dicts(conn.execute(sql + " ORDER BY module_code, name", params))


def link_list(conn, list_id, module_code):
    circ.ensure(conn)
    module_code = (module_code or "").strip() or None
    if module_code and not conn.execute("SELECT 1 FROM modules WHERE module_code = ?",
                                        (module_code,)).fetchone():
        raise ValueError(f"No module {module_code}")
    if not conn.execute("UPDATE reading_lists SET module_code = ? WHERE list_id = ?",
                        (module_code, list_id)).rowcount:
        raise ValueError("No such reading list")


def set_importance(conn, item_id, importance):
    circ.ensure(conn)
    if importance not in circ.schema.IMPORTANCE:
        raise ValueError(f"Importance is one of: {', '.join(circ.schema.IMPORTANCE)}")
    if not conn.execute("UPDATE reading_list_items SET importance = ? WHERE item_id = ?",
                        (importance, item_id)).rowcount:
        raise ValueError("No such reading list item")


def holdings_check(conn, list_id) -> dict:
    """Each item with its lendable copies against what the module needs."""
    circ.ensure(conn)
    lst = _one(conn, "SELECT list_id, name, module_code FROM reading_lists WHERE list_id = ?",
               (list_id,))
    if not lst:
        raise ValueError("No such reading list")
    students = conn.execute("SELECT COUNT(*) FROM student_modules WHERE module_code = ? AND "
                            "LOWER(COALESCE(status, '')) = 'enrolled'",
                            (lst["module_code"],)).fetchone()[0] if lst["module_code"] else 0
    items = []
    for item in _dicts(conn.execute(
            "SELECT i.item_id, i.book_id, COALESCE(i.importance, 'recommended') AS importance, "
            "b.title, b.author, b.isbn, (SELECT COUNT(*) FROM library_copies c WHERE c.book_id = "
            "i.book_id AND c.item_type <> 'reference' AND c.status NOT IN ('lost', 'withdrawn', "
            "'missing', 'on_order')) AS lendable FROM reading_list_items i LEFT JOIN books b "
            "ON b.book_id = i.book_id WHERE i.list_id = ? ORDER BY i.order_index, i.item_id",
            (list_id,))):
        ratio = {"essential": ESSENTIAL_RATIO, "recommended": RECOMMENDED_RATIO}.get(
            item["importance"])
        needed = math.ceil(students / ratio) if ratio and students else (1 if ratio else 0)
        items.append(dict(item, needed=needed, shortfall=max(needed - item["lendable"], 0)))
    return {"list": lst, "students": students, "items": items}


def request_shortfall(conn, list_id, actor) -> int:
    """Raise a purchase request for every item the list is short of."""
    check = holdings_check(conn, list_id)
    made = 0
    for item in check["items"]:
        if not item["shortfall"]:
            continue
        module = check["list"]["module_code"] or "no module"
        reason = (f"Reading list '{check['list']['name']}' ({module}): {item['importance']}, "
                  f"{check['students']} students, {item['lendable']} copies — "
                  f"{item['shortfall']} more needed")
        if conn.execute("SELECT 1 FROM book_requests WHERE isbn IS ? AND title = ? AND status = "
                        "'pending'", (item["isbn"], item["title"])).fetchone():
            continue
        conn.execute("INSERT INTO book_requests (user_id, title, author, isbn, reason, status, "
                     "priority, requested_date) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
                     (actor, item["title"], item["author"], item["isbn"], reason,
                      "high" if item["importance"] == "essential" else "normal",
                      circ._fmt(datetime.now())))
        made += 1
    return made


# ── acquisitions ────────────────────────────────────────────────────────


def set_fund(conn, fund_code, name, academic_year, allocation, department=None):
    circ.ensure(conn)
    try:
        allocation = round(float(allocation), 2)
    except (TypeError, ValueError):
        raise ValueError("The allocation must be a number") from None
    if not (fund_code or "").strip() or not (name or "").strip() or allocation < 0:
        raise ValueError("A fund needs a code, a name and a non-negative allocation")
    conn.execute("INSERT INTO library_funds VALUES (?, ?, ?, ?, ?) ON CONFLICT(fund_code) DO "
                 "UPDATE SET name = excluded.name, department = excluded.department, "
                 "academic_year = excluded.academic_year, allocation = excluded.allocation",
                 (fund_code.strip().upper(), name.strip(), department, str(academic_year).strip(),
                  allocation))


def fund_position(conn, fund_code=None) -> list[dict]:
    circ.ensure(conn)
    rows = _dicts(conn.execute(
        "SELECT f.*, COALESCE((SELECT SUM((o.quantity - o.received_qty) * o.unit_price) FROM "
        "library_orders o WHERE o.fund_code = f.fund_code AND o.status IN ('ordered', "
        "'part_received')), 0) AS committed, COALESCE((SELECT SUM(o.received_qty * o.unit_price) "
        "FROM library_orders o WHERE o.fund_code = f.fund_code), 0) AS spent FROM library_funds f"
        + (" WHERE f.fund_code = ?" if fund_code else "") + " ORDER BY f.fund_code",
        (fund_code,) if fund_code else ()))
    for r in rows:
        r["remaining"] = round(r["allocation"] - r["committed"] - r["spent"], 2)
    return rows


def requests(conn, status="pending") -> list[dict]:
    return _dicts(conn.execute("SELECT * FROM book_requests WHERE status = ? ORDER BY "
                               "CASE priority WHEN 'high' THEN 0 ELSE 1 END, requested_date",
                               (status,)))


def place_order(conn, *, supplier, fund_code, quantity, unit_price, title=None, author=None,
                isbn=None, book_id=None, request_id=None, item_type="standard", actor=None,
                force=False) -> int:
    circ.ensure(conn)
    if request_id:
        req = _one(conn, "SELECT * FROM book_requests WHERE request_id = ?", (request_id,))
        if not req:
            raise ValueError("No such purchase request")
        title, author, isbn = title or req["title"], author or req["author"], isbn or req["isbn"]
    if book_id:
        book = _one(conn, "SELECT title, author, isbn FROM books WHERE book_id = ?", (book_id,))
        if not book:
            raise ValueError(f"No title {book_id}")
        title, author, isbn = book["title"], book["author"], book["isbn"]
    try:
        quantity, unit_price = int(quantity), round(float(unit_price), 2)
    except (TypeError, ValueError):
        raise ValueError("Quantity and price must be numbers") from None
    if not (title or "").strip() or not (supplier or "").strip() or quantity <= 0 or unit_price < 0:
        raise ValueError("An order needs a title, a supplier, a quantity and a price")
    if item_type not in circ.schema.ITEM_TYPES:
        raise ValueError(f"Item type is one of: {', '.join(circ.schema.ITEM_TYPES)}")
    fund = fund_position(conn, (fund_code or "").upper())
    if not fund:
        raise ValueError(f"No fund {fund_code}")
    if quantity * unit_price > fund[0]["remaining"] and not force:
        raise ValueError(f"Over budget: £{quantity * unit_price:.2f} ordered, £"
                         f"{fund[0]['remaining']:.2f} left in {fund[0]['fund_code']}")
    cur = conn.execute("INSERT INTO library_orders (request_id, book_id, title, author, isbn, "
                       "supplier, fund_code, quantity, unit_price, item_type, ordered_by) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (request_id, book_id, title.strip(), author, isbn, supplier.strip(),
                        fund[0]["fund_code"], quantity, unit_price, item_type, actor))
    if request_id:
        conn.execute("UPDATE book_requests SET status = 'ordered', processed_date = ?, "
                     "processed_by = ? WHERE request_id = ?",
                     (circ._fmt(datetime.now()), actor, request_id))
    return int(cur.lastrowid)


def _new_title(conn, order):
    book_id = f"BK-{(order['isbn'] or uuid.uuid4().hex[:10]).replace('-', '')}"
    while conn.execute("SELECT 1 FROM books WHERE book_id = ?", (book_id,)).fetchone():
        book_id = f"BK-{uuid.uuid4().hex[:10]}"
    existing = order["isbn"] and _one(conn, "SELECT book_id FROM books WHERE isbn = ?",
                                      (order["isbn"],))
    if existing:
        return existing["book_id"]
    conn.execute("INSERT INTO books (book_id, title, author, isbn, status, added_date, quantity, "
                 "available_quantity, purchase_price, supplier, purchase_date) VALUES "
                 "(?, ?, ?, ?, 'available', ?, 0, 0, ?, ?, date('now'))",
                 (book_id, order["title"], order["author"] or "Unknown", order["isbn"],
                  circ._fmt(datetime.now()), order["unit_price"], order["supplier"]))
    return book_id


def receive(conn, order_id, quantity, location=None) -> list[str]:
    """Book in copies from an order; creates the title the first time."""
    order = _one(conn, "SELECT * FROM library_orders WHERE order_id = ?", (order_id,))
    if not order or order["status"] in ("received", "cancelled"):
        raise ValueError("That order is not open")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValueError("Say how many arrived") from None
    outstanding = order["quantity"] - order["received_qty"]
    if not 1 <= quantity <= outstanding:
        raise ValueError(f"Between 1 and {outstanding} copies are still due on this order")
    book_id = order["book_id"] or _new_title(conn, order)
    made = circ.add_copies(conn, book_id, quantity, order["item_type"], location,
                           order["unit_price"])
    received = order["received_qty"] + quantity
    conn.execute("UPDATE library_orders SET book_id = ?, received_qty = ?, status = ?, "
                 "received_at = ? WHERE order_id = ?",
                 (book_id, received, "received" if received == order["quantity"] else
                  "part_received", circ._fmt(datetime.now()), order_id))
    if received == order["quantity"] and order["request_id"]:
        conn.execute("UPDATE book_requests SET status = 'fulfilled' WHERE request_id = ?",
                     (order["request_id"],))
    return made


def cancel_order(conn, order_id, reason):
    if not (reason or "").strip():
        raise ValueError("Record why the order is cancelled")
    if not conn.execute("UPDATE library_orders SET status = 'cancelled', cancelled_reason = ? "
                        "WHERE order_id = ? AND status = 'ordered'", (reason.strip(), order_id)
                        ).rowcount:
        raise ValueError("Only an order with nothing received can be cancelled")


def orders(conn, open_only=True) -> list[dict]:
    circ.ensure(conn)
    where = " WHERE status IN ('ordered', 'part_received')" if open_only else ""
    # db-audit: ignore[DBW001] - literal clause
    return _dicts(conn.execute(f"SELECT * FROM library_orders{where} ORDER BY ordered_at DESC"))


# ── stocktake ───────────────────────────────────────────────────────────


def locations(conn) -> list[str]:
    circ.ensure(conn)
    return [r[0] for r in conn.execute("SELECT DISTINCT location FROM library_copies WHERE "
                                       "TRIM(COALESCE(location, '')) <> '' ORDER BY location")]


def start_stocktake(conn, location, actor) -> int:
    circ.ensure(conn)
    if location not in locations(conn):
        raise ValueError("Choose a location that holds copies")
    if conn.execute("SELECT 1 FROM library_stocktakes WHERE location = ? AND finished_at IS NULL",
                    (location,)).fetchone():
        raise ValueError(f"A stocktake of {location} is already in progress")
    return int(conn.execute("INSERT INTO library_stocktakes (location, started_by) VALUES (?, ?)",
                            (location, actor)).lastrowid)


def scan(conn, stocktake_id, barcode) -> str:
    """Record a barcode seen on the shelf; returns what to tell the scanner."""
    take = _one(conn, "SELECT * FROM library_stocktakes WHERE stocktake_id = ? AND finished_at "
                      "IS NULL", (stocktake_id,))
    if not take:
        raise ValueError("That stocktake is not open")
    barcode = str(barcode or "").strip()
    conn.execute("INSERT OR IGNORE INTO library_stocktake_scans (stocktake_id, barcode) VALUES "
                 "(?, ?)", (stocktake_id, barcode))
    copy = _one(conn, "SELECT c.*, b.title FROM library_copies c JOIN books b ON b.book_id = "
                      "c.book_id WHERE c.barcode = ?", (barcode,))
    if not copy:
        return "unknown barcode — not in the catalogue"
    notes = []
    if copy["location"] != take["location"]:
        notes.append(f"belongs in {copy['location'] or 'no location'}")
    if copy["status"] in ("on_loan", "lost", "missing", "withdrawn"):
        notes.append(f"recorded as {copy['status'].replace('_', ' ')}")
    return f"{copy['title']}" + (f" — {'; '.join(notes)}" if notes else " — OK")


def stocktake_progress(conn, stocktake_id) -> dict:
    take = _one(conn, "SELECT * FROM library_stocktakes WHERE stocktake_id = ?", (stocktake_id,))
    if not take:
        raise ValueError("No such stocktake")
    expected = _dicts(conn.execute(
        "SELECT c.copy_id, c.barcode, b.title, b.classmark FROM library_copies c JOIN books b "
        "ON b.book_id = c.book_id WHERE c.location = ? AND c.status IN ('available', 'damaged') "
        "ORDER BY b.classmark, b.title", (take["location"],)))
    seen = {r[0] for r in conn.execute("SELECT barcode FROM library_stocktake_scans WHERE "
                                       "stocktake_id = ?", (stocktake_id,))}
    return {"stocktake": take, "expected": len(expected), "scanned": len(seen),
            "not_seen": [c for c in expected if c["barcode"] not in seen]}


def finish_stocktake(conn, stocktake_id, mark_missing=True) -> dict:
    progress = stocktake_progress(conn, stocktake_id)
    if progress["stocktake"]["finished_at"]:
        raise ValueError("That stocktake is already finished")
    now = circ._fmt(datetime.now())
    conn.execute("UPDATE library_copies SET last_seen = ? WHERE barcode IN (SELECT barcode FROM "
                 "library_stocktake_scans WHERE stocktake_id = ?)", (now, stocktake_id))
    missing = progress["not_seen"] if mark_missing else []
    books = set()
    for c in missing:
        conn.execute("UPDATE library_copies SET status = 'missing' WHERE copy_id = ?",
                     (c["copy_id"],))
        books.add(conn.execute("SELECT book_id FROM library_copies WHERE copy_id = ?",
                               (c["copy_id"],)).fetchone()[0])
    for book_id in books:
        circ.sync_title(conn, book_id)
    conn.execute("UPDATE library_stocktakes SET finished_at = ?, missing_marked = ? WHERE "
                 "stocktake_id = ?", (now, len(missing), stocktake_id))
    return {"scanned": progress["scanned"], "missing": [c["barcode"] for c in missing]}


# ── leavers ─────────────────────────────────────────────────────────────


def outstanding(conn, ref) -> dict:
    who = circ.borrower(conn, ref)
    return {"borrower": who, "loans": circ.current_loans(conn, who),
            "owed": circ.open_charges(conn, who)}


def leavers(conn) -> list[dict]:
    """Students whose studies have ended but who still hold items or owe money."""
    circ.ensure(conn)
    out = []
    for sid, status in conn.execute(
            "SELECT student_id, COALESCE(status, '') FROM students WHERE COALESCE(is_active, 1) = 0 "
            "OR LOWER(COALESCE(status, '')) IN ('withdrawn', 'graduated', 'completed', "
            "'inactive', 'transferred')").fetchall():
        state = outstanding(conn, sid)
        if state["loans"] or state["owed"]:
            out.append({"student_id": sid, "status": status, "name": state["borrower"]["name"],
                        "loans": len(state["loans"]), "owed": state["owed"],
                        "email": state["borrower"]["email"]})
    return out


def notify_leaver(conn, student_id) -> list:
    """Tell a departing student what they still need to return or pay."""
    state = outstanding(conn, student_id)
    if not state["loans"] and not state["owed"]:
        return []
    lines = [f"• {l['title'] or l['book_id']} (due {str(l['due_date'])[:10]})" for l in
             state["loans"]]
    body = ("Your studies are ending, but your library account is not clear.\n\n"
            + ("Please return:\n" + "\n".join(lines) + "\n\n" if lines else "")
            + (f"Outstanding library charges: £{state['owed']:.2f}\n\n" if state["owed"] else "")
            + "Contact the library if you think this is wrong.")
    return circ._notice(conn, student_id, "Library account: items or charges outstanding", body)


# ── e-resources ─────────────────────────────────────────────────────────


_ERESOURCE_FIELDS = ("title", "provider", "resource_type", "url", "concurrent_users",
                     "annual_cost", "start_date", "renewal_date", "notice_days", "status",
                     "owner", "notes")


def _clean_eresource(values: dict) -> dict:
    clean = {k: (str(values.get(k)).strip() or None) if values.get(k) is not None else None
             for k in _ERESOURCE_FIELDS}
    if not clean["title"]:
        raise ValueError("Give the resource a title")
    try:
        for key, cast in (("concurrent_users", int), ("annual_cost", float), ("notice_days", int)):
            clean[key] = cast(clean[key]) if clean[key] is not None else None
        for key in ("start_date", "renewal_date"):
            if clean[key]:
                date.fromisoformat(clean[key][:10])
    except ValueError:
        raise ValueError("Users, cost and notice period must be numbers; dates YYYY-MM-DD") \
            from None
    clean["notice_days"] = 90 if clean["notice_days"] is None else clean["notice_days"]
    clean["status"] = clean["status"] or "active"
    if clean["status"] not in ("trial", "active", "cancelled"):
        raise ValueError("Status is trial, active or cancelled")
    return clean


def save_eresource(conn, values: dict, resource_id=None) -> int:
    circ.ensure(conn)
    fields = _ERESOURCE_FIELDS
    clean = _clean_eresource(values)
    if resource_id:
        sets = ", ".join(f"{k} = ?" for k in fields)
        # db-audit: ignore[DBW001] - field names are literals
        conn.execute(f"UPDATE library_eresources SET {sets} WHERE resource_id = ?",
                     (*[clean[k] for k in fields], resource_id))
        return int(resource_id)
    # db-audit: ignore[DBW001] - field names are literals
    return int(conn.execute(f"INSERT INTO library_eresources ({', '.join(fields)}) VALUES "
                            f"({', '.join('?' for _ in fields)})",
                            [clean[k] for k in fields]).lastrowid)


def record_usage(conn, resource_id, period, uses):
    circ.ensure(conn)
    if not (len(str(period)) == 7 and str(period)[4] == "-"):
        raise ValueError("Usage period is a month, YYYY-MM")
    try:
        uses = int(uses)
    except (TypeError, ValueError):
        raise ValueError("Uses must be a whole number") from None
    if uses < 0:
        raise ValueError("Uses cannot be negative")
    conn.execute("INSERT OR REPLACE INTO library_eresource_usage VALUES (?, ?, ?)",
                 (resource_id, period, uses))


def eresources(conn, today=None) -> list[dict]:
    """Each resource with its last 12 months' use, cost per use and whether
    its renewal decision is due (inside the notice period)."""
    circ.ensure(conn)
    today = today or date.today()
    since = (today.replace(day=1) - timedelta(days=365)).strftime("%Y-%m")
    rows = _dicts(conn.execute(
        "SELECT r.*, COALESCE((SELECT SUM(u.uses) FROM library_eresource_usage u WHERE "
        "u.resource_id = r.resource_id AND u.period >= ?), 0) AS uses_12m FROM "
        "library_eresources r ORDER BY r.status, r.renewal_date", (since,)))
    for r in rows:
        r["cost_per_use"] = round(r["annual_cost"] / r["uses_12m"], 2) \
            if r["annual_cost"] and r["uses_12m"] else None
        renewal = date.fromisoformat(r["renewal_date"][:10]) if r["renewal_date"] else None
        r["decision_due"] = bool(renewal and r["status"] != "cancelled" and
                                 renewal - timedelta(days=r["notice_days"] or 0) <= today)
    return rows
