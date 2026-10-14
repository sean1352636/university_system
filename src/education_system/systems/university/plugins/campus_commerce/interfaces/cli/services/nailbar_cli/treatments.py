"""Treatment catalogue: browsing and staff maintenance."""

import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

import education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.nailbar_cli as _pkg
from .helpers import format_currency, is_staff, print_subheader

logger = logging.getLogger(__name__)


def view_treatments():
    """View available nail treatments"""
    try:
        print_subheader("NAIL TREATMENTS")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT treatment_id, treatment_name, category, price,
                       duration_minutes, description, status
                FROM nailbar_treatments
                WHERE status = 'active'
                ORDER BY category, treatment_name
            ''')
            treatments = cursor.fetchall()

            if not treatments:
                print("\n❌ No treatments available")
            else:
                current_category = None
                for treatment in treatments:
                    try:
                        treat_id, name, category, price, duration, desc, status = treatment

                        # Print category header if changed
                        if category != current_category:
                            current_category = category
                            print(f"\n{'━' * 70}")
                            print(f"  {category.upper()}")
                            print(f"{'━' * 70}")

                        print(f"\nID {treat_id}: {name}")
                        print(f"  Price: {format_currency(price)} | Duration: {duration} minutes")
                        if desc:
                            print(f"  {desc}")
                    except Exception as e:
                        logger.error(f"Error displaying treatment: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error viewing treatments: {e}")
        print(f"❌ Error viewing treatments: {e}")

    input("\nPress Enter to continue...")


def view_treatments_by_category():
    """Browse treatments by category"""
    try:
        print_subheader("BROWSE TREATMENTS BY CATEGORY")

        with get_connection() as conn:
            # Get categories
            cursor = conn.execute('''
                SELECT DISTINCT category
                FROM nailbar_treatments
                WHERE status = 'active'
                ORDER BY category
            ''')
            categories = cursor.fetchall()

            if not categories:
                print("\n❌ No categories available")
                input("\nPress Enter to continue...")
                return

            print("\nAvailable Categories:")
            for idx, (category,) in enumerate(categories, 1):
                # Count treatments in category
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM nailbar_treatments
                    WHERE category = ? AND status = 'active'
                ''', (category,))
                count = cursor.fetchone()[0]
                print(f"{idx}. {category.title()} ({count} treatments)")

            print("0. Back to menu")

            choice = input("\nSelect category: ").strip()

            try:
                choice_idx = int(choice)
                if choice_idx == 0:
                    return
                if 1 <= choice_idx <= len(categories):
                    selected_category = categories[choice_idx - 1][0]

                    # Show treatments in category
                    cursor = conn.execute('''
                        SELECT treatment_id, treatment_name, price,
                               duration_minutes, description
                        FROM nailbar_treatments
                        WHERE category = ? AND status = 'active'
                        ORDER BY treatment_name
                    ''', (selected_category,))
                    treatments = cursor.fetchall()

                    print(f"\n{'━' * 70}")
                    print(f"  {selected_category.upper()} TREATMENTS")
                    print(f"{'━' * 70}")

                    for treat_id, name, price, duration, desc in treatments:
                        print(f"\nID {treat_id}: {name}")
                        print(f"  Price: {format_currency(price)} | Duration: {duration} minutes")
                        if desc:
                            print(f"  {desc}")
                else:
                    print("❌ Invalid choice")
            except ValueError:
                print("❌ Invalid input")

    except Exception as e:
        logger.error(f"Error browsing treatments: {e}")
        print(f"❌ Error browsing treatments: {e}")

    input("\nPress Enter to continue...")


def add_treatment():
    """Add a new treatment (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("ADD NEW TREATMENT")

        name = input("\nTreatment name: ").strip()
        if not name:
            print("❌ Treatment name is required")
            input("\nPress Enter to continue...")
            return

        # Show available categories
        print("\nCategories:")
        categories = ['manicure', 'pedicure', 'art', 'extensions', 'treatment', 'other']
        for idx, cat in enumerate(categories, 1):
            print(f"{idx}. {cat.title()}")

        cat_choice = input("\nSelect category (or enter custom): ").strip()
        try:
            cat_idx = int(cat_choice)
            if 1 <= cat_idx <= len(categories):
                category = categories[cat_idx - 1]
            else:
                print("❌ Invalid category")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            category = cat_choice.lower()

        price_str = input("Price (GBP): ").strip()
        try:
            price = float(price_str)
            if price <= 0:
                print("❌ Price must be positive")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid price")
            input("\nPress Enter to continue...")
            return

        duration_str = input("Duration (minutes): ").strip()
        try:
            duration = int(duration_str)
            if duration <= 0:
                print("❌ Duration must be positive")
                input("\nPress Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid duration")
            input("\nPress Enter to continue...")
            return

        description = input("Description (optional): ").strip()

        # Confirmation
        print(f"\n{'━' * 70}")
        print(f"Treatment: {name}")
        print(f"Category: {category}")
        print(f"Price: {format_currency(price)}")
        print(f"Duration: {duration} minutes")
        if description:
            print(f"Description: {description}")
        print(f"{'━' * 70}")

        confirm = input("\nAdd this treatment? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Cancelled")
            input("\nPress Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                INSERT INTO nailbar_treatments
                (treatment_name, category, price, duration_minutes, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
            ''', (name, category, price, duration, description or None, datetime.now().isoformat()))

        print("\n✅ Treatment added successfully!")
        _pkg.log_activity('create', 'nailbar_treatment', treatment_name=name, price=price)
        logger.info(f"Treatment added: {name}")

    except Exception as e:
        logger.error(f"Error adding treatment: {e}")
        print(f"❌ Error adding treatment: {e}")

    input("\nPress Enter to continue...")


def update_treatment():
    """Update an existing treatment (staff only)"""
    if not is_staff():
        print("❌ Access denied. Staff only.")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("UPDATE TREATMENT")

        # Show all treatments
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT treatment_id, treatment_name, category, price, duration_minutes
                FROM nailbar_treatments
                WHERE status = 'active'
                ORDER BY treatment_name
            ''')
            treatments = cursor.fetchall()

            if not treatments:
                print("\n❌ No treatments available")
                input("\nPress Enter to continue...")
                return

            print("\nAvailable Treatments:")
            for treat_id, name, cat, price, duration in treatments:
                print(f"ID {treat_id}: {name} ({cat}) - {format_currency(price)}, {duration} min")

        treatment_id = input("\nEnter treatment ID to update (0 to cancel): ").strip()
        if treatment_id == "0":
            return

        if not treatment_id.isdigit():
            print("❌ Invalid treatment ID")
            input("\nPress Enter to continue...")
            return

        # Get current treatment details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT treatment_name, category, price, duration_minutes, description
                FROM nailbar_treatments
                WHERE treatment_id = ? AND status = 'active'
            ''', (treatment_id,))
            current = cursor.fetchone()

            if not current:
                print("❌ Treatment not found")
                input("\nPress Enter to continue...")
                return

            curr_name, curr_cat, curr_price, curr_duration, curr_desc = current

        print("\nCurrent details:")
        print(f"Name: {curr_name}")
        print(f"Category: {curr_cat}")
        print(f"Price: {format_currency(curr_price)}")
        print(f"Duration: {curr_duration} minutes")
        print(f"Description: {curr_desc or 'None'}")

        print("\nEnter new values (press Enter to keep current):")

        new_name = input(f"Name [{curr_name}]: ").strip() or curr_name
        new_cat = input(f"Category [{curr_cat}]: ").strip() or curr_cat

        price_input = input(f"Price [{curr_price}]: ").strip()
        try:
            new_price = float(price_input) if price_input else curr_price
        except ValueError:
            print("❌ Invalid price, keeping current")
            new_price = curr_price

        duration_input = input(f"Duration [{curr_duration}]: ").strip()
        try:
            new_duration = int(duration_input) if duration_input else curr_duration
        except ValueError:
            print("❌ Invalid duration, keeping current")
            new_duration = curr_duration

        new_desc = input(f"Description [{curr_desc or 'None'}]: ").strip()
        if not new_desc:
            new_desc = curr_desc

        # Confirmation
        confirm = input("\nSave changes? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Cancelled")
            input("\nPress Enter to continue...")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE nailbar_treatments
                SET treatment_name = ?, category = ?, price = ?,
                    duration_minutes = ?, description = ?, updated_at = ?
                WHERE treatment_id = ?
            ''', (new_name, new_cat, new_price, new_duration, new_desc,
                  datetime.now().isoformat(), treatment_id))

        print("\n✅ Treatment updated successfully!")
        _pkg.log_activity('update', 'nailbar_treatment', treatment_id=treatment_id,
                    changes={'name': new_name, 'price': new_price})
        logger.info(f"Treatment updated: ID {treatment_id}")

    except Exception as e:
        logger.error(f"Error updating treatment: {e}")
        print(f"❌ Error updating treatment: {e}")

    input("\nPress Enter to continue...")


__all__ = [
    'view_treatments', 'view_treatments_by_category', 'add_treatment',
    'update_treatment',
]
