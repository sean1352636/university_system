"""
Blockchain Credentials & Digital Badges GUI

Comprehensive GUI for managing blockchain credentials, digital badges,
badge issuances, verifications, and wallet management. Includes authentication,
error handling, and email notifications.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import logging
import traceback
import secrets
import hashlib

# Core infrastructure
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.constants import paths
from university_system.modules.shared.utils.activity_logger import log_activity

# Email service
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BlockchainCredentialsGUI:
    """Blockchain Credentials & Digital Badges Management GUI"""

    def __init__(self, root: tk.Tk, auth_system: Optional[UserAuth] = None):
        self.root = root
        self.root.title("Blockchain Credentials & Digital Badges")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Initialize authentication
        if auth_system:
            self.auth = auth_system
        else:
            self.auth = UserAuth()

        # Initialize database
        self.init_database()

        # Configure styles
        self.setup_styles()

        # Setup current user
        self.setup_current_user()

        # Check authentication status - require login through main system
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        if not auth.current_user:
            messagebox.showerror("Authentication Required",
                "Please log in through the main University System GUI.\n\n"
                "Run: python run.py --gui")
            self.root.destroy()
            return

        # Show main interface
        self.create_main_interface()

    def setup_current_user(self):
        """Setup current user from authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                logger.info(f"Blockchain GUI: Using authenticated user {self.auth.current_user.get('username', 'Unknown')}")
            else:
                logger.info("Blockchain GUI: No authenticated user - will show login screen")
        except Exception as e:
            logger.error(f"Error setting up current user: {e}")

    def init_database(self):
        """Initialize database tables"""
        try:
            from university_system.infrastructure.database.remaining_features_schema import BLOCKCHAIN_SCHEMA

            with transaction() as conn:
                conn.executescript(BLOCKCHAIN_SCHEMA)

            logger.info("Blockchain Credentials database tables initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            messagebox.showerror("Database Error", f"Failed to initialize database: {e}")

    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Header.TLabel',
                       font=('Arial', 16, 'bold'),
                       background='#2c3e50',
                       foreground='white',
                       padding=10)

        style.configure('Title.TLabel',
                       font=('Arial', 12, 'bold'),
                       background='#f0f0f0')

        style.configure('Action.TButton',
                       font=('Arial', 10),
                       padding=5)

        style.configure('Treeview',
                       font=('Arial', 9),
                       rowheight=25)

        style.configure('Treeview.Heading',
                       font=('Arial', 10, 'bold'))

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill='x', padx=10, pady=(10, 5))

        ttk.Label(header_frame, text="Blockchain Credentials & Digital Badges",
                 style='Header.TLabel').pack(side='left')

        # Return to homepage button
        ttk.Button(header_frame, text="← Return to Main Menu",
                  command=self.return_to_main_menu).pack(side='right', padx=5)

        if self.auth.current_user:
            user_info = f"Logged in as: {self.auth.current_user.get('username', 'User')} ({self.auth.current_user.get('role', 'user')})"
            ttk.Label(header_frame, text=user_info,
                     font=('Arial', 10)).pack(side='right', padx=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Create tabs
        self.create_credentials_tab()
        self.create_badges_tab()
        self.create_issuances_tab()
        self.create_verifications_tab()
        self.create_wallets_tab()
        self.create_templates_tab()

        # Refresh data
        self.refresh_all_data()

    def create_credentials_tab(self):
        """Create blockchain credentials tab"""
        cred_frame = ttk.Frame(self.notebook)
        self.notebook.add(cred_frame, text="🎓 Credentials")

        # Controls
        controls_frame = ttk.Frame(cred_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="➕ Issue Credential",
                  command=self.issue_credential, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_credentials, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="✅ Verify",
                  command=self.verify_credential, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="❌ Revoke",
                  command=self.revoke_credential, style='Action.TButton').pack(side='left', padx=5)

        # Search
        ttk.Label(controls_frame, text="Student ID:").pack(side='left', padx=5)
        self.cred_search_var = tk.StringVar()
        search_entry = ttk.Entry(controls_frame, textvariable=self.cred_search_var, width=15)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<Return>', lambda e: self.load_credentials())

        # Credentials tree
        tree_frame = ttk.Frame(cred_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('credential_id', 'student_id', 'credential_type', 'credential_name',
                  'issue_date', 'blockchain_hash', 'is_revoked')
        self.cred_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.cred_tree.heading(col, text=col.replace('_', ' ').title())
            self.cred_tree.column(col, width=120)

        # Adjust specific column widths
        self.cred_tree.column('blockchain_hash', width=200)
        self.cred_tree.column('credential_name', width=180)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.cred_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.cred_tree.xview)
        self.cred_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.cred_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_badges_tab(self):
        """Create digital badges catalog tab"""
        badges_frame = ttk.Frame(self.notebook)
        self.notebook.add(badges_frame, text="🏅 Badges")

        # Controls
        controls_frame = ttk.Frame(badges_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="➕ Create Badge",
                  command=self.create_badge, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_badges, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="✏️ Edit Selected",
                  command=self.edit_badge, style='Action.TButton').pack(side='left', padx=5)

        # Filter
        ttk.Label(controls_frame, text="Type:").pack(side='left', padx=5)
        self.badge_filter_var = tk.StringVar(value='all')
        ttk.Combobox(controls_frame, textvariable=self.badge_filter_var,
                    values=['all', 'skill', 'achievement', 'completion'],
                    width=12, state='readonly').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Filter",
                  command=self.load_badges, style='Action.TButton').pack(side='left', padx=5)

        # Badges tree
        tree_frame = ttk.Frame(badges_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('badge_id', 'badge_name', 'badge_type', 'criteria',
                  'issuer_name', 'is_active', 'created_at')
        self.badges_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.badges_tree.heading(col, text=col.replace('_', ' ').title())
            self.badges_tree.column(col, width=120)

        self.badges_tree.column('badge_name', width=150)
        self.badges_tree.column('criteria', width=200)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.badges_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.badges_tree.xview)
        self.badges_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.badges_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_issuances_tab(self):
        """Create badge issuances tab"""
        issuances_frame = ttk.Frame(self.notebook)
        self.notebook.add(issuances_frame, text="📜 Issuances")

        # Controls
        controls_frame = ttk.Frame(issuances_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="➕ Issue Badge",
                  command=self.issue_badge, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_issuances, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="❌ Revoke",
                  command=self.revoke_badge_issuance, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="📤 Export",
                  command=self.export_issuances, style='Action.TButton').pack(side='left', padx=5)

        # Search
        ttk.Label(controls_frame, text="Student ID:").pack(side='left', padx=5)
        self.issuance_search_var = tk.StringVar()
        search_entry = ttk.Entry(controls_frame, textvariable=self.issuance_search_var, width=15)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<Return>', lambda e: self.load_issuances())

        # Issuances tree
        tree_frame = ttk.Frame(issuances_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('issuance_id', 'badge_id', 'student_id', 'issued_date',
                  'blockchain_hash', 'expires_at', 'is_revoked')
        self.issuances_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.issuances_tree.heading(col, text=col.replace('_', ' ').title())
            self.issuances_tree.column(col, width=120)

        self.issuances_tree.column('blockchain_hash', width=200)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.issuances_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.issuances_tree.xview)
        self.issuances_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.issuances_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_verifications_tab(self):
        """Create credential verifications tab"""
        verify_frame = ttk.Frame(self.notebook)
        self.notebook.add(verify_frame, text="✅ Verifications")

        # Controls
        controls_frame = ttk.Frame(verify_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_verifications, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="📊 View Details",
                  command=self.view_verification_details, style='Action.TButton').pack(side='left', padx=5)

        # Verifications tree
        tree_frame = ttk.Frame(verify_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('verification_id', 'credential_id', 'badge_issuance_id',
                  'verifier_name', 'verifier_email', 'verified_date', 'verification_method')
        self.verify_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.verify_tree.heading(col, text=col.replace('_', ' ').title())
            self.verify_tree.column(col, width=120)

        self.verify_tree.column('verifier_name', width=150)
        self.verify_tree.column('verifier_email', width=180)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.verify_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.verify_tree.xview)
        self.verify_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.verify_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_wallets_tab(self):
        """Create blockchain wallets tab"""
        wallets_frame = ttk.Frame(self.notebook)
        self.notebook.add(wallets_frame, text="💳 Wallets")

        # Controls
        controls_frame = ttk.Frame(wallets_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="➕ Create Wallet",
                  command=self.create_wallet, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_wallets, style='Action.TButton').pack(side='left', padx=5)

        # Wallets tree
        tree_frame = ttk.Frame(wallets_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('wallet_id', 'user_id', 'wallet_address', 'blockchain_type',
                  'created_at')
        self.wallets_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.wallets_tree.heading(col, text=col.replace('_', ' ').title())
            self.wallets_tree.column(col, width=120)

        self.wallets_tree.column('wallet_address', width=300)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.wallets_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.wallets_tree.xview)
        self.wallets_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.wallets_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_templates_tab(self):
        """Create credential templates tab"""
        templates_frame = ttk.Frame(self.notebook)
        self.notebook.add(templates_frame, text="📋 Templates")

        # Controls
        controls_frame = ttk.Frame(templates_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="➕ Create Template",
                  command=self.create_template, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_templates, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="✏️ Edit Selected",
                  command=self.edit_template, style='Action.TButton').pack(side='left', padx=5)

        # Templates tree
        tree_frame = ttk.Frame(templates_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('template_id', 'template_name', 'credential_type', 'is_active')
        self.templates_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.templates_tree.heading(col, text=col.replace('_', ' ').title())
            self.templates_tree.column(col, width=150)

        self.templates_tree.column('template_name', width=250)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.templates_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.templates_tree.xview)
        self.templates_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.templates_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    # Data loading methods
    def refresh_all_data(self):
        """Refresh all tab data"""
        try:
            self.load_credentials()
            self.load_badges()
            self.load_issuances()
            self.load_verifications()
            self.load_wallets()
            self.load_templates()
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")
            messagebox.showerror("Error", f"Failed to refresh data: {e}")

    def load_credentials(self):
        """Load blockchain credentials"""
        try:
            for item in self.cred_tree.get_children():
                self.cred_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                search_student = self.cred_search_var.get().strip()
                if search_student:
                    cursor.execute('''
                        SELECT credential_id, student_id, credential_type, credential_name,
                               issue_date, blockchain_hash, is_revoked
                        FROM blockchain_credentials
                        WHERE student_id = ?
                        ORDER BY issue_date DESC
                    ''', (search_student,))
                else:
                    cursor.execute('''
                        SELECT credential_id, student_id, credential_type, credential_name,
                               issue_date, blockchain_hash, is_revoked
                        FROM blockchain_credentials
                        ORDER BY issue_date DESC
                        LIMIT 100
                    ''')

                credentials = cursor.fetchall()

                for cred in credentials:
                    status = 'Revoked' if cred[6] else 'Active'
                    self.cred_tree.insert('', 'end', values=(
                        cred[0], cred[1], cred[2], cred[3],
                        cred[4], cred[5], status
                    ))

            logger.info(f"Loaded {len(credentials)} credentials")

        except Exception as e:
            logger.error(f"Error loading credentials: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"Failed to load credentials: {e}")

    def load_badges(self):
        """Load digital badges"""
        try:
            for item in self.badges_tree.get_children():
                self.badges_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                badge_filter = self.badge_filter_var.get()
                if badge_filter == 'all':
                    cursor.execute('''
                        SELECT badge_id, badge_name, badge_type, criteria,
                               issuer_name, is_active, created_at
                        FROM digital_badges
                        ORDER BY created_at DESC
                    ''')
                else:
                    cursor.execute('''
                        SELECT badge_id, badge_name, badge_type, criteria,
                               issuer_name, is_active, created_at
                        FROM digital_badges
                        WHERE badge_type = ?
                        ORDER BY created_at DESC
                    ''', (badge_filter,))

                badges = cursor.fetchall()

                for badge in badges:
                    status = 'Active' if badge[5] else 'Inactive'
                    self.badges_tree.insert('', 'end', values=(
                        badge[0], badge[1], badge[2], badge[3],
                        badge[4], status, badge[6]
                    ))

            logger.info(f"Loaded {len(badges)} badges")

        except Exception as e:
            logger.error(f"Error loading badges: {e}")
            messagebox.showerror("Error", f"Failed to load badges: {e}")

    def load_issuances(self):
        """Load badge issuances"""
        try:
            for item in self.issuances_tree.get_children():
                self.issuances_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                search_student = self.issuance_search_var.get().strip()
                if search_student:
                    cursor.execute('''
                        SELECT issuance_id, badge_id, student_id, issued_date,
                               blockchain_hash, expires_at, is_revoked
                        FROM badge_issuances
                        WHERE student_id = ?
                        ORDER BY issued_date DESC
                    ''', (search_student,))
                else:
                    cursor.execute('''
                        SELECT issuance_id, badge_id, student_id, issued_date,
                               blockchain_hash, expires_at, is_revoked
                        FROM badge_issuances
                        ORDER BY issued_date DESC
                        LIMIT 100
                    ''')

                issuances = cursor.fetchall()

                for issuance in issuances:
                    status = 'Revoked' if issuance[6] else 'Active'
                    self.issuances_tree.insert('', 'end', values=(
                        issuance[0], issuance[1], issuance[2], issuance[3],
                        issuance[4], issuance[5] or 'No Expiry', status
                    ))

            logger.info(f"Loaded {len(issuances)} issuances")

        except Exception as e:
            logger.error(f"Error loading issuances: {e}")
            messagebox.showerror("Error", f"Failed to load issuances: {e}")

    def load_verifications(self):
        """Load credential verifications"""
        try:
            for item in self.verify_tree.get_children():
                self.verify_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT verification_id, credential_id, badge_issuance_id,
                           verifier_name, verifier_email, verified_date, verification_method
                    FROM credential_verifications
                    ORDER BY verified_date DESC
                    LIMIT 100
                ''')

                verifications = cursor.fetchall()

                for verify in verifications:
                    self.verify_tree.insert('', 'end', values=verify)

            logger.info(f"Loaded {len(verifications)} verifications")

        except Exception as e:
            logger.error(f"Error loading verifications: {e}")
            messagebox.showerror("Error", f"Failed to load verifications: {e}")

    def load_wallets(self):
        """Load blockchain wallets"""
        try:
            for item in self.wallets_tree.get_children():
                self.wallets_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT wallet_id, user_id, wallet_address, blockchain_type, created_at
                    FROM blockchain_wallets
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                wallets = cursor.fetchall()

                for wallet in wallets:
                    self.wallets_tree.insert('', 'end', values=wallet)

            logger.info(f"Loaded {len(wallets)} wallets")

        except Exception as e:
            logger.error(f"Error loading wallets: {e}")
            messagebox.showerror("Error", f"Failed to load wallets: {e}")

    def load_templates(self):
        """Load credential templates"""
        try:
            for item in self.templates_tree.get_children():
                self.templates_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT template_id, template_name, credential_type, is_active
                    FROM credential_templates
                    ORDER BY template_name
                ''')

                templates = cursor.fetchall()

                for template in templates:
                    status = 'Active' if template[3] else 'Inactive'
                    self.templates_tree.insert('', 'end', values=(
                        template[0], template[1], template[2], status
                    ))

            logger.info(f"Loaded {len(templates)} templates")

        except Exception as e:
            logger.error(f"Error loading templates: {e}")
            messagebox.showerror("Error", f"Failed to load templates: {e}")

    # Action methods
    def issue_credential(self):
        """Issue a new blockchain credential"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Issue Blockchain Credential")
            dialog.geometry("450x450")

            # Form fields
            ttk.Label(dialog, text="Student ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            student_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=student_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Credential Type:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            cred_type_var = tk.StringVar(value='degree')
            ttk.Combobox(dialog, textvariable=cred_type_var,
                        values=['degree', 'certificate', 'diploma', 'transcript'],
                        width=28, state='readonly').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Credential Name:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            cred_name_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=cred_name_var, width=30).grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Issue Date:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            issue_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
            ttk.Entry(dialog, textvariable=issue_date_var, width=30).grid(row=3, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Blockchain Type:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
            blockchain_var = tk.StringVar(value='ethereum')
            ttk.Combobox(dialog, textvariable=blockchain_var,
                        values=['ethereum', 'hyperledger', 'polygon'],
                        width=28, state='readonly').grid(row=4, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Metadata (JSON):").grid(row=5, column=0, padx=10, pady=5, sticky='nw')
            metadata_text = scrolledtext.ScrolledText(dialog, width=30, height=5)
            metadata_text.grid(row=5, column=1, padx=10, pady=5)
            metadata_text.insert('1.0', '{}')

            def save_credential():
                try:
                    student_id = student_id_var.get().strip()
                    cred_type = cred_type_var.get()
                    cred_name = cred_name_var.get().strip()
                    issue_date = issue_date_var.get().strip()
                    metadata = metadata_text.get('1.0', 'end-1c').strip()

                    if not student_id or not cred_name:
                        messagebox.showerror("Error", "Student ID and Credential Name are required")
                        return

                    # Validate JSON metadata
                    try:
                        json.loads(metadata)
                    except json.JSONDecodeError:
                        messagebox.showerror("Error", "Invalid JSON metadata")
                        return

                    # Generate blockchain hash (simulated)
                    data = f"{student_id}{cred_type}{cred_name}{issue_date}{datetime.now().isoformat()}"
                    blockchain_hash = hashlib.sha256(data.encode()).hexdigest()

                    # Generate blockchain address (simulated)
                    blockchain_address = f"0x{hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:40]}"

                    # Generate IPFS hash (simulated)
                    ipfs_hash = f"Qm{hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:44]}"

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO blockchain_credentials
                            (student_id, credential_type, credential_name, issue_date,
                             blockchain_hash, blockchain_address, ipfs_hash, metadata)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (student_id, cred_type, cred_name, issue_date,
                              blockchain_hash, blockchain_address, ipfs_hash, metadata))

                        credential_id = cursor.lastrowid

                    # Log activity
                    log_activity('create', 'blockchain_credential', credential_id,
                                details={'student_id': student_id, 'credential_type': cred_type})

                    # Send notification email
                    if EMAIL_AVAILABLE:
                        try:
                            send_email(
                                recipient_email=f"student{student_id}@university.edu",
                                subject="Blockchain Credential Issued",
                                body=f"Your {cred_type} credential has been issued on the blockchain.\n\n"
                                     f"Credential: {cred_name}\n"
                                     f"Issue Date: {issue_date}\n"
                                     f"Blockchain Hash: {blockchain_hash}\n"
                                     f"Blockchain Address: {blockchain_address}\n\n"
                                     f"You can verify this credential at any time using the blockchain hash."
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send notification email: {e}")

                    messagebox.showinfo("Success", f"Credential issued successfully!\n\n"
                                                    f"Credential ID: {credential_id}\n"
                                                    f"Blockchain Hash: {blockchain_hash}")
                    dialog.destroy()
                    self.load_credentials()

                except Exception as e:
                    logger.error(f"Error issuing credential: {e}\n{traceback.format_exc()}")
                    messagebox.showerror("Error", f"Failed to issue credential: {e}")

            ttk.Button(dialog, text="Issue Credential", command=save_credential).grid(
                row=6, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening issue dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def verify_credential(self):
        """Verify selected credential"""
        try:
            selected = self.cred_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a credential to verify")
                return

            values = self.cred_tree.item(selected[0])['values']
            credential_id = values[0]
            blockchain_hash = values[5]

            # Simulate blockchain verification
            verification_result = hashlib.sha256(blockchain_hash.encode()).hexdigest()

            # Log verification
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO credential_verifications
                    (credential_id, verifier_name, verified_date, verification_method)
                    VALUES (?, ?, ?, 'blockchain')
                ''', (credential_id, self.auth.current_user.get('username', 'Unknown'),
                      datetime.now().isoformat()))

            log_activity('verify', 'blockchain_credential', credential_id,
                        details={'blockchain_hash': blockchain_hash})

            messagebox.showinfo("Verification Result",
                              f"Credential Verified Successfully!\n\n"
                              f"Credential ID: {credential_id}\n"
                              f"Blockchain Hash: {blockchain_hash}\n"
                              f"Verification Hash: {verification_result[:32]}...\n"
                              f"Status: VALID")

            self.load_verifications()

        except Exception as e:
            logger.error(f"Error verifying credential: {e}")
            messagebox.showerror("Error", f"Failed to verify credential: {e}")

    def revoke_credential(self):
        """Revoke selected credential"""
        try:
            selected = self.cred_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a credential to revoke")
                return

            credential_id = self.cred_tree.item(selected[0])['values'][0]

            reason = tk.simpledialog.askstring("Revoke Credential",
                                              "Enter reason for revocation:")
            if not reason:
                return

            if messagebox.askyesno("Confirm", "Are you sure you want to revoke this credential?"):
                # Generate revocation hash
                revocation_hash = hashlib.sha256(
                    f"{credential_id}{reason}{datetime.now().isoformat()}".encode()
                ).hexdigest()

                with transaction() as conn:
                    cursor = conn.cursor()

                    cursor.execute('''
                        UPDATE blockchain_credentials
                        SET is_revoked = 1
                        WHERE credential_id = ?
                    ''', (credential_id,))

                    cursor.execute('''
                        INSERT INTO revoked_credentials
                        (credential_id, revoked_date, reason, revoked_by, blockchain_revocation_hash)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (credential_id, datetime.now().isoformat(), reason,
                          self.auth.current_user.get('user_id'),
                          revocation_hash))

                log_activity('revoke', 'blockchain_credential', credential_id,
                            details={'reason': reason})

                messagebox.showinfo("Success", "Credential revoked successfully")
                self.load_credentials()

        except Exception as e:
            logger.error(f"Error revoking credential: {e}")
            messagebox.showerror("Error", f"Failed to revoke credential: {e}")

    def create_badge(self):
        """Create a new digital badge"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Create Digital Badge")
            dialog.geometry("450x400")

            # Form fields
            ttk.Label(dialog, text="Badge Name:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            badge_name_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=badge_name_var, width=30).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Badge Type:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            badge_type_var = tk.StringVar(value='skill')
            ttk.Combobox(dialog, textvariable=badge_type_var,
                        values=['skill', 'achievement', 'completion'],
                        width=28, state='readonly').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Criteria:").grid(row=2, column=0, padx=10, pady=5, sticky='nw')
            criteria_text = scrolledtext.ScrolledText(dialog, width=30, height=4)
            criteria_text.grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Description:").grid(row=3, column=0, padx=10, pady=5, sticky='nw')
            description_text = scrolledtext.ScrolledText(dialog, width=30, height=4)
            description_text.grid(row=3, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Issuer Name:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
            issuer_var = tk.StringVar(value="University")
            ttk.Entry(dialog, textvariable=issuer_var, width=30).grid(row=4, column=1, padx=10, pady=5)

            def save_badge():
                try:
                    badge_name = badge_name_var.get().strip()
                    badge_type = badge_type_var.get()
                    criteria = criteria_text.get('1.0', 'end-1c').strip()
                    description = description_text.get('1.0', 'end-1c').strip()
                    issuer_name = issuer_var.get().strip()

                    if not badge_name or not criteria:
                        messagebox.showerror("Error", "Badge name and criteria are required")
                        return

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO digital_badges
                            (badge_name, description, criteria, issuer_name, badge_type, is_active)
                            VALUES (?, ?, ?, ?, ?, 1)
                        ''', (badge_name, description, criteria, issuer_name, badge_type))

                        badge_id = cursor.lastrowid

                    log_activity('create', 'digital_badge', badge_id,
                                details={'badge_name': badge_name, 'badge_type': badge_type})

                    messagebox.showinfo("Success", f"Badge created successfully!\nBadge ID: {badge_id}")
                    dialog.destroy()
                    self.load_badges()

                except Exception as e:
                    logger.error(f"Error creating badge: {e}")
                    messagebox.showerror("Error", f"Failed to create badge: {e}")

            ttk.Button(dialog, text="Create Badge", command=save_badge).grid(
                row=5, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening create badge dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def edit_badge(self):
        """Edit selected badge"""
        try:
            selected = self.badges_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a badge to edit")
                return

            values = self.badges_tree.item(selected[0])['values']
            badge_id = values[0]

            # Get full badge details
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT badge_name, description, criteria, issuer_name, badge_type, is_active
                    FROM digital_badges
                    WHERE badge_id = ?
                ''', (badge_id,))
                badge = cursor.fetchone()

            if not badge:
                messagebox.showerror("Error", "Badge not found")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit Badge - {badge[0]}")
            dialog.geometry("450x400")

            # Form fields with current values
            ttk.Label(dialog, text="Badge Name:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            badge_name_var = tk.StringVar(value=badge[0])
            ttk.Entry(dialog, textvariable=badge_name_var, width=30).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Badge Type:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            badge_type_var = tk.StringVar(value=badge[4])
            ttk.Combobox(dialog, textvariable=badge_type_var,
                        values=['skill', 'achievement', 'completion'],
                        width=28, state='readonly').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Criteria:").grid(row=2, column=0, padx=10, pady=5, sticky='nw')
            criteria_text = scrolledtext.ScrolledText(dialog, width=30, height=4)
            criteria_text.grid(row=2, column=1, padx=10, pady=5)
            criteria_text.insert('1.0', badge[2] or '')

            ttk.Label(dialog, text="Description:").grid(row=3, column=0, padx=10, pady=5, sticky='nw')
            description_text = scrolledtext.ScrolledText(dialog, width=30, height=4)
            description_text.grid(row=3, column=1, padx=10, pady=5)
            description_text.insert('1.0', badge[1] or '')

            ttk.Label(dialog, text="Active:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
            is_active_var = tk.BooleanVar(value=bool(badge[5]))
            ttk.Checkbutton(dialog, variable=is_active_var).grid(row=4, column=1, padx=10, pady=5, sticky='w')

            def save_changes():
                try:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE digital_badges
                            SET badge_name = ?, description = ?, criteria = ?,
                                badge_type = ?, is_active = ?
                            WHERE badge_id = ?
                        ''', (badge_name_var.get(), description_text.get('1.0', 'end-1c'),
                              criteria_text.get('1.0', 'end-1c'), badge_type_var.get(),
                              int(is_active_var.get()), badge_id))

                    log_activity('update', 'digital_badge', badge_id,
                                details={'badge_name': badge_name_var.get()})

                    messagebox.showinfo("Success", "Badge updated successfully")
                    dialog.destroy()
                    self.load_badges()

                except Exception as e:
                    logger.error(f"Error updating badge: {e}")
                    messagebox.showerror("Error", f"Failed to update badge: {e}")

            ttk.Button(dialog, text="Save Changes", command=save_changes).grid(
                row=5, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error editing badge: {e}")
            messagebox.showerror("Error", f"Failed to edit badge: {e}")

    def issue_badge(self):
        """Issue badge to student"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Issue Badge")
            dialog.geometry("400x350")

            # Form fields
            ttk.Label(dialog, text="Badge ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            badge_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=badge_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Student ID:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            student_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=student_id_var, width=30).grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Evidence URL:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            evidence_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=evidence_var, width=30).grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Expires At (Optional):").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            expires_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=expires_var, width=30).grid(row=3, column=1, padx=10, pady=5)
            ttk.Label(dialog, text="Format: YYYY-MM-DD", font=('Arial', 8)).grid(
                row=4, column=1, padx=10, sticky='w')

            def save_issuance():
                try:
                    badge_id = badge_id_var.get().strip()
                    student_id = student_id_var.get().strip()
                    evidence_url = evidence_var.get().strip()
                    expires_at = expires_var.get().strip() or None

                    if not badge_id or not student_id:
                        messagebox.showerror("Error", "Badge ID and Student ID are required")
                        return

                    # Generate blockchain hash
                    data = f"{badge_id}{student_id}{datetime.now().isoformat()}"
                    blockchain_hash = hashlib.sha256(data.encode()).hexdigest()

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO badge_issuances
                            (badge_id, student_id, issued_date, blockchain_hash,
                             evidence_url, expires_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (badge_id, student_id, datetime.now().isoformat(),
                              blockchain_hash, evidence_url, expires_at))

                        issuance_id = cursor.lastrowid

                    log_activity('create', 'badge_issuance', issuance_id,
                                details={'badge_id': badge_id, 'student_id': student_id})

                    # Send notification
                    if EMAIL_AVAILABLE:
                        try:
                            send_email(
                                recipient_email=f"student{student_id}@university.edu",
                                subject="Digital Badge Issued",
                                body=f"Congratulations! A digital badge has been issued to you.\n\n"
                                     f"Badge ID: {badge_id}\n"
                                     f"Issue Date: {datetime.now().strftime('%Y-%m-%d')}\n"
                                     f"Blockchain Hash: {blockchain_hash}\n\n"
                                     f"View your badge in your student portal."
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send notification: {e}")

                    messagebox.showinfo("Success", f"Badge issued successfully!\nIssuance ID: {issuance_id}")
                    dialog.destroy()
                    self.load_issuances()

                except Exception as e:
                    logger.error(f"Error issuing badge: {e}")
                    messagebox.showerror("Error", f"Failed to issue badge: {e}")

            ttk.Button(dialog, text="Issue Badge", command=save_issuance).grid(
                row=5, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening issue badge dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def revoke_badge_issuance(self):
        """Revoke badge issuance"""
        try:
            selected = self.issuances_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select an issuance to revoke")
                return

            issuance_id = self.issuances_tree.item(selected[0])['values'][0]

            reason = tk.simpledialog.askstring("Revoke Badge", "Enter reason for revocation:")
            if not reason:
                return

            if messagebox.askyesno("Confirm", "Are you sure you want to revoke this badge issuance?"):
                with transaction() as conn:
                    cursor = conn.cursor()

                    cursor.execute('''
                        UPDATE badge_issuances
                        SET is_revoked = 1
                        WHERE issuance_id = ?
                    ''', (issuance_id,))

                    cursor.execute('''
                        INSERT INTO revoked_credentials
                        (badge_issuance_id, revoked_date, reason, revoked_by)
                        VALUES (?, ?, ?, ?)
                    ''', (issuance_id, datetime.now().isoformat(), reason,
                          self.auth.current_user.get('user_id')))

                log_activity('revoke', 'badge_issuance', issuance_id, details={'reason': reason})

                messagebox.showinfo("Success", "Badge issuance revoked successfully")
                self.load_issuances()

        except Exception as e:
            logger.error(f"Error revoking badge issuance: {e}")
            messagebox.showerror("Error", f"Failed to revoke badge issuance: {e}")

    def export_issuances(self):
        """Export issuances to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT issuance_id, badge_id, student_id, issued_date,
                           blockchain_hash, expires_at, is_revoked
                    FROM badge_issuances
                    ORDER BY issued_date DESC
                ''')

                issuances = cursor.fetchall()

            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Issuance ID', 'Badge ID', 'Student ID', 'Issued Date',
                               'Blockchain Hash', 'Expires At', 'Is Revoked'])
                writer.writerows(issuances)

            messagebox.showinfo("Success", f"Issuances exported to {filename}")
            log_activity('export', 'badge_issuances', None,
                        details={'filename': filename, 'record_count': len(issuances)})

        except Exception as e:
            logger.error(f"Error exporting issuances: {e}")
            messagebox.showerror("Error", f"Failed to export issuances: {e}")

    def view_verification_details(self):
        """View verification details"""
        try:
            selected = self.verify_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a verification to view")
                return

            values = self.verify_tree.item(selected[0])['values']

            details = f"Verification Details:\n\n"
            details += f"Verification ID: {values[0]}\n"
            details += f"Credential ID: {values[1] or 'N/A'}\n"
            details += f"Badge Issuance ID: {values[2] or 'N/A'}\n"
            details += f"Verifier Name: {values[3]}\n"
            details += f"Verifier Email: {values[4]}\n"
            details += f"Verified Date: {values[5]}\n"
            details += f"Verification Method: {values[6]}"

            messagebox.showinfo("Verification Details", details)

        except Exception as e:
            logger.error(f"Error viewing verification: {e}")
            messagebox.showerror("Error", f"Failed to view verification: {e}")

    def create_wallet(self):
        """Create a new blockchain wallet"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Create Blockchain Wallet")
            dialog.geometry("400x250")

            ttk.Label(dialog, text="User ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            user_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=user_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Blockchain Type:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            blockchain_var = tk.StringVar(value='ethereum')
            ttk.Combobox(dialog, textvariable=blockchain_var,
                        values=['ethereum', 'hyperledger', 'polygon', 'cardano'],
                        width=28, state='readonly').grid(row=1, column=1, padx=10, pady=5)

            def save_wallet():
                try:
                    user_id = user_id_var.get().strip()
                    blockchain_type = blockchain_var.get()

                    if not user_id:
                        messagebox.showerror("Error", "User ID is required")
                        return

                    # Generate wallet address (simulated)
                    wallet_address = f"0x{hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:40]}"
                    public_key = hashlib.sha256(secrets.token_bytes(32)).hexdigest()

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO blockchain_wallets
                            (user_id, wallet_address, blockchain_type, public_key)
                            VALUES (?, ?, ?, ?)
                        ''', (user_id, wallet_address, blockchain_type, public_key))

                        wallet_id = cursor.lastrowid

                    log_activity('create', 'blockchain_wallet', wallet_id,
                                details={'user_id': user_id, 'blockchain_type': blockchain_type})

                    messagebox.showinfo("Success",
                                      f"Wallet created successfully!\n\n"
                                      f"Wallet ID: {wallet_id}\n"
                                      f"Wallet Address: {wallet_address}")
                    dialog.destroy()
                    self.load_wallets()

                except Exception as e:
                    logger.error(f"Error creating wallet: {e}")
                    messagebox.showerror("Error", f"Failed to create wallet: {e}")

            ttk.Button(dialog, text="Create Wallet", command=save_wallet).grid(
                row=2, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening create wallet dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def create_template(self):
        """Create credential template"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Create Credential Template")
            dialog.geometry("450x400")

            ttk.Label(dialog, text="Template Name:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            template_name_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=template_name_var, width=30).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Credential Type:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            cred_type_var = tk.StringVar(value='degree')
            ttk.Combobox(dialog, textvariable=cred_type_var,
                        values=['degree', 'certificate', 'diploma', 'transcript'],
                        width=28, state='readonly').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Fields (JSON):").grid(row=2, column=0, padx=10, pady=5, sticky='nw')
            fields_text = scrolledtext.ScrolledText(dialog, width=30, height=6)
            fields_text.grid(row=2, column=1, padx=10, pady=5)
            fields_text.insert('1.0', '["name", "date", "signature"]')

            def save_template():
                try:
                    template_name = template_name_var.get().strip()
                    cred_type = cred_type_var.get()
                    fields = fields_text.get('1.0', 'end-1c').strip()

                    if not template_name:
                        messagebox.showerror("Error", "Template name is required")
                        return

                    # Validate JSON
                    try:
                        json.loads(fields)
                    except json.JSONDecodeError:
                        messagebox.showerror("Error", "Invalid JSON format for fields")
                        return

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO credential_templates
                            (template_name, credential_type, fields)
                            VALUES (?, ?, ?)
                        ''', (template_name, cred_type, fields))

                        template_id = cursor.lastrowid

                    log_activity('create', 'credential_template', template_id,
                                details={'template_name': template_name})

                    messagebox.showinfo("Success", f"Template created successfully!\nTemplate ID: {template_id}")
                    dialog.destroy()
                    self.load_templates()

                except Exception as e:
                    logger.error(f"Error creating template: {e}")
                    messagebox.showerror("Error", f"Failed to create template: {e}")

            ttk.Button(dialog, text="Create Template", command=save_template).grid(
                row=3, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening create template dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def edit_template(self):
        """Edit selected template"""
        try:
            selected = self.templates_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a template to edit")
                return

            template_id = self.templates_tree.item(selected[0])['values'][0]

            # Get template details
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT template_name, credential_type, fields, is_active
                    FROM credential_templates
                    WHERE template_id = ?
                ''', (template_id,))
                template = cursor.fetchone()

            if not template:
                messagebox.showerror("Error", "Template not found")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit Template - {template[0]}")
            dialog.geometry("450x350")

            ttk.Label(dialog, text="Template Name:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            template_name_var = tk.StringVar(value=template[0])
            ttk.Entry(dialog, textvariable=template_name_var, width=30).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Active:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            is_active_var = tk.BooleanVar(value=bool(template[3]))
            ttk.Checkbutton(dialog, variable=is_active_var).grid(row=1, column=1, padx=10, pady=5, sticky='w')

            ttk.Label(dialog, text="Fields (JSON):").grid(row=2, column=0, padx=10, pady=5, sticky='nw')
            fields_text = scrolledtext.ScrolledText(dialog, width=30, height=6)
            fields_text.grid(row=2, column=1, padx=10, pady=5)
            fields_text.insert('1.0', template[2] or '')

            def save_changes():
                try:
                    fields = fields_text.get('1.0', 'end-1c').strip()

                    # Validate JSON
                    try:
                        json.loads(fields)
                    except json.JSONDecodeError:
                        messagebox.showerror("Error", "Invalid JSON format for fields")
                        return

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE credential_templates
                            SET template_name = ?, fields = ?, is_active = ?
                            WHERE template_id = ?
                        ''', (template_name_var.get(), fields, int(is_active_var.get()), template_id))

                    log_activity('update', 'credential_template', template_id,
                                details={'template_name': template_name_var.get()})

                    messagebox.showinfo("Success", "Template updated successfully")
                    dialog.destroy()
                    self.load_templates()

                except Exception as e:
                    logger.error(f"Error updating template: {e}")
                    messagebox.showerror("Error", f"Failed to update template: {e}")

            ttk.Button(dialog, text="Save Changes", command=save_changes).grid(
                row=3, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error editing template: {e}")
            messagebox.showerror("Error", f"Failed to edit template: {e}")

    def return_to_main_menu(self):
        """Return to main menu by closing the blockchain credentials window"""
        if messagebox.askyesno("Confirm", "Return to main menu?"):
            try:
                # Log the action
                if self.auth and self.auth.current_user:
                    log_activity('Closed Blockchain Credentials',
                               user=self.auth.current_user.get('username', 'Unknown'))

                # Close the window
                self.root.destroy()
                logger.info("Blockchain Credentials GUI closed")
            except Exception as e:
                logger.error(f"Error closing Blockchain Credentials GUI: {e}")
                self.root.destroy()


def launch_blockchain_credentials_gui(auth=None):
    """Launch the Blockchain Credentials & Digital Badges GUI"""
    try:
        root = tk.Tk()
        app = BlockchainCredentialsGUI(root, auth_system=auth)
        root.mainloop()
    except Exception as e:
        logger.error(f"Error launching Blockchain Credentials GUI: {e}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    launch_blockchain_credentials_gui()
