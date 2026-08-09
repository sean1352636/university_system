"""Extracted class implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CandidatesWindow:
    def __init__(self, parent, db, user, election_id, position_title,
                 already_voted, on_close):
        self.db = db
        self.user = user
        self.election_id = election_id
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
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=20,
                                                      pady=18)

        body = ttk.Frame(self.win, style="TFrame", padding=20)
        body.pack(fill="both", expand=True)

        if self.already_voted:
            ttk.Label(body, text="You have already voted for this position.",
                      style="Subtitle.TLabel").pack(anchor="w", pady=(0, 12))
        else:
            ttk.Label(body, text="Select your preferred candidate:",
                      style="Subtitle.TLabel").pack(anchor="w", pady=(0, 12))

        canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(body, orient="vertical",
                               command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        inner = ttk.Frame(canvas, style="TFrame")
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT c.id, c.student_id, "
            "       COALESCE(NULLIF(TRIM(s.first_name||' '||s.last_name),''), c.student_id), "
            "       COALESCE(c.manifesto,'') "
            "FROM election_candidates c "
            "LEFT JOIN students s ON s.student_id = c.student_id "
            "WHERE c.election_id = ? "
            "ORDER BY 3",
            (self.election_id,))
        candidates = cur.fetchall()

        voter_id = self.user.get('student_id') or self.user.get('username')
        voted_for = None
        if self.already_voted:
            r = cur.execute(
                "SELECT candidate_id FROM election_votes "
                "WHERE voter_id=? AND election_id=?",
                (voter_id, self.election_id)).fetchone()
            if r:
                voted_for = r[0]
        conn.close()

        if not candidates:
            tk.Label(inner,
                     text="No candidates registered for this position yet.",
                     bg=BG, fg=MUTED,
                     font=("Segoe UI", 11, "italic")).pack(pady=40)
        else:
            for cid, sid, name, manifesto in candidates:
                is_chosen = (cid == voted_for)
                bg_color = "#dcfce7" if is_chosen else CARD
                border = SUCCESS if is_chosen else "#e2e8f0"

                card = tk.Frame(inner, bg=bg_color, padx=16, pady=14,
                                highlightbackground=border,
                                highlightthickness=2)
                card.pack(fill="x", pady=6, padx=2)

                top = tk.Frame(card, bg=bg_color)
                top.pack(fill="x")

                if not self.already_voted:
                    rb = tk.Radiobutton(top, text="",
                                        variable=self.selected_candidate,
                                        value=cid, bg=bg_color,
                                        activebackground=bg_color)
                    rb.pack(side="left")

                tk.Label(top, text=name, bg=bg_color, fg=PRIMARY,
                         font=("Segoe UI", 13, "bold")).pack(side="left",
                                                              padx=(4, 0))
                tk.Label(top, text=f"  ({sid})", bg=bg_color, fg=MUTED,
                         font=("Segoe UI", 10)).pack(side="left")

                if is_chosen:
                    tk.Label(top, text="  ✓ Your vote",
                             bg=bg_color, fg=SUCCESS,
                             font=("Segoe UI", 10, "bold")).pack(side="left")

                tk.Label(card,
                         text=manifesto or "No manifesto provided.",
                         bg=bg_color, fg=TEXT,
                         font=("Segoe UI", 10),
                         wraplength=540, justify="left").pack(anchor="w",
                                                               pady=(6, 0))

        footer = ttk.Frame(self.win, style="TFrame", padding=(20, 10))
        footer.pack(fill="x")
        ttk.Button(footer, text="Close", style="Accent.TButton",
                   command=self.close).pack(side="right", padx=4)

        if not self.already_voted and candidates:
            if self.db.get_setting("election_open") == "1":
                ttk.Button(footer, text="Cast Vote", style="Success.TButton",
                           command=self.cast_vote).pack(side="right", padx=4)
            else:
                tk.Label(footer, text="Voting is currently closed.",
                         bg=BG, fg=DANGER,
                         font=("Segoe UI", 10, "bold")).pack(side="right",
                                                              padx=8)

    def cast_vote(self):
        cid = self.selected_candidate.get()
        if not cid:
            messagebox.showwarning(
                "Pick a candidate",
                "Please select a candidate before voting.",
                parent=self.win)
            return
        if not messagebox.askyesno(
                "Confirm Vote",
                "Are you sure? Votes are final and cannot be changed.",
                parent=self.win):
            return
        voter_id = self.user.get('student_id') or self.user.get('username')
        vote_time = datetime.now().isoformat(timespec='seconds')
        try:
            conn = self.db.connect()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO election_votes "
                "(election_id, voter_id, candidate_id, vote_time) "
                "VALUES (?, ?, ?, ?)",
                (self.election_id, voter_id, cid, vote_time))
            # Keep election_candidates.votes in sync so reports that
            # read it directly (e.g. analytics) stay accurate.
            cur.execute(
                "UPDATE election_candidates "
                "SET votes = COALESCE(votes,0) + 1 WHERE id = ?", (cid,))
            # Look up the candidate's display name for the receipt;
            # falls back to the chosen candidate's id.
            row = cur.execute(
                "SELECT COALESCE(NULLIF(TRIM(s.first_name||' '||s.last_name),''), "
                "                c.student_id) "
                "FROM election_candidates c "
                "LEFT JOIN students s ON s.student_id = c.student_id "
                "WHERE c.id = ?", (cid,)).fetchone()
            candidate_name = row[0] if row else f"#{cid}"
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Already voted",
                "You have already voted for this position.",
                parent=self.win)
            self.close()
            return

        # Send a confirmation receipt to the voter (best-effort).
        _send_candidate_email(
            self.db, 'vote_confirmation', {
                'position': self.position_title,
                'election_id': str(self.election_id),
                'candidate_name': candidate_name,
                'vote_time': vote_time,
            }, voter_id)

        messagebox.showinfo(
            "Vote recorded",
            "Your vote has been securely recorded. A confirmation "
            "email has been sent. Thank you!",
            parent=self.win)
        self.close()

    def close(self):
        self.win.destroy()
        self.on_close()
