"""
Cinema Booking System - Gift Card Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
import random
import string
from datetime import datetime, timedelta

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def show_gift_cards_page(self):
    """Display gift cards management page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.gift_cards.title"),
             style="Subtitle.TLabel").pack(pady=10)

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)

    ttk.Button(btn_frame, text=_t("cinema.btn.create_gift_card"), style="Success.TButton",
              command=self.create_gift_card).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.check_balance"), style="Primary.TButton",
              command=self.check_gift_card_balance).pack(side="left", padx=5)

    # Gift cards list
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Code", "Initial", "Balance", "Purchaser", "Recipient", "Purchased", "Status")
    self.gc_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

    for col in columns:
        self.gc_tree.heading(col, text=col)
    self.gc_tree.column("ID", width=50)
    self.gc_tree.column("Code", width=120)
    self.gc_tree.column("Initial", width=80)
    self.gc_tree.column("Balance", width=80)
    self.gc_tree.column("Purchaser", width=120)
    self.gc_tree.column("Recipient", width=120)
    self.gc_tree.column("Purchased", width=100)
    self.gc_tree.column("Status", width=80)

    self.refresh_gift_cards()

    self.gc_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.gc_tree.yview)
    self.gc_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)

    ttk.Button(action_frame, text=_t("cinema.members.view_details"), style="Secondary.TButton",
              command=self.view_gift_card_details).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.members.deactivate"), style="Danger.TButton",
              command=self.deactivate_gift_card).pack(side="left", padx=5)

def refresh_gift_cards(self):
    """Refresh gift cards list."""
    for item in self.gc_tree.get_children():
        self.gc_tree.delete(item)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gift_cards ORDER BY id DESC")

        for row in cursor.fetchall():
            self.gc_tree.insert("", "end", values=(
                row[0], row[1], f"£{row[2]:.2f}", f"£{row[3]:.2f}",
                row[4] or "-", row[6] or "-",
                row[9][:10] if row[9] else "-", row[11].upper()
            ))
    finally:
        conn.close()

def create_gift_card(self):
    """Create a new gift card."""
    form_window = tk.Toplevel(self.root)
    form_window.title("Create Gift Card")
    form_window.geometry("500x450")
    form_window.configure(bg="#ecf0f1")
    form_window.transient(self.root)
    form_window.grab_set()

    fields_frame = ttk.Frame(form_window, style="Card.TFrame", padding=20)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(fields_frame, text=_t("cinema.gift_cards.create"), font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    tk.Label(fields_frame, text=_t("cinema.gift_cards.value_label"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    value_var = tk.StringVar(value="50")
    value_combo = ttk.Combobox(fields_frame, textvariable=value_var, width=32,
                               values=["25", "50", "75", "100", "150", "200"])
    value_combo.grid(row=1, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.labels.purchaser_name"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    purchaser_entry = ttk.Entry(fields_frame, width=35)
    purchaser_entry.grid(row=2, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.labels.purchaser_email"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    purchaser_email = ttk.Entry(fields_frame, width=35)
    purchaser_email.grid(row=3, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.labels.recipient_name"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    recipient_entry = ttk.Entry(fields_frame, width=35)
    recipient_entry.grid(row=4, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.gift_cards.recipient_email"), bg="#ffffff", fg="#333333").grid(row=5, column=0, sticky="w", pady=5)
    recipient_email = ttk.Entry(fields_frame, width=35)
    recipient_email.grid(row=5, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.labels.personal_message"), bg="#ffffff", fg="#333333").grid(row=6, column=0, sticky="nw", pady=5)
    message_text = tk.Text(fields_frame, width=27, height=3, font=("Helvetica", 10))
    message_text.grid(row=6, column=1, pady=5)

    def generate_code():
        return 'GC' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

    def save_gift_card():
        try:
            value = float(value_var.get())
        except (ValueError, TypeError):
            messagebox.showwarning(_t("cinema.common.warning"), "Invalid value")
            return

        code = generate_code()
        expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO gift_cards
                (code, initial_value, current_balance, purchaser_name, purchaser_email,
                 recipient_name, recipient_email, message, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (code, value, value, purchaser_entry.get().strip(),
                  purchaser_email.get().strip(), recipient_entry.get().strip(),
                  recipient_email.get().strip(), message_text.get("1.0", tk.END).strip(), expiry))
            conn.commit()

            messagebox.showinfo(_t("cinema.gift_cards.created"),
                f"Gift Card Code: {code}\nValue: £{value:.2f}\nExpires: {expiry}\n\n"
                "This code can be used during checkout.")
            form_window.destroy()
            self.refresh_gift_cards()

        except Exception as e:
            messagebox.showerror(_t("cinema.common.error"), f"Failed: {str(e)}")
        finally:
            conn.close()

    btn_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    btn_frame.grid(row=7, column=0, columnspan=2, pady=20)

    ttk.Button(btn_frame, text=_t("cinema.gift_cards.create"), style="Success.TButton",
              command=save_gift_card).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.cancel"), style="Secondary.TButton",
              command=form_window.destroy).pack(side="left", padx=5)

def check_gift_card_balance(self):
    """Check gift card balance."""
    dialog = tk.Toplevel(self.root)
    dialog.title("Check Gift Card Balance")
    dialog.geometry("400x250")
    dialog.configure(bg="#ecf0f1")
    dialog.transient(self.root)
    dialog.grab_set()

    frame = ttk.Frame(dialog, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.labels.enter_gift_card_code"), font=("Helvetica", 12, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(pady=10)

    code_entry = ttk.Entry(frame, width=25)
    code_entry.pack(pady=10)

    result_label = tk.Label(frame, text="", bg="#ffffff", fg="#27ae60",
                           font=("Helvetica", 14))
    result_label.pack(pady=10)

    def check():
        code = code_entry.get().strip().upper()
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT current_balance, status, expiry_date FROM gift_cards WHERE code = ?", (code,))
            result = cursor.fetchone()
        finally:
            conn.close()

        if result:
            if result[1] != 'active':
                result_label.config(text=f"Card is {result[1]}", fg="#dc3545")
            elif result[2] and result[2] < datetime.now().strftime("%Y-%m-%d"):
                result_label.config(text=_t("cinema.messages.card_expired"), fg="#dc3545")
            else:
                result_label.config(text=f"Balance: £{result[0]:.2f}", fg="#27ae60")
        else:
            result_label.config(text=_t("cinema.messages.gift_card_not_found"), fg="#dc3545")

    ttk.Button(frame, text=_t("cinema.btn.check_balance"), style="Primary.TButton",
              command=check).pack()

def view_gift_card_details(self):
    """View gift card details."""
    selected = self.gc_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a gift card")
        return
    messagebox.showinfo(_t("cinema.common.info"), "Gift card details displayed in the list")

def deactivate_gift_card(self):
    """Deactivate a gift card."""
    selected = self.gc_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a gift card")
        return

    gc_id = self.gc_tree.item(selected[0])['values'][0]

    if not messagebox.askyesno(_t("cinema.common.confirm"), "Deactivate this gift card?"):
        return

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE gift_cards SET status = 'inactive' WHERE id = ?", (gc_id,))
        conn.commit()
    finally:
        conn.close()

    self.refresh_gift_cards()
