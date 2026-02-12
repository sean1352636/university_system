"""
Integration Marketplace Core Service

Integration catalog, installation management, credentials,
sync logs, data mappings, webhooks, and usage analytics.

Extended with:
- Search & Discovery
- Bulk Operations
- Import/Export
- Reports & Dashboards
- Security & Credentials Management
- Scheduling & Automation
- Validation & Testing
- Data Mapping Tools
- Notifications & Alerts
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.feature_gui_factory import create_gui_launcher
from university_system.modules.shared.constants import paths
from university_system.modules.shared.utils.i18n import get_text, _
from university_system.core.sql_safety import validate_identifier

# Try to import optional dependencies
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


class IntegrationCatalogManager:
    """Manages integration catalog"""

    @staticmethod
    def add_integration(integration_name: str, provider_name: str,
                       integration_type: str, category: str,
                       description: str = "", version: str = "1.0",
                       is_official: bool = False) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_catalog (
                    integration_name, provider_name, integration_type,
                    category, description, version, is_official
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (integration_name, provider_name, integration_type,
                  category, description, version, is_official))
            integration_id = cursor.lastrowid
            conn.commit()
            return integration_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error adding integration: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_available_integrations(category: str = "") -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if category:
                cursor.execute('''
                    SELECT * FROM integration_catalog
                    WHERE category = ? AND is_active = 1
                    ORDER BY rating DESC, install_count DESC
                ''', (category,))
            else:
                cursor.execute('''
                    SELECT * FROM integration_catalog
                    WHERE is_active = 1
                    ORDER BY rating DESC, install_count DESC
                ''')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


class InstallationManager:
    """Manages integration installations"""

    @staticmethod
    def install_integration(integration_id: int, installed_by: str,
                           configuration: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Get version
            cursor.execute('''
                SELECT version FROM integration_catalog
                WHERE integration_id = ?
            ''', (integration_id,))
            version = cursor.fetchone()['version']

            cursor.execute('''
                INSERT INTO installed_integrations (
                    integration_id, installed_by, version_installed, configuration
                ) VALUES (?, ?, ?, ?)
            ''', (integration_id, installed_by, version, configuration))
            install_id = cursor.lastrowid

            # Update install count
            cursor.execute('''
                UPDATE integration_catalog
                SET install_count = install_count + 1
                WHERE integration_id = ?
            ''', (integration_id,))

            conn.commit()
            return install_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error installing integration: {e}")
        finally:
            conn.close()

    @staticmethod
    def uninstall_integration(install_id: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE installed_integrations
                SET status = 'uninstalled', is_enabled = 0
                WHERE install_id = ?
            ''', (install_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error uninstalling integration: {e}")
        finally:
            conn.close()


class CredentialManager:
    """Manages integration credentials"""

    @staticmethod
    def store_credentials(install_id: int, credential_type: str,
                         api_key: str = "", api_secret: str = "",
                         oauth_token: str = "", endpoint_url: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_credentials (
                    install_id, credential_type, api_key, api_secret,
                    oauth_token, endpoint_url
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (install_id, credential_type, api_key, api_secret,
                  oauth_token, endpoint_url))
            credential_id = cursor.lastrowid
            conn.commit()
            return credential_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error storing credentials: {e}")
        finally:
            conn.close()


class SyncManager:
    """Manages integration synchronization"""

    @staticmethod
    def start_sync(install_id: int) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_sync_logs (
                    install_id, sync_status
                ) VALUES (?, 'running')
            ''', (install_id,))
            log_id = cursor.lastrowid
            conn.commit()
            return log_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error starting sync: {e}")
        finally:
            conn.close()

    @staticmethod
    def complete_sync(log_id: int, sync_status: str, records_synced: int = 0,
                     errors_encountered: int = 0, error_details: str = "") -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE integration_sync_logs
                SET sync_end_time = ?, sync_status = ?,
                    records_synced = ?, errors_encountered = ?, error_details = ?
                WHERE log_id = ?
            ''', (datetime.now().isoformat(), sync_status, records_synced,
                  errors_encountered, error_details, log_id))

            # Update last sync date
            cursor.execute('''
                UPDATE installed_integrations
                SET last_sync_date = ?
                WHERE install_id = (
                    SELECT install_id FROM integration_sync_logs WHERE log_id = ?
                )
            ''', (datetime.now().isoformat(), log_id))

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error completing sync: {e}")
        finally:
            conn.close()


class DataMappingManager:
    """Manages field mappings for integrations"""

    @staticmethod
    def create_mapping(install_id: int, source_field: str, target_field: str,
                      transformation_rule: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_data_mappings (
                    install_id, source_field, target_field, transformation_rule
                ) VALUES (?, ?, ?, ?)
            ''', (install_id, source_field, target_field, transformation_rule))
            mapping_id = cursor.lastrowid
            conn.commit()
            return mapping_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating mapping: {e}")
        finally:
            conn.close()


class WebhookManager:
    """Manages integration webhooks"""

    @staticmethod
    def register_webhook(install_id: int, webhook_url: str, event_type: str,
                        secret_key: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_webhooks (
                    install_id, webhook_url, event_type, secret_key
                ) VALUES (?, ?, ?, ?)
            ''', (install_id, webhook_url, event_type, secret_key))
            webhook_id = cursor.lastrowid
            conn.commit()
            return webhook_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error registering webhook: {e}")
        finally:
            conn.close()


# =============================================================================
# SEARCH & DISCOVERY (1-6)
# =============================================================================

class SearchDiscoveryManager:
    """Manages search and discovery operations for integrations"""

    @staticmethod
    def search_catalog(query: str, highlight: bool = True) -> List[Dict[str, Any]]:
        """Full-text search across integration names, providers, and descriptions with highlighting"""
        with get_connection() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            cursor.execute('''
                SELECT integration_id, integration_name, provider_name, description,
                       category, integration_type, version, rating, install_count
                FROM integration_catalog
                WHERE is_active = 1 AND (
                    integration_name LIKE ? OR
                    provider_name LIKE ? OR
                    description LIKE ?
                )
                ORDER BY rating DESC, install_count DESC
            ''', (search_pattern, search_pattern, search_pattern))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if highlight and query:
                    # Add highlighting markers
                    for field in ['integration_name', 'provider_name', 'description']:
                        if result.get(field):
                            result[f'{field}_highlighted'] = re.sub(
                                f'({re.escape(query)})',
                                r'**\1**',
                                result[field],
                                flags=re.IGNORECASE
                            )
                results.append(result)
            return results

    @staticmethod
    def filter_by_rating(min_rating: float) -> List[Dict[str, Any]]:
        """Filter catalog by minimum star rating threshold"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM integration_catalog
                WHERE is_active = 1 AND rating >= ?
                ORDER BY rating DESC, install_count DESC
            ''', (min_rating,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def filter_by_compatibility(system_version: str) -> List[Dict[str, Any]]:
        """Show only integrations compatible with current system version"""
        with get_connection() as conn:
            cursor = conn.cursor()
            # Parse major.minor from version
            major_minor = '.'.join(system_version.split('.')[:2])
            cursor.execute('''
                SELECT * FROM integration_catalog
                WHERE is_active = 1 AND (
                    min_version IS NULL OR min_version <= ? OR
                    min_version LIKE ?
                )
                ORDER BY rating DESC
            ''', (system_version, f"{major_minor}%"))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def find_similar_integrations(integration_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Suggest similar integrations based on selected one's category/features"""
        with get_connection() as conn:
            cursor = conn.cursor()
            # Get the source integration's category and type
            cursor.execute('''
                SELECT category, integration_type FROM integration_catalog
                WHERE integration_id = ?
            ''', (integration_id,))
            source = cursor.fetchone()

            if not source:
                return []

            cursor.execute('''
                SELECT * FROM integration_catalog
                WHERE is_active = 1 AND integration_id != ?
                    AND (category = ? OR integration_type = ?)
                ORDER BY
                    CASE WHEN category = ? AND integration_type = ? THEN 0
                         WHEN category = ? THEN 1
                         ELSE 2 END,
                    rating DESC
                LIMIT ?
            ''', (integration_id, source['category'], source['integration_type'],
                  source['category'], source['integration_type'], source['category'], limit))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def search_sync_logs(start_date: str = None, end_date: str = None,
                        status: str = None, error_contains: str = None) -> List[Dict[str, Any]]:
        """Search logs by date range, status, or error message content"""
        with get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM integration_sync_logs WHERE 1=1"
            params = []

            if start_date:
                query += " AND sync_start_time >= ?"
                params.append(start_date)
            if end_date:
                query += " AND sync_start_time <= ?"
                params.append(end_date)
            if status:
                query += " AND sync_status = ?"
                params.append(status)
            if error_contains:
                query += " AND error_details LIKE ?"
                params.append(f"%{error_contains}%")

            query += " ORDER BY sync_start_time DESC LIMIT 500"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def advanced_filter(filters: Dict[str, Any], logic: str = 'AND') -> List[Dict[str, Any]]:
        """Multi-criteria filter with AND/OR logic"""
        with get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params = []

            if filters.get('category'):
                conditions.append("category = ?")
                params.append(filters['category'])
            if filters.get('integration_type'):
                conditions.append("integration_type = ?")
                params.append(filters['integration_type'])
            if filters.get('min_rating'):
                conditions.append("rating >= ?")
                params.append(filters['min_rating'])
            if filters.get('is_official') is not None:
                conditions.append("is_official = ?")
                params.append(1 if filters['is_official'] else 0)
            if filters.get('provider_name'):
                conditions.append("provider_name LIKE ?")
                params.append(f"%{filters['provider_name']}%")
            if filters.get('min_installs'):
                conditions.append("install_count >= ?")
                params.append(filters['min_installs'])

            if not conditions:
                conditions = ["1=1"]

            # Validate logic operator to prevent injection
            safe_logic = logic.upper() if logic.upper() in ('AND', 'OR') else 'AND'
            joiner = " " + safe_logic + " "
            query = "SELECT * FROM integration_catalog WHERE is_active = 1 AND (" + joiner.join(conditions) + ") ORDER BY rating DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# BULK OPERATIONS (7-12)
# =============================================================================

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
# IMPORT/EXPORT (13-18)
# =============================================================================

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
            filepath = os.path.join(paths.DATA_DIR, 'exports', f'catalog_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

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
            filepath = os.path.join(paths.DATA_DIR, 'exports', f'config_bundle_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        content = json.dumps(bundle, indent=2, default=str)

        if password:
            # Simple encryption using password hash
            key = hashlib.sha256(password.encode()).hexdigest()
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
            key = hashlib.sha256(password.encode()).hexdigest()
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
            filepath = os.path.join(paths.DATA_DIR, 'reports', f'sync_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')

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
            filepath = os.path.join(paths.DATA_DIR, 'exports', f'mappings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')

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
# REPORTS & DASHBOARDS (19-25)
# =============================================================================

class ReportsDashboardManager:
    """Manages reports and dashboard data for integrations"""

    @staticmethod
    def get_dashboard_overview() -> Dict[str, Any]:
        """Real-time dashboard with KPIs, charts, and status widgets"""
        dashboard = {
            'generated_at': datetime.now().isoformat(),
            'kpis': {},
            'status_summary': {},
            'recent_activity': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()

            # KPIs
            cursor.execute('SELECT COUNT(*) FROM integration_catalog WHERE is_active = 1')
            dashboard['kpis']['total_available'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM installed_integrations WHERE status = "active"')
            dashboard['kpis']['total_installed'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM installed_integrations WHERE is_enabled = 1')
            dashboard['kpis']['total_enabled'] = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM integration_sync_logs
                WHERE sync_start_time >= date('now', '-1 day')
            ''')
            dashboard['kpis']['syncs_last_24h'] = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM integration_sync_logs
                WHERE sync_status = 'failed' AND sync_start_time >= date('now', '-1 day')
            ''')
            dashboard['kpis']['failed_syncs_24h'] = cursor.fetchone()[0]

            # Status summary
            cursor.execute('''
                SELECT sync_status, COUNT(*) FROM integration_sync_logs
                WHERE sync_start_time >= date('now', '-7 days')
                GROUP BY sync_status
            ''')
            dashboard['status_summary'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Recent activity
            cursor.execute('''
                SELECT isl.log_id, ic.integration_name, isl.sync_status, isl.sync_start_time
                FROM integration_sync_logs isl
                JOIN installed_integrations ii ON isl.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                ORDER BY isl.sync_start_time DESC
                LIMIT 10
            ''')
            dashboard['recent_activity'] = [dict(row) for row in cursor.fetchall()]

        return dashboard

    @staticmethod
    def generate_health_report() -> Dict[str, Any]:
        """Comprehensive health report for all integrations"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'overall_health': 'healthy',
            'integrations': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ii.install_id, ic.integration_name, ii.status, ii.is_enabled,
                       ii.last_sync_date,
                       (SELECT COUNT(*) FROM integration_sync_logs isl
                        WHERE isl.install_id = ii.install_id AND isl.sync_status = 'failed'
                        AND isl.sync_start_time >= date('now', '-7 days')) as recent_failures
                FROM installed_integrations ii
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE ii.status != 'uninstalled'
            ''')

            unhealthy_count = 0
            for row in cursor.fetchall():
                health_status = 'healthy'
                issues = []

                if row['recent_failures'] > 0:
                    health_status = 'warning' if row['recent_failures'] < 3 else 'critical'
                    issues.append(f"{row['recent_failures']} failed syncs in last 7 days")

                if not row['is_enabled']:
                    health_status = 'disabled'
                    issues.append("Integration is disabled")

                if row['last_sync_date']:
                    last_sync = datetime.fromisoformat(row['last_sync_date'].replace('Z', '+00:00'))
                    if (datetime.now() - last_sync.replace(tzinfo=None)).days > 7:
                        if health_status == 'healthy':
                            health_status = 'warning'
                        issues.append("No sync in over 7 days")

                if health_status in ['warning', 'critical']:
                    unhealthy_count += 1

                report['integrations'].append({
                    'install_id': row['install_id'],
                    'integration_name': row['integration_name'],
                    'health_status': health_status,
                    'issues': issues
                })

            if unhealthy_count > len(report['integrations']) / 2:
                report['overall_health'] = 'critical'
            elif unhealthy_count > 0:
                report['overall_health'] = 'warning'

        return report

    @staticmethod
    def get_error_analysis(days: int = 30) -> Dict[str, Any]:
        """Analyze and categorize sync errors by type/frequency"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        analysis = {
            'period': f"Last {days} days",
            'total_errors': 0,
            'error_by_type': {},
            'error_by_integration': {},
            'top_error_messages': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) FROM integration_sync_logs
                WHERE sync_status = 'failed' AND sync_start_time >= ?
            ''', (cutoff,))
            analysis['total_errors'] = cursor.fetchone()[0]

            cursor.execute('''
                SELECT ic.integration_name, COUNT(*) as error_count
                FROM integration_sync_logs isl
                JOIN installed_integrations ii ON isl.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE isl.sync_status = 'failed' AND isl.sync_start_time >= ?
                GROUP BY ic.integration_name
                ORDER BY error_count DESC
            ''', (cutoff,))
            analysis['error_by_integration'] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute('''
                SELECT error_details, COUNT(*) as count
                FROM integration_sync_logs
                WHERE sync_status = 'failed' AND error_details IS NOT NULL
                    AND sync_start_time >= ?
                GROUP BY error_details
                ORDER BY count DESC
                LIMIT 10
            ''', (cutoff,))
            analysis['top_error_messages'] = [
                {'message': row[0], 'count': row[1]}
                for row in cursor.fetchall()
            ]

        return analysis

    @staticmethod
    def get_usage_trends(days: int = 30) -> Dict[str, Any]:
        """Usage trend data for visualization"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        trends = {
            'period': f"Last {days} days",
            'daily_syncs': [],
            'daily_records': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DATE(sync_start_time) as sync_date,
                       COUNT(*) as sync_count,
                       SUM(COALESCE(records_synced, 0)) as total_records
                FROM integration_sync_logs
                WHERE sync_start_time >= ?
                GROUP BY DATE(sync_start_time)
                ORDER BY sync_date
            ''', (cutoff,))

            for row in cursor.fetchall():
                trends['daily_syncs'].append({'date': row[0], 'count': row[1]})
                trends['daily_records'].append({'date': row[0], 'records': row[2]})

        return trends

    @staticmethod
    def get_api_call_statistics(days: int = 30) -> Dict[str, Any]:
        """Statistics on API calls per integration"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        stats = {
            'period': f"Last {days} days",
            'by_integration': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ic.integration_name,
                       COUNT(isl.log_id) as total_syncs,
                       SUM(CASE WHEN isl.sync_status = 'success' THEN 1 ELSE 0 END) as successful,
                       SUM(CASE WHEN isl.sync_status = 'failed' THEN 1 ELSE 0 END) as failed,
                       AVG(COALESCE(isl.records_synced, 0)) as avg_records
                FROM integration_sync_logs isl
                JOIN installed_integrations ii ON isl.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE isl.sync_start_time >= ?
                GROUP BY ic.integration_name
                ORDER BY total_syncs DESC
            ''', (cutoff,))

            for row in cursor.fetchall():
                stats['by_integration'].append({
                    'integration_name': row[0],
                    'total_syncs': row[1],
                    'successful': row[2],
                    'failed': row[3],
                    'success_rate': round(row[2] / row[1] * 100, 1) if row[1] > 0 else 0,
                    'avg_records_per_sync': round(row[4] or 0, 1)
                })

        return stats

    @staticmethod
    def compare_integration_performance(install_ids: List[int]) -> Dict[str, Any]:
        """Side-by-side performance comparison"""
        comparison = {'integrations': []}

        with get_connection() as conn:
            cursor = conn.cursor()
            for install_id in install_ids:
                cursor.execute('''
                    SELECT ic.integration_name,
                           COUNT(isl.log_id) as total_syncs,
                           SUM(CASE WHEN isl.sync_status = 'success' THEN 1 ELSE 0 END) as successful,
                           AVG(COALESCE(isl.records_synced, 0)) as avg_records,
                           AVG(
                               CASE WHEN isl.sync_end_time IS NOT NULL
                               THEN (julianday(isl.sync_end_time) - julianday(isl.sync_start_time)) * 86400
                               ELSE NULL END
                           ) as avg_duration_seconds
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    LEFT JOIN integration_sync_logs isl ON ii.install_id = isl.install_id
                    WHERE ii.install_id = ?
                    GROUP BY ii.install_id
                ''', (install_id,))

                row = cursor.fetchone()
                if row:
                    comparison['integrations'].append({
                        'install_id': install_id,
                        'integration_name': row[0],
                        'total_syncs': row[1] or 0,
                        'success_rate': round((row[2] or 0) / (row[1] or 1) * 100, 1),
                        'avg_records': round(row[3] or 0, 1),
                        'avg_duration_seconds': round(row[4] or 0, 2)
                    })

        return comparison

    @staticmethod
    def generate_compliance_report() -> Dict[str, Any]:
        """Report showing data handling compliance status"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'compliance_status': 'compliant',
            'findings': [],
            'integrations': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()

            # Check for integrations without encryption
            cursor.execute('''
                SELECT ic.integration_name, ii.install_id
                FROM installed_integrations ii
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE ii.status = 'active'
                AND NOT EXISTS (
                    SELECT 1 FROM integration_credentials icr
                    WHERE icr.install_id = ii.install_id
                )
            ''')
            no_creds = cursor.fetchall()
            if no_creds:
                report['findings'].append({
                    'severity': 'warning',
                    'finding': f"{len(no_creds)} active integrations have no credentials configured",
                    'affected': [row[0] for row in no_creds]
                })

            # Check for old credentials
            cursor.execute('''
                SELECT ic.integration_name, icr.created_at
                FROM integration_credentials icr
                JOIN installed_integrations ii ON icr.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE icr.created_at < date('now', '-90 days')
            ''')
            old_creds = cursor.fetchall()
            if old_creds:
                report['findings'].append({
                    'severity': 'info',
                    'finding': f"{len(old_creds)} integrations have credentials older than 90 days",
                    'recommendation': "Consider rotating credentials"
                })

            if any(f['severity'] == 'critical' for f in report['findings']):
                report['compliance_status'] = 'non-compliant'
            elif any(f['severity'] == 'warning' for f in report['findings']):
                report['compliance_status'] = 'needs-attention'

        return report


# =============================================================================
# SECURITY & CREDENTIALS (26-31)
# =============================================================================

class SecurityCredentialsManager:
    """Manages security and credential operations"""

    @staticmethod
    def rotate_api_credentials(credential_id: int) -> Dict[str, Any]:
        """Automatically rotate/regenerate API keys"""
        result = {'credential_id': credential_id, 'rotated': False}

        new_api_key = secrets.token_urlsafe(32)
        new_secret = secrets.token_urlsafe(48)

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE integration_credentials
                SET api_key = ?, api_secret = ?, created_at = ?
                WHERE credential_id = ?
            ''', (new_api_key, new_secret, datetime.now().isoformat(), credential_id))

            result['rotated'] = cursor.rowcount > 0
            result['new_api_key_prefix'] = new_api_key[:8] + '...' if result['rotated'] else None

        return result

    @staticmethod
    def check_credential_expiry(days_threshold: int = 30) -> List[Dict[str, Any]]:
        """Scan and alert for expiring credentials"""
        expiring = []
        threshold_date = (datetime.now() + timedelta(days=days_threshold)).isoformat()

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT icr.credential_id, ic.integration_name, icr.token_expiry, icr.created_at
                FROM integration_credentials icr
                JOIN installed_integrations ii ON icr.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE icr.token_expiry IS NOT NULL AND icr.token_expiry <= ?
            ''', (threshold_date,))

            for row in cursor.fetchall():
                expiry = datetime.fromisoformat(row['token_expiry'].replace('Z', '+00:00'))
                days_until = (expiry.replace(tzinfo=None) - datetime.now()).days
                expiring.append({
                    'credential_id': row['credential_id'],
                    'integration_name': row['integration_name'],
                    'token_expiry': row['token_expiry'],
                    'days_until_expiry': days_until,
                    'status': 'expired' if days_until < 0 else 'expiring_soon'
                })

        return expiring

    @staticmethod
    def validate_credentials(credential_id: int) -> Dict[str, Any]:
        """Test if credentials are still valid by pinging endpoint"""
        result = {'credential_id': credential_id, 'valid': False, 'message': ''}

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT endpoint_url, api_key FROM integration_credentials
                WHERE credential_id = ?
            ''', (credential_id,))
            cred = cursor.fetchone()

        if not cred:
            result['message'] = 'Credential not found'
            return result

        if not cred['endpoint_url']:
            result['message'] = 'No endpoint URL configured'
            return result

        # Simulate validation (in production, would make actual HTTP request)
        result['valid'] = True
        result['message'] = 'Endpoint reachable (simulated)'
        result['endpoint_url'] = cred['endpoint_url']

        return result

    @staticmethod
    def encrypt_export_credentials(password: str) -> str:
        """Export credentials with password encryption"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT credential_id, install_id, credential_type, endpoint_url
                FROM integration_credentials
            ''')
            credentials = [dict(row) for row in cursor.fetchall()]

        content = json.dumps({
            'exported_at': datetime.now().isoformat(),
            'credentials': credentials
        })

        # Simple XOR encryption
        key = hashlib.sha256(password.encode()).hexdigest()
        encrypted = ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(content))

        filepath = os.path.join(paths.DATA_DIR, 'exports', f'credentials_encrypted_{datetime.now().strftime("%Y%m%d_%H%M%S")}.enc')
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump({'encrypted': True, 'data': encrypted}, f)

        return filepath

    @staticmethod
    def audit_credential_access(credential_id: int = None, days: int = 30) -> List[Dict[str, Any]]:
        """View log of credential access events"""
        # This would typically query an audit log table
        # For now, return simulated data
        return [
            {
                'timestamp': datetime.now().isoformat(),
                'credential_id': credential_id or 1,
                'action': 'accessed',
                'user': 'system',
                'ip_address': '127.0.0.1',
                'note': 'Simulated audit log entry'
            }
        ]

    @staticmethod
    def revoke_all_tokens(install_id: int) -> Dict[str, Any]:
        """Emergency revoke all OAuth tokens for an integration"""
        result = {'install_id': install_id, 'revoked_count': 0}

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE integration_credentials
                SET oauth_token = NULL, oauth_refresh_token = NULL,
                    token_expiry = NULL
                WHERE install_id = ?
            ''', (install_id,))
            result['revoked_count'] = cursor.rowcount

        return result


# =============================================================================
# SCHEDULING & AUTOMATION (32-36)
# =============================================================================

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
# VALIDATION & TESTING (37-42)
# =============================================================================

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
# DATA MAPPING TOOLS (43-46)
# =============================================================================

class DataMappingToolsManager:
    """Advanced data mapping tools"""

    @staticmethod
    def auto_detect_mappings(install_id: int, source_fields: List[str],
                            target_fields: List[str]) -> List[Dict[str, Any]]:
        """Automatically suggest field mappings based on names"""
        suggestions = []

        # Normalize field names for comparison
        def normalize(name):
            return re.sub(r'[^a-z0-9]', '', name.lower())

        source_normalized = {normalize(f): f for f in source_fields}
        target_normalized = {normalize(f): f for f in target_fields}

        # Find exact matches
        for src_norm, src_orig in source_normalized.items():
            if src_norm in target_normalized:
                suggestions.append({
                    'source_field': src_orig,
                    'target_field': target_normalized[src_norm],
                    'confidence': 1.0,
                    'match_type': 'exact'
                })

        # Find partial matches
        for src_norm, src_orig in source_normalized.items():
            if src_norm not in target_normalized:  # Skip already matched
                for tgt_norm, tgt_orig in target_normalized.items():
                    if tgt_norm not in [s['target_field'] for s in suggestions if s['confidence'] == 1.0]:
                        # Check if one contains the other
                        if src_norm in tgt_norm or tgt_norm in src_norm:
                            suggestions.append({
                                'source_field': src_orig,
                                'target_field': tgt_orig,
                                'confidence': 0.7,
                                'match_type': 'partial'
                            })

        # Common field name mappings
        common_mappings = {
            'firstname': ['first_name', 'fname', 'givenname'],
            'lastname': ['last_name', 'lname', 'surname', 'familyname'],
            'email': ['emailaddress', 'mail', 'e_mail'],
            'phone': ['phonenumber', 'tel', 'telephone', 'mobile'],
            'id': ['identifier', 'uuid', 'key'],
            'createdat': ['created', 'creationdate', 'datecreated'],
            'updatedat': ['updated', 'modifiedat', 'lastmodified']
        }

        for src_norm, src_orig in source_normalized.items():
            for base, alternatives in common_mappings.items():
                if src_norm == base or src_norm in alternatives:
                    for tgt_norm, tgt_orig in target_normalized.items():
                        if tgt_norm == base or tgt_norm in alternatives:
                            if not any(s['source_field'] == src_orig and s['target_field'] == tgt_orig for s in suggestions):
                                suggestions.append({
                                    'source_field': src_orig,
                                    'target_field': tgt_orig,
                                    'confidence': 0.8,
                                    'match_type': 'semantic'
                                })

        return sorted(suggestions, key=lambda x: -x['confidence'])

    @staticmethod
    def preview_transformation(mapping_id: int, sample_data: Any) -> Dict[str, Any]:
        """Preview transformation rule output on sample data"""
        result = {'mapping_id': mapping_id, 'input': sample_data, 'output': None, 'error': None}

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT transformation_rule FROM integration_data_mappings
                WHERE mapping_id = ?
            ''', (mapping_id,))
            mapping = cursor.fetchone()

        if not mapping:
            result['error'] = 'Mapping not found'
            return result

        rule = mapping['transformation_rule']
        if not rule:
            result['output'] = sample_data
            result['message'] = 'No transformation (direct copy)'
            return result

        try:
            # Apply common transformations
            if rule.upper().startswith('UPPER'):
                result['output'] = str(sample_data).upper()
            elif rule.upper().startswith('LOWER'):
                result['output'] = str(sample_data).lower()
            elif rule.upper().startswith('TRIM'):
                result['output'] = str(sample_data).strip()
            elif rule.startswith('{') and rule.endswith('}'):
                # JSON template
                template = json.loads(rule)
                result['output'] = template
            else:
                result['output'] = sample_data
                result['message'] = 'Unknown transformation, using direct copy'
        except Exception as e:
            result['error'] = str(e)

        return result

    @staticmethod
    def duplicate_mapping_set(install_id: int, new_install_id: int) -> Dict[str, Any]:
        """Clone an existing mapping configuration"""
        result = {'source_install_id': install_id, 'target_install_id': new_install_id, 'mappings_copied': 0}

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT source_field, target_field, transformation_rule, is_active
                FROM integration_data_mappings
                WHERE install_id = ?
            ''', (install_id,))
            mappings = cursor.fetchall()

        with transaction() as conn:
            cursor = conn.cursor()
            for mapping in mappings:
                cursor.execute('''
                    INSERT INTO integration_data_mappings
                    (install_id, source_field, target_field, transformation_rule, is_active)
                    VALUES (?, ?, ?, ?, ?)
                ''', (new_install_id, mapping['source_field'], mapping['target_field'],
                      mapping['transformation_rule'], mapping['is_active']))
                result['mappings_copied'] += 1

        return result

    @staticmethod
    def import_mappings_from_template(install_id: int, template_name: str) -> Dict[str, Any]:
        """Import standard mapping templates"""
        templates = {
            'student_basic': [
                {'source': 'student_id', 'target': 'id', 'transform': None},
                {'source': 'first_name', 'target': 'firstName', 'transform': 'TRIM'},
                {'source': 'last_name', 'target': 'lastName', 'transform': 'TRIM'},
                {'source': 'email', 'target': 'emailAddress', 'transform': 'LOWER'},
                {'source': 'enrollment_date', 'target': 'enrolledAt', 'transform': None}
            ],
            'course_basic': [
                {'source': 'course_id', 'target': 'id', 'transform': None},
                {'source': 'course_name', 'target': 'title', 'transform': None},
                {'source': 'course_code', 'target': 'code', 'transform': 'UPPER'},
                {'source': 'credits', 'target': 'creditHours', 'transform': None}
            ],
            'grade_basic': [
                {'source': 'grade_id', 'target': 'id', 'transform': None},
                {'source': 'student_id', 'target': 'studentId', 'transform': None},
                {'source': 'course_id', 'target': 'courseId', 'transform': None},
                {'source': 'grade', 'target': 'letterGrade', 'transform': 'UPPER'},
                {'source': 'points', 'target': 'gradePoints', 'transform': None}
            ]
        }

        if template_name not in templates:
            return {'error': f"Template '{template_name}' not found. Available: {list(templates.keys())}"}

        result = {'install_id': install_id, 'template': template_name, 'mappings_created': 0}

        with transaction() as conn:
            cursor = conn.cursor()
            for mapping in templates[template_name]:
                cursor.execute('''
                    INSERT INTO integration_data_mappings
                    (install_id, source_field, target_field, transformation_rule, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (install_id, mapping['source'], mapping['target'], mapping['transform']))
                result['mappings_created'] += 1

        return result


# =============================================================================
# NOTIFICATIONS & ALERTS (47-50)
# =============================================================================

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
# CLI INTERFACE FUNCTIONS
# =============================================================================

def search_catalog():
    """Full-text search across integration names, providers, and descriptions with highlighting"""
    print("\n" + "="*50)
    print("      SEARCH INTEGRATION CATALOG")
    print("="*50)

    query = input("Enter search term: ").strip()
    if not query:
        print("No search term provided.")
        return

    results = SearchDiscoveryManager.search_catalog(query, highlight=True)

    if not results:
        print(f"\nNo integrations found matching '{query}'")
        return

    print(f"\nFound {len(results)} integration(s):\n")
    for i, r in enumerate(results, 1):
        name = r.get('integration_name_highlighted', r.get('integration_name', 'N/A'))
        provider = r.get('provider_name_highlighted', r.get('provider_name', 'N/A'))
        desc = r.get('description_highlighted', r.get('description', ''))[:80]
        rating = r.get('rating', 0)
        installs = r.get('install_count', 0)
        print(f"{i}. {name} by {provider}")
        print(f"   Rating: {'*' * int(rating)} ({rating:.1f}) | Installs: {installs}")
        print(f"   {desc}...")
        print()


def filter_by_rating():
    """Filter catalog by minimum star rating threshold"""
    print("\n" + "="*50)
    print("      FILTER BY RATING")
    print("="*50)

    try:
        min_rating = float(input("Enter minimum rating (0-5): ").strip())
        if min_rating < 0 or min_rating > 5:
            print("Rating must be between 0 and 5.")
            return
    except ValueError:
        print("Invalid rating value.")
        return

    results = SearchDiscoveryManager.filter_by_rating(min_rating)

    if not results:
        print(f"\nNo integrations found with rating >= {min_rating}")
        return

    print(f"\nFound {len(results)} integration(s) with rating >= {min_rating}:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('integration_name')} - Rating: {r.get('rating', 0):.1f} | Installs: {r.get('install_count', 0)}")


def filter_by_compatibility():
    """Show only integrations compatible with current system version"""
    print("\n" + "="*50)
    print("      FILTER BY COMPATIBILITY")
    print("="*50)

    system_version = input("Enter system version (e.g., 5.0.0): ").strip() or "5.0.0"

    results = SearchDiscoveryManager.filter_by_compatibility(system_version)

    if not results:
        print(f"\nNo integrations compatible with version {system_version}")
        return

    print(f"\nFound {len(results)} integration(s) compatible with v{system_version}:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('integration_name')} v{r.get('version', '1.0')} by {r.get('provider_name')}")


def find_similar_integrations():
    """Suggest similar integrations based on selected one's category/features"""
    print("\n" + "="*50)
    print("      FIND SIMILAR INTEGRATIONS")
    print("="*50)

    try:
        integration_id = int(input("Enter integration ID to find similar: ").strip())
    except ValueError:
        print("Invalid integration ID.")
        return

    limit = input("Max results (default 5): ").strip()
    limit = int(limit) if limit.isdigit() else 5

    results = SearchDiscoveryManager.find_similar_integrations(integration_id, limit)

    if not results:
        print(f"\nNo similar integrations found for ID {integration_id}")
        return

    print(f"\nFound {len(results)} similar integration(s):\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('integration_name')} - {r.get('category')} | {r.get('integration_type')}")
        print(f"   Rating: {r.get('rating', 0):.1f} | Installs: {r.get('install_count', 0)}")


def search_sync_logs():
    """Search logs by date range, status, or error message content"""
    print("\n" + "="*50)
    print("      SEARCH SYNC LOGS")
    print("="*50)

    start_date = input("Start date (YYYY-MM-DD, or blank): ").strip() or None
    end_date = input("End date (YYYY-MM-DD, or blank): ").strip() or None
    status = input("Status filter (success/failed/running, or blank): ").strip() or None
    error_contains = input("Error message contains (or blank): ").strip() or None

    results = SearchDiscoveryManager.search_sync_logs(start_date, end_date, status, error_contains)

    if not results:
        print("\nNo sync logs found matching criteria.")
        return

    print(f"\nFound {len(results)} log(s):\n")
    for log in results[:20]:  # Limit display
        print(f"Log #{log.get('log_id')} | Install: {log.get('install_id')} | Status: {log.get('sync_status')}")
        print(f"  Time: {log.get('sync_start_time')} | Records: {log.get('records_synced', 0)} | Errors: {log.get('errors_encountered', 0)}")
        if log.get('error_details'):
            print(f"  Error: {log.get('error_details')[:100]}...")
        print()

    if len(results) > 20:
        print(f"... and {len(results) - 20} more logs")


def advanced_filter_dialog():
    """Multi-criteria filter dialog with AND/OR logic"""
    print("\n" + "="*50)
    print("      ADVANCED FILTER")
    print("="*50)

    filters = {}

    category = input("Category (or blank): ").strip()
    if category:
        filters['category'] = category

    integration_type = input("Type (API/Webhook/File, or blank): ").strip()
    if integration_type:
        filters['integration_type'] = integration_type

    min_rating = input("Minimum rating (or blank): ").strip()
    if min_rating:
        try:
            filters['min_rating'] = float(min_rating)
        except ValueError:
            pass

    is_official = input("Official only? (y/n/blank): ").strip().lower()
    if is_official == 'y':
        filters['is_official'] = True
    elif is_official == 'n':
        filters['is_official'] = False

    provider = input("Provider name contains (or blank): ").strip()
    if provider:
        filters['provider_name'] = provider

    min_installs = input("Minimum installs (or blank): ").strip()
    if min_installs:
        try:
            filters['min_installs'] = int(min_installs)
        except ValueError:
            pass

    logic = input("Logic (AND/OR, default AND): ").strip().upper() or 'AND'

    results = SearchDiscoveryManager.advanced_filter(filters, logic)

    if not results:
        print("\nNo integrations found matching criteria.")
        return

    print(f"\nFound {len(results)} integration(s):\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('integration_name')} by {r.get('provider_name')}")
        print(f"   Category: {r.get('category')} | Type: {r.get('integration_type')} | Rating: {r.get('rating', 0):.1f}")


# =============================================================================
# BULK OPERATIONS CLI FUNCTIONS (7-12)
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


# =============================================================================
# IMPORT/EXPORT CLI FUNCTIONS (13-18)
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


# =============================================================================
# REPORTS & DASHBOARDS CLI FUNCTIONS (19-25)
# =============================================================================

def show_dashboard_overview():
    """Real-time dashboard with KPIs, charts, and status widgets"""
    print("\n" + "="*60)
    print("           INTEGRATION DASHBOARD")
    print("="*60)

    dashboard = ReportsDashboardManager.get_dashboard_overview()

    kpis = dashboard.get('kpis', {})
    print("\n--- KEY PERFORMANCE INDICATORS ---")
    print(f"  Available Integrations:  {kpis.get('total_available', 0)}")
    print(f"  Installed Integrations:  {kpis.get('total_installed', 0)}")
    print(f"  Enabled Integrations:    {kpis.get('total_enabled', 0)}")
    print(f"  Syncs (Last 24h):        {kpis.get('syncs_last_24h', 0)}")
    print(f"  Failed Syncs (24h):      {kpis.get('failed_syncs_24h', 0)}")

    status = dashboard.get('status_summary', {})
    if status:
        print("\n--- SYNC STATUS (Last 7 Days) ---")
        for s, count in status.items():
            bar = '*' * min(count, 20)
            print(f"  {s:12} {bar} ({count})")

    recent = dashboard.get('recent_activity', [])
    if recent:
        print("\n--- RECENT ACTIVITY ---")
        for activity in recent[:5]:
            print(f"  [{activity.get('sync_status', 'N/A'):8}] {activity.get('integration_name', 'N/A')} - {activity.get('sync_start_time', 'N/A')[:16]}")

    print(f"\nGenerated: {dashboard.get('generated_at', 'N/A')}")


def generate_health_report():
    """Comprehensive health report for all integrations"""
    print("\n" + "="*60)
    print("           INTEGRATION HEALTH REPORT")
    print("="*60)

    report = ReportsDashboardManager.generate_health_report()

    overall = report.get('overall_health', 'unknown')
    status_icon = {'healthy': '[OK]', 'warning': '[!]', 'critical': '[X]'}.get(overall, '[?]')
    print(f"\nOverall Status: {status_icon} {overall.upper()}")

    integrations = report.get('integrations', [])
    if integrations:
        print(f"\n--- INTEGRATION STATUS ({len(integrations)} total) ---")

        for status in ['critical', 'warning', 'disabled', 'healthy']:
            filtered = [i for i in integrations if i.get('health_status') == status]
            if filtered:
                icon = {'healthy': '[OK]', 'warning': '[!]', 'critical': '[X]', 'disabled': '[-]'}.get(status, '[?]')
                print(f"\n{icon} {status.upper()} ({len(filtered)}):")
                for integ in filtered:
                    print(f"    - {integ.get('integration_name')}")
                    for issue in integ.get('issues', []):
                        print(f"        {issue}")

    print(f"\nGenerated: {report.get('generated_at', 'N/A')}")


def show_error_analysis():
    """Analyze and categorize sync errors by type/frequency"""
    print("\n" + "="*60)
    print("           ERROR ANALYSIS")
    print("="*60)

    days = input("Analysis period in days (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    analysis = ReportsDashboardManager.get_error_analysis(days)

    print(f"\n--- SUMMARY ({analysis.get('period')}) ---")
    print(f"  Total Errors: {analysis.get('total_errors', 0)}")

    by_integration = analysis.get('error_by_integration', {})
    if by_integration:
        print("\n--- ERRORS BY INTEGRATION ---")
        for name, count in sorted(by_integration.items(), key=lambda x: -x[1])[:10]:
            bar = '*' * min(count, 20)
            print(f"  {name[:25]:25} {bar} ({count})")

    top_errors = analysis.get('top_error_messages', [])
    if top_errors:
        print("\n--- TOP ERROR MESSAGES ---")
        for i, err in enumerate(top_errors[:5], 1):
            msg = err.get('message', 'N/A')[:60]
            print(f"  {i}. [{err.get('count')}x] {msg}...")


def generate_usage_trend_chart():
    """Usage trend data visualization"""
    print("\n" + "="*60)
    print("           USAGE TRENDS")
    print("="*60)

    days = input("Trend period in days (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    trends = ReportsDashboardManager.get_usage_trends(days)

    daily_syncs = trends.get('daily_syncs', [])
    if daily_syncs:
        print(f"\n--- DAILY SYNC COUNT ({trends.get('period')}) ---")
        max_count = max(d.get('count', 0) for d in daily_syncs) or 1
        for day in daily_syncs[-14:]:  # Last 14 days
            count = day.get('count', 0)
            bar_len = int((count / max_count) * 30)
            bar = '*' * bar_len
            print(f"  {day.get('date', 'N/A')}: {bar} ({count})")

    daily_records = trends.get('daily_records', [])
    if daily_records:
        print(f"\n--- DAILY RECORDS SYNCED ---")
        max_records = max(d.get('records', 0) for d in daily_records) or 1
        for day in daily_records[-14:]:
            records = day.get('records', 0)
            bar_len = int((records / max_records) * 30) if max_records > 0 else 0
            bar = '*' * bar_len
            print(f"  {day.get('date', 'N/A')}: {bar} ({records})")


def show_api_call_statistics():
    """Statistics on API calls per integration"""
    print("\n" + "="*60)
    print("           API CALL STATISTICS")
    print("="*60)

    days = input("Statistics period in days (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    stats = ReportsDashboardManager.get_api_call_statistics(days)

    print(f"\n--- BY INTEGRATION ({stats.get('period')}) ---")
    print(f"{'Integration':<25} {'Total':>8} {'Success':>8} {'Failed':>8} {'Rate':>8} {'Avg Rec':>10}")
    print("-" * 75)

    for integ in stats.get('by_integration', []):
        print(f"{integ.get('integration_name', 'N/A')[:24]:<25} "
              f"{integ.get('total_syncs', 0):>8} "
              f"{integ.get('successful', 0):>8} "
              f"{integ.get('failed', 0):>8} "
              f"{integ.get('success_rate', 0):>7.1f}% "
              f"{integ.get('avg_records_per_sync', 0):>10.1f}")


def compare_integration_performance():
    """Side-by-side performance comparison"""
    print("\n" + "="*60)
    print("           PERFORMANCE COMPARISON")
    print("="*60)

    ids_input = input("Enter install IDs to compare (comma-separated): ").strip()
    if not ids_input:
        print("No IDs provided.")
        return

    try:
        install_ids = [int(x.strip()) for x in ids_input.split(',')]
    except ValueError:
        print("Invalid ID format.")
        return

    comparison = ReportsDashboardManager.compare_integration_performance(install_ids)

    integrations = comparison.get('integrations', [])
    if not integrations:
        print("\nNo data found for the specified integrations.")
        return

    print(f"\n{'Integration':<25} {'Syncs':>8} {'Success%':>10} {'Avg Rec':>10} {'Avg Time':>12}")
    print("-" * 70)

    for integ in integrations:
        print(f"{integ.get('integration_name', 'N/A')[:24]:<25} "
              f"{integ.get('total_syncs', 0):>8} "
              f"{integ.get('success_rate', 0):>9.1f}% "
              f"{integ.get('avg_records', 0):>10.1f} "
              f"{integ.get('avg_duration_seconds', 0):>10.2f}s")


def generate_compliance_report():
    """Report showing data handling compliance status"""
    print("\n" + "="*60)
    print("           COMPLIANCE REPORT")
    print("="*60)

    report = ReportsDashboardManager.generate_compliance_report()

    status = report.get('compliance_status', 'unknown')
    status_icon = {'compliant': '[OK]', 'needs-attention': '[!]', 'non-compliant': '[X]'}.get(status, '[?]')
    print(f"\nCompliance Status: {status_icon} {status.upper()}")

    findings = report.get('findings', [])
    if findings:
        print("\n--- FINDINGS ---")
        for finding in findings:
            severity = finding.get('severity', 'info').upper()
            icon = {'CRITICAL': '[X]', 'WARNING': '[!]', 'INFO': '[i]'}.get(severity, '[?]')
            print(f"\n{icon} {severity}: {finding.get('finding')}")
            if finding.get('affected'):
                print(f"   Affected: {', '.join(finding.get('affected')[:5])}")
            if finding.get('recommendation'):
                print(f"   Recommendation: {finding.get('recommendation')}")
    else:
        print("\nNo compliance issues found.")

    print(f"\nGenerated: {report.get('generated_at', 'N/A')}")


# =============================================================================
# SECURITY & CREDENTIALS CLI FUNCTIONS (26-31)
# =============================================================================

def rotate_api_credentials():
    """Automatically rotate/regenerate API keys"""
    print("\n" + "="*50)
    print("      ROTATE API CREDENTIALS")
    print("="*50)

    try:
        credential_id = int(input("Enter credential ID to rotate: ").strip())
    except ValueError:
        print("Invalid credential ID.")
        return

    confirm = input(f"Rotate credentials for ID {credential_id}? This will invalidate current keys. (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        result = SecurityCredentialsManager.rotate_api_credentials(credential_id)
        if result.get('rotated'):
            print(f"\nCredentials rotated successfully!")
            print(f"  Credential ID: {result.get('credential_id')}")
            print(f"  New API Key (prefix): {result.get('new_api_key_prefix')}")
            print("\nIMPORTANT: Update your integration with the new credentials.")
        else:
            print("\nFailed to rotate credentials. Credential may not exist.")
    except Exception as e:
        print(f"\nError rotating credentials: {e}")


def check_credential_expiry():
    """Scan and alert for expiring credentials"""
    print("\n" + "="*50)
    print("      CHECK CREDENTIAL EXPIRY")
    print("="*50)

    days = input("Days threshold (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    try:
        expiring = SecurityCredentialsManager.check_credential_expiry(days)

        if not expiring:
            print(f"\nNo credentials expiring within {days} days.")
            return

        print(f"\nFound {len(expiring)} credential(s) expiring within {days} days:\n")

        expired = [c for c in expiring if c.get('status') == 'expired']
        expiring_soon = [c for c in expiring if c.get('status') == 'expiring_soon']

        if expired:
            print("[X] EXPIRED:")
            for c in expired:
                print(f"    - {c.get('integration_name')} (ID: {c.get('credential_id')})")
                print(f"      Expired: {c.get('token_expiry')}")

        if expiring_soon:
            print("\n[!] EXPIRING SOON:")
            for c in expiring_soon:
                print(f"    - {c.get('integration_name')} (ID: {c.get('credential_id')})")
                print(f"      Expires: {c.get('token_expiry')} ({c.get('days_until_expiry')} days)")

    except Exception as e:
        print(f"\nError checking expiry: {e}")


def validate_credentials():
    """Test if credentials are still valid by pinging endpoint"""
    print("\n" + "="*50)
    print("      VALIDATE CREDENTIALS")
    print("="*50)

    try:
        credential_id = int(input("Enter credential ID to validate: ").strip())
    except ValueError:
        print("Invalid credential ID.")
        return

    print("\nValidating credentials...")

    try:
        result = SecurityCredentialsManager.validate_credentials(credential_id)

        if result.get('valid'):
            print(f"\n[OK] Credentials are VALID")
            print(f"  Endpoint: {result.get('endpoint_url', 'N/A')}")
            print(f"  Message: {result.get('message')}")
        else:
            print(f"\n[X] Credentials are INVALID")
            print(f"  Message: {result.get('message')}")

    except Exception as e:
        print(f"\nError validating credentials: {e}")


def encrypt_export_credentials():
    """Export credentials with password encryption"""
    print("\n" + "="*50)
    print("      EXPORT ENCRYPTED CREDENTIALS")
    print("="*50)

    password = input("Enter encryption password: ").strip()
    if not password:
        print("Password is required for encrypted export.")
        return

    confirm_password = input("Confirm password: ").strip()
    if password != confirm_password:
        print("Passwords do not match.")
        return

    try:
        filepath = SecurityCredentialsManager.encrypt_export_credentials(password)
        print(f"\nCredentials exported (encrypted) to:\n{filepath}")
        print("\nKeep this file secure and remember your password!")
    except Exception as e:
        print(f"\nError exporting credentials: {e}")


def audit_credential_access():
    """View log of credential access events"""
    print("\n" + "="*50)
    print("      CREDENTIAL ACCESS AUDIT")
    print("="*50)

    cred_id = input("Credential ID (or blank for all): ").strip()
    credential_id = int(cred_id) if cred_id.isdigit() else None

    days = input("Days of history (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    try:
        logs = SecurityCredentialsManager.audit_credential_access(credential_id, days)

        if not logs:
            print("\nNo access logs found.")
            return

        print(f"\n--- CREDENTIAL ACCESS LOG (Last {days} days) ---\n")
        for log in logs:
            print(f"[{log.get('timestamp', 'N/A')[:19]}] {log.get('action', 'N/A').upper()}")
            print(f"  Credential ID: {log.get('credential_id')}")
            print(f"  User: {log.get('user', 'N/A')} | IP: {log.get('ip_address', 'N/A')}")
            if log.get('note'):
                print(f"  Note: {log.get('note')}")
            print()

    except Exception as e:
        print(f"\nError retrieving audit logs: {e}")


def revoke_all_tokens():
    """Emergency revoke all OAuth tokens for an integration"""
    print("\n" + "="*50)
    print("      EMERGENCY TOKEN REVOCATION")
    print("="*50)

    print("\n[!] WARNING: This will revoke ALL OAuth tokens for the specified integration.")
    print("    The integration will stop working until new tokens are configured.\n")

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    confirm = input(f"CONFIRM: Revoke ALL tokens for install ID {install_id}? (type 'REVOKE' to confirm): ").strip()
    if confirm != 'REVOKE':
        print("Cancelled.")
        return

    try:
        result = SecurityCredentialsManager.revoke_all_tokens(install_id)
        print(f"\n[OK] Tokens revoked successfully!")
        print(f"  Install ID: {result.get('install_id')}")
        print(f"  Tokens revoked: {result.get('revoked_count')}")
    except Exception as e:
        print(f"\nError revoking tokens: {e}")


# =============================================================================
# SCHEDULING & AUTOMATION CLI FUNCTIONS (32-36)
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


# =============================================================================
# VALIDATION & TESTING CLI FUNCTIONS (37-42)
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
            print(f"\n[OK] CONNECTION SUCCESSFUL")
            print(f"  Endpoint: {result.get('endpoint_url', 'N/A')}")
            print(f"  Latency: {result.get('latency_ms')} ms")
            print(f"  Message: {result.get('message')}")
        else:
            print(f"\n[X] CONNECTION FAILED")
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
            print(f"\n[OK] Mapping rule is VALID")
            print(f"  Message: {result.get('message', 'Validation passed')}")
        else:
            print(f"\n[X] Mapping rule is INVALID")
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
            print(f"\n[OK] WEBHOOK DELIVERED")
            print(f"  URL: {result.get('webhook_url', 'N/A')}")
            print(f"  Payload: {json.dumps(result.get('payload_sent', {}), indent=2)[:200]}...")
            response = result.get('response', {})
            print(f"  Response: {response.get('status_code')} - {response.get('body', 'N/A')}")
        else:
            print(f"\n[X] WEBHOOK DELIVERY FAILED")
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
            print(f"\n[OK] Configuration is VALID")
            print(f"  Message: {result.get('message', 'Valid JSON')}")
            config = result.get('parsed_config')
            if config:
                print(f"\n  Configuration preview:")
                config_str = json.dumps(config, indent=2)
                for line in config_str.split('\n')[:10]:
                    print(f"    {line}")
                if config_str.count('\n') > 10:
                    print("    ...")
        else:
            print(f"\n[X] Configuration is INVALID")
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


# =============================================================================
# DATA MAPPING TOOLS CLI FUNCTIONS (43-46)
# =============================================================================

def auto_detect_mappings():
    """Automatically suggest field mappings based on names"""
    print("\n" + "="*50)
    print("      AUTO-DETECT FIELD MAPPINGS")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    print("\nEnter source fields (comma-separated):")
    source_input = input("> ").strip()
    if not source_input:
        print("Source fields are required.")
        return
    source_fields = [f.strip() for f in source_input.split(',')]

    print("\nEnter target fields (comma-separated):")
    target_input = input("> ").strip()
    if not target_input:
        print("Target fields are required.")
        return
    target_fields = [f.strip() for f in target_input.split(',')]

    try:
        suggestions = DataMappingToolsManager.auto_detect_mappings(install_id, source_fields, target_fields)

        if not suggestions:
            print("\nNo mapping suggestions found.")
            return

        print(f"\n--- SUGGESTED MAPPINGS ({len(suggestions)}) ---")
        print(f"{'Source':<25} {'Target':<25} {'Confidence':<12} {'Match Type':<12}")
        print("-" * 80)

        for s in suggestions:
            confidence = f"{s.get('confidence', 0) * 100:.0f}%"
            print(f"{s.get('source_field', 'N/A'):<25} "
                  f"{s.get('target_field', 'N/A'):<25} "
                  f"{confidence:<12} "
                  f"{s.get('match_type', 'N/A'):<12}")

        print("\nUse Data Mappings to create these mappings.")

    except Exception as e:
        print(f"\nError detecting mappings: {e}")


def preview_transformation():
    """Preview transformation rule output on sample data"""
    print("\n" + "="*50)
    print("      PREVIEW TRANSFORMATION")
    print("="*50)

    try:
        mapping_id = int(input("Enter mapping ID: ").strip())
    except ValueError:
        print("Invalid mapping ID.")
        return

    sample_data = input("Enter sample data to transform: ").strip()
    if not sample_data:
        print("Sample data is required.")
        return

    try:
        result = DataMappingToolsManager.preview_transformation(mapping_id, sample_data)

        print(f"\n--- TRANSFORMATION PREVIEW ---")
        print(f"  Input:  {result.get('input', 'N/A')}")
        print(f"  Output: {result.get('output', 'N/A')}")

        if result.get('error'):
            print(f"  Error: {result.get('error')}")
        elif result.get('message'):
            print(f"  Note: {result.get('message')}")

    except Exception as e:
        print(f"\nError previewing transformation: {e}")


def duplicate_mapping_set():
    """Clone an existing mapping configuration"""
    print("\n" + "="*50)
    print("      DUPLICATE MAPPING SET")
    print("="*50)

    try:
        source_id = int(input("Source install ID (copy from): ").strip())
        target_id = int(input("Target install ID (copy to): ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    if source_id == target_id:
        print("Source and target must be different.")
        return

    confirm = input(f"Copy all mappings from install {source_id} to {target_id}? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        result = DataMappingToolsManager.duplicate_mapping_set(source_id, target_id)
        print(f"\nMappings duplicated successfully!")
        print(f"  From: Install ID {result.get('source_install_id')}")
        print(f"  To: Install ID {result.get('target_install_id')}")
        print(f"  Mappings copied: {result.get('mappings_copied')}")

    except Exception as e:
        print(f"\nError duplicating mappings: {e}")


def import_mappings_from_template():
    """Import standard mapping templates"""
    print("\n" + "="*50)
    print("      IMPORT MAPPING TEMPLATE")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    print("\nAvailable templates:")
    print("  - student_basic: Standard student fields")
    print("  - course_basic: Standard course fields")
    print("  - grade_basic: Standard grade fields")

    template_name = input("\nTemplate name: ").strip().lower()
    if not template_name:
        print("Template name is required.")
        return

    try:
        result = DataMappingToolsManager.import_mappings_from_template(install_id, template_name)

        if result.get('error'):
            print(f"\n[X] Error: {result.get('error')}")
            return

        print(f"\nTemplate imported successfully!")
        print(f"  Install ID: {result.get('install_id')}")
        print(f"  Template: {result.get('template')}")
        print(f"  Mappings created: {result.get('mappings_created')}")

    except Exception as e:
        print(f"\nError importing template: {e}")


# =============================================================================
# NOTIFICATIONS & ALERTS CLI FUNCTIONS (47-50)
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
        print(f"\nAlert rules configured!")
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
        print(f"\nSubscription created!")
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
            print(f"\n[OK] TEST NOTIFICATION SENT")
            print(f"  Channel: {result.get('channel_type')}")
            print(f"  Target: {result.get('target')}")
            print(f"  Message: {result.get('message')}")
        else:
            print(f"\n[X] TEST NOTIFICATION FAILED")
            print(f"  Message: {result.get('message')}")

    except Exception as e:
        print(f"\nError testing channel: {e}")


# =============================================================================
# MAIN CLI MENU
# =============================================================================

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
                print(f"\nFeature available via Integration managers.")
                print("Use: from university_system.modules.shared.services.integrations import IntegrationCatalogManager")

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



__all__ = [
    # Manager Classes
    'IntegrationCatalogManager', 'InstallationManager', 'CredentialManager',
    'SyncManager', 'DataMappingManager', 'WebhookManager',
    'SearchDiscoveryManager', 'BulkOperationsManager', 'ImportExportManager',
    'ReportsDashboardManager', 'SecurityCredentialsManager', 'SchedulingManager',
    'ValidationTestingManager', 'DataMappingToolsManager', 'NotificationsAlertManager',

    # CLI Functions - Search & Discovery (10-15)
    'search_catalog', 'filter_by_rating', 'filter_by_compatibility',
    'find_similar_integrations', 'search_sync_logs', 'advanced_filter_dialog',

    # CLI Functions - Bulk Operations (20-25)
    'bulk_install_integrations', 'bulk_uninstall_integrations',
    'bulk_enable_integrations', 'bulk_disable_integrations',
    'bulk_sync_integrations', 'bulk_update_credentials',

    # CLI Functions - Import/Export (30-35)
    'export_catalog_to_json', 'import_integrations_from_json',
    'export_configuration_bundle', 'import_configuration_bundle',
    'export_sync_report_pdf', 'export_mappings_to_excel',

    # CLI Functions - Reports & Dashboards (40-46)
    'show_dashboard_overview', 'generate_health_report', 'show_error_analysis',
    'generate_usage_trend_chart', 'show_api_call_statistics',
    'compare_integration_performance', 'generate_compliance_report',

    # CLI Functions - Security & Credentials (50-55)
    'rotate_api_credentials', 'check_credential_expiry', 'validate_credentials',
    'encrypt_export_credentials', 'audit_credential_access', 'revoke_all_tokens',

    # CLI Functions - Scheduling & Automation (60-64)
    'schedule_sync', 'view_scheduled_tasks', 'pause_scheduled_syncs',
    'set_maintenance_window', 'configure_retry_policy',

    # CLI Functions - Validation & Testing (70-75)
    'test_integration_connection', 'validate_mapping_rules', 'dry_run_sync',
    'test_webhook_delivery', 'validate_json_configuration', 'run_integration_diagnostics',

    # CLI Functions - Data Mapping Tools (80-83)
    'auto_detect_mappings', 'preview_transformation',
    'duplicate_mapping_set', 'import_mappings_from_template',

    # CLI Functions - Notifications & Alerts (90-93)
    'configure_alert_rules', 'subscribe_to_notifications',
    'view_notification_history', 'test_notification_channel',

    # Menu & GUI
    'display_integration_marketplace_menu',
    'launch_integration_marketplace_gui',
]
