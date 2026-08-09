"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class UniversityApp:
    def __init__(self, host=None):
        """Build the Research Portal.

        ``host`` may be:
          * ``None`` (legacy / subprocess entry point) — create a new
            ``tk.Tk()`` root and own it; ``run()`` enters mainloop.
          * a workspace tab ``Frame`` (passed by the main GUI's
            ``open_in_workspace``) — embed inside it; the caller owns
            the window and its mainloop.
          * a ``Toplevel`` — embed inside it without owning the
            mainloop (uncommon, but supported for symmetry).
        """
        self.db = Database()
        self.user = _get_current_user()
        self.user_display = _user_display_name(self.user)
        logger.info("Research Portal starting user=%s role=%s",
                    self.user_display,
                    (self.user or {}).get('role') or 'none')

        if host is None:
            self.root = tk.Tk()
            self.root.title("University Research Management System")
            self.root.geometry("1320x820")
            self.root.minsize(1100, 700)
            self.root.configure(bg=PALETTE["bg"])
            self._owns_root = True
        else:
            self.root = host
            self._owns_root = False
            try:
                self.root.configure(bg=PALETTE["bg"])
            except tk.TclError:
                pass

        configure_styles()
        self._build_header()
        self._build_body()
        self._build_statusbar()

    def _build_header(self):
        header = tk.Frame(self.root, bg=PALETTE["header"], height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        left = tk.Frame(header, bg=PALETTE["header"])
        left.pack(side="left", padx=24, pady=10)
        tk.Label(left, text="🎓  University Research Office",
                 bg=PALETTE["header"], fg=PALETTE["text"],
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(left, text="Ethics · Outputs · IP · Research Degrees",
                 bg=PALETTE["header"], fg=PALETTE["muted"],
                 font=("Segoe UI", 10)).pack(anchor="w")

        right = tk.Frame(header, bg=PALETTE["header"])
        right.pack(side="right", padx=24)
        tk.Label(right, text=datetime.now().strftime("%A, %d %B %Y"),
                 bg=PALETTE["header"], fg=PALETTE["muted"],
                 font=("Segoe UI", 10)).pack(anchor="e", pady=(14, 0))
        role = (self.user or {}).get('role') or ('Research Administrator' if self.user else 'not signed in')
        tk.Label(right,
                 text=f"{self.user_display}  ({role})",
                 bg=PALETTE["header"], fg=PALETTE["text"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="e")

    def _build_body(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        self.dashboard = DashboardTab(self.notebook, self.db, self)
        self.ethics = EthicsTab(self.notebook, self.db, self)
        self.outputs = OutputsTab(self.notebook, self.db, self)
        self.ip = IPTab(self.notebook, self.db, self)
        self.thesis = ThesisTab(self.notebook, self.db, self)
        self.people = PeopleTab(self.notebook, self.db, self)

        self.notebook.add(self.dashboard, text="  Dashboard  ")
        self.notebook.add(self.ethics, text="  Ethics  ")
        self.notebook.add(self.outputs, text="  Outputs (REF)  ")
        self.notebook.add(self.ip, text="  IP & Commercialisation  ")
        self.notebook.add(self.thesis, text="  Theses & Vivas  ")
        self.notebook.add(self.people, text="  People  ")

        self.notebook.bind("<<NotebookTabChanged>>",
                           lambda e: self._on_tab_changed())

    def _on_tab_changed(self):
        current = self.notebook.select()
        if not current:
            return
        widget = self.notebook.nametowidget(current)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=PALETTE["border"], height=24)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Label(bar, text="Data: central student_records.db",
                 bg=PALETTE["border"], fg=PALETTE["muted"],
                 font=("Segoe UI", 9)).pack(side="left", padx=12)
        tk.Label(bar, text="Ready",
                 bg=PALETTE["border"], fg=PALETTE["muted"],
                 font=("Segoe UI", 9)).pack(side="right", padx=12)

    def run(self):
        if not self._owns_root:
            # Embedded mode: caller owns mainloop. Just hook DB close
            # to the host's destroy.
            try:
                self.root.bind("<Destroy>",
                               lambda e, r=self.root: self.db.close()
                               if e.widget is r else None,
                               add="+")
            except tk.TclError:
                pass
            return
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.db.close()
        if self._owns_root:
            self.root.destroy()
