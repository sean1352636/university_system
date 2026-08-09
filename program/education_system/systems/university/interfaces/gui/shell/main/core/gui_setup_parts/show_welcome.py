"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_welcome(self):
    """Show the pre-login / signed-out landing screen.

    Pre-8.117.20 this rendered as a single welcome label in the
    upper-left of a 1400×900 panel — visually empty. The post-login
    state already gets the proper integrated dashboard via
    ``show_main_interface`` → ``show_integrated_dashboard``, so this
    function only fires before login or after explicit logout.

    Reshape: a centred hero card with the welcome text, a clear
    "Sign in" call-to-action, and a small set of context buttons
    (CLI mode / language / quit). Quick actions still appear *if*
    a user is somehow viewing this with auth set — preserves the
    pre-existing fallback for callers that route here mid-session.
    """
    self.clear_content()

    container = ttk.Frame(self.content_frame, padding=20)
    container.grid(row=0, column=0, sticky="nsew")
    self.content_frame.columnconfigure(0, weight=1)
    self.content_frame.rowconfigure(0, weight=1)

    # Centred hero card
    hero = ttk.Frame(container, padding=30)
    hero.place(relx=0.5, rely=0.4, anchor='center')

    ttk.Label(hero, text="🎓",
              font=('Arial', 48)).pack(pady=(0, 8))
    ttk.Label(hero, text=_t('gui.shell.main.core.gui_setup_parts.show_welcome.labels.education_system', default="Education System"),
              font=('Arial', 22, 'bold')).pack()
    ttk.Label(hero, text=_t("gui.welcome_text"),
              foreground='#555555',
              wraplength=420, justify='center',
              font=('Arial', 11)).pack(pady=(8, 18))

    # Pre-login: clear sign-in CTA + secondary actions
    if not (self.auth and self.auth.current_user):
        cta = ttk.Frame(hero)
        cta.pack(pady=(4, 0))
        ttk.Button(cta, text=_t("common.login"),
                   command=lambda: self.toggle_login_logout(),
                   width=18).pack(side=tk.LEFT, padx=4)
        ttk.Button(cta, text=_t("gui.switch_to_cli"),
                   command=lambda: self.switch_to_cli(),
                   width=18).pack(side=tk.LEFT, padx=4)

        # Tip about Ctrl+K — surfaces the otherwise-hidden launcher.
        ttk.Label(hero,
                  text=_t('gui.shell.main.core.gui_setup_parts.show_welcome.labels.tip_press_ctrl_k_to_jump_to_any_feature', default="Tip: press Ctrl+K to jump to any feature."),
                  foreground='#888888',
                  font=('Arial', 9, 'italic')).pack(pady=(18, 0))
        return

    # Signed-in fallback path — same quick-actions block as pre-8.117.20
    # in case a caller routes here mid-session. The post-login flow
    # normally uses show_integrated_dashboard, so this is rarely hit.
    user = self.auth.current_user
    permissions = user.get('permissions', [])

    quick_actions = []
    if 'view_any_student' in permissions or 'view_own_record' in permissions:
        quick_actions.append((_t("gui.view_student_records"), self.show_student_records))
    if 'create_student' in permissions:
        quick_actions.append((_t("gui.create_new_student"), self.create_student_dialog))
    if 'access_chatbot' in permissions:
        quick_actions.append((_t("gui.launch_chatbot"), self.show_chatbot))
    if 'view_analytics' in permissions:
        quick_actions.append((_t("gui.view_analytics"), self.show_analytics))
    if any(p in permissions for p in ['view_trips', 'register_for_trips', 'manage_trips']):
        quick_actions.append((_t("gui.trip_management"), self.show_trip_management_gui))
    if ADVANCED_SEARCH_GUI_AVAILABLE and 'view_any_student' in permissions:
        quick_actions.append((_t("gui.advanced_search"), self.show_advanced_search_gui))
    if ('manage_schedules' in permissions) or ('view_own_timetable' in permissions):
        quick_actions.append((_t("gui.module_scheduling"), self.show_module_scheduling))

    if quick_actions:
        qa_frame = ttk.Frame(hero)
        qa_frame.pack(pady=(20, 0))
        ttk.Label(qa_frame, text=_t("gui.quick_actions"),
                  font=('Arial', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, pady=(0, 6))
        for i, (text, command) in enumerate(quick_actions[:4]):
            r, c = 1 + i // 2, i % 2
            ttk.Button(qa_frame, text=text, command=command,
                       width=22).grid(row=r, column=c, padx=4, pady=3)
