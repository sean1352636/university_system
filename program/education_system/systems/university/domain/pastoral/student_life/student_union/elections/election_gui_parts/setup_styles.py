"""Extracted function implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def setup_styles():
    style = ttk.Style()

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
