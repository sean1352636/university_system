"""Module-level helpers extracted from gui.py."""
from __future__ import annotations

import tkinter as tk
from tkinter import Toplevel, Label, Entry, Button, ttk

try:
    from education_system.university_system.core.i18n import get_text as _t_real
except Exception:
    def _t_real(key, **kw):
        return kw.get('_default', key.rsplit('.', 1)[-1].replace('_', ' '))

# --- _t (i18n with inline default fallback) -----------------------------
def _t(key: str, default: str, **fmt) -> str:
    try:
        val = _t_real(key, **fmt)
        if val == key or val is None:
            raise KeyError
        return val
    except Exception:
        return default.format(**fmt) if fmt else default



# --- _prompt_string -----------------------------------------------------
def _prompt_string(parent, prompt: str) -> str | None:
    win = Toplevel(parent)
    win.title(prompt)
    var = StringVar()
    Label(win, text=prompt).pack(padx=12, pady=(8, 2))
    Entry(win, textvariable=var, width=40).pack(padx=12, pady=4)
    result = {"value": None}

    def ok():
        result["value"] = var.get().strip()
        win.destroy()
    Button(win, text="OK", command=ok).pack(pady=6)
    win.grab_set()
    win.wait_window()
    return result["value"]




# --- _render_bar_table --------------------------------------------------
def _render_bar_table(parent, title, data, theme, drill=None):
    Label(parent, text=title, font=("Helvetica", 13, "bold"),
          bg=theme["panel"], fg=theme["accent"]
          ).pack(anchor="w", pady=(0, 10))
    if not data:
        Label(parent, text="No data.", bg=theme["panel"], fg=theme["muted"]
              ).pack(pady=12)
        return
    total = sum(r[1] for r in data) or 1
    max_count = max(r[1] for r in data)
    grid = Frame(parent, bg=theme["panel"])
    grid.pack(fill="both", expand=True)
    for j, h in enumerate(("Category", "n", "%", "bar")):
        Label(grid, text=h, bg=theme["accent"], fg=theme["header_fg"],
              padx=6).grid(row=0, column=j, sticky="ew", padx=1, pady=1)
    for i, (cat, n) in enumerate(data, 1):
        bar = "█" * max(1, int(n / max_count * 40))
        label = cat or "(blank)"
        Label(grid, text=label, bg=theme["panel"], fg=theme["text"],
              anchor="w", padx=6
              ).grid(row=i, column=0, sticky="ew")
        Label(grid, text=str(n), bg=theme["panel"],
              fg=theme["text"]).grid(row=i, column=1)
        Label(grid, text=f"{n / total * 100:.1f}%",
              bg=theme["panel"], fg=theme["text"]
              ).grid(row=i, column=2)
        lbl = Label(grid, text=bar, bg=theme["panel"],
                    fg=theme["accent"], font=("Courier", 10), anchor="w")
        lbl.grid(row=i, column=3, sticky="ew")
        if drill:
            lbl.bind("<Double-1>", lambda _e, c=label: drill(c))




# --- _embed_chart -------------------------------------------------------
def _embed_chart(parent, field, theme):
    """feature 19 — embed a matplotlib chart in the report frame."""
    try:
        import matplotlib
        matplotlib.use("TkAgg", force=False)
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        fig = reports_engine.render_chart(field)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, pady=8)
    except Exception:
        pass


# ----------------------------------------------------------------------------
#  Public entry points
# ----------------------------------------------------------------------------


