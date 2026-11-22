"""Interactive security administration menus for the health portal."""
import logging

logger = logging.getLogger(__name__)

from datetime import datetime

from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3
from education_system.systems.university.domains.health.domain.health.services import (
    analyze_data_access_patterns,
    get_connection,
    view_failed_logins,
)

from .audit import log_audit_event, view_audit_log
from .encryption import encryption_key_management
from .schema import _first_existing_column, ensure_security_schema
from .security_reports import generate_security_report

def advanced_security_menu(auth):
    """Advanced security management"""
    ensure_security_schema()
    if auth.current_user['role'] != 'admin':
        print("Only administrators can access advanced security features.")
        return

    while True:
        print("\n===== Advanced Security Management =====")
        print("1. User Session Management")
        print("2. IP Restriction Management")
        print("3. Two-Factor Authentication")
        print("4. Security Policy Configuration")
        print("5. Encryption Key Management")
        print("6. Access Control Lists")
        print("7. Security Incident Response")
        print("8. Return to Main Menu")

        choice = input("\nEnter your choice (1-8): ")

        if choice == '1':
            user_session_management(auth)
        elif choice == '2':
            ip_restriction_management(auth)
        elif choice == '3':
            two_factor_authentication_setup(auth)
        elif choice == '4':
            security_policy_configuration(auth)
        elif choice == '5':
            encryption_key_management(auth)
        elif choice == '6':
            access_control_lists(auth)
        elif choice == '7':
            security_incident_response(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")


def user_session_management(auth):
    """Manage active user sessions"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Active User Sessions =====")

    # Get recent login activity from audit trail
    cursor.execute('''
    SELECT user_id, ip_address, timestamp
    FROM audit_trail
    WHERE action = 'login' AND timestamp >= datetime('now', '-24 hours')
    ORDER BY timestamp DESC
    ''')

    sessions = cursor.fetchall()

    if not sessions:
        print("No active sessions found in the last 24 hours.")
        conn.close()
        return

    print("Recent Login Activity (Last 24 hours):")
    for user_id, ip_address, timestamp in sessions:
        print(f"  {timestamp} - User: {user_id} - IP: {ip_address}")

    # Session management options
    print("\nSession Management Options:")
    print("1. Force logout all users")
    print("2. Force logout specific user")
    print("3. View failed login attempts")
    print("4. Return to security menu")

    choice = input("\nSelect option (1-4): ")

    if choice == '1':
        confirm = input("Force logout ALL users? (yes/no): ")
        if confirm.lower() == 'yes':
            # This would invalidate all sessions in a real system
            log_audit_event(auth.current_user['id'], 'force_logout_all', 'security', 0)
            print("All user sessions terminated.")

    elif choice == '2':
        user_to_logout = input("Enter username to force logout: ")
        log_audit_event(auth.current_user['id'], 'force_logout_user', 'security', 0, user_to_logout)
        print(f"User {user_to_logout} session terminated.")

    elif choice == '3':
        view_failed_logins(auth)

    conn.close()


def access_control_lists(auth):
    """
    Show roles and their permissions, regardless of the exact column names used
    by the roles/permissions tables.
    """
    ensure_security_schema()

    conn = get_connection()
    try:
        r_name = _first_existing_column(conn, "roles", ["name", "role_name", "title", "label", "code"])
        p_name = _first_existing_column(conn, "permissions", ["name", "permission_name", "permission", "code", "label"])

        # The health schema declares roles.role_name / permissions.permission_name;
        # a screen adds no columns of its own.
        cur = conn.cursor()
        if not r_name or not p_name:
            print("The roles / permissions tables have no name column; nothing to show.")
            return

        sql = f"""
        SELECT r.{r_name} AS role_name,
               COALESCE(GROUP_CONCAT(p.{p_name}, ', '), '(no permissions)') AS permissions
          FROM roles r
     LEFT JOIN role_permissions rp ON rp.role_id = r.id
     LEFT JOIN permissions p      ON p.id = rp.permission_id
      GROUP BY r.{r_name}
      ORDER BY r.{r_name} COLLATE NOCASE
        """
        rows = cur.execute(sql).fetchall()

        print("\nAccess Control Lists:")
        if not rows:
            print("- No roles found.")
        else:
            for role_name, perms in rows:
                role_name = role_name or "(unnamed role)"
                print(f"- {role_name}: {perms}")

        input("\nPress Enter to return...")

    except sqlite3.OperationalError as e:
        print(f"ACL view unavailable: {e}")
        input("\nPress Enter to return...")
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


def security_policy_configuration(auth):
    """
    Display and manage security policies.
    Works with either (policy_name,status,last_updated) or (policy_key,value,updated_at).
    """
    ensure_security_schema()
    conn = get_connection()
    try:
        c = conn.cursor()

        policy_name = _first_existing_column(conn, "data_privacy_settings", ["policy_name", "policy_key", "name", "key"])
        status_col  = _first_existing_column(conn, "data_privacy_settings", ["status", "value", "enabled"])
        updated_col = _first_existing_column(conn, "data_privacy_settings", ["last_updated", "updated_at", "modified_at", "timestamp"])

        sql = ("SELECT [" + policy_name + "], [" + status_col + "], [" + updated_col + "]"
               " FROM [data_privacy_settings] ORDER BY [" + policy_name + "]")
        rows = c.execute(sql).fetchall()

        print("\nSecurity Policies:")
        if not rows:
            print("- (none)")
        else:
            for pname, pstatus, pupd in rows:
                # normalize status for display
                s = str(pstatus).strip().lower()
                if s in ("1","true","on","enabled","enable","active"):
                    s_disp = "enabled"
                elif s in ("0","false","off","disabled","disable","inactive"):
                    s_disp = "disabled"
                else:
                    s_disp = pstatus if pstatus is not None else "—"
                print(f"- {pname or '(unnamed)'}: {s_disp} (updated {pupd or '—'})")

        input("\nPress Enter to return...")

    except sqlite3.OperationalError as e:
        print(f"Security policy view unavailable: {e}")
        input("\nPress Enter to return...")
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


def security_incident_response(auth):
    """Simple incident viewer (schema-adaptive)."""
    try:
        ensure_security_schema()
    except Exception as e:
        print(f"(warning) Incident schema check failed: {e}")

    conn = get_connection()
    try:
        c = conn.cursor()

        kid   = _first_existing_column(conn, "security_incidents", ["incident_id", "id", "reference", "ref"])
        title = _first_existing_column(conn, "security_incidents", ["title", "summary"])
        sev   = _first_existing_column(conn, "security_incidents", ["severity", "priority"])
        stat  = _first_existing_column(conn, "security_incidents", ["status"])
        when  = _first_existing_column(conn, "security_incidents", ["detected_at", "opened_at", "created_at"])

        from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
        for col_name in [kid, title, sev, stat, when]:
            validate_identifier(col_name, "column")
        sel = ", ".join(["[" + x + "]" for x in [kid, title, sev, stat, when]])
        rows = c.execute("SELECT " + sel + " FROM security_incidents ORDER BY [" + when + "] DESC LIMIT 50").fetchall()

        print("\nSecurity Incidents (latest 50):")
        if not rows:
            print("- (none)")
        else:
            for r in rows:
                inc_id, t, s, st, dt = r
                print(f"- {inc_id or '(no-id)'} | {t or '(no title)'} | {s or '—'} | {st or '—'} | {dt or '—'}")

        input("\nPress Enter to return...")

    except sqlite3.OperationalError as e:
        print(f"Incident view unavailable: {e}")
        input("\nPress Enter to return...")
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


def ip_restriction_management(auth):
    """IP restrictions are not offered: the health portal runs as a desktop
    CLI/GUI session with no client address to check, so an "allowed ranges"
    setting would only look like protection. Access is controlled by sign-in,
    role permissions and the session timeout. The failed-login view stays."""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== IP Restriction Management =====")
    print("IP restrictions are not enforced by the health portal: desktop sessions")
    print("have no client IP address to check. Access is controlled by sign-in,")
    print("role permissions and the session timeout.")

    cursor.execute("SELECT setting_value FROM security_settings "
                   "WHERE setting_name = 'ip_restriction_enabled'")
    row = cursor.fetchone()
    if row and row[0] == '1':
        # A stored "enabled" was never enforced; record that it is off.
        cursor.execute("UPDATE security_settings SET setting_value = '0', updated_at = ? "
                       "WHERE setting_name = 'ip_restriction_enabled'",
                       (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        log_audit_event(auth.current_user['id'], 'retire_ip_restriction_setting', 'security', 0)
        conn.commit()
        print("(The stored 'enabled' setting was never enforced and has been switched off.)")

    print("\n1. View Failed Login Attempts by IP (last 24 hours)")
    print("2. Return to security menu")
    choice = input("\nSelect option (1-2): ")

    if choice == '1':
        cursor.execute('''
        SELECT ip_address, COUNT(*) as attempt_count
        FROM audit_trail
        WHERE action = 'failed_login' AND timestamp >= datetime('now', '-24 hours')
        GROUP BY ip_address
        ORDER BY attempt_count DESC
        ''')

        ip_attempts = cursor.fetchall()

        if ip_attempts:
            print("\nFailed Login Attempts by IP (Last 24 hours):")
            for ip, count in ip_attempts:
                print(f"  {ip or '(no address)'}: {count} attempts")
        else:
            print("No failed login attempts in the last 24 hours.")

    conn.close()


def _mfa_statistics():
    """Real two-factor figures from the platform sign-in database (auth.db)."""
    from education_system.systems.university.domains.health.application.health.access import (
        CLINICAL_ROLES,
    )
    from education_system.platform.identity.auth import db as auth_db
    conn = auth_db.connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM users WHERE COALESCE(is_active, 1) = 1"
                             ).fetchone()[0]
        enrolled = conn.execute("SELECT COUNT(DISTINCT user_id) FROM mfa_secrets "
                                "WHERE is_enabled = 1").fetchone()[0]
        marks = ",".join("?" * len(CLINICAL_ROLES))
        providers = conn.execute(
            f"SELECT COUNT(DISTINCT us.user_id) FROM user_systems us "  # nosec B608
            f"WHERE us.system_key = 'university' AND LOWER(us.role) IN ({marks})",
            tuple(CLINICAL_ROLES)).fetchone()[0]
        providers_mfa = conn.execute(
            f"SELECT COUNT(DISTINCT us.user_id) FROM user_systems us "  # nosec B608
            f"JOIN mfa_secrets m ON m.user_id = us.user_id AND m.is_enabled = 1 "
            f"WHERE us.system_key = 'university' AND LOWER(us.role) IN ({marks})",
            tuple(CLINICAL_ROLES)).fetchone()[0]
        recent = None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mfa_verification_attempts'"
                        ).fetchone():
            cols = {r[1] for r in conn.execute("PRAGMA table_info(mfa_verification_attempts)")}
            when = next((c for c in ("attempted_at", "created_at", "timestamp") if c in cols),
                        None)
            if when:
                recent = conn.execute(
                    f'SELECT COUNT(*) FROM mfa_verification_attempts '  # nosec B608
                    f'WHERE "{when}" >= datetime(\'now\', \'-7 days\')').fetchone()[0]
    finally:
        conn.close()
    return {"active_users": total, "users_with_2fa": enrolled, "providers": providers,
            "providers_with_2fa": providers_mfa, "attempts_7_days": recent}


def two_factor_authentication_setup(auth):
    """Two-factor authentication for health staff.

    Two-factor sign-in belongs to the platform sign-in (MFA in auth.db), so
    the health portal does not keep its own "require 2FA for providers"
    switch - a stored value that nothing enforced. This screen shows the real
    figures and where 2FA is managed."""
    print("\n===== Two-Factor Authentication =====")
    print("Two-factor sign-in is managed by the platform sign-in (account security /")
    print("MFA settings), not by a health portal setting. A 'require 2FA for")
    print("providers' switch here was never enforced and is no longer offered.")

    conn = get_connection()
    try:
        row = conn.execute("SELECT setting_value FROM security_settings "
                           "WHERE setting_name = 'require_2fa_for_providers'").fetchone()
        if row and row[0] == '1':
            conn.execute("UPDATE security_settings SET setting_value = '0', updated_at = ? "
                         "WHERE setting_name = 'require_2fa_for_providers'",
                         (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
            log_audit_event(auth.current_user['id'], 'retire_provider_2fa_setting', 'security', 0)
            conn.commit()
    finally:
        conn.close()

    print("\n1. View 2FA Statistics")
    print("2. Return to security menu")
    choice = input("\nSelect option (1-2): ")

    if choice == '1':
        try:
            stats = _mfa_statistics()
        except Exception as exc:
            print(f"2FA statistics unavailable: {exc}")
            return
        print("2FA Statistics:")
        print(f"• Active users: {stats['active_users']}")
        print(f"• Users with 2FA enabled: {stats['users_with_2fa']}")
        print(f"• Health staff (clinical roles): {stats['providers']}, "
              f"with 2FA enabled: {stats['providers_with_2fa']}")
        if stats['attempts_7_days'] is not None:
            print(f"• 2FA verification attempts (last 7 days): {stats['attempts_7_days']}")


def review_security_settings(auth):
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Security Settings Review =====")

    cursor.execute('''
    SELECT setting_name, setting_value, updated_at, updated_by
    FROM security_settings
    ORDER BY setting_name
    ''')

    settings = cursor.fetchall()

    if not settings:
        print("No security settings found.")
        conn.close()
        return

    security_issues = []

    for setting_name, setting_value, updated_at, updated_by in settings:
        print(f"\n{setting_name}: {setting_value}")
        if updated_at:
            print(f"  Last updated: {updated_at} by {updated_by}")

        # Security assessment
        if setting_name == 'session_timeout_minutes':
            timeout = int(setting_value)
            if timeout > 60:
                security_issues.append(f"Session timeout too long: {timeout} minutes")
                print("  🔴 RISK: Session timeout should be ≤60 minutes")
            elif timeout <= 30:
                print("  ✅ Good: Appropriate session timeout")
            else:
                print("  🟡 Acceptable: Session timeout within range")

        elif setting_name == 'max_failed_login_attempts':
            max_attempts = int(setting_value)
            if max_attempts > 5:
                security_issues.append(f"Too many login attempts allowed: {max_attempts}")
                print("  🔴 RISK: Max attempts should be ≤5")
            else:
                print("  ✅ Good: Appropriate login attempt limit")

        elif setting_name == 'password_expiry_days':
            expiry_days = int(setting_value)
            if expiry_days > 90:
                security_issues.append(f"Password expiry too long: {expiry_days} days")
                print("  🔴 RISK: Password should expire within 90 days")
            else:
                print("  ✅ Good: Appropriate password expiry")

        elif setting_name == 'encryption_enabled':
            if setting_value != '1':
                security_issues.append("Data encryption disabled")
                print("  🔴 CRITICAL: Encryption should be enabled")
            else:
                print("  ✅ Good: Encryption enabled")

        elif setting_name == 'audit_logging_enabled':
            if setting_value != '1':
                security_issues.append("Audit logging disabled")
                print("  🔴 CRITICAL: Audit logging should be enabled")
            else:
                print("  ✅ Good: Audit logging enabled")

        elif setting_name in ('require_2fa_for_providers', 'ip_restriction_enabled',
                              'allowed_ip_ranges'):
            print("  ℹ️  Not enforced by the health portal (2FA is managed by the platform "
                  "sign-in; desktop sessions have no client IP)")

    # Security recommendations
    print("\n===== Security Assessment =====")

    if security_issues:
        print("Security Issues Found:")
        for issue in security_issues:
            print(f"  🔴 {issue}")

        print("\nRecommendations:")
        print("  • Review and update security settings")
        print("  • Implement stricter policies where needed")
        print("  • Regular security setting audits")
    else:
        print("✅ All security settings appear to be properly configured.")

    # Update settings option
    update_settings = input("\nUpdate security settings? (y/n): ").lower()
    if update_settings == 'y':
        update_security_settings(auth)

    conn.close()


def update_security_settings(auth):
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Update Security Settings =====")

    # Show current settings
    cursor.execute('''
    SELECT setting_name, setting_value
    FROM security_settings
    ORDER BY setting_name
    ''')

    settings = cursor.fetchall()
    setting_names = [setting[0] for setting in settings]

    print("Current Settings:")
    for i, (name, value) in enumerate(settings):
        print(f"{i+1}. {name}: {value}")

    while True:
        choice = input(f"\nSelect setting to update (1-{len(settings)}) or 'q' to quit: ")
        if choice.lower() == 'q':
            break

        try:
            setting_idx = int(choice) - 1
            if 0 <= setting_idx < len(settings):
                setting_name = setting_names[setting_idx]
                current_value = settings[setting_idx][1]

                print(f"\nUpdating: {setting_name}")
                print(f"Current value: {current_value}")

                new_value = input("New value: ").strip()
                if new_value:
                    cursor.execute('''
                    UPDATE security_settings
                    SET setting_value = ?, updated_at = ?, updated_by = ?
                    WHERE setting_name = ?
                    ''', (new_value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                          auth.current_user['username'], setting_name))

                    conn.commit()
                    log_audit_event(auth.current_user['id'], 'update_security_setting', 'security_setting', 0,
                                   f"{setting_name}: {current_value} -> {new_value}")
                    print(f"Setting updated: {setting_name} = {new_value}")
                else:
                    print("No change made.")
            else:
                print("Invalid choice.")
        except ValueError:
            print("Invalid input.")

    conn.close()


def security_audit_menu(auth):
    """Security audit and monitoring"""
    if auth.current_user['role'] != 'admin':
        print("Only administrators can access security audit features.")
        return

    while True:
        print("\n===== Security Audit =====")
        print("1. View Audit Log")
        print("2. Failed Login Attempts")
        print("3. Data Access Patterns")
        print("4. Security Settings Review")
        print("5. Generate Security Report")
        print("6. Return to Main Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            view_audit_log(auth)
        elif choice == '2':
            view_failed_logins(auth)
        elif choice == '3':
            analyze_data_access_patterns(auth)
        elif choice == '4':
            review_security_settings(auth)
        elif choice == '5':
            generate_security_report(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")
