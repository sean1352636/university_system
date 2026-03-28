"""Textbook Store CLI — browse, search, buy/sell used textbooks, and view orders.

Mirrors every feature of the textbook GUI (textbook_manager.py) but as a
terminal-based menu interface.
"""

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.commerce.services.shop_management import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_id():
    """Return the current user's student_id or username."""
    if config.auth and config.auth.current_user:
        u = config.auth.current_user
        if isinstance(u, dict):
            return u.get("student_id") or u.get("username", "unknown")
        return getattr(u, "student_id", getattr(u, "username", "unknown"))
    return "unknown"


def _init_textbook_tables():
    """Ensure textbook tables exist and seed sample data if empty."""
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
                    "INSERT INTO textbooks (isbn, title, author, edition, publisher, year, module_code, required, price, description) VALUES (?,?,?,?,?,?,?,?,?,?)", s)
            conn.commit()


# ---------------------------------------------------------------------------
# 1. Browse / Search textbooks
# ---------------------------------------------------------------------------

def browse_textbooks():
    """Browse and search the textbook catalogue."""
    _init_textbook_tables()

    search = input("\nSearch textbooks (title/author/ISBN, or press Enter to list all): ").strip()
    module = input("Filter by module code (or press Enter for all): ").strip()

    with get_connection() as conn:
        query = "SELECT * FROM textbooks WHERE 1=1"
        params = []
        if search:
            query += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])
        if module:
            query += " AND module_code = ?"
            params.append(module)
        query += " ORDER BY title"
        rows = conn.execute(query, params).fetchall()

    if not rows:
        print("No textbooks found.")
        return

    print(f"\n{'ID':<5} {'ISBN':<16} {'Title':<35} {'Author':<22} {'Ed.':<5} {'Module':<8} {'Req?':<9} {'Price':<8}")
    print("-" * 108)
    for r in rows:
        req = "Required" if r["required"] else "Optional"
        print(f"{r['textbook_id']:<5} {r['isbn']:<16} {r['title'][:34]:<35} {r['author'][:21]:<22} {r['edition']:<5} {r['module_code']:<8} {req:<9} £{r['price']:.2f}")

    print(f"\n{len(rows)} textbook(s) found.")


# ---------------------------------------------------------------------------
# 2. View textbook details
# ---------------------------------------------------------------------------

def view_textbook_details():
    """View full details for a specific textbook."""
    _init_textbook_tables()

    tid = input("\nEnter textbook ID: ").strip()
    if not tid.isdigit():
        print("Invalid ID.")
        return

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM textbooks WHERE textbook_id = ?", (int(tid),)).fetchone()

    if not row:
        print("Textbook not found.")
        return

    print(f"\n{'=' * 50}")
    print(f"  Title:       {row['title']}")
    print(f"  Author:      {row['author']}")
    print(f"  ISBN:        {row['isbn']}")
    print(f"  Edition:     {row['edition']}")
    print(f"  Publisher:   {row['publisher']}")
    print(f"  Year:        {row['year']}")
    print(f"  Module:      {row['module_code']}")
    print(f"  Type:        {'Required' if row['required'] else 'Optional'}")
    print(f"  Price:       £{row['price']:.2f}")
    print(f"  Description: {row['description']}")
    print(f"{'=' * 50}")


# ---------------------------------------------------------------------------
# 3. My course books
# ---------------------------------------------------------------------------

def my_course_books():
    """Show required/recommended textbooks for the current user's enrolled modules."""
    _init_textbook_tables()
    student_id = _get_user_id()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT t.*,
                   (SELECT COUNT(*) FROM textbook_listings tl
                    WHERE tl.textbook_id = t.textbook_id AND tl.status = 'available') AS used_count
            FROM textbooks t
            WHERE t.module_code IN (SELECT module_code FROM student_modules WHERE student_id = ?)
            ORDER BY t.required DESC, t.module_code, t.title
        """, (student_id,)).fetchall()

    if not rows:
        print("\nNo enrolled modules found, or no textbooks linked to your modules.")
        return

    print(f"\n{'Module':<8} {'Title':<35} {'Author':<22} {'Req?':<9} {'Price':<8} {'Used avail.'}")
    print("-" * 95)
    for r in rows:
        req = "Required" if r["required"] else "Optional"
        used = f"{r['used_count']} available" if r["used_count"] > 0 else "None"
        print(f"{r['module_code']:<8} {r['title'][:34]:<35} {r['author'][:21]:<22} {req:<9} £{r['price']:.2f}  {used}")

    print(f"\n{len(rows)} textbook(s) for your modules.")


# ---------------------------------------------------------------------------
# 4. Used book exchange — browse available listings
# ---------------------------------------------------------------------------

def browse_used_books():
    """Browse available used textbooks from other students."""
    _init_textbook_tables()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT tl.*, t.title
            FROM textbook_listings tl
            JOIN textbooks t ON tl.textbook_id = t.textbook_id
            WHERE tl.status = 'available'
            ORDER BY tl.listed_date DESC
        """).fetchall()

    if not rows:
        print("\nNo used textbooks currently available.")
        return

    print(f"\n{'Listing':<9} {'Title':<35} {'Condition':<11} {'Price':<8} {'Seller':<15} {'Listed':<12}")
    print("-" * 95)
    for r in rows:
        print(f"{r['listing_id']:<9} {r['title'][:34]:<35} {r['condition']:<11} £{r['price']:.2f}  {r['seller_id'][:14]:<15} {r['listed_date']}")

    print(f"\n{len(rows)} listing(s) available.")


# ---------------------------------------------------------------------------
# 5. Find used copies of a specific textbook
# ---------------------------------------------------------------------------

def find_used_copies():
    """Search for used copies of a specific textbook by ID."""
    _init_textbook_tables()

    tid = input("\nEnter textbook ID to find used copies: ").strip()
    if not tid.isdigit():
        print("Invalid ID.")
        return

    with get_connection() as conn:
        book = conn.execute("SELECT title FROM textbooks WHERE textbook_id = ?", (int(tid),)).fetchone()
        if not book:
            print("Textbook not found.")
            return

        rows = conn.execute("""
            SELECT tl.*, t.title
            FROM textbook_listings tl
            JOIN textbooks t ON tl.textbook_id = t.textbook_id
            WHERE tl.textbook_id = ? AND tl.status = 'available'
            ORDER BY tl.price ASC
        """, (int(tid),)).fetchall()

    if not rows:
        print(f"\nNo used copies available for '{book['title']}'.")
        return

    print(f"\nUsed copies of '{book['title']}':")
    print(f"{'Listing':<9} {'Condition':<11} {'Price':<8} {'Seller':<15} {'Listed':<12}")
    print("-" * 60)
    for r in rows:
        print(f"{r['listing_id']:<9} {r['condition']:<11} £{r['price']:.2f}  {r['seller_id'][:14]:<15} {r['listed_date']}")


# ---------------------------------------------------------------------------
# 6. Buy a used textbook
# ---------------------------------------------------------------------------

def buy_used_textbook():
    """Purchase a used textbook listing."""
    _init_textbook_tables()

    lid = input("\nEnter listing ID to buy: ").strip()
    if not lid.isdigit():
        print("Invalid listing ID.")
        return

    user_id = _get_user_id()

    with get_connection() as conn:
        listing = conn.execute("""
            SELECT tl.*, t.title
            FROM textbook_listings tl
            JOIN textbooks t ON tl.textbook_id = t.textbook_id
            WHERE tl.listing_id = ?
        """, (int(lid),)).fetchone()

        if not listing:
            print("Listing not found.")
            return
        if listing["status"] != "available":
            print("This listing is no longer available.")
            return
        if listing["seller_id"] == user_id:
            print("You cannot buy your own listing.")
            return

        print(f"\n  Title:     {listing['title']}")
        print(f"  Condition: {listing['condition']}")
        print(f"  Price:     £{listing['price']:.2f}")
        print(f"  Seller:    {listing['seller_id']}")

        confirm = input("\nConfirm purchase? (y/n): ").strip().lower()
        if confirm != "y":
            print("Purchase cancelled.")
            return

        conn.execute(
            "INSERT INTO textbook_orders (listing_id, buyer_id, seller_id, price, status) VALUES (?, ?, ?, ?, 'pending')",
            (int(lid), user_id, listing["seller_id"], listing["price"]),
        )
        conn.execute("UPDATE textbook_listings SET status = 'sold' WHERE listing_id = ?", (int(lid),))
        conn.commit()

    print("Order placed! Contact the seller to arrange pickup.")


# ---------------------------------------------------------------------------
# 7. Sell a textbook (list for sale)
# ---------------------------------------------------------------------------

def sell_textbook():
    """List a textbook for sale on the exchange."""
    _init_textbook_tables()

    print("\nHow would you like to identify the textbook?")
    print("1. By textbook ID")
    print("2. By ISBN")
    method = input("Choice (1-2): ").strip()

    textbook_id = None

    if method == "1":
        tid = input("Enter textbook ID: ").strip()
        if not tid.isdigit():
            print("Invalid ID.")
            return
        with get_connection() as conn:
            row = conn.execute("SELECT textbook_id, title FROM textbooks WHERE textbook_id = ?", (int(tid),)).fetchone()
        if not row:
            print("Textbook not found.")
            return
        textbook_id = row["textbook_id"]
        print(f"Selected: {row['title']}")

    elif method == "2":
        isbn = input("Enter ISBN: ").strip()
        with get_connection() as conn:
            row = conn.execute("SELECT textbook_id, title FROM textbooks WHERE isbn = ?", (isbn,)).fetchone()
        if not row:
            print("ISBN not found in the textbook catalogue.")
            return
        textbook_id = row["textbook_id"]
        print(f"Found: {row['title']}")

    else:
        print("Invalid choice.")
        return

    print("\nCondition options: like_new, good, fair, poor")
    condition = input("Condition: ").strip().lower()
    if condition not in ("like_new", "good", "fair", "poor"):
        print("Invalid condition. Defaulting to 'good'.")
        condition = "good"

    price_str = input("Asking price (£): ").strip()
    try:
        price = float(price_str)
    except ValueError:
        print("Invalid price.")
        return

    notes = input("Notes (optional): ").strip()
    user_id = _get_user_id()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO textbook_listings (textbook_id, seller_id, condition, price, notes, status) VALUES (?, ?, ?, ?, ?, 'available')",
            (textbook_id, user_id, condition, price, notes),
        )
        conn.commit()

    print("Textbook listed for sale!")


# ---------------------------------------------------------------------------
# 8. View my orders (bought and sold)
# ---------------------------------------------------------------------------

def view_textbook_orders():
    """View the current user's textbook buy/sell orders."""
    _init_textbook_tables()
    user_id = _get_user_id()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT o.*, t.title
            FROM textbook_orders o
            JOIN textbook_listings tl ON o.listing_id = tl.listing_id
            JOIN textbooks t ON tl.textbook_id = t.textbook_id
            WHERE o.buyer_id = ? OR o.seller_id = ?
            ORDER BY o.order_date DESC
        """, (user_id, user_id)).fetchall()

    if not rows:
        print("\nNo textbook orders found.")
        return

    print(f"\n{'Order':<7} {'Title':<35} {'Price':<8} {'Status':<10} {'Date':<20} {'Role'}")
    print("-" * 95)
    for r in rows:
        role = "Buyer" if r["buyer_id"] == user_id else "Seller"
        print(f"{r['order_id']:<7} {r['title'][:34]:<35} £{r['price']:.2f}  {r['status']:<10} {r['order_date'][:19]:<20} {role}")

    print(f"\n{len(rows)} order(s).")


# ---------------------------------------------------------------------------
# 9. View my active listings
# ---------------------------------------------------------------------------

def view_my_listings():
    """View the current user's active textbook listings."""
    _init_textbook_tables()
    user_id = _get_user_id()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT tl.*, t.title
            FROM textbook_listings tl
            JOIN textbooks t ON tl.textbook_id = t.textbook_id
            WHERE tl.seller_id = ?
            ORDER BY tl.listed_date DESC
        """, (user_id,)).fetchall()

    if not rows:
        print("\nYou have no textbook listings.")
        return

    print(f"\n{'Listing':<9} {'Title':<35} {'Condition':<11} {'Price':<8} {'Status':<10} {'Listed'}")
    print("-" * 90)
    for r in rows:
        print(f"{r['listing_id']:<9} {r['title'][:34]:<35} {r['condition']:<11} £{r['price']:.2f}  {r['status']:<10} {r['listed_date']}")

    print(f"\n{len(rows)} listing(s).")


# ---------------------------------------------------------------------------
# 10. Cancel a listing
# ---------------------------------------------------------------------------

def cancel_listing():
    """Cancel one of your own active textbook listings."""
    _init_textbook_tables()
    user_id = _get_user_id()

    lid = input("\nEnter listing ID to cancel: ").strip()
    if not lid.isdigit():
        print("Invalid listing ID.")
        return

    with get_connection() as conn:
        listing = conn.execute(
            "SELECT * FROM textbook_listings WHERE listing_id = ? AND seller_id = ?",
            (int(lid), user_id),
        ).fetchone()

        if not listing:
            print("Listing not found or you are not the seller.")
            return
        if listing["status"] != "available":
            print(f"Cannot cancel — listing status is '{listing['status']}'.")
            return

        confirm = input("Cancel this listing? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return

        conn.execute("UPDATE textbook_listings SET status = 'cancelled' WHERE listing_id = ?", (int(lid),))
        conn.commit()

    print("Listing cancelled.")
