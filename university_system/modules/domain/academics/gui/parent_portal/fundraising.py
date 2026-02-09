from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from .base import ParentPortalGUI

def donate_to_campaign(self):
    """Make a donation to fundraising campaign"""
    dialog = DonationDialog(self.root, self.children)
    if dialog.result:
        campaign, amount, child = dialog.result
        messagebox.showinfo(_t("common.success"), _t("parent.fundraising.donation_thank_you", amount=f"{amount:.2f}", campaign=campaign))
ParentPortalGUI.donate_to_campaign = donate_to_campaign

def show_fundraising_interface(self):
    """Show fundraising interface"""
    self.clear_content()
    self.update_status(_t("parent.fundraising.title"))

    title = ttk.Label(self.content_frame, text=_t("parent.fundraising.campaigns_title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Active campaigns
    campaigns_frame = ttk.LabelFrame(self.content_frame, text=_t("parent.fundraising.active_campaigns"), padding=15)
    campaigns_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='fundraising_campaigns'
        """)

        if cursor.fetchone():
            # Use correct column: status instead of is_active
            cursor.execute("""
            SELECT campaign_name, goal_amount, current_amount, end_date, description
            FROM fundraising_campaigns
            WHERE status = 'active' OR status IS NULL
            ORDER BY end_date
            LIMIT 10
            """)

            campaigns = cursor.fetchall()

            if campaigns:
                for campaign in campaigns:
                    camp_name = campaign[0] or 'Unnamed Campaign'
                    camp_frame = ttk.LabelFrame(campaigns_frame, text=camp_name, padding=10)
                    camp_frame.pack(fill=tk.X, pady=5)

                    goal = float(campaign[1]) if campaign[1] else 0
                    current = float(campaign[2]) if campaign[2] else 0
                    progress = (current / goal * 100) if goal > 0 else 0
                    ttk.Label(camp_frame, text=_t("parent.fundraising.goal_progress", goal=f"{goal:.2f}", current=f"{current:.2f}", progress=f"{progress:.1f}"),
                             font=('Arial', 10, 'bold')).pack(anchor='w')
                    end_date = campaign[3] or _t("parent.fundraising.not_set")
                    ttk.Label(camp_frame, text=_t("parent.fundraising.ends_date", date=end_date),
                             font=('Arial', 9)).pack(anchor='w')
                    if campaign[4]:
                        ttk.Label(camp_frame, text=campaign[4], wraplength=600).pack(anchor='w', pady=3)

                    ttk.Button(camp_frame, text=_t("parent.fundraising.contribute"),
                              command=lambda c=camp_name: self.contribute_to_fundraiser(c)).pack(anchor='e', pady=5)
            else:
                ttk.Label(campaigns_frame, text=_t("parent.fundraising.no_active_campaigns"),
                         font=('Arial', 11)).pack(pady=50)
        else:
            ttk.Label(campaigns_frame, text=_t("parent.fundraising.system_not_configured"),
                     font=('Arial', 11)).pack(pady=20)

        conn.close()

    except Exception as e:
        ttk.Label(campaigns_frame, text=_t("parent.fundraising.error_loading", error=str(e)),
                 font=('Arial', 10)).pack(pady=20)
ParentPortalGUI.show_fundraising_interface = show_fundraising_interface

def contribute_to_fundraiser(self, campaign_name):
    """Contribute to a fundraiser"""
    amount = simpledialog.askfloat(_t("parent.fundraising.contribute"), _t("parent.fundraising.enter_amount", campaign=campaign_name))
    if amount:
        messagebox.showinfo(_t("parent.fundraising.thank_you_title"),
                           _t("parent.fundraising.contribution_thank_you", amount=f"{amount:.2f}", campaign=campaign_name))
ParentPortalGUI.contribute_to_fundraiser = contribute_to_fundraiser

def show_donations_history(self):
    """Show history of donations made by the parent"""
    self.clear_content()
    self.update_status(_t("parent.fundraising.my_donations"))

    title = ttk.Label(self.content_frame, text=_t("parent.fundraising.donation_history"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Donations display frame
    donations_frame = ttk.LabelFrame(self.content_frame, text=_t("parent.fundraising.your_donations"), padding=15)
    donations_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Check if donations table exists
        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='donations'
        """)

        if cursor.fetchone():
            # Get donations - try to match by parent_id or alumni_id
            parent_id = self.parent_id if self.parent_id else ''

            cursor.execute("""
            SELECT d.amount, d.donation_date, d.campaign,
                   COALESCE(fc.campaign_name, d.campaign, 'General Fund'),
                   d.payment_method, d.donation_type
            FROM donations d
            LEFT JOIN fundraising_campaigns fc ON d.campaign_id = fc.campaign_id
            WHERE d.alumni_id = ? OR d.alumni_id LIKE ?
            ORDER BY d.donation_date DESC
            LIMIT 50
            """, (parent_id, f'%{parent_id}%'))

            donations = cursor.fetchall()

            if donations:
                # Create treeview for donations
                columns = ("Amount", "Date", "Campaign", "Payment Method", "Type")
                tree = ttk.Treeview(donations_frame, columns=columns, show="headings", height=12)

                tree.heading("Amount", text=_t("common.amount"))
                tree.heading("Date", text=_t("common.date"))
                tree.heading("Campaign", text=_t("parent.fundraising.campaign"))
                tree.heading("Payment Method", text=_t("parent.fundraising.payment_method"))
                tree.heading("Type", text=_t("common.type"))

                tree.column("Amount", width=100)
                tree.column("Date", width=100)
                tree.column("Campaign", width=200)
                tree.column("Payment Method", width=120)
                tree.column("Type", width=100)

                total_donated = 0
                for donation in donations:
                    amount = float(donation[0]) if donation[0] else 0
                    total_donated += amount
                    date = donation[1] or 'N/A'
                    campaign = donation[3] or 'General Fund'
                    payment = donation[4] or 'N/A'
                    dtype = donation[5] or 'general'

                    tree.insert('', tk.END, values=(
                        f"${amount:.2f}",
                        date,
                        campaign,
                        payment,
                        dtype.title()
                    ))

                scrollbar = ttk.Scrollbar(donations_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)

                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Summary
                summary_frame = ttk.Frame(self.content_frame)
                summary_frame.pack(fill=tk.X, padx=20, pady=10)

                ttk.Label(summary_frame, text=_t("parent.fundraising.total_donations", total=f"{total_donated:.2f}"),
                         font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
                ttk.Label(summary_frame, text=_t("parent.fundraising.donation_count", count=len(donations)),
                         font=('Arial', 10)).pack(side=tk.LEFT)
            else:
                ttk.Label(donations_frame, text=_t("parent.fundraising.no_donations_found"),
                         font=('Arial', 11)).pack(pady=50)
                ttk.Label(donations_frame, text=_t("parent.fundraising.make_donation_hint"),
                         font=('Arial', 9, 'italic')).pack()
        else:
            ttk.Label(donations_frame, text=_t("parent.fundraising.donation_system_not_configured"),
                     font=('Arial', 11)).pack(pady=50)

        conn.close()

    except Exception as e:
        ttk.Label(donations_frame, text=_t("parent.fundraising.error_loading_donations", error=str(e)),
                 font=('Arial', 10)).pack(pady=20)

    # Back button
    ttk.Button(self.content_frame, text=_t("parent.fundraising.back_to_financial"),
              command=self.show_financial_menu).pack(pady=10)
ParentPortalGUI.show_donations_history = show_donations_history
