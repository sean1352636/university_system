"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def add_service():
    """Add a new barber service (staff only)"""
    if not is_staff_or_admin():
        print("❌ This function is only available to staff and administrators")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("ADD NEW SERVICE")

        name = input("\nService name: ").strip()
        if not name:
            print("❌ Service name is required")
            input("\nPress Enter to continue...")
            return

        try:
            price = float(input("Price (GBP): ").strip())
            if price <= 0:
                print("❌ Price must be greater than zero")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid price format")
            input("\nPress Enter to continue...")
            return

        try:
            duration = int(input("Duration (minutes): ").strip())
            if duration <= 0:
                print("❌ Duration must be greater than zero")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid duration format")
            input("\nPress Enter to continue...")
            return

        description = input("Description (optional): ").strip()

        confirm = input(f"\nAdd service '{name}' at GBP {price:.2f} for {duration} minutes? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Service addition cancelled")
            input("\nPress Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                INSERT INTO barber_services (service_name, price, duration_minutes, description, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (name, price, duration, description if description else None))

        print(f"\n✅ Service '{name}' added successfully!")

        if ACTIVITY_LOG_AVAILABLE:
            user = get_current_user()
            log_activity('create', 'barber_service', details={
                'name': name, 'price': price, 'duration': duration
            })

    except Exception as e:
        logger.error(f"Error adding service: {e}")
        print(f"❌ Error adding service: {e}")

    input("\nPress Enter to continue...")
