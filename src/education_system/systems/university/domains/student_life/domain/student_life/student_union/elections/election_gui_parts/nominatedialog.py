"""Extracted class implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class NominateDialog:
    """Submit a candidacy nomination for an election in nomination phase.

    Replaces the standalone NominationDialog from
    ``student_union_gui/elections/election_core.py`` so the merged
    voter dashboard covers the full self-nomination workflow without
    the user needing a separate menu entry.
    """

    def __init__(self, parent, db, user, on_done):
        self.db = db
        self.user = user
        self.on_done = on_done
        self.election_data = {}

        self.win = tk.Toplevel(parent)
        self.win.title("Nominate Myself")
        self.win.configure(bg=BG)
        self.win.geometry("680x620")
        self.win.transient(parent)
        self.win.grab_set()

        self.build()

    def build(self):
        ttk.Label(self.win, text="Submit a Nomination",
                  style="Title.TLabel").pack(pady=(20, 4))
        ttk.Label(self.win,
                  text="Stand as a candidate in an election currently "
                       "accepting nominations.",
                  style="Subtitle.TLabel").pack(pady=(0, 16))

        card = tk.Frame(self.win, bg=CARD, padx=24, pady=20,
                        highlightbackground="#e2e8f0",
                        highlightthickness=1)
        card.pack(padx=20, fill="both", expand=True, pady=(0, 16))

        tk.Label(card, text="Election", bg=CARD,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.election_var = tk.StringVar()
        self.election_combo = ttk.Combobox(
            card, textvariable=self.election_var,
            state="readonly", font=("Segoe UI", 11))
        self.election_combo.pack(fill="x", pady=(2, 14), ipady=3)
        self._load_elections()

        tk.Label(card, text="Manifesto", bg=CARD,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(card,
                 text="Why should students vote for you? "
                      "(min. 100 characters)",
                 bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))
        self.manifesto = tk.Text(card, height=10, wrap="word",
                                 font=("Segoe UI", 10),
                                 relief="solid", borderwidth=1)
        self.manifesto.pack(fill="both", expand=True, pady=(0, 12))

        bar = tk.Frame(card, bg=CARD)
        bar.pack(fill="x")
        ttk.Button(bar, text="Cancel", style="Accent.TButton",
                   command=self.win.destroy).pack(side="right", padx=4)
        ttk.Button(bar, text="Submit Nomination", style="Primary.TButton",
                   command=self.submit).pack(side="right", padx=4)

    def _load_elections(self):
        try:
            conn = self.db.connect()
            rows = conn.execute(
                "SELECT id, title, COALESCE(department,'') "
                "FROM elections "
                "WHERE LOWER(COALESCE(status,''))='nomination' "
                "  AND COALESCE(nomination_end, date('now')) >= date('now') "
                "ORDER BY title").fetchall()
            conn.close()
        except sqlite3.OperationalError:
            rows = []
        if rows:
            self.election_data = {
                f"{pos} ({dept or 'All Departments'})": eid
                for eid, pos, dept in rows
            }
            self.election_combo['values'] = list(self.election_data.keys())
        else:
            self.election_data = {}
            self.election_combo['values'] = [
                "No elections currently accepting nominations"
            ]

    def submit(self):
        choice = self.election_var.get()
        if not choice or choice not in self.election_data:
            messagebox.showwarning(
                "Pick an election",
                "Please select an election before submitting.",
                parent=self.win)
            return
        manifesto = self.manifesto.get("1.0", "end").strip()
        if len(manifesto) < 100:
            messagebox.showwarning(
                "Manifesto too short",
                "Please write a manifesto of at least 100 characters.",
                parent=self.win)
            return

        sid = self.user.get('student_id') or self.user.get('username')
        eid = self.election_data[choice]
        try:
            conn = self.db.connect()
            cur = conn.cursor()
            # Reject duplicate self-nominations for the same election.
            existing = cur.execute(
                "SELECT id FROM election_candidates "
                "WHERE election_id = ? AND student_id = ?",
                (eid, sid)).fetchone()
            if existing:
                messagebox.showinfo(
                    "Already nominated",
                    "You're already standing in this election.",
                    parent=self.win)
                self.win.destroy()
                return
            cur.execute(
                "INSERT INTO election_candidates "
                "(election_id, student_id, manifesto, votes) "
                "VALUES (?, ?, ?, 0)",
                (eid, sid, manifesto))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(
                "Failed", f"Could not submit nomination:\n{e}",
                parent=self.win)
            return

        # The display label was "Position (Department)"; pull just the
        # position out for the notification.
        position_label = choice.split(" (", 1)[0]
        _send_candidate_email(
            self.db, 'candidate_nominated', {
                'position': position_label,
                'election_id': str(eid),
                'date_nominated': datetime.now().strftime('%Y-%m-%d'),
                'manifesto_preview': manifesto[:500],
            }, sid)

        messagebox.showinfo(
            "Submitted",
            "Your nomination has been submitted. Good luck!",
            parent=self.win)
        self.win.destroy()
        self.on_done()
