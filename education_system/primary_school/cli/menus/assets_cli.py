"""Assets CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def assets_menu(auth):
    """Assets management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.facilities.assets.services.asset_service import AssetService

    svc = AssetService(get_db_path())

    while True:
        print_header("Assets")
        print_menu([
            ("1", "List assets"),
            ("2", "View details"),
            ("3", "Add Asset"),
            ("4", "Update Asset"),
            ("5", "Delete Asset"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_assets()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_asset(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            name = input("  Name: ").strip()
            asset_type = input("  Asset Type: ").strip()
            try:
                svc.create_asset(name=name, asset_type=asset_type)
                print("\n  Asset created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            name = input("  Name: ").strip()
            asset_type = input("  Asset Type: ").strip()
            try:
                svc.update_asset(int(pk), name=name, asset_type=asset_type)
                print("\n  Asset updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_asset(int(pk))
                print("\n  Asset deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
