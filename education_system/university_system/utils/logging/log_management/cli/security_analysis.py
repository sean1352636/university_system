"""Security analysis CLI functions."""

from datetime import datetime, timedelta
from collections import defaultdict


def security_analysis_menu(log_manager, auth):
    """Security analysis menu"""
    print("\n\U0001f512 SECURITY ANALYSIS")
    print("="*25)

    print("1. Failed Login Analysis")
    print("2. Unusual Activity Detection")
    print("3. Admin Action Audit")
    print("4. User Behavior Analysis")
    print("5. Return")

    choice = input("Choose analysis: ")

    if choice == '1':
        analyze_failed_logins(log_manager)
    elif choice == '2':
        detect_unusual_activity(log_manager)
    elif choice == '3':
        audit_admin_actions(log_manager)
    elif choice == '4':
        analyze_user_behavior(log_manager)


def analyze_failed_logins(log_manager):
    """Analyze failed login attempts"""
    print("\n\U0001f510 FAILED LOGIN ANALYSIS")
    print("="*30)

    # Get failed logins from last 24 hours
    filters = {
        'date_from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d'),
        'action': 'login',
        'status': 'failure'
    }

    failed_logins = log_manager.db.search_logs(filters, limit=1000)

    if not failed_logins:
        print("No failed logins found in the last 24 hours.")
        return

    # Analyze by user
    user_failures = defaultdict(int)
    for login in failed_logins:
        user_failures[login['username']] += 1

    print(f"Total failed logins: {len(failed_logins)}")
    print(f"Unique users with failures: {len(user_failures)}")

    print("\nTop users with failed logins:")
    sorted_failures = sorted(user_failures.items(), key=lambda x: x[1], reverse=True)
    for user, count in sorted_failures[:10]:
        print(f"  {user}: {count} failures")

    # Users with excessive failures (potential brute force)
    suspicious_users = [user for user, count in user_failures.items() if count >= 5]
    if suspicious_users:
        print(f"\n\u26a0\ufe0f Users with 5+ failed logins (potential brute force):")
        for user in suspicious_users:
            print(f"  {user}: {user_failures[user]} failures")

    input("\nPress Enter to continue...")


def detect_unusual_activity(log_manager):
    """Detect unusual activity patterns"""
    print("\n\U0001f575\ufe0f UNUSUAL ACTIVITY DETECTION")
    print("="*35)

    # Get activities from last 7 days
    filters = {
        'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    }

    activities = log_manager.db.search_logs(filters, limit=5000)

    if not activities:
        print("No activities found for analysis.")
        return

    # Analyze by hour
    hour_activity = defaultdict(int)
    unusual_hours = []

    for activity in activities:
        try:
            hour = datetime.fromisoformat(activity['timestamp']).hour
            hour_activity[hour] += 1

            # Flag activities between 2-6 AM as unusual
            if 2 <= hour <= 6:
                unusual_hours.append(activity)
        except (ValueError, KeyError, TypeError):
            continue

    print("Activity by hour of day:")
    for hour in range(24):
        count = hour_activity.get(hour, 0)
        bar = "\u2588" * (count // 10)  # Simple bar chart
        print(f"{hour:02d}:00 | {count:4d} | {bar}")

    if unusual_hours:
        print(f"\n\u26a0\ufe0f Activities during unusual hours (2-6 AM): {len(unusual_hours)}")
        recent_unusual = unusual_hours[-5:]  # Show last 5
        for activity in recent_unusual:
            timestamp = activity['timestamp'][:19]
            user = activity['username']
            action = activity['action']
            print(f"  {timestamp} - {user}: {action}")

    input("\nPress Enter to continue...")


def audit_admin_actions(log_manager):
    """Audit administrative actions"""
    print("\n\U0001f468\u200d\U0001f4bc ADMIN ACTION AUDIT")
    print("="*25)

    # Get admin actions from last 30 days
    filters = {
        'date_from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
        'role': 'admin'
    }

    admin_actions = log_manager.db.search_logs(filters, limit=1000)

    if not admin_actions:
        print("No admin actions found in the last 30 days.")
        return

    # Categorize actions
    sensitive_actions = ['delete', 'user_management', 'system_config']
    regular_actions = ['create', 'read', 'update']

    sensitive_count = 0
    regular_count = 0
    action_breakdown = defaultdict(int)
    admin_breakdown = defaultdict(int)

    for action in admin_actions:
        action_type = action['action']
        admin_user = action['username']

        action_breakdown[action_type] += 1
        admin_breakdown[admin_user] += 1

        if action_type in sensitive_actions:
            sensitive_count += 1
        else:
            regular_count += 1

    print(f"Total admin actions: {len(admin_actions)}")
    print(f"Sensitive actions: {sensitive_count}")
    print(f"Regular actions: {regular_count}")

    print("\nActions by type:")
    for action_type, count in sorted(action_breakdown.items(), key=lambda x: x[1], reverse=True):
        sensitivity = "\u26a0\ufe0f" if action_type in sensitive_actions else "\u2705"
        print(f"  {sensitivity} {action_type}: {count}")

    print("\nActions by admin:")
    for admin, count in sorted(admin_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"  {admin}: {count} actions")

    # Show recent sensitive actions
    recent_sensitive = [a for a in admin_actions if a['action'] in sensitive_actions][-10:]
    if recent_sensitive:
        print("\nRecent sensitive admin actions:")
        for action in recent_sensitive:
            timestamp = action['timestamp'][:19]
            user = action['username']
            action_type = action['action']
            module = action['module']
            print(f"  {timestamp} - {user}: {action_type} on {module}")

    input("\nPress Enter to continue...")


def analyze_user_behavior(log_manager):
    """Analyze user behavior patterns"""
    print("\n\U0001f465 USER BEHAVIOR ANALYSIS")
    print("="*30)

    # Get activities from last 7 days
    filters = {
        'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    }

    activities = log_manager.db.search_logs(filters, limit=5000)

    if not activities:
        print("No activities found for analysis.")
        return

    # Analyze user patterns
    user_stats = defaultdict(lambda: {
        'total_actions': 0,
        'unique_modules': set(),
        'actions_by_hour': defaultdict(int),
        'success_rate': 0,
        'failures': 0
    })

    for activity in activities:
        user = activity['username']
        stats = user_stats[user]

        stats['total_actions'] += 1
        stats['unique_modules'].add(activity['module'])

        try:
            hour = datetime.fromisoformat(activity['timestamp']).hour
            stats['actions_by_hour'][hour] += 1
        except (ValueError, KeyError, TypeError):
            pass

        if activity['status'] == 'failure':
            stats['failures'] += 1

    # Calculate success rates
    for user, stats in user_stats.items():
        if stats['total_actions'] > 0:
            stats['success_rate'] = ((stats['total_actions'] - stats['failures']) / stats['total_actions']) * 100
        stats['unique_modules'] = len(stats['unique_modules'])

    # Sort by activity level
    sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['total_actions'], reverse=True)

    print(f"User behavior analysis for {len(sorted_users)} users:")
    print(f"{'User':<15} {'Actions':<8} {'Modules':<8} {'Success%':<8} {'Failures':<8}")
    print("-" * 60)

    for user, stats in sorted_users[:15]:  # Top 15 users
        print(f"{user:<15} {stats['total_actions']:<8} {stats['unique_modules']:<8} "
              f"{stats['success_rate']:<7.1f}% {stats['failures']:<8}")

    # Identify unusual patterns
    print("\nUnusual patterns detected:")

    # Users with low success rates
    low_success_users = [(user, stats) for user, stats in user_stats.items()
                        if stats['success_rate'] < 80 and stats['total_actions'] > 10]

    if low_success_users:
        print("Users with low success rates (<80%):")
        for user, stats in low_success_users:
            print(f"  {user}: {stats['success_rate']:.1f}% success rate ({stats['failures']} failures)")

    # Users with very high activity
    high_activity_users = [(user, stats) for user, stats in user_stats.items()
                          if stats['total_actions'] > 100]

    if high_activity_users:
        print("Users with very high activity (>100 actions):")
        for user, stats in high_activity_users:
            print(f"  {user}: {stats['total_actions']} actions")

    input("\nPress Enter to continue...")
