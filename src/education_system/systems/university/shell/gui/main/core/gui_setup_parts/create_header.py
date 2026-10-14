"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def create_header(self, parent):
    """Create the top control bar.

    Pre-8.117.20 this was a ``LabelFrame "System Control"`` wrapper
    holding [Shutdown][Logout][Switch CLI][Switch System] in a row
    plus two lines of status labels — visual noise, status-at-top
    breaks desktop convention, and Shutdown sat one click of muscle
    memory away from Logout. Reshaped to:

    - Plain Frame (no LabelFrame) — less ttk-style noise.
    - Routine actions (Switch CLI / Switch System / Logout) on the
      left as primary buttons.
    - Destructive actions (Shutdown) folded into a "⏻ Power ▾"
      menubutton on the right. One extra click of intent before
      Shutdown — protects against muscle-memory accidents.
    - Status + current-user labels removed. They now live in the
      bottom status bar (``create_status_bar``).
    """
    header_frame = ttk.Frame(parent, padding=(0, 0, 0, 6))
    header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
    header_frame.columnconfigure(1, weight=1)

    # ── Routine actions (left) ──
    left = ttk.Frame(header_frame)
    left.grid(row=0, column=0, sticky=tk.W)

    # Login/Logout button (dynamic text based on auth status)
    self.login_logout_btn = ttk.Button(
        left, text=_t("common.logout"),
        command=lambda: self.toggle_login_logout())
    self.login_logout_btn.pack(side=tk.LEFT, padx=(0, 6))

    ttk.Button(left, text=_t("gui.switch_to_cli"),
               command=lambda: self.switch_to_cli()).pack(
        side=tk.LEFT, padx=(0, 6))

    # Superadmins (admin role on the university system) can jump
    # straight to one of the other systems without going through the
    # login. Hidden for everyone else.
    try:
        from education_system.launcher.roles import is_superadmin
        if is_superadmin(self.auth.current_user if self.auth else None):
            ttk.Button(
                left, text=_t('gui.shell.main.core.gui_setup_parts.create_header.buttons.switch_system', default="Switch System"),
                command=lambda: _switch_system_dialog(self),
            ).pack(side=tk.LEFT, padx=(0, 6))
    except Exception:
        logger.exception("Could not evaluate superadmin status for header")

    # ── Destructive actions (right) ──
    right = ttk.Frame(header_frame)
    right.grid(row=0, column=2, sticky=tk.E)

    power_btn = ttk.Button(right, text="⏻ " + _t("gui.shutdown"),
                           command=lambda: self.shutdown_system())
    power_btn.pack(side=tk.RIGHT)

    # ── Language switcher ──
    # auth_gui.show_language_selector had been written but never wired to
    # anything, so the university shell shipped with no way to change
    # language even though every screen is translated. Shows the active
    # language on the button so the current setting is visible at a glance.
    try:
        self.lang_btn = ttk.Button(
            right,
            text=f"🌐 {get_current_language_name()}",
            command=lambda: self.show_language_selector())
        self.lang_btn.pack(side=tk.RIGHT, padx=(0, 6))
    except Exception:
        logger.exception("Could not create the language button")

    # ── Notification bell (in-shell alert centre) ──
    # Admin/staff shells previously had no at-a-glance unread indicator;
    # messages were only reachable by drilling into the Email Manager.
    # This surfaces the live unread count (University inbox + cross-system
    # messages) and opens the unread-inbox Hub on click. Packed left of
    # the power button.
    self.notif_bell_btn = ttk.Button(
        right, text="🔔",
        command=lambda: self._open_notifications())
    self.notif_bell_btn.pack(side=tk.RIGHT, padx=(0, 6))
    # Populate the badge now; the 60s session timer keeps it fresh.
    try:
        self._refresh_notification_badge()
    except Exception:
        logger.debug("initial notification badge refresh failed", exc_info=True)

    # ── Institution logo (ambient branding) ──
    # Shares the stretchy middle column with the clock: logo pinned west,
    # clock east, so they sit at opposite ends of that cell. Whatever an
    # admin sets in Branding & Customization shows here on every screen,
    # not just the dashboard. Silently absent when no logo is configured.
    # The label is created unconditionally (blank when no logo is set) so
    # ``refresh_header_logo`` can fill it in later without rebuilding the
    # header — otherwise a logo set mid-session would not show until restart.
    self._header_logo_image = None
    self._header_logo_label = ttk.Label(header_frame)
    self._header_logo_label.grid(row=0, column=1, sticky=tk.W, padx=(14, 0))
    refresh_header_logo(self)

    # ── Live clock (ambient date/time) ──
    # Sits in the header's stretchy middle column, right-aligned so it
    # tucks in just left of the bell / power actions. Ticks once a
    # second via its own after-loop, cancelled in _cancel_timers.
    self.clock_var = tk.StringVar()
    clock_lbl = ttk.Label(header_frame, textvariable=self.clock_var,
                          foreground='#555555')
    clock_lbl.grid(row=0, column=1, sticky=tk.E, padx=(0, 14))
    self._update_clock()
