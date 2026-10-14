"""API management CLI functions."""

import secrets


def api_management_menu(log_manager, auth):
    """API management menu"""
    print("\n\U0001f50c API MANAGEMENT")
    print("="*18)

    api_enabled = log_manager.config.get('api_enabled', False)

    print(f"API Status: {'Enabled' if api_enabled else 'Disabled'}")

    print("\n1. Enable/Disable API")
    print("2. Generate API Key")
    print("3. View API Statistics")
    print("4. API Documentation")
    print("5. Return")

    choice = input("Choose option: ")

    if choice == '1':
        toggle_api(log_manager)
    elif choice == '2':
        generate_api_key(log_manager)
    elif choice == '3':
        view_api_stats(log_manager)
    elif choice == '4':
        show_api_docs()


def toggle_api(log_manager):
    """Toggle API on/off"""
    current_status = log_manager.config.get('api_enabled', False)
    new_status = not current_status

    log_manager.config.set('api_enabled', new_status)

    status_text = "enabled" if new_status else "disabled"
    print(f"API has been {status_text}")


def generate_api_key(log_manager):
    """Generate new API key"""
    new_key = secrets.token_urlsafe(32)

    log_manager.config.set('api_secret_key', new_key)

    print("New API key generated:")
    print(f"Key: {new_key}")
    print("\u26a0\ufe0f Store this key securely - it won't be shown again!")


def show_api_docs():
    """Show API documentation"""
    print("\n\U0001f4da API DOCUMENTATION")
    print("="*22)

    docs = """
    Log Management API Endpoints:

    Authentication:
    POST /api/auth/login - Get authentication token

    Log Operations:
    POST /api/logs/search - Search logs with filters
    GET  /api/logs/recent - Get recent logs
    GET  /api/logs/user/{user_id} - Get logs for specific user

    Analytics:
    GET  /api/analytics/summary - Get activity summary
    GET  /api/analytics/user/{user_id} - Get user analytics
    POST /api/analytics/chart - Generate activity chart

    Alerts:
    GET  /api/alerts - Get recent alerts
    POST /api/alerts/check - Trigger alert checks

    Export:
    POST /api/export/logs - Export logs with filters

    System:
    GET  /api/system/status - Get system status
    GET  /api/config - Get configuration
    PUT  /api/config - Update configuration

    Health:
    GET  /api/health - Health check

    All endpoints require authentication via Bearer token.
    """

    print(docs)
    input("\nPress Enter to continue...")


def view_api_stats(log_manager):
    """View API statistics (placeholder)"""
    print("\nAPI statistics not yet implemented.")
    input("\nPress Enter to continue...")
