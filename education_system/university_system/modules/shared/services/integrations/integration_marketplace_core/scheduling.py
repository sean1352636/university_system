"""Scheduling & Automation Manager and CLI functions"""

from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import (
    datetime, json, os, Any, Dict, List, get_connection, paths, transaction,
)


class SchedulingManager:
    """Manages scheduling and automation for integrations"""

    @staticmethod
    def schedule_sync(install_id: int, cron_expression: str = None,
                     frequency: str = 'daily', time_of_day: str = '00:00') -> Dict[str, Any]:
        """Set up scheduled sync jobs with cron-like configuration"""
        schedule_config = {
            'install_id': install_id,
            'frequency': frequency,
            'time_of_day': time_of_day,
            'cron_expression': cron_expression,
            'created_at': datetime.now().isoformat()
        }

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE installed_integrations
                SET sync_frequency = ?, configuration = json_set(
                    COALESCE(configuration, '{}'),
                    '$.schedule', ?
                )
                WHERE install_id = ?
            ''', (frequency, json.dumps(schedule_config), install_id))

        return schedule_config

    @staticmethod
    def get_scheduled_tasks() -> List[Dict[str, Any]]:
        """View/manage all scheduled sync tasks"""
        tasks = []

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ii.install_id, ic.integration_name, ii.sync_frequency,
                       ii.configuration, ii.is_enabled, ii.last_sync_date
                FROM installed_integrations ii
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE ii.status = 'active' AND ii.sync_frequency != 'manual'
            ''')

            for row in cursor.fetchall():
                config = json.loads(row['configuration']) if row['configuration'] else {}
                schedule = config.get('schedule', {})
                tasks.append({
                    'install_id': row['install_id'],
                    'integration_name': row['integration_name'],
                    'frequency': row['sync_frequency'],
                    'time_of_day': schedule.get('time_of_day', 'Not set'),
                    'is_enabled': bool(row['is_enabled']),
                    'last_sync': row['last_sync_date'],
                    'is_paused': schedule.get('paused', False)
                })

        return tasks

    @staticmethod
    def pause_scheduled_syncs(install_ids: List[int] = None) -> Dict[str, Any]:
        """Temporarily pause all scheduled syncs"""
        result = {'paused': []}

        with transaction() as conn:
            cursor = conn.cursor()

            if install_ids:
                for install_id in install_ids:
                    cursor.execute('''
                        UPDATE installed_integrations
                        SET configuration = json_set(
                            COALESCE(configuration, '{}'),
                            '$.schedule.paused', 1
                        )
                        WHERE install_id = ?
                    ''', (install_id,))
                    result['paused'].append(install_id)
            else:
                cursor.execute('''
                    UPDATE installed_integrations
                    SET configuration = json_set(
                        COALESCE(configuration, '{}'),
                        '$.schedule.paused', 1
                    )
                    WHERE sync_frequency != 'manual'
                ''')
                result['paused_all'] = True

        return result

    @staticmethod
    def set_maintenance_window(start_time: str, end_time: str,
                               days_of_week: List[str] = None) -> Dict[str, Any]:
        """Define maintenance windows when syncs won't run"""
        window = {
            'start_time': start_time,
            'end_time': end_time,
            'days_of_week': days_of_week or ['Saturday', 'Sunday'],
            'created_at': datetime.now().isoformat()
        }

        # Store in a config table or file
        config_path = os.path.join(paths.DATA_DIR, 'config', 'maintenance_windows.json')
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        windows = []
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                windows = json.load(f)

        windows.append(window)

        with open(config_path, 'w') as f:
            json.dump(windows, f, indent=2)

        return window

    @staticmethod
    def configure_retry_policy(install_id: int, max_retries: int = 3,
                              backoff_seconds: int = 60,
                              backoff_multiplier: float = 2.0) -> Dict[str, Any]:
        """Set retry attempts and backoff for failed syncs"""
        policy = {
            'max_retries': max_retries,
            'backoff_seconds': backoff_seconds,
            'backoff_multiplier': backoff_multiplier
        }

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE installed_integrations
                SET configuration = json_set(
                    COALESCE(configuration, '{}'),
                    '$.retry_policy', ?
                )
                WHERE install_id = ?
            ''', (json.dumps(policy), install_id))

        return {'install_id': install_id, 'retry_policy': policy}


# =============================================================================
# CLI FUNCTIONS
# =============================================================================

def schedule_sync():
    """Set up scheduled sync jobs with cron-like configuration"""
    print("\n" + "="*50)
    print("      SCHEDULE SYNC")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    print("\nFrequency options: hourly, daily, weekly, monthly")
    frequency = input("Frequency (default: daily): ").strip().lower() or 'daily'
    if frequency not in ['hourly', 'daily', 'weekly', 'monthly']:
        print("Invalid frequency. Using 'daily'.")
        frequency = 'daily'

    time_of_day = input("Time of day (HH:MM, default 00:00): ").strip() or '00:00'

    cron_expr = input("Custom cron expression (or blank to use frequency): ").strip() or None

    try:
        result = SchedulingManager.schedule_sync(install_id, cron_expr, frequency, time_of_day)
        print(f"\nSync scheduled successfully!")
        print(f"  Install ID: {result.get('install_id')}")
        print(f"  Frequency: {result.get('frequency')}")
        print(f"  Time: {result.get('time_of_day')}")
        if result.get('cron_expression'):
            print(f"  Cron: {result.get('cron_expression')}")
    except Exception as e:
        print(f"\nError scheduling sync: {e}")


def view_scheduled_tasks():
    """View/manage all scheduled sync tasks"""
    print("\n" + "="*50)
    print("      SCHEDULED TASKS")
    print("="*50)

    try:
        tasks = SchedulingManager.get_scheduled_tasks()

        if not tasks:
            print("\nNo scheduled tasks found.")
            return

        print(f"\nFound {len(tasks)} scheduled task(s):\n")
        print(f"{'ID':<6} {'Integration':<25} {'Frequency':<10} {'Time':<8} {'Status':<10} {'Last Sync':<20}")
        print("-" * 85)

        for task in tasks:
            status = 'PAUSED' if task.get('is_paused') else ('ENABLED' if task.get('is_enabled') else 'DISABLED')
            last_sync = task.get('last_sync', 'Never')[:19] if task.get('last_sync') else 'Never'
            print(f"{task.get('install_id'):<6} "
                  f"{task.get('integration_name', 'N/A')[:24]:<25} "
                  f"{task.get('frequency', 'N/A'):<10} "
                  f"{task.get('time_of_day', 'N/A'):<8} "
                  f"{status:<10} "
                  f"{last_sync:<20}")

    except Exception as e:
        print(f"\nError retrieving scheduled tasks: {e}")


def pause_scheduled_syncs():
    """Temporarily pause all scheduled syncs"""
    print("\n" + "="*50)
    print("      PAUSE SCHEDULED SYNCS")
    print("="*50)

    ids_input = input("Enter install IDs to pause (comma-separated, or blank for ALL): ").strip()

    install_ids = None
    if ids_input:
        try:
            install_ids = [int(x.strip()) for x in ids_input.split(',')]
        except ValueError:
            print("Invalid ID format.")
            return

    scope = f"{len(install_ids)} integration(s)" if install_ids else "ALL integrations"
    confirm = input(f"Pause scheduled syncs for {scope}? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        result = SchedulingManager.pause_scheduled_syncs(install_ids)
        if result.get('paused_all'):
            print("\n[OK] All scheduled syncs have been paused.")
        else:
            print(f"\n[OK] Paused syncs for {len(result.get('paused', []))} integration(s).")
    except Exception as e:
        print(f"\nError pausing syncs: {e}")


def set_maintenance_window():
    """Define maintenance windows when syncs won't run"""
    print("\n" + "="*50)
    print("      SET MAINTENANCE WINDOW")
    print("="*50)

    start_time = input("Start time (HH:MM): ").strip()
    if not start_time:
        print("Start time is required.")
        return

    end_time = input("End time (HH:MM): ").strip()
    if not end_time:
        print("End time is required.")
        return

    print("\nDays of week (comma-separated, e.g., Saturday,Sunday)")
    print("Options: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday")
    days_input = input("Days (default: Saturday,Sunday): ").strip()

    if days_input:
        days_of_week = [d.strip() for d in days_input.split(',')]
    else:
        days_of_week = ['Saturday', 'Sunday']

    try:
        result = SchedulingManager.set_maintenance_window(start_time, end_time, days_of_week)
        print(f"\nMaintenance window created!")
        print(f"  Time: {result.get('start_time')} - {result.get('end_time')}")
        print(f"  Days: {', '.join(result.get('days_of_week', []))}")
    except Exception as e:
        print(f"\nError setting maintenance window: {e}")


def configure_retry_policy():
    """Set retry attempts and backoff for failed syncs"""
    print("\n" + "="*50)
    print("      CONFIGURE RETRY POLICY")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    max_retries = input("Max retry attempts (default 3): ").strip()
    max_retries = int(max_retries) if max_retries.isdigit() else 3

    backoff = input("Initial backoff seconds (default 60): ").strip()
    backoff = int(backoff) if backoff.isdigit() else 60

    multiplier = input("Backoff multiplier (default 2.0): ").strip()
    try:
        multiplier = float(multiplier) if multiplier else 2.0
    except ValueError:
        multiplier = 2.0

    try:
        result = SchedulingManager.configure_retry_policy(install_id, max_retries, backoff, multiplier)
        policy = result.get('retry_policy', {})
        print(f"\nRetry policy configured for install ID {result.get('install_id')}:")
        print(f"  Max retries: {policy.get('max_retries')}")
        print(f"  Initial backoff: {policy.get('backoff_seconds')} seconds")
        print(f"  Backoff multiplier: {policy.get('backoff_multiplier')}x")
        print(f"\n  Retry delays: {backoff}s -> {int(backoff * multiplier)}s -> {int(backoff * multiplier * multiplier)}s ...")
    except Exception as e:
        print(f"\nError configuring retry policy: {e}")
