"""Main CLI menu and GUI launcher for Integration Marketplace"""

from education_system.systems.university.services.integrations.integration_marketplace_core._imports import create_gui_launcher

from education_system.systems.university.services.integrations.integration_marketplace_core.search_discovery import (
    search_catalog, filter_by_rating, filter_by_compatibility,
    find_similar_integrations, search_sync_logs, advanced_filter_dialog,
)
from education_system.systems.university.services.integrations.integration_marketplace_core.bulk_operations import (
    bulk_install_integrations, bulk_uninstall_integrations,
    bulk_enable_integrations, bulk_disable_integrations,
    bulk_sync_integrations, bulk_update_credentials,
)
from education_system.systems.university.services.integrations.integration_marketplace_core.import_export import (
    export_catalog_to_json, import_integrations_from_json,
    export_configuration_bundle, import_configuration_bundle,
    export_sync_report_pdf, export_mappings_to_excel,
)
from education_system.systems.university.services.integrations.integration_marketplace_core.reports import (
    show_dashboard_overview, generate_health_report, show_error_analysis,
    generate_usage_trend_chart, show_api_call_statistics,
    compare_integration_performance, generate_compliance_report,
)
from education_system.systems.university.services.integrations.integration_marketplace_core.security import (
    rotate_api_credentials, check_credential_expiry, validate_credentials,
    encrypt_export_credentials, audit_credential_access, revoke_all_tokens,
)
from education_system.systems.university.services.integrations.integration_marketplace_core.scheduling import (
    schedule_sync, view_scheduled_tasks, pause_scheduled_syncs,
    set_maintenance_window, configure_retry_policy,
)
from education_system.systems.university.services.integrations.integration_marketplace_core.validation import (
    test_integration_connection, validate_mapping_rules, dry_run_sync,
    test_webhook_delivery, validate_json_configuration, run_integration_diagnostics,
)
from education_system.systems.university.services.integrations.integration_marketplace_core.mapping_tools import (
    auto_detect_mappings, preview_transformation,
    duplicate_mapping_set, import_mappings_from_template,
)
from education_system.systems.university.services.integrations.integration_marketplace_core.notifications import (
    configure_alert_rules, subscribe_to_notifications,
    view_notification_history, test_notification_channel,
)


def display_integration_marketplace_menu(auth):
    """Display the Integration Marketplace CLI menu"""
    while True:
        print("\n" + "="*100)
        print("           INTEGRATION MARKETPLACE")
        print("="*100)

        print("\n--- BASIC OPERATIONS ---")
        print(f"{'1.  Browse Catalog':<25} {'2.  Install Integration':<25} {'3.  Manage Credentials':<25} {'4.  Sync Logs':<25}")
        print(f"{'5.  Data Mappings':<25} {'6.  Webhook Config':<25} {'7.  Usage Analytics':<25}")

        print("\n--- SEARCH & DISCOVERY ---")
        print(f"{'10. Search Catalog':<25} {'11. Filter by Rating':<25} {'12. Filter Compat.':<25} {'13. Find Similar':<25}")
        print(f"{'14. Search Sync Logs':<25} {'15. Advanced Filter':<25}")

        print("\n--- BULK OPERATIONS ---")
        print(f"{'20. Bulk Install':<25} {'21. Bulk Uninstall':<25} {'22. Bulk Enable':<25} {'23. Bulk Disable':<25}")
        print(f"{'24. Bulk Sync':<25} {'25. Bulk Update Creds':<25}")

        print("\n--- IMPORT/EXPORT ---")
        print(f"{'30. Export to JSON':<25} {'31. Import from JSON':<25} {'32. Export Config':<25} {'33. Import Config':<25}")
        print(f"{'34. Export Sync PDF':<25} {'35. Export to Excel':<25}")

        print("\n--- REPORTS & DASHBOARDS ---")
        print(f"{'40. Dashboard Overview':<25} {'41. Health Report':<25} {'42. Error Analysis':<25} {'43. Usage Trends':<25}")
        print(f"{'44. API Call Stats':<25} {'45. Compare Perf.':<25} {'46. Compliance Report':<25}")

        print("\n--- SECURITY & CREDENTIALS ---")
        print(f"{'50. Rotate Credentials':<25} {'51. Check Expiry':<25} {'52. Validate Creds':<25} {'53. Export Encrypted':<25}")
        print(f"{'54. Audit Access':<25} {'55. Revoke Tokens':<25}")

        print("\n--- SCHEDULING & AUTOMATION ---")
        print(f"{'60. Schedule Sync':<25} {'61. View Tasks':<25} {'62. Pause Syncs':<25} {'63. Maintenance Window':<25}")
        print(f"{'64. Retry Policy':<25}")

        print("\n--- VALIDATION & TESTING ---")
        print(f"{'70. Test Connection':<25} {'71. Validate Mappings':<25} {'72. Dry Run Sync':<25} {'73. Test Webhook':<25}")
        print(f"{'74. Validate JSON':<25} {'75. Run Diagnostics':<25}")

        print("\n--- DATA MAPPING TOOLS ---")
        print(f"{'80. Auto-Detect':<25} {'81. Preview Transform':<25} {'82. Duplicate Mapping':<25} {'83. Import Template':<25}")

        print("\n--- NOTIFICATIONS & ALERTS ---")
        print(f"{'90. Configure Alerts':<25} {'91. Subscribe':<25} {'92. View History':<25} {'93. Test Channel':<25}")

        print("\n0.  Return to Main Menu")
        print("="*100)

        try:
            choice = input("\nEnter your choice: ").strip()

            # Basic operations (existing placeholders)
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print("\nFeature available via Integration managers.")
                print("Use: from education_system.systems.university.services.integrations import IntegrationCatalogManager")

            # Search & Discovery (10-15)
            elif choice == '10':
                search_catalog()
            elif choice == '11':
                filter_by_rating()
            elif choice == '12':
                filter_by_compatibility()
            elif choice == '13':
                find_similar_integrations()
            elif choice == '14':
                search_sync_logs()
            elif choice == '15':
                advanced_filter_dialog()

            # Bulk Operations (20-25)
            elif choice == '20':
                bulk_install_integrations()
            elif choice == '21':
                bulk_uninstall_integrations()
            elif choice == '22':
                bulk_enable_integrations()
            elif choice == '23':
                bulk_disable_integrations()
            elif choice == '24':
                bulk_sync_integrations()
            elif choice == '25':
                bulk_update_credentials()

            # Import/Export (30-35)
            elif choice == '30':
                export_catalog_to_json()
            elif choice == '31':
                import_integrations_from_json()
            elif choice == '32':
                export_configuration_bundle()
            elif choice == '33':
                import_configuration_bundle()
            elif choice == '34':
                export_sync_report_pdf()
            elif choice == '35':
                export_mappings_to_excel()

            # Reports & Dashboards (40-46)
            elif choice == '40':
                show_dashboard_overview()
            elif choice == '41':
                generate_health_report()
            elif choice == '42':
                show_error_analysis()
            elif choice == '43':
                generate_usage_trend_chart()
            elif choice == '44':
                show_api_call_statistics()
            elif choice == '45':
                compare_integration_performance()
            elif choice == '46':
                generate_compliance_report()

            # Security & Credentials (50-55)
            elif choice == '50':
                rotate_api_credentials()
            elif choice == '51':
                check_credential_expiry()
            elif choice == '52':
                validate_credentials()
            elif choice == '53':
                encrypt_export_credentials()
            elif choice == '54':
                audit_credential_access()
            elif choice == '55':
                revoke_all_tokens()

            # Scheduling & Automation (60-64)
            elif choice == '60':
                schedule_sync()
            elif choice == '61':
                view_scheduled_tasks()
            elif choice == '62':
                pause_scheduled_syncs()
            elif choice == '63':
                set_maintenance_window()
            elif choice == '64':
                configure_retry_policy()

            # Validation & Testing (70-75)
            elif choice == '70':
                test_integration_connection()
            elif choice == '71':
                validate_mapping_rules()
            elif choice == '72':
                dry_run_sync()
            elif choice == '73':
                test_webhook_delivery()
            elif choice == '74':
                validate_json_configuration()
            elif choice == '75':
                run_integration_diagnostics()

            # Data Mapping Tools (80-83)
            elif choice == '80':
                auto_detect_mappings()
            elif choice == '81':
                preview_transformation()
            elif choice == '82':
                duplicate_mapping_set()
            elif choice == '83':
                import_mappings_from_template()

            # Notifications & Alerts (90-93)
            elif choice == '90':
                configure_alert_rules()
            elif choice == '91':
                subscribe_to_notifications()
            elif choice == '92':
                view_notification_history()
            elif choice == '93':
                test_notification_channel()

            elif choice == '0':
                break
            else:
                print("Invalid choice. Please try again.")

        except KeyboardInterrupt:
            print("\nReturning to main menu...")
            break
        except Exception as e:
            print(f"Error: {e}")


# Use factory to create GUI launcher
launch_integration_marketplace_gui = create_gui_launcher(
    title="Integration Marketplace",
    description="""Browse and install third-party integrations.

Features:
• Integration catalog
• Installation management
• Credential management
• Sync logs
• Data mappings
• Webhook configuration""",
    cli_instruction="Use CLI: Integration Marketplace"
)
