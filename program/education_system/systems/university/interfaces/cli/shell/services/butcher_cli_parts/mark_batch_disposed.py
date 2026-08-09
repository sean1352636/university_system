"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def mark_batch_disposed():
    """Mark a batch as sold or disposed"""
    try:
        batch_number = input("\nEnter batch number: ").strip()

        if not batch_number:
            print("❌ Batch number cannot be empty")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE butcher_product_expiry
                SET status = 'disposed'
                WHERE batch_number = ?
            ''', (batch_number,))

            if conn.total_changes > 0:
                print(f"\n✅ Batch {batch_number} marked as disposed")
                logger.info(f"Batch {batch_number} marked as disposed")
            else:
                print(f"❌ Batch {batch_number} not found")

    except Exception as e:
        logger.error(f"Error marking batch disposed: {e}")
        print(f"❌ Error: {e}")
