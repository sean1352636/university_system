"""Data loading methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timedelta
from tkinter import messagebox

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)


class DataLoadingMixin:
    """Mixin providing data loading/refresh methods."""

    def refresh_all_data(self):
        """Refresh all tab data"""
        try:
            self.load_catalog()
            self.load_installed()
            self.load_credentials()
            self.load_sync_logs()
            self.load_mappings()
            self.load_webhooks()
            self.load_analytics()
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")
            messagebox.showerror(_t("common.error"), _t("integration_marketplace.errors.refresh_failed", error=str(e)))

    def load_catalog(self):
        """Load integration catalog"""
        try:
            for item in self.catalog_tree.get_children():
                self.catalog_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                category = self.catalog_category_var.get()
                if category:
                    cursor.execute('''
                        SELECT integration_id, integration_name, provider_name, category,
                               integration_type, version, rating, install_count, is_official
                        FROM integration_catalog
                        WHERE category = ? AND is_active = 1
                        ORDER BY rating DESC, install_count DESC
                    ''', (category,))
                else:
                    cursor.execute('''
                        SELECT integration_id, integration_name, provider_name, category,
                               integration_type, version, rating, install_count, is_official
                        FROM integration_catalog
                        WHERE is_active = 1
                        ORDER BY rating DESC, install_count DESC
                        LIMIT 100
                    ''')

                integrations = cursor.fetchall()

                for integration in integrations:
                    is_official = _t("common.yes") if integration[8] else _t("common.no")
                    self.catalog_tree.insert('', 'end', values=(
                        integration[0], integration[1], integration[2], integration[3],
                        integration[4], integration[5], integration[6] or _t("common.na"),
                        integration[7] or 0, is_official
                    ))

            logger.info(f"Loaded {len(integrations)} integrations from catalog")

        except Exception as e:
            logger.error(f"Error loading catalog: {e}\n{traceback.format_exc()}")
            messagebox.showerror(_t("common.error"), f"Failed to load catalog: {e}")

    def load_installed(self):
        """Load installed integrations"""
        try:
            for item in self.installed_tree.get_children():
                self.installed_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                status_filter = self.installed_filter_var.get()
                if status_filter == 'all':
                    cursor.execute('''
                        SELECT ii.install_id, ic.integration_name, ii.version_installed,
                               ii.installation_date, ii.status, ii.last_sync_date,
                               ii.sync_frequency, ii.is_enabled
                        FROM installed_integrations ii
                        JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                        ORDER BY ii.installation_date DESC
                    ''')
                else:
                    cursor.execute('''
                        SELECT ii.install_id, ic.integration_name, ii.version_installed,
                               ii.installation_date, ii.status, ii.last_sync_date,
                               ii.sync_frequency, ii.is_enabled
                        FROM installed_integrations ii
                        JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                        WHERE ii.status = ?
                        ORDER BY ii.installation_date DESC
                    ''', (status_filter,))

                installed = cursor.fetchall()

                for install in installed:
                    enabled = _t("common.enabled") if install[7] else _t("common.disabled")
                    self.installed_tree.insert('', 'end', values=(
                        install[0], install[1], install[2], install[3],
                        install[4], install[5] or _t("common.never"), install[6], enabled
                    ))

            logger.info(f"Loaded {len(installed)} installed integrations")

        except Exception as e:
            logger.error(f"Error loading installed integrations: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to load installed integrations: {e}")

    def load_credentials(self):
        """Load integration credentials"""
        try:
            for item in self.cred_tree.get_children():
                self.cred_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT credential_id, install_id, credential_type, endpoint_url,
                           created_at, token_expiry
                    FROM integration_credentials
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                credentials = cursor.fetchall()

                for cred in credentials:
                    # Properly extract values from sqlite3.Row
                    self.cred_tree.insert('', 'end', values=(
                        cred[0],  # credential_id
                        cred[1],  # install_id
                        cred[2] or _t("common.na"),  # credential_type
                        cred[3] or _t("common.na"),  # endpoint_url
                        cred[4][:19] if cred[4] else 'N/A',  # created_at (trim timestamp)
                        cred[5][:19] if cred[5] else 'N/A'   # token_expiry (trim timestamp)
                    ))

            logger.info(f"Loaded {len(credentials)} credentials")

        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to load credentials: {e}")

    def load_sync_logs(self):
        """Load integration sync logs"""
        try:
            for item in self.sync_tree.get_children():
                self.sync_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                status_filter = self.sync_filter_var.get()
                if status_filter == 'all':
                    cursor.execute('''
                        SELECT log_id, install_id, sync_start_time, sync_end_time,
                               sync_status, records_synced, errors_encountered
                        FROM integration_sync_logs
                        ORDER BY sync_start_time DESC
                        LIMIT 100
                    ''')
                else:
                    cursor.execute('''
                        SELECT log_id, install_id, sync_start_time, sync_end_time,
                               sync_status, records_synced, errors_encountered
                        FROM integration_sync_logs
                        WHERE sync_status = ?
                        ORDER BY sync_start_time DESC
                        LIMIT 100
                    ''', (status_filter,))

                logs = cursor.fetchall()

                for log in logs:
                    # Properly extract values from sqlite3.Row
                    self.sync_tree.insert('', 'end', values=(
                        log[0],  # log_id
                        log[1],  # install_id
                        log[2][:19] if log[2] else 'N/A',  # sync_start_time
                        log[3][:19] if log[3] else 'N/A',  # sync_end_time
                        log[4] or _t("common.na"),  # sync_status
                        log[5] if log[5] is not None else 0,  # records_synced
                        log[6] if log[6] is not None else 0   # errors_encountered
                    ))

            logger.info(f"Loaded {len(logs)} sync logs")

        except Exception as e:
            logger.error(f"Error loading sync logs: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to load sync logs: {e}")

    def load_mappings(self):
        """Load data mappings"""
        try:
            for item in self.mappings_tree.get_children():
                self.mappings_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT mapping_id, install_id, source_field, target_field,
                           transformation_rule, is_active
                    FROM integration_data_mappings
                    ORDER BY install_id
                    LIMIT 100
                ''')

                mappings = cursor.fetchall()

                for mapping in mappings:
                    status = 'Active' if mapping[5] else 'Inactive'
                    self.mappings_tree.insert('', 'end', values=(
                        mapping[0], mapping[1], mapping[2], mapping[3],
                        mapping[4] or 'None', status
                    ))

            logger.info(f"Loaded {len(mappings)} data mappings")

        except Exception as e:
            logger.error(f"Error loading mappings: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to load mappings: {e}")

    def load_webhooks(self):
        """Load webhooks"""
        try:
            for item in self.webhooks_tree.get_children():
                self.webhooks_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT webhook_id, install_id, webhook_url, event_type,
                           is_active, last_triggered_at, created_at
                    FROM integration_webhooks
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                webhooks = cursor.fetchall()

                for webhook in webhooks:
                    status = 'Active' if webhook[4] else 'Inactive'
                    self.webhooks_tree.insert('', 'end', values=(
                        webhook[0], webhook[1], webhook[2], webhook[3],
                        status, webhook[5] or _t("common.never"), webhook[6]
                    ))

            logger.info(f"Loaded {len(webhooks)} webhooks")

        except Exception as e:
            logger.error(f"Error loading webhooks: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to load webhooks: {e}")

    def load_analytics(self):
        """Load usage analytics"""
        try:
            for item in self.analytics_tree.get_children():
                self.analytics_tree.delete(item)

            days = int(self.analytics_days_var.get())
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT analytics_id, install_id, metric_name, metric_value,
                           measurement_date
                    FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                    ORDER BY measurement_date DESC
                    LIMIT 100
                ''', (cutoff_date,))

                analytics = cursor.fetchall()

                for item in analytics:
                    self.analytics_tree.insert('', 'end', values=item)

            logger.info(f"Loaded {len(analytics)} analytics records")

        except Exception as e:
            logger.error(f"Error loading analytics: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to load analytics: {e}")
