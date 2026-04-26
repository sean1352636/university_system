"""
University Student Union Election Voting System
A complete GUI-based voting system using Tkinter and SQLite.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import hashlib
import os
from datetime import datetime


# ---------- Database Layer ----------
class Database:
    def __init__(self, db_path="election.db"):
        self.db_path = db_path
        self.init_db()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.connect()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                created_at TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE NOT NULL,
                description TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                position_id INTEGER NOT NULL,
                manifesto TEXT,
                FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                candidate_id INTEGER NOT NULL,
                position_id INTEGER NOT NULL,
                voted_at TEXT NOT NULL,
                UNIQUE(user_id, position_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (candidate_id) REFERENCES candidates(id),
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Default election status
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    ("election_open", "1"))

        # Seed admin
        cur.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO users (student_id, full_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                ("admin", "System Administrator", hash_password("admin123"),
                 "admin", datetime.now().isoformat())
            )

        # Seed demo data if empty
        cur.execute("SELECT COUNT(*) FROM positions")
        if cur.fetchone()[0] == 0:
            demo_positions = [
                ("President", "Leads the student union and represents the student body."),
                ("Vice President", "Assists the President and oversees committees."),
                ("Secretary General", "Manages records, minutes, and communications."),
                ("Treasurer", "Manages union finances and budgeting."),
            ]
            cur.executemany(
                "INSERT INTO positions (title, description) VALUES (?, ?)",
                demo_positions
            )

            cur.execute("SELECT id, title FROM positions")
            pos_map = {title: pid for pid, title in cur.fetchall()}

            demo_candidates = [
                ("Alice Johnson", pos_map["President"],
                 "Campaigning for better library hours and mental health support."),
                ("Brian Okello", pos_map["President"],
                 "Focused on improving campus dining and transportation."),
                ("Carmen Diaz", pos_map["Vice President"],
                 "Advocate for inclusive clubs and student representation."),
                ("David Park", pos_map["Vice President"],
                 "Wants to expand sports programs and intramural events."),
                ("Esther Mwangi", pos_map["Secretary General"],
                 "Promises transparent communication and digital records."),
                ("Faisal Rahman", pos_map["Treasurer"],
                 "Will publish quarterly budgets and reduce unnecessary spending."),
            ]
            cur.executemany(
                "INSERT INTO candidates (full_name, position_id, manifesto) VALUES (?, ?, ?)",
                demo_candidates
            )

        conn.commit()
        conn.close()

    def get_setting(self, key):
        conn = self.connect()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

    def set_setting(self, key, value):
        conn = self.connect()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, value))
        conn.commit()
        conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ---------- Styling ----------
PRIMARY = "#1e3a8a"      # deep blue
ACCENT = "#3b82f6"       # bright blue
SUCCESS = "#16a34a"
DANGER = "#dc2626"
BG = "#f1f5f9"
CARD = "#ffffff"
TEXT = "#0f172a"
MUTED = "#64748b"


def setup_styles():
    style = ttk.Style()
    style.theme_use("clam")

    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD, relief="flat")
    style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
    style.configure("Card.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 10))
    style.configure("Title.TLabel", background=BG, foreground=PRIMARY,
                    font=("Segoe UI", 20, "bold"))
    style.configure("Subtitle.TLabel", background=BG, foreground=MUTED,
                    font=("Segoe UI", 11))
    style.configure("Heading.TLabel", background=CARD, foreground=PRIMARY,
                    font=("Segoe UI", 14, "bold"))
    style.configure("Muted.TLabel", background=CARD, foreground=MUTED,
                    font=("Segoe UI", 9))

    style.configure("Primary.TButton", background=PRIMARY, foreground="white",
                    font=("Segoe UI", 10, "bold"), padding=(16, 10), borderwidth=0)
    style.map("Primary.TButton", background=[("active", ACCENT)])

    style.configure("Accent.TButton", background=ACCENT, foreground="white",
                    font=("Segoe UI", 10, "bold"), padding=(14, 8), borderwidth=0)
    style.map("Accent.TButton", background=[("active", PRIMARY)])

    style.configure("Success.TButton", background=SUCCESS, foreground="white",
                    font=("Segoe UI", 10, "bold"), padding=(14, 8), borderwidth=0)
    style.map("Success.TButton", background=[("active", "#15803d")])

    style.configure("Danger.TButton", background=DANGER, foreground="white",
                    font=("Segoe UI", 10, "bold"), padding=(14, 8), borderwidth=0)
    style.map("Danger.TButton", background=[("active", "#b91c1c")])

    style.configure("TEntry", fieldbackground="white", padding=8)
    style.configure("Treeview", background="white", fieldbackground="white",
                    rowheight=28, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", background=PRIMARY, foreground="white",
                    font=("Segoe UI", 10, "bold"), padding=8)
    style.map("Treeview", background=[("selected", ACCENT)])


# ---------- Login / Register ----------
class LoginWindow:
    def __init__(self, root, db, on_login_success):
        self.root = root
        self.db = db
        self.on_login_success = on_login_success
        self.frame = None
        self.build()

    def build(self):
        if self.frame:
            self.frame.destroy()

        self.frame = ttk.Frame(self.root, style="TFrame")
        self.frame.pack(fill="both", expand=True)

        # Center container
        outer = ttk.Frame(self.frame, style="TFrame")
        outer.place(relx=0.5, rely=0.5, anchor="center")

        # Header
        ttk.Label(outer, text="🎓 Student Union Elections",
                  style="Title.TLabel").pack(pady=(0, 6))
        ttk.Label(outer, text="Sign in to cast your vote",
                  style="Subtitle.TLabel").pack(pady=(0, 24))

        # Card
        card = tk.Frame(outer, bg=CARD, padx=36, pady=32,
                        highlightbackground="#e2e8f0", highlightthickness=1)
        card.pack()

        tk.Label(card, text="Student ID", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.id_entry = ttk.Entry(card, width=32, font=("Segoe UI", 11))
        self.id_entry.grid(row=1, column=0, pady=(0, 14), ipady=4)

        tk.Label(card, text="Password", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.pw_entry = ttk.Entry(card, width=32, show="•", font=("Segoe UI", 11))
        self.pw_entry.grid(row=3, column=0, pady=(0, 18), ipady=4)

        ttk.Button(card, text="Sign In", style="Primary.TButton",
                   command=self.login).grid(row=4, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(card, text="Register New Account", style="Accent.TButton",
                   command=self.show_register).grid(row=5, column=0, sticky="ew")

        # Hint
        hint = tk.Label(card,
                        text="Demo admin → admin / admin123",
                        bg=CARD, fg=MUTED, font=("Segoe UI", 9, "italic"))
        hint.grid(row=6, column=0, pady=(18, 0))

        self.id_entry.focus()
        self.root.bind("<Return>", lambda e: self.login())

    def login(self):
        sid = self.id_entry.get().strip()
        pw = self.pw_entry.get()

        if not sid or not pw:
            messagebox.showwarning("Missing fields", "Please enter both Student ID and password.")
            return

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, full_name, role FROM users WHERE student_id=? AND password_hash=?",
            (sid, hash_password(pw))
        )
        row = cur.fetchone()
        conn.close()

        if row:
            user = {"id": row[0], "name": row[1], "role": row[2], "student_id": sid}
            self.root.unbind("<Return>")
            self.on_login_success(user)
        else:
            messagebox.showerror("Login failed", "Invalid student ID or password.")

    def show_register(self):
        RegisterDialog(self.root, self.db)


class RegisterDialog:
    def __init__(self, parent, db):
        self.db = db
        self.win = tk.Toplevel(parent)
        self.win.title("Register")
        self.win.configure(bg=BG)
        self.win.geometry("420x420")
        self.win.transient(parent)
        self.win.grab_set()

        ttk.Label(self.win, text="Create Account",
                  style="Title.TLabel").pack(pady=(20, 4))
        ttk.Label(self.win, text="Register as a student voter",
                  style="Subtitle.TLabel").pack(pady=(0, 16))

        card = tk.Frame(self.win, bg=CARD, padx=28, pady=22,
                        highlightbackground="#e2e8f0", highlightthickness=1)
        card.pack(padx=20, fill="x")

        tk.Label(card, text="Full Name", bg=CARD, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.name = ttk.Entry(card, font=("Segoe UI", 11))
        self.name.pack(fill="x", pady=(2, 10), ipady=3)

        tk.Label(card, text="Student ID", bg=CARD, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.sid = ttk.Entry(card, font=("Segoe UI", 11))
        self.sid.pack(fill="x", pady=(2, 10), ipady=3)

        tk.Label(card, text="Password", bg=CARD, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.pw = ttk.Entry(card, show="•", font=("Segoe UI", 11))
        self.pw.pack(fill="x", pady=(2, 10), ipady=3)

        tk.Label(card, text="Confirm Password", bg=CARD, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.pw2 = ttk.Entry(card, show="•", font=("Segoe UI", 11))
        self.pw2.pack(fill="x", pady=(2, 14), ipady=3)

        ttk.Button(card, text="Create Account", style="Primary.TButton",
                   command=self.register).pack(fill="x")

    def register(self):
        name = self.name.get().strip()
        sid = self.sid.get().strip()
        pw = self.pw.get()
        pw2 = self.pw2.get()

        if not all([name, sid, pw, pw2]):
            messagebox.showwarning("Missing", "Please fill in all fields.", parent=self.win)
            return
        if len(pw) < 4:
            messagebox.showwarning("Weak password", "Password must be at least 4 characters.",
                                   parent=self.win)
            return
        if pw != pw2:
            messagebox.showwarning("Mismatch", "Passwords do not match.", parent=self.win)
            return

        try:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (student_id, full_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (sid, name, hash_password(pw), "student", datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Account created. You can now sign in.",
                                parent=self.win)
            self.win.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "That Student ID is already registered.",
                                 parent=self.win)


# ---------- Voter Dashboard ----------
class VoterDashboard:
    def __init__(self, root, db, user, on_logout):
        self.root = root
        self.db = db
        self.user = user
        self.on_logout = on_logout
        self.frame = None
        self.position_buttons = {}
        self.build()

    def build(self):
        if self.frame:
            self.frame.destroy()

        self.frame = ttk.Frame(self.root, style="TFrame")
        self.frame.pack(fill="both", expand=True)

        # Top bar
        topbar = tk.Frame(self.frame, bg=PRIMARY, height=64)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="🎓 Student Union Elections",
                 bg=PRIMARY, fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=24)

        right = tk.Frame(topbar, bg=PRIMARY)
        right.pack(side="right", padx=20)
        tk.Label(right, text=f"  {self.user['name']}",
                 bg=PRIMARY, fg="white",
                 font=("Segoe UI", 11)).pack(side="left", padx=(0, 16))
        ttk.Button(right, text="Logout", style="Danger.TButton",
                   command=self.logout).pack(side="left")

        # Content
        content = ttk.Frame(self.frame, style="TFrame", padding=24)
        content.pack(fill="both", expand=True)

        # Status banner
        status = self.db.get_setting("election_open")
        if status != "1":
            banner = tk.Frame(content, bg="#fef3c7", padx=14, pady=10,
                              highlightbackground="#fbbf24", highlightthickness=1)
            banner.pack(fill="x", pady=(0, 16))
            tk.Label(banner,
                     text="⚠ Voting is currently closed by the administrator.",
                     bg="#fef3c7", fg="#92400e",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")

        ttk.Label(content, text="Available Positions",
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(content,
                  text="Select a position below to view candidates and cast your vote.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 18))

        # Positions grid (scrollable)
        canvas = tk.Canvas(content, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        grid_frame = ttk.Frame(canvas, style="TFrame")
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        grid_frame.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Mouse wheel scroll
        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        self.render_positions(grid_frame)

    def render_positions(self, parent):
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT id, title, description FROM positions ORDER BY id")
        positions = cur.fetchall()

        # Get user's existing votes
        cur.execute("SELECT position_id FROM votes WHERE user_id=?", (self.user["id"],))
        voted_positions = {row[0] for row in cur.fetchall()}
        conn.close()

        col_count = 2
        for idx, (pid, title, desc) in enumerate(positions):
            row, col = divmod(idx, col_count)

            card = tk.Frame(parent, bg=CARD, padx=20, pady=18,
                            highlightbackground="#e2e8f0", highlightthickness=1)
            card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8, ipadx=4)
            parent.grid_columnconfigure(col, weight=1, minsize=320)

            tk.Label(card, text=title, bg=CARD, fg=PRIMARY,
                     font=("Segoe UI", 14, "bold")).pack(anchor="w")
            tk.Label(card, text=desc or "", bg=CARD, fg=MUTED,
                     font=("Segoe UI", 9), wraplength=320,
                     justify="left").pack(anchor="w", pady=(4, 14))

            if pid in voted_positions:
                tk.Label(card, text="✓ You have voted",
                         bg=CARD, fg=SUCCESS,
                         font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))
                ttk.Button(card, text="View Candidates",
                           style="Accent.TButton",
                           command=lambda p=pid, t=title: self.open_candidates(p, t, True)
                           ).pack(fill="x")
            else:
                ttk.Button(card, text="View Candidates & Vote",
                           style="Primary.TButton",
                           command=lambda p=pid, t=title: self.open_candidates(p, t, False)
                           ).pack(fill="x")

    def open_candidates(self, position_id, position_title, already_voted):
        CandidatesWindow(self.root, self.db, self.user, position_id,
                         position_title, already_voted, self.refresh)

    def refresh(self):
        self.build()

    def logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to log out?"):
            self.on_logout()


class CandidatesWindow:
    def __init__(self, parent, db, user, position_id, position_title,
                 already_voted, on_close):
        self.db = db
        self.user = user
        self.position_id = position_id
        self.position_title = position_title
        self.already_voted = already_voted
        self.on_close = on_close
        self.selected_candidate = tk.IntVar(value=0)

        self.win = tk.Toplevel(parent)
        self.win.title(f"Candidates — {position_title}")
        self.win.configure(bg=BG)
        self.win.geometry("640x600")
        self.win.transient(parent)
        self.win.grab_set()

        self.build()

    def build(self):
        header = tk.Frame(self.win, bg=PRIMARY, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=self.position_title,
                 bg=PRIMARY, fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=20, pady=18)

        body = ttk.Frame(self.win, style="TFrame", padding=20)
        body.pack(fill="both", expand=True)

        if self.already_voted:
            ttk.Label(body, text="You have already voted for this position.",
                      style="Subtitle.TLabel").pack(anchor="w", pady=(0, 12))
        else:
            ttk.Label(body, text="Select your preferred candidate:",
                      style="Subtitle.TLabel").pack(anchor="w", pady=(0, 12))

        # Scrollable area
        canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        inner = ttk.Frame(canvas, style="TFrame")
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, full_name, manifesto FROM candidates WHERE position_id=? ORDER BY full_name",
            (self.position_id,)
        )
        candidates = cur.fetchall()

        # Find user's vote if already voted
        voted_for = None
        if self.already_voted:
            cur.execute(
                "SELECT candidate_id FROM votes WHERE user_id=? AND position_id=?",
                (self.user["id"], self.position_id)
            )
            r = cur.fetchone()
            if r:
                voted_for = r[0]
        conn.close()

        if not candidates:
            tk.Label(inner, text="No candidates registered for this position yet.",
                     bg=BG, fg=MUTED, font=("Segoe UI", 11, "italic")).pack(pady=40)
        else:
            for cid, name, manifesto in candidates:
                is_chosen = (cid == voted_for)
                bg_color = "#dcfce7" if is_chosen else CARD
                border = SUCCESS if is_chosen else "#e2e8f0"

                card = tk.Frame(inner, bg=bg_color, padx=16, pady=14,
                                highlightbackground=border, highlightthickness=2)
                card.pack(fill="x", pady=6, padx=2)

                top = tk.Frame(card, bg=bg_color)
                top.pack(fill="x")

                if not self.already_voted:
                    rb = tk.Radiobutton(top, text="", variable=self.selected_candidate,
                                        value=cid, bg=bg_color, activebackground=bg_color)
                    rb.pack(side="left")

                tk.Label(top, text=name, bg=bg_color, fg=PRIMARY,
                         font=("Segoe UI", 13, "bold")).pack(side="left", padx=(4, 0))

                if is_chosen:
                    tk.Label(top, text="  ✓ Your vote",
                             bg=bg_color, fg=SUCCESS,
                             font=("Segoe UI", 10, "bold")).pack(side="left")

                tk.Label(card,
                         text=manifesto or "No manifesto provided.",
                         bg=bg_color, fg=TEXT,
                         font=("Segoe UI", 10),
                         wraplength=540, justify="left").pack(anchor="w", pady=(6, 0))

        # Footer
        footer = ttk.Frame(self.win, style="TFrame", padding=(20, 10))
        footer.pack(fill="x")

        ttk.Button(footer, text="Close", style="Accent.TButton",
                   command=self.close).pack(side="right", padx=4)

        if not self.already_voted and candidates:
            election_open = self.db.get_setting("election_open") == "1"
            if election_open:
                ttk.Button(footer, text="Cast Vote", style="Success.TButton",
                           command=self.cast_vote).pack(side="right", padx=4)
            else:
                tk.Label(footer, text="Voting is currently closed.",
                         bg=BG, fg=DANGER,
                         font=("Segoe UI", 10, "bold")).pack(side="right", padx=8)

    def cast_vote(self):
        cid = self.selected_candidate.get()
        if not cid:
            messagebox.showwarning("Pick a candidate",
                                   "Please select a candidate before voting.",
                                   parent=self.win)
            return

        if not messagebox.askyesno("Confirm Vote",
                                    "Are you sure? Votes are final and cannot be changed.",
                                    parent=self.win):
            return

        try:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO votes (user_id, candidate_id, position_id, voted_at) VALUES (?, ?, ?, ?)",
                (self.user["id"], cid, self.position_id, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            messagebox.showinfo("Vote recorded",
                                "Your vote has been securely recorded. Thank you!",
                                parent=self.win)
            self.close()
        except sqlite3.IntegrityError:
            messagebox.showerror("Already voted",
                                 "You have already voted for this position.",
                                 parent=self.win)
            self.close()

    def close(self):
        self.win.destroy()
        self.on_close()


# ---------- Admin Dashboard ----------
class AdminDashboard:
    def __init__(self, root, db, user, on_logout):
        self.root = root
        self.db = db
        self.user = user
        self.on_logout = on_logout
        self.frame = None
        self.current_tab = None
        self.build()

    def build(self):
        if self.frame:
            self.frame.destroy()

        self.frame = ttk.Frame(self.root, style="TFrame")
        self.frame.pack(fill="both", expand=True)

        # Top bar
        topbar = tk.Frame(self.frame, bg=PRIMARY, height=64)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="🛡 Election Administration",
                 bg=PRIMARY, fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=24)

        right = tk.Frame(topbar, bg=PRIMARY)
        right.pack(side="right", padx=20)
        tk.Label(right, text=f"Admin: {self.user['name']}",
                 bg=PRIMARY, fg="white",
                 font=("Segoe UI", 11)).pack(side="left", padx=(0, 16))
        ttk.Button(right, text="Logout", style="Danger.TButton",
                   command=self.logout).pack(side="left")

        # Tabs
        nb = ttk.Notebook(self.frame)
        nb.pack(fill="both", expand=True, padx=16, pady=16)

        # Configure notebook style
        style = ttk.Style()
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 8), font=("Segoe UI", 10, "bold"))

        positions_tab = ttk.Frame(nb, style="TFrame", padding=16)
        candidates_tab = ttk.Frame(nb, style="TFrame", padding=16)
        results_tab = ttk.Frame(nb, style="TFrame", padding=16)
        voters_tab = ttk.Frame(nb, style="TFrame", padding=16)
        settings_tab = ttk.Frame(nb, style="TFrame", padding=16)

        nb.add(results_tab, text="📊 Results")
        nb.add(positions_tab, text="📋 Positions")
        nb.add(candidates_tab, text="👤 Candidates")
        nb.add(voters_tab, text="🎓 Voters")
        nb.add(settings_tab, text="⚙ Settings")

        self.build_results_tab(results_tab)
        self.build_positions_tab(positions_tab)
        self.build_candidates_tab(candidates_tab)
        self.build_voters_tab(voters_tab)
        self.build_settings_tab(settings_tab)

    # ----- Results -----
    def build_results_tab(self, parent):
        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(header, text="Live Election Results",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Refresh", style="Accent.TButton",
                   command=lambda: self.build_results_tab(parent)).pack(side="right")

        # Clear existing children except header (we just rebuilt header)
        for w in parent.winfo_children():
            if w is header:
                continue
            w.destroy()

        # Stats summary
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE role='student'")
        total_voters = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM votes")
        active_voters = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM votes")
        total_votes = cur.fetchone()[0]

        stats = ttk.Frame(parent, style="TFrame")
        stats.pack(fill="x", pady=(0, 16))
        self._stat_card(stats, "Registered Voters", total_voters, 0)
        self._stat_card(stats, "Voters Participated", active_voters, 1)
        self._stat_card(stats, "Total Votes Cast", total_votes, 2)
        turnout = f"{(active_voters / total_voters * 100):.1f}%" if total_voters else "0%"
        self._stat_card(stats, "Turnout", turnout, 3)

        # Scrollable results
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        inner = ttk.Frame(canvas, style="TFrame")
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        cur.execute("SELECT id, title FROM positions ORDER BY id")
        positions = cur.fetchall()

        for pid, ptitle in positions:
            self._render_position_results(inner, cur, pid, ptitle)

        conn.close()

    def _stat_card(self, parent, label, value, col):
        card = tk.Frame(parent, bg=CARD, padx=18, pady=14,
                        highlightbackground="#e2e8f0", highlightthickness=1)
        card.grid(row=0, column=col, sticky="ew", padx=4)
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(card, text=str(value), bg=CARD, fg=PRIMARY,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(card, text=label, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w")

    def _render_position_results(self, parent, cur, position_id, position_title):
        cur.execute("""
            SELECT c.id, c.full_name, COUNT(v.id) as vote_count
            FROM candidates c
            LEFT JOIN votes v ON v.candidate_id = c.id
            WHERE c.position_id = ?
            GROUP BY c.id, c.full_name
            ORDER BY vote_count DESC, c.full_name
        """, (position_id,))
        rows = cur.fetchall()

        section = tk.Frame(parent, bg=CARD, padx=20, pady=16,
                           highlightbackground="#e2e8f0", highlightthickness=1)
        section.pack(fill="x", pady=8, padx=2)

        tk.Label(section, text=position_title, bg=CARD, fg=PRIMARY,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))

        if not rows:
            tk.Label(section, text="No candidates registered.",
                     bg=CARD, fg=MUTED, font=("Segoe UI", 10, "italic")).pack(anchor="w")
            return

        total = sum(r[2] for r in rows)
        max_votes = max(r[2] for r in rows) if rows else 0

        for idx, (_, name, count) in enumerate(rows):
            pct = (count / total * 100) if total else 0
            is_leading = (count == max_votes and count > 0)

            row = tk.Frame(section, bg=CARD)
            row.pack(fill="x", pady=4)

            label_frame = tk.Frame(row, bg=CARD)
            label_frame.pack(fill="x")

            display_name = f"🏆 {name}" if is_leading else name
            color = SUCCESS if is_leading else TEXT
            tk.Label(label_frame, text=display_name, bg=CARD, fg=color,
                     font=("Segoe UI", 11, "bold")).pack(side="left")
            tk.Label(label_frame, text=f"{count} votes ({pct:.1f}%)",
                     bg=CARD, fg=MUTED,
                     font=("Segoe UI", 10)).pack(side="right")

            # Bar
            bar_bg = tk.Frame(row, bg="#e2e8f0", height=12)
            bar_bg.pack(fill="x", pady=(4, 0))
            bar_bg.pack_propagate(False)
            if count > 0:
                bar_color = SUCCESS if is_leading else ACCENT
                width_pct = (count / max_votes) if max_votes else 0
                fill = tk.Frame(bar_bg, bg=bar_color)
                fill.place(relwidth=width_pct, relheight=1)

    # ----- Positions -----
    def build_positions_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Manage Positions", style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="+ Add Position", style="Primary.TButton",
                   command=lambda: self.add_position(parent)).pack(side="right")

        cols = ("ID", "Title", "Description")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("ID", width=60, anchor="center")
        tree.column("Title", width=200)
        tree.column("Description", width=500)
        tree.pack(fill="both", expand=True, pady=(0, 10))

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT id, title, description FROM positions ORDER BY id")
        for row in cur.fetchall():
            tree.insert("", "end", values=row)
        conn.close()

        action_bar = ttk.Frame(parent, style="TFrame")
        action_bar.pack(fill="x")
        ttk.Button(action_bar, text="Edit Selected", style="Accent.TButton",
                   command=lambda: self.edit_position(tree, parent)).pack(side="left", padx=4)
        ttk.Button(action_bar, text="Delete Selected", style="Danger.TButton",
                   command=lambda: self.delete_position(tree, parent)).pack(side="left", padx=4)

    def add_position(self, parent_tab):
        title = simpledialog.askstring("New Position", "Position title:", parent=self.root)
        if not title:
            return
        desc = simpledialog.askstring("New Position", "Description (optional):",
                                      parent=self.root) or ""
        try:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute("INSERT INTO positions (title, description) VALUES (?, ?)",
                        (title.strip(), desc.strip()))
            conn.commit()
            conn.close()
            self.build_positions_tab(parent_tab)
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "A position with that title already exists.")

    def edit_position(self, tree, parent_tab):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a position to edit.")
            return
        vals = tree.item(sel[0])["values"]
        pid, current_title, current_desc = vals[0], vals[1], vals[2]

        new_title = simpledialog.askstring("Edit Position", "Title:",
                                           initialvalue=current_title, parent=self.root)
        if new_title is None:
            return
        new_desc = simpledialog.askstring("Edit Position", "Description:",
                                          initialvalue=current_desc, parent=self.root) or ""
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("UPDATE positions SET title=?, description=? WHERE id=?",
                    (new_title.strip(), new_desc.strip(), pid))
        conn.commit()
        conn.close()
        self.build_positions_tab(parent_tab)

    def delete_position(self, tree, parent_tab):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a position to delete.")
            return
        vals = tree.item(sel[0])["values"]
        pid, title = vals[0], vals[1]
        if not messagebox.askyesno(
            "Delete", f"Delete '{title}'?\nAll candidates and votes for this position will also be removed."
        ):
            return
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM votes WHERE position_id=?", (pid,))
        cur.execute("DELETE FROM candidates WHERE position_id=?", (pid,))
        cur.execute("DELETE FROM positions WHERE id=?", (pid,))
        conn.commit()
        conn.close()
        self.build_positions_tab(parent_tab)

    # ----- Candidates -----
    def build_candidates_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Manage Candidates", style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="+ Add Candidate", style="Primary.TButton",
                   command=lambda: self.add_candidate(parent)).pack(side="right")

        cols = ("ID", "Name", "Position", "Manifesto")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("ID", width=60, anchor="center")
        tree.column("Name", width=180)
        tree.column("Position", width=160)
        tree.column("Manifesto", width=400)
        tree.pack(fill="both", expand=True, pady=(0, 10))

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.full_name, p.title, c.manifesto
            FROM candidates c
            JOIN positions p ON c.position_id = p.id
            ORDER BY p.title, c.full_name
        """)
        for row in cur.fetchall():
            tree.insert("", "end", values=row)
        conn.close()

        action_bar = ttk.Frame(parent, style="TFrame")
        action_bar.pack(fill="x")
        ttk.Button(action_bar, text="Delete Selected", style="Danger.TButton",
                   command=lambda: self.delete_candidate(tree, parent)).pack(side="left", padx=4)

    def add_candidate(self, parent_tab):
        CandidateDialog(self.root, self.db, lambda: self.build_candidates_tab(parent_tab))

    def delete_candidate(self, tree, parent_tab):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a candidate to delete.")
            return
        vals = tree.item(sel[0])["values"]
        cid, name = vals[0], vals[1]
        if not messagebox.askyesno(
            "Delete", f"Delete candidate '{name}'?\nAll votes for this candidate will also be removed."
        ):
            return
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM votes WHERE candidate_id=?", (cid,))
        cur.execute("DELETE FROM candidates WHERE id=?", (cid,))
        conn.commit()
        conn.close()
        self.build_candidates_tab(parent_tab)

    # ----- Voters -----
    def build_voters_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Registered Voters", style="Title.TLabel").pack(side="left")

        cols = ("ID", "Student ID", "Name", "Role", "Registered", "Votes Cast")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("ID", width=50, anchor="center")
        tree.column("Student ID", width=120)
        tree.column("Name", width=200)
        tree.column("Role", width=80, anchor="center")
        tree.column("Registered", width=160)
        tree.column("Votes Cast", width=100, anchor="center")
        tree.pack(fill="both", expand=True)

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.student_id, u.full_name, u.role, u.created_at,
                   (SELECT COUNT(*) FROM votes WHERE user_id = u.id)
            FROM users u
            ORDER BY u.role DESC, u.created_at
        """)
        for row in cur.fetchall():
            created = row[4][:10] if row[4] else ""
            tree.insert("", "end", values=(row[0], row[1], row[2], row[3], created, row[5]))
        conn.close()

    # ----- Settings -----
    def build_settings_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        ttk.Label(parent, text="Election Settings", style="Title.TLabel").pack(anchor="w", pady=(0, 16))

        card = tk.Frame(parent, bg=CARD, padx=24, pady=20,
                        highlightbackground="#e2e8f0", highlightthickness=1)
        card.pack(fill="x", pady=(0, 16))

        is_open = self.db.get_setting("election_open") == "1"
        status_text = "🟢 Voting is OPEN" if is_open else "🔴 Voting is CLOSED"
        status_color = SUCCESS if is_open else DANGER

        tk.Label(card, text="Voting Status", bg=CARD, fg=PRIMARY,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(card, text=status_text, bg=CARD, fg=status_color,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 12))

        toggle_text = "Close Voting" if is_open else "Open Voting"
        toggle_style = "Danger.TButton" if is_open else "Success.TButton"
        ttk.Button(card, text=toggle_text, style=toggle_style,
                   command=lambda: self.toggle_voting(parent)).pack(anchor="w")

        # Danger zone
        dz = tk.Frame(parent, bg=CARD, padx=24, pady=20,
                      highlightbackground="#fca5a5", highlightthickness=1)
        dz.pack(fill="x")

        tk.Label(dz, text="⚠ Danger Zone", bg=CARD, fg=DANGER,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(dz, text="Clear all votes from the system. This cannot be undone.",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 12))
        ttk.Button(dz, text="Clear All Votes", style="Danger.TButton",
                   command=lambda: self.reset_votes(parent)).pack(anchor="w")

    def toggle_voting(self, parent):
        is_open = self.db.get_setting("election_open") == "1"
        new_value = "0" if is_open else "1"
        self.db.set_setting("election_open", new_value)
        self.build_settings_tab(parent)

    def reset_votes(self, parent):
        if not messagebox.askyesno(
            "Confirm Reset",
            "Are you absolutely sure?\nAll votes will be permanently deleted."
        ):
            return
        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM votes")
        conn.commit()
        conn.close()
        messagebox.showinfo("Reset complete", "All votes have been cleared.")

    def logout(self):
        if messagebox.askyesno("Logout", "Log out of the admin panel?"):
            self.on_logout()


class CandidateDialog:
    def __init__(self, parent, db, on_save):
        self.db = db
        self.on_save = on_save

        self.win = tk.Toplevel(parent)
        self.win.title("Add Candidate")
        self.win.configure(bg=BG)
        self.win.geometry("460x460")
        self.win.transient(parent)
        self.win.grab_set()

        ttk.Label(self.win, text="New Candidate",
                  style="Title.TLabel").pack(pady=(20, 4))

        card = tk.Frame(self.win, bg=CARD, padx=28, pady=22,
                        highlightbackground="#e2e8f0", highlightthickness=1)
        card.pack(padx=20, fill="both", expand=True, pady=(8, 16))

        tk.Label(card, text="Full Name", bg=CARD,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.name = ttk.Entry(card, font=("Segoe UI", 11))
        self.name.pack(fill="x", pady=(2, 12), ipady=3)

        tk.Label(card, text="Position", bg=CARD,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute("SELECT id, title FROM positions ORDER BY title")
        self.positions = cur.fetchall()
        conn.close()

        if not self.positions:
            tk.Label(card, text="(No positions exist — create one first)",
                     bg=CARD, fg=DANGER, font=("Segoe UI", 9)).pack(anchor="w")
            self.position_combo = None
        else:
            self.position_var = tk.StringVar()
            self.position_combo = ttk.Combobox(
                card, textvariable=self.position_var,
                values=[p[1] for p in self.positions],
                state="readonly", font=("Segoe UI", 11)
            )
            self.position_combo.current(0)
            self.position_combo.pack(fill="x", pady=(2, 12), ipady=3)

        tk.Label(card, text="Manifesto", bg=CARD,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.manifesto = tk.Text(card, height=6, font=("Segoe UI", 10),
                                 wrap="word", relief="solid", borderwidth=1)
        self.manifesto.pack(fill="both", expand=True, pady=(2, 12))

        ttk.Button(card, text="Save Candidate", style="Primary.TButton",
                   command=self.save).pack(fill="x")

    def save(self):
        name = self.name.get().strip()
        manifesto = self.manifesto.get("1.0", "end").strip()

        if not name:
            messagebox.showwarning("Missing", "Please enter the candidate's name.",
                                   parent=self.win)
            return
        if not self.position_combo:
            messagebox.showwarning("No positions", "Create a position first.",
                                   parent=self.win)
            return

        title = self.position_var.get()
        pos_id = next((p[0] for p in self.positions if p[1] == title), None)
        if not pos_id:
            messagebox.showerror("Error", "Invalid position.", parent=self.win)
            return

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO candidates (full_name, position_id, manifesto) VALUES (?, ?, ?)",
            (name, pos_id, manifesto)
        )
        conn.commit()
        conn.close()

        self.win.destroy()
        self.on_save()


# ---------- App Controller ----------
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Student Union Election System")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)

        self.db = Database()
        setup_styles()

        self.show_login()

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def show_login(self):
        self.clear()
        LoginWindow(self.root, self.db, self.on_login)

    def on_login(self, user):
        self.clear()
        if user["role"] == "admin":
            AdminDashboard(self.root, self.db, user, self.show_login)
        else:
            VoterDashboard(self.root, self.db, user, self.show_login)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
