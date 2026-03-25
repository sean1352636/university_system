"""
Decision Maker
Define options and weighted criteria, score each option,
see auto-calculated results with bar chart visualization.
Save/load decisions to JSON.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os


DATA_DIR = os.path.dirname(os.path.abspath(__file__))


class DecisionMakerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Decision Maker")
        self.geometry("1050x720")
        self.minsize(900, 600)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Winner.TLabel", font=("Segoe UI", 14, "bold"), foreground="#2e7d32")
        style.configure("Score.TLabel", font=("Segoe UI", 11))

        self.options = []       # list of str
        self.criteria = []      # list of (name, weight)
        self.scores = {}        # {option: {criterion: score}}
        self.decision_name = tk.StringVar(value="New Decision")

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Decision Maker", style="Title.TLabel").pack(side=tk.LEFT)

        btn_bar = ttk.Frame(top)
        btn_bar.pack(side=tk.RIGHT)
        ttk.Button(btn_bar, text="Save", command=self._save).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="Load", command=self._load).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="New", command=self._new).pack(side=tk.LEFT, padx=3)

        name_frame = ttk.Frame(self, padding=(10, 0, 10, 5))
        name_frame.pack(fill=tk.X)
        ttk.Label(name_frame, text="Decision:").pack(side=tk.LEFT)
        ttk.Entry(name_frame, textvariable=self.decision_name, width=40,
                  font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=5)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # -- Setup tab --
        setup = ttk.Frame(notebook, padding=10)
        notebook.add(setup, text="  Setup  ")

        paned = ttk.PanedWindow(setup, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Options panel
        opt_frame = ttk.LabelFrame(setup, text="Options", padding=10)
        paned.add(opt_frame, weight=1)

        opt_input = ttk.Frame(opt_frame)
        opt_input.pack(fill=tk.X, pady=(0, 5))
        self.option_var = tk.StringVar()
        ttk.Entry(opt_input, textvariable=self.option_var, width=25).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(opt_input, text="Add Option", command=self._add_option).pack(side=tk.LEFT)

        self.options_listbox = tk.Listbox(opt_frame, font=("Segoe UI", 10), height=12)
        self.options_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        ttk.Button(opt_frame, text="Remove Selected", command=self._remove_option).pack()

        # Criteria panel
        crit_frame = ttk.LabelFrame(setup, text="Criteria (with weights 1-10)", padding=10)
        paned.add(crit_frame, weight=1)

        crit_input = ttk.Frame(crit_frame)
        crit_input.pack(fill=tk.X, pady=(0, 5))
        self.criterion_var = tk.StringVar()
        ttk.Entry(crit_input, textvariable=self.criterion_var, width=20).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(crit_input, text="Weight:").pack(side=tk.LEFT)
        self.weight_var = tk.StringVar(value="5")
        weight_spin = ttk.Spinbox(crit_input, from_=1, to=10, textvariable=self.weight_var, width=4)
        weight_spin.pack(side=tk.LEFT, padx=5)
        ttk.Button(crit_input, text="Add", command=self._add_criterion).pack(side=tk.LEFT)

        cols = ("criterion", "weight")
        self.crit_tree = ttk.Treeview(crit_frame, columns=cols, show="headings", height=10)
        self.crit_tree.heading("criterion", text="Criterion")
        self.crit_tree.heading("weight", text="Weight")
        self.crit_tree.column("criterion", width=180)
        self.crit_tree.column("weight", width=60, anchor=tk.CENTER)
        self.crit_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        ttk.Button(crit_frame, text="Remove Selected", command=self._remove_criterion).pack()

        # -- Scoring tab --
        score_tab = ttk.Frame(notebook, padding=10)
        notebook.add(score_tab, text="  Scoring  ")

        score_top = ttk.Frame(score_tab)
        score_top.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(score_top, text="Score each option against each criterion (1-10):",
                  style="Heading.TLabel").pack(side=tk.LEFT)
        ttk.Button(score_top, text="Build Scoring Grid", command=self._build_scoring_grid).pack(side=tk.RIGHT)

        self.score_canvas = tk.Canvas(score_tab, bg="#fafafa", highlightthickness=0)
        score_scroll = ttk.Scrollbar(score_tab, orient=tk.VERTICAL, command=self.score_canvas.yview)
        self.score_inner = ttk.Frame(self.score_canvas)
        self.score_canvas.configure(yscrollcommand=score_scroll.set)
        score_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.score_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.score_window = self.score_canvas.create_window((0, 0), window=self.score_inner, anchor=tk.NW)
        self.score_inner.bind("<Configure>",
                              lambda e: self.score_canvas.configure(scrollregion=self.score_canvas.bbox("all")))
        self.score_canvas.bind("<Configure>",
                               lambda e: self.score_canvas.itemconfig(self.score_window, width=e.width))

        self.score_widgets = {}  # {(option, criterion): StringVar}

        # -- Results tab --
        results_tab = ttk.Frame(notebook, padding=10)
        notebook.add(results_tab, text="  Results  ")

        results_top = ttk.Frame(results_tab)
        results_top.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(results_top, text="Calculate Results", command=self._calculate).pack(side=tk.LEFT)
        self.winner_label = ttk.Label(results_top, text="", style="Winner.TLabel")
        self.winner_label.pack(side=tk.RIGHT, padx=10)

        result_cols = ("option", "score", "pct")
        self.result_tree = ttk.Treeview(results_tab, columns=result_cols, show="headings", height=6)
        self.result_tree.heading("option", text="Option")
        self.result_tree.heading("score", text="Weighted Score")
        self.result_tree.heading("pct", text="% of Max")
        self.result_tree.column("option", width=200)
        self.result_tree.column("score", width=130, anchor=tk.CENTER)
        self.result_tree.column("pct", width=100, anchor=tk.CENTER)
        self.result_tree.pack(fill=tk.X, pady=(0, 10))

        self.chart_canvas = tk.Canvas(results_tab, bg="white", height=250,
                                      highlightthickness=1, highlightbackground="#ccc")
        self.chart_canvas.pack(fill=tk.BOTH, expand=True)

    def _add_option(self):
        name = self.option_var.get().strip()
        if not name:
            return
        if name in self.options:
            messagebox.showwarning("Duplicate", "Option already exists.")
            return
        self.options.append(name)
        self.options_listbox.insert(tk.END, name)
        self.option_var.set("")

    def _remove_option(self):
        sel = self.options_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        removed = self.options.pop(idx)
        self.options_listbox.delete(idx)
        self.scores.pop(removed, None)

    def _add_criterion(self):
        name = self.criterion_var.get().strip()
        if not name:
            return
        try:
            weight = int(self.weight_var.get())
            if weight < 1 or weight > 10:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid", "Weight must be 1-10.")
            return
        # Check duplicate
        for c, w in self.criteria:
            if c == name:
                messagebox.showwarning("Duplicate", "Criterion already exists.")
                return
        self.criteria.append((name, weight))
        self.crit_tree.insert("", tk.END, values=(name, weight))
        self.criterion_var.set("")

    def _remove_criterion(self):
        sel = self.crit_tree.selection()
        if not sel:
            return
        item = self.crit_tree.item(sel[0])
        crit_name = item["values"][0]
        self.criteria = [(c, w) for c, w in self.criteria if c != crit_name]
        self.crit_tree.delete(sel[0])
        for opt in self.scores:
            self.scores[opt].pop(crit_name, None)

    def _build_scoring_grid(self):
        for widget in self.score_inner.winfo_children():
            widget.destroy()
        self.score_widgets.clear()

        if not self.options or not self.criteria:
            ttk.Label(self.score_inner, text="Add options and criteria first.",
                      style="Heading.TLabel").grid(row=0, column=0, padx=20, pady=20)
            return

        # Header row
        ttk.Label(self.score_inner, text="Option", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, padx=10, pady=5, sticky=tk.W)
        for j, (crit, weight) in enumerate(self.criteria):
            ttk.Label(self.score_inner, text=f"{crit}\n(w={weight})",
                      font=("Segoe UI", 9), anchor=tk.CENTER).grid(
                row=0, column=j + 1, padx=8, pady=5)

        for i, opt in enumerate(self.options):
            ttk.Label(self.score_inner, text=opt, font=("Segoe UI", 10)).grid(
                row=i + 1, column=0, padx=10, pady=3, sticky=tk.W)
            if opt not in self.scores:
                self.scores[opt] = {}
            for j, (crit, _) in enumerate(self.criteria):
                var = tk.StringVar(value=str(self.scores[opt].get(crit, 5)))
                spin = ttk.Spinbox(self.score_inner, from_=1, to=10, textvariable=var, width=4)
                spin.grid(row=i + 1, column=j + 1, padx=8, pady=3)
                self.score_widgets[(opt, crit)] = var

    def _calculate(self):
        if not self.options or not self.criteria:
            messagebox.showinfo("Setup Required", "Add options and criteria first.")
            return

        # Collect scores from widgets
        for (opt, crit), var in self.score_widgets.items():
            try:
                val = int(var.get())
                val = max(1, min(10, val))
            except (ValueError, tk.TclError):
                val = 5
            if opt not in self.scores:
                self.scores[opt] = {}
            self.scores[opt][crit] = val

        # Calculate weighted scores
        results = []
        max_possible = sum(w * 10 for _, w in self.criteria)
        for opt in self.options:
            total = 0
            for crit, weight in self.criteria:
                score = self.scores.get(opt, {}).get(crit, 5)
                total += score * weight
            pct = (total / max_possible * 100) if max_possible > 0 else 0
            results.append((opt, total, pct))

        results.sort(key=lambda x: x[1], reverse=True)

        # Update results tree
        self.result_tree.delete(*self.result_tree.get_children())
        for opt, total, pct in results:
            self.result_tree.insert("", tk.END, values=(opt, f"{total:.1f}", f"{pct:.1f}%"))

        if results:
            self.winner_label.configure(text=f"Winner: {results[0][0]} ({results[0][1]:.1f} pts)")

        # Draw bar chart
        self._draw_chart(results)

    def _draw_chart(self, results):
        c = self.chart_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 50 or h < 50 or not results:
            return

        margin_left = 120
        margin_right = 30
        margin_top = 20
        margin_bottom = 20
        chart_w = w - margin_left - margin_right
        chart_h = h - margin_top - margin_bottom

        max_score = max(r[1] for r in results) if results else 1
        if max_score == 0:
            max_score = 1

        bar_count = len(results)
        bar_gap = 8
        bar_h = max(10, min(40, (chart_h - bar_gap * (bar_count + 1)) / bar_count))

        colors = ["#4caf50", "#2196f3", "#ff9800", "#e91e63", "#9c27b0",
                  "#00bcd4", "#795548", "#607d8b", "#f44336", "#3f51b5"]

        for i, (opt, score, pct) in enumerate(results):
            y1 = margin_top + bar_gap + i * (bar_h + bar_gap)
            y2 = y1 + bar_h
            bar_w = (score / max_score) * chart_w

            color = colors[i % len(colors)]
            c.create_rectangle(margin_left, y1, margin_left + bar_w, y2,
                               fill=color, outline="")

            # Label
            c.create_text(margin_left - 5, (y1 + y2) / 2, text=opt,
                          anchor=tk.E, font=("Segoe UI", 10))

            # Score on bar
            c.create_text(margin_left + bar_w + 5, (y1 + y2) / 2,
                          text=f"{score:.1f} ({pct:.0f}%)",
                          anchor=tk.W, font=("Segoe UI", 9))

    def _save(self):
        data = {
            "name": self.decision_name.get(),
            "options": self.options,
            "criteria": self.criteria,
            "scores": self.scores
        }
        path = filedialog.asksaveasfilename(
            initialdir=DATA_DIR, defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=f"{self.decision_name.get().replace(' ', '_')}.json"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                messagebox.showinfo("Saved", f"Decision saved to:\n{path}")
            except OSError as e:
                messagebox.showerror("Error", f"Failed to save: {e}")

    def _load(self):
        path = filedialog.askopenfilename(
            initialdir=DATA_DIR, filetypes=[("JSON files", "*.json")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            messagebox.showerror("Error", f"Failed to load: {e}")
            return

        self.decision_name.set(data.get("name", "Loaded Decision"))
        self.options = data.get("options", [])
        self.criteria = [tuple(c) for c in data.get("criteria", [])]
        self.scores = data.get("scores", {})

        # Refresh options listbox
        self.options_listbox.delete(0, tk.END)
        for o in self.options:
            self.options_listbox.insert(tk.END, o)

        # Refresh criteria tree
        self.crit_tree.delete(*self.crit_tree.get_children())
        for c, w in self.criteria:
            self.crit_tree.insert("", tk.END, values=(c, w))

        self._build_scoring_grid()
        messagebox.showinfo("Loaded", f"Decision '{data.get('name', '')}' loaded.")

    def _new(self):
        if messagebox.askyesno("New Decision", "Clear everything and start fresh?"):
            self.decision_name.set("New Decision")
            self.options.clear()
            self.criteria.clear()
            self.scores.clear()
            self.options_listbox.delete(0, tk.END)
            self.crit_tree.delete(*self.crit_tree.get_children())
            self.result_tree.delete(*self.result_tree.get_children())
            self.winner_label.configure(text="")
            self.chart_canvas.delete("all")
            for widget in self.score_inner.winfo_children():
                widget.destroy()
            self.score_widgets.clear()


if __name__ == "__main__":
    app = DecisionMakerApp()
    app.mainloop()
