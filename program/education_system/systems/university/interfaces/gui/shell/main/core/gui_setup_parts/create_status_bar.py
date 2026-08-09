"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def create_status_bar(self, parent):
    """Bottom status bar — replaces the status + current-user rows
    that used to live inside the header.

    Thin Frame at row 2 spanning both columns of ``main_frame``.
    Three regions: status (left) · current user (centre) · system
    name + version (right). Separator line at the top so it visually
    detaches from the workspace canvas above. No LabelFrame wrapper —
    convention for a status bar is a sunken-ish thin row, which a
    plain Frame + Separator delivers without the "Content" label
    chrome the old layout used."""
    bar = ttk.Frame(parent)
    bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
    bar.columnconfigure(0, weight=1)
    bar.columnconfigure(1, weight=1)
    bar.columnconfigure(2, weight=1)

    ttk.Separator(parent, orient='horizontal').grid(
        row=2, column=0, columnspan=2, sticky="new")

    # Status (left)
    left = ttk.Frame(bar, padding=(2, 4))
    left.grid(row=0, column=0, sticky=tk.W)
    ttk.Label(left, text=_t("gui.status") + ": ",
              foreground='#555555').pack(side=tk.LEFT)
    ttk.Label(left, textvariable=self.status_var).pack(side=tk.LEFT)

    # Current user (centre)
    centre = ttk.Frame(bar, padding=(2, 4))
    centre.grid(row=0, column=1, sticky=tk.N)
    ttk.Label(centre, text=_t("gui.current_user") + ": ",
              foreground='#555555').pack(side=tk.LEFT)
    ttk.Label(centre, textvariable=self.current_user_var).pack(side=tk.LEFT)

    # System / version (right)
    right_box = ttk.Frame(bar, padding=(2, 4))
    right_box.grid(row=0, column=2, sticky=tk.E)
    sys_name = _detect_system_name(self)
    ver = _detect_version()
    if sys_name:
        ttk.Label(right_box, text=sys_name,
                  foreground='#555555').pack(side=tk.LEFT)
    if sys_name and ver:
        ttk.Label(right_box, text=" · ",
                  foreground='#aaaaaa').pack(side=tk.LEFT)
    if ver:
        ttk.Label(right_box, text=f"v{ver}",
                  foreground='#555555').pack(side=tk.LEFT)
