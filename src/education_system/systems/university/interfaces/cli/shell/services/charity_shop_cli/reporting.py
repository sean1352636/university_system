"""
All reports, revenue analytics, profit margins, and trend analysis.
"""

from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli._imports import (
    sqlite3, logger, datetime, timedelta,
    get_connection, List, Dict,
    TABLE_NAME, SALES_TABLE, DONORS_TABLE, DONATIONS_TABLE,
)


def calculate_profit_margin(item_id: int = None, category: str = None) -> Dict:
    """Show profit after donation costs."""
    conn = get_connection()
    cursor = conn.cursor()

    if item_id:
        cursor.execute(f"""
            SELECT name, price, donation_cost, sold_quantity,
                   (price * sold_quantity) as revenue,
                   (price - COALESCE(donation_cost, 0)) * sold_quantity as profit
            FROM {TABLE_NAME}
            WHERE id = ? AND sold_quantity > 0
        """, (item_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'name': row[0],
                'price': row[1],
                'donation_cost': row[2] or 0,
                'quantity_sold': row[3],
                'revenue': row[4],
                'profit': row[5],
                'margin_percent': (row[5] / row[4] * 100) if row[4] > 0 else 0
            }
        return {}

    else:
        params = []
        query = f"""
            SELECT SUM(price * sold_quantity) as total_revenue,
                   SUM((price - COALESCE(donation_cost, 0)) * sold_quantity) as total_profit
            FROM {TABLE_NAME}
            WHERE sold_quantity > 0
        """
        if category:
            query = query.replace("WHERE", "WHERE category = ? AND")
            params.append(category)

        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            return {
                'total_revenue': row[0],
                'total_profit': row[1],
                'margin_percent': (row[1] / row[0] * 100) if row[0] > 0 else 0
            }
        return {'total_revenue': 0, 'total_profit': 0, 'margin_percent': 0}


def generate_daily_sales_report(date: str = None) -> Dict:
    """Daily sales summary."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT COUNT(*), SUM(total_amount), SUM(quantity)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) = ? AND refunded = 0
    """, (date,))
    row = cursor.fetchone()

    cursor.execute(f"""
        SELECT payment_method, COUNT(*), SUM(total_amount)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) = ? AND refunded = 0
        GROUP BY payment_method
    """, (date,))
    by_payment = cursor.fetchall()

    conn.close()

    return {
        'date': date,
        'total_transactions': row[0] or 0,
        'total_revenue': row[1] or 0,
        'total_items_sold': row[2] or 0,
        'by_payment_method': [{'method': r[0], 'count': r[1], 'amount': r[2]} for r in by_payment]
    }


def generate_weekly_sales_report(start_date: str = None) -> Dict:
    """Weekly performance report."""
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT DATE(sale_date) as day, COUNT(*), SUM(total_amount), SUM(quantity)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND DATE(sale_date) < ? AND refunded = 0
        GROUP BY DATE(sale_date)
        ORDER BY day
    """, (start_date, end_date))
    daily = cursor.fetchall()

    cursor.execute(f"""
        SELECT COUNT(*), SUM(total_amount), SUM(quantity)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND DATE(sale_date) < ? AND refunded = 0
    """, (start_date, end_date))
    totals = cursor.fetchone()

    conn.close()

    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_transactions': totals[0] or 0,
        'total_revenue': totals[1] or 0,
        'total_items_sold': totals[2] or 0,
        'daily_breakdown': [{'date': d[0], 'transactions': d[1], 'revenue': d[2], 'items': d[3]} for d in daily]
    }


def generate_monthly_sales_report(year: int = None, month: int = None) -> Dict:
    """Monthly trends report."""
    if not year:
        year = datetime.now().year
    if not month:
        month = datetime.now().month

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT COUNT(*), SUM(total_amount), SUM(quantity), AVG(total_amount)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND DATE(sale_date) < ? AND refunded = 0
    """, (start_date, end_date))
    totals = cursor.fetchone()

    cursor.execute(f"""
        SELECT strftime('%W', sale_date) as week, COUNT(*), SUM(total_amount)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND DATE(sale_date) < ? AND refunded = 0
        GROUP BY week
    """, (start_date, end_date))
    weekly = cursor.fetchall()

    conn.close()

    return {
        'year': year,
        'month': month,
        'total_transactions': totals[0] or 0,
        'total_revenue': totals[1] or 0,
        'total_items_sold': totals[2] or 0,
        'average_transaction': totals[3] or 0,
        'weekly_breakdown': [{'week': w[0], 'transactions': w[1], 'revenue': w[2]} for w in weekly]
    }


def best_selling_items_report(limit: int = 10, period_days: int = 30) -> List[Dict]:
    """Top performing items."""
    conn = get_connection()
    cursor = conn.cursor()

    start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT s.name, s.category, SUM(sl.quantity) as qty_sold,
               SUM(sl.total_amount) as revenue, s.price
        FROM {SALES_TABLE} sl
        JOIN {TABLE_NAME} s ON sl.item_id = s.id
        WHERE DATE(sl.sale_date) >= ? AND sl.refunded = 0
        GROUP BY sl.item_id
        ORDER BY qty_sold DESC
        LIMIT ?
    """, (start_date, limit))

    results = []
    for row in cursor.fetchall():
        results.append({
            'name': row[0],
            'category': row[1],
            'quantity_sold': row[2],
            'revenue': row[3],
            'unit_price': row[4]
        })

    conn.close()
    return results


def slow_moving_items_report(days_threshold: int = 60) -> List[Dict]:
    """Items not selling."""
    conn = get_connection()
    cursor = conn.cursor()

    cutoff_date = (datetime.now() - timedelta(days=days_threshold)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT id, name, category, price, quantity, date_added,
               julianday('now') - julianday(date_added) as days_in_stock
        FROM {TABLE_NAME}
        WHERE sold = 0 AND quantity > 0 AND date_added <= ?
        ORDER BY date_added ASC
    """, (cutoff_date,))

    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'name': row[1],
            'category': row[2],
            'price': row[3],
            'quantity': row[4],
            'date_added': row[5],
            'days_in_stock': int(row[6])
        })

    conn.close()
    return results


def revenue_trend_analysis(period: str = 'monthly', num_periods: int = 12) -> List[Dict]:
    """Revenue over time analysis."""
    conn = get_connection()
    cursor = conn.cursor()

    if period == 'daily':
        group_format = '%Y-%m-%d'
        days_back = num_periods
    elif period == 'weekly':
        group_format = '%Y-W%W'
        days_back = num_periods * 7
    else:  # monthly
        group_format = '%Y-%m'
        days_back = num_periods * 30

    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT strftime(?, sale_date) as period,
               COUNT(*) as transactions,
               SUM(total_amount) as revenue,
               SUM(quantity) as items
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND refunded = 0
        GROUP BY period
        ORDER BY period
    """, (group_format, start_date))

    results = []
    for row in cursor.fetchall():
        results.append({
            'period': row[0],
            'transactions': row[1],
            'revenue': row[2],
            'items_sold': row[3]
        })

    conn.close()
    return results


def category_performance_comparison(period_days: int = 30) -> List[Dict]:
    """Compare category sales."""
    conn = get_connection()
    cursor = conn.cursor()

    start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT s.category,
               COUNT(DISTINCT sl.id) as transactions,
               SUM(sl.quantity) as items_sold,
               SUM(sl.total_amount) as revenue,
               AVG(sl.total_amount) as avg_sale
        FROM {SALES_TABLE} sl
        JOIN {TABLE_NAME} s ON sl.item_id = s.id
        WHERE DATE(sl.sale_date) >= ? AND sl.refunded = 0
        GROUP BY s.category
        ORDER BY revenue DESC
    """, (start_date,))

    results = []
    for row in cursor.fetchall():
        results.append({
            'category': row[0],
            'transactions': row[1],
            'items_sold': row[2],
            'revenue': row[3],
            'average_sale': row[4]
        })

    conn.close()
    return results


def seasonal_trends_report() -> Dict:
    """Identify seasonal patterns."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT strftime('%m', sale_date) as month,
               COUNT(*) as transactions,
               SUM(total_amount) as revenue
        FROM {SALES_TABLE}
        WHERE refunded = 0
        GROUP BY month
        ORDER BY month
    """)

    monthly = {}
    for row in cursor.fetchall():
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_idx = int(row[0]) - 1
        monthly[month_names[month_idx]] = {
            'transactions': row[1],
            'revenue': row[2]
        }

    # By day of week
    cursor.execute(f"""
        SELECT strftime('%w', sale_date) as day,
               COUNT(*) as transactions,
               SUM(total_amount) as revenue
        FROM {SALES_TABLE}
        WHERE refunded = 0
        GROUP BY day
    """)

    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    daily = {}
    for row in cursor.fetchall():
        daily[day_names[int(row[0])]] = {
            'transactions': row[1],
            'revenue': row[2]
        }

    conn.close()

    return {
        'by_month': monthly,
        'by_day_of_week': daily
    }


def donor_contribution_report(period_days: int = 365) -> List[Dict]:
    """Track donations by source."""
    conn = get_connection()
    cursor = conn.cursor()

    start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT d.name, d.email,
               COUNT(dn.id) as donation_count,
               SUM(dn.quantity) as items_donated,
               SUM(dn.estimated_value) as total_value
        FROM {DONORS_TABLE} d
        LEFT JOIN {DONATIONS_TABLE} dn ON d.id = dn.donor_id
        WHERE dn.date_received >= ?
        GROUP BY d.id
        ORDER BY total_value DESC
    """, (start_date,))

    results = []
    for row in cursor.fetchall():
        results.append({
            'name': row[0],
            'email': row[1],
            'donation_count': row[2],
            'items_donated': row[3],
            'total_value': row[4]
        })

    conn.close()
    return results


def tax_deduction_report(year: int = None) -> List[Dict]:
    """Generate donation receipts for tax purposes."""
    if not year:
        year = datetime.now().year

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT d.id, d.name, d.email, d.address,
               SUM(dn.estimated_value) as total_value,
               COUNT(dn.id) as donation_count
        FROM {DONORS_TABLE} d
        JOIN {DONATIONS_TABLE} dn ON d.id = dn.donor_id
        WHERE strftime('%Y', dn.date_received) = ?
        GROUP BY d.id
        ORDER BY d.name
    """, (str(year),))

    results = []
    for row in cursor.fetchall():
        results.append({
            'donor_id': row[0],
            'name': row[1],
            'email': row[2],
            'address': row[3],
            'total_deductible': row[4],
            'donation_count': row[5],
            'tax_year': year
        })

    conn.close()
    return results
