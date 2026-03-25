# ViewWaitlistsDialog – view and remove waitlist entries
from education_system.university_system.modules.domain.academics.gui.course_management_gui.waitlists._imports import _, messagebox, tk, ttk, sqlite3, DEFAULT_DB_PATH


class ViewWaitlistsDialog:
    def __init__(self, parent, auth):
        self.parent = parent; self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("View Course Waitlists")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent); self.dialog.grab_set()
        self._ui(); self._load()

    def _ui(self):
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        cols = ("ID","Code","Name","Student ID","Position","Status","Added")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c)
        self.tree.column("ID", width=60); self.tree.column("Code", width=90)
        self.tree.column("Name", width=240); self.tree.column("Student ID", width=120)
        self.tree.column("Position", width=80); self.tree.column("Status", width=90)
        self.tree.column("Added", width=140)
        y = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); y.pack(side=tk.RIGHT, fill=tk.Y)

        btns = ttk.Frame(self.dialog); btns.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btns, text="Refresh", command=self._load).pack(side=tk.LEFT)
        ttk.Button(btns, text="Remove Selected", command=self._remove).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load(self):
        from education_system.university_system.infrastructure.database.db import sqlite3
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cur = conn.cursor()
                cur.execute("""
                SELECT w.id, c.course_code, c.course_name, w.student_id, w.position, w.status, w.added_at
                FROM course_waitlist w
                JOIN courses c ON w.course_id = c.id
                ORDER BY c.course_code, w.position
                """)
                rows = cur.fetchall()
            for i in self.tree.get_children(): self.tree.delete(i)
            for r in rows: self.tree.insert("", tk.END, values=r)
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load waitlists: {e}")

    def _remove(self):
        from education_system.university_system.infrastructure.database.db import sqlite3
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Pick a waitlist entry to remove."); return
        row = self.tree.item(sel[0])['values']; waitlist_id = row[0]
        if not messagebox.askyesno(_("common.confirm"), "Remove selected waitlist entry?"): return
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            # capture course to fix positions
            cur.execute("SELECT course_id, position FROM course_waitlist WHERE id = ?", (waitlist_id,))
            r = cur.fetchone()
            if not r:
                conn.close(); self._load(); return
            course_id, pos = r
            cur.execute("DELETE FROM course_waitlist WHERE id = ?", (waitlist_id,))
            # close the gap in positions for remaining 'Waiting'
            cur.execute("""
                UPDATE course_waitlist
                SET position = position - 1
                WHERE course_id = ? AND status = 'Waiting' AND position > ?
            """, (course_id, pos))
            conn.commit(); conn.close()
            self._load()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to remove entry: {e}")
