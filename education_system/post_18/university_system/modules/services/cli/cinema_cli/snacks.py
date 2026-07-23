"""Cinema CLI snacks and concessions functions."""

import logging
from typing import Tuple, List, Dict

from education_system.post_18.university_system.modules.services.cli.cinema_cli.constants import SNACKS_MENU, COMBO_DEALS
from education_system.post_18.university_system.modules.services.cli.cinema_cli.utils import print_subheader

logger = logging.getLogger(__name__)


def display_snacks_menu():
    """Display snacks menu with combo deals"""
    print_subheader("🍿 SNACKS & CONCESSIONS")

    print("\n🎁 COMBO DEALS (Best Value!):")
    print("-" * 70)
    for idx, (combo_name, combo_data) in enumerate(COMBO_DEALS.items(), 1):
        savings = combo_data['original'] - combo_data['price']
        print(f"{idx}. {combo_name} - £{combo_data['price']:.2f} (Save £{savings:.2f})")
        print(f"   Includes: {', '.join(combo_data['items'])}")

    print("\n🍿 INDIVIDUAL ITEMS:")
    print("-" * 70)
    start_idx = len(COMBO_DEALS) + 1
    for idx, (item, price) in enumerate(SNACKS_MENU.items(), start_idx):
        print(f"{idx}. {item} - £{price:.2f}")


def suggest_combo_for_party(num_tickets: int):
    """Suggest appropriate combo based on party size"""
    suggestions = []

    if num_tickets == 1:
        suggestions.append("Small Combo")
    elif num_tickets == 2:
        suggestions.append("Medium Combo")
    elif num_tickets >= 3:
        suggestions.append("Family Combo")
        if num_tickets >= 4:
            suggestions.append("Large Combo")

    if suggestions:
        print(f"\n💡 Recommended for {num_tickets} person(s): {', '.join(suggestions)}")


def add_snacks_to_order() -> Tuple[float, List[Dict]]:
    """Interactive snacks ordering with combo support"""
    try:
        snacks_total = 0.0
        snacks_list = []

        display_snacks_menu()

        total_items = len(COMBO_DEALS) + len(SNACKS_MENU)

        while True:
            choice = input(f"\n🍿 Select item (1-{total_items}, 0 to finish): ").strip()

            if choice == "0":
                break

            if not choice.isdigit():
                print("❌ Invalid selection")
                continue

            item_idx = int(choice)

            # Check if it's a combo
            if item_idx <= len(COMBO_DEALS):
                combo_name = list(COMBO_DEALS.keys())[item_idx - 1]
                combo_data = COMBO_DEALS[combo_name]

                qty_str = input(f"Quantity of {combo_name}: ").strip()

                try:
                    qty = int(qty_str)
                    if qty < 1 or qty > 5:
                        print("❌ Quantity must be between 1 and 5 for combos")
                        continue
                except ValueError:
                    print("❌ Invalid quantity")
                    continue

                subtotal = combo_data['price'] * qty
                snacks_list.append({
                    'name': combo_name,
                    'price': combo_data['price'],
                    'quantity': qty,
                    'subtotal': subtotal,
                    'is_combo': True
                })
                snacks_total += subtotal

                savings = (combo_data['original'] - combo_data['price']) * qty
                print(f"✅ Added {qty}x {combo_name} (Saved £{savings:.2f})")

            # Individual item
            elif item_idx <= total_items:
                snack_idx = item_idx - len(COMBO_DEALS) - 1
                snacks_menu_list = list(SNACKS_MENU.items())

                if snack_idx < 0 or snack_idx >= len(snacks_menu_list):
                    print("❌ Invalid selection")
                    continue

                snack_name, snack_price = snacks_menu_list[snack_idx]

                qty_str = input(f"Quantity of {snack_name}: ").strip()

                try:
                    qty = int(qty_str)
                    if qty < 1 or qty > 10:
                        print("❌ Quantity must be between 1 and 10")
                        continue
                except ValueError:
                    print("❌ Invalid quantity")
                    continue

                subtotal = snack_price * qty
                snacks_list.append({
                    'name': snack_name,
                    'price': snack_price,
                    'quantity': qty,
                    'subtotal': subtotal,
                    'is_combo': False
                })
                snacks_total += subtotal

                print(f"✅ Added {qty}x {snack_name}")
            else:
                print("❌ Invalid selection")

        return snacks_total, snacks_list

    except Exception as e:
        logger.error(f"Error adding snacks: {e}")
        return 0.0, []
