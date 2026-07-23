"""Central Admin Portal CLI.

Text-based menu interface for superadmin dashboard operations:
system health, user summary, user listing, audit log, and overview.
"""

from education_system.shared.admin_portal.admin_service import AdminService, SYSTEM_LABELS

SYSTEM_KEYS = ["primary", "secondary", "college", "university"]


def _print_header(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _system_health(svc):
    _print_header("System Health")
    health = svc.get_system_health()
    for info in health:
        status_mark = "[OK]" if info["status"] == "online" else "[--]"
        print(f"\n  {status_mark} {info['label']}")
        print(f"       Students: {info['student_count']}")
        print(f"       Staff:    {info['staff_count']}")
        print(f"       DB Size:  {info['db_size_mb']} MB")
        print(f"       Last Activity: {info['last_activity'] or 'N/A'}")
        print(f"       Status:   {info['status']}")
    print()


def _user_summary(svc):
    _print_header("User Summary")
    summary = svc.get_user_summary()
    print(f"\n  Total users: {summary['total_users']}")

    by_role = summary.get("by_role", {})
    if by_role:
        print("\n  By Role:")
        for role, count in sorted(by_role.items()):
            print(f"    {role:15s} {count}")

    by_system = summary.get("by_system", {})
    if by_system:
        print("\n  By System:")
        for sys_key, roles in sorted(by_system.items()):
            label = SYSTEM_LABELS.get(sys_key, sys_key)
            total = sum(roles.values())
            detail = ", ".join(f"{r}: {c}" for r, c in sorted(roles.items()))
            print(f"    {label:25s} {total} ({detail})")
    print()


def _list_users(svc):
    _print_header("List Users")

    # Optional filters
    print("\n  Filter by system (leave blank for all):")
    for i, key in enumerate(SYSTEM_KEYS, 1):
        print(f"    {i}) {SYSTEM_LABELS.get(key, key)}")
    print("    0) All systems")
    choice = input("  System [0]: ").strip()
    system = None
    if choice.isdigit() and 1 <= int(choice) <= len(SYSTEM_KEYS):
        system = SYSTEM_KEYS[int(choice) - 1]

    role = input("  Role filter (admin/staff/teacher/student/parent or blank): ").strip() or None

    users = svc.get_all_users(system=system, role=role)
    if not users:
        print("\n  No users found.")
    else:
        print(f"\n  {'Username':15s} {'Display Name':25s} {'Role(s)':20s} {'System(s)':25s} {'Last Login':19s}")
        print("  " + "-" * 104)
        for u in users:
            roles = ", ".join(sorted(set(s["role"] for s in u["systems"])))
            systems = ", ".join(sorted(set(
                SYSTEM_LABELS.get(s["system_key"], s["system_key"])
                for s in u["systems"]
            )))
            last = (u["last_login"] or "Never")[:19]
            print(f"  {u['username']:15s} {u['display_name']:25s} {roles:20s} {systems:25s} {last:19s}")
    print()


def _audit_log(svc):
    _print_header("Audit Log")
    entries = svc.get_audit_summary(limit=30)
    if not entries:
        print("\n  No audit entries found.")
    else:
        for e in entries:
            ts = (e["timestamp"] or "")[:19]
            print(f"\n  [{ts}] {e['type'].upper()}")
            print(f"    {e['description']}")
            print(f"    {e['details']}")
    print()


def _system_overview(svc):
    _print_header("System Overview")
    summary = svc.get_user_summary()
    health = svc.get_system_health()

    total_students = sum(h["student_count"] for h in health)
    active = sum(1 for h in health if h["status"] == "online")

    print(f"\n  Total users:    {summary['total_users']}")
    print(f"  Total students: {total_students}")
    print(f"  Active systems: {active}/4")

    print("\n  System Details:")
    for h in health:
        status = "ONLINE" if h["status"] == "online" else "OFFLINE"
        print(f"    {h['label']:25s} [{status}] "
              f"Students: {h['student_count']}, Staff: {h['staff_count']}, "
              f"DB: {h['db_size_mb']} MB")
    print()


def run(db_path=None, auth=None):
    """Run the Central Admin Portal CLI menu loop."""
    svc = AdminService()
    _print_header("Central Admin Portal")

    while True:
        print("\n  1) System health")
        print("  2) User summary")
        print("  3) List users")
        print("  4) Audit log")
        print("  5) System overview")
        print("  0) Back")

        choice = input("\n  Select option: ").strip()

        if choice == "1":
            _system_health(svc)
        elif choice == "2":
            _user_summary(svc)
        elif choice == "3":
            _list_users(svc)
        elif choice == "4":
            _audit_log(svc)
        elif choice == "5":
            _system_overview(svc)
        elif choice == "0":
            print("\n  Returning...\n")
            break
        else:
            print("\n  Invalid option. Please try again.")
