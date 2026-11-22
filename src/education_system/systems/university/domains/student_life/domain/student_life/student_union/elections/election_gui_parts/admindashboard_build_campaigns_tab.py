"""Methods build_campaigns_tab through reset_votes."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminDashboard:
    def build_campaigns_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Campaign Materials",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Refresh", style="Accent.TButton",
                   command=lambda: self.build_campaigns_tab(parent)
                   ).pack(side="right")

        ttk.Label(
            parent,
            text="Pending campaign uploads from candidates. Approve or "
                 "reject before publication.",
            style="Subtitle.TLabel").pack(anchor="w", pady=(0, 12))

        cols = ("Material ID", "Candidate", "Type", "Status",
                "Upload Date", "Content")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Material ID", width=90, anchor="center")
        tree.column("Candidate", width=180)
        tree.column("Type", width=120)
        tree.column("Status", width=130, anchor="center")
        tree.column("Upload Date", width=120)
        tree.column("Content", width=400)
        tree.pack(fill="both", expand=True, pady=(0, 10))

        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT m.material_id, "
                "       COALESCE(NULLIF(TRIM(s.first_name||' '||s.last_name),''), c.student_id), "
                "       COALESCE(m.material_type,''), "
                "       COALESCE(m.status,'pending_approval'), "
                "       COALESCE(m.upload_date,''), "
                "       COALESCE(m.content,'') "
                "FROM campaign_materials m "
                "JOIN election_candidates c ON c.id = m.candidate_id "
                "LEFT JOIN students s ON s.student_id = c.student_id "
                "ORDER BY CASE LOWER(m.status) "
                "  WHEN 'pending_approval' THEN 0 ELSE 1 END, "
                "  m.material_id DESC").fetchall()
        except sqlite3.OperationalError:
            rows = []
        finally:
            conn.close()

        for r in rows:
            tree.insert("", "end", values=r)

        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text="Approve Selected", style="Success.TButton",
                   command=lambda: self._set_material_status(
                       tree, parent, 'approved')
                   ).pack(side="left", padx=4)
        ttk.Button(bar, text="Reject Selected", style="Danger.TButton",
                   command=lambda: self._set_material_status(
                       tree, parent, 'rejected')
                   ).pack(side="left", padx=4)

    def _set_material_status(self, tree, parent_tab, status):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a material to update.")
            return
        mid = tree.item(sel[0])["values"][0]
        reason = ""
        if status == 'rejected':
            reason = simpledialog.askstring(
                "Rejection reason", "Reason (optional):",
                parent=self.root) or ""
        reviewer = self.user.get('id') or self.user.get('user_id') or 0
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE campaign_materials "
                "SET status=?, reviewed_at=?, reviewed_by=?, "
                "    rejection_reason=? "
                "WHERE material_id=?",
                (status, datetime.now().isoformat(), reviewer, reason,
                 mid))
            conn.commit()
        finally:
            conn.close()
        self.build_campaigns_tab(parent_tab)

    def build_expenses_tab(self, parent):
        SPEND_LIMIT = 100.0
        for w in parent.winfo_children():
            w.destroy()
        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Campaign Expenses",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Refresh", style="Accent.TButton",
                   command=lambda: self.build_expenses_tab(parent)
                   ).pack(side="right")

        ttk.Label(
            parent,
            text=f"Per-candidate spending against the £{SPEND_LIMIT:.0f} "
                 f"campaign cap. Candidates flagged in red are over.",
            style="Subtitle.TLabel").pack(anchor="w", pady=(0, 12))

        cols = ("Candidate", "Position", "Total spent",
                "Items", "Status")
        tree = ttk.Treeview(parent, columns=cols, show="headings",
                            height=18)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Candidate", width=200)
        tree.column("Position", width=160)
        tree.column("Total spent", width=120, anchor="e")
        tree.column("Items", width=80, anchor="center")
        tree.column("Status", width=140, anchor="center")
        tree.pack(fill="both", expand=True)
        tree.tag_configure("over", background="#fee2e2")
        tree.tag_configure("ok", background="#dcfce7")

        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT c.id, "
                "       COALESCE(NULLIF(TRIM(s.first_name||' '||s.last_name),''), c.student_id), "
                "       e.title, "
                "       COALESCE(SUM(x.amount), 0), "
                "       COUNT(x.expense_id) "
                "FROM election_candidates c "
                "JOIN elections e ON e.id = c.election_id "
                "LEFT JOIN students s ON s.student_id = c.student_id "
                "LEFT JOIN campaign_expenses x ON x.candidate_id = c.id "
                "GROUP BY c.id, 2, e.title "
                "ORDER BY 4 DESC").fetchall()
        except sqlite3.OperationalError:
            rows = []
        finally:
            conn.close()

        for cid, name, position, total, items in rows:
            over = total > SPEND_LIMIT
            status = (f"OVER LIMIT (+£{total - SPEND_LIMIT:.2f})"
                      if over else f"Under cap (£{SPEND_LIMIT - total:.2f} left)")
            tree.insert("", "end",
                        values=(name, position, f"£{total:.2f}",
                                items, status),
                        tags=("over" if over else "ok",))

    def build_voters_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        header = ttk.Frame(parent, style="TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Eligible Voters",
                  style="Title.TLabel").pack(side="left")

        cols = ("Student ID", "Name", "Course", "Status", "Votes Cast")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Student ID", width=120)
        tree.column("Name", width=220)
        tree.column("Course", width=140)
        tree.column("Status", width=100, anchor="center")
        tree.column("Votes Cast", width=100, anchor="center")
        tree.pack(fill="both", expand=True)

        conn = self.db.connect()
        for r in conn.execute(
                "SELECT s.student_id, "
                "       COALESCE(NULLIF(TRIM(s.first_name||' '||s.last_name),''), s.student_id), "
                "       COALESCE(s.course,''), "
                "       COALESCE(s.status,'Active'), "
                "       (SELECT COUNT(*) FROM election_votes v "
                "         WHERE v.voter_id = s.student_id) "
                "FROM students s "
                "ORDER BY s.last_name, s.first_name"):
            tree.insert("", "end", values=r)
        conn.close()

    def build_settings_tab(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        ttk.Label(parent, text="Election Settings",
                  style="Title.TLabel").pack(anchor="w", pady=(0, 16))

        card = tk.Frame(parent, bg=CARD, padx=24, pady=20,
                        highlightbackground="#e2e8f0",
                        highlightthickness=1)
        card.pack(fill="x", pady=(0, 16))

        is_open = self.db.get_setting("election_open") == "1"
        status_text = "🟢 Voting is OPEN" if is_open else "🔴 Voting is CLOSED"
        status_color = SUCCESS if is_open else DANGER
        tk.Label(card, text="Voting Status (global toggle)", bg=CARD, fg=PRIMARY,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(card, text=status_text, bg=CARD, fg=status_color,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 4))
        tk.Label(card,
                 text="Per-election status is set on each row in the "
                      "Positions tab; this toggle gates the Voter Dashboard "
                      "regardless of individual election status.",
                 bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9), wraplength=600,
                 justify="left").pack(anchor="w", pady=(0, 12))
        toggle_text = "Close Voting" if is_open else "Open Voting"
        toggle_style = "Danger.TButton" if is_open else "Success.TButton"
        ttk.Button(card, text=toggle_text, style=toggle_style,
                   command=lambda: self.toggle_voting(parent)
                   ).pack(anchor="w")

        dz = tk.Frame(parent, bg=CARD, padx=24, pady=20,
                      highlightbackground="#fca5a5", highlightthickness=1)
        dz.pack(fill="x")
        tk.Label(dz, text="⚠ Danger Zone", bg=CARD, fg=DANGER,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(dz,
                 text="Clear all votes from every election. This cannot be "
                      "undone — campaign material and candidate records are "
                      "kept.",
                 bg=CARD, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 12))
        ttk.Button(dz, text="Clear All Votes", style="Danger.TButton",
                   command=lambda: self.reset_votes(parent)
                   ).pack(anchor="w")

    def toggle_voting(self, parent):
        is_open = self.db.get_setting("election_open") == "1"
        # Flip first, then notify on the close transition.
        self.db.set_setting("election_open", "0" if is_open else "1")
        if is_open:
            # OPEN → CLOSED: tell every active student that voting is
            # now closed. Bulk send via _bulk_email_active_students;
            # best-effort, non-blocking.
            closed_by = (self.user.get('username')
                         or self.user.get('email')
                         or 'Elections Admin')
            sent = _bulk_email_active_students(
                self.db, 'voting_closed', {
                    'closed_at':
                        datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'closed_by': closed_by,
                })
            messagebox.showinfo(
                "Voting closed",
                f"Voting has been closed. Notification emails queued "
                f"for {sent} active student(s).")
        self.build_settings_tab(parent)

    def reset_votes(self, parent):
        if not messagebox.askyesno(
                "Confirm Reset",
                "Are you absolutely sure?\nAll votes will be permanently "
                "deleted."):
            return
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM election_votes")
            conn.execute("UPDATE election_candidates SET votes = 0")
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo("Reset complete", "All votes have been cleared.")
