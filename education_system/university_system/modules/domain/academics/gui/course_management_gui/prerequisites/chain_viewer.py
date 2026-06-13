"""Prerequisite chain viewer.

Shows the full transitive prerequisite tree for a selected course. The
existing PrerequisitesWindow only shows direct (depth-1) prerequisites; this
view walks the graph recursively using DFS with cycle detection so a corrupt
prerequisite graph cannot loop forever.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core import paths
from education_system.university_system.core.i18n import get_text as _

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
logger = logging.getLogger(__name__)

_MAX_DEPTH = 12  # Prevents pathological depth even when cycle detection misses.


class PrerequisiteChainDialog:
    """Pick a course, see its full prerequisite tree."""

    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self._courses = []  # list of (id, code, name)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Prerequisite Chain")
        self.dialog.geometry("750x550")
        self.dialog.transient(parent)

        self._build_ui()
        self._load_course_list()

    def _build_ui(self):
        top = ttk.Frame(self.dialog, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Prerequisite Chain Viewer",
                  font=("Arial", 13, "bold")).pack(side=tk.LEFT)

        picker = ttk.Frame(self.dialog, padding=(10, 0))
        picker.pack(fill=tk.X)
        ttk.Label(picker, text="Course:").pack(side=tk.LEFT)
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(picker, textvariable=self.course_var,
                                         width=60, state="readonly")
        self.course_combo.pack(side=tk.LEFT, padx=5)
        self.course_combo.bind("<<ComboboxSelected>>",
                               lambda _e: self._populate_tree())

        body = ttk.Frame(self.dialog, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(body, columns=("type",), show="tree headings", height=22)
        self.tree.heading("#0", text="Course")
        self.tree.heading("type", text="Requirement")
        self.tree.column("#0", width=420)
        self.tree.column("type", width=200, anchor=tk.W)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.dialog, textvariable=self.status_var,
                  anchor=tk.W, padding=(10, 5)).pack(fill=tk.X)

        ttk.Button(self.dialog, text=_("common.close", default="Close"),
                   command=self.dialog.destroy).pack(pady=8)

    def _load_course_list(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                cur = conn.cursor()
                cur.execute("""
                    SELECT id,
                           COALESCE(course_code, code, '') AS code,
                           COALESCE(course_name, name, '') AS name
                    FROM courses
                    ORDER BY code
                """)
                self._courses = cur.fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Failed to load courses for chain viewer")
            messagebox.showerror(_("common.database_error"),
                                 f"Failed to load courses: {e}")
            return
        self.course_combo["values"] = [
            f"{code} - {name}" for _id, code, name in self._courses
        ]
        if self._courses:
            self.course_combo.current(0)
            self._populate_tree()
        else:
            self.status_var.set("No courses found.")

    def _populate_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        idx = self.course_combo.current()
        if idx < 0 or idx >= len(self._courses):
            return
        course_id, code, name = self._courses[idx]
        try:
            adjacency = self._load_prereq_graph()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"),
                                 f"Failed to load prerequisites: {e}")
            return

        course_lookup = {cid: (code_, name_) for cid, code_, name_ in self._courses}
        root = self.tree.insert("", tk.END, text=f"{code} - {name}",
                                values=("(target course)",), open=True)

        prereqs = adjacency.get(course_id, [])
        if not prereqs:
            self.tree.insert(root, tk.END, text="(no prerequisites)", values=("",))
            self.status_var.set("No prerequisites for this course.")
            return

        cycles_found = []
        nodes_added = self._walk(root, course_id, adjacency, course_lookup,
                                 visited={course_id}, depth=1,
                                 cycles=cycles_found)
        if cycles_found:
            self.status_var.set(
                f"{nodes_added} prerequisite node(s) shown. "
                f"WARNING: {len(cycles_found)} cycle(s) detected — see [CYCLE] markers."
            )
        else:
            self.status_var.set(f"{nodes_added} prerequisite node(s) shown.")

    def _walk(self, parent_node, course_id, adjacency, lookup, visited, depth, cycles):
        if depth > _MAX_DEPTH:
            self.tree.insert(parent_node, tk.END,
                             text=f"... (max depth {_MAX_DEPTH} reached)",
                             values=("",))
            return 0
        added = 0
        for prereq_id, requirement in adjacency.get(course_id, []):
            if prereq_id in lookup:
                code, name = lookup[prereq_id]
                label = f"{code} - {name}"
            else:
                label = f"(course id {prereq_id} — not found)"
            if prereq_id in visited:
                self.tree.insert(parent_node, tk.END,
                                 text=f"[CYCLE] {label}",
                                 values=(requirement,))
                cycles.append(prereq_id)
                added += 1
                continue
            node = self.tree.insert(parent_node, tk.END, text=label,
                                    values=(requirement,), open=True)
            added += 1
            added += self._walk(node, prereq_id, adjacency, lookup,
                                visited | {prereq_id}, depth + 1, cycles)
        return added

    def _load_prereq_graph(self):
        """Return {course_id: [(prereq_course_id, requirement_label), ...]}."""
        graph = {}
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(course_prerequisites)")
            cols = {r[1] for r in cur.fetchall()}
            if not cols:
                return graph
            select = ["course_id", "prerequisite_course_id"]
            has_required = "is_required" in cols
            has_grade = "minimum_grade" in cols
            if has_required:
                select.append("is_required")
            if has_grade:
                select.append("minimum_grade")
            cur.execute(f"SELECT {', '.join(select)} FROM course_prerequisites")
            for row in cur.fetchall():
                cid, pid = row[0], row[1]
                idx = 2
                required = bool(row[idx]) if has_required else True
                idx += 1 if has_required else 0
                grade = row[idx] if has_grade else None
                label_parts = ["Required" if required else "Recommended"]
                if grade:
                    label_parts.append(f"min grade {grade}")
                graph.setdefault(cid, []).append((pid, ", ".join(label_parts)))
        finally:
            conn.close()
        return graph
