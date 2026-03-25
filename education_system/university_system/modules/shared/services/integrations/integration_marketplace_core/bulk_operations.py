"""Bulk Operations Manager and CLI functions"""

from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import Any, Dict, List, get_connection, transaction
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.installation import InstallationManager
from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core.sync import SyncManager


class BulkOperationsManager:
    """Manages bulk operations for integrations"""

    @staticmethod
    def bulk_install_integrations(integration_ids: List[int], installed_by: str) -> Dict[str, Any]:
        """Install multiple selected integrations at once"""
        results = {'success': [], 'failed': []}

        for integration_id in integration_ids:
            try:
                install_id = InstallationManager.install_integration(integration_id, installed_by)
                results['success'].append({'integration_id': integration_id, 'install_id': install_id})
            except Exception as e:
                results['failed'].append({'integration_id': integration_id, 'error': str(e)})

        return results

    @staticmethod
    def bulk_uninstall_integrations(install_ids: List[int]) -> Dict[str, Any]:
        """Uninstall multiple integrations simultaneously"""
        results = {'success': [], 'failed': []}

        for install_id in install_ids:
            try:
                InstallationManager.uninstall_integration(install_id)
                results['success'].append(install_id)
            except Exception as e:
                results['failed'].append({'install_id': install_id, 'error': str(e)})

        return results

    @staticmethod
    def bulk_enable_integrations(install_ids: List[int]) -> Dict[str, Any]:
        """Enable multiple disabled integrations"""
        results = {'success': [], 'failed': []}

        with transaction() as conn:
            cursor = conn.cursor()
            for install_id in install_ids:
                try:
                    cursor.execute('''
                        UPDATE installed_integrations
                        SET is_enabled = 1, status = 'active'
                        WHERE install_id = ?
                    ''', (install_id,))
                    results['success'].append(install_id)
                except Exception as e:
                    results['failed'].append({'install_id': install_id, 'error': str(e)})

        return results

    @staticmethod
    def bulk_disable_integrations(install_ids: List[int]) -> Dict[str, Any]:
        """Disable multiple integrations without uninstalling"""
        results = {'success': [], 'failed': []}

        with transaction() as conn:
            cursor = conn.cursor()
            for install_id in install_ids:
                try:
                    cursor.execute('''
                        UPDATE installed_integrations
                        SET is_enabled = 0, status = 'inactive'
                        WHERE install_id = ?
                    ''', (install_id,))
                    results['success'].append(install_id)
                except Exception as e:
                    results['failed'].append({'install_id': install_id, 'error': str(e)})

        return results

    @staticmethod
    def bulk_sync_integrations(install_ids: List[int] = None) -> Dict[str, Any]:
        """Trigger sync for all selected/enabled integrations"""
        results = {'success': [], 'failed': []}

        with get_connection() as conn:
            cursor = conn.cursor()

            if install_ids:
                placeholders = ','.join(['?' for _ in install_ids])
                cursor.execute(f'''
                    SELECT install_id FROM installed_integrations
                    WHERE install_id IN ({placeholders}) AND is_enabled = 1
                ''', install_ids)
            else:
                cursor.execute('''
                    SELECT install_id FROM installed_integrations
                    WHERE is_enabled = 1
                ''')

            enabled_ids = [row['install_id'] for row in cursor.fetchall()]

        for install_id in enabled_ids:
            try:
                log_id = SyncManager.start_sync(install_id)
                # Simulate sync completion
                SyncManager.complete_sync(log_id, 'success', records_synced=0)
                results['success'].append({'install_id': install_id, 'log_id': log_id})
            except Exception as e:
                results['failed'].append({'install_id': install_id, 'error': str(e)})

        return results

    @staticmethod
    def bulk_update_credentials(updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update endpoint URLs for multiple credentials at once"""
        results = {'success': [], 'failed': []}

        with transaction() as conn:
            cursor = conn.cursor()
            for update in updates:
                try:
                    cursor.execute('''
                        UPDATE integration_credentials
                        SET endpoint_url = ?
                        WHERE credential_id = ?
                    ''', (update.get('endpoint_url'), update.get('credential_id')))
                    results['success'].append(update.get('credential_id'))
                except Exception as e:
                    results['failed'].append({
                        'credential_id': update.get('credential_id'),
                        'error': str(e)
                    })

        return results


# =============================================================================
# CLI FUNCTIONS
# =============================================================================

def bulk_install_integrations():
    """Install multiple selected integrations at once"""
    print("\n" + "="*50)
    print("      BULK INSTALL INTEGRATIONS")
    print("="*50)

    ids_input = input("Enter integration IDs (comma-separated): ").strip()
    if not ids_input:
        print("No IDs provided.")
        return

    try:
        integration_ids = [int(x.strip()) for x in ids_input.split(',')]
    except ValueError:
        print("Invalid ID format. Use comma-separated numbers.")
        return

    installed_by = input("Installed by (username): ").strip() or "admin"

    print(f"\nInstalling {len(integration_ids)} integration(s)...")
    results = BulkOperationsManager.bulk_install_integrations(integration_ids, installed_by)

    print(f"\nSuccessful: {len(results['success'])}")
    for s in results['success']:
        print(f"  - Integration {s['integration_id']} -> Install ID: {s['install_id']}")

    if results['failed']:
        print(f"\nFailed: {len(results['failed'])}")
        for f in results['failed']:
            print(f"  - Integration {f['integration_id']}: {f['error']}")


def bulk_uninstall_integrations():
    """Uninstall multiple integrations simultaneously"""
    print("\n" + "="*50)
    print("      BULK UNINSTALL INTEGRATIONS")
    print("="*50)

    ids_input = input("Enter install IDs to uninstall (comma-separated): ").strip()
    if not ids_input:
        print("No IDs provided.")
        return

    try:
        install_ids = [int(x.strip()) for x in ids_input.split(',')]
    except ValueError:
        print("Invalid ID format. Use comma-separated numbers.")
        return

    confirm = input(f"Uninstall {len(install_ids)} integration(s)? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    results = BulkOperationsManager.bulk_uninstall_integrations(install_ids)

    print(f"\nSuccessfully uninstalled: {len(results['success'])}")
    if results['failed']:
        print(f"Failed: {len(results['failed'])}")
        for f in results['failed']:
            print(f"  - Install {f['install_id']}: {f['error']}")


def bulk_enable_integrations():
    """Enable multiple disabled integrations"""
    print("\n" + "="*50)
    print("      BULK ENABLE INTEGRATIONS")
    print("="*50)

    ids_input = input("Enter install IDs to enable (comma-separated): ").strip()
    if not ids_input:
        print("No IDs provided.")
        return

    try:
        install_ids = [int(x.strip()) for x in ids_input.split(',')]
    except ValueError:
        print("Invalid ID format. Use comma-separated numbers.")
        return

    results = BulkOperationsManager.bulk_enable_integrations(install_ids)

    print(f"\nSuccessfully enabled: {len(results['success'])}")
    if results['failed']:
        print(f"Failed: {len(results['failed'])}")


def bulk_disable_integrations():
    """Disable multiple integrations without uninstalling"""
    print("\n" + "="*50)
    print("      BULK DISABLE INTEGRATIONS")
    print("="*50)

    ids_input = input("Enter install IDs to disable (comma-separated): ").strip()
    if not ids_input:
        print("No IDs provided.")
        return

    try:
        install_ids = [int(x.strip()) for x in ids_input.split(',')]
    except ValueError:
        print("Invalid ID format. Use comma-separated numbers.")
        return

    results = BulkOperationsManager.bulk_disable_integrations(install_ids)

    print(f"\nSuccessfully disabled: {len(results['success'])}")
    if results['failed']:
        print(f"Failed: {len(results['failed'])}")


def bulk_sync_integrations():
    """Trigger sync for all selected/enabled integrations"""
    print("\n" + "="*50)
    print("      BULK SYNC INTEGRATIONS")
    print("="*50)

    ids_input = input("Enter install IDs to sync (comma-separated, or blank for all enabled): ").strip()

    install_ids = None
    if ids_input:
        try:
            install_ids = [int(x.strip()) for x in ids_input.split(',')]
        except ValueError:
            print("Invalid ID format. Use comma-separated numbers.")
            return

    scope = f"{len(install_ids)} integration(s)" if install_ids else "all enabled integrations"
    print(f"\nSyncing {scope}...")

    results = BulkOperationsManager.bulk_sync_integrations(install_ids)

    print(f"\nSuccessfully synced: {len(results['success'])}")
    for s in results['success']:
        print(f"  - Install {s['install_id']} -> Log ID: {s['log_id']}")

    if results['failed']:
        print(f"\nFailed: {len(results['failed'])}")
        for f in results['failed']:
            print(f"  - Install {f['install_id']}: {f['error']}")


def bulk_update_credentials():
    """Update endpoint URLs for multiple credentials at once"""
    print("\n" + "="*50)
    print("      BULK UPDATE CREDENTIALS")
    print("="*50)

    updates = []
    print("Enter credential updates (empty credential ID to finish):")

    while True:
        cred_id = input("\nCredential ID: ").strip()
        if not cred_id:
            break

        try:
            cred_id = int(cred_id)
        except ValueError:
            print("Invalid ID.")
            continue

        endpoint_url = input("New endpoint URL: ").strip()
        if endpoint_url:
            updates.append({'credential_id': cred_id, 'endpoint_url': endpoint_url})

    if not updates:
        print("No updates provided.")
        return

    results = BulkOperationsManager.bulk_update_credentials(updates)

    print(f"\nSuccessfully updated: {len(results['success'])}")
    if results['failed']:
        print(f"Failed: {len(results['failed'])}")
