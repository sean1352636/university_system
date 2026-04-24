"""Import/Export Manager and CLI functions"""

from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import (
    datetime, hashlib, json, os,
    Any, Dict, List,
    get_connection, paths, transaction,
    REPORTLAB_AVAILABLE, letter, SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, getSampleStyleSheet, colors,
    OPENPYXL_AVAILABLE, openpyxl,
)


class ImportExportManager:
    """Manages import and export operations for integrations"""

    @staticmethod
    def export_catalog_to_json(filepath: str = None) -> str:
        """Export full catalog to JSON file"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM integration_catalog WHERE is_active = 1')
            catalog = [dict(row) for row in cursor.fetchall()]

        if not filepath:
            filepath = os.path.join(paths.EXPORTS_DIR, f'catalog_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump({'exported_at': datetime.now().isoformat(), 'catalog': catalog}, f, indent=2, default=str)

        return filepath

    @staticmethod
    def import_integrations_from_json(filepath: str) -> Dict[str, Any]:
        """Import integrations from JSON backup"""
        results = {'imported': 0, 'skipped': 0, 'errors': []}

        with open(filepath, 'r') as f:
            data = json.load(f)

        catalog = data.get('catalog', data) if isinstance(data, dict) else data

        with transaction() as conn:
            cursor = conn.cursor()
            for item in catalog:
                try:
                    # Check if integration already exists
                    cursor.execute('''
                        SELECT integration_id FROM integration_catalog
                        WHERE integration_name = ? AND provider_name = ?
                    ''', (item.get('integration_name'), item.get('provider_name')))

                    if cursor.fetchone():
                        results['skipped'] += 1
                        continue

                    cursor.execute('''
                        INSERT INTO integration_catalog (
                            integration_name, provider_name, integration_type,
                            category, description, version, is_official
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (item.get('integration_name'), item.get('provider_name'),
                          item.get('integration_type', 'API'), item.get('category', 'Other'),
                          item.get('description', ''), item.get('version', '1.0'),
                          item.get('is_official', 0)))
                    results['imported'] += 1
                except Exception as e:
                    results['errors'].append({'item': item.get('integration_name'), 'error': str(e)})

        return results

    @staticmethod
    def export_configuration_bundle(filepath: str = None, password: str = None) -> str:
        """Export all configs, credentials (encrypted), and mappings as a bundle"""
        bundle = {
            'exported_at': datetime.now().isoformat(),
            'version': '1.0',
            'installed_integrations': [],
            'credentials': [],
            'data_mappings': [],
            'webhooks': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()

            # Export installed integrations
            cursor.execute('SELECT * FROM installed_integrations')
            bundle['installed_integrations'] = [dict(row) for row in cursor.fetchall()]

            # Export credentials (mask sensitive data)
            cursor.execute('SELECT credential_id, install_id, credential_type, endpoint_url, created_at FROM integration_credentials')
            bundle['credentials'] = [dict(row) for row in cursor.fetchall()]

            # Export mappings
            cursor.execute('SELECT * FROM integration_data_mappings')
            bundle['data_mappings'] = [dict(row) for row in cursor.fetchall()]

            # Export webhooks
            cursor.execute('SELECT webhook_id, install_id, webhook_url, event_type, is_active FROM integration_webhooks')
            bundle['webhooks'] = [dict(row) for row in cursor.fetchall()]

        if not filepath:
            filepath = os.path.join(paths.EXPORTS_DIR, f'config_bundle_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        content = json.dumps(bundle, indent=2, default=str)

        if password:
            # Derive encryption key from password using PBKDF2
            dk = hashlib.pbkdf2_hmac('sha256', password.encode(), b'config-bundle-salt', 100000)
            key = dk.hex()
            encrypted = ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(content))
            content = json.dumps({'encrypted': True, 'data': encrypted})

        with open(filepath, 'w') as f:
            f.write(content)

        return filepath

    @staticmethod
    def import_configuration_bundle(filepath: str, password: str = None) -> Dict[str, Any]:
        """Import and restore configuration bundle"""
        results = {'installed_integrations': 0, 'credentials': 0, 'mappings': 0, 'webhooks': 0, 'errors': []}

        with open(filepath, 'r') as f:
            content = f.read()

        data = json.loads(content)

        if data.get('encrypted'):
            if not password:
                raise ValueError("Password required for encrypted bundle")
            dk = hashlib.pbkdf2_hmac('sha256', password.encode(), b'config-bundle-salt', 100000)
            key = dk.hex()
            decrypted = ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data['data']))
            data = json.loads(decrypted)

        with transaction() as conn:
            cursor = conn.cursor()

            # Import installed integrations
            for item in data.get('installed_integrations', []):
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO installed_integrations
                        (integration_id, installed_by, version_installed, configuration, sync_frequency)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (item.get('integration_id'), item.get('installed_by', 'import'),
                          item.get('version_installed'), item.get('configuration'),
                          item.get('sync_frequency', 'daily')))
                    results['installed_integrations'] += 1
                except Exception as e:
                    results['errors'].append(str(e))

            # Import mappings
            for item in data.get('data_mappings', []):
                try:
                    cursor.execute('''
                        INSERT INTO integration_data_mappings
                        (install_id, source_field, target_field, transformation_rule, is_active)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (item.get('install_id'), item.get('source_field'),
                          item.get('target_field'), item.get('transformation_rule'),
                          item.get('is_active', 1)))
                    results['mappings'] += 1
                except Exception as e:
                    results['errors'].append(str(e))

        return results

    @staticmethod
    def export_sync_report_pdf(filepath: str = None, days: int = 30) -> str:
        """Generate PDF report of sync history"""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF export. Install with: pip install reportlab")

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT isl.log_id, ic.integration_name, isl.sync_start_time,
                       isl.sync_status, isl.records_synced, isl.errors_encountered
                FROM integration_sync_logs isl
                JOIN installed_integrations ii ON isl.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE isl.sync_start_time >= ?
                ORDER BY isl.sync_start_time DESC
            ''', (cutoff,))
            logs = cursor.fetchall()

        if not filepath:
            filepath = os.path.join(paths.REPORTS_DIR, f'sync_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"Sync Report - Last {days} Days", styles['Heading1']))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        elements.append(Spacer(1, 20))

        # Create table
        table_data = [['Log ID', 'Integration', 'Start Time', 'Status', 'Records', 'Errors']]
        for log in logs:
            table_data.append([
                str(log[0]), log[1] or 'N/A',
                log[2][:19] if log[2] else 'N/A',
                log[3] or 'N/A', str(log[4] or 0), str(log[5] or 0)
            ])

        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)

        doc.build(elements)
        return filepath

    @staticmethod
    def export_mappings_to_excel(filepath: str = None) -> str:
        """Export data mappings to Excel for review"""
        if not OPENPYXL_AVAILABLE:
            raise ImportError("openpyxl is required for Excel export. Install with: pip install openpyxl")

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT dm.mapping_id, ic.integration_name, dm.source_field,
                       dm.target_field, dm.transformation_rule, dm.is_active
                FROM integration_data_mappings dm
                JOIN installed_integrations ii ON dm.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                ORDER BY ic.integration_name
            ''')
            mappings = cursor.fetchall()

        if not filepath:
            filepath = os.path.join(paths.EXPORTS_DIR, f'mappings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data Mappings"

        # Header
        headers = ['Mapping ID', 'Integration', 'Source Field', 'Target Field', 'Transformation', 'Active']
        ws.append(headers)

        # Data
        for mapping in mappings:
            ws.append([
                mapping[0], mapping[1], mapping[2], mapping[3],
                mapping[4] or '', 'Yes' if mapping[5] else 'No'
            ])

        wb.save(filepath)
        return filepath


# =============================================================================
# CLI FUNCTIONS
# =============================================================================

def export_catalog_to_json():
    """Export full catalog to JSON file"""
    print("\n" + "="*50)
    print("      EXPORT CATALOG TO JSON")
    print("="*50)

    filepath = input("Export path (or blank for default): ").strip() or None

    try:
        result_path = ImportExportManager.export_catalog_to_json(filepath)
        print(f"\nCatalog exported successfully to:\n{result_path}")
    except Exception as e:
        print(f"\nError exporting catalog: {e}")


def import_integrations_from_json():
    """Import integrations from JSON backup"""
    print("\n" + "="*50)
    print("      IMPORT INTEGRATIONS FROM JSON")
    print("="*50)

    filepath = input("JSON file path: ").strip()
    if not filepath:
        print("No file path provided.")
        return

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    try:
        results = ImportExportManager.import_integrations_from_json(filepath)
        print(f"\nImport complete:")
        print(f"  Imported: {results['imported']}")
        print(f"  Skipped (already exist): {results['skipped']}")
        if results['errors']:
            print(f"  Errors: {len(results['errors'])}")
            for e in results['errors'][:5]:
                print(f"    - {e['item']}: {e['error']}")
    except Exception as e:
        print(f"\nError importing: {e}")


def export_configuration_bundle():
    """Export all configs, credentials (encrypted), and mappings as a bundle"""
    print("\n" + "="*50)
    print("      EXPORT CONFIGURATION BUNDLE")
    print("="*50)

    filepath = input("Export path (or blank for default): ").strip() or None
    password = input("Encryption password (or blank for no encryption): ").strip() or None

    try:
        result_path = ImportExportManager.export_configuration_bundle(filepath, password)
        encrypted_msg = " (encrypted)" if password else ""
        print(f"\nConfiguration bundle exported{encrypted_msg} to:\n{result_path}")
    except Exception as e:
        print(f"\nError exporting bundle: {e}")


def import_configuration_bundle():
    """Import and restore configuration bundle"""
    print("\n" + "="*50)
    print("      IMPORT CONFIGURATION BUNDLE")
    print("="*50)

    filepath = input("Bundle file path: ").strip()
    if not filepath:
        print("No file path provided.")
        return

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    password = input("Decryption password (if encrypted, or blank): ").strip() or None

    try:
        results = ImportExportManager.import_configuration_bundle(filepath, password)
        print(f"\nImport complete:")
        print(f"  Installed integrations: {results['installed_integrations']}")
        print(f"  Credentials: {results['credentials']}")
        print(f"  Mappings: {results['mappings']}")
        print(f"  Webhooks: {results['webhooks']}")
        if results['errors']:
            print(f"  Errors: {len(results['errors'])}")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError importing bundle: {e}")


def export_sync_report_pdf():
    """Generate PDF report of sync history"""
    print("\n" + "="*50)
    print("      EXPORT SYNC REPORT (PDF)")
    print("="*50)

    if not REPORTLAB_AVAILABLE:
        print("\nreportlab is required for PDF export.")
        print("Install with: pip install reportlab")
        return

    filepath = input("Export path (or blank for default): ").strip() or None
    days = input("Days of history (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    try:
        result_path = ImportExportManager.export_sync_report_pdf(filepath, days)
        print(f"\nSync report exported to:\n{result_path}")
    except Exception as e:
        print(f"\nError exporting report: {e}")


def export_mappings_to_excel():
    """Export data mappings to Excel for review"""
    print("\n" + "="*50)
    print("      EXPORT MAPPINGS TO EXCEL")
    print("="*50)

    if not OPENPYXL_AVAILABLE:
        print("\nopenpyxl is required for Excel export.")
        print("Install with: pip install openpyxl")
        return

    filepath = input("Export path (or blank for default): ").strip() or None

    try:
        result_path = ImportExportManager.export_mappings_to_excel(filepath)
        print(f"\nMappings exported to:\n{result_path}")
    except Exception as e:
        print(f"\nError exporting mappings: {e}")
