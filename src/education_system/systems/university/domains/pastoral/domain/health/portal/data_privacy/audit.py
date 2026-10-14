"""Audit trail logging and viewing for the health portal."""

from education_system.systems.university.domains.pastoral.domain.health.services import get_connection
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

# Configure logging for audit trail
audit_logger = configure_logging(name=__name__)

def log_audit_event(user_id, action, resource_type, resource_id, details=None):
    """Log audit events for compliance"""
    audit_logger.info(f"USER:{user_id} ACTION:{action} RESOURCE:{resource_type}:{resource_id} DETAILS:{details}")


def view_audit_log(auth):
    """View system audit log"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get recent audit events
    cursor.execute('''
    SELECT user_id, action, resource_type, resource_id, timestamp, ip_address
    FROM audit_trail
    ORDER BY timestamp DESC
    LIMIT 50
    ''')

    audit_events = cursor.fetchall()

    if not audit_events:
        print("No audit events found.")
        conn.close()
        return

    print("\n===== System Audit Log (Last 50 Events) =====")
    for event in audit_events:
        user_id, action, resource_type, resource_id, timestamp, ip_address = event

        print(f"{timestamp} - User: {user_id} - Action: {action}")
        print(f"  Resource: {resource_type}:{resource_id}")
        if ip_address:
            print(f"  IP: {ip_address}")
        print("-" * 30)

    conn.close()
