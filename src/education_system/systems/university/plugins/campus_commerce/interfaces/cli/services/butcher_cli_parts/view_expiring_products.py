"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_expiring_products():
    """View products expiring soon"""
    try:
        days = input("\nShow products expiring within (days, default 7): ").strip()
        try:
            days = int(days) if days else 7
        except ValueError:
            days = 7

        cutoff_date = (datetime.now() + timedelta(days=days)).date().isoformat()

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT e.batch_number, p.name, p.category,
                       e.quantity_kg, e.expiry_date, e.received_date
                FROM butcher_product_expiry e
                JOIN products p ON e.product_id = p.source_product_id AND p.source_type = 'butcher'
                WHERE e.status = 'active' AND e.expiry_date <= ?
                ORDER BY e.expiry_date
            ''', (cutoff_date,))

            batches = cursor.fetchall()

            if not batches:
                print(f"\n✅ No products expiring within {days} days")
            else:
                print(f"\n⚠️  PRODUCTS EXPIRING WITHIN {days} DAYS:")
                print("=" * 80)

                for batch in batches:
                    batch_num, name, category, qty, exp_date, recv_date = batch

                    days_until = (datetime.fromisoformat(exp_date).date() - datetime.now().date()).days

                    if days_until < 0:
                        urgency = "🔴 EXPIRED"
                    elif days_until <= 2:
                        urgency = "🟠 URGENT"
                    else:
                        urgency = "🟡 WARNING"

                    print(f"\n{urgency}")
                    print(f"   Product: {name} ({category})")
                    print(f"   Batch: {batch_num}")
                    print(f"   Quantity: {float(qty):.2f}kg")
                    print(f"   Expires: {exp_date} ({days_until} days)")
                    print(f"   Received: {recv_date}")

                print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error viewing expiring products: {e}")
        print(f"❌ Error: {e}")
