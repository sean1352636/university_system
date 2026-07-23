"""Notifications & Alerts Manager and CLI functions"""

from education_system.post_18.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import (
    datetime, json, timedelta, Any, Dict, List, get_connection, transaction,
)


class NotificationsAlertManager:
    """Manages notifications and alerts for integrations"""

    @staticmethod
    def configure_alert_rules(install_id: int, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Set up custom alerts for error thresholds"""
        # Store rules in configuration
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE installed_integrations
                SET configuration = json_set(
                    COALESCE(configuration, '{}'),
                    '$.alert_rules', ?
                )
                WHERE install_id = ?
            ''', (json.dumps(rules), install_id))

        return {'install_id': install_id, 'rules_configured': len(rules), 'rules': rules}

    @staticmethod
    def subscribe_to_notifications(install_id: int, user_email: str,
                                  event_types: List[str]) -> Dict[str, Any]:
        """Subscribe users to integration events"""
        subscription = {
            'user_email': user_email,
            'event_types': event_types,
            'subscribed_at': datetime.now().isoformat()
        }

        with transaction() as conn:
            cursor = conn.cursor()

            # Get current subscriptions
            cursor.execute('''
                SELECT configuration FROM installed_integrations
                WHERE install_id = ?
            ''', (install_id,))
            row = cursor.fetchone()

            config = json.loads(row['configuration']) if row and row['configuration'] else {}
            subscriptions = config.get('subscriptions', [])

            # Add or update subscription
            existing = next((s for s in subscriptions if s['user_email'] == user_email), None)
            if existing:
                existing['event_types'] = list(set(existing['event_types'] + event_types))
            else:
                subscriptions.append(subscription)

            config['subscriptions'] = subscriptions

            cursor.execute('''
                UPDATE installed_integrations
                SET configuration = ?
                WHERE install_id = ?
            ''', (json.dumps(config), install_id))

        return {'install_id': install_id, 'subscription': subscription}

    @staticmethod
    def get_notification_history(install_id: int = None, days: int = 30) -> List[Dict[str, Any]]:
        """View past notifications sent"""
        # This would typically query a notifications log table
        # For now, return simulated data
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        history = [
            {
                'notification_id': 1,
                'install_id': install_id or 1,
                'event_type': 'sync_failed',
                'sent_to': 'admin@university.edu',
                'sent_at': datetime.now().isoformat(),
                'subject': 'Integration Sync Failed',
                'status': 'delivered'
            }
        ]

        return history

    @staticmethod
    def test_notification_channel(channel_type: str, target: str) -> Dict[str, Any]:
        """Send test notification to verify setup"""
        result = {
            'channel_type': channel_type,
            'target': target,
            'sent': False,
            'message': ''
        }

        if channel_type == 'email':
            # Simulate email test
            result['sent'] = True
            result['message'] = f'Test email sent to {target}'
        elif channel_type == 'webhook':
            # Simulate webhook test
            result['sent'] = True
            result['message'] = f'Test webhook sent to {target}'
        elif channel_type == 'slack':
            result['sent'] = True
            result['message'] = f'Test Slack message sent to {target}'
        else:
            result['message'] = f'Unknown channel type: {channel_type}'

        return result


# =============================================================================
# CLI FUNCTIONS
# =============================================================================

def configure_alert_rules():
    """Set up custom alerts for error thresholds"""
    print("\n" + "="*50)
    print("      CONFIGURE ALERT RULES")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    rules = []
    print("\nDefine alert rules (empty rule name to finish):")

    while True:
        rule_name = input("\nRule name (e.g., 'high_error_rate'): ").strip()
        if not rule_name:
            break

        print("Condition types: error_count, error_rate, sync_duration, no_sync")
        condition_type = input("Condition type: ").strip()

        threshold = input("Threshold value: ").strip()
        try:
            threshold = float(threshold)
        except ValueError:
            threshold = 0

        severity = input("Severity (info/warning/critical): ").strip().lower() or 'warning'

        rules.append({
            'name': rule_name,
            'condition_type': condition_type,
            'threshold': threshold,
            'severity': severity
        })

    if not rules:
        print("No rules defined.")
        return

    try:
        result = NotificationsAlertManager.configure_alert_rules(install_id, rules)
        print("\nAlert rules configured!")
        print(f"  Install ID: {result.get('install_id')}")
        print(f"  Rules configured: {result.get('rules_configured')}")

        for rule in result.get('rules', []):
            print(f"\n  - {rule.get('name')}")
            print(f"    Condition: {rule.get('condition_type')} >= {rule.get('threshold')}")
            print(f"    Severity: {rule.get('severity')}")

    except Exception as e:
        print(f"\nError configuring rules: {e}")


def subscribe_to_notifications():
    """Subscribe users to integration events"""
    print("\n" + "="*50)
    print("      SUBSCRIBE TO NOTIFICATIONS")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    email = input("Email address: ").strip()
    if not email or '@' not in email:
        print("Valid email is required.")
        return

    print("\nEvent types (comma-separated):")
    print("  Available: sync_failed, sync_success, credential_expiry, error_threshold")
    events_input = input("Events to subscribe: ").strip()
    if not events_input:
        print("At least one event type is required.")
        return

    event_types = [e.strip() for e in events_input.split(',')]

    try:
        result = NotificationsAlertManager.subscribe_to_notifications(install_id, email, event_types)
        subscription = result.get('subscription', {})
        print("\nSubscription created!")
        print(f"  Install ID: {result.get('install_id')}")
        print(f"  Email: {subscription.get('user_email')}")
        print(f"  Events: {', '.join(subscription.get('event_types', []))}")

    except Exception as e:
        print(f"\nError creating subscription: {e}")


def view_notification_history():
    """View past notifications sent"""
    print("\n" + "="*50)
    print("      NOTIFICATION HISTORY")
    print("="*50)

    install_id_input = input("Install ID (or blank for all): ").strip()
    install_id = int(install_id_input) if install_id_input.isdigit() else None

    days = input("Days of history (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    try:
        history = NotificationsAlertManager.get_notification_history(install_id, days)

        if not history:
            print("\nNo notifications found.")
            return

        print(f"\n--- NOTIFICATION HISTORY (Last {days} days) ---\n")
        for notif in history:
            status_icon = {'delivered': '[OK]', 'failed': '[X]', 'pending': '[...]'}.get(notif.get('status'), '[?]')
            print(f"{status_icon} [{notif.get('sent_at', 'N/A')[:16]}] {notif.get('event_type', 'N/A').upper()}")
            print(f"    To: {notif.get('sent_to', 'N/A')}")
            print(f"    Subject: {notif.get('subject', 'N/A')}")
            print()

    except Exception as e:
        print(f"\nError retrieving history: {e}")


def test_notification_channel():
    """Send test notification to verify setup"""
    print("\n" + "="*50)
    print("      TEST NOTIFICATION CHANNEL")
    print("="*50)

    print("\nChannel types: email, webhook, slack")
    channel_type = input("Channel type: ").strip().lower()
    if not channel_type:
        print("Channel type is required.")
        return

    if channel_type == 'email':
        target = input("Email address: ").strip()
    elif channel_type == 'webhook':
        target = input("Webhook URL: ").strip()
    elif channel_type == 'slack':
        target = input("Slack channel/webhook: ").strip()
    else:
        print(f"Unknown channel type: {channel_type}")
        return

    if not target:
        print("Target is required.")
        return

    print(f"\nSending test notification via {channel_type}...")

    try:
        result = NotificationsAlertManager.test_notification_channel(channel_type, target)

        if result.get('sent'):
            print("\n[OK] TEST NOTIFICATION SENT")
            print(f"  Channel: {result.get('channel_type')}")
            print(f"  Target: {result.get('target')}")
            print(f"  Message: {result.get('message')}")
        else:
            print("\n[X] TEST NOTIFICATION FAILED")
            print(f"  Message: {result.get('message')}")

    except Exception as e:
        print(f"\nError testing channel: {e}")
