"""Extracted function implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def configure_styles():
    # 8.117.71 — only configure NAMED styles. Pre-8.117.71 this
    # reconfigured base styles (".", TFrame, TLabel, TButton,
    # TNotebook, TNotebook.Tab, Treeview, Treeview.Heading, TEntry,
    # TCombobox) on the global ttk.Style — and because the portal
    # is launched in-process via ``open_in_workspace`` (so it shares
    # the main GUI's Tk root), those overrides bled out and recoloured
    # the whole main window. Base styles now stay on clam defaults;
    # only the Research.* named styles are touched.
    style = ttk.Style()

    style.configure("Panel.TFrame", background=PALETTE["panel"])
    style.configure("Header.TFrame", background=PALETTE["header"])

    style.configure("Panel.TLabel", background=PALETTE["panel"])
    style.configure("Header.TLabel", background=PALETTE["header"],
                    foreground=PALETTE["text"], font=("Segoe UI", 14, "bold"))
    style.configure("Subheader.TLabel", background=PALETTE["header"],
                    foreground=PALETTE["muted"], font=("Segoe UI", 10))
    style.configure("SectionTitle.TLabel", background=PALETTE["panel"],
                    foreground=PALETTE["text"], font=("Segoe UI", 13, "bold"))
    style.configure("Muted.TLabel", background=PALETTE["panel"],
                    foreground=PALETTE["muted"], font=("Segoe UI", 9))
    style.configure("StatValue.TLabel", background=PALETTE["panel"],
                    foreground=PALETTE["text"], font=("Segoe UI", 20, "bold"))
    style.configure("StatLabel.TLabel", background=PALETTE["panel"],
                    foreground=PALETTE["muted"], font=("Segoe UI", 9))

    style.configure("Accent.TButton", padding=(14, 7))
    style.configure("Danger.TButton", foreground=PALETTE["danger"])

    return style
