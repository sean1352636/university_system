"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def toggle_service_availability():
    """Enable or disable a service (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT service_id, service_name, price, status
                FROM barber_services
                ORDER BY service_name
            ''')
            services = cursor.fetchall()

            if not services:
                print("\n❌ No services found")
                input("\nPress Enter to continue...")
                return

            print_subheader("ALL SERVICES")
            print("\n{:<5} {:<30} {:<12} {:<10}".format("ID", "Service", "Price (GBP)", "Status"))
            print("-" * 60)

            for svc in services:
                svc_id, name, price, status = svc
                print("{:<5} {:<30} {:<12.2f} {:<10}".format(
                    svc_id, name[:29], float(price), status.upper()
                ))

            service_id = input("\nEnter service ID to toggle (0 to cancel): ").strip()
            if service_id == "0":
                return

            if not service_id.isdigit():
                print("❌ Invalid service ID")
                input("\nPress Enter to continue...")
                return

            cursor = conn.execute('''
                SELECT service_name, status FROM barber_services WHERE service_id = ?
            ''', (service_id,))
            service = cursor.fetchone()

            if not service:
                print("❌ Service not found")
                input("\nPress Enter to continue...")
                return

            name, current_status = service
            new_status = 'inactive' if current_status == 'active' else 'active'

            confirm = input(f"\nChange '{name}' status from {current_status} to {new_status}? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Operation cancelled")
                input("\nPress Enter to continue...")
                return

            with transaction() as conn_tx:
                conn_tx.execute('''
                    UPDATE barber_services SET status = ? WHERE service_id = ?
                ''', (new_status, service_id))

            print(f"\n✅ Service status updated to {new_status}!")

            if ACTIVITY_LOG_AVAILABLE:
                log_activity('update', 'barber_service', details={
                    'service_id': service_id, 'status': new_status
                })

    except Exception as e:
        logger.error(f"Error toggling service availability: {e}")
        print(f"❌ Error toggling service availability: {e}")

    input("\nPress Enter to continue...")
