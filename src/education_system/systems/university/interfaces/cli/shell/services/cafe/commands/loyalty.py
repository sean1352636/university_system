from ..context import *  # noqa: F401,F403

def loyalty_points_cli() -> None:
    """Loyalty points management submenu."""
    while True:
        print("\n--- Loyalty Points ---")
        print("1. View All Loyalty Accounts")
        print("2. Look Up Account")
        print("3. Register New Account")
        print("4. Add Points")
        print("5. Redeem Points")
        print("6. View Points History")
        print("7. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            accounts = get_all_loyalty_accounts()
            if not accounts:
                print("\nNo loyalty accounts found.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 65}")
            print(f"{'ID':<6} {'Student ID':<15} {'Name':<25} {'Points':<10}")
            print(f"{'=' * 65}")
            for acc in accounts:
                lid, sid, cname, points = acc
                print(f"{lid:<6} {sid:<15} {cname[:24]:<25} {points:<10}")
            print(f"\nTotal: {len(accounts)} accounts")
            input("\nPress Enter to continue...")

        elif choice == '2':
            student_id = input("Enter Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue

            account = get_loyalty_account(student_id)
            if not account:
                print(f"No loyalty account found for Student ID: {student_id}")
                create = input("Create a new account? (y/n): ").strip().lower()
                if create == 'y':
                    cname = input("Customer name: ").strip()
                    if cname:
                        account = get_or_create_loyalty_account(student_id, cname)
                        if account:
                            print(f"\n Account created for {cname}!")
                if not account:
                    continue

            lid, sid, cname, points = account
            print(f"\n{'=' * 40}")
            print("LOYALTY ACCOUNT")
            print(f"{'=' * 40}")
            print(f"Student ID: {sid}")
            print(f"Name:       {cname}")
            print(f"Points:     {points}")
            # Show conversion: 100 points = £1 discount
            print(f"Value:      £{points / 100:.2f} (100 pts = £1)")
            input("\nPress Enter to continue...")

        elif choice == '3':
            student_id = input("Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue
            customer_name = input("Customer name: ").strip()
            if not customer_name:
                print("Customer name is required.")
                continue

            account = get_or_create_loyalty_account(student_id, customer_name)
            if account:
                print(f"\n Loyalty account ready for {customer_name} (Student: {student_id})")
                print(f"  Current points: {account[3]}")
            else:
                print("\n Failed to create loyalty account.")

        elif choice == '4':
            student_id = input("Enter Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue

            account = get_loyalty_account(student_id)
            if not account:
                print("No loyalty account found for this student.")
                continue

            lid, sid, cname, current_points = account
            print(f"\nCustomer: {cname} | Current Points: {current_points}")

            try:
                points = int(input("Points to add: "))
                if points < 1:
                    print("Points must be greater than zero.")
                    continue
            except ValueError:
                print("Invalid number.")
                continue

            reason = input("Reason (optional): ").strip()

            if add_loyalty_points(student_id, points, reason):
                print(f"\n {points} points added to {cname}'s account!")
                print(f"  New balance: {current_points + points} points")
            else:
                print("\n Failed to add points.")

        elif choice == '5':
            student_id = input("Enter Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue

            account = get_loyalty_account(student_id)
            if not account:
                print("No loyalty account found for this student.")
                continue

            lid, sid, cname, current_points = account
            print(f"\nCustomer: {cname} | Current Points: {current_points}")
            print(f"Redeemable value: £{current_points / 100:.2f} (100 pts = £1)")

            if current_points < 1:
                print("No points available to redeem.")
                continue

            try:
                points = int(input(f"Points to redeem (max {current_points}): "))
                if points < 1:
                    print("Points must be greater than zero.")
                    continue
                if points > current_points:
                    print(f"Insufficient points. Maximum: {current_points}")
                    continue
            except ValueError:
                print("Invalid number.")
                continue

            reason = input("Reason (optional): ").strip()

            if redeem_loyalty_points(student_id, points, reason):
                print(f"\n {points} points redeemed from {cname}'s account!")
                print(f"  Discount value: £{points / 100:.2f}")
                print(f"  Remaining balance: {current_points - points} points")
            else:
                print("\n Failed to redeem points.")

        elif choice == '6':
            student_id = input("Enter Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue

            account = get_loyalty_account(student_id)
            if not account:
                print("No loyalty account found for this student.")
                continue

            log = get_loyalty_log(student_id)
            if not log:
                print(f"\nNo transaction history for {account[2]}.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 80}")
            print(f"LOYALTY POINTS HISTORY - {account[2]} (Balance: {account[3]} pts)")
            print(f"{'=' * 80}")
            print(f"{'ID':<6} {'Change':<10} {'Type':<12} {'Reason':<25} {'Date':<20}")
            print("-" * 80)
            for entry in log:
                log_id, change, trans_type, reason, date = entry
                change_str = f"+{change}" if change > 0 else str(change)
                print(f"{log_id:<6} {change_str:<10} {trans_type:<12} {(reason or '')[:24]:<25} {str(date)[:19]:<20}")
            input("\nPress Enter to continue...")

        elif choice == '7':
            break

