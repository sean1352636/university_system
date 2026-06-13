"""Tab creation mixin for IntegrationMarketplaceGUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, scrolledtext

from education_system.university_system.core.i18n import get_text as _t


class TabsMixin:
    """Mixin providing tab creation methods for the notebook interface."""

    def create_catalog_tab(self):
        """Create integration catalog tab"""
        catalog_frame = ttk.Frame(self.notebook)
        self.notebook.add(catalog_frame, text=_t("integration_marketplace.tabs.catalog"))

        # Controls
        controls_frame = ttk.Frame(catalog_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=_t("integration_marketplace.catalog.add_integration"),
                  command=self.add_integration).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.refresh"),
                  command=self.load_catalog).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.catalog.install_selected"),
                  command=self.install_integration, style='Accent.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.catalog.view_details"),
                  command=self.view_integration_details).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.catalog.find_similar"),
                  command=self.find_similar_integrations).pack(side='left', padx=5)

        # Second row of controls for search and filters
        search_frame = ttk.Frame(catalog_frame)
        search_frame.pack(fill='x', padx=10, pady=5)

        # Search box
        ttk.Label(search_frame, text=_t("integration_marketplace.common.search")).pack(side='left', padx=5)
        self.catalog_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.catalog_search_var, width=25)
        search_entry.pack(side='left', padx=5)
        ttk.Button(search_frame, text=_t("integration_marketplace.common.search_btn"),
                  command=self.search_catalog).pack(side='left', padx=5)

        # Category filter
        ttk.Label(search_frame, text=_t("integration_marketplace.catalog.category")).pack(side='left', padx=5)
        self.catalog_category_var = tk.StringVar(value='')
        ttk.Combobox(search_frame, textvariable=self.catalog_category_var,
                    values=['', 'LMS', 'SIS', 'CRM', 'Analytics', 'Communication', 'Storage'],
                    width=12, state='readonly').pack(side='left', padx=5)

        # Rating filter
        ttk.Label(search_frame, text=_t("integration_marketplace.catalog.min_rating")).pack(side='left', padx=5)
        self.catalog_rating_var = tk.StringVar(value='')
        ttk.Combobox(search_frame, textvariable=self.catalog_rating_var,
                    values=['', '1', '2', '3', '4', '5'],
                    width=5, state='readonly').pack(side='left', padx=5)

        ttk.Button(search_frame, text=_t("integration_marketplace.common.filter"),
                  command=self.load_catalog).pack(side='left', padx=5)
        ttk.Button(search_frame, text=_t("integration_marketplace.catalog.filter_by_rating"),
                  command=self.filter_by_rating).pack(side='left', padx=5)
        ttk.Button(search_frame, text=_t("integration_marketplace.catalog.compatible_only"),
                  command=self.filter_by_compatibility).pack(side='left', padx=5)
        ttk.Button(search_frame, text=_t("integration_marketplace.catalog.advanced_filter"),
                  command=self.advanced_filter_dialog).pack(side='left', padx=5)

        # Catalog tree
        tree_frame = ttk.Frame(catalog_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('integration_id', 'integration_name', 'provider_name', 'category',
                  'integration_type', 'version', 'rating', 'install_count', 'is_official')
        self.catalog_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        column_labels = {
            'integration_id': _t("integration_marketplace.columns.integration_id"),
            'integration_name': _t("integration_marketplace.columns.integration_name"),
            'provider_name': _t("integration_marketplace.columns.provider_name"),
            'category': _t("integration_marketplace.columns.category"),
            'integration_type': _t("integration_marketplace.columns.integration_type"),
            'version': _t("integration_marketplace.columns.version"),
            'rating': _t("integration_marketplace.columns.rating"),
            'install_count': _t("integration_marketplace.columns.install_count"),
            'is_official': _t("integration_marketplace.columns.is_official")
        }

        for col in columns:
            self.catalog_tree.heading(col, text=column_labels[col])
            self.catalog_tree.column(col, width=100)

        self.catalog_tree.column('integration_name', width=200)
        self.catalog_tree.column('provider_name', width=150)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.catalog_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.catalog_tree.xview)
        self.catalog_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.catalog_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Description panel
        desc_frame = ttk.LabelFrame(catalog_frame, text=_t("integration_marketplace.catalog.description"), padding=10)
        desc_frame.pack(fill='x', padx=10, pady=5)

        self.catalog_description = scrolledtext.ScrolledText(desc_frame, height=4, wrap=tk.WORD)
        self.catalog_description.pack(fill='both', expand=True)

        # Bind selection event
        self.catalog_tree.bind('<<TreeviewSelect>>', self.on_catalog_select)

    def create_installed_tab(self):
        """Create installed integrations tab"""
        installed_frame = ttk.Frame(self.notebook)
        self.notebook.add(installed_frame, text=_t("integration_marketplace.tabs.installed"))

        # Controls
        controls_frame = ttk.Frame(installed_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=_t("integration_marketplace.common.refresh"),
                  command=self.load_installed).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.installed.configure"),
                  command=self.configure_integration).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.installed.sync_now"),
                  command=self.sync_integration).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.installed.uninstall"),
                  command=self.uninstall_integration).pack(side='left', padx=5)

        # Status filter
        ttk.Label(controls_frame, text=_t("integration_marketplace.common.status")).pack(side='left', padx=5)
        self.installed_filter_var = tk.StringVar(value='active')
        ttk.Combobox(controls_frame, textvariable=self.installed_filter_var,
                    values=['all', 'active', 'inactive', 'error'],
                    width=10, state='readonly').pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.filter"),
                  command=self.load_installed).pack(side='left', padx=5)

        # Bulk operations frame
        bulk_frame = ttk.LabelFrame(installed_frame, text=_t("integration_marketplace.installed.bulk_operations"), padding=5)
        bulk_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(bulk_frame, text=_t("integration_marketplace.installed.bulk_install"),
                  command=self.bulk_install_integrations).pack(side='left', padx=5)
        ttk.Button(bulk_frame, text=_t("integration_marketplace.installed.bulk_uninstall"),
                  command=self.bulk_uninstall_integrations).pack(side='left', padx=5)
        ttk.Button(bulk_frame, text=_t("integration_marketplace.installed.bulk_enable"),
                  command=self.bulk_enable_integrations).pack(side='left', padx=5)
        ttk.Button(bulk_frame, text=_t("integration_marketplace.installed.bulk_disable"),
                  command=self.bulk_disable_integrations).pack(side='left', padx=5)
        ttk.Button(bulk_frame, text=_t("integration_marketplace.installed.bulk_sync"),
                  command=self.bulk_sync_integrations).pack(side='left', padx=5)

        # Scheduling & Automation frame
        scheduling_frame = ttk.LabelFrame(installed_frame, text=_t("integration_marketplace.installed.scheduling"), padding=5)
        scheduling_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(scheduling_frame, text=_t("integration_marketplace.installed.schedule_sync"),
                  command=self.schedule_sync).pack(side='left', padx=5)
        ttk.Button(scheduling_frame, text=_t("integration_marketplace.installed.view_scheduled"),
                  command=self.view_scheduled_tasks).pack(side='left', padx=5)
        ttk.Button(scheduling_frame, text=_t("integration_marketplace.installed.pause_syncs"),
                  command=self.pause_scheduled_syncs).pack(side='left', padx=5)
        ttk.Button(scheduling_frame, text=_t("integration_marketplace.installed.maintenance_window"),
                  command=self.set_maintenance_window).pack(side='left', padx=5)
        ttk.Button(scheduling_frame, text=_t("integration_marketplace.installed.retry_policy"),
                  command=self.configure_retry_policy).pack(side='left', padx=5)

        # Installed tree
        tree_frame = ttk.Frame(installed_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('install_id', 'integration_name', 'version_installed', 'installation_date',
                  'status', 'last_sync_date', 'sync_frequency', 'is_enabled')
        self.installed_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        column_labels = {
            'install_id': _t("integration_marketplace.columns.install_id"),
            'integration_name': _t("integration_marketplace.columns.integration_name"),
            'version_installed': _t("integration_marketplace.columns.version_installed"),
            'installation_date': _t("integration_marketplace.columns.installation_date"),
            'status': _t("integration_marketplace.columns.status"),
            'last_sync_date': _t("integration_marketplace.columns.last_sync_date"),
            'sync_frequency': _t("integration_marketplace.columns.sync_frequency"),
            'is_enabled': _t("integration_marketplace.columns.is_enabled")
        }

        for col in columns:
            self.installed_tree.heading(col, text=column_labels[col])
            self.installed_tree.column(col, width=120)

        self.installed_tree.column('integration_name', width=200)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.installed_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.installed_tree.xview)
        self.installed_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.installed_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_credentials_tab(self):
        """Create credentials management tab"""
        cred_frame = ttk.Frame(self.notebook)
        self.notebook.add(cred_frame, text=_t("integration_marketplace.tabs.credentials"))

        # Controls
        controls_frame = ttk.Frame(cred_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=_t("integration_marketplace.credentials.add"),
                  command=self.add_credentials).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.refresh"),
                  command=self.load_credentials).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.credentials.edit"),
                  command=self.edit_credentials).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.delete"),
                  command=self.delete_credentials).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.credentials.bulk_update"),
                  command=self.bulk_update_credentials).pack(side='left', padx=5)

        # Security & Credentials frame
        security_frame = ttk.LabelFrame(cred_frame, text=_t("integration_marketplace.credentials.security"), padding=5)
        security_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(security_frame, text=_t("integration_marketplace.credentials.rotate_api"),
                  command=self.rotate_api_credentials).pack(side='left', padx=5)
        ttk.Button(security_frame, text=_t("integration_marketplace.credentials.check_expiry"),
                  command=self.check_credential_expiry).pack(side='left', padx=5)
        ttk.Button(security_frame, text=_t("integration_marketplace.credentials.validate"),
                  command=self.validate_credentials).pack(side='left', padx=5)
        ttk.Button(security_frame, text=_t("integration_marketplace.credentials.encrypted_export"),
                  command=self.encrypt_export_credentials).pack(side='left', padx=5)
        ttk.Button(security_frame, text=_t("integration_marketplace.credentials.audit_access"),
                  command=self.audit_credential_access).pack(side='left', padx=5)
        ttk.Button(security_frame, text=_t("integration_marketplace.credentials.revoke_tokens"),
                  command=self.revoke_all_tokens).pack(side='left', padx=5)

        # Credentials tree
        tree_frame = ttk.Frame(cred_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('credential_id', 'install_id', 'credential_type', 'endpoint_url',
                  'created_at', 'token_expiry')
        self.cred_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        column_labels = {
            'credential_id': _t("integration_marketplace.columns.credential_id"),
            'install_id': _t("integration_marketplace.columns.install_id"),
            'credential_type': _t("integration_marketplace.columns.credential_type"),
            'endpoint_url': _t("integration_marketplace.columns.endpoint_url"),
            'created_at': _t("integration_marketplace.columns.created_at"),
            'token_expiry': _t("integration_marketplace.columns.token_expiry")
        }

        for col in columns:
            self.cred_tree.heading(col, text=column_labels[col])
            self.cred_tree.column(col, width=120)

        self.cred_tree.column('endpoint_url', width=250)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.cred_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.cred_tree.xview)
        self.cred_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.cred_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_sync_logs_tab(self):
        """Create sync logs tab"""
        sync_frame = ttk.Frame(self.notebook)
        self.notebook.add(sync_frame, text=_t("integration_marketplace.tabs.sync_logs"))

        # Controls
        controls_frame = ttk.Frame(sync_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=_t("integration_marketplace.common.refresh"),
                  command=self.load_sync_logs).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.sync_logs.view_details"),
                  command=self.view_sync_details).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.sync_logs.export_logs"),
                  command=self.export_sync_logs).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.sync_logs.search_logs"),
                  command=self.search_sync_logs).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.sync_logs.export_pdf"),
                  command=self.export_sync_report_pdf).pack(side='left', padx=5)

        # Status filter
        ttk.Label(controls_frame, text=_t("integration_marketplace.common.status")).pack(side='left', padx=5)
        self.sync_filter_var = tk.StringVar(value='all')
        ttk.Combobox(controls_frame, textvariable=self.sync_filter_var,
                    values=['all', 'success', 'failed', 'running'],
                    width=10, state='readonly').pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.filter"),
                  command=self.load_sync_logs).pack(side='left', padx=5)

        # Validation & Testing frame
        validation_frame = ttk.LabelFrame(sync_frame, text=_t("integration_marketplace.sync_logs.validation"), padding=5)
        validation_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(validation_frame, text=_t("integration_marketplace.sync_logs.test_connection"),
                  command=self.test_integration_connection).pack(side='left', padx=5)
        ttk.Button(validation_frame, text=_t("integration_marketplace.sync_logs.validate_mappings"),
                  command=self.validate_mapping_rules).pack(side='left', padx=5)
        ttk.Button(validation_frame, text=_t("integration_marketplace.sync_logs.dry_run"),
                  command=self.dry_run_sync).pack(side='left', padx=5)
        ttk.Button(validation_frame, text=_t("integration_marketplace.sync_logs.test_webhook"),
                  command=self.test_webhook_delivery).pack(side='left', padx=5)
        ttk.Button(validation_frame, text=_t("integration_marketplace.sync_logs.validate_config"),
                  command=self.validate_json_configuration).pack(side='left', padx=5)
        ttk.Button(validation_frame, text=_t("integration_marketplace.sync_logs.run_diagnostics"),
                  command=self.run_integration_diagnostics).pack(side='left', padx=5)

        # Sync logs tree
        tree_frame = ttk.Frame(sync_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('log_id', 'install_id', 'sync_start_time', 'sync_end_time',
                  'sync_status', 'records_synced', 'errors_encountered')
        self.sync_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        column_labels = {
            'log_id': _t("integration_marketplace.columns.log_id"),
            'install_id': _t("integration_marketplace.columns.install_id"),
            'sync_start_time': _t("integration_marketplace.columns.sync_start_time"),
            'sync_end_time': _t("integration_marketplace.columns.sync_end_time"),
            'sync_status': _t("integration_marketplace.columns.sync_status"),
            'records_synced': _t("integration_marketplace.columns.records_synced"),
            'errors_encountered': _t("integration_marketplace.columns.errors_encountered")
        }

        for col in columns:
            self.sync_tree.heading(col, text=column_labels[col])
            self.sync_tree.column(col, width=120)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.sync_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.sync_tree.xview)
        self.sync_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.sync_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_mappings_tab(self):
        """Create data mappings tab"""
        mappings_frame = ttk.Frame(self.notebook)
        self.notebook.add(mappings_frame, text=_t("integration_marketplace.tabs.mappings"))

        # Controls
        controls_frame = ttk.Frame(mappings_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=_t("integration_marketplace.mappings.add"),
                  command=self.add_mapping).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.refresh"),
                  command=self.load_mappings).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.mappings.edit"),
                  command=self.edit_mapping).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.delete"),
                  command=self.delete_mapping).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.mappings.export_excel"),
                  command=self.export_mappings_to_excel).pack(side='left', padx=5)

        # Data Mapping Tools frame
        mapping_tools_frame = ttk.LabelFrame(mappings_frame, text=_t("integration_marketplace.mappings.tools"), padding=5)
        mapping_tools_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(mapping_tools_frame, text=_t("integration_marketplace.mappings.auto_detect"),
                  command=self.auto_detect_mappings).pack(side='left', padx=5)
        ttk.Button(mapping_tools_frame, text=_t("integration_marketplace.mappings.preview"),
                  command=self.preview_transformation).pack(side='left', padx=5)
        ttk.Button(mapping_tools_frame, text=_t("integration_marketplace.mappings.duplicate"),
                  command=self.duplicate_mapping_set).pack(side='left', padx=5)
        ttk.Button(mapping_tools_frame, text=_t("integration_marketplace.mappings.import_template"),
                  command=self.import_mappings_from_template).pack(side='left', padx=5)

        # Mappings tree
        tree_frame = ttk.Frame(mappings_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('mapping_id', 'install_id', 'source_field', 'target_field',
                  'transformation_rule', 'is_active')
        self.mappings_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        column_labels = {
            'mapping_id': _t("integration_marketplace.columns.mapping_id"),
            'install_id': _t("integration_marketplace.columns.install_id"),
            'source_field': _t("integration_marketplace.columns.source_field"),
            'target_field': _t("integration_marketplace.columns.target_field"),
            'transformation_rule': _t("integration_marketplace.columns.transformation_rule"),
            'is_active': _t("integration_marketplace.columns.is_active")
        }

        for col in columns:
            self.mappings_tree.heading(col, text=column_labels[col])
            self.mappings_tree.column(col, width=120)

        self.mappings_tree.column('source_field', width=150)
        self.mappings_tree.column('target_field', width=150)
        self.mappings_tree.column('transformation_rule', width=200)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.mappings_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.mappings_tree.xview)
        self.mappings_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.mappings_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_webhooks_tab(self):
        """Create webhooks tab"""
        webhooks_frame = ttk.Frame(self.notebook)
        self.notebook.add(webhooks_frame, text=_t("integration_marketplace.tabs.webhooks"))

        # Controls
        controls_frame = ttk.Frame(webhooks_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=_t("integration_marketplace.webhooks.add"),
                  command=self.add_webhook).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.refresh"),
                  command=self.load_webhooks).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.webhooks.edit"),
                  command=self.edit_webhook).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.delete"),
                  command=self.delete_webhook).pack(side='left', padx=5)

        # Notifications & Alerts frame
        notifications_frame = ttk.LabelFrame(webhooks_frame, text=_t("integration_marketplace.webhooks.notifications"), padding=5)
        notifications_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(notifications_frame, text=_t("integration_marketplace.webhooks.configure_alerts"),
                  command=self.configure_alert_rules).pack(side='left', padx=5)
        ttk.Button(notifications_frame, text=_t("integration_marketplace.webhooks.subscribe"),
                  command=self.subscribe_to_notifications).pack(side='left', padx=5)
        ttk.Button(notifications_frame, text=_t("integration_marketplace.webhooks.view_history"),
                  command=self.view_notification_history).pack(side='left', padx=5)
        ttk.Button(notifications_frame, text=_t("integration_marketplace.webhooks.test_channel"),
                  command=self.test_notification_channel).pack(side='left', padx=5)

        # Webhooks tree
        tree_frame = ttk.Frame(webhooks_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('webhook_id', 'install_id', 'webhook_url', 'event_type',
                  'is_active', 'last_triggered_at', 'created_at')
        self.webhooks_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        column_labels = {
            'webhook_id': _t("integration_marketplace.columns.webhook_id"),
            'install_id': _t("integration_marketplace.columns.install_id"),
            'webhook_url': _t("integration_marketplace.columns.webhook_url"),
            'event_type': _t("integration_marketplace.columns.event_type"),
            'is_active': _t("integration_marketplace.columns.is_active"),
            'last_triggered_at': _t("integration_marketplace.columns.last_triggered_at"),
            'created_at': _t("integration_marketplace.columns.created_at")
        }

        for col in columns:
            self.webhooks_tree.heading(col, text=column_labels[col])
            self.webhooks_tree.column(col, width=120)

        self.webhooks_tree.column('webhook_url', width=300)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.webhooks_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.webhooks_tree.xview)
        self.webhooks_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.webhooks_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_analytics_tab(self):
        """Create usage analytics tab"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text=_t("integration_marketplace.tabs.analytics"))

        # Controls
        controls_frame = ttk.Frame(analytics_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=_t("integration_marketplace.common.refresh"),
                  command=self.load_analytics).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.analytics.view_summary"),
                  command=self.view_analytics_summary).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.export"),
                  command=self.export_analytics).pack(side='left', padx=5)

        # Date filter
        ttk.Label(controls_frame, text=_t("integration_marketplace.analytics.days")).pack(side='left', padx=5)
        self.analytics_days_var = tk.StringVar(value='30')
        ttk.Spinbox(controls_frame, from_=1, to=365, textvariable=self.analytics_days_var,
                   width=10).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("integration_marketplace.common.filter"),
                  command=self.load_analytics).pack(side='left', padx=5)

        # Reports & Dashboard frame
        reports_frame = ttk.LabelFrame(analytics_frame, text=_t("integration_marketplace.analytics.reports"), padding=5)
        reports_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(reports_frame, text=_t("integration_marketplace.analytics.dashboard"),
                  command=self.show_dashboard_overview).pack(side='left', padx=5)
        ttk.Button(reports_frame, text=_t("integration_marketplace.analytics.health_report"),
                  command=self.generate_health_report).pack(side='left', padx=5)
        ttk.Button(reports_frame, text=_t("integration_marketplace.analytics.error_analysis"),
                  command=self.show_error_analysis).pack(side='left', padx=5)
        ttk.Button(reports_frame, text=_t("integration_marketplace.analytics.usage_trend"),
                  command=self.generate_usage_trend_chart).pack(side='left', padx=5)
        ttk.Button(reports_frame, text=_t("integration_marketplace.analytics.api_statistics"),
                  command=self.show_api_call_statistics).pack(side='left', padx=5)
        ttk.Button(reports_frame, text=_t("integration_marketplace.analytics.compare_performance"),
                  command=self.compare_integration_performance).pack(side='left', padx=5)
        ttk.Button(reports_frame, text=_t("integration_marketplace.analytics.compliance_report"),
                  command=self.generate_compliance_report).pack(side='left', padx=5)

        # Import/Export frame
        import_export_frame = ttk.LabelFrame(analytics_frame, text=_t("integration_marketplace.analytics.import_export"), padding=5)
        import_export_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(import_export_frame, text=_t("integration_marketplace.analytics.export_catalog"),
                  command=self.export_catalog_to_json).pack(side='left', padx=5)
        ttk.Button(import_export_frame, text=_t("integration_marketplace.analytics.import_json"),
                  command=self.import_integrations_from_json).pack(side='left', padx=5)
        ttk.Button(import_export_frame, text=_t("integration_marketplace.analytics.export_config"),
                  command=self.export_configuration_bundle).pack(side='left', padx=5)
        ttk.Button(import_export_frame, text=_t("integration_marketplace.analytics.import_config"),
                  command=self.import_configuration_bundle).pack(side='left', padx=5)

        # Analytics tree
        tree_frame = ttk.Frame(analytics_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('analytics_id', 'install_id', 'metric_name', 'metric_value',
                  'measurement_date')
        self.analytics_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.analytics_tree.heading(col, text=col.replace('_', ' ').title())
            self.analytics_tree.column(col, width=150)

        self.analytics_tree.column('metric_name', width=200)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.analytics_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.analytics_tree.xview)
        self.analytics_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.analytics_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
