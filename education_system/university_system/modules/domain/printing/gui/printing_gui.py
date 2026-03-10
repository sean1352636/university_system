import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PrintingServicesGUI:
    """Print quota management and print job submission system."""

    def __init__(self, parent=None):
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Printing Services")
        self.window.geometry("950x650")

        try:
            from education_system.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        try:
            from education_system.university_system.modules.shared.utils.i18n import get_text as _t
            self._t = _t
        except ImportError:
            self._t = lambda key, **kw: key

        self._init_db()
        self._build_ui()
        self._load_data()

    def _init_db(self):
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS print_quotas (
                    quota_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL UNIQUE,
                    total_pages INTEGER DEFAULT 500,
                    used_pages INTEGER DEFAULT 0,
                    color_pages_used INTEGER DEFAULT 0,
                    semester TEXT DEFAULT '',
                    last_reset TEXT DEFAULT (date('now'))
                )""")
                conn.execute("""CREATE TABLE IF NOT EXISTS print_jobs (
                    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    pages INTEGER DEFAULT 1,
                    copies INTEGER DEFAULT 1,
                    color INTEGER DEFAULT 0,
                    double_sided INTEGER DEFAULT 1,
                    paper_size TEXT DEFAULT 'A4',
                    printer_location TEXT DEFAULT '',
                    status TEXT DEFAULT 'queued',
                    cost_credits INTEGER DEFAULT 0,
                    submitted_at TEXT DEFAULT (datetime('now')),
                    completed_at TEXT
                )""")
                conn.execute("""CREATE TABLE IF NOT EXISTS print_credit_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                )""")
        except Exception as e:
            logger.error(f"DB init error: {e}")

    def _get_user_id(self):
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user = self.auth.current_user
            if isinstance(user, dict):
                return user.get('student_id', user.get('username', 'unknown'))
            return getattr(user, 'student_id', getattr(user, 'username', 'unknown'))
        return 'unknown'

    def _ensure_quota(self, conn, student_id):
        """Ensure student has a print quota record."""
        row = conn.execute("SELECT * FROM print_quotas WHERE student_id = ?", (student_id,)).fetchone()
        if not row:
            conn.execute("INSERT INTO print_quotas (student_id, total_pages, used_pages) VALUES (?, 500, 0)", (student_id,))
            conn.commit()
            row = conn.execute("SELECT * FROM print_quotas WHERE student_id = ?", (student_id,)).fetchone()
        return row

    def _build_ui(self):
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_quota_tab()
        self._build_print_tab()
        self._build_history_tab()
        self._build_credits_tab()

    def _build_quota_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Print Quota")

        # Quota display
        quota_frame = ttk.LabelFrame(tab, text="Print Quota Summary", padding=20)
        quota_frame.pack(fill=tk.X, padx=10, pady=10)

        self.quota_labels = {}
        stats = [
            ("Total Pages", "total"), ("Used Pages", "used"),
            ("Remaining", "remaining"), ("Color Pages Used", "color")
        ]
        stat_frame = ttk.Frame(quota_frame)
        stat_frame.pack(fill=tk.X)
        for i, (label, key) in enumerate(stats):
            f = ttk.LabelFrame(stat_frame, text=label, padding=10)
            f.grid(row=0, column=i, padx=10, pady=5, sticky="nsew")
            stat_frame.columnconfigure(i, weight=1)
            val = ttk.Label(f, text="0", font=("", 18, "bold"))
            val.pack()
            self.quota_labels[key] = val

        # Progress bar
        prog_frame = ttk.Frame(quota_frame)
        prog_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(prog_frame, text="Usage:").pack(side=tk.LEFT, padx=5)
        self.quota_progress = ttk.Progressbar(prog_frame, maximum=100, length=400)
        self.quota_progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.quota_pct_label = ttk.Label(prog_frame, text="0%")
        self.quota_pct_label.pack(side=tk.LEFT, padx=5)

        ttk.Button(tab, text="Refresh", command=self._load_quota).pack(pady=10)

    def _build_print_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Submit Print Job")

        form = ttk.LabelFrame(tab, text="Print Job Details", padding=15)
        form.pack(fill=tk.X, padx=10, pady=10)

        row = 0
        ttk.Label(form, text="File Name:").grid(row=row, column=0, sticky=tk.W, pady=3)
        file_frame = ttk.Frame(form)
        file_frame.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)
        self.file_entry = ttk.Entry(file_frame, width=30)
        self.file_entry.pack(side=tk.LEFT)
        ttk.Button(file_frame, text="Browse...", command=self._browse_file).pack(side=tk.LEFT, padx=5)

        row += 1
        ttk.Label(form, text="Pages:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.pages_entry = ttk.Spinbox(form, from_=1, to=200, width=8)
        self.pages_entry.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Copies:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.copies_entry = ttk.Spinbox(form, from_=1, to=20, width=8)
        self.copies_entry.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        self.color_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Color printing (2 credits/page)", variable=self.color_var).grid(
            row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        self.duplex_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Double-sided printing", variable=self.duplex_var).grid(
            row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Paper Size:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.paper_combo = ttk.Combobox(form, values=["A4", "A3", "Letter", "Legal"], state="readonly", width=10)
        self.paper_combo.set("A4")
        self.paper_combo.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Printer:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.printer_combo = ttk.Combobox(form, values=[
            "Library - Ground Floor", "Library - 1st Floor", "Student Center",
            "Computer Lab A", "Computer Lab B", "Engineering Building"
        ], state="readonly", width=25)
        self.printer_combo.set("Library - Ground Floor")
        self.printer_combo.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        self.cost_label = ttk.Label(form, text="Estimated cost: 1 credit(s)", font=("", 10))
        self.cost_label.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)

        # Update cost estimate on changes
        for widget in [self.pages_entry, self.copies_entry]:
            widget.bind("<KeyRelease>", lambda e: self._update_cost())
        self.color_var.trace_add("write", lambda *a: self._update_cost())
        self.duplex_var.trace_add("write", lambda *a: self._update_cost())

        row += 1
        ttk.Button(form, text="Submit Print Job", command=self._submit_job).grid(
            row=row, column=1, sticky=tk.W, pady=10, padx=5)

    def _build_history_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Print History")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_history).pack(side=tk.LEFT, padx=2)

        cols = ("job_id", "file", "pages", "copies", "color", "duplex", "printer", "cost", "status", "submitted")
        self.history_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for c, w in zip(cols, (50, 150, 50, 50, 50, 50, 130, 50, 70, 130)):
            self.history_tree.heading(c, text=c.replace("_", " ").title())
            self.history_tree.column(c, width=w, minwidth=30)
        self.history_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_credits_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Buy Credits")

        info = ttk.LabelFrame(tab, text="Purchase Print Credits", padding=15)
        info.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info, text="Add pages to your print quota:", font=("", 11)).pack(anchor=tk.W, pady=(0, 10))

        packages = [
            ("50 pages", 50, "2.50"),
            ("100 pages", 100, "4.50"),
            ("250 pages", 250, "10.00"),
            ("500 pages", 500, "18.00"),
        ]
        for label, pages, price in packages:
            f = ttk.Frame(info)
            f.pack(fill=tk.X, pady=3)
            ttk.Label(f, text=f"{label} - \u00a3{price}", width=25).pack(side=tk.LEFT)
            ttk.Button(f, text="Purchase", command=lambda p=pages, pr=price: self._purchase_credits(p, pr)).pack(side=tk.LEFT, padx=10)

        # Transaction history
        ttk.Label(tab, text="Transaction History", font=("", 11, "bold")).pack(anchor=tk.W, padx=10, pady=(15, 5))
        cols = ("id", "amount", "type", "description", "date")
        self.trans_tree = ttk.Treeview(tab, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (50, 80, 80, 200, 150)):
            self.trans_tree.heading(c, text=c.title())
            self.trans_tree.column(c, width=w, minwidth=40)
        self.trans_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def _load_data(self):
        self._load_quota()
        self._load_history()
        self._load_transactions()

    def _load_quota(self):
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            student_id = self._get_user_id()
            with get_connection() as conn:
                row = self._ensure_quota(conn, student_id)
                total = row["total_pages"]
                used = row["used_pages"]
                remaining = total - used
                color = row["color_pages_used"]
                pct = (used / max(total, 1)) * 100

                self.quota_labels["total"].configure(text=str(total))
                self.quota_labels["used"].configure(text=str(used))
                self.quota_labels["remaining"].configure(text=str(remaining))
                self.quota_labels["color"].configure(text=str(color))
                self.quota_progress['value'] = pct
                self.quota_pct_label.configure(text=f"{pct:.0f}%")

                if remaining < 50:
                    self.quota_labels["remaining"].configure(foreground="red")
                else:
                    self.quota_labels["remaining"].configure(foreground="green")
        except Exception as e:
            logger.debug(f"Load quota: {e}")

    def _load_history(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            student_id = self._get_user_id()
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM print_jobs WHERE student_id = ? ORDER BY submitted_at DESC",
                    (student_id,)
                ).fetchall()
                for r in rows:
                    self.history_tree.insert("", tk.END, values=(
                        r["job_id"], r["file_name"], r["pages"], r["copies"],
                        "Yes" if r["color"] else "No",
                        "Yes" if r["double_sided"] else "No",
                        r["printer_location"], r["cost_credits"],
                        r["status"], r["submitted_at"]
                    ))
        except Exception as e:
            logger.debug(f"Load history: {e}")

    def _load_transactions(self):
        for item in self.trans_tree.get_children():
            self.trans_tree.delete(item)
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            student_id = self._get_user_id()
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM print_credit_transactions WHERE student_id = ? ORDER BY created_at DESC",
                    (student_id,)
                ).fetchall()
                for r in rows:
                    self.trans_tree.insert("", tk.END, values=(
                        r["transaction_id"], r["amount"], r["transaction_type"],
                        r["description"], r["created_at"]
                    ))
        except Exception as e:
            logger.debug(f"Load transactions: {e}")

    def _update_cost(self):
        try:
            pages = int(self.pages_entry.get())
            copies = int(self.copies_entry.get())
            rate = 2 if self.color_var.get() else 1
            total = pages * copies * rate
            if self.duplex_var.get():
                total = max(1, total // 2 + total % 2)
            self.cost_label.configure(text=f"Estimated cost: {total} credit(s)")
        except (ValueError, tk.TclError):
            pass

    def _browse_file(self):
        path = filedialog.askopenfilename(
            parent=self.window,
            filetypes=[("PDF", "*.pdf"), ("Documents", "*.doc;*.docx"), ("All files", "*.*")]
        )
        if path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, path.split("/")[-1])

    def _submit_job(self):
        file_name = self.file_entry.get().strip()
        if not file_name:
            messagebox.showwarning("Warning", "Please select or enter a file name.")
            return

        try:
            pages = int(self.pages_entry.get())
            copies = int(self.copies_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid pages or copies value.")
            return

        color = 1 if self.color_var.get() else 0
        duplex = 1 if self.duplex_var.get() else 0
        rate = 2 if color else 1
        cost = pages * copies * rate
        if duplex:
            cost = max(1, cost // 2 + cost % 2)

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            student_id = self._get_user_id()
            with get_connection() as conn:
                quota = self._ensure_quota(conn, student_id)
                remaining = quota["total_pages"] - quota["used_pages"]
                if cost > remaining:
                    messagebox.showerror("Error", f"Insufficient print credits. Need {cost}, have {remaining}.\nPurchase more credits in the 'Buy Credits' tab.")
                    return

                conn.execute("""INSERT INTO print_jobs
                    (student_id, file_name, pages, copies, color, double_sided, paper_size, printer_location, cost_credits, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')""",
                    (student_id, file_name, pages, copies, color, duplex,
                     self.paper_combo.get(), self.printer_combo.get(), cost))

                conn.execute("UPDATE print_quotas SET used_pages = used_pages + ?, color_pages_used = color_pages_used + ? WHERE student_id = ?",
                    (cost, pages * copies if color else 0, student_id))

                conn.execute("INSERT INTO print_credit_transactions (student_id, amount, transaction_type, description) VALUES (?, ?, 'debit', ?)",
                    (student_id, -cost, f"Print job: {file_name} ({pages}p x{copies})"))
                conn.commit()

            messagebox.showinfo("Success", f"Print job submitted! Cost: {cost} credits.\nCollect from: {self.printer_combo.get()}")
            self.file_entry.delete(0, tk.END)
            self._load_data()
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")

    def _purchase_credits(self, pages, price):
        if messagebox.askyesno("Confirm Purchase", f"Purchase {pages} print credits for \u00a3{price}?"):
            try:
                from education_system.university_system.infrastructure.database.db import get_connection
                student_id = self._get_user_id()
                with get_connection() as conn:
                    self._ensure_quota(conn, student_id)
                    conn.execute("UPDATE print_quotas SET total_pages = total_pages + ? WHERE student_id = ?",
                        (pages, student_id))
                    conn.execute("INSERT INTO print_credit_transactions (student_id, amount, transaction_type, description) VALUES (?, ?, 'credit', ?)",
                        (student_id, pages, f"Purchased {pages} pages (\u00a3{price})"))
                    conn.commit()
                messagebox.showinfo("Success", f"{pages} credits added to your account!")
                self._load_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")


def launch_printing_gui(parent=None):
    return PrintingServicesGUI(parent=parent)
