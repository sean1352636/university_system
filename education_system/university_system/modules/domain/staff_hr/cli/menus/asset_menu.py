"""
Asset Menu - Asset and equipment management CLI.
"""

from education_system.university_system.modules.domain.staff_hr.services import AssetManager


def display_asset_menu(user_id: str, is_admin: bool = False) -> None:
    """Display asset management menu."""
    while True:
        print("\n" + "=" * 60)
        print("ASSET & EQUIPMENT MANAGEMENT")
        print("=" * 60)

        # Show user's assigned assets
        my_assets = AssetManager.get_user_assets(user_id)
        if my_assets:
            print(f"\nMy Assigned Assets: {len(my_assets)}")

        print("\n  1. View My Assets")
        print("  2. Report Issue")
        print("  3. Request New Asset")
        print("  4. View My Requests")

        if is_admin:
            print("\n--- Admin ---")
            print("  5. Browse All Assets")
            print("  6. Assign Asset")
            print("  7. Process Return")
            print("  8. Manage Issues")
            print("  9. Schedule Maintenance")
            print("  10. Add New Asset")
            print("  11. View Audit Log")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_my_assets(user_id)
        elif choice == '2':
            _report_issue(user_id)
        elif choice == '3':
            _request_asset(user_id)
        elif choice == '4':
            _view_requests(user_id)
        elif choice == '5' and is_admin:
            _browse_assets()
        elif choice == '6' and is_admin:
            _assign_asset(user_id)
        elif choice == '7' and is_admin:
            _process_return(user_id)
        elif choice == '8' and is_admin:
            _manage_issues(user_id)
        elif choice == '9' and is_admin:
            _schedule_maintenance()
        elif choice == '10' and is_admin:
            _add_asset()
        elif choice == '11' and is_admin:
            _view_audit_log()
        else:
            print("Invalid choice.")


def _view_my_assets(user_id: str) -> None:
    """View user's assigned assets."""
    assets = AssetManager.get_user_assets(user_id)
    print("\n" + "-" * 60)
    print("MY ASSIGNED ASSETS")
    print("-" * 60)

    if assets:
        for a in assets:
            print(f"\n  {a.get('name')} ({a.get('asset_tag')})")
            print(f"    Category: {a.get('category_name', 'N/A')}")
            print(f"    Serial: {a.get('serial_number', 'N/A')}")
            print(f"    Condition: {a.get('condition', 'N/A')}")
            print(f"    Assigned: {a.get('assigned_date', 'N/A')}")
    else:
        print("No assets assigned to you.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _report_issue(user_id: str) -> None:
    """Report an issue with an asset."""
    assets = AssetManager.get_user_assets(user_id)
    if not assets:
        print("\nNo assets assigned. Cannot report issue.")
        input("Press Enter to continue...")
        return

    print("\nYour Assets:")
    for i, a in enumerate(assets, 1):
        print(f"  {i}. {a.get('name')} ({a.get('asset_tag')})")

    try:
        choice = int(input("\nSelect asset (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(assets):
            asset = assets[choice - 1]

            print("\nIssue Types: damage, malfunction, theft, loss, other")
            issue_type = input("Issue Type: ").strip() or 'malfunction'

            print("\nSeverity: low, medium, high, critical")
            severity = input("Severity: ").strip() or 'medium'

            description = input("Description:\n").strip()

            issue_id = AssetManager.report_issue(
                asset['asset_id'], user_id,
                issue_type=issue_type,
                severity=severity,
                description=description
            )
            print(f"\nIssue reported. ID: {issue_id}")
    except ValueError:
        print("\nInvalid input.")

    input("Press Enter to continue...")


def _request_asset(user_id: str) -> None:
    """Request a new asset."""
    categories = AssetManager.get_categories()
    print("\n--- Request New Asset ---")
    print("\nCategories:")
    for i, c in enumerate(categories, 1):
        print(f"  {i}. {c.get('name')}")

    try:
        cat_choice = int(input("\nSelect category: ").strip()) - 1
        if cat_choice < 0 or cat_choice >= len(categories):
            print("Invalid selection.")
            input("Press Enter to continue...")
            return
        category = categories[cat_choice]

        justification = input("Justification:\n").strip()
        priority = input("Priority (low/medium/high): ").strip() or 'medium'

        request_id = AssetManager.submit_request(
            user_id, category['category_id'],
            justification=justification,
            priority=priority
        )
        print(f"\nRequest submitted. ID: {request_id}")
    except ValueError:
        print("\nInvalid input.")

    input("Press Enter to continue...")


def _view_requests(user_id: str) -> None:
    """View user's asset requests."""
    requests = AssetManager.get_user_requests(user_id)
    print("\n" + "-" * 60)
    print("MY ASSET REQUESTS")
    print("-" * 60)

    if requests:
        for r in requests:
            status = r.get('status', 'pending').upper()
            print(f"\n  [{status}] {r.get('category_name', 'N/A')}")
            print(f"    Requested: {r.get('request_date', 'N/A')[:10]}")
            print(f"    Priority: {r.get('priority', 'N/A')}")
            if r.get('justification'):
                print(f"    Reason: {r.get('justification')[:50]}...")
    else:
        print("No asset requests found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _browse_assets() -> None:
    """Browse all assets."""
    categories = AssetManager.get_categories()
    print("\n--- Browse Assets ---")
    print("  0. All Categories")
    for i, c in enumerate(categories, 1):
        print(f"  {i}. {c.get('name')}")

    try:
        cat_choice = int(input("\nSelect category (0 for all): ").strip())
        category_id = None
        if 1 <= cat_choice <= len(categories):
            category_id = categories[cat_choice - 1]['category_id']

        assets = AssetManager.get_assets(category_id=category_id, limit=50)
        print("\n" + "-" * 60)
        print("ASSETS")
        print("-" * 60)

        if assets:
            for a in assets:
                status = a.get('status', 'available').upper()
                print(f"\n  [{status}] {a.get('name')}")
                print(f"    Tag: {a.get('asset_tag')} | Serial: {a.get('serial_number', 'N/A')}")
                print(f"    Condition: {a.get('condition', 'N/A')} | Location: {a.get('location', 'N/A')}")
        else:
            print("No assets found.")

        print("-" * 60)
    except ValueError:
        print("Invalid input.")

    input("\nPress Enter to continue...")


def _assign_asset(admin_id: str) -> None:
    """Assign asset to user."""
    assets = AssetManager.get_assets(status='available', limit=50)
    if not assets:
        print("\nNo available assets.")
        input("Press Enter to continue...")
        return

    print("\nAvailable Assets:")
    for i, a in enumerate(assets, 1):
        print(f"  {i}. {a.get('name')} ({a.get('asset_tag')})")

    try:
        choice = int(input("\nSelect asset (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(assets):
            asset = assets[choice - 1]
            user_id = input("Assign to User ID: ").strip()
            notes = input("Notes: ").strip()

            AssetManager.assign_asset(
                asset['asset_id'], user_id,
                assigned_by=admin_id,
                notes=notes
            )
            print("\nAsset assigned successfully.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _process_return(admin_id: str) -> None:
    """Process asset return."""
    # Get assigned assets
    assets = AssetManager.get_assets(status='assigned', limit=50)
    if not assets:
        print("\nNo assigned assets to return.")
        input("Press Enter to continue...")
        return

    print("\nAssigned Assets:")
    for i, a in enumerate(assets, 1):
        print(f"  {i}. {a.get('name')} - {a.get('assigned_to_name', a.get('assigned_to', 'N/A'))}")

    try:
        choice = int(input("\nSelect asset (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(assets):
            asset = assets[choice - 1]

            print("\nCondition: excellent, good, fair, poor, damaged")
            condition = input("Return Condition: ").strip() or 'good'
            notes = input("Notes: ").strip()

            AssetManager.return_asset(
                asset['asset_id'],
                returned_by=admin_id,
                condition=condition,
                notes=notes
            )
            print("\nAsset returned successfully.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _manage_issues(admin_id: str) -> None:
    """Manage asset issues."""
    issues = AssetManager.get_open_issues(limit=20)
    print("\n" + "-" * 60)
    print("OPEN ASSET ISSUES")
    print("-" * 60)

    if not issues:
        print("No open issues.")
        input("\nPress Enter to continue...")
        return

    for i, issue in enumerate(issues, 1):
        severity = issue.get('severity', 'medium').upper()
        print(f"\n  {i}. [{severity}] {issue.get('asset_name', 'N/A')}")
        print(f"     Type: {issue.get('issue_type')} | Reported: {issue.get('reported_date', 'N/A')[:10]}")
        if issue.get('description'):
            print(f"     {issue.get('description')[:60]}...")

    print("-" * 60)

    try:
        choice = int(input("\nSelect issue to update (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(issues):
            issue = issues[choice - 1]

            print("\nStatus: open, in_progress, resolved, closed")
            status = input("New Status: ").strip()
            resolution = input("Resolution Notes: ").strip()

            if status:
                AssetManager.update_issue(
                    issue['issue_id'],
                    status=status,
                    resolution=resolution,
                    resolved_by=admin_id if status in ('resolved', 'closed') else None
                )
                print("\nIssue updated.")
    except ValueError:
        print("\nInvalid input.")

    input("Press Enter to continue...")


def _schedule_maintenance() -> None:
    """Schedule asset maintenance."""
    assets = AssetManager.get_assets(limit=50)
    if not assets:
        print("\nNo assets found.")
        input("Press Enter to continue...")
        return

    print("\nAssets:")
    for i, a in enumerate(assets[:20], 1):
        print(f"  {i}. {a.get('name')} ({a.get('asset_tag')})")

    try:
        choice = int(input("\nSelect asset (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= min(len(assets), 20):
            asset = assets[choice - 1]

            print("\nMaintenance Type: preventive, repair, inspection, calibration, upgrade")
            maint_type = input("Type: ").strip() or 'preventive'
            scheduled_date = input("Scheduled Date (YYYY-MM-DD): ").strip()
            notes = input("Notes: ").strip()

            maint_id = AssetManager.schedule_maintenance(
                asset['asset_id'],
                maintenance_type=maint_type,
                scheduled_date=scheduled_date,
                notes=notes
            )
            print(f"\nMaintenance scheduled. ID: {maint_id}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _add_asset() -> None:
    """Add a new asset."""
    categories = AssetManager.get_categories()
    print("\n--- Add New Asset ---")
    print("\nCategories:")
    for i, c in enumerate(categories, 1):
        print(f"  {i}. {c.get('name')}")

    try:
        cat_choice = int(input("\nSelect category: ").strip()) - 1
        if cat_choice < 0 or cat_choice >= len(categories):
            print("Invalid selection.")
            input("Press Enter to continue...")
            return
        category = categories[cat_choice]

        name = input("Asset Name: ").strip()
        serial = input("Serial Number: ").strip()
        location = input("Location: ").strip()
        purchase_date = input("Purchase Date (YYYY-MM-DD): ").strip()
        purchase_cost = input("Purchase Cost: ").strip()

        if name:
            asset_id = AssetManager.create_asset(
                name=name,
                category_id=category['category_id'],
                serial_number=serial,
                location=location,
                purchase_date=purchase_date if purchase_date else None,
                purchase_cost=float(purchase_cost) if purchase_cost else None
            )
            print(f"\nAsset created. ID: {asset_id}")
        else:
            print("\nAsset name is required.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_audit_log() -> None:
    """View asset audit log."""
    logs = AssetManager.get_audit_log(limit=30)
    print("\n" + "-" * 60)
    print("ASSET AUDIT LOG (Recent 30)")
    print("-" * 60)

    if logs:
        for log in logs:
            print(f"\n  {log.get('timestamp', 'N/A')[:19]}")
            print(f"    Asset: {log.get('asset_name', 'N/A')} | Action: {log.get('action')}")
            print(f"    By: {log.get('action_by', 'System')}")
    else:
        print("No audit log entries.")

    print("-" * 60)
    input("\nPress Enter to continue...")
