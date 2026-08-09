from education_system.systems.university.domains.operations.domain.commerce.cafe import *  # noqa: F401,F403
from .schema import get_db_connection

def add_supplier(name: str, contact_person: str, email: str, phone: str, address: str, payment_terms: str) -> Optional[int]:
    """Add a new supplier. Returns supplier_id or None."""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cafe_suppliers (name, contact_person, email, phone, address, payment_terms) VALUES (?, ?, ?, ?, ?, ?)",
            (name, contact_person or None, email or None, phone or None, address or None, payment_terms or None)
        )
        conn.commit()
        supplier_id = cursor.lastrowid
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('cafe_supplier', supplier_name=name)
        return supplier_id
    except sqlite3.Error as e:
        logger.error(f"Error adding supplier: {e}")
        return None

def get_all_suppliers() -> List[Tuple]:
    """Get all suppliers."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT supplier_id, name, contact_person, email, phone, address, payment_terms FROM cafe_suppliers ORDER BY name")
    results = cursor.fetchall()
    conn.close()
    return results

def get_supplier(supplier_id: int) -> Optional[Tuple]:
    """Get a single supplier by ID."""
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT supplier_id, name, contact_person, email, phone, address, payment_terms FROM cafe_suppliers WHERE supplier_id = ?", (supplier_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def update_supplier(supplier_id: int, name: str, contact_person: str, email: str, phone: str, address: str, payment_terms: str) -> bool:
    """Update a supplier."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_suppliers SET name = ?, contact_person = ?, email = ?, phone = ?, address = ?, payment_terms = ? WHERE supplier_id = ?",
            (name, contact_person, email, phone, address, payment_terms, supplier_id)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_supplier', supplier_id=supplier_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating supplier: {e}")
        return False

def delete_supplier(supplier_id: int) -> bool:
    """Delete a supplier."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cafe_supplier_products WHERE supplier_id = ?", (supplier_id,))
        cursor.execute("DELETE FROM cafe_suppliers WHERE supplier_id = ?", (supplier_id,))
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_delete('cafe_supplier', supplier_id=supplier_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting supplier: {e}")
        return False

def link_supplier_to_product(supplier_id: int, product_id: int, cost_per_unit: float = None, notes: str = "") -> bool:
    """Link a supplier to a product/inventory item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cafe_supplier_products (supplier_id, product_id, cost_per_unit, notes) VALUES (?, ?, ?, ?)",
            (supplier_id, product_id, cost_per_unit, notes)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error linking supplier to product: {e}")
        return False

def get_supplier_products(supplier_id: int) -> List[Tuple]:
    """Get products linked to a supplier."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.product_id, p.name, p.category, sp.cost_per_unit, sp.notes
        FROM cafe_supplier_products sp
        JOIN products p ON sp.product_id = p.product_id AND p.source_type = 'cafe'
        WHERE sp.supplier_id = ?
        ORDER BY p.name
    ''', (supplier_id,))
    results = cursor.fetchall()
    conn.close()
    return results
