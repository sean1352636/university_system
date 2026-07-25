"""
Cinema Booking System - Season Pass Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.systems.university.infrastructure.database.db import sqlite3
import random
import string
from datetime import datetime, timedelta

try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.systems.university.interfaces.gui.operations.commerce.cinema.cinema_gui.database import DB_FILE
from education_system.systems.university.interfaces.gui.operations.commerce.cinema.cinema_gui.constants import SEASON_PASSES

def show_season_passes_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.passes.title"), style="Subtitle.TLabel").pack(pady=10)
    info = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    info.pack(fill="x", pady=10)
    tk.Label(info, text=_t("cinema.passes.season_options"), font=("Helvetica", 12, "bold"), bg="#ffffff", fg="#e74c3c").pack(anchor="w")
    for ptype, pinfo in SEASON_PASSES.items():
        tk.Label(info, text=f"{ptype.title()}: £{pinfo['price']:.2f} - {pinfo['duration_days']} days unlimited", bg="#ffffff", fg="#7f8c8d").pack(anchor="w")
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.sell_pass"), style="Success.TButton", command=self.sell_pass).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.passes.verify"), style="Primary.TButton", command=self.verify_pass).pack(side="left", padx=5)
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)
    columns = ("ID", "Code", _t("cinema.columns.customer"), "Type", "Start", "End", "Used", "Status")
    self.pass_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
    for col in columns:
        self.pass_tree.heading(col, text=col)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM season_passes ORDER BY id DESC")
        for row in cursor.fetchall():
            self.pass_tree.insert("", "end", values=(row[0], row[1], row[3], row[5].title(), row[7], row[8], row[9], row[10].upper()))
    finally:
        conn.close()
    self.pass_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.pass_tree.yview)
    self.pass_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

def sell_pass(self):
    form = tk.Toplevel(self.root)
    form.title("Sell Season Pass")
    form.geometry("400x300")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()
    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text=_t("cinema.passes.sell"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)
    tk.Label(frame, text=_t("cinema.members.name_required"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    name_e = ttk.Entry(frame, width=25)
    name_e.grid(row=1, column=1, pady=5)
    tk.Label(frame, text=_t("cinema.members.email_required"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    email_e = ttk.Entry(frame, width=25)
    email_e.grid(row=2, column=1, pady=5)
    tk.Label(frame, text=_t("cinema.labels.type"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    type_var = tk.StringVar(value="monthly")
    ttk.Combobox(frame, textvariable=type_var, width=22, values=list(SEASON_PASSES.keys())).grid(row=3, column=1, pady=5)
    def sell():
        if not name_e.get().strip() or not email_e.get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Name and email required")
            return
        code = 'SP' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        start = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=SEASON_PASSES[type_var.get()]['duration_days'])).strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO season_passes (pass_code, customer_name, customer_email, pass_type, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?)",
                          (code, name_e.get(), email_e.get(), type_var.get(), start, end))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), f"Pass Code: {code}\nValid until: {end}")
        form.destroy()
        self.show_season_passes_page()
    ttk.Button(frame, text=_t("cinema.btn.sell"), style="Success.TButton", command=sell).grid(row=4, column=0, columnspan=2, pady=20)

def verify_pass(self):
    dialog = tk.Toplevel(self.root)
    dialog.title("Verify Pass")
    dialog.geometry("350x250")
    dialog.configure(bg="#ecf0f1")
    dialog.transient(self.root)
    dialog.grab_set()
    frame = ttk.Frame(dialog, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text=_t("cinema.labels.enter_pass_code"), font=("Helvetica", 12, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)
    code_e = ttk.Entry(frame, width=20)
    code_e.pack(pady=10)
    result_l = tk.Label(frame, text="", bg="#ffffff", fg="#27ae60", font=("Helvetica", 12))
    result_l.pack(pady=10)
    def verify():
        code = code_e.get().strip().upper()
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM season_passes WHERE pass_code = ?", (code,))
            result = cursor.fetchone()
        finally:
            conn.close()
        if result:
            valid = result[10] == 'active' and result[8] >= datetime.now().strftime("%Y-%m-%d")
            if valid:
                result_l.config(text=f"VALID - {result[3]}\nUntil: {result[8]}", fg="#27ae60")
            else:
                result_l.config(text=_t("cinema.status.expired_invalid"), fg="#dc3545")
        else:
            result_l.config(text=_t("cinema.status.not_found"), fg="#dc3545")
    ttk.Button(frame, text=_t("cinema.btn.verify"), style="Primary.TButton", command=verify).pack()
