"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def view_staff():
    """View all barber staff"""
    try:
        print_subheader("BARBER STAFF")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT staff_id, staff_name, specialization, availability, status
                FROM barber_staff
                WHERE status = 'active'
                ORDER BY staff_name
            ''')
            staff = cursor.fetchall()

            if not staff:
                print("\n❌ No staff available")
            else:
                print("\n{:<5} {:<25} {:<30} {:<20}".format(
                    "ID", "Name", "Specialization", "Availability"
                ))
                print("-" * 85)

                for member in staff:
                    try:
                        staff_id, name, spec, avail, status = member
                        print("{:<5} {:<25} {:<30} {:<20}".format(
                            staff_id,
                            name[:24],
                            (spec[:29] if spec else "General")[:29],
                            (avail[:19] if avail else "Mon-Sat 9AM-6PM")[:19]
                        ))
                    except Exception as e:
                        logger.error(f"Error displaying staff member: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing staff: {e}")
        print(f"❌ Error viewing staff: {e}")

    input("\nPress Enter to continue...")
