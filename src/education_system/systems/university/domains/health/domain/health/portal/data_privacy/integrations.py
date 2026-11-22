"""External system integration management for the health portal."""

import logging
from datetime import datetime

from education_system.systems.university.domains.health.domain.health.services import external_system_connections, get_connection

from .audit import log_audit_event

def integration_logs(auth):
    """Stub: show last 20 integration log entries if present."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='integration_logs'")
        if not c.fetchone():
            print("No 'integration_logs' table."); return
        # The severity column is 'status' (success/error/pending) — there is no
        # 'level' column on integration_logs, in the baseline migration or in
        # the CREATE TABLE at the top of this module, so this query could only
        # ever raise. 'provider' identifies the integration; 'system' is the
        # optional vendor name and is frequently NULL, so fall back to it
        # rather than printing "None" for every row.
        c.execute(
            "SELECT created_at, COALESCE(provider, system, 'unknown'),"
            "       COALESCE(status, '-'), COALESCE(event_type, ''),"
            "       COALESCE(message, '')"
            " FROM integration_logs"
            " ORDER BY created_at DESC LIMIT 20")
        rows = c.fetchall()
        if not rows:
            print("No integration log entries recorded yet.")
            return
        print("\nLast 20 integration log entries:")
        for ts, source, status, event_type, msg in rows:
            event = f" {event_type}" if event_type else ""
            print(f"[{ts}] {source}{event} [{status}]: {msg}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")


def data_sync_status(auth):
    """Stub: show pending/out-of-sync items if present."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_queue'")
        if not c.fetchone():
            print("No 'sync_queue' table."); return
        # sync_queue has no 'system' column and never holds status 'synced' —
        # the statuses it writes are pending/locked/failed/done. Grouping by a
        # column that does not exist raised, and comparing against a status
        # that is never used would have reported everything as outstanding.
        # queue_name is the nearest thing to a system, with entity_type as a
        # fallback for rows that do not set one.
        c.execute(
            "SELECT COALESCE(queue_name, entity_type, 'default'),"
            "       COALESCE(status, 'pending'), COUNT(*)"
            " FROM sync_queue"
            " WHERE COALESCE(status, 'pending') NOT IN ('done', 'synced', 'completed')"
            " GROUP BY 1, 2"
            " ORDER BY 1, 2")
        rows = c.fetchall()
        if not rows:
            print("All queues are clear — nothing waiting to sync."); return
        print("Outstanding sync items:")
        for queue, status, n in rows:
            print(f" - {queue} [{status}]: {n}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")


def _who(auth):
    user = auth.current_user or {}
    return str(user.get('username') or user.get('id'))


def laboratory_system_integration(auth):
    """Laboratory results: recent events, manual entry from a lab report, and
    results-file import (lab_results + lab_integration_events). There is no
    live connection to an outside laboratory; this is how results arrive."""
    from education_system.systems.university.domains.health.application.health import (
        integrations,
    )
    conn = get_connection()
    try:
        print("\n===== Laboratory System Integration =====")
        rows = integrations.recent_events(conn, "lab_integration_events")
        if not rows:
            print("No laboratory results have been received yet.")
        for ts, typ, status, patient, _payload in rows:
            print(f"[{ts}] {typ}: {status}" + (f"  (student {patient})" if patient else ""))
        print("\n1. Enter a result from a lab report")
        print("2. Import a lab results file (CSV)")
        print("3. Return")
        choice = input("Select option (1-3): ").strip()
        try:
            if choice == '1':
                values = {f: input(f"{f.replace('_', ' ').capitalize()}: ").strip()
                          for f in ("student_id", "test_name", "test_code", "result_value",
                                    "units", "reference_range", "abnormal_flag", "lab_name",
                                    "resulted_date")}
                rid = integrations.record_lab_result(conn, values, by=_who(auth))
                log_audit_event(auth.current_user['id'], 'lab_result_entered', 'lab_result', rid,
                                values['student_id'])
                conn.commit()
                print(f"Lab result recorded (#{rid}).")
            elif choice == '2':
                path = input("Path to the CSV file: ").strip()
                n, errors = integrations.import_lab_file(conn, path, by=_who(auth))
                log_audit_event(auth.current_user['id'], 'lab_results_imported', 'lab_result', 0,
                                f"{n} imported from {path}")
                conn.commit()
                print(f"{n} result(s) imported.")
                for err in errors[:20]:
                    print(f"  ✗ {err}")
                if len(errors) > 20:
                    print(f"  … and {len(errors) - 20} more")
        except (ValueError, LookupError, OSError) as exc:
            conn.rollback()
            print(f"Not recorded: {exc}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")


def insurance_system_integration(auth):
    """Insurance verification records (insurance_integration_events): what an
    insurer confirmed, when and by whom. No live insurer connection exists."""
    from education_system.systems.university.domains.health.application.health import (
        integrations,
    )
    conn = get_connection()
    try:
        print("\n===== Insurance System Integration =====")
        rows = integrations.recent_events(conn, "insurance_integration_events")
        if not rows:
            print("No insurance verifications recorded yet.")
        for ts, typ, status, patient, _payload in rows:
            print(f"[{ts}] {typ}: {status}" + (f"  (student {patient})" if patient else ""))
        print("\n1. Record an insurance verification")
        print("2. Return")
        if input("Select option (1-2): ").strip() != '1':
            return
        student_id = input("Student ID: ").strip()
        print("Outcome: " + ", ".join(integrations.VERIFICATION_OUTCOMES))
        outcome = input("Outcome: ").strip().lower()
        try:
            eid = integrations.record_insurance_verification(
                conn, student_id=student_id, outcome=outcome, by=_who(auth),
                reference=input("Insurer reference (optional): ").strip() or None,
                notes=input("Notes (optional): ").strip() or None)
            log_audit_event(auth.current_user['id'], 'insurance_verification', 'insurance', eid,
                            f"{student_id}: {outcome}")
            conn.commit()
            print(f"Verification recorded (#{eid}).")
        except (ValueError, LookupError) as exc:
            conn.rollback()
            print(f"Not recorded: {exc}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")


def integration_management(auth):
    """External system integration management"""
    if auth.current_user['role'] != 'admin':
        print("Only administrators can manage integrations.")
        return

    while True:
        print("\n===== Integration Management =====")
        print("1. External System Connections")
        print("2. API Key Management")
        print("3. Data Sync Status")
        print("4. Integration Logs")
        print("5. Laboratory System Integration")
        print("6. Insurance System Integration")
        print("7. Integration Health Check")
        print("8. Return to Main Menu")

        choice = input("\nEnter your choice (1-8): ")

        if choice == '1':
            external_system_connections(auth)
        elif choice == '2':
            api_key_management(auth)
        elif choice == '3':
            data_sync_status(auth)
        elif choice == '4':
            integration_logs(auth)
        elif choice == '5':
            laboratory_system_integration(auth)
        elif choice == '6':
            insurance_system_integration(auth)
        elif choice == '7':
            integration_health_check(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")


HEALTH_KEY_PREFIX = "health: "


def _key_manager():
    """The platform API key store (shared auth DB, PBKDF2-hashed keys) — the
    same store ``api_key_required`` checks on the unified API, so a key made
    here is one the API actually accepts."""
    from education_system import paths
    from education_system.platform.delivery.api.security.api_keys import APIKeyManager
    return APIKeyManager(str(paths.PLATFORM_AUTH_DB))


def api_key_management(auth):
    """Manage API keys for health integrations (generate, rotate, revoke;
    hashed at rest, shown once, every action audited)."""
    print("\n===== API Key Management =====")
    try:
        manager = _key_manager()
        keys = [k for k in manager.list_keys() if str(k['label']).startswith(HEALTH_KEY_PREFIX)]
    except Exception as exc:
        print(f"The API key store could not be opened: {exc}")
        return

    print("API Key Status:")
    if not keys:
        print("  No health integration keys have been issued.")
    for i, key in enumerate(keys):
        status_icon = "✅" if key["active"] else "⛔"
        print(f"{i+1}. {status_icon} {key['label'][len(HEALTH_KEY_PREFIX):]}")
        print(f"   Key: {key['prefix']}… (the full key is never stored)")
        print(f"   Created: {key['created_at']}   Last used: {key['last_used_at'] or 'never'}")
        print(f"   Status: {'Active' if key['active'] else 'Revoked'}")

    print("\nActions:")
    print("1. Generate New API Key")
    print("2. Rotate Existing Key")
    print("3. Revoke API Key")
    print("4. View Key Usage Statistics")
    print("5. Return to integration menu")

    choice = input("\nSelect action (1-5): ")

    def pick():
        num = input("Enter key number: ").strip()
        if num.isdigit() and 1 <= int(num) <= len(keys):
            return keys[int(num) - 1]
        print("Invalid key number.")
        return None

    try:
        if choice == '1':
            service_name = input("Enter service name for new API key: ").strip()
            if not service_name:
                print("A service name is required.")
                return
            days = input("Expires after how many days? [365]: ").strip()
            raw = manager.create_key(HEALTH_KEY_PREFIX + service_name, systems=["university"],
                                     created_by=auth.current_user.get('id'),
                                     expires_in_days=int(days) if days.isdigit() else 365)
            log_audit_event(auth.current_user['id'], 'generate_api_key', 'integration', 0,
                            f"{service_name} ({raw[:12]}…)")
            print(f"New API key generated for {service_name}.")
            print(f"Key (shown once — store it now): {raw}")
        elif choice == '2':
            key = pick()
            if key and key['active']:
                raw = manager.rotate_key(key['id'], expires_in_days=365)
                log_audit_event(auth.current_user['id'], 'rotate_api_key', 'integration',
                                key['id'], f"{key['label']} -> {raw[:12]}…")
                print("API key rotated: the old key no longer works.")
                print(f"New key (shown once): {raw}")
            elif key:
                print("That key is already revoked.")
        elif choice == '3':
            key = pick()
            if key and manager.revoke_key(key['id']):
                log_audit_event(auth.current_user['id'], 'revoke_api_key', 'integration',
                                key['id'], key['label'])
                print("API key revoked.")
        elif choice == '4':
            for key in keys:
                print(f"- {key['label'][len(HEALTH_KEY_PREFIX):]}: last used "
                      f"{key['last_used_at'] or 'never'}; "
                      f"{'active' if key['active'] else 'revoked'}")
    except Exception as exc:
        print(f"Not done: {exc}")


def integration_health_check(auth):
    """Check health of all integrations, from what they actually recorded."""
    from education_system.systems.university.domains.health.application.health import (
        integrations,
    )
    print("\n===== Integration Health Check =====")
    conn = get_connection()
    try:
        health_checks = integrations.health_summary(conn)
    finally:
        conn.close()

    print("System Health Status (last 30 days):")
    for check in health_checks:
        if not check["events_30d"]:
            icon, status = "⚪", "No activity"
        elif check["failures_30d"]:
            icon, status = "🟡", "Errors recorded"
        else:
            icon, status = "✅", "Healthy"
        print(f"\n{icon} {check['system']}")
        print(f"   Status: {status}  ({check['mode']})")
        print(f"   Events: {check['events_30d']}   Failures: {check['failures_30d']}")
        print(f"   Last activity: {check['last_activity'] or 'never'}")

    attention = [c for c in health_checks if c["failures_30d"]]
    if attention:
        print("\n⚠️ Some integrations recorded errors and require attention.")
    else:
        print("\nNo integration errors recorded.")
