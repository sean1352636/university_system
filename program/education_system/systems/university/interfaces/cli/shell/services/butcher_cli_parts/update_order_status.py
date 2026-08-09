"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def update_order_status():
    """Update order status (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to update orders")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Update Order Status")

        order_number = input("\nEnter order number: ").strip()

        if not order_number:
            print("❌ Order number cannot be empty")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT order_id, user_name, total_amount, order_status, order_date
                FROM orders
                WHERE source_type = 'butcher' AND order_number = ?
            ''', (order_number,))

            order = cursor.fetchone()

            if not order:
                print(f"❌ Order {order_number} not found")
                input("\nPress Enter to continue...")
                return

            order_id, user_name, amount, current_status, order_date = order

            print(f"\n📋 Order: {order_number}")
            print(f"   Customer: {user_name}")
            print(f"   Amount: {format_currency(float(amount))}")
            print(f"   Current Status: {current_status.upper()}")
            print(f"   Ordered: {format_date(order_date)}")

            print("\n📊 New Status:")
            print("1. Pending")
            print("2. Processing")
            print("3. Ready for Pickup")
            print("4. Completed")
            print("5. Cancelled")

            status_choice = input("\nSelect new status (1-5): ").strip()

            status_map = {
                '1': 'pending',
                '2': 'processing',
                '3': 'ready',
                '4': 'completed',
                '5': 'cancelled'
            }

            new_status = status_map.get(status_choice)

            if not new_status:
                print("❌ Invalid status choice")
                input("\nPress Enter to continue...")
                return

            if new_status == current_status:
                print("❌ Status is already set to this value")
                input("\nPress Enter to continue...")
                return

            notes = input("Notes (optional): ").strip()

            confirm = input(f"\nUpdate status from '{current_status}' to '{new_status}'? (yes/no): ").strip().lower()

            if confirm != 'yes':
                print("❌ Update cancelled")
                input("\nPress Enter to continue...")
                return

            # Update status
            with transaction() as trans_conn:
                if new_status == 'completed':
                    trans_conn.execute('''
                        UPDATE orders
                        SET order_status = ?, completed_date = ?, notes = ?
                        WHERE order_id = ? AND source_type = 'butcher'
                    ''', (new_status, datetime.now().isoformat(), notes, order_id))
                else:
                    trans_conn.execute('''
                        UPDATE orders
                        SET order_status = ?, notes = ?
                        WHERE order_id = ? AND source_type = 'butcher'
                    ''', (new_status, notes, order_id))

            print(f"\n✅ Order {order_number} status updated to {new_status.upper()}")

            logger.info(f"Admin updated order {order_number} status to {new_status}")

            # Send email notification if available
            if EMAIL_AVAILABLE:
                try:
                    email_cursor = conn.execute('''
                        SELECT user_email FROM orders WHERE order_id = ? AND source_type = 'butcher'
                    ''', (order_id,))

                    email_result = email_cursor.fetchone()
                    if email_result and email_result[0]:
                        send_email(
                            email_result[0],
                            f'Butcher Shop Order Update - {order_number}',
                            f'Your order {order_number} status has been updated to: {new_status.upper()}'
                        )
                except Exception as e:
                    logger.error(f"Error sending status update email: {e}")

    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")
