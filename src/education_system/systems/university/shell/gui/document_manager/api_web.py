import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.database.db import get_connection
except ImportError:
    from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


# The Document Manager has no REST API or web server of its own: no route
# under the unified API (``python -m education_system --university --api``)
# serves documents, and nothing checks a document API key. The windows below
# say so instead of pretending a server started or keys were issued.
NO_DOCUMENT_API = (
    "The Document Manager does not have a REST API or web server.\n\n"
    "The university's unified API has no document endpoints, so there is "
    "nothing to start, no API key it would accept and no API traffic to report."
)


class APIWebManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def _not_available(self, title, parent=None):
        messagebox.showinfo(title, _t('gui.shell.document_manager.api_web.dialogs.no_document_api',
                                      default=NO_DOCUMENT_API), parent=parent or self.root)

    def start_api_server(self):
        """Start the REST API server"""
        if not self.gui.ensure_login('admin'):
            return

        self._not_available(_t('gui.shell.document_manager.api_web.dialogs.start_api_server', default="Start API Server"))
        self.gui.log_event('view', 'api_server', details='Checked document API server (none exists)')

    def view_api_endpoints(self):
        """View available API endpoints"""
        if not self.gui.ensure_login():
            return

        # Create endpoints window
        endpoints_window = tk.Toplevel(self.root)
        endpoints_window.title(_t('gui.shell.document_manager.api_web.windows.api_endpoints', default="API Endpoints"))
        endpoints_window.geometry("1000x700")
        endpoints_window.transient(self.root)
        endpoints_window.grab_set()

        ttk.Label(endpoints_window, text=_t('gui.shell.document_manager.api_web.labels.available_rest_api_endpoints', default="Available REST API Endpoints"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        ttk.Label(endpoints_window,
                  text=_t('gui.shell.document_manager.api_web.labels.endpoints_not_served',
                          default="Design reference only: none of these endpoints is served yet. "
                                  "The Document Manager has no running API."),
                  foreground='#c0392b', wraplength=900).pack(pady=(0, 5))

        # Create notebook for different endpoint categories
        notebook = ttk.Notebook(endpoints_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Document endpoints
        doc_frame = ttk.Frame(notebook, padding=10)
        notebook.add(doc_frame, text=_t('gui.shell.document_manager.api_web.tabs.document_apis', default="Document APIs"))

        doc_text = tk.Text(doc_frame, wrap='word', font=("Courier", 9))
        doc_text.pack(fill='both', expand=True)

        doc_text.insert('1.0', """
DOCUMENT MANAGEMENT ENDPOINTS

GET /api/documents
    - List all documents (paginated)
    - Query params: page, limit, status, student_id
    - Response: JSON array of documents

GET /api/documents/{id}
    - Get specific document details
    - Response: JSON document object

POST /api/documents
    - Upload new document
    - Body: multipart/form-data with file and metadata
    - Response: Created document with ID

PUT /api/documents/{id}
    - Update document metadata
    - Body: JSON with fields to update
    - Response: Updated document

DELETE /api/documents/{id}
    - Delete document
    - Response: Success message

GET /api/documents/{id}/download
    - Download document file
    - Response: File stream

POST /api/documents/{id}/approve
    - Approve pending document
    - Response: Updated document
        """)
        doc_text.config(state='disabled')

        # Student endpoints
        student_frame = ttk.Frame(notebook, padding=10)
        notebook.add(student_frame, text=_t('gui.shell.document_manager.api_web.tabs.student_apis', default="Student APIs"))

        student_text = tk.Text(student_frame, wrap='word', font=("Courier", 9))
        student_text.pack(fill='both', expand=True)

        student_text.insert('1.0', """
STUDENT ENDPOINTS

GET /api/students/{id}/documents
    - Get all documents for a student
    - Query params: status, type
    - Response: JSON array of documents

POST /api/students/{id}/upload
    - Upload document for student
    - Body: multipart/form-data
    - Response: Created document

GET /api/students/{id}/compliance
    - Check student compliance status
    - Response: Compliance report

GET /api/students/{id}/notifications
    - Get student notifications
    - Response: JSON array of notifications
        """)
        student_text.config(state='disabled')

        # System endpoints
        system_frame = ttk.Frame(notebook, padding=10)
        notebook.add(system_frame, text=_t('gui.shell.document_manager.api_web.tabs.system_apis', default="System APIs"))

        system_text = tk.Text(system_frame, wrap='word', font=("Courier", 9))
        system_text.pack(fill='both', expand=True)

        system_text.insert('1.0', """
SYSTEM ENDPOINTS

GET /api/stats
    - Get system statistics
    - Response: JSON with counts and metrics

GET /api/reports/compliance
    - Generate compliance report
    - Query params: format (json, csv, pdf)
    - Response: Report data

POST /api/search
    - Advanced document search
    - Body: JSON with search criteria
    - Response: Search results

GET /api/health
    - Health check endpoint
    - Response: Server status

GET /api/version
    - Get API version information
    - Response: Version details
        """)
        system_text.config(state='disabled')

        ttk.Button(endpoints_window, text=_t('gui.shell.document_manager.api_web.buttons.close', default="Close"),
                  command=endpoints_window.destroy).pack(pady=10)

        self.gui.log_event('view', 'api_endpoints', details='Viewed API documentation')

    def api_keys_management(self):
        """Manage API keys and access tokens"""
        if not self.gui.ensure_login('admin'):
            return

        # Create API keys window
        keys_window = tk.Toplevel(self.root)
        keys_window.title(_t('gui.shell.document_manager.api_web.windows.api_keys_management', default="API Keys Management"))
        keys_window.geometry("900x600")
        keys_window.transient(self.root)
        keys_window.grab_set()

        ttk.Label(keys_window, text=_t('gui.shell.document_manager.api_web.labels.api_keys_management', default="API Keys Management"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Keys list
        tree_frame = ttk.Frame(keys_window)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        tree = ttk.Treeview(tree_frame,
                           columns=('Key', 'Name', 'Created', 'Expires', 'Permissions', 'Status'),
                           show='headings', height=15)
        tree.heading('Key', text=_t('gui.shell.document_manager.api_web.headings.api_key', default='API Key'))
        tree.heading('Name', text=_t('gui.shell.document_manager.api_web.headings.key_name', default='Key Name'))
        tree.heading('Created', text=_t('gui.shell.document_manager.api_web.headings.created_date', default='Created Date'))
        tree.heading('Expires', text=_t('gui.shell.document_manager.api_web.headings.expiry_date', default='Expiry Date'))
        tree.heading('Permissions', text=_t('gui.shell.document_manager.api_web.headings.permissions', default='Permissions'))
        tree.heading('Status', text=_t('gui.shell.document_manager.api_web.headings.status', default='Status'))

        tree.column('Key', width=150)
        tree.column('Name', width=120)
        tree.column('Created', width=100)
        tree.column('Expires', width=100)
        tree.column('Permissions', width=120)
        tree.column('Status', width=80)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # No document API accepts keys, so none is listed or issued here.
        notice = ttk.Label(keys_window,
                           text=_t('gui.shell.document_manager.api_web.labels.no_api_keys',
                                   default="No API keys: the Document Manager has no API that accepts them, "
                                           "so issuing one would give a credential that opens nothing."),
                           foreground='gray', wraplength=860)
        notice.pack(pady=(0, 5))

        # Button frame
        button_frame = ttk.Frame(keys_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        def generate_new_key():
            self._not_available(_t('gui.shell.document_manager.api_web.dialogs.generate_api_key', default="Generate API Key"),
                                parent=keys_window)

        def revoke_selected():
            if not tree.selection():
                messagebox.showinfo(_t('gui.shell.document_manager.api_web.dialogs.revoke', default="Revoke"),
                                    _t('gui.shell.document_manager.api_web.dialogs.no_keys_to_revoke',
                                       default="There are no document API keys to revoke."),
                                    parent=keys_window)

        ttk.Button(button_frame, text=_t('gui.shell.document_manager.api_web.buttons.generate_new_key', default="Generate New Key"),
                  command=generate_new_key).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.api_web.buttons.revoke_selected', default="Revoke Selected"),
                  command=revoke_selected).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.api_web.buttons.close', default="Close"),
                  command=keys_window.destroy).pack(side='right', padx=5)

    def api_usage_statistics(self):
        """View API usage statistics"""
        if not self.gui.ensure_login('admin'):
            return

        # Create statistics window
        stats_window = tk.Toplevel(self.root)
        stats_window.title(_t('gui.shell.document_manager.api_web.windows.api_usage_statistics', default="API Usage Statistics"))
        stats_window.geometry("1000x700")
        stats_window.transient(self.root)
        stats_window.grab_set()

        ttk.Label(stats_window, text=_t('gui.shell.document_manager.api_web.labels.api_usage_statistics', default="API Usage Statistics"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Stats cards
        cards_frame = ttk.Frame(stats_window)
        cards_frame.pack(fill='x', padx=10, pady=5)

        # Real figures: API calls are whatever the audit log recorded with an
        # "API..." action (the same source the console Document Manager reads).
        total = today = month = 0
        daily, by_endpoint = [], []
        error = None
        try:
            with get_connection() as conn:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                "AND name = 'audit_log'").fetchone():
                    total, today, month = conn.execute("""
                        SELECT COUNT(*),
                               COALESCE(SUM(date(timestamp) = date('now')), 0),
                               COALESCE(SUM(strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')), 0)
                        FROM audit_log WHERE action LIKE 'API%'
                    """).fetchone()
                    daily = conn.execute("""
                        SELECT date(timestamp), COUNT(*) FROM audit_log
                        WHERE action LIKE 'API%' AND timestamp >= date('now', '-6 days')
                        GROUP BY date(timestamp) ORDER BY date(timestamp)
                    """).fetchall()
                    by_endpoint = conn.execute("""
                        SELECT COALESCE(table_name, action), COUNT(*) FROM audit_log
                        WHERE action LIKE 'API%' GROUP BY 1 ORDER BY 2 DESC LIMIT 5
                    """).fetchall()
        except Exception as exc:
            error = exc

        stats = [
            ("Total Requests", f"{total:,}", "#3498db"),
            ("Today", f"{today:,}", "#27ae60"),
            ("This Month", f"{month:,}", "#f39c12"),
            ("Avg Response Time", "Not recorded", "#9b59b6")
        ]

        for title, value, color in stats:
            card = tk.Frame(cards_frame, bg=color, relief='raised', bd=2)
            card.pack(side='left', fill='both', expand=True, padx=5)

            tk.Label(card, text=value, font=("Arial", 20, "bold"),
                    bg=color, fg='white').pack(pady=(10, 0))
            tk.Label(card, text=title, font=("Arial", 9),
                    bg=color, fg='white').pack(pady=(0, 10))

        chart_frame = ttk.LabelFrame(stats_window, text=_t('gui.shell.document_manager.api_web.labels.request_volume_last_7_days', default="Request Volume (Last 7 Days)"), padding=10)
        chart_frame.pack(fill='both', expand=True, padx=10, pady=5)

        chart_text = tk.Text(chart_frame, height=15, font=("Courier", 9))
        chart_text.pack(fill='both', expand=True)

        if error is not None:
            body = f"Could not read the audit log: {error}"
        elif not total:
            body = ("No API requests have been recorded.\n\n" + NO_DOCUMENT_API)
        else:
            peak = max(c for _d, c in daily) if daily else 0
            lines = ["API Request Volume (Last 7 Days)", ""]
            for day, count in daily:
                bar = "\u2588" * (int(count / peak * 30) if peak else 0)
                lines.append(f"{day}  {bar}  {count:,} requests")
            if not daily:
                lines.append("No requests in the last 7 days.")
            lines += ["", "Top Endpoints:"]
            for i, (endpoint, count) in enumerate(by_endpoint, 1):
                lines.append(f"{i}. {endpoint} - {count:,} requests ({count / total * 100:.0f}%)")
            body = "\n".join(lines)
        chart_text.insert('1.0', body)
        chart_text.config(state='disabled')

        ttk.Button(stats_window, text=_t('gui.shell.document_manager.api_web.buttons.close', default="Close"),
                  command=stats_window.destroy).pack(pady=10)

        self.gui.log_event('view', 'api_usage_stats', details='Viewed API usage statistics')

    def api_documentation(self):
        """Open API documentation in browser"""
        self._not_available(_t('gui.shell.document_manager.api_web.dialogs.api_documentation', default="API Documentation"))
        self.gui.log_event('view', 'api_documentation', details='Checked document API docs (no API exists)')

    def start_web_server(self):
        """Start the web interface server"""
        if not self.gui.ensure_login('admin'):
            return

        self._not_available(_t('gui.shell.document_manager.api_web.dialogs.start_web_server', default="Start Web Server"))
        self.gui.log_event('view', 'web_server', details='Checked document web server (none exists)')

    def web_interface_settings(self):
        """Configure web interface settings"""
        if not self.gui.ensure_login('admin'):
            return

        # Create settings window
        settings_window = tk.Toplevel(self.root)
        settings_window.title(_t('gui.shell.document_manager.api_web.windows.web_interface_settings', default="Web Interface Settings"))
        settings_window.geometry("700x650")
        settings_window.transient(self.root)
        settings_window.grab_set()

        ttk.Label(settings_window, text=_t('gui.shell.document_manager.api_web.labels.web_interface_configuration', default="Web Interface Configuration"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        saved = self._load_web_settings()

        ttk.Label(settings_window,
                  text=_t('gui.shell.document_manager.api_web.labels.web_settings_stored_only',
                          default="These settings are saved for when a document web interface exists; "
                                  "none is running today."),
                  foreground='gray', wraplength=640).pack(pady=(0, 5))

        # Create notebook
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Server settings
        server_frame = ttk.Frame(notebook, padding=10)
        notebook.add(server_frame, text=_t('gui.shell.document_manager.api_web.tabs.server', default="Server"))

        settings_form = ttk.Frame(server_frame)
        settings_form.pack(fill='both', expand=True)

        ttk.Label(settings_form, text=_t('gui.shell.document_manager.api_web.labels.server_port', default="Server Port:")).grid(row=0, column=0, sticky='w', pady=5)
        port_entry = ttk.Entry(settings_form, width=30)
        port_entry.insert(0, str(saved.get('port', "8080")))
        port_entry.grid(row=0, column=1, sticky='ew', pady=5)

        ttk.Label(settings_form, text=_t('gui.shell.document_manager.api_web.labels.host', default="Host:")).grid(row=1, column=0, sticky='w', pady=5)
        host_entry = ttk.Entry(settings_form, width=30)
        host_entry.insert(0, str(saved.get('host', "localhost")))
        host_entry.grid(row=1, column=1, sticky='ew', pady=5)

        debug_var = tk.BooleanVar(value=bool(saved.get('debug', False)))
        ttk.Checkbutton(settings_form, text=_t('gui.shell.document_manager.api_web.buttons.debug_mode_development_only', default="Debug Mode (Development only)"),
                       variable=debug_var).grid(row=2, column=0, columnspan=2, sticky='w', pady=5)

        auto_reload_var = tk.BooleanVar(value=bool(saved.get('auto_reload', False)))
        ttk.Checkbutton(settings_form, text=_t('gui.shell.document_manager.api_web.buttons.auto_reload_on_file_changes', default="Auto-reload on file changes"),
                       variable=auto_reload_var).grid(row=3, column=0, columnspan=2, sticky='w', pady=5)

        settings_form.columnconfigure(1, weight=1)

        # Features settings
        features_frame = ttk.Frame(notebook, padding=10)
        notebook.add(features_frame, text=_t('gui.shell.document_manager.api_web.tabs.features', default="Features"))

        feature_vars = {}
        features = [
            ("Enable Student Portal", True),
            ("Enable Admin Dashboard", True),
            ("Enable Document Upload", True),
            ("Enable Real-time Notifications", True),
            ("Enable Mobile Responsive Design", True),
            ("Enable Dark Mode", False),
            ("Enable Multi-language Support", False),
            ("Enable SSO/OAuth Login", False)
        ]

        for feature_text, default_value in features:
            var = tk.BooleanVar(value=bool(saved.get('features', {}).get(feature_text, default_value)))
            feature_vars[feature_text] = var
            ttk.Checkbutton(features_frame, text=feature_text,
                           variable=var).pack(anchor='w', pady=5)

        # Security settings
        security_frame = ttk.Frame(notebook, padding=10)
        notebook.add(security_frame, text=_t('gui.shell.document_manager.api_web.tabs.security', default="Security"))

        ttk.Label(security_frame, text=_t('gui.shell.document_manager.api_web.labels.security_configuration', default="Security Configuration"),
                 font=("Arial", 11, "bold")).pack(pady=5)

        security_vars = {}
        security_options = [
            ("Enable HTTPS", False),
            ("Require Authentication", True),
            ("Enable CSRF Protection", True),
            ("Enable Rate Limiting", True),
            ("Enable Session Timeout (30 min)", True),
            ("Log All Access Attempts", True)
        ]

        for option_text, default_value in security_options:
            var = tk.BooleanVar(value=bool(saved.get('security', {}).get(option_text, default_value)))
            security_vars[option_text] = var
            ttk.Checkbutton(security_frame, text=option_text,
                           variable=var).pack(anchor='w', pady=5)

        def save_settings():
            port = port_entry.get().strip()
            if not port.isdigit() or not 1 <= int(port) <= 65535:
                messagebox.showerror(_t('gui.shell.document_manager.api_web.dialogs.error', default="Error"),
                                     _t('gui.shell.document_manager.api_web.dialogs.port_invalid',
                                        default="The port must be a number from 1 to 65535."),
                                     parent=settings_window)
                return
            settings = {
                'port': int(port), 'host': host_entry.get().strip() or 'localhost',
                'debug': debug_var.get(), 'auto_reload': auto_reload_var.get(),
                'features': {k: v.get() for k, v in feature_vars.items()},
                'security': {k: v.get() for k, v in security_vars.items()},
            }
            try:
                self._save_web_settings(settings)
            except Exception as exc:
                messagebox.showerror(_t('gui.shell.document_manager.api_web.dialogs.error', default="Error"),
                                     f"Could not save the settings: {exc}", parent=settings_window)
                return
            messagebox.showinfo(_t('gui.shell.document_manager.api_web.dialogs.settings_saved', default="Settings Saved"),
                                _t('gui.shell.document_manager.api_web.dialogs.web_interface_settings_saved',
                                   default="Web interface settings saved."), parent=settings_window)

            self.gui.log_event('update', 'web_interface_settings',
                          details='Updated web interface configuration')

            settings_window.destroy()

        # Button frame
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.document_manager.api_web.buttons.save_settings', default="Save Settings"),
                  command=save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.api_web.buttons.cancel', default="Cancel"),
                  command=settings_window.destroy).pack(side='right', padx=5)

    _WEB_SETTINGS_KEY = 'document_web_interface_settings'

    def _load_web_settings(self):
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT setting_value FROM system_settings WHERE key = ?",
                                   (self._WEB_SETTINGS_KEY,)).fetchone()
            return json.loads(row[0]) if row and row[0] else {}
        except Exception:
            logger.debug("No saved web interface settings", exc_info=True)
            return {}

    def _save_web_settings(self, settings):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rows = [(self._WEB_SETTINGS_KEY, json.dumps(settings), 'Document Manager web interface settings'),
                # The console Document Manager reads host/port by these names.
                ('web_interface_host', settings['host'], 'Document web interface host'),
                ('web_interface_port', str(settings['port']), 'Document web interface port')]
        with get_connection() as conn:
            for name, value, description in rows:
                conn.execute(
                    "INSERT OR REPLACE INTO system_settings "
                    "(key, value, description, setting_name, setting_value, updated_date) "
                    "VALUES (?, ?, ?, ?, ?, ?)", (name, value, description, name, value, now))
            conn.commit()

    def generate_mobile_interface(self):
        """Install the bundled mobile-responsive document interface files."""
        from pathlib import Path
        from education_system import paths
        source = Path(__file__).resolve().parents[3] / "assets" / "web" / "mobile"
        destination = Path(paths.UNIVERSITY_DATA_DIR) / "document_manager" / "web" / "mobile"
        try:
            assets = [p for p in source.iterdir() if p.is_file()]
            if not assets:
                raise FileNotFoundError(f"No mobile interface files in {source}")
            destination.mkdir(parents=True, exist_ok=True)
            for asset in assets:
                (destination / asset.name).write_bytes(asset.read_bytes())
        except Exception as exc:
            messagebox.showerror(_t('gui.shell.document_manager.api_web.dialogs.mobile_interface', default="Mobile Interface"),
                                 f"Could not generate the mobile interface: {exc}", parent=self.root)
            return

        messagebox.showinfo(_t('gui.shell.document_manager.api_web.dialogs.mobile_interface', default="Mobile Interface"),
                            f"Mobile interface files ({len(assets)}) written to:\n{destination}\n\n"
                            "They are static files; no web server is serving them yet.",
                            parent=self.root)

        self.gui.log_event('generate', 'mobile_interface',
                      details=f'Generated mobile interface ({len(assets)} files) in {destination}')

    def mobile_app_qr_code(self):
        """Generate QR code for mobile app access"""
        if not self.gui.ensure_login():
            return

        # Create QR code window
        qr_window = tk.Toplevel(self.root)
        qr_window.title(_t('gui.shell.document_manager.api_web.windows.mobile_app_access', default="Mobile App Access"))
        qr_window.geometry("500x600")
        qr_window.transient(self.root)
        qr_window.grab_set()

        ttk.Label(qr_window, text=_t('gui.shell.document_manager.api_web.labels.mobile_app_access', default="Mobile App Access"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # The address comes from the saved web interface settings.
        saved = self._load_web_settings()
        url = f"http://{saved.get('host', 'localhost')}:{saved.get('port', 8080)}/mobile"

        qr_frame = tk.Frame(qr_window, bg='white', relief='solid', bd=2)
        qr_frame.pack(padx=20, pady=20)

        canvas = tk.Canvas(qr_frame, width=300, height=300, bg='white')
        canvas.pack(padx=20, pady=20)

        try:
            import qrcode
            qr = qrcode.QRCode(border=0)
            qr.add_data(url)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            cell = 300 / len(matrix)
            for y, row in enumerate(matrix):
                for x, dark in enumerate(row):
                    if dark:
                        canvas.create_rectangle(x * cell, y * cell, (x + 1) * cell, (y + 1) * cell,
                                                fill='black', outline='black')
            scan_text = _t('gui.shell.document_manager.api_web.labels.scan_with_your_mobile_device', default="Scan with your mobile device")
        except ImportError:
            canvas.create_text(150, 150, width=260, justify='center',
                               text="QR codes need the 'qrcode' package, which is not installed.")
            scan_text = ""

        ttk.Label(qr_window, text=scan_text, font=("Arial", 11)).pack()
        ttk.Label(qr_window,
                  text=_t('gui.shell.document_manager.api_web.labels.mobile_not_served',
                          default="No document web server is running, so this address does not answer yet."),
                  foreground='gray', wraplength=440).pack(pady=(5, 0))

        url_frame = ttk.Frame(qr_window)
        url_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(url_frame, text=_t('gui.shell.document_manager.api_web.labels.or_visit', default="Or visit:")).pack()
        url_text = tk.Text(url_frame, height=2, width=40)
        url_text.insert('1.0', url)
        url_text.config(state='disabled')
        url_text.pack(pady=5)

        def copy_url():
            qr_window.clipboard_clear()
            qr_window.clipboard_append(url)
            messagebox.showinfo(_t('gui.shell.document_manager.api_web.dialogs.copied', default="Copied"), _t('gui.shell.document_manager.api_web.dialogs.url_copied_to_clipboard', default="URL copied to clipboard"),
                                parent=qr_window)

        ttk.Button(qr_window, text=_t('gui.shell.document_manager.api_web.buttons.copy_url', default="Copy URL"),
                  command=copy_url).pack(pady=5)

        ttk.Button(qr_window, text=_t('gui.shell.document_manager.api_web.buttons.close', default="Close"),
                  command=qr_window.destroy).pack(pady=10)

        self.gui.log_event('generate', 'mobile_qr_code',
                      details='Generated mobile app QR code')
