"""Extracted class implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CandidateDialog:
    """Bind a real student record to an election as a candidate.

    The standalone version of this dialog took a free-text "Full Name";
    in the merged version we instead require selecting an existing
    student so the candidacy joins back to the central students table.
    """

    def __init__(self, parent, db, on_save):
        self.db = db
        self.on_save = on_save

        self.win = tk.Toplevel(parent)
        self.win.title("Add Candidate")
        self.win.configure(bg=BG)
        self.win.geometry("520x520")
        self.win.transient(parent)
        self.win.grab_set()

        ttk.Label(self.win, text="New Candidate",
                  style="Title.TLabel").pack(pady=(20, 4))

        card = tk.Frame(self.win, bg=CARD, padx=28, pady=22,
                        highlightbackground="#e2e8f0",
                        highlightthickness=1)
        card.pack(padx=20, fill="both", expand=True, pady=(8, 16))

        # Student picker
        tk.Label(card, text="Student", bg=CARD,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        conn = self.db.connect()
        self.students = conn.execute(
            "SELECT student_id, "
            "       COALESCE(NULLIF(TRIM(first_name||' '||last_name),''), student_id) "
            "FROM students ORDER BY last_name, first_name").fetchall()
        self.elections = conn.execute(
            "SELECT id, title FROM elections "
            "ORDER BY title").fetchall()
        conn.close()

        if not self.students:
            tk.Label(card, text="(No students in the system — import "
                                "students first.)",
                     bg=CARD, fg=DANGER,
                     font=("Segoe UI", 9)).pack(anchor="w")
            self.student_combo = None
        else:
            self.student_var = tk.StringVar()
            self.student_combo = ttk.Combobox(
                card, textvariable=self.student_var,
                values=[f"{sid} — {name}" for sid, name in self.students],
                state="readonly", font=("Segoe UI", 11))
            self.student_combo.current(0)
            self.student_combo.pack(fill="x", pady=(2, 12), ipady=3)

        # Position picker
        tk.Label(card, text="Position", bg=CARD,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        if not self.elections:
            tk.Label(card, text="(No elections yet — create one first.)",
                     bg=CARD, fg=DANGER,
                     font=("Segoe UI", 9)).pack(anchor="w")
            self.election_combo = None
        else:
            self.election_var = tk.StringVar()
            self.election_combo = ttk.Combobox(
                card, textvariable=self.election_var,
                values=[p[1] for p in self.elections],
                state="readonly", font=("Segoe UI", 11))
            self.election_combo.current(0)
            self.election_combo.pack(fill="x", pady=(2, 12), ipady=3)

        # Manifesto
        tk.Label(card, text="Manifesto", bg=CARD,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.manifesto = tk.Text(card, height=6, font=("Segoe UI", 10),
                                 wrap="word", relief="solid", borderwidth=1)
        self.manifesto.pack(fill="both", expand=True, pady=(2, 12))

        ttk.Button(card, text="Save Candidate", style="Primary.TButton",
                   command=self.save).pack(fill="x")

    def save(self):
        if not self.student_combo or not self.election_combo:
            messagebox.showwarning(
                "Missing prerequisite",
                "Need at least one student and one election before "
                "adding a candidate.",
                parent=self.win)
            return
        sid_label = self.student_var.get()
        sid = sid_label.split(" — ", 1)[0] if sid_label else ""
        position_title = self.election_var.get()
        eid = next((e[0] for e in self.elections
                    if e[1] == position_title), None)
        manifesto = self.manifesto.get("1.0", "end").strip()

        if not (sid and eid):
            messagebox.showerror("Error", "Pick a student and a position.",
                                 parent=self.win)
            return
        try:
            conn = self.db.connect()
            conn.execute(
                "INSERT INTO election_candidates "
                "(election_id, student_id, manifesto, votes) "
                "VALUES (?, ?, ?, 0)",
                (eid, sid, manifesto))
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError as e:
            messagebox.showerror("DB error", str(e), parent=self.win)
            return

        # Notify the candidate (best-effort; insert is already committed).
        _send_candidate_email(
            self.db, 'candidate_nominated', {
                'position': position_title,
                'election_id': str(eid),
                'date_nominated': datetime.now().strftime('%Y-%m-%d'),
                'manifesto_preview': (manifesto or '(no manifesto provided)')[:500],
            }, sid)

        self.win.destroy()
        self.on_save()
