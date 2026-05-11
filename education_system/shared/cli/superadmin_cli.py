"""Super Admin CLI Dashboard for the Education System.

Provides a text-based management console matching the GUI SuperAdminDashboard,
covering all 14 sections: dashboard, system health, user management, analytics,
misconduct, notifications, student search, student journey, permission matrix,
audit log, backup/restore, batch operations, active sessions, and quick launch.
"""

import getpass
from datetime import datetime

SYSTEM_KEYS = ["primary", "school", "college", "university"]
SYSTEM_LABELS = {
    "university": "University",
    "college":    "Sixth Form College",
    "school":     "Secondary School",
    "primary":    "Primary School",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _header(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _subheader(title):
    print(f"\n  --- {title} ---")


def _pause():
    input("\n  Press Enter to continue...")


def _confirm(prompt):
    return input(f"\n  {prompt} (y/n): ").strip().lower() == "y"


# ---------------------------------------------------------------------------
# Service accessors (lazy, with safe fallbacks)
# ---------------------------------------------------------------------------

_admin_svc = None
_analytics_svc = None
_notification_svc = None
_journey_svc = None


def _get_admin():
    global _admin_svc
    if _admin_svc is None:
        try:
            from education_system.shared.admin_portal.admin_service import AdminService
            _admin_svc = AdminService()
        except Exception as e:
            print(f"  [!] AdminService unavailable: {e}")
    return _admin_svc


def _get_analytics():
    global _analytics_svc
    if _analytics_svc is None:
        try:
            from education_system.shared.analytics.analytics_service import AnalyticsService
            _analytics_svc = AnalyticsService()
        except Exception as e:
            print(f"  [!] AnalyticsService unavailable: {e}")
    return _analytics_svc


def _get_notifications():
    global _notification_svc
    if _notification_svc is None:
        try:
            from education_system.shared.notifications.service import CrossSystemNotificationService
            _notification_svc = CrossSystemNotificationService()
        except Exception as e:
            print(f"  [!] NotificationService unavailable: {e}")
    return _notification_svc


def _get_journey():
    return None


# ---------------------------------------------------------------------------
# 1. Dashboard (overview)
# ---------------------------------------------------------------------------

def _dashboard(user_info):
    _header("Super Admin Dashboard")

    svc = _get_admin()
    analytics = _get_analytics()

    if svc:
        health = svc.get_system_health()
        summary = svc.get_user_summary()

        print(f"\n  Registered Users: {summary.get('total_users', 0)}")

        _subheader("System Status")
        for h in health:
            status = "ONLINE" if h["status"] == "online" else "OFFLINE"
            print(f"    [{status:7s}] {h['label']:25s}  "
                  f"Students: {h['student_count']:>5}  Staff: {h['staff_count']:>4}  "
                  f"DB: {h['db_size_mb']:.1f} MB")

    if analytics:
        s = analytics.get_summary()
        _subheader("Student Overview")
        print(f"    Total Students:  {s.get('total_students', 0)}")
        print(f"    Active:          {s.get('total_active', 0)}")
        print(f"    Transferred:     {s.get('total_transferred', 0)}")
        print(f"    Graduated:       {s.get('total_graduated', 0)}")

    if svc:
        recent = svc.get_audit_summary(limit=10)
        if recent:
            _subheader("Recent Activity")
            for e in recent[:10]:
                ts = (e["timestamp"] or "")[:19]
                print(f"    [{ts}] {e['type']:12s}  {e['description']}")

    _pause()


# ---------------------------------------------------------------------------
# 2. System Health
# ---------------------------------------------------------------------------

def _system_health():
    _header("System Health")
    svc = _get_admin()
    if not svc:
        _pause()
        return

    health = svc.get_system_health()
    for h in health:
        status_icon = "[OK]" if h["status"] == "online" else "[--]"
        config = svc.get_system_config(h["system"])
        print(f"\n  {status_icon} {h['label']}")
        print(f"       Status:        {h['status']}")
        print(f"       Database:      {'Exists' if h['db_exists'] else 'MISSING'}")
        print(f"       DB Size:       {h['db_size_mb']:.1f} MB")
        print(f"       DB Path:       {config.get('db_path', 'N/A')}")
        print(f"       Students:      {h['student_count']}")
        print(f"       Staff:         {h['staff_count']}")
        print(f"       Last Activity: {h['last_activity'] or 'N/A'}")

    _pause()


# ---------------------------------------------------------------------------
# 3. User Management
# ---------------------------------------------------------------------------

def _user_management():
    svc = _get_admin()
    if not svc:
        return

    while True:
        _header("User Management")
        print("\n  1) List users")
        print("  2) Search users")
        print("  3) Create user")
        print("  4) Edit user")
        print("  5) Reset password")
        print("  6) Deactivate user")
        print("  0) Back")

        choice = input("\n  Select: ").strip()

        if choice == "1":
            _list_users(svc)
        elif choice == "2":
            _search_users(svc)
        elif choice == "3":
            _create_user(svc)
        elif choice == "4":
            _edit_user(svc)
        elif choice == "5":
            _reset_password(svc)
        elif choice == "6":
            _deactivate_user(svc)
        elif choice == "0":
            break


def _list_users(svc):
    _header("List Users")

    # Optional filters
    print("\n  Filter by system (blank for all):")
    for i, key in enumerate(SYSTEM_KEYS, 1):
        print(f"    {i}) {SYSTEM_LABELS[key]}")
    print(f"    0) All systems")
    sys_choice = input("  System [0]: ").strip()
    system = None
    if sys_choice.isdigit() and 1 <= int(sys_choice) <= len(SYSTEM_KEYS):
        system = SYSTEM_KEYS[int(sys_choice) - 1]

    role = input("  Role filter (admin/staff/teacher/student/parent or blank): ").strip() or None

    users = svc.get_all_users(system=system, role=role)
    if not users:
        print("\n  No users found.")
    else:
        print(f"\n  {'Username':15s} {'Display Name':25s} {'Role(s)':15s} {'System(s)':30s} {'Active':6s} {'Last Login':19s}")
        print("  " + "-" * 112)
        for u in users:
            roles = ", ".join(sorted(set(s["role"] for s in u["systems"])))
            systems = ", ".join(sorted(set(
                SYSTEM_LABELS.get(s["system_key"], s["system_key"])
                for s in u["systems"]
            )))
            active = "Yes" if u.get("is_active", 1) else "No"
            last = (u.get("last_login") or "Never")[:19]
            print(f"  {u['username']:15s} {u['display_name']:25s} {roles:15s} {systems:30s} {active:6s} {last:19s}")

    _pause()


def _search_users(svc):
    query = input("\n  Search (username/name): ").strip()
    if not query:
        return
    users = svc.get_all_users()
    matches = [u for u in users if query.lower() in u["username"].lower()
               or query.lower() in (u.get("display_name") or "").lower()]

    if not matches:
        print("\n  No matching users found.")
    else:
        print(f"\n  Found {len(matches)} user(s):\n")
        for u in matches:
            roles = ", ".join(f"{s['system_key']}:{s['role']}" for s in u["systems"])
            active = "Active" if u.get("is_active", 1) else "Inactive"
            print(f"    ID: {u['id']}  Username: {u['username']}  "
                  f"Name: {u.get('display_name', '')}  [{active}]")
            print(f"      Email: {u.get('email', 'N/A')}  Systems: {roles}")
            print(f"      Last Login: {u.get('last_login', 'Never')}")
    _pause()


def _create_user(svc):
    _subheader("Create New User")
    username = input("  Username: ").strip()
    if not username:
        return
    display_name = input("  Display Name: ").strip() or username
    email = input("  Email: ").strip()
    password = getpass.getpass("  Password: ")
    if not password:
        print("  Password is required.")
        return

    # System/role assignments
    systems_roles = []
    print("\n  Assign systems (y/n for each):")
    for key in SYSTEM_KEYS:
        assign = input(f"    {SYSTEM_LABELS[key]}? (y/n): ").strip().lower()
        if assign == "y":
            role = input(f"      Role for {SYSTEM_LABELS[key]} (admin/staff/teacher/student/parent): ").strip()
            if role:
                systems_roles.append({"system_key": key, "role": role})

    if not systems_roles:
        print("  At least one system must be assigned.")
        return

    try:
        user_id = svc.create_user(username, display_name, email, password, systems_roles)
        print(f"\n  User created successfully (ID: {user_id})")
    except Exception as e:
        print(f"\n  Error creating user: {e}")
    _pause()


def _edit_user(svc):
    _subheader("Edit User")
    username = input("  Username to edit: ").strip()
    if not username:
        return

    users = svc.get_all_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        print(f"  User '{username}' not found.")
        _pause()
        return

    print(f"\n  Current: {user['display_name']} | {user.get('email', 'N/A')} | "
          f"Active: {'Yes' if user.get('is_active', 1) else 'No'}")
    current_systems = ", ".join(f"{s['system_key']}:{s['role']}" for s in user["systems"])
    print(f"  Systems: {current_systems}")

    display_name = input(f"\n  New display name [{user['display_name']}]: ").strip() or None
    email = input(f"  New email [{user.get('email', '')}]: ").strip() or None
    active_input = input(f"  Active (y/n, blank to keep): ").strip().lower()
    is_active = None
    if active_input == "y":
        is_active = 1
    elif active_input == "n":
        is_active = 0

    if display_name or email or is_active is not None:
        try:
            svc.update_user(user["id"], display_name=display_name, email=email, is_active=is_active)
            print("  User details updated.")
        except Exception as e:
            print(f"  Error: {e}")

    # Update system/role assignments
    update_systems = input("\n  Update system/role assignments? (y/n): ").strip().lower()
    if update_systems == "y":
        systems_roles = []
        for key in SYSTEM_KEYS:
            current_role = next((s["role"] for s in user["systems"] if s["system_key"] == key), None)
            prompt = f"    {SYSTEM_LABELS[key]} [current: {current_role or 'none'}] (role/blank to keep/'remove'): "
            val = input(prompt).strip().lower()
            if val == "remove":
                continue
            elif val:
                systems_roles.append({"system_key": key, "role": val})
            elif current_role:
                systems_roles.append({"system_key": key, "role": current_role})

        try:
            svc.update_user_systems(user["id"], systems_roles)
            print("  System assignments updated.")
        except Exception as e:
            print(f"  Error: {e}")

    _pause()


def _reset_password(svc):
    _subheader("Reset Password")
    username = input("  Username: ").strip()
    if not username:
        return

    users = svc.get_all_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        print(f"  User '{username}' not found.")
        _pause()
        return

    new_pw = getpass.getpass("  New password: ")
    confirm = getpass.getpass("  Confirm password: ")
    if new_pw != confirm:
        print("  Passwords do not match.")
        _pause()
        return

    try:
        svc.reset_password(user["id"], new_pw)
        print("  Password reset successfully.")
    except Exception as e:
        print(f"  Error: {e}")
    _pause()


def _deactivate_user(svc):
    _subheader("Deactivate User")
    username = input("  Username: ").strip()
    if not username:
        return

    users = svc.get_all_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        print(f"  User '{username}' not found.")
        _pause()
        return

    if not _confirm(f"Deactivate user '{username}'?"):
        return

    try:
        svc.deactivate_user(user["id"])
        print("  User deactivated.")
    except Exception as e:
        print(f"  Error: {e}")
    _pause()


# ---------------------------------------------------------------------------
# 4. Student Analytics
# ---------------------------------------------------------------------------

def _student_analytics():
    svc = _get_analytics()
    admin = _get_admin()
    if not svc:
        return

    while True:
        _header("Student Analytics")
        print("\n  1) Summary overview")
        print("  2) Per-system breakdown")
        print("  3) Retention statistics")
        print("  4) Transfer rates")
        print("  5) Year-over-year trends")
        print("  6) Cross-system comparison")
        print("  7) Export CSV")
        print("  0) Back")

        choice = input("\n  Select: ").strip()

        if choice == "1":
            s = svc.get_summary()
            _subheader("Student Summary")
            print(f"    Total Students:  {s.get('total_students', 0)}")
            print(f"    Active:          {s.get('total_active', 0)}")
            print(f"    Transferred:     {s.get('total_transferred', 0)}")
            print(f"    Graduated:       {s.get('total_graduated', 0)}")
            _pause()

        elif choice == "2":
            s = svc.get_summary()
            _subheader("Per-System Breakdown")
            for sys_info in s.get("systems", []):
                print(f"\n    {sys_info.get('label', sys_info.get('system', ''))}:")
                print(f"      Total: {sys_info.get('total', 0)}  Active: {sys_info.get('active', 0)}  "
                      f"Transferred: {sys_info.get('transferred', 0)}  Graduated: {sys_info.get('graduated', 0)}")
            _pause()

        elif choice == "3":
            retention = svc.get_retention_stats()
            _subheader("Retention Statistics")
            print(f"\n  {'System':25s} {'Total':>7s} {'Active':>7s} {'Retained%':>9s} {'Dropout':>8s} {'Dropout%':>9s}")
            print("  " + "-" * 67)
            for r in retention:
                print(f"  {r.get('label', r.get('system', '')):25s} "
                      f"{r.get('total', 0):7d} {r.get('active', 0):7d} "
                      f"{r.get('retained_pct', 0):8.1f}% {r.get('dropped_out', 0):8d} "
                      f"{r.get('dropout_pct', 0):8.1f}%")
            _pause()

        elif choice == "4":
            transfers = svc.get_transfer_rates()
            _subheader("Transfer Rates")
            if not transfers:
                print("    No transfer data available.")
            else:
                print(f"\n  {'Source':25s} {'Destination':25s} {'Count':>6s} {'Rate%':>7s}")
                print("  " + "-" * 65)
                for t in transfers:
                    src = SYSTEM_LABELS.get(t.get("source_system", ""), t.get("source_system", ""))
                    dst = SYSTEM_LABELS.get(t.get("destination_system", ""), t.get("destination_system", ""))
                    print(f"  {src:25s} {dst:25s} {t.get('count', 0):6d} {t.get('rate_pct', 0):6.1f}%")
            _pause()

        elif choice == "5":
            trends = svc.get_year_trends()
            _subheader("Year-over-Year Trends")
            if not trends:
                print("    No trend data available.")
            else:
                print(f"\n  {'System':25s} {'Year':>6s} {'Students':>10s}")
                print("  " + "-" * 43)
                for t in trends:
                    label = SYSTEM_LABELS.get(t.get("system", ""), t.get("system", ""))
                    print(f"  {label:25s} {t.get('year', ''):>6s} {t.get('student_count', 0):10d}")
            _pause()

        elif choice == "6":
            _subheader("Cross-System Comparison")
            health = admin.get_system_health() if admin else []
            retention = svc.get_retention_stats()

            ret_map = {r.get("system", ""): r for r in retention}

            print(f"\n  {'System':25s} {'Students':>9s} {'Staff':>6s} {'DB (MB)':>8s} {'Retained%':>10s} {'Dropout%':>9s}")
            print("  " + "-" * 69)
            for h in health:
                r = ret_map.get(h["system"], {})
                print(f"  {h['label']:25s} {h['student_count']:9d} {h['staff_count']:6d} "
                      f"{h['db_size_mb']:8.1f} {r.get('retained_pct', 0):9.1f}% {r.get('dropout_pct', 0):8.1f}%")
            _pause()

        elif choice == "7":
            try:
                csv_data = svc.export_summary_csv()
                filename = f"superadmin_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                with open(filename, "w") as f:
                    f.write(csv_data)
                print(f"\n  Exported to: {filename}")
            except Exception as e:
                print(f"\n  Error exporting: {e}")
            _pause()

        elif choice == "0":
            break


# ---------------------------------------------------------------------------
# 5. Misconduct Overview
# ---------------------------------------------------------------------------

def _misconduct():
    _header("Academic Misconduct Overview")

    # Query misconduct tables directly across systems
    import sqlite3
    from pathlib import Path

    shared_dir = Path(__file__).resolve().parent.parent
    edu_root = shared_dir.parent

    db_paths = {
        "university": edu_root / "university_system" / "data" / "db_files" / "student_records.db",
    }

    misconduct_tables = [
        "academic_misconduct", "misconduct_cases", "behaviour_incidents",
        "disciplinary_records", "academic_integrity_cases",
    ]

    total = active = resolved = critical = 0

    for sys_key in SYSTEM_KEYS:
        db_path = db_paths.get(sys_key)
        if not db_path or not db_path.exists():
            print(f"  {SYSTEM_LABELS[sys_key]:25s}  Database not found")
            continue

        sys_total = sys_active = sys_critical = 0
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            for table in misconduct_tables:
                try:
                    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    count = row[0] if row else 0
                    sys_total += count

                    # Try to count active/critical
                    try:
                        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                        if "status" in cols:
                            a = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE status IN ('active', 'open', 'pending', 'under_review')").fetchone()
                            sys_active += a[0] if a else 0
                            r = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE status IN ('resolved', 'closed', 'completed')").fetchone()
                            resolved += r[0] if r else 0
                        if "severity" in cols:
                            c = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE severity IN ('critical', 'high', 'severe')").fetchone()
                            sys_critical += c[0] if c else 0
                    except Exception:
                        pass
                except Exception:
                    pass

            conn.close()
        except Exception:
            pass

        total += sys_total
        active += sys_active
        critical += sys_critical

        print(f"  {SYSTEM_LABELS[sys_key]:25s}  Total: {sys_total:>5}  Active: {sys_active:>5}  Critical: {sys_critical:>5}")

    _subheader("Global Totals")
    print(f"    Total Cases:    {total}")
    print(f"    Active:         {active}")
    print(f"    Resolved:       {resolved}")
    print(f"    Critical:       {critical}")
    _pause()


# ---------------------------------------------------------------------------
# 6. Notifications
# ---------------------------------------------------------------------------

def _notifications(user_info):
    nsvc = _get_notifications()
    if not nsvc:
        print("  Notification service unavailable.")
        _pause()
        return

    user_id = user_info.get("user_id") or user_info.get("id")

    while True:
        unread = nsvc.get_unread_count(user_id)
        _header(f"Notifications (Unread: {unread})")
        print("\n  1) View all notifications")
        print("  2) View unread only")
        print("  3) Mark all as read")
        print("  4) Send notification to user")
        print("  5) Broadcast to role")
        print("  0) Back")

        choice = input("\n  Select: ").strip()

        if choice == "1":
            notes = nsvc.get_all(user_id, limit=50)
            _display_notifications(notes)

        elif choice == "2":
            notes = nsvc.get_unread(user_id)
            _display_notifications(notes)

        elif choice == "3":
            nsvc.mark_all_read(user_id)
            print("  All notifications marked as read.")
            _pause()

        elif choice == "4":
            _send_notification(nsvc, user_id)

        elif choice == "5":
            _broadcast_notification(nsvc, user_id)

        elif choice == "0":
            break


def _display_notifications(notes):
    if not notes:
        print("\n  No notifications.")
    else:
        print(f"\n  {'ID':>5s}  {'From':12s} {'Title':30s} {'Priority':8s} {'Read':5s} {'Date':19s}")
        print("  " + "-" * 82)
        for n in notes:
            read = "Yes" if n.get("is_read") else "No"
            ts = (n.get("created_at") or "")[:19]
            title = (n.get("title") or "")[:30]
            print(f"  {n.get('id', ''):>5}  {n.get('sender_system', ''):12s} "
                  f"{title:30s} {n.get('priority', 'normal'):8s} {read:5s} {ts:19s}")

        # View detail
        detail_id = input("\n  Enter notification ID for detail (or blank): ").strip()
        if detail_id.isdigit():
            note = next((n for n in notes if str(n.get("id")) == detail_id), None)
            if note:
                print(f"\n    Title:    {note.get('title', '')}")
                print(f"    From:     {note.get('sender_system', '')} (user {note.get('sender_user_id', '')})")
                print(f"    Priority: {note.get('priority', 'normal')}")
                print(f"    Date:     {note.get('created_at', '')}")
                print(f"    Message:  {note.get('message', 'N/A')}")
    _pause()


def _send_notification(nsvc, sender_id):
    _subheader("Send Notification")
    recipient_id = input("  Recipient user ID: ").strip()
    if not recipient_id.isdigit():
        print("  Invalid user ID.")
        return

    print("  Target system:")
    for i, key in enumerate(SYSTEM_KEYS, 1):
        print(f"    {i}) {SYSTEM_LABELS[key]}")
    sys_choice = input("  System: ").strip()
    target_system = None
    if sys_choice.isdigit() and 1 <= int(sys_choice) <= len(SYSTEM_KEYS):
        target_system = SYSTEM_KEYS[int(sys_choice) - 1]
    else:
        print("  Invalid system.")
        return

    title = input("  Title: ").strip()
    if not title:
        print("  Title is required.")
        return

    priority = input("  Priority (normal/high/urgent) [normal]: ").strip() or "normal"
    message = input("  Message (optional): ").strip()

    try:
        nsvc.send(sender_id, "__superadmin__", int(recipient_id), target_system,
                  title, message=message or None, priority=priority)
        print("  Notification sent.")
    except Exception as e:
        print(f"  Error: {e}")
    _pause()


def _broadcast_notification(nsvc, sender_id):
    _subheader("Broadcast to Role")

    print("  Target system:")
    for i, key in enumerate(SYSTEM_KEYS, 1):
        print(f"    {i}) {SYSTEM_LABELS[key]}")
    sys_choice = input("  System: ").strip()
    target_system = None
    if sys_choice.isdigit() and 1 <= int(sys_choice) <= len(SYSTEM_KEYS):
        target_system = SYSTEM_KEYS[int(sys_choice) - 1]
    else:
        print("  Invalid system.")
        return

    target_role = input("  Target role (admin/staff/teacher/student/parent): ").strip()
    if not target_role:
        return

    title = input("  Title: ").strip()
    if not title:
        return

    priority = input("  Priority (normal/high/urgent) [normal]: ").strip() or "normal"
    message = input("  Message (optional): ").strip()

    try:
        count = nsvc.send_to_role(sender_id, "__superadmin__", target_system,
                                  target_role, title, message=message or None, priority=priority)
        print(f"  Broadcast sent to {count} user(s).")
    except Exception as e:
        print(f"  Error: {e}")
    _pause()


# ---------------------------------------------------------------------------
# 7. Student Search
# ---------------------------------------------------------------------------

def _student_search():
    _header("Cross-System Student Search")
    jsvc = _get_journey()
    if not jsvc:
        return

    query = input("\n  Search by name: ").strip()
    if not query:
        return

    results = jsvc.search_student(query)
    if not results:
        print("\n  No students found.")
    else:
        print(f"\n  Found {len(results)} result(s):\n")
        print(f"  {'#':>3s}  {'System':15s} {'Student ID':12s} {'Name':30s} {'Status':12s} {'Year':8s}")
        print("  " + "-" * 82)
        for i, r in enumerate(results, 1):
            sys_label = SYSTEM_LABELS.get(r.get("system", ""), r.get("system", ""))
            print(f"  {i:3d}  {sys_label:15s} {r.get('student_id', ''):12s} "
                  f"{r.get('name', ''):30s} {r.get('status', ''):12s} {r.get('year_group', ''):8s}")

    _pause()


# ---------------------------------------------------------------------------
# 8. Student Journey
# ---------------------------------------------------------------------------

def _student_journey():
    _header("Student Journey Tracker")
    jsvc = _get_journey()
    if not jsvc:
        return

    query = input("\n  Student name or ID: ").strip()
    if not query:
        return

    # Search first
    results = jsvc.search_student(query)
    if not results:
        print("\n  No students found.")
        _pause()
        return

    if len(results) == 1:
        picked = results[0]
    else:
        print(f"\n  Found {len(results)} result(s):")
        for i, r in enumerate(results, 1):
            sys_label = SYSTEM_LABELS.get(r.get("system", ""), r.get("system", ""))
            print(f"    {i}) {r.get('name', '')} ({sys_label}, {r.get('student_id', '')})")
        sel = input("\n  Select student #: ").strip()
        try:
            picked = results[int(sel) - 1]
        except (ValueError, IndexError):
            print("  Invalid selection.")
            return

    # Get journey
    journey = jsvc.get_journey(
        student_id=picked.get("student_id") or picked.get("id"),
        system=picked.get("system"),
    )

    if not journey:
        print("\n  No journey data found.")
    else:
        _subheader(f"Journey for: {picked.get('name', 'Unknown')}")
        for i, stage in enumerate(journey):
            sys_label = SYSTEM_LABELS.get(stage.get("system", ""), stage.get("system", ""))
            connector = "  |" if i < len(journey) - 1 else "   "

            print(f"\n  [{i + 1}] {sys_label}")
            print(f"  {connector}   Student ID:  {stage.get('student_id', 'N/A')}")
            print(f"  {connector}   Status:      {stage.get('status', 'N/A')}")
            print(f"  {connector}   Year Group:  {stage.get('year_group', 'N/A')}")
            print(f"  {connector}   Enrolled:    {stage.get('enrolled_date', 'N/A')}")

            history = stage.get("academic_history", [])
            if history:
                print(f"  {connector}   History:")
                for h in history[:5]:
                    print(f"  {connector}     - {h}")
            if i < len(journey) - 1:
                print(f"  {connector}")
                print(f"  {'  v'}")

    _pause()


# ---------------------------------------------------------------------------
# 9. Permission Matrix
# ---------------------------------------------------------------------------

def _permission_matrix():
    _header("Permission Matrix")
    svc = _get_admin()
    if not svc:
        return

    users = svc.get_all_users()
    if not users:
        print("\n  No users found.")
        _pause()
        return

    print(f"\n  {'Username':15s} {'Display Name':20s} {'Primary':10s} {'Secondary':10s} {'College':10s} {'University':10s}")
    print("  " + "-" * 77)

    for u in users:
        roles_by_system = {}
        for s in u["systems"]:
            roles_by_system[s["system_key"]] = s["role"]

        pri = roles_by_system.get("primary", "\u2014")
        sec = roles_by_system.get("secondary", roles_by_system.get("school", "\u2014"))
        col = roles_by_system.get("college", "\u2014")
        uni = roles_by_system.get("university", "\u2014")

        print(f"  {u['username']:15s} {u.get('display_name', ''):20s} "
              f"{pri:10s} {sec:10s} {col:10s} {uni:10s}")

    _pause()


# ---------------------------------------------------------------------------
# 10. Audit Log
# ---------------------------------------------------------------------------

def _audit_log():
    svc = _get_admin()
    if not svc:
        return

    while True:
        _header("Audit Log")
        print("\n  1) View recent entries")
        print("  2) Filter by type")
        print("  3) Search entries")
        print("  4) Filter by date range")
        print("  5) Export CSV")
        print("  0) Back")

        choice = input("\n  Select: ").strip()

        if choice == "1":
            entries = svc.get_audit_summary(limit=30)
            _display_audit(entries)

        elif choice == "2":
            print("\n  Type: 1) notification  2) transfer")
            t = input("  Select: ").strip()
            type_filter = "notification" if t == "1" else "transfer" if t == "2" else None
            entries = svc.get_audit_summary(limit=50, type_filter=type_filter)
            _display_audit(entries)

        elif choice == "3":
            search = input("\n  Search text: ").strip()
            entries = svc.get_audit_summary(limit=50, search_text=search)
            _display_audit(entries)

        elif choice == "4":
            date_from = input("\n  From date (YYYY-MM-DD, blank for none): ").strip() or None
            date_to = input("  To date (YYYY-MM-DD, blank for none): ").strip() or None
            entries = svc.get_audit_summary(limit=100, date_from=date_from, date_to=date_to)
            _display_audit(entries)

        elif choice == "5":
            entries = svc.get_audit_summary(limit=500)
            if entries:
                filename = f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                import csv
                with open(filename, "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=["type", "timestamp", "description", "details"])
                    w.writeheader()
                    w.writerows(entries)
                print(f"\n  Exported {len(entries)} entries to: {filename}")
            else:
                print("\n  No entries to export.")
            _pause()

        elif choice == "0":
            break


def _display_audit(entries):
    if not entries:
        print("\n  No audit entries found.")
    else:
        print(f"\n  {'Type':12s} {'Timestamp':19s} {'Description':40s}")
        print("  " + "-" * 73)
        for e in entries:
            ts = (e["timestamp"] or "")[:19]
            desc = (e["description"] or "")[:40]
            print(f"  {e['type']:12s} {ts:19s} {desc:40s}")
            if e.get("details"):
                print(f"  {'':12s} {'':19s} {e['details'][:60]}")
    _pause()


# ---------------------------------------------------------------------------
# 11. Backup / Restore
# ---------------------------------------------------------------------------

def _backup_restore():
    svc = _get_admin()
    if not svc:
        return

    while True:
        _header("Backup / Restore")

        health = svc.get_system_health()

        print("\n  Current Database Status:")
        for h in health:
            print(f"    {h['label']:25s}  {h['db_size_mb']:.1f} MB  [{h['status']}]")

        print("\n\n  1) Backup individual system")
        print("  2) Backup all systems")
        print("  3) Backup auth database")
        print("  0) Back")

        choice = input("\n  Select: ").strip()

        if choice == "1":
            print("\n  Select system to backup:")
            for i, key in enumerate(SYSTEM_KEYS, 1):
                print(f"    {i}) {SYSTEM_LABELS[key]}")
            sel = input("  System: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(SYSTEM_KEYS):
                sys_key = SYSTEM_KEYS[int(sel) - 1]
                try:
                    path = svc.backup_database(sys_key)
                    print(f"\n  Backup created: {path}")
                except Exception as e:
                    print(f"\n  Error: {e}")
            _pause()

        elif choice == "2":
            print("\n  Backing up all systems...")
            for key in SYSTEM_KEYS:
                try:
                    path = svc.backup_database(key)
                    print(f"    {SYSTEM_LABELS[key]:25s} -> {path}")
                except Exception as e:
                    print(f"    {SYSTEM_LABELS[key]:25s} ERROR: {e}")
            _pause()

        elif choice == "3":
            try:
                path = svc.backup_database("auth")
                print(f"\n  Auth database backup: {path}")
            except Exception as e:
                print(f"\n  Error: {e}")
            _pause()

        elif choice == "0":
            break


# ---------------------------------------------------------------------------
# 12. Batch Operations
# ---------------------------------------------------------------------------

def _batch_operations():
    svc = _get_admin()
    if not svc:
        return

    while True:
        _header("Batch Operations")
        print("\n  1) Bulk role change")
        print("  2) Bulk deactivation")
        print("  0) Back")

        choice = input("\n  Select: ").strip()

        if choice == "1":
            _bulk_role_change(svc)
        elif choice == "2":
            _bulk_deactivate(svc)
        elif choice == "0":
            break


def _bulk_role_change(svc):
    _subheader("Bulk Role Change")

    print("  Target system:")
    for i, key in enumerate(SYSTEM_KEYS, 1):
        print(f"    {i}) {SYSTEM_LABELS[key]}")
    sel = input("  System: ").strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(SYSTEM_KEYS)):
        return
    system = SYSTEM_KEYS[int(sel) - 1]

    current_role = input("  Current role to change FROM: ").strip()
    new_role = input("  New role to change TO: ").strip()

    if not current_role or not new_role:
        return

    users = svc.get_all_users(system=system, role=current_role)
    if not users:
        print(f"\n  No users found with role '{current_role}' in {SYSTEM_LABELS[system]}.")
        _pause()
        return

    print(f"\n  Found {len(users)} user(s) with role '{current_role}' in {SYSTEM_LABELS[system]}.")
    if not _confirm(f"Change all {len(users)} users from '{current_role}' to '{new_role}'?"):
        return

    count = 0
    for u in users:
        try:
            new_systems = []
            for s in u["systems"]:
                if s["system_key"] == system and s["role"] == current_role:
                    new_systems.append({"system_key": system, "role": new_role})
                else:
                    new_systems.append(s)
            svc.update_user_systems(u["id"], new_systems)
            count += 1
        except Exception:
            pass

    print(f"\n  Updated {count}/{len(users)} users.")
    _pause()


def _bulk_deactivate(svc):
    _subheader("Bulk Deactivation")

    print("  Target system:")
    for i, key in enumerate(SYSTEM_KEYS, 1):
        print(f"    {i}) {SYSTEM_LABELS[key]}")
    sel = input("  System: ").strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(SYSTEM_KEYS)):
        return
    system = SYSTEM_KEYS[int(sel) - 1]

    role = input("  Role to deactivate (or blank for all): ").strip() or None

    users = svc.get_all_users(system=system, role=role)
    active_users = [u for u in users if u.get("is_active", 1)]

    if not active_users:
        print("\n  No active users matching criteria.")
        _pause()
        return

    print(f"\n  Found {len(active_users)} active user(s).")
    if not _confirm(f"Deactivate all {len(active_users)} matching users?"):
        return

    count = 0
    for u in active_users:
        try:
            svc.deactivate_user(u["id"])
            count += 1
        except Exception:
            pass

    print(f"\n  Deactivated {count}/{len(active_users)} users.")
    _pause()


# ---------------------------------------------------------------------------
# 13. Active Sessions
# ---------------------------------------------------------------------------

def _active_sessions():
    svc = _get_admin()
    if not svc:
        return

    while True:
        _header("Active Sessions")
        sessions = svc.get_active_sessions()

        if not sessions:
            print("\n  No active sessions.")
        else:
            print(f"\n  {'Username':15s} {'User ID':>8s} {'Token':12s} {'Created':19s} {'Expires':19s}")
            print("  " + "-" * 75)
            for s in sessions:
                print(f"  {s.get('username', ''):15s} {s.get('user_id', ''):>8} "
                      f"{s.get('token_preview', ''):12s} "
                      f"{(s.get('created_at') or '')[:19]:19s} "
                      f"{(s.get('expires_at') or '')[:19]:19s}")

        print(f"\n  Total: {len(sessions)} session(s)")
        print("\n  1) Force logout a user")
        print("  2) Refresh")
        print("  0) Back")

        choice = input("\n  Select: ").strip()

        if choice == "1":
            uid = input("  User ID to force logout: ").strip()
            if uid.isdigit() and _confirm(f"Force logout user ID {uid}?"):
                try:
                    svc.force_logout_user(int(uid))
                    print("  Sessions terminated.")
                except Exception as e:
                    print(f"  Error: {e}")
                _pause()
        elif choice == "2":
            continue
        elif choice == "0":
            break


# ---------------------------------------------------------------------------
# 14. Quick Launch
# ---------------------------------------------------------------------------

def _quick_launch(user_info, auth):
    _header("Quick Launch")
    print("\n  Launch a specific system CLI:\n")

    for i, key in enumerate(SYSTEM_KEYS, 1):
        print(f"    {i}) {SYSTEM_LABELS[key]}")
    print("    0) Cancel")

    choice = input("\n  Select system: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(SYSTEM_KEYS)):
        return None

    system = SYSTEM_KEYS[int(choice) - 1]

    # Find the user's role in this system
    role = "admin"
    for s in user_info.get("systems", []):
        if s["system_key"] == system:
            role = s["role"]
            break

    print(f"\n  Launching {SYSTEM_LABELS[system]} as {role}...")
    return system, role


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(user_info, auth):
    """Run the Super Admin CLI Dashboard.

    Returns ``(system_key, role)`` if the user chooses Quick Launch,
    or ``None`` if they exit normally.
    """
    display = user_info.get("display_name") or user_info.get("username", "Admin")

    while True:
        _header(f"Super Admin Dashboard  |  {display}")
        print("""
   1) Dashboard Overview         8) Student Journey
   2) System Health              9) Permission Matrix
   3) User Management           10) Audit Log
   4) Student Analytics         11) Backup / Restore
   5) Misconduct Overview       12) Batch Operations
   6) Notifications             13) Active Sessions
   7) Student Search            14) Quick Launch

   G) Switch to GUI Dashboard
   0) Logout                    Q) Shutdown
""")

        choice = input("  Select: ").strip()

        if choice == "1":
            _dashboard(user_info)
        elif choice == "2":
            _system_health()
        elif choice == "3":
            _user_management()
        elif choice == "4":
            _student_analytics()
        elif choice == "5":
            _misconduct()
        elif choice == "6":
            _notifications(user_info)
        elif choice == "7":
            _student_search()
        elif choice == "8":
            _student_journey()
        elif choice == "9":
            _permission_matrix()
        elif choice == "10":
            _audit_log()
        elif choice == "11":
            _backup_restore()
        elif choice == "12":
            _batch_operations()
        elif choice == "13":
            _active_sessions()
        elif choice == "14":
            result = _quick_launch(user_info, auth)
            if result:
                return result
        elif choice.lower() == "g":
            from education_system import switch as _switch
            print("\n  Switching to GUI dashboard...\n")
            _switch.request_switch("__superadmin__", "gui")
            return None
        elif choice == "0":
            print("\n  Logging out...\n")
            return None
        elif choice.lower() == "q":
            if _confirm("Shut down the application?"):
                print("\n  Shutting down...\n")
                import sys
                sys.exit(0)
        else:
            print("\n  Invalid option.")
