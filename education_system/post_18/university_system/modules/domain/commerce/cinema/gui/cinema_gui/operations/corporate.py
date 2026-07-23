"""
Cinema Booking System - Corporate Accounts
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def show_corporate_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.corporate.title"), style="Subtitle.TLabel").pack(pady=10)
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text="+ Add Account", style="Success.TButton", command=self.add_corporate).pack(side="left", padx=5)
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)
    columns = ("ID", "Company", "Contact", "Email", "Credit", "Balance", "Discount", "Status")
    self.corp_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
    for col in columns:
        self.corp_tree.heading(col, text=col)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM corporate_accounts ORDER BY company_name")
        for row in cursor.fetchall():
            self.corp_tree.insert("", "end", values=(row[0], row[1], row[2], row[3], f"\u00a3{row[7]:.2f}", f"\u00a3{row[8]:.2f}", f"{row[10]}%", row[11].upper()))
    finally:
        conn.close()
    self.corp_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.corp_tree.yview)
    self.corp_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

def add_corporate(self):
    form = tk.Toplevel(self.root)
    form.title("Add Corporate Account")
    form.geometry("450x400")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()
    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text=_t("cinema.corporate.new_account"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)
    fields = [("Company:*", "company"), ("Contact:*", "contact"), ("Email:*", "email"), ("Phone:", "phone"), ("Credit Limit:", "credit"), ("Discount %:", "discount")]
    entries = {}
    for i, (label, key) in enumerate(fields):
        tk.Label(frame, text=label, bg="#ffffff", fg="#333333").grid(row=i+1, column=0, sticky="w", pady=5)
        e = ttk.Entry(frame, width=30)
        e.grid(row=i+1, column=1, pady=5)
        entries[key] = e
    entries['credit'].insert(0, "1000")
    entries['discount'].insert(0, "10")
    def save():
        if not entries['company'].get().strip() or not entries['contact'].get().strip() or not entries['email'].get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Company, contact, email required")
            return
        try:
            credit = float(entries['credit'].get() or 1000)
            discount = float(entries['discount'].get() or 10)
        except (ValueError, TypeError):
            credit, discount = 1000, 10
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO corporate_accounts (company_name, contact_name, contact_email, contact_phone, credit_limit, discount_percent) VALUES (?, ?, ?, ?, ?, ?)",
                          (entries['company'].get(), entries['contact'].get(), entries['email'].get(), entries['phone'].get(), credit, discount))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Account created!")
        form.destroy()
        self.show_corporate_page()
    ttk.Button(frame, text=_t("cinema.btn.create"), style="Success.TButton", command=save).grid(row=len(fields)+1, column=0, columnspan=2, pady=20)
