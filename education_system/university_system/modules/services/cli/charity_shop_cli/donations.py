"""
Donation and donor management: recording, receipts, drives, thank-you letters.
"""

from ._imports import (
    sqlite3, random, logger, datetime,
    get_connection, List, Dict, Any, Optional,
    DONATIONS_TABLE, DONORS_TABLE,
    ACTIVITY_LOGGER_AVAILABLE, log_create,
)


def record_donation(donor_id: int, item_description: str, category: str = None,
                   quantity: int = 1, estimated_value: float = None,
                   donation_drive_id: str = None, notes: str = None) -> Optional[int]:
    """Log donated items with donor info."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        receipt_number = f"DON-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        cursor.execute(f"""
            INSERT INTO {DONATIONS_TABLE}
            (donor_id, item_description, category, quantity, estimated_value,
             date_received, receipt_number, donation_drive_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (donor_id, item_description, category, quantity, estimated_value,
              datetime.now().strftime("%Y-%m-%d"), receipt_number, donation_drive_id, notes))

        donation_id = cursor.lastrowid

        # Update donor totals
        cursor.execute(f"""
            UPDATE {DONORS_TABLE}
            SET total_donations = total_donations + 1,
                total_value = total_value + COALESCE(?, 0)
            WHERE id = ?
        """, (estimated_value, donor_id))

        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_donation', donation_id=donation_id,
                       donor_id=donor_id, description=item_description)

        return donation_id
    except sqlite3.Error as e:
        logger.error(f"Error recording donation: {e}")
        return None


def generate_donation_receipt(donation_id: int) -> Optional[Dict]:
    """Create tax receipts for donors."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT dn.*, d.name, d.email, d.address
        FROM {DONATIONS_TABLE} dn
        JOIN {DONORS_TABLE} d ON dn.donor_id = d.id
        WHERE dn.id = ?
    """, (donation_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        'receipt_number': row[7],
        'date': row[6],
        'donor_name': row[10],
        'donor_email': row[11],
        'donor_address': row[12],
        'item_description': row[2],
        'category': row[3],
        'quantity': row[4],
        'estimated_value': row[5],
        'organization': 'University Charity Shop',
        'tax_id': 'XX-XXXXXXX',  # Would be real tax ID
        'statement': 'This receipt confirms that the above items were donated. '
                    'No goods or services were provided in exchange for this donation.'
    }


def donor_database(action: str, **kwargs) -> Any:
    """Track donor information and history."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'add':
        name = kwargs.get('name')
        email = kwargs.get('email')
        phone = kwargs.get('phone')
        address = kwargs.get('address')
        notes = kwargs.get('notes')

        cursor.execute(f"""
            INSERT INTO {DONORS_TABLE} (name, email, phone, address, date_registered, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, phone, address, datetime.now().strftime("%Y-%m-%d"), notes))

        donor_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return donor_id

    elif action == 'get':
        donor_id = kwargs.get('donor_id')
        cursor.execute(f"SELECT * FROM {DONORS_TABLE} WHERE id = ?", (donor_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'phone': row[3],
                'address': row[4],
                'date_registered': row[5],
                'total_donations': row[6],
                'total_value': row[7],
                'notes': row[8]
            }
        return None

    elif action == 'search':
        search_term = kwargs.get('term', '')
        cursor.execute(f"""
            SELECT * FROM {DONORS_TABLE}
            WHERE name LIKE ? OR email LIKE ?
        """, (f"%{search_term}%", f"%{search_term}%"))

        donors = []
        for row in cursor.fetchall():
            donors.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'total_donations': row[6],
                'total_value': row[7]
            })
        conn.close()
        return donors

    elif action == 'list':
        cursor.execute(f"SELECT * FROM {DONORS_TABLE} ORDER BY name")
        donors = []
        for row in cursor.fetchall():
            donors.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'total_donations': row[6],
                'total_value': row[7]
            })
        conn.close()
        return donors

    conn.close()
    return None


def donation_value_estimator(category: str, condition: str, description: str = "") -> float:
    """Estimate value for tax purposes based on category and condition."""
    # Base values by category (in GBP)
    base_values = {
        'Books': 3.00,
        'Clothing': 8.00,
        'Electronics': 25.00,
        'Furniture': 50.00,
        'Homeware': 10.00,
        'Toys': 5.00,
        'Music/DVDs': 2.00,
        'Accessories': 7.00,
        'Sports': 15.00,
        'Other': 5.00
    }

    # Condition multipliers
    condition_mult = {
        'New': 1.5,
        'Excellent': 1.2,
        'Good': 1.0,
        'Fair': 0.6,
        'Poor': 0.3
    }

    base = base_values.get(category, 5.00)
    multiplier = condition_mult.get(condition, 1.0)

    return round(base * multiplier, 2)


def donation_drive_tracker(action: str, **kwargs) -> Any:
    """Manage collection events."""
    # Store drives in a simple format within donations table using donation_drive_id
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'summary':
        drive_id = kwargs.get('drive_id')

        cursor.execute(f"""
            SELECT COUNT(*) as donations,
                   SUM(quantity) as items,
                   SUM(estimated_value) as value
            FROM {DONATIONS_TABLE}
            WHERE donation_drive_id = ?
        """, (drive_id,))

        row = cursor.fetchone()
        conn.close()

        return {
            'drive_id': drive_id,
            'total_donations': row[0] or 0,
            'total_items': row[1] or 0,
            'total_value': row[2] or 0
        }

    elif action == 'list_drives':
        cursor.execute(f"""
            SELECT DISTINCT donation_drive_id,
                   COUNT(*) as donations,
                   SUM(estimated_value) as value,
                   MIN(date_received) as start_date,
                   MAX(date_received) as end_date
            FROM {DONATIONS_TABLE}
            WHERE donation_drive_id IS NOT NULL
            GROUP BY donation_drive_id
        """)

        drives = []
        for row in cursor.fetchall():
            drives.append({
                'drive_id': row[0],
                'donations': row[1],
                'total_value': row[2],
                'start_date': row[3],
                'end_date': row[4]
            })
        conn.close()
        return drives

    conn.close()
    return None


def thank_you_letter_generator(donor_id: int, year: int = None) -> Dict:
    """Generate automated donor appreciation letter."""
    if not year:
        year = datetime.now().year

    conn = get_connection()
    cursor = conn.cursor()

    # Get donor info
    cursor.execute(f"SELECT name, email, address FROM {DONORS_TABLE} WHERE id = ?", (donor_id,))
    donor = cursor.fetchone()

    if not donor:
        conn.close()
        return {}

    # Get year's donations
    cursor.execute(f"""
        SELECT COUNT(*), SUM(quantity), SUM(estimated_value)
        FROM {DONATIONS_TABLE}
        WHERE donor_id = ? AND strftime('%Y', date_received) = ?
    """, (donor_id, str(year)))
    stats = cursor.fetchone()

    conn.close()

    letter = {
        'donor_name': donor[0],
        'donor_email': donor[1],
        'donor_address': donor[2],
        'year': year,
        'donation_count': stats[0] or 0,
        'items_donated': stats[1] or 0,
        'total_value': stats[2] or 0,
        'letter_text': f"""
Dear {donor[0]},

Thank you for your generous donations to the University Charity Shop during {year}.

Your {stats[0] or 0} donation(s) totaling {stats[1] or 0} items with an estimated value of
\u00a3{stats[2] or 0:.2f} have made a real difference in our community.

Your support helps us:
- Provide affordable items to students and community members
- Reduce waste through recycling and reuse
- Fund university programs and scholarships

We truly appreciate your continued support and look forward to your future contributions.

With gratitude,
University Charity Shop Team
"""
    }

    return letter
