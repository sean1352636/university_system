"""
Student Union Elections — GUI

Merger of the standalone Tk election app (originally in /add/voting_system.py)
and the university system's existing election data model
(union_elections / election_candidates / election_votes / campaign_*).

What changed vs. the standalone app:
  * Backed by the central DB (DEFAULT_DB_PATH) instead of election.db.
  * Login removed — uses the main GUI's authenticated user via get_global_auth().
  * Self-registration dropped; voters are real students from the students table.
  * Candidate dialog binds to a student_id (drop-down of registered students)
    instead of a free-text "Full Name", so candidacy is tied to the central
    student record.
  * "Positions" map onto union_elections rows; manage them as elections.
  * Two extra admin tabs surface data the central model already has but the
    standalone UI didn't: Campaign Materials (approve/reject pending uploads)
    and Campaign Expenses (per-candidate totals against the £100 spend cap).

What stayed the same:
  * The polished Tk UI: cards, themed buttons, scrollable dashboards,
    treeviews. The /add app's visual language was the strong half of the
    merge — only the data layer underneath has been replaced.
"""

# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the package and put it on sys.path.
import os
import sys

if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(
            os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

from education_system.university_system.modules.shared.constants.paths import (
    DEFAULT_DB_PATH,
)


# Optional auth bootstrap from EDU_AUTH_* env vars (set by main_gui's
# subprocess launcher). If running standalone with no parent, we'll
# fall back to a guard message.
def _bootstrap_auth_from_env():
    user_id = os.environ.get('EDU_AUTH_USER_ID')
    username = os.environ.get('EDU_AUTH_USERNAME')
    if not (user_id or username):
        return
    perms = [p for p in os.environ.get(
        'EDU_AUTH_PERMISSIONS', '').split(',') if p]
    current_user = {
        'id': user_id or None,
        'user_id': user_id or None,
        'username': username or '',
        'role': os.environ.get('EDU_AUTH_ROLE', '') or '',
        'email': os.environ.get('EDU_AUTH_EMAIL', '') or '',
        'permissions': perms,
    }
    try:
        from types import SimpleNamespace

        def _check(perm, _u=current_user):
            return perm in _u['permissions']
        shim = SimpleNamespace(
            current_user=current_user,
            user_role=current_user['role'],
            check_permission=_check,
            is_authenticated=True,
        )
        from education_system.university_system.infrastructure.auth import (
            set_global_auth,
        )
        set_global_auth(shim)
        try:
            from education_system.university_system.infrastructure.shared_context import (  # noqa: E501
                set_auth as _shared_set_auth,
            )
            _shared_set_auth(shim)
        except Exception:
            pass
    except Exception:
        pass


_bootstrap_auth_from_env()


# ---------- Database Layer ----------
class Database:
    """Adapter between the standalone UI's vocabulary and the central tables.

    Methods are intentionally thin and lean on direct SQL inside dashboard
    code; this class owns connection handling, schema bootstrap, and
    settings only. Mappings used throughout the file:

        positions  → union_elections (election_id, position, status,
                                      description [added idempotently])
        candidates → election_candidates joined with students for the
                     display name; ``election_candidates.student_id``
                     is the link to the real student record
        votes      → election_votes (voter_id is a student_id)
        settings   → union_voting_settings (key, value) — created here,
                     used for the global "election_open" toggle that
                     gates the Voter Dashboard
    """

    def __init__(self):
        self.db_path = str(DEFAULT_DB_PATH)
        self._ensure_schema()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self):
        """Idempotent: add the description column to union_elections,
        create the settings + audit table, install the per-voter
        uniqueness index. Safe to call repeatedly."""
        conn = self.connect()
        try:
            stmts = (
                # Description text on each election (the standalone UI
                # had it in its `positions` table; central schema lacks it).
                "ALTER TABLE union_elections ADD COLUMN description TEXT",
                # Free-form key/value settings used by this GUI.
                "CREATE TABLE IF NOT EXISTS union_voting_settings ("
                "  key TEXT PRIMARY KEY, value TEXT)",
                # One vote per voter per election.
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "  idx_election_votes_uniq "
                "  ON election_votes(election_id, voter_id)",
            )
            for stmt in stmts:
                try:
                    conn.execute(stmt)
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # column/index already present
            # Default the global toggle to open.
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO union_voting_settings "
                    "(key, value) VALUES ('election_open', '1')")
                conn.commit()
            except sqlite3.OperationalError:
                pass
        finally:
            conn.close()

    def get_setting(self, key):
        conn = self.connect()
        try:
            r = conn.execute(
                "SELECT value FROM union_voting_settings WHERE key=?",
                (key,)).fetchone()
            return r[0] if r else None
        finally:
            conn.close()

    def set_setting(self, key, value):
        conn = self.connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO union_voting_settings "
                "(key, value) VALUES (?, ?)",
                (key, value))
            conn.commit()
        finally:
            conn.close()


# ---------- Styling ----------
PRIMARY = "#1e3a8a"
ACCENT = "#3b82f6"
SUCCESS = "#16a34a"
DANGER = "#dc2626"
WARN = "#d97706"
BG = "#f1f5f9"
CARD = "#ffffff"
TEXT = "#0f172a"
MUTED = "#64748b"


def setup_styles():
    style = ttk.Style()
    style.theme_use("clam")

    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD, relief="flat")
    style.configure("TLabel", background=BG, foreground=TEXT,
                    font=("Segoe UI", 10))
    style.configure("Card.TLabel", background=CARD, foreground=TEXT,
                    font=("Segoe UI", 10))
    style.configure("Title.TLabel", background=BG, foreground=PRIMARY,
                    font=("Segoe UI", 20, "bold"))
    style.configure("Subtitle.TLabel", background=BG, foreground=MUTED,
                    font=("Segoe UI", 11))
    style.configure("Heading.TLabel", background=CARD, foreground=PRIMARY,
                    font=("Segoe UI", 14, "bold"))
    style.configure("Muted.TLabel", background=CARD, foreground=MUTED,
                    font=("Segoe UI", 9))

    style.configure("Primary.TButton", background=PRIMARY, foreground="white",
                    font=("Segoe UI", 10, "bold"),
                    padding=(16, 10), borderwidth=0)
    style.map("Primary.TButton", background=[("active", ACCENT)])

    style.configure("Accent.TButton", background=ACCENT, foreground="white",
                    font=("Segoe UI", 10, "bold"),
                    padding=(14, 8), borderwidth=0)
    style.map("Accent.TButton", background=[("active", PRIMARY)])

    style.configure("Success.TButton", background=SUCCESS, foreground="white",
                    font=("Segoe UI", 10, "bold"),
                    padding=(14, 8), borderwidth=0)
    style.map("Success.TButton", background=[("active", "#15803d")])

    style.configure("Danger.TButton", background=DANGER, foreground="white",
                    font=("Segoe UI", 10, "bold"),
                    padding=(14, 8), borderwidth=0)
    style.map("Danger.TButton", background=[("active", "#b91c1c")])

    style.configure("TEntry", fieldbackground="white", padding=8)
    style.configure("Treeview", background="white", fieldbackground="white",
                    rowheight=28, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", background=PRIMARY, foreground="white",
                    font=("Segoe UI", 10, "bold"), padding=8)
    style.map("Treeview", background=[("selected", ACCENT)])

    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(16, 8),
                    font=("Segoe UI", 10, "bold"))


# ---------- Helpers ----------
def _full_name(first, last, fallback=""):
    """Compose 'first last' from possibly-None columns; fall back to id."""
    s = " ".join(p for p in (first or "", last or "") if p).strip()
    return s or fallback


def _is_admin_user(user):
    role = (user or {}).get('role', '').lower()
    return role in ('admin', 'superadmin', 'staff', 'instructor')


def _student_contact(db, student_id):
    """Look up a student's email + display name from the central
    ``students`` table. Returns ``(email_or_None, display_name)``.

    Display name falls back to ``student_id`` when first/last names
    aren't populated, so emails always have something to address.
    """
    if not student_id:
        return None, ""
    try:
        conn = db.connect()
        row = conn.execute(
            "SELECT email_address, first_name, last_name "
            "FROM students WHERE student_id = ?",
            (student_id,)).fetchone()
        conn.close()
    except sqlite3.Error:
        return None, str(student_id)
    if not row:
        return None, str(student_id)
    email, first, last = row
    name = _full_name(first, last, fallback=str(student_id))
    return (email or None), name


def _send_candidate_email(db, template_name, template_vars, student_id):
    """Render a student_union/* template and queue it for one student.

    Looks up the student's email_address from the central ``students``
    table, renders the template via shared template_utils, queues via
    shared.utils.email_service.queue_email. Silently no-ops on missing
    email/template/infra so the caller's primary action is never
    blocked. Returns True on a successful queue.
    """
    email, name = _student_contact(db, student_id)
    if not email:
        return False
    full_vars = {
        'student_name': name,
        'student_id': str(student_id),
        **(template_vars or {}),
    }
    try:
        from education_system.university_system.infrastructure.email.template_utils import (  # noqa: E501
            render_template,
        )
        subject, body = render_template(
            f'student_union/{template_name}', full_vars)
        if not (subject and body):
            return False
    except Exception:
        return False
    try:
        from education_system.university_system.modules.shared.utils.email_service import (  # noqa: E501
            queue_email,
        )
        return bool(queue_email(email, subject, body))
    except Exception:
        return False


def _bulk_email_active_students(db, template_name, template_vars):
    """Render ``student_union/<template_name>`` once per active student
    and queue it. Used for whole-cohort notifications such as the
    voting-closed broadcast.

    Returns the count of successfully queued emails.
    """
    try:
        from education_system.university_system.infrastructure.email.template_utils import (  # noqa: E501
            render_template,
        )
        from education_system.university_system.modules.shared.utils.email_service import (  # noqa: E501
            queue_email,
        )
    except Exception:
        return 0

    try:
        conn = db.connect()
        rows = conn.execute(
            "SELECT student_id, "
            "       COALESCE(email_address,''), "
            "       COALESCE(NULLIF(TRIM(first_name||' '||last_name),''), "
            "                student_id) "
            "FROM students "
            "WHERE LOWER(COALESCE(status,'active')) = 'active' "
            "  AND COALESCE(email_address,'') <> ''").fetchall()
        conn.close()
    except sqlite3.Error:
        return 0

    sent = 0
    for sid, email, name in rows:
        full_vars = {
            'student_name': name,
            'student_id': str(sid),
            **(template_vars or {}),
        }
        try:
            subject, body = render_template(
                f'student_union/{template_name}', full_vars)
            if not (subject and body):
                continue
            if queue_email(email, subject, body):
                sent += 1
        except Exception:
            continue
    return sent


# ---------- Voter Dashboard ----------
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
            "SELECT election_id, position, COALESCE(description,'') "
            "FROM union_elections "
            "WHERE LOWER(COALESCE(status,'')) IN ('voting','open') "
            "ORDER BY election_id")
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


# ---------- Self-nomination dialog ----------
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
                "SELECT election_id, position, COALESCE(department,'') "
                "FROM union_elections "
                "WHERE LOWER(COALESCE(status,''))='nomination' "
                "  AND COALESCE(nomination_end, date('now')) >= date('now') "
                "ORDER BY position").fetchall()
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


# ---------- Admin Dashboard ----------
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

    # ----- Results -----
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

    # ----- Positions -----
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

    # ----- Candidates -----
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

    # ----- Campaigns -----
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

    # ----- Expenses -----
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
                "       e.position, "
                "       COALESCE(SUM(x.amount), 0), "
                "       COUNT(x.expense_id) "
                "FROM election_candidates c "
                "JOIN union_elections e ON e.election_id = c.election_id "
                "LEFT JOIN students s ON s.student_id = c.student_id "
                "LEFT JOIN campaign_expenses x ON x.candidate_id = c.id "
                "GROUP BY c.id, 2, e.position "
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

    # ----- Voters -----
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

    # ----- Settings -----
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


# ---------- Add-Candidate dialog ----------
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
            "SELECT election_id, position FROM union_elections "
            "ORDER BY position").fetchall()
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


# ---------- App Controller ----------
class App:
    """Auth-aware launcher: dispatches to the admin or voter dashboard
    based on the logged-in user's role. No login window — this assumes
    the parent process has already authenticated.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Student Union Election System")
        self.root.geometry("1200x780")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)

        self.db = Database()
        setup_styles()

        self.user = self._resolve_user()
        if not self.user:
            self._show_no_auth()
        else:
            self._dispatch()

    def _resolve_user(self):
        """Pull the logged-in user from the global auth, or fall back to
        env vars (already consumed by _bootstrap_auth_from_env). Returns
        a dict with at least 'username', 'role', and ideally 'student_id'.
        """
        try:
            from education_system.university_system.infrastructure.auth import (  # noqa: E501
                get_global_auth,
            )
            ga = get_global_auth()
            cu = getattr(ga, 'current_user', None) if ga else None
            if cu:
                return {
                    'id': cu.get('id') or cu.get('user_id'),
                    'user_id': cu.get('user_id') or cu.get('id'),
                    'username': cu.get('username', ''),
                    'role': cu.get('role', ''),
                    'email': cu.get('email', ''),
                    'student_id': cu.get('student_id')
                                  or cu.get('username', ''),
                    'name': cu.get('name')
                            or cu.get('username', ''),
                }
        except Exception:
            pass
        return None

    def _show_no_auth(self):
        for w in self.root.winfo_children():
            w.destroy()
        outer = ttk.Frame(self.root, style="TFrame")
        outer.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(outer, text="🔒 Authentication required",
                  style="Title.TLabel").pack(pady=(0, 6))
        ttk.Label(outer,
                  text="Launch this module from the main GUI after "
                       "logging in.",
                  style="Subtitle.TLabel").pack(pady=(0, 24))
        ttk.Button(outer, text="Close", style="Danger.TButton",
                   command=self.root.destroy).pack()

    def _dispatch(self):
        for w in self.root.winfo_children():
            w.destroy()
        if _is_admin_user(self.user):
            AdminDashboard(self.root, self.db, self.user, self.root.destroy)
        else:
            VoterDashboard(self.root, self.db, self.user, self.root.destroy)

    def run(self):
        self.root.mainloop()


def open_in_toplevel(parent, auth=None):
    """Embed the election GUI in a Toplevel of an existing Tk app.

    Used by the Student Union GUI to surface this module without
    spawning a new process. ``auth`` is the live UserAuth (or shim)
    from the host app — falls back to global auth lookup.
    """
    win = tk.Toplevel(parent)
    win.title("Student Union Election System")
    win.geometry("1200x780")
    win.minsize(900, 600)
    win.configure(bg=BG)

    db = Database()
    setup_styles()

    # Resolve user — prefer the LIVE global auth over the passed-in
    # handle. If the host GUI was opened in an earlier session, its
    # ``self.auth`` may still point at a logged-out (or even replaced)
    # auth instance, so trusting it would show "please log in" even
    # though the user has since re-authenticated. Global is the source
    # of truth that ``main_gui.set_auth`` updates on every login.
    user = None
    cu = None
    try:
        from education_system.university_system.infrastructure.auth import (  # noqa: E501
            get_global_auth,
        )
        ga = get_global_auth()
        cu = ga.current_user if (ga and getattr(ga, 'current_user', None)) else None
    except Exception:
        cu = None
    if cu is None:
        try:
            cu = (auth.current_user
                  if (auth and getattr(auth, 'current_user', None))
                  else None)
        except Exception:
            cu = None

    if cu:
        user = {
            'id': cu.get('id') or cu.get('user_id'),
            'user_id': cu.get('user_id') or cu.get('id'),
            'username': cu.get('username', ''),
            'role': cu.get('role', ''),
            'email': cu.get('email', ''),
            'student_id': cu.get('student_id') or cu.get('username', ''),
            'name': cu.get('name') or cu.get('username', ''),
        }

    if not user:
        outer = ttk.Frame(win, style="TFrame")
        outer.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(outer, text="🔒 Authentication required",
                  style="Title.TLabel").pack(pady=(0, 6))
        ttk.Label(outer,
                  text="Log in through the main GUI to access elections.",
                  style="Subtitle.TLabel").pack(pady=(0, 24))
        ttk.Button(outer, text="Close", style="Danger.TButton",
                   command=win.destroy).pack()
        return win

    if _is_admin_user(user):
        AdminDashboard(win, db, user, win.destroy)
    else:
        VoterDashboard(win, db, user, win.destroy)
    return win


if __name__ == "__main__":
    App().run()
