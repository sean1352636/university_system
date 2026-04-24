"""Read-only viewer for the JSON evaluation rubrics shipped under
``university_system/templates/course_evaluation/``.

Lists each template, shows its metadata, and renders the questions in a
table. The point is discoverability — admins/staff can browse the pool of
rubrics without touching the filesystem before deciding which one to attach
to a course evaluation campaign.
"""

import json
import logging
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from education_system.university_system.core.paths import TEMPLATES_DIR
from education_system.university_system.modules.shared.utils.i18n import get_text as _

logger = logging.getLogger(__name__)

# Templates live alongside the python source tree under
# ``university_system/templates/course_evaluation/``.
_TEMPLATES_DIR = TEMPLATES_DIR / "course_evaluation"


def _list_template_files() -> list[Path]:
    if not _TEMPLATES_DIR.is_dir():
        return []
    return sorted(p for p in _TEMPLATES_DIR.glob("*.json") if p.is_file())


class EvaluationTemplatesViewerDialog:
    """Browse the bundled course-evaluation rubric templates."""

    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self._templates = []  # list of (Path, dict)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Evaluation Templates")
        self.dialog.geometry("950x600")
        self.dialog.transient(parent)

        self._build_ui()
        self._load_templates()

    def _build_ui(self):
        header = ttk.Frame(self.dialog, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Course Evaluation Templates",
                  font=("Arial", 13, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text=str(_TEMPLATES_DIR),
                  foreground="#666").pack(side=tk.LEFT, padx=15)

        body = ttk.PanedWindow(self.dialog, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left: template list
        left = ttk.Frame(body)
        body.add(left, weight=1)
        ttk.Label(left, text="Templates").pack(anchor=tk.W)
        self.list_var = tk.StringVar(value=[])
        self.listbox = tk.Listbox(left, listvariable=self.list_var,
                                  exportselection=False, height=22)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", lambda _e: self._show_selected())

        # Right: details
        right = ttk.Frame(body)
        body.add(right, weight=3)

        meta_frame = ttk.LabelFrame(right, text="Metadata", padding=10)
        meta_frame.pack(fill=tk.X)
        self.meta_name = tk.StringVar()
        self.meta_type = tk.StringVar()
        self.meta_desc = tk.StringVar()
        for r, (lbl, var) in enumerate((("Name", self.meta_name),
                                         ("Type", self.meta_type),
                                         ("Description", self.meta_desc))):
            ttk.Label(meta_frame, text=f"{lbl}:").grid(row=r, column=0, sticky=tk.NW, pady=2)
            ttk.Label(meta_frame, textvariable=var, wraplength=620
                      ).grid(row=r, column=1, sticky=tk.W, padx=6)

        questions_frame = ttk.LabelFrame(right, text="Questions", padding=10)
        questions_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        cols = ("idx", "category", "type", "scale", "text")
        self.qtree = ttk.Treeview(questions_frame, columns=cols,
                                  show="headings", height=14)
        for c, label, w in (("idx", "#", 32),
                            ("category", "Category", 130),
                            ("type", "Type", 80),
                            ("scale", "Scale", 60),
                            ("text", "Question", 460)):
            self.qtree.heading(c, text=label)
            self.qtree.column(c, width=w, anchor=tk.W)
        scroll = ttk.Scrollbar(questions_frame, orient=tk.VERTICAL,
                               command=self.qtree.yview)
        self.qtree.configure(yscrollcommand=scroll.set)
        self.qtree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.dialog, textvariable=self.status_var,
                  anchor=tk.W, padding=(10, 5)).pack(fill=tk.X)
        ttk.Button(self.dialog, text=_("common.close", default="Close"),
                   command=self.dialog.destroy).pack(pady=8)

    def _load_templates(self):
        files = _list_template_files()
        self._templates = []
        for fp in files:
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Could not read template %s: %s", fp.name, e)
                data = {"template_name": fp.stem, "_error": str(e),
                        "questions": []}
            self._templates.append((fp, data))

        labels = []
        for fp, data in self._templates:
            name = data.get("template_name") or fp.stem
            labels.append(name)
        self.list_var.set(labels)

        if not self._templates:
            self.status_var.set(
                f"No templates found in {_TEMPLATES_DIR}. Check that the "
                f"templates directory exists.")
            return
        self.listbox.selection_set(0)
        self._show_selected()

    def _show_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        fp, data = self._templates[sel[0]]
        if "_error" in data:
            self.meta_name.set(fp.name)
            self.meta_type.set("(unreadable)")
            self.meta_desc.set(data["_error"])
            for row in self.qtree.get_children():
                self.qtree.delete(row)
            self.status_var.set(f"Failed to read {fp.name}.")
            return

        self.meta_name.set(data.get("template_name", "(unnamed)"))
        self.meta_type.set(data.get("template_type", ""))
        self.meta_desc.set(data.get("description", ""))

        for row in self.qtree.get_children():
            self.qtree.delete(row)
        questions = data.get("questions", []) or []
        for i, q in enumerate(questions, start=1):
            qmin = q.get("scale_min", "")
            qmax = q.get("scale_max", "")
            scale = f"{qmin}-{qmax}" if qmin != qmax else (str(qmin) if qmin != "" else "")
            self.qtree.insert("", tk.END, values=(
                i,
                q.get("question_category", ""),
                q.get("question_type", ""),
                scale,
                q.get("question_text", ""),
            ))
        self.status_var.set(
            f"{len(questions)} question(s). Source: {fp.name}")
