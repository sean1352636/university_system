"""CLI for the textbook store and used-book exchange."""

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.commerce.textbooks.services import textbook_service


def main():
    """Run the textbooks CLI menu loop."""
    textbook_service.init_db()

    while True:
        print("\n===== Textbook Store =====")
        print("1. Search Textbooks")
        print("2. View Textbook Details")
        print("3. View My Course Textbooks")
        print("4. Browse Used Listings")
        print("5. Create Used Listing")
        print("6. Buy Used Listing")
        print("7. View My Orders")
        print("8. List Module Codes")
        print("0. Back / Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            search_textbooks()
        elif choice == "2":
            view_textbook_details()
        elif choice == "3":
            view_course_textbooks()
        elif choice == "4":
            browse_listings()
        elif choice == "5":
            create_listing()
        elif choice == "6":
            buy_listing()
        elif choice == "7":
            view_orders()
        elif choice == "8":
            list_module_codes()
        elif choice == "0":
            print("Returning to main menu.")
            break
        else:
            print("Invalid option. Please try again.")


def search_textbooks():
    """Search the textbook catalogue."""
    try:
        search_term = input("Search term (title/author/ISBN, leave blank for all): ").strip()
        module_code = input("Module code (leave blank for all): ").strip() or None

        results = textbook_service.search_textbooks(search_term=search_term, module_code=module_code)
        if not results:
            print("No textbooks found.")
            return
        print(
            f"\n{'ID':<5} {'Title':<35} {'Author':<20} {'Edition':<8} "
            f"{'Module':<8} {'Price':<8} {'Req?':<5}"
        )
        print("-" * 89)
        for t in results:
            req = "Yes" if t["required"] else "No"
            print(
                f"{t['textbook_id']:<5} {t['title']:<35} {t['author']:<20} "
                f"{t['edition']:<8} {t['module_code']:<8} "
                f"{t['price']:<8.2f} {req:<5}"
            )
    except Exception as e:
        print(f"Error: {e}")


def view_textbook_details():
    """View detailed info for a single textbook."""
    try:
        textbook_id = input("Textbook ID: ").strip()
        t = textbook_service.get_textbook(int(textbook_id))
        if not t:
            print("Textbook not found.")
            return
        req = "Required" if t["required"] else "Recommended"
        print(f"\nTitle:       {t['title']}")
        print(f"Author:      {t['author']}")
        print(f"Edition:     {t['edition']}")
        print(f"Publisher:   {t['publisher']}")
        print(f"Year:        {t['year']}")
        print(f"ISBN:        {t['isbn']}")
        print(f"Module:      {t['module_code']}")
        print(f"Status:      {req}")
        print(f"Price:       {t['price']:.2f}")
        print(f"Description: {t['description']}")
    except Exception as e:
        print(f"Error: {e}")


def view_course_textbooks():
    """View textbooks for a student's enrolled modules."""
    try:
        student_id = input("Student ID: ").strip()
        books = textbook_service.get_course_textbooks(student_id)
        if not books:
            print("No course textbooks found (student may not be enrolled in any modules).")
            return
        print(
            f"\n{'ID':<5} {'Title':<35} {'Module':<8} {'Req?':<5} "
            f"{'Price':<8} {'Used Available':<15}"
        )
        print("-" * 76)
        for t in books:
            req = "Yes" if t["required"] else "No"
            print(
                f"{t['textbook_id']:<5} {t['title']:<35} {t['module_code']:<8} "
                f"{req:<5} {t['price']:<8.2f} {t['used_count']:<15}"
            )
    except Exception as e:
        print(f"Error: {e}")


def browse_listings():
    """Browse available used-book listings."""
    try:
        textbook_id_input = input("Filter by textbook ID (leave blank for all): ").strip()
        textbook_id = int(textbook_id_input) if textbook_id_input else None

        listings = textbook_service.get_available_listings(textbook_id=textbook_id)
        if not listings:
            print("No available listings found.")
            return
        print(
            f"\n{'ID':<6} {'Title':<30} {'Condition':<12} {'Price':<8} "
            f"{'Seller':<15} {'Listed':<12}"
        )
        print("-" * 83)
        for l in listings:
            print(
                f"{l['listing_id']:<6} {l['title']:<30} {l['condition']:<12} "
                f"{l['price']:<8.2f} {l['seller_id']:<15} {l['listed_date']:<12}"
            )
    except Exception as e:
        print(f"Error: {e}")


def create_listing():
    """List a textbook for sale on the exchange."""
    try:
        # Show available textbooks
        books = textbook_service.get_all_textbooks_for_combo()
        if books:
            print("\nAvailable textbooks:")
            for b in books:
                print(f"  ID {b['textbook_id']}: {b['title']} by {b['author']}")

        textbook_id = input("\nTextbook ID: ").strip()
        seller_id = input("Your user/student ID: ").strip()
        condition = input("Condition (like_new/good/fair/poor) [good]: ").strip() or "good"
        price = input("Asking price: ").strip()
        notes = input("Notes: ").strip()

        textbook_service.create_listing(
            textbook_id=int(textbook_id),
            seller_id=seller_id,
            condition=condition,
            price=float(price),
            notes=notes,
        )
        print("Listing created successfully.")
    except Exception as e:
        print(f"Error: {e}")


def buy_listing():
    """Purchase a used-book listing."""
    try:
        listing_id = input("Listing ID to purchase: ").strip()
        buyer_id = input("Your user/student ID: ").strip()

        textbook_service.buy_listing(int(listing_id), buyer_id)
        print("Purchase completed successfully.")
    except Exception as e:
        print(f"Error: {e}")


def view_orders():
    """View orders for a user (as buyer or seller)."""
    try:
        user_id = input("Your user/student ID: ").strip()
        orders = textbook_service.get_orders(user_id)
        if not orders:
            print("No orders found.")
            return
        print(
            f"\n{'ID':<6} {'Title':<30} {'Buyer':<12} {'Seller':<12} "
            f"{'Price':<8} {'Status':<10} {'Date':<20}"
        )
        print("-" * 98)
        for o in orders:
            print(
                f"{o['order_id']:<6} {o['title']:<30} {o['buyer_id']:<12} "
                f"{o['seller_id']:<12} {o['price']:<8.2f} {o['status']:<10} "
                f"{o['order_date']:<20}"
            )
    except Exception as e:
        print(f"Error: {e}")


def list_module_codes():
    """Display all module codes in the textbook catalogue."""
    try:
        codes = textbook_service.get_all_module_codes()
        if not codes:
            print("No module codes found.")
            return
        print("\nModule codes:")
        for code in codes:
            print(f"  {code}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
