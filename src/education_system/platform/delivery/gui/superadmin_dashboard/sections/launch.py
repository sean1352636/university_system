"""Launch System section.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CONTENT_BG,
    DEFAULT_SYSTEM_COLOR,
    LAUNCH_ONLY_SYSTEMS,
    SYSTEM_BLURBS,
    SYSTEM_COLORS,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class LaunchMixin:
    def _build_launch(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame,
            text="Quick Launch",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Launch an individual education system. You will enter as superadmin.",
            font=("Segoe UI", 10),
            bg=CONTENT_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 24))

        # One card per system, three to a row. Built from SYSTEM_ORDER rather
        # than a hand-written list: the hand-written one had drifted to five
        # entries while the platform had grown past it, so half the systems
        # had no way in from here.
        grid = tk.Frame(frame, bg=CONTENT_BG)
        grid.pack(padx=40, pady=(0, 30))
        _LAUNCH_COLS = 3

        launch_configs = [
            (
                key,
                SYSTEM_LABELS.get(key) or LAUNCH_ONLY_SYSTEMS.get(key, key),
                SYSTEM_COLORS.get(key, DEFAULT_SYSTEM_COLOR),
                SYSTEM_BLURBS.get(key, ""),
            )
            for key in [*SYSTEM_ORDER, *LAUNCH_ONLY_SYSTEMS]
        ]

        for i, (sys_key, label, color, desc) in enumerate(launch_configs):
            row, col = divmod(i, _LAUNCH_COLS)

            btn_frame = tk.Frame(grid, bg=color, cursor="hand2")
            btn_frame.grid(row=row, column=col, padx=14, pady=14, sticky=tk.NSEW)
            grid.columnconfigure(col, weight=1)
            grid.rowconfigure(row, weight=1)

            inner = tk.Frame(btn_frame, bg=color)
            inner.pack(padx=3, pady=3, fill=tk.BOTH, expand=True)

            name_lbl = tk.Label(
                inner,
                text=label,
                font=("Segoe UI", 18, "bold"),
                bg=color,
                fg=TEXT_LIGHT,
            )
            name_lbl.pack(padx=30, pady=(30, 4))

            desc_lbl = tk.Label(
                inner,
                text=desc,
                font=("Segoe UI", 10),
                bg=color,
                fg="#e0e0e0",
                justify=tk.CENTER,
            )
            desc_lbl.pack(padx=30, pady=(0, 6))

            launch_lbl = tk.Label(
                inner,
                text="Click to Launch  \u2192",
                font=("Segoe UI", 10, "bold"),
                bg=color,
                fg=TEXT_LIGHT,
            )
            launch_lbl.pack(padx=30, pady=(4, 30))

            # Bind click to all widgets in the button frame
            def _make_handler(sk=sys_key):
                return lambda e: self._launch_system(sk)

            handler = _make_handler()
            for widget in (btn_frame, inner, name_lbl, desc_lbl, launch_lbl):
                widget.bind("<Button-1>", handler)

            # Hover effect
            def _on_enter(e, frm=btn_frame, c=color):
                try:
                    # Lighten the colour slightly
                    r = int(c[1:3], 16)
                    g = int(c[3:5], 16)
                    b = int(c[5:7], 16)
                    r = min(255, r + 20)
                    g = min(255, g + 20)
                    b = min(255, b + 20)
                    lighter = f"#{r:02x}{g:02x}{b:02x}"
                    frm.configure(bg=lighter)
                    for child in frm.winfo_children():
                        child.configure(bg=lighter)
                        for grandchild in child.winfo_children():
                            grandchild.configure(bg=lighter)
                except Exception:
                    pass

            def _on_leave(e, frm=btn_frame, c=color):
                try:
                    frm.configure(bg=c)
                    for child in frm.winfo_children():
                        child.configure(bg=c)
                        for grandchild in child.winfo_children():
                            grandchild.configure(bg=c)
                except Exception:
                    pass

            btn_frame.bind("<Enter>", _on_enter)
            btn_frame.bind("<Leave>", _on_leave)

    def _launch_system(self, system_key):
        """Set launch attributes and close the dashboard."""
        self._stop_auto_refresh()
        self.launch_system = system_key
        self.launch_role = "admin"
        self.destroy()
