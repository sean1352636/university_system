"""
Cinema Booking System - Lost & Found Management
"""
import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.cinema.gui.cinema_gui.database import DB_FILE

def show_lost_found_page(self):
    """Display lost and found management page."""
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.lost_found.title"), style="Subtitle.TLabel").pack(anchor="w", pady=10)

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.log_found_item"), style="Success.TButton", command=self.log_found_item).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.search_items"), style="Secondary.TButton", command=self.search_lost_items).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.process_claim"), style="Primary.TButton", command=self.process_claim).pack(side="left", padx=5)

    filter_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    filter_frame.pack(fill="x", pady=5)

    self.lf_filter = getattr(self, 'lf_filter', 'unclaimed')
    filters = [("Unclaimed", "unclaimed"), ("Claimed", "claimed"), ("All", "all")]

    for text, value in filters:
        style = "Primary.TButton" if self.lf_filter == value else "Secondary.TButton"
        ttk.Button(filter_frame, text=text, style=style,
                  command=lambda v=value: self.set_lf_filter(v)).pack(side="left", padx=2)

    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Date", "Description", "Category", "Location", "Status", "Days Held")
    self.lf_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
    for col in columns:
        self.lf_tree.heading(col, text=col)
        self.lf_tree.column(col, width=100)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()

        query = "SELECT id, found_date, item_description, category, location_found, status, created_at FROM lost_found"
        if self.lf_filter == 'unclaimed':
            query += " WHERE status = 'unclaimed'"
        elif self.lf_filter == 'claimed':
            query += " WHERE status = 'claimed'"
        query += " ORDER BY found_date DESC"

        cursor.execute(query)
        for row in cursor.fetchall():
            days_held = "-"
            if row[1]:
                try:
                    found_date = datetime.strptime(row[1], "%Y-%m-%d")
                    days_held = (datetime.now() - found_date).days
                except (ValueError, TypeError):
                    pass
            self.lf_tree.insert("", "end", values=(row[0], row[1], row[2][:30] if row[2] else "", row[3], row[4] or "-", row[5].upper(), days_held))
    finally:
        conn.close()

    self.lf_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.lf_tree.yview)
    self.lf_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)
    ttk.Button(action_frame, text=_t("cinema.members.view_details"), style="Secondary.TButton", command=self.view_lf_details).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.mark_disposed"), style="Danger.TButton", command=self.dispose_lf_item).pack(side="left", padx=5)

    stats_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    stats_frame.pack(fill="x", pady=10)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM lost_found WHERE status = 'unclaimed'")
        unclaimed = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM lost_found WHERE status = 'claimed'")
        claimed = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM lost_found WHERE status = 'unclaimed' AND found_date <= date('now', '-30 days')")
        over_30_days = cursor.fetchone()[0]
    finally:
        conn.close()

    tk.Label(stats_frame, text=f"Unclaimed: {unclaimed} | Claimed: {claimed} | Over 30 days: {over_30_days}",
            bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

def set_lf_filter(self, filter_value):
    """Set the lost & found filter."""
    self.lf_filter = filter_value
    self.show_lost_found_page()

def log_found_item(self):
    """Log a newly found item."""
    form = tk.Toplevel(self.root)
    form.title("Log Found Item")
    form.geometry("450x550")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.lost_found.log_item"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    fields = {}

    tk.Label(frame, text=_t("cinema.labels.description_required"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    desc_text = tk.Text(frame, height=3, width=30, bg="#0f3460", fg="white")
    desc_text.grid(row=1, column=1, pady=5)
    fields['desc'] = desc_text

    tk.Label(frame, text=_t("cinema.labels.category"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    categories = ["electronics", "clothing", "bags", "accessories", "documents", "keys", "jewelry", "other"]
    cat_var = tk.StringVar(value="other")
    cat_combo = ttk.Combobox(frame, textvariable=cat_var, values=categories, width=27)
    cat_combo.grid(row=2, column=1, pady=5)
    fields['cat_var'] = cat_var

    tk.Label(frame, text=_t("cinema.labels.location_found"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    loc_e = ttk.Entry(frame, width=30)
    loc_e.grid(row=3, column=1, pady=5)
    fields['location'] = loc_e

    tk.Label(frame, text=_t("cinema.labels.screen_optional"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    screen_e = ttk.Entry(frame, width=30)
    screen_e.grid(row=4, column=1, pady=5)
    fields['screen'] = screen_e

    tk.Label(frame, text=_t("cinema.labels.found_date"), bg="#ffffff", fg="#333333").grid(row=5, column=0, sticky="w", pady=5)
    date_e = ttk.Entry(frame, width=30)
    date_e.insert(0, datetime.now().strftime("%Y-%m-%d"))
    date_e.grid(row=5, column=1, pady=5)
    fields['date'] = date_e

    tk.Label(frame, text=_t("cinema.labels.found_time"), bg="#ffffff", fg="#333333").grid(row=6, column=0, sticky="w", pady=5)
    time_e = ttk.Entry(frame, width=30)
    time_e.insert(0, datetime.now().strftime("%H:%M"))
    time_e.grid(row=6, column=1, pady=5)
    fields['time'] = time_e

    tk.Label(frame, text=_t("cinema.labels.storage_location"), bg="#ffffff", fg="#333333").grid(row=7, column=0, sticky="w", pady=5)
    storage_e = ttk.Entry(frame, width=30)
    storage_e.insert(0, "Front desk cabinet")
    storage_e.grid(row=7, column=1, pady=5)
    fields['storage'] = storage_e

    tk.Label(frame, text=_t("cinema.tickets.notes_label"), bg="#ffffff", fg="#333333").grid(row=8, column=0, sticky="w", pady=5)
    notes_e = ttk.Entry(frame, width=30)
    notes_e.grid(row=8, column=1, pady=5)
    fields['notes'] = notes_e

    def save():
        desc = fields['desc'].get("1.0", tk.END).strip()
        if not desc:
            messagebox.showwarning(_t("cinema.common.warning"), "Description is required")
            return

        screen = None
        if fields['screen'].get().strip():
            try:
                screen = int(fields['screen'].get())
            except (ValueError, TypeError):
                pass

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO lost_found (item_description, category, location_found, screen_number,
                                        found_date, found_time, storage_location, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (desc, fields['cat_var'].get(), fields['location'].get(), screen,
                  fields['date'].get(), fields['time'].get(), fields['storage'].get(), fields['notes'].get()))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Item logged successfully!")
        form.destroy()
        self.show_lost_found_page()

    ttk.Button(frame, text=_t("cinema.btn.log_item"), style="Success.TButton", command=save).grid(row=9, column=0, columnspan=2, pady=20)

def search_lost_items(self):
    """Search for lost items."""
    form = tk.Toplevel(self.root)
    form.title("Search Lost Items")
    form.geometry("600x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.lost_found.search"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    search_frame = ttk.Frame(frame, style="Card.TFrame")
    search_frame.pack(fill="x", pady=10)

    tk.Label(search_frame, text=_t("cinema.buttons.search_label"), bg="#ffffff", fg="#333333").pack(side="left")
    search_e = ttk.Entry(search_frame, width=30)
    search_e.pack(side="left", padx=5)

    tk.Label(search_frame, text=_t("cinema.labels.category"), bg="#ffffff", fg="#333333").pack(side="left", padx=(10, 0))
    categories = ["all", "electronics", "clothing", "bags", "accessories", "documents", "keys", "jewelry", "other"]
    cat_var = tk.StringVar(value="all")
    cat_combo = ttk.Combobox(search_frame, textvariable=cat_var, values=categories, width=15, state="readonly")
    cat_combo.pack(side="left", padx=5)

    tree_frame = ttk.Frame(frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Date", "Description", "Category", "Location", "Status")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=90)
    tree.pack(fill="both", expand=True, side="left")

    def search():
        for item in tree.get_children():
            tree.delete(item)

        search_term = search_e.get().strip()
        category = cat_var.get()

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            query = "SELECT id, found_date, item_description, category, location_found, status FROM lost_found WHERE status = 'unclaimed'"
            params = []

            if search_term:
                query += " AND item_description LIKE ?"
                params.append(f"%{escape_like(search_term)}%")
            if category != "all":
                query += " AND category = ?"
                params.append(category)

            query += " ORDER BY found_date DESC"

            cursor.execute(query, params)
            for row in cursor.fetchall():
                tree.insert("", "end", values=(row[0], row[1], row[2][:30], row[3], row[4] or "-", row[5]))
        finally:
            conn.close()

    ttk.Button(search_frame, text=_t("cinema.buttons.search"), style="Primary.TButton", command=search).pack(side="left", padx=10)

    search()

def process_claim(self):
    """Process a claim for a lost item."""
    selected = self.lf_tree.selection() if hasattr(self, 'lf_tree') else None
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select an item to process claim")
        return

    item_id = self.lf_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lost_found WHERE id = ?", (item_id,))
        item = cursor.fetchone()
    finally:
        conn.close()

    if not item:
        messagebox.showerror(_t("cinema.common.error"), "Item not found")
        return

    form = tk.Toplevel(self.root)
    form.title("Process Claim")
    form.geometry("450x450")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.btn.process_claim"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tk.Label(frame, text=f"Item: {item[1]}", bg="#ffffff", fg="#333333", wraplength=350).pack(anchor="w")
    tk.Label(frame, text=f"Found: {item[5]} at {item[4] or 'Unknown'}", bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

    tk.Label(frame, text=_t("cinema.labels.claimant_name"), bg="#ffffff", fg="#333333").pack(anchor="w", pady=(15, 0))
    name_e = ttk.Entry(frame, width=35)
    name_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.labels.claimant_email"), bg="#ffffff", fg="#333333").pack(anchor="w")
    email_e = ttk.Entry(frame, width=35)
    email_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.labels.claimant_phone"), bg="#ffffff", fg="#333333").pack(anchor="w")
    phone_e = ttk.Entry(frame, width=35)
    phone_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.labels.identification_method"), bg="#ffffff", fg="#333333").pack(anchor="w")
    methods = ["ID verification", "Described item accurately", "Provided receipt", "Other"]
    method_var = tk.StringVar(value="ID verification")
    method_combo = ttk.Combobox(frame, textvariable=method_var, values=methods, width=32)
    method_combo.pack(pady=5)

    def complete_claim():
        if not name_e.get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Claimant name is required")
            return

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE lost_found
                SET claimed = 1, claimed_by_name = ?, claimed_by_email = ?, claimed_by_phone = ?,
                    claim_date = ?, identification_method = ?, status = 'claimed'
                WHERE id = ?
            ''', (name_e.get(), email_e.get(), phone_e.get(), datetime.now().strftime("%Y-%m-%d"),
                  method_var.get(), item_id))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Claim processed successfully!")
        form.destroy()
        self.show_lost_found_page()

    ttk.Button(frame, text=_t("cinema.btn.complete_claim"), style="Success.TButton", command=complete_claim).pack(pady=20)

def view_lf_details(self):
    """View details of selected lost & found item."""
    selected = self.lf_tree.selection() if hasattr(self, 'lf_tree') else None
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select an item")
        return

    item_id = self.lf_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lost_found WHERE id = ?", (item_id,))
        item = cursor.fetchone()
    finally:
        conn.close()

    if not item:
        messagebox.showerror(_t("cinema.common.error"), "Item not found")
        return

    form = tk.Toplevel(self.root)
    form.title("Item Details")
    form.geometry("400x450")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.lost_found.item_details"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    details = [
        ("Description:", item[1]),
        ("Category:", item[2]),
        ("Location Found:", item[3] or "N/A"),
        ("Screen:", item[4] or "N/A"),
        ("Found Date:", item[5]),
        ("Found Time:", item[6] or "N/A"),
        ("Storage:", item[8] or "N/A"),
        ("Status:", item[16].upper() if item[16] else "UNCLAIMED"),
    ]

    if item[9]:
        details.extend([
            ("Claimed By:", item[10]),
            ("Claim Date:", item[13]),
        ])

    for label, value in details:
        row = ttk.Frame(frame, style="Card.TFrame")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg="#ffffff", fg="#7f8c8d", width=15, anchor="w").pack(side="left")
        tk.Label(row, text=str(value), bg="#ffffff", fg="#333333", wraplength=200).pack(side="left")

def dispose_lf_item(self):
    """Mark item as disposed after retention period."""
    selected = self.lf_tree.selection() if hasattr(self, 'lf_tree') else None
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select an item")
        return

    item_id = self.lf_tree.item(selected[0])['values'][0]

    if not messagebox.askyesno(_t("cinema.common.confirm"), "Mark this item as disposed?\n\nThis action cannot be undone."):
        return

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE lost_found SET status = 'disposed' WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()

    messagebox.showinfo(_t("cinema.common.success"), "Item marked as disposed")
    self.show_lost_found_page()
