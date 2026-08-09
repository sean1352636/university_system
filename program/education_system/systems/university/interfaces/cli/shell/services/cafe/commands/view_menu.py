from ..context import *  # noqa: F401,F403

def view_menu_cli() -> None:
    """View the cafe menu."""
    print("\n--- Cafe Menu ---")
    print("\nFilter by category:")
    print("1. All Items")
    for i, cat in enumerate(CATEGORIES, 2):
        print(f"{i}. {cat}")

    filter_choice = input("\nSelect category (or press Enter for All): ").strip()

    category = None
    try:
        choice_num = int(filter_choice)
        if 2 <= choice_num <= len(CATEGORIES) + 1:
            category = CATEGORIES[choice_num - 2]
    except ValueError:
        pass

    items = get_all_menu_items(category=category, available_only=True)

    if not items:
        print("\nNo menu items found.")
        input("\nPress Enter to continue...")
        return

    if ACTIVITY_LOGGER_AVAILABLE:
        log_read('cafe_menu', category=category or 'all', count=len(items))

    print(f"\n{'=' * 80}")
    print(f"{'ID':<5} {'Item':<25} {'Category':<12} {'Price':<10} {'Stock':<8}")
    print(f"{'=' * 80}")

    current_category = None
    for item in items:
        item_id, name, cat, desc, price, available, stock = item
        if cat != current_category:
            current_category = cat
            print(f"\n--- {cat} ---")
        print(f"{item_id:<5} {name[:24]:<25} {cat:<12} £{price:<9.2f} {stock:<8}")

    print(f"{'=' * 80}")
    input("\nPress Enter to continue...")

