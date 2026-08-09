"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def update_service():
    """Update an existing service (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        view_services()

        service_id = input("\nEnter service ID to update (0 to cancel): ").strip()
        if service_id == "0":
            return

        if not service_id.isdigit():
            print("❌ Invalid service ID")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT service_id, service_name, price, duration_minutes, description
                FROM barber_services WHERE service_id = ?
            ''', (service_id,))
            service = cursor.fetchone()

            if not service:
                print("❌ Service not found")
                input("\nPress Enter to continue...")
                return

            svc_id, name, price, duration, desc = service

            print("\nCurrent details:")
            print(f"Name: {name}")
            print(f"Price: GBP {float(price):.2f}")
            print(f"Duration: {duration} minutes")
            print(f"Description: {desc or 'N/A'}")

            print("\nEnter new values (press Enter to keep current):")

            new_name = input(f"Name [{name}]: ").strip() or name

            price_input = input(f"Price (GBP) [{price}]: ").strip()
            new_price = float(price_input) if price_input else price

            duration_input = input(f"Duration (min) [{duration}]: ").strip()
            new_duration = int(duration_input) if duration_input else duration

            new_desc = input(f"Description [{desc or 'N/A'}]: ").strip()
            if not new_desc:
                new_desc = desc

            confirm = input("\nUpdate service? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Update cancelled")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE barber_services
                    SET service_name = ?, price = ?, duration_minutes = ?, description = ?
                    WHERE service_id = ?
                ''', (new_name, new_price, new_duration, new_desc, service_id))

            print("\n✅ Service updated successfully!")

            if ACTIVITY_LOG_AVAILABLE:
                log_activity('update', 'barber_service', details={
                    'service_id': service_id, 'name': new_name
                })

    except Exception as e:
        logger.error(f"Error updating service: {e}")
        print(f"❌ Error updating service: {e}")

    input("\nPress Enter to continue...")
