"""Methods __init__ through delete_candidate."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminDashboard:
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
        tk.Label(topbar, text="🛡 Election Administration",
                 bg=PRIMARY, fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=24)

        right = tk.Frame(topbar, bg=PRIMARY)
        right.pack(side="right", padx=20)
        tk.Label(right, text=f"Admin: {self.user.get('username','')}",
                 bg=PRIMARY, fg="white",
                 font=("Segoe UI", 11)).pack(side="left", padx=(0, 16))
        ttk.Button(right, text="Close", style="Danger.TButton",
                   command=self.on_logout).pack(side="left")

        nb = ttk.Notebook(self.frame)
        nb.pack(fill="both", expand=True, padx=16, pady=16)

        results_tab = ttk.Frame(nb, style="TFrame", padding=16)
        positions_tab = ttk.Frame(nb, style="TFrame", padding=16)
        candidates_tab = ttk.Frame(nb, style="TFrame", padding=16)
        campaigns_tab = ttk.Frame(nb, style="TFrame", padding=16)
        expenses_tab = ttk.Frame(nb, style="TFrame", padding=16)
        voters_tab = ttk.Frame(nb, style="TFrame", padding=16)
        settings_tab = ttk.Frame(nb, style="TFrame", padding=16)

        nb.add(results_tab,    text="📊 Results")
        nb.add(positions_tab,  text="📋 Positions")
        nb.add(candidates_tab, text="👤 Candidates")
        nb.add(campaigns_tab,  text="📣 Campaigns")
        nb.add(expenses_tab,   text="💷 Expenses")
        nb.add(voters_tab,     text="🎓 Voters")
        nb.add(settings_tab,   text="⚙ Settings")

        self.build_results_tab(results_tab)
        self.build_positions_tab(positions_tab)
        self.build_candidates_tab(candidates_tab)
        self.build_campaigns_tab(campaigns_tab)
        self.build_expenses_tab(expenses_tab)
        self.build_voters_tab(voters_tab)
        self.build_settings_tab(settings_tab)

    def build_results_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Live Election Results",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Refresh", style="Accent.TButton",
                   command=lambda: self.build_results_tab(parent)
                   ).pack(side="right")

        conn = self.db.connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM students "
            "WHERE LOWER(COALESCE(status,'active')) = 'active'")
        total_voters = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT voter_id) FROM election_votes")
        active_voters = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM election_votes")
        total_votes = cur.fetchone()[0]

        stats = ttk.Frame(parent, style="TFrame")
        stats.pack(fill="x", pady=(0, 16))
        self._stat_card(stats, "Eligible Voters", total_voters, 0)
        self._stat_card(stats, "Voters Participated", active_voters, 1)
        self._stat_card(stats, "Total Votes Cast", total_votes, 2)
        turnout = (f"{(active_voters / total_voters * 100):.1f}%"
                   if total_voters else "0%")
        self._stat_card(stats, "Turnout", turnout, 3)

        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical",
                               command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        inner = ttk.Frame(canvas, style="TFrame")
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        cur.execute(
            "SELECT election_id, position FROM union_elections "
            "ORDER BY election_id")
        for eid, ptitle in cur.fetchall():
            self._render_position_results(inner, cur, eid, ptitle)
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

    def _render_position_results(self, parent, cur, election_id, position_title):
        cur.execute(
            "SELECT c.id, "
            "       COALESCE(NULLIF(TRIM(s.first_name||' '||s.last_name),''), c.student_id), "
            "       COUNT(v.id) "
            "FROM election_candidates c "
            "LEFT JOIN students s ON s.student_id = c.student_id "
            "LEFT JOIN election_votes v ON v.candidate_id = c.id "
            "                            AND v.election_id = ? "
            "WHERE c.election_id = ? "
            "GROUP BY c.id, 2 "
            "ORDER BY 3 DESC, 2",
            (election_id, election_id))
        rows = cur.fetchall()

        section = tk.Frame(parent, bg=CARD, padx=20, pady=16,
                           highlightbackground="#e2e8f0",
                           highlightthickness=1)
        section.pack(fill="x", pady=8, padx=2)
        tk.Label(section, text=position_title, bg=CARD, fg=PRIMARY,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w",
                                                      pady=(0, 8))

        if not rows:
            tk.Label(section, text="No candidates registered.",
                     bg=CARD, fg=MUTED,
                     font=("Segoe UI", 10, "italic")).pack(anchor="w")
            return

        total = sum(r[2] for r in rows)
        max_votes = max(r[2] for r in rows) if rows else 0
        for _, name, count in rows:
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

            bar_bg = tk.Frame(row, bg="#e2e8f0", height=12)
            bar_bg.pack(fill="x", pady=(4, 0))
            bar_bg.pack_propagate(False)
            if count > 0:
                bar_color = SUCCESS if is_leading else ACCENT
                width_pct = (count / max_votes) if max_votes else 0
                fill = tk.Frame(bar_bg, bg=bar_color)
                fill.place(relwidth=width_pct, relheight=1)

    def build_positions_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Manage Elections",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="+ Add Election", style="Primary.TButton",
                   command=lambda: self.add_position(parent)
                   ).pack(side="right")

        cols = ("ID", "Position", "Status", "Description")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("ID", width=60, anchor="center")
        tree.column("Position", width=180)
        tree.column("Status", width=100, anchor="center")
        tree.column("Description", width=480)
        tree.pack(fill="both", expand=True, pady=(0, 10))

        conn = self.db.connect()
        for r in conn.execute(
                "SELECT election_id, position, COALESCE(status,'voting'), "
                "       COALESCE(description,'') "
                "FROM union_elections ORDER BY election_id"):
            tree.insert("", "end", values=r)
        conn.close()

        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text="Edit Selected", style="Accent.TButton",
                   command=lambda: self.edit_position(tree, parent)
                   ).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete Selected", style="Danger.TButton",
                   command=lambda: self.delete_position(tree, parent)
                   ).pack(side="left", padx=4)

    def add_position(self, parent_tab):
        title = simpledialog.askstring(
            "New Election", "Position title (e.g. President):",
            parent=self.root)
        if not title:
            return
        desc = simpledialog.askstring(
            "New Election", "Description (optional):",
            parent=self.root) or ""
        today = datetime.now().date().isoformat()
        conn = self.db.connect()
        try:
            conn.execute(
                "INSERT INTO union_elections "
                "(position, description, status, voting_start, voting_end) "
                "VALUES (?, ?, 'voting', ?, ?)",
                (title.strip(), desc.strip(), today, today))
            conn.commit()
        finally:
            conn.close()
        self.build_positions_tab(parent_tab)

    def edit_position(self, tree, parent_tab):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select an election to edit.")
            return
        vals = tree.item(sel[0])["values"]
        eid, current_title, current_status, current_desc = vals
        new_title = simpledialog.askstring(
            "Edit Election", "Position:",
            initialvalue=current_title, parent=self.root)
        if new_title is None:
            return
        new_status = simpledialog.askstring(
            "Edit Election",
            "Status (voting / nomination / completed / upcoming):",
            initialvalue=current_status, parent=self.root) or current_status
        new_desc = simpledialog.askstring(
            "Edit Election", "Description:",
            initialvalue=current_desc, parent=self.root) or ""
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE union_elections "
                "SET position=?, status=?, description=? "
                "WHERE election_id=?",
                (new_title.strip(), new_status.strip(),
                 new_desc.strip(), eid))
            conn.commit()
        finally:
            conn.close()
        self.build_positions_tab(parent_tab)

    def delete_position(self, tree, parent_tab):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select an election to delete.")
            return
        vals = tree.item(sel[0])["values"]
        eid, title = vals[0], vals[1]
        if not messagebox.askyesno(
                "Delete",
                f"Delete '{title}'?\nAll candidates and votes for this "
                f"election will also be removed."):
            return
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM election_votes WHERE election_id=?",
                         (eid,))
            conn.execute("DELETE FROM election_candidates "
                         "WHERE election_id=?", (eid,))
            conn.execute("DELETE FROM union_elections WHERE election_id=?",
                         (eid,))
            conn.commit()
        finally:
            conn.close()
        self.build_positions_tab(parent_tab)

    def build_candidates_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Manage Candidates",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="+ Add Candidate", style="Primary.TButton",
                   command=lambda: self.add_candidate(parent)
                   ).pack(side="right")

        cols = ("ID", "Student ID", "Name", "Position", "Manifesto")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("ID", width=60, anchor="center")
        tree.column("Student ID", width=110)
        tree.column("Name", width=180)
        tree.column("Position", width=160)
        tree.column("Manifesto", width=400)
        tree.pack(fill="both", expand=True, pady=(0, 10))

        conn = self.db.connect()
        rows = conn.execute(
            "SELECT c.id, c.student_id, "
            "       COALESCE(NULLIF(TRIM(s.first_name||' '||s.last_name),''), c.student_id), "
            "       e.position, COALESCE(c.manifesto,'') "
            "FROM election_candidates c "
            "LEFT JOIN students s ON s.student_id = c.student_id "
            "JOIN union_elections e ON e.election_id = c.election_id "
            "ORDER BY e.position, 3").fetchall()
        conn.close()
        for r in rows:
            tree.insert("", "end", values=r)

        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text="Delete Selected", style="Danger.TButton",
                   command=lambda: self.delete_candidate(tree, parent)
                   ).pack(side="left", padx=4)

    def add_candidate(self, parent_tab):
        CandidateDialog(self.root, self.db,
                        lambda: self.build_candidates_tab(parent_tab))

    def delete_candidate(self, tree, parent_tab):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a candidate to delete.")
            return
        vals = tree.item(sel[0])["values"]
        cid, sid, name = vals[0], vals[1], vals[2]
        if not messagebox.askyesno(
                "Delete",
                f"Delete candidate '{name}'?\nAll votes for this candidate "
                f"will also be removed."):
            return

        # Capture the position + election id BEFORE deleting, so the
        # notification email has full context.
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT c.election_id, e.position "
                "FROM election_candidates c "
                "JOIN union_elections e ON e.election_id = c.election_id "
                "WHERE c.id = ?", (cid,)).fetchone()
            election_id = row[0] if row else None
            position = row[1] if row else "(unknown position)"

            conn.execute("DELETE FROM election_votes WHERE candidate_id=?",
                         (cid,))
            conn.execute("DELETE FROM campaign_materials WHERE candidate_id=?",
                         (cid,))
            conn.execute("DELETE FROM campaign_expenses WHERE candidate_id=?",
                         (cid,))
            conn.execute("DELETE FROM election_candidates WHERE id=?",
                         (cid,))
            conn.commit()
        finally:
            conn.close()

        # Notify the (former) candidate that their candidacy was removed.
        removed_by = (self.user.get('username')
                      or self.user.get('email')
                      or 'Elections Admin')
        _send_candidate_email(
            self.db, 'candidate_removed', {
                'position': position,
                'election_id': str(election_id) if election_id else '—',
                'date_removed': datetime.now().strftime('%Y-%m-%d'),
                'removed_by': removed_by,
            }, sid)

        self.build_candidates_tab(parent_tab)
