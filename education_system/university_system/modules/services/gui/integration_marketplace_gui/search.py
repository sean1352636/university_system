"""Search and discovery methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import logging

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)


class SearchMixin:
    """Mixin providing search and discovery methods."""

    def search_catalog(self):
        """Full-text search across integration names, providers, and descriptions with highlighting"""
        try:
            search_term = self.catalog_search_var.get().strip()
            if not search_term:
                messagebox.showwarning(_t("common.warning"), "Please enter a search term")
                return

            # Clear existing items
            for item in self.catalog_tree.get_children():
                self.catalog_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                search_pattern = f'%{search_term}%'
                cursor.execute('''
                    SELECT integration_id, integration_name, provider_name, category,
                           integration_type, version, rating, install_count, is_official,
                           description
                    FROM integration_catalog
                    WHERE is_active = 1 AND (
                        integration_name LIKE ? OR
                        provider_name LIKE ? OR
                        description LIKE ?
                    )
                    ORDER BY
                        CASE WHEN integration_name LIKE ? THEN 1
                             WHEN provider_name LIKE ? THEN 2
                             ELSE 3 END,
                        rating DESC
                ''', (search_pattern, search_pattern, search_pattern,
                      search_pattern, search_pattern))

                integrations = cursor.fetchall()

            for integration in integrations:
                is_official = 'Yes' if integration[8] else 'No'
                self.catalog_tree.insert('', 'end', values=(
                    integration[0], integration[1], integration[2], integration[3],
                    integration[4], integration[5], integration[6] or _t("common.na"),
                    integration[7] or 0, is_official
                ))

            # Update description with highlighted results
            if integrations:
                self.catalog_description.delete('1.0', 'end')
                self.catalog_description.insert('1.0',
                    f"Found {len(integrations)} integration(s) matching '{search_term}'")

            log_activity('search', 'integration_catalog', None,
                        details={'search_term': search_term, 'results_count': len(integrations)})

        except Exception as e:
            logger.error(f"Error searching catalog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to search catalog: {e}")

    def filter_by_rating(self):
        """Filter catalog by minimum star rating threshold"""
        try:
            min_rating = self.catalog_rating_var.get()
            if not min_rating:
                messagebox.showwarning(_t("common.warning"), "Please select a minimum rating")
                return

            min_rating = float(min_rating)

            # Clear existing items
            for item in self.catalog_tree.get_children():
                self.catalog_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT integration_id, integration_name, provider_name, category,
                           integration_type, version, rating, install_count, is_official
                    FROM integration_catalog
                    WHERE is_active = 1 AND rating >= ?
                    ORDER BY rating DESC, install_count DESC
                ''', (min_rating,))

                integrations = cursor.fetchall()

            for integration in integrations:
                is_official = 'Yes' if integration[8] else 'No'
                self.catalog_tree.insert('', 'end', values=(
                    integration[0], integration[1], integration[2], integration[3],
                    integration[4], integration[5], integration[6] or _t("common.na"),
                    integration[7] or 0, is_official
                ))

            messagebox.showinfo("Filter Results",
                              f"Found {len(integrations)} integration(s) with rating >= {min_rating}")

        except Exception as e:
            logger.error(f"Error filtering by rating: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to filter by rating: {e}")

    def filter_by_compatibility(self):
        """Show only integrations compatible with current system version"""
        try:
            # Get current system version
            system_version = "5.0.0"  # From CLAUDE.md

            # Clear existing items
            for item in self.catalog_tree.get_children():
                self.catalog_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                # Filter integrations that have compatible version (major version match)
                cursor.execute('''
                    SELECT integration_id, integration_name, provider_name, category,
                           integration_type, version, rating, install_count, is_official
                    FROM integration_catalog
                    WHERE is_active = 1
                    ORDER BY rating DESC, install_count DESC
                ''')

                integrations = cursor.fetchall()

            # Filter by version compatibility (major.minor compatibility)
            system_major = int(system_version.split('.')[0])
            compatible = []
            for integration in integrations:
                try:
                    int_version = integration[5] or "1.0.0"
                    int_major = int(int_version.split('.')[0])
                    # Compatible if integration major version <= system major version
                    if int_major <= system_major:
                        compatible.append(integration)
                except (ValueError, IndexError):
                    compatible.append(integration)  # Include if version parsing fails

            for integration in compatible:
                is_official = 'Yes' if integration[8] else 'No'
                self.catalog_tree.insert('', 'end', values=(
                    integration[0], integration[1], integration[2], integration[3],
                    integration[4], integration[5], integration[6] or _t("common.na"),
                    integration[7] or 0, is_official
                ))

            messagebox.showinfo("Compatibility Filter",
                              f"Found {len(compatible)} integration(s) compatible with system v{system_version}")

        except Exception as e:
            logger.error(f"Error filtering by compatibility: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to filter by compatibility: {e}")

    def find_similar_integrations(self):
        """Suggest similar integrations based on selected one's category/features"""
        try:
            selected = self.catalog_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to find similar ones")
                return

            values = self.catalog_tree.item(selected[0])['values']
            integration_id = values[0]
            category = values[3]
            integration_type = values[4]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT integration_id, integration_name, provider_name, category,
                           integration_type, version, rating, install_count, is_official
                    FROM integration_catalog
                    WHERE is_active = 1
                      AND integration_id != ?
                      AND (category = ? OR integration_type = ?)
                    ORDER BY
                        CASE WHEN category = ? AND integration_type = ? THEN 1
                             WHEN category = ? THEN 2
                             ELSE 3 END,
                        rating DESC
                    LIMIT 10
                ''', (integration_id, category, integration_type,
                      category, integration_type, category))

                similar = cursor.fetchall()

            if not similar:
                messagebox.showinfo("Similar Integrations", "No similar integrations found")
                return

            # Show in a dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Similar Integrations")
            dialog.geometry("700x400")
            dialog.transient(self.root)

            ttk.Label(dialog, text=f"Integrations similar to '{values[1]}':",
                     style='Title.TLabel').pack(padx=10, pady=10)

            # Create treeview for results
            columns = ('name', 'provider', 'category', 'type', 'rating')
            tree = ttk.Treeview(dialog, columns=columns, show='headings', height=10)

            column_labels = {
                'name': _t("integration_marketplace.columns.integration_name"),
                'provider': _t("integration_marketplace.columns.provider_name"),
                'category': _t("integration_marketplace.columns.category"),
                'type': _t("integration_marketplace.columns.integration_type"),
                'rating': _t("integration_marketplace.columns.rating")
            }

            for col in columns:
                tree.heading(col, text=column_labels[col])

            tree.column('name', width=200)
            tree.column('provider', width=150)
            tree.column('category', width=100)
            tree.column('type', width=100)
            tree.column('rating', width=70)

            for item in similar:
                tree.insert('', 'end', values=(
                    item[1], item[2], item[3], item[4], item[6] or _t("common.na")
                ))

            tree.pack(fill='both', expand=True, padx=10, pady=10)

            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error finding similar integrations: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to find similar integrations: {e}")

    def search_sync_logs(self):
        """Search logs by date range, status, or error message content"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.search_sync_logs"))
            dialog.geometry("500x350")
            dialog.transient(self.root)
            dialog.grab_set()

            # Date range
            ttk.Label(dialog, text="Start Date (YYYY-MM-DD):").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            ttk.Entry(dialog, textvariable=start_date_var, width=20).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="End Date (YYYY-MM-DD):").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
            ttk.Entry(dialog, textvariable=end_date_var, width=20).grid(row=1, column=1, padx=10, pady=5)

            # Status filter
            ttk.Label(dialog, text="Status:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            status_var = tk.StringVar(value='all')
            ttk.Combobox(dialog, textvariable=status_var,
                        values=['all', 'success', 'failed', 'running'],
                        width=18, state='readonly').grid(row=2, column=1, padx=10, pady=5)

            # Error message search
            ttk.Label(dialog, text="Error Contains:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            error_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=error_var, width=30).grid(row=3, column=1, padx=10, pady=5)

            def perform_search():
                try:
                    start_date = start_date_var.get()
                    end_date = end_date_var.get()
                    status = status_var.get()
                    error_text = error_var.get().strip()

                    # Clear existing items
                    for item in self.sync_tree.get_children():
                        self.sync_tree.delete(item)

                    with get_connection() as conn:
                        cursor = conn.cursor()

                        query = '''
                            SELECT log_id, install_id, sync_start_time, sync_end_time,
                                   sync_status, records_synced, errors_encountered
                            FROM integration_sync_logs
                            WHERE sync_start_time >= ? AND sync_start_time <= ?
                        '''
                        params = [start_date, end_date + ' 23:59:59']

                        if status != 'all':
                            query += ' AND sync_status = ?'
                            params.append(status)

                        if error_text:
                            query += ' AND error_details LIKE ?'
                            params.append(f'%{error_text}%')

                        query += ' ORDER BY sync_start_time DESC LIMIT 100'

                        cursor.execute(query, params)
                        logs = cursor.fetchall()

                    for log in logs:
                        self.sync_tree.insert('', 'end', values=(
                            log[0], log[1],
                            log[2][:19] if log[2] else 'N/A',
                            log[3][:19] if log[3] else 'N/A',
                            log[4] or _t("common.na"),
                            log[5] if log[5] is not None else 0,
                            log[6] if log[6] is not None else 0
                        ))

                    messagebox.showinfo("Search Results", f"Found {len(logs)} log entries")
                    dialog.destroy()

                except Exception as e:
                    logger.error(f"Error searching sync logs: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to search: {e}")

            ttk.Button(dialog, text="Search", command=perform_search).grid(row=4, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening search dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open search dialog: {e}")

    def advanced_filter_dialog(self):
        """Multi-criteria filter dialog with AND/OR logic"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.advanced_filter"))
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Advanced Filter Options", style='Title.TLabel').pack(pady=10)

            # Filter frame
            filter_frame = ttk.LabelFrame(dialog, text="Filter Criteria", padding=10)
            filter_frame.pack(fill='x', padx=10, pady=5)

            # Category
            ttk.Label(filter_frame, text="Category:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
            category_var = tk.StringVar()
            ttk.Combobox(filter_frame, textvariable=category_var,
                        values=['', 'LMS', 'SIS', 'CRM', 'Analytics', 'Communication', 'Storage'],
                        width=20).grid(row=0, column=1, padx=5, pady=5)

            # Type
            ttk.Label(filter_frame, text="Integration Type:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
            type_var = tk.StringVar()
            ttk.Combobox(filter_frame, textvariable=type_var,
                        values=['', 'API', 'OAuth', 'SAML', 'Database', 'Webhook'],
                        width=20).grid(row=1, column=1, padx=5, pady=5)

            # Provider
            ttk.Label(filter_frame, text="Provider Contains:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
            provider_var = tk.StringVar()
            ttk.Entry(filter_frame, textvariable=provider_var, width=22).grid(row=2, column=1, padx=5, pady=5)

            # Min Rating
            ttk.Label(filter_frame, text="Minimum Rating:").grid(row=3, column=0, padx=5, pady=5, sticky='w')
            rating_var = tk.StringVar()
            ttk.Spinbox(filter_frame, from_=0, to=5, textvariable=rating_var, width=20).grid(row=3, column=1, padx=5, pady=5)

            # Min Installs
            ttk.Label(filter_frame, text="Minimum Installs:").grid(row=4, column=0, padx=5, pady=5, sticky='w')
            installs_var = tk.StringVar(value='0')
            ttk.Entry(filter_frame, textvariable=installs_var, width=22).grid(row=4, column=1, padx=5, pady=5)

            # Official only
            official_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(filter_frame, text="Official Integrations Only",
                           variable=official_var).grid(row=5, column=0, columnspan=2, padx=5, pady=5)

            # Logic
            ttk.Label(filter_frame, text="Filter Logic:").grid(row=6, column=0, padx=5, pady=5, sticky='w')
            logic_var = tk.StringVar(value='AND')
            ttk.Radiobutton(filter_frame, text="AND (all criteria)", variable=logic_var,
                           value='AND').grid(row=6, column=1, padx=5, pady=2, sticky='w')
            ttk.Radiobutton(filter_frame, text="OR (any criteria)", variable=logic_var,
                           value='OR').grid(row=7, column=1, padx=5, pady=2, sticky='w')

            def apply_filter():
                try:
                    # Clear existing items
                    for item in self.catalog_tree.get_children():
                        self.catalog_tree.delete(item)

                    conditions = []
                    params = []

                    if category_var.get():
                        conditions.append("category = ?")
                        params.append(category_var.get())

                    if type_var.get():
                        conditions.append("integration_type = ?")
                        params.append(type_var.get())

                    if provider_var.get():
                        conditions.append("provider_name LIKE ?")
                        params.append(f'%{provider_var.get()}%')

                    if rating_var.get():
                        try:
                            min_rating = float(rating_var.get())
                            conditions.append("rating >= ?")
                            params.append(min_rating)
                        except ValueError:
                            pass

                    if installs_var.get():
                        try:
                            min_installs = int(installs_var.get())
                            conditions.append("install_count >= ?")
                            params.append(min_installs)
                        except ValueError:
                            pass

                    if official_var.get():
                        conditions.append("is_official = 1")

                    logic = ' AND ' if logic_var.get() == 'AND' else ' OR '

                    query = '''
                        SELECT integration_id, integration_name, provider_name, category,
                               integration_type, version, rating, install_count, is_official
                        FROM integration_catalog
                        WHERE is_active = 1
                    '''

                    if conditions:
                        query += ' AND (' + logic.join(conditions) + ')'

                    query += ' ORDER BY rating DESC, install_count DESC LIMIT 100'

                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        integrations = cursor.fetchall()

                    for integration in integrations:
                        is_official = _t("common.yes") if integration[8] else _t("common.no")
                        self.catalog_tree.insert('', 'end', values=(
                            integration[0], integration[1], integration[2], integration[3],
                            integration[4], integration[5], integration[6] or _t("common.na"),
                            integration[7] or 0, is_official
                        ))

                    messagebox.showinfo("Filter Results", f"Found {len(integrations)} integration(s)")
                    dialog.destroy()

                except Exception as e:
                    logger.error(f"Error applying filter: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to apply filter: {e}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text=_t("integration_marketplace.common.filter"), command=apply_filter).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            logger.error(f"Error opening advanced filter dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open dialog: {e}")
