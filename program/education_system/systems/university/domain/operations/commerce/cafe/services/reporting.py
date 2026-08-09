from education_system.systems.university.domain.operations.commerce.cafe import *  # noqa: F401,F403
from education_system.systems.university.domain.operations.commerce.cafe.persistence.schema import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.menu_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.order_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.inventory_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.supplier_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.reservation_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.loyalty_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.schedule_repository import *

def get_sales_summary(period: str = "day") -> Dict:
    """Get sales summary for a period."""
    conn = get_db_connection()
    if not conn:
        return {}

    cursor = conn.cursor()

    _PERIOD_FILTERS = {
        "day": "DATE(order_date) = DATE('now')",
        "week": "DATE(order_date) >= DATE('now', '-7 days')",
        "month": "DATE(order_date) >= DATE('now', 'start of month')",
    }
    date_filter = _PERIOD_FILTERS.get(period, "1=1")

    cursor.execute(f'''
        SELECT COUNT(*), COALESCE(SUM(total_amount), 0)
        FROM orders
        WHERE source_type = 'cafe' AND {date_filter}
    ''')
    result = cursor.fetchone()
    order_count = result[0] or 0
    total_sales = result[1] or 0.0

    cursor.execute(f'''
        SELECT payment_method, COUNT(*), COALESCE(SUM(total_amount), 0)
        FROM orders
        WHERE source_type = 'cafe' AND {date_filter}
        GROUP BY payment_method
    ''')
    payment_breakdown = cursor.fetchall()

    conn.close()

    return {
        'order_count': order_count,
        'total_sales': total_sales,
        'payment_breakdown': payment_breakdown
    }

def get_popular_items(limit: int = 20) -> List[Tuple]:
    """Get most popular items by quantity sold."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute('''
        SELECT item_name, SUM(quantity) as total_qty, SUM(subtotal) as total_sales
        FROM order_items
        WHERE source_type = 'cafe'
        GROUP BY item_name
        ORDER BY total_qty DESC
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def get_low_stock_items(threshold: int = 20) -> List[Tuple]:
    """Get items with low stock."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, category, stock_quantity
        FROM products
        WHERE source_type = 'cafe' AND stock_quantity < ?
        ORDER BY stock_quantity ASC
    ''', (threshold,))
    results = cursor.fetchall()
    conn.close()
    return results

