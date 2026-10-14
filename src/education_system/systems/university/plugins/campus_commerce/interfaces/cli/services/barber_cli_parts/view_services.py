"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_services():
    """View available barber services"""
    try:
        print_subheader("AVAILABLE BARBER SERVICES")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT service_id, service_name, price, duration_minutes, description, status
                FROM barber_services
                WHERE status = 'active'
                ORDER BY service_name
            ''')
            services = cursor.fetchall()

            if not services:
                print("\n❌ No services available")
            else:
                print("\n{:<5} {:<25} {:<12} {:<15} {:<30}".format(
                    "ID", "Service", "Price (GBP)", "Duration (min)", "Description"
                ))
                print("-" * 90)

                for service in services:
                    try:
                        svc_id, name, price, duration, desc, status = service
                        desc_short = (desc[:27] + "...") if desc and len(desc) > 30 else (desc or "")
                        print("{:<5} {:<25} {:<12.2f} {:<15} {:<30}".format(
                            svc_id, name[:24], float(price), duration, desc_short
                        ))
                    except Exception as e:
                        logger.error(f"Error displaying service: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing services: {e}")
        print(f"❌ Error viewing services: {e}")

    input("\nPress Enter to continue...")
