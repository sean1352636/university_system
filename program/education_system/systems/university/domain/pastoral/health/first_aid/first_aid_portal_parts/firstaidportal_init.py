"""Methods __init__ through _create_emergency_tab."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class FirstAidPortal:
    def __init__(self, root):
        self.root = root
        # When ``root`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), skip window-chrome calls. Same
        # shape as Library (8.117.34).
        if hasattr(self.root, "wm_title"):
            self.root.title("University First Aid Portal")
            self.root.geometry("1000x700")
        try:
            self.root.configure(bg="#f0f4f8")
        except tk.TclError:
            pass

        # Color scheme
        self.colors = {
            "primary": "#c0392b",      # Medical red
            "secondary": "#2980b9",    # Medical blue
            "accent": "#27ae60",       # Green for safety
            "bg": "#f0f4f8",
            "card": "#ffffff",
            "text": "#2c3e50",
            "warning": "#e67e22",
        }

        # Auth + persistence
        self.user = _get_current_user()
        self.user_display = _user_display_name(self.user) or 'Guest'
        try:
            self.db = IncidentDB()
        except Exception:
            self.db = None
            logger.exception("First Aid Portal starting without DB persistence")
        logger.info("First Aid Portal starting user=%s role=%s db=%s",
                    self.user_display,
                    (self.user or {}).get('role') or 'none',
                    'on' if self.db else 'off')

        # First aid data
        self.first_aid_data = self._load_first_aid_data()
        self.emergency_contacts = self._load_emergency_contacts()

        self._setup_styles()
        self._create_header()
        self._create_main_content()
        self._create_footer()

    def _setup_styles(self):
        # Namespaced so that embedding this app in the main GUI workspace
        # (process-global ttk.Style) doesn't recolour the host's notebook.
        style = ttk.Style()
        style.configure("FirstAid.TNotebook", background=self.colors["bg"], borderwidth=0)
        style.configure(
            "FirstAid.TNotebook.Tab",
            padding=[20, 10],
            font=("Segoe UI", 10, "bold"),
            background="#d6dde5",
            foreground=self.colors["text"],
        )
        style.map(
            "FirstAid.TNotebook.Tab",
            background=[("selected", self.colors["primary"])],
            foreground=[("selected", "white")],
        )

    def _create_header(self):
        header = tk.Frame(self.root, bg=self.colors["primary"], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_frame = tk.Frame(header, bg=self.colors["primary"])
        title_frame.pack(expand=True, fill="both", padx=20)

        tk.Label(
            title_frame,
            text="⚕  UNIVERSITY FIRST AID PORTAL",
            font=("Segoe UI", 20, "bold"),
            bg=self.colors["primary"],
            fg="white",
        ).pack(side="left", pady=20)

        tk.Label(
            title_frame,
            text="Emergency Response & Health Information System",
            font=("Segoe UI", 10, "italic"),
            bg=self.colors["primary"],
            fg="#ffe5e5",
        ).pack(side="right", pady=25)

        role = (self.user or {}).get('role') or ('—' if self.user else 'not signed in')
        tk.Label(
            title_frame,
            text=f"Signed in: {self.user_display}  ({role})",
            font=("Segoe UI", 9),
            bg=self.colors["primary"],
            fg="#ffe5e5",
        ).pack(side="right", padx=15, pady=25)

    def _create_main_content(self):
        self.notebook = ttk.Notebook(self.root, style="FirstAid.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._create_home_tab()
        self._create_first_aid_tab()
        self._create_emergency_tab()
        self._create_report_tab()
        self._create_resources_tab()

    def _emergency_banner_text(self):
        """Build the Home-tab emergency banner from the contact data so it
        never drifts from the Emergency Contacts tab. Prefers the two most
        critical contacts; falls back to whatever is available."""
        wanted = ("Emergency Services", "Campus Security",
                  "University Health Center")
        picked = []
        for name in wanted:
            for c in self.emergency_contacts:
                if c["name"] == name:
                    picked.append(c)
                    break
            if len(picked) >= 2:
                break
        if not picked:
            picked = self.emergency_contacts[:2]
        return "  |  ".join(f"{c['name']}: {c['number']}" for c in picked)

    def _create_home_tab(self):
        home = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(home, text="🏠 Home")

        welcome = tk.Label(
            home,
            text="Welcome to the First Aid Portal",
            font=("Segoe UI", 22, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        )
        welcome.pack(pady=20)

        msg = tk.Label(
            home,
            text="Quick access to first aid guidance, emergency contacts, and incident reporting.",
            font=("Segoe UI", 11),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        )
        msg.pack(pady=5)

        # Emergency banner
        emergency_frame = tk.Frame(home, bg=self.colors["primary"], relief="raised", bd=2)
        emergency_frame.pack(fill="x", padx=40, pady=20)

        tk.Label(
            emergency_frame,
            text="🚨  IN CASE OF EMERGENCY  🚨",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors["primary"],
            fg="white",
        ).pack(pady=5)

        tk.Label(
            emergency_frame,
            text=self._emergency_banner_text(),
            font=("Segoe UI", 12),
            bg=self.colors["primary"],
            fg="white",
        ).pack(pady=5)

        # Quick action cards
        cards_frame = tk.Frame(home, bg=self.colors["bg"])
        cards_frame.pack(pady=30)

        cards = [
            ("🩹", "First Aid Guides", "Step-by-step instructions", 1),
            ("📞", "Emergency Contacts", "Quick dial numbers", 2),
            ("📝", "Report Incident", "Log health incidents", 3),
            ("📚", "Resources", "Training & downloads", 4),
        ]

        for i, (icon, title, desc, tab_idx) in enumerate(cards):
            card = tk.Frame(cards_frame, bg=self.colors["card"], relief="raised", bd=1, width=200, height=150)
            card.grid(row=0, column=i, padx=15, pady=10)
            card.grid_propagate(False)

            tk.Label(card, text=icon, font=("Segoe UI", 30), bg=self.colors["card"]).pack(pady=(15, 5))
            tk.Label(card, text=title, font=("Segoe UI", 12, "bold"), bg=self.colors["card"], fg=self.colors["text"]).pack()
            tk.Label(card, text=desc, font=("Segoe UI", 9), bg=self.colors["card"], fg="#7f8c8d").pack(pady=2)

            btn = tk.Button(
                card,
                text="Open",
                font=("Segoe UI", 9, "bold"),
                bg=self.colors["secondary"],
                fg="white",
                relief="flat",
                cursor="hand2",
                command=lambda idx=tab_idx: self.notebook.select(idx),
            )
            btn.pack(pady=8)

        # Date/time
        dt_label = tk.Label(
            home,
            text=f"Today: {datetime.now().strftime('%A, %B %d, %Y')}",
            font=("Segoe UI", 10, "italic"),
            bg=self.colors["bg"],
            fg="#7f8c8d",
        )
        dt_label.pack(pady=10)

    def _create_first_aid_tab(self):
        fa_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(fa_tab, text="🩹 First Aid Guides")

        # Left panel — list of conditions
        left = tk.Frame(fa_tab, bg=self.colors["card"], width=250)
        left.pack(side="left", fill="y", padx=(10, 5), pady=10)
        left.pack_propagate(False)

        tk.Label(
            left,
            text="Select Condition",
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["card"],
            fg=self.colors["text"],
        ).pack(pady=10)

        # Search box
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._filter_conditions)
        search_entry = tk.Entry(left, textvariable=self.search_var, font=("Segoe UI", 10), relief="solid", bd=1)
        search_entry.pack(fill="x", padx=10, pady=5)
        search_entry.insert(0, "")

        tk.Label(left, text="🔍 Search conditions", font=("Segoe UI", 8), bg=self.colors["card"], fg="#95a5a6").pack()

        # Listbox
        list_frame = tk.Frame(left, bg=self.colors["card"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.condition_listbox = tk.Listbox(
            list_frame,
            font=("Segoe UI", 10),
            bg="white",
            fg=self.colors["text"],
            selectbackground=self.colors["primary"],
            selectforeground="white",
            relief="flat",
            yscrollcommand=scrollbar.set,
            activestyle="none",
        )
        self.condition_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.condition_listbox.yview)

        for condition in self.first_aid_data.keys():
            self.condition_listbox.insert("end", condition)

        self.condition_listbox.bind("<<ListboxSelect>>", self._show_first_aid_instructions)

        # Right panel — instructions
        right = tk.Frame(fa_tab, bg=self.colors["card"])
        right.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)

        self.condition_title = tk.Label(
            right,
            text="Select a condition to view instructions",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["card"],
            fg=self.colors["primary"],
        )
        self.condition_title.pack(pady=15, padx=15, anchor="w")

        self.instructions_text = scrolledtext.ScrolledText(
            right,
            font=("Segoe UI", 11),
            bg="#fafafa",
            fg=self.colors["text"],
            relief="flat",
            wrap="word",
            padx=15,
            pady=10,
        )
        self.instructions_text.pack(fill="both", expand=True, padx=15, pady=10)
        self.instructions_text.insert(
            "1.0",
            "\n\n👈 Please select a first aid condition from the list on the left.\n\n"
            "You will find step-by-step instructions for handling common emergencies.",
        )
        self.instructions_text.config(state="disabled")

    def _create_emergency_tab(self):
        em_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(em_tab, text="📞 Emergency Contacts")

        tk.Label(
            em_tab,
            text="Emergency Contact Directory",
            font=("Segoe UI", 18, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(pady=15)

        # Scrollable area so every contact card is reachable regardless
        # of window height (previously the bottom row could be clipped).
        outer = tk.Frame(em_tab, bg=self.colors["bg"])
        outer.pack(fill="both", expand=True, padx=20, pady=10)

        canvas = tk.Canvas(outer, bg=self.colors["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical",
                                  command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        container = tk.Frame(canvas, bg=self.colors["bg"])
        window_id = canvas.create_window((0, 0), window=container, anchor="nw")

        def _on_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        container.bind("<Configure>", _on_configure)
        # Keep the inner frame as wide as the canvas so the two columns
        # share the full width and expand with the window.
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(window_id, width=e.width))

        # Mousewheel scrolling, scoped to while the cursor is over this
        # tab so it doesn't hijack scrolling elsewhere in the portal.
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(_e=None):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)         # Win/macOS
            canvas.bind_all("<Button-4>",
                            lambda e: canvas.yview_scroll(-1, "units"))  # Linux
            canvas.bind_all("<Button-5>",
                            lambda e: canvas.yview_scroll(1, "units"))   # Linux

        def _unbind_wheel(_e=None):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        container.grid_columnconfigure(0, weight=1, uniform="contact")
        container.grid_columnconfigure(1, weight=1, uniform="contact")

        # Create contact cards
        for i, contact in enumerate(self.emergency_contacts):
            row = i // 2
            col = i % 2

            card = tk.Frame(container, bg=self.colors["card"], relief="raised", bd=1)
            card.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)

            # Color strip
            strip = tk.Frame(card, bg=contact["color"], width=8)
            strip.pack(side="left", fill="y")

            info = tk.Frame(card, bg=self.colors["card"])
            info.pack(side="left", fill="both", expand=True, padx=15, pady=15)

            tk.Label(
                info,
                text=f"{contact['icon']}  {contact['name']}",
                font=("Segoe UI", 13, "bold"),
                bg=self.colors["card"],
                fg=self.colors["text"],
                anchor="w",
                justify="left",
            ).pack(anchor="w", fill="x")

            tk.Label(
                info,
                text=contact["number"],
                font=("Segoe UI", 16, "bold"),
                bg=self.colors["card"],
                fg=contact["color"],
            ).pack(anchor="w", pady=3)

            tk.Label(
                info,
                text=contact["description"],
                font=("Segoe UI", 10),
                bg=self.colors["card"],
                fg="#7f8c8d",
                wraplength=460,
                justify="left",
            ).pack(anchor="w", fill="x")

            tk.Label(
                info,
                text=f"📍 {contact['location']}",
                font=("Segoe UI", 9, "italic"),
                bg=self.colors["card"],
                fg="#7f8c8d",
                wraplength=460,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(5, 0))
