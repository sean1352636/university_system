"""CLI module for Parent Account Continuity."""

from education_system.shared.parent_continuity.parent_service import ParentContinuityService

SYSTEM_NAMES = {
    "university": "University",
    "college": "Sixth Form College",
    "school": "Secondary School",
    "secondary": "Secondary School",
    "primary": "Primary School",
}


def run(db_path=None, auth=None):
    """Run the Parent Account Continuity CLI menu loop."""
    svc = ParentContinuityService(auth_db_path=db_path)

    # Determine current system
    current_system = "college"
    if isinstance(auth, dict):
        current_system = auth.get("system_key", "college")

    while True:
        print("\n=== Parent Account Continuity ===")
        print(f"Current system: {SYSTEM_NAMES.get(current_system, current_system)}")
        print("1) View unlinked parents")
        print("2) Link specific parent")
        print("3) Link all parents")
        print("4) Search by student name")
        print("0) Back")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            _view_unlinked(svc, current_system)
        elif choice == "2":
            _link_specific(svc, current_system)
        elif choice == "3":
            _link_all(svc, current_system)
        elif choice == "4":
            _search_by_name(svc)
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def _view_unlinked(svc, dest_system):
    """Display unlinked parents for the destination system."""
    print(f"\nSearching for unlinked parents in {SYSTEM_NAMES.get(dest_system, dest_system)}...")
    try:
        parents = svc.get_unlinked_parents(dest_system)
        if not parents:
            print("No unlinked parent accounts found.")
            return

        print(f"\nFound {len(parents)} unlinked parent(s):\n")
        print(f"{'#':<4} {'Student':<25} {'Parent':<25} {'Source':<18} {'Email':<30}")
        print("-" * 102)
        for i, p in enumerate(parents, 1):
            src = SYSTEM_NAMES.get(p["source_system"], p["source_system"])
            print(f"{i:<4} {p['student_name']:<25} {p['parent_name']:<25} "
                  f"{src:<18} {p.get('parent_email', ''):<30}")
    except Exception as e:
        print(f"Error: {e}")


def _link_specific(svc, dest_system):
    """Link a specific parent account."""
    try:
        parents = svc.get_unlinked_parents(dest_system)
        if not parents:
            print("No unlinked parent accounts found.")
            return

        _view_unlinked(svc, dest_system)
        idx_str = input("\nEnter parent number to link (or 0 to cancel): ").strip()
        try:
            idx = int(idx_str)
        except ValueError:
            print("Invalid number.")
            return

        if idx == 0:
            return
        if idx < 1 or idx > len(parents):
            print("Invalid number.")
            return

        p = parents[idx - 1]
        uid = p.get("parent_user_id")
        if not uid:
            print("No matching auth account found for this parent.")
            return

        ok = svc.link_parent_to_system(uid, dest_system, role="parent")
        if ok:
            print(f"Successfully linked '{p['parent_name']}' to "
                  f"{SYSTEM_NAMES.get(dest_system, dest_system)}.")
        else:
            print("Failed to link parent account.")
    except Exception as e:
        print(f"Error: {e}")


def _link_all(svc, dest_system):
    """Link all unlinked parents."""
    try:
        parents = svc.get_unlinked_parents(dest_system)
        if not parents:
            print("No unlinked parent accounts found.")
            return

        confirm = input(f"Link {len(parents)} parent account(s)? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return

        linked = 0
        failed = 0
        for p in parents:
            uid = p.get("parent_user_id")
            if not uid:
                failed += 1
                continue
            ok = svc.link_parent_to_system(uid, dest_system, role="parent")
            if ok:
                linked += 1
            else:
                failed += 1

        print(f"Linked: {linked}, Failed: {failed}")
    except Exception as e:
        print(f"Error: {e}")


def _search_by_name(svc):
    """Search for parent accounts by student name across all systems."""
    name = input("Student name to search: ").strip()
    if not name:
        print("No name entered.")
        return

    all_systems = ["primary", "secondary", "college", "university"]
    total = 0

    print(f"\nSearching for parents of '{name}' across all systems...\n")
    print(f"{'System':<20} {'Student':<25} {'Parent':<25} {'Email':<30} {'Auth Match':<10}")
    print("-" * 110)

    for src in all_systems:
        try:
            parents = svc.find_parent_accounts(name, src)
            for p in parents:
                src_display = SYSTEM_NAMES.get(src, src)
                matched = "Yes" if p.get("matched_user_id") else "No"
                print(f"{src_display:<20} {p['student_name']:<25} "
                      f"{p['parent_name']:<25} {p.get('parent_email', ''):<30} {matched:<10}")
                total += 1
        except Exception:
            pass

    if total == 0:
        print("No parent records found.")
    else:
        print(f"\nTotal: {total} record(s)")
