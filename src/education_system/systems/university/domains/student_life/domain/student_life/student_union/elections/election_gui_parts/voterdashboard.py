"""Extracted class implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class VoterDashboard:
    def __init__(self, root, db, user, on_logout):
        self.root = root
        self.db = db
        self.user = user
        self.on_logout = on_logout
        self.frame = None
        self.build()

    def build(self):
        if self.frame:
            self.frame.destroy()

        self.frame = ttk.Frame(self.root, style="TFrame")
        self.frame.pack(fill="both", expand=True)

        topbar = tk.Frame(self.frame, bg=PRIMARY, height=64)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        tk.Label(topbar, text="🎓 Student Union Elections",
                 bg=PRIMARY, fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=24)

        right = tk.Frame(topbar, bg=PRIMARY)
        right.pack(side="right", padx=20)
        tk.Label(right, text=f"  {self.user.get('name') or self.user.get('username') or self.user.get('student_id', '')}",
                 bg=PRIMARY, fg="white",
                 font=("Segoe UI", 11)).pack(side="left", padx=(0, 16))
        ttk.Button(right, text="Close", style="Danger.TButton",
                   command=self.on_logout).pack(side="left")

        content = ttk.Frame(self.frame, style="TFrame", padding=24)
        content.pack(fill="both", expand=True)

        if self.db.get_setting("election_open") != "1":
            banner = tk.Frame(content, bg="#fef3c7", padx=14, pady=10,
                              highlightbackground="#fbbf24",
                              highlightthickness=1)
            banner.pack(fill="x", pady=(0, 16))
            tk.Label(banner,
                     text="⚠ Voting is currently closed by the administrator.",
                     bg="#fef3c7", fg="#92400e",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")

        title_row = ttk.Frame(content, style="TFrame")
        title_row.pack(fill="x")
        ttk.Label(title_row, text="Open Elections",
                  style="Title.TLabel").pack(side="left")
        # Nominate-Myself entry point — surfaces the same workflow that
        # was previously buried in the separate "Elections & Voting"
        # dialog. Only shows when the user looks like a student.
        if not _is_admin_user(self.user):
            ttk.Button(title_row, text="📝 Nominate Myself",
                       style="Accent.TButton",
                       command=self.nominate_self).pack(side="right")
        ttk.Label(
            content,
            text="Select a position below to view candidates and cast your vote.",
            style="Subtitle.TLabel").pack(anchor="w", pady=(2, 18))

        canvas = tk.Canvas(content, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(content, orient="vertical",
                               command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        grid_frame = ttk.Frame(canvas, style="TFrame")
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        grid_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        self.render_positions(grid_frame)

    def render_positions(self, parent):
        conn = self.db.connect()
        cur = conn.cursor()
        # Only surface elections the admin has marked as actively voting.
        cur.execute(
            "SELECT id, title, COALESCE(description,'') "
            "FROM elections "
            "WHERE LOWER(COALESCE(status,'')) IN ('voting','open') "
            "ORDER BY id")
        positions = cur.fetchall()

        voter_id = self.user.get('student_id') or self.user.get('username')
        cur.execute(
            "SELECT election_id FROM election_votes WHERE voter_id=?",
            (voter_id,))
        voted = {r[0] for r in cur.fetchall()}
        conn.close()

        if not positions:
            tk.Label(parent,
                     text="No elections are currently open. Check back later.",
                     bg=BG, fg=MUTED,
                     font=("Segoe UI", 11, "italic")).pack(pady=40)
            return

        col_count = 2
        for idx, (pid, title, desc) in enumerate(positions):
            row, col = divmod(idx, col_count)
            card = tk.Frame(parent, bg=CARD, padx=20, pady=18,
                            highlightbackground="#e2e8f0",
                            highlightthickness=1)
            card.grid(row=row, column=col, sticky="nsew",
                      padx=8, pady=8, ipadx=4)
            parent.grid_columnconfigure(col, weight=1, minsize=320)

            tk.Label(card, text=title, bg=CARD, fg=PRIMARY,
                     font=("Segoe UI", 14, "bold")).pack(anchor="w")
            tk.Label(card, text=desc or "", bg=CARD, fg=MUTED,
                     font=("Segoe UI", 9), wraplength=320,
                     justify="left").pack(anchor="w", pady=(4, 14))

            if pid in voted:
                tk.Label(card, text="✓ You have voted",
                         bg=CARD, fg=SUCCESS,
                         font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                              pady=(0, 8))
                ttk.Button(card, text="View Candidates",
                           style="Accent.TButton",
                           command=lambda p=pid, t=title:
                               self.open_candidates(p, t, True)
                           ).pack(fill="x")
            else:
                ttk.Button(card, text="View Candidates & Vote",
                           style="Primary.TButton",
                           command=lambda p=pid, t=title:
                               self.open_candidates(p, t, False)
                           ).pack(fill="x")

    def open_candidates(self, election_id, position_title, already_voted):
        CandidatesWindow(self.root, self.db, self.user,
                         election_id, position_title,
                         already_voted, self.refresh)

    def nominate_self(self):
        NominateDialog(self.root, self.db, self.user, self.refresh)

    def refresh(self):
        self.build()
