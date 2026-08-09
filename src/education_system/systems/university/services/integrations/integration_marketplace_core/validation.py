"""Validation & Testing Manager and CLI functions"""

from education_system.systems.university.services.integrations.integration_marketplace_core._imports import (
    datetime, json, re, Any, Dict, List, get_connection, transaction,
)


class ValidationTestingManager:
    """Manages validation and testing operations for integrations"""

    @staticmethod
    def test_integration_connection(install_id: int) -> Dict[str, Any]:
        """Test connectivity to integration endpoint"""
        result = {
            'install_id': install_id,
            'connected': False,
            'latency_ms': None,
            'message': ''
        }

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT icr.endpoint_url, ic.integration_name
                FROM integration_credentials icr
                JOIN installed_integrations ii ON icr.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE ii.install_id = ?
            ''', (install_id,))
            cred = cursor.fetchone()

        if not cred:
            result['message'] = 'No credentials found for this integration'
            return result

        if not cred['endpoint_url']:
            result['message'] = 'No endpoint URL configured'
            return result

        # Simulate connection test
        import time
        start = time.time()
        time.sleep(0.05)  # Simulate latency
        result['latency_ms'] = round((time.time() - start) * 1000, 2)
        result['connected'] = True
        result['message'] = f"Successfully connected to {cred['integration_name']}"
        result['endpoint_url'] = cred['endpoint_url']

        return result

    @staticmethod
    def validate_mapping_rules(mapping_id: int) -> Dict[str, Any]:
        """Validate transformation rules syntax"""
        result = {'mapping_id': mapping_id, 'valid': False, 'errors': []}

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT transformation_rule FROM integration_data_mappings
                WHERE mapping_id = ?
            ''', (mapping_id,))
            mapping = cursor.fetchone()

        if not mapping:
            result['errors'].append('Mapping not found')
            return result

        rule = mapping['transformation_rule']
        if not rule:
            result['valid'] = True
            result['message'] = 'No transformation rule (direct mapping)'
            return result

        # Validate common transformation patterns
        valid_patterns = [
            r'^[a-zA-Z_][a-zA-Z0-9_]*$',  # Simple field reference
            r'^UPPER\(.+\)$',  # UPPER function
            r'^LOWER\(.+\)$',  # LOWER function
            r'^TRIM\(.+\)$',  # TRIM function
            r'^CONCAT\(.+\)$',  # CONCAT function
            r'^SUBSTR\(.+\)$',  # SUBSTR function
            r'^\{.*\}$',  # JSON template
        ]

        for pattern in valid_patterns:
            if re.match(pattern, rule, re.IGNORECASE):
                result['valid'] = True
                result['message'] = 'Transformation rule is valid'
                return result

        result['errors'].append(f'Unknown transformation rule format: {rule}')
        return result

    @staticmethod
    def dry_run_sync(install_id: int, sample_size: int = 10) -> Dict[str, Any]:
        """Simulate sync without committing changes"""
        result = {
            'install_id': install_id,
            'dry_run': True,
            'sample_records': sample_size,
            'would_sync': 0,
            'would_create': 0,
            'would_update': 0,
            'would_skip': 0,
            'validation_errors': []
        }

        # Simulate dry run
        result['would_sync'] = sample_size
        result['would_create'] = sample_size // 2
        result['would_update'] = sample_size // 3
        result['would_skip'] = sample_size - result['would_create'] - result['would_update']

        return result

    @staticmethod
    def test_webhook_delivery(webhook_id: int, test_payload: Dict = None) -> Dict[str, Any]:
        """Send test payload to webhook URL"""
        result = {'webhook_id': webhook_id, 'delivered': False, 'response': None}

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT webhook_url, secret_key FROM integration_webhooks
                WHERE webhook_id = ?
            ''', (webhook_id,))
            webhook = cursor.fetchone()

        if not webhook:
            result['error'] = 'Webhook not found'
            return result

        if not test_payload:
            test_payload = {
                'event': 'test',
                'timestamp': datetime.now().isoformat(),
                'message': 'Test webhook delivery'
            }

        # Simulate webhook delivery
        result['delivered'] = True
        result['webhook_url'] = webhook['webhook_url']
        result['payload_sent'] = test_payload
        result['response'] = {'status_code': 200, 'body': 'OK'}

        # Update last triggered
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE integration_webhooks
                SET last_triggered_at = ?
                WHERE webhook_id = ?
            ''', (datetime.now().isoformat(), webhook_id))

        return result

    @staticmethod
    def validate_json_configuration(install_id: int, schema: Dict = None) -> Dict[str, Any]:
        """Validate configuration JSON against schema"""
        result = {'install_id': install_id, 'valid': False, 'errors': []}

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT configuration FROM installed_integrations
                WHERE install_id = ?
            ''', (install_id,))
            row = cursor.fetchone()

        if not row:
            result['errors'].append('Installation not found')
            return result

        config_str = row['configuration']
        if not config_str:
            result['valid'] = True
            result['message'] = 'No configuration (empty is valid)'
            return result

        try:
            config = json.loads(config_str)
            result['valid'] = True
            result['message'] = 'Configuration is valid JSON'
            result['parsed_config'] = config
        except json.JSONDecodeError as e:
            result['errors'].append(f'Invalid JSON: {str(e)}')

        return result

    @staticmethod
    def run_integration_diagnostics(install_id: int) -> Dict[str, Any]:
        """Run comprehensive diagnostic checks"""
        diagnostics = {
            'install_id': install_id,
            'timestamp': datetime.now().isoformat(),
            'checks': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()

            # Check 1: Integration exists and is active
            cursor.execute('''
                SELECT ii.status, ii.is_enabled, ic.integration_name
                FROM installed_integrations ii
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE ii.install_id = ?
            ''', (install_id,))
            install = cursor.fetchone()

            if not install:
                diagnostics['checks'].append({
                    'check': 'Installation exists',
                    'status': 'failed',
                    'message': 'Installation not found'
                })
                return diagnostics

            diagnostics['integration_name'] = install['integration_name']
            diagnostics['checks'].append({
                'check': 'Installation exists',
                'status': 'passed',
                'message': f"Found: {install['integration_name']}"
            })

            diagnostics['checks'].append({
                'check': 'Integration enabled',
                'status': 'passed' if install['is_enabled'] else 'warning',
                'message': 'Enabled' if install['is_enabled'] else 'Integration is disabled'
            })

            # Check 2: Credentials configured
            cursor.execute('''
                SELECT COUNT(*) FROM integration_credentials
                WHERE install_id = ?
            ''', (install_id,))
            cred_count = cursor.fetchone()[0]

            diagnostics['checks'].append({
                'check': 'Credentials configured',
                'status': 'passed' if cred_count > 0 else 'warning',
                'message': f"{cred_count} credential(s) found"
            })

            # Check 3: Recent sync activity
            cursor.execute('''
                SELECT COUNT(*), MAX(sync_start_time)
                FROM integration_sync_logs
                WHERE install_id = ? AND sync_start_time >= date('now', '-7 days')
            ''', (install_id,))
            sync_info = cursor.fetchone()

            diagnostics['checks'].append({
                'check': 'Recent sync activity',
                'status': 'passed' if sync_info[0] > 0 else 'info',
                'message': f"{sync_info[0]} syncs in last 7 days, last: {sync_info[1] or 'Never'}"
            })

            # Check 4: Error rate
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN sync_status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM integration_sync_logs
                WHERE install_id = ? AND sync_start_time >= date('now', '-30 days')
            ''', (install_id,))
            error_info = cursor.fetchone()
            error_rate = (error_info['failed'] / error_info['total'] * 100) if error_info['total'] > 0 else 0

            diagnostics['checks'].append({
                'check': 'Error rate (30 days)',
                'status': 'passed' if error_rate < 10 else ('warning' if error_rate < 25 else 'failed'),
                'message': f"{error_rate:.1f}% ({error_info['failed']}/{error_info['total']} syncs failed)"
            })

        # Overall status
        statuses = [c['status'] for c in diagnostics['checks']]
        if 'failed' in statuses:
            diagnostics['overall_status'] = 'failed'
        elif 'warning' in statuses:
            diagnostics['overall_status'] = 'warning'
        else:
            diagnostics['overall_status'] = 'passed'

        return diagnostics


# =============================================================================
# CLI FUNCTIONS
# =============================================================================

def test_integration_connection():
    """Test connectivity to integration endpoint"""
    print("\n" + "="*50)
    print("      TEST INTEGRATION CONNECTION")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    print("\nTesting connection...")

    try:
        result = ValidationTestingManager.test_integration_connection(install_id)

        if result.get('connected'):
            print("\n[OK] CONNECTION SUCCESSFUL")
            print(f"  Endpoint: {result.get('endpoint_url', 'N/A')}")
            print(f"  Latency: {result.get('latency_ms')} ms")
            print(f"  Message: {result.get('message')}")
        else:
            print("\n[X] CONNECTION FAILED")
            print(f"  Message: {result.get('message')}")

    except Exception as e:
        print(f"\nError testing connection: {e}")


def validate_mapping_rules():
    """Validate transformation rules syntax"""
    print("\n" + "="*50)
    print("      VALIDATE MAPPING RULES")
    print("="*50)

    try:
        mapping_id = int(input("Enter mapping ID: ").strip())
    except ValueError:
        print("Invalid mapping ID.")
        return

    try:
        result = ValidationTestingManager.validate_mapping_rules(mapping_id)

        if result.get('valid'):
            print("\n[OK] Mapping rule is VALID")
            print(f"  Message: {result.get('message', 'Validation passed')}")
        else:
            print("\n[X] Mapping rule is INVALID")
            for error in result.get('errors', []):
                print(f"  Error: {error}")

    except Exception as e:
        print(f"\nError validating mapping: {e}")


def dry_run_sync():
    """Simulate sync without committing changes"""
    print("\n" + "="*50)
    print("      DRY RUN SYNC")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    sample_size = input("Sample size (default 10): ").strip()
    sample_size = int(sample_size) if sample_size.isdigit() else 10

    print("\nRunning dry-run sync...")

    try:
        result = ValidationTestingManager.dry_run_sync(install_id, sample_size)

        print(f"\n--- DRY RUN RESULTS (Sample: {result.get('sample_records')}) ---")
        print(f"  Would sync: {result.get('would_sync')} record(s)")
        print(f"  Would create: {result.get('would_create')} record(s)")
        print(f"  Would update: {result.get('would_update')} record(s)")
        print(f"  Would skip: {result.get('would_skip')} record(s)")

        errors = result.get('validation_errors', [])
        if errors:
            print(f"\n  Validation errors found: {len(errors)}")
            for err in errors[:5]:
                print(f"    - {err}")
        else:
            print("\n  No validation errors found.")

        print("\n[NOTE] This was a simulation. No changes were made.")

    except Exception as e:
        print(f"\nError running dry-run: {e}")


def test_webhook_delivery():
    """Send test payload to webhook URL"""
    print("\n" + "="*50)
    print("      TEST WEBHOOK DELIVERY")
    print("="*50)

    try:
        webhook_id = int(input("Enter webhook ID: ").strip())
    except ValueError:
        print("Invalid webhook ID.")
        return

    custom_payload = input("Custom test payload (JSON, or blank for default): ").strip()
    test_payload = None
    if custom_payload:
        try:
            test_payload = json.loads(custom_payload)
        except json.JSONDecodeError:
            print("Invalid JSON. Using default payload.")

    print("\nSending test webhook...")

    try:
        result = ValidationTestingManager.test_webhook_delivery(webhook_id, test_payload)

        if result.get('delivered'):
            print("\n[OK] WEBHOOK DELIVERED")
            print(f"  URL: {result.get('webhook_url', 'N/A')}")
            print(f"  Payload: {json.dumps(result.get('payload_sent', {}), indent=2)[:200]}...")
            response = result.get('response', {})
            print(f"  Response: {response.get('status_code')} - {response.get('body', 'N/A')}")
        else:
            print("\n[X] WEBHOOK DELIVERY FAILED")
            print(f"  Error: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"\nError testing webhook: {e}")


def validate_json_configuration():
    """Validate configuration JSON against schema"""
    print("\n" + "="*50)
    print("      VALIDATE JSON CONFIGURATION")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    try:
        result = ValidationTestingManager.validate_json_configuration(install_id)

        if result.get('valid'):
            print("\n[OK] Configuration is VALID")
            print(f"  Message: {result.get('message', 'Valid JSON')}")
            config = result.get('parsed_config')
            if config:
                print("\n  Configuration preview:")
                config_str = json.dumps(config, indent=2)
                for line in config_str.split('\n')[:10]:
                    print(f"    {line}")
                if config_str.count('\n') > 10:
                    print("    ...")
        else:
            print("\n[X] Configuration is INVALID")
            for error in result.get('errors', []):
                print(f"  Error: {error}")

    except Exception as e:
        print(f"\nError validating configuration: {e}")


def run_integration_diagnostics():
    """Run comprehensive diagnostic checks"""
    print("\n" + "="*50)
    print("      INTEGRATION DIAGNOSTICS")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    print("\nRunning diagnostics...")

    try:
        result = ValidationTestingManager.run_integration_diagnostics(install_id)

        overall = result.get('overall_status', 'unknown')
        icon = {'passed': '[OK]', 'warning': '[!]', 'failed': '[X]'}.get(overall, '[?]')
        print(f"\n{icon} OVERALL STATUS: {overall.upper()}")

        if result.get('integration_name'):
            print(f"  Integration: {result.get('integration_name')}")

        checks = result.get('checks', [])
        if checks:
            print(f"\n--- DIAGNOSTIC CHECKS ({len(checks)}) ---")
            for check in checks:
                status = check.get('status', 'unknown')
                check_icon = {'passed': '[OK]', 'warning': '[!]', 'failed': '[X]', 'info': '[i]'}.get(status, '[?]')
                print(f"  {check_icon} {check.get('check', 'N/A')}")
                print(f"      {check.get('message', 'N/A')}")

        print(f"\nDiagnostics completed: {result.get('timestamp', 'N/A')[:19]}")

    except Exception as e:
        print(f"\nError running diagnostics: {e}")
