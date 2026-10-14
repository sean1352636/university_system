"""External system integration management for the health portal."""

import logging
from datetime import datetime

from education_system.systems.university.domains.pastoral.domain.health.services import external_system_connections, get_connection

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


def laboratory_system_integration(auth):
    """Stub: show last lab pushes if present."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lab_integration_events'")
        if not c.fetchone():
            print("No 'lab_integration_events' table."); return
        c.execute("SELECT created_at, event_type, status FROM lab_integration_events ORDER BY created_at DESC LIMIT 20")
        for ts, typ, status in c.fetchall():
            print(f"[{ts}] {typ}: {status}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")


def insurance_system_integration(auth):
    """Stub: show last insurance pushes if present."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='insurance_integration_events'")
        if not c.fetchone():
            print("No 'insurance_integration_events' table."); return
        c.execute("SELECT created_at, event_type, status FROM insurance_integration_events ORDER BY created_at DESC LIMIT 20")
        for ts, typ, status in c.fetchall():
            print(f"[{ts}] {typ}: {status}")
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


def api_key_management(auth):
    """Manage API keys for integrations"""
    print("\n===== API Key Management =====")

    # Mock API keys
    api_keys = [
        {"service": "LabCorp API", "key": "lc_***************", "expires": "2024-12-31", "status": "Active"},
        {"service": "Insurance API", "key": "ins_**************", "expires": "2024-06-30", "status": "Active"},
        {"service": "State Registry", "key": "sr_***************", "expires": "2025-03-15", "status": "Active"},
        {"service": "Hospital API", "key": "hosp_*************", "expires": "2024-02-28", "status": "Expiring Soon"}
    ]

    print("API Key Status:")
    for i, key in enumerate(api_keys):
        status_icon = "🟡" if key["status"] == "Expiring Soon" else "✅"
        print(f"{i+1}. {status_icon} {key['service']}")
        print(f"   Key: {key['key']}")
        print(f"   Expires: {key['expires']}")
        print(f"   Status: {key['status']}")

    print("\nActions:")
    print("1. Generate New API Key")
    print("2. Rotate Existing Key")
    print("3. Revoke API Key")
    print("4. View Key Usage Statistics")
    print("5. Return to integration menu")

    choice = input("\nSelect action (1-5): ")

    if choice == '1':
        service_name = input("Enter service name for new API key: ")
        print(f"New API key generated for {service_name}")
        print("Key: api_key_" + datetime.now().strftime('%Y%m%d%H%M%S'))
        log_audit_event(auth.current_user['id'], 'generate_api_key', 'integration', 0, service_name)

    elif choice == '2':
        key_num = input("Enter key number to rotate: ")
        print(f"API key {key_num} rotated successfully.")
        print("Old key will be valid for 24 hours for transition.")


def integration_health_check(auth):
    """Check health of all integrations"""
    print("\n===== Integration Health Check =====")

    # Mock health check results
    health_checks = [
        {"system": "LabCorp API", "status": "Healthy", "response_time": "245ms", "last_error": None},
        {"system": "Insurance API", "status": "Degraded", "response_time": "1.2s", "last_error": "Timeout on 2024-01-15"},
        {"system": "State Registry", "status": "Healthy", "response_time": "156ms", "last_error": None},
        {"system": "Hospital EMR", "status": "Down", "response_time": "N/A", "last_error": "Connection refused"}
    ]

    print("System Health Status:")

    for check in health_checks:
        if check["status"] == "Healthy":
            icon = "✅"
        elif check["status"] == "Degraded":
            icon = "🟡"
        else:
            icon = "❌"

        print(f"\n{icon} {check['system']}")
        print(f"   Status: {check['status']}")
        print(f"   Response Time: {check['response_time']}")
        if check['last_error']:
            print(f"   Last Error: {check['last_error']}")

    # Overall health summary
    healthy_count = sum(1 for c in health_checks if c["status"] == "Healthy")
    total_count = len(health_checks)

    print(f"\nOverall Integration Health: {healthy_count}/{total_count} systems healthy")

    if healthy_count < total_count:
        print("⚠️ Some integrations require attention.")
    else:
        print("✅ All integrations are functioning normally.")
