"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def manage_expiry_dates():
    """Manage product expiry dates (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to manage expiry dates")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Expiry Date Management")

        print("\n1. Add expiry batch")
        print("2. View expiring products")
        print("3. Mark batch as sold/disposed")
        print("0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            add_expiry_batch()
        elif choice == '2':
            view_expiring_products()
        elif choice == '3':
            mark_batch_disposed()

    except Exception as e:
        logger.error(f"Error in expiry management: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")
