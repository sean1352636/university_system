"""The apprenticeships desktop shell.

One window, three regions: a header, a navigation sidebar, and a content
pane that every screen renders into. Layout follows the house pattern —
1400x900, minimum 1200x800, ``grid`` for the shell and ``pack`` inside
it — so this sits alongside the other systems rather than looking like
a different application.

What is different here is that the navigation is built from the signed-in
role. The five roles are not variations on one menu with bits hidden:
an employer and an end-point assessor want genuinely different screens,
and an assessor must not even see the provider's formative judgements.
So :data:`NAV_BY_ROLE` gives each role its own tree, and every screen
re-checks permission through the service layer anyway — the menu is
convenience, not security.
"""

from __future__ import annotations

import importlib
import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from education_system.platform import branding
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.apprenticeships import SYSTEM_NAME, VERSION, config
from education_system.systems.apprenticeships.services import preferences
from education_system.systems.apprenticeships.services.access import Actor, resolve

logger = logging.getLogger(__name__)

FOOTER_LABEL = "Apprenticeships"

# Where the window modules live: one package per role, plus ``shared`` for
# screens several roles open — the service scopes what each of them sees.
_WINDOW_PACKAGE = "education_system.systems.apprenticeships.interfaces.gui.windows"

# Appended to every role's menu. Account screens belong to everyone, so
# they are defined once rather than repeated five times — and adding a
# screen here can't then be forgotten for one role.
SYSTEM_CATEGORY: list[tuple[str, str]] = [
    ("Change Password", "system.change_password"),
    ("Multi-Factor Authentication", "system.mfa"),
    ("Settings", "system.settings"),
    ("About", "system.about"),
]

# Admin-only additions to that category.
SYSTEM_CATEGORY_ADMIN: list[tuple[str, str]] = [
    ("User Accounts", "system.user_accounts"),
]

# role -> [(category, [(label, module)])]. ``module`` is the dotted tail
# under _WINDOW_PACKAGE (a role package or ``shared``); each one exposes
# ``render(gui)``.
NAV_BY_ROLE: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {
    config.ADMIN: [
        ("Overview", [
            ("Dashboard", "admin.dashboard"),
            ("My Tasks", "shared.tasks"),
            ("Calendar", "shared.calendar"),
            ("Search", "shared.search"),
            ("Awaiting Signature", "shared.signatures"),
            ("Reports", "admin.reports"),
        ]),
        ("People", [
            ("Admissions", "shared.admissions"),
            ("Apprentices", "admin.apprentices"),
            ("Employers", "admin.employers"),
            ("Employer Contacts", "shared.employer_contacts"),
            ("Staff & Caseloads", "admin.staff"),
            ("Workload", "shared.workload"),
        ]),
        ("Cross-System", [
            ("University Progression", "shared.university_progression"),
            ("Learner Journey (360)", "shared.learner_journey"),
        ]),
        ("Delivery", [
            ("Programmes & KSBs", "admin.programmes"),
            ("Learning Plans", "shared.learning_plan"),
            ("Degree Apprenticeships", "admin.degree_apprenticeships"),
        ]),
        ("Progress", [
            ("Action Plans", "shared.actions"),
            ("Assignments", "shared.assignments"),
            ("Skills Matrix", "shared.skills_matrix"),
            ("Functional Skills", "shared.functional_skills"),
            ("Qualifications", "shared.qualifications"),
        ]),
        ("Support", [
            ("Support & Adjustments", "shared.support"),
            ("Welfare & Risk", "shared.welfare"),
        ]),
        ("Assurance", [
            ("Funding", "admin.funding"),
            ("Compliance", "admin.compliance"),
            ("Documents", "shared.documents"),
            ("Audit Log", "admin.audit_log"),
            ("Employer Risk", "admin.employer_risk"),
        ]),
        ("Quality", [
            ("Complaints", "shared.complaints"),
            ("Appeals", "shared.appeals"),
            ("Surveys", "shared.surveys"),
        ]),
        ("Communication", [
            ("Correspondence", "shared.email"),
        ]),
    ],
    config.STAFF: [
        ("Overview", [
            ("Dashboard", "staff.dashboard"),
            ("My Tasks", "shared.tasks"),
            ("Calendar", "shared.calendar"),
            ("Search", "shared.search"),
            ("Awaiting Signature", "shared.signatures"),
            ("My Caseload", "staff.caseload"),
            ("Workload", "shared.workload"),
            # Read-only for staff: a tutor plans around who is coming
            # without being able to admit them. The screen itself gates
            # the Accept/Decline buttons on admission.decide.
            ("Admissions Queue", "shared.admissions"),
        ]),
        # Read-only board for staff; submitting needs admission.decide.
        ("Cross-System", [
            ("University Progression", "shared.university_progression"),
            ("Learner Journey (360)", "shared.learner_journey"),
        ]),
        ("Delivery", [
            ("Learning Plans", "shared.learning_plan"),
            ("Training Sessions", "staff.training"),
            ("Off-the-Job Approvals", "staff.assessments"),
        ]),
        ("Assessment", [
            ("Portfolios", "staff.portfolios"),
            ("Progress Reviews", "staff.reviews"),
            ("Gateway Checks", "staff.gateway_checks"),
        ]),
        ("Progress", [
            ("Action Plans", "shared.actions"),
            ("Assignments", "shared.assignments"),
            ("Skills Matrix", "shared.skills_matrix"),
            ("Functional Skills", "shared.functional_skills"),
            ("Qualifications", "shared.qualifications"),
        ]),
        ("Support", [
            ("Support & Adjustments", "shared.support"),
            ("Welfare & Risk", "shared.welfare"),
            ("Employer Contacts", "shared.employer_contacts"),
            ("Documents", "shared.documents"),
        ]),
        ("Quality", [
            ("Complaints", "shared.complaints"),
            ("Surveys", "shared.surveys"),
        ]),
        ("Communication", [
            ("Correspondence", "shared.email"),
        ]),
    ],
    config.APPRENTICE: [
        ("My Apprenticeship", [
            ("Dashboard", "apprentice.dashboard"),
            ("My Tasks", "shared.tasks"),
            ("Calendar", "shared.calendar"),
            ("Search", "shared.search"),
            ("My Details", "apprentice.profile"),
            ("Learning Plan", "shared.learning_plan"),
        ]),
        ("My Evidence", [
            ("Off-the-Job Hours", "apprentice.off_the_job_hours"),
            ("Portfolio", "apprentice.portfolio"),
            ("Progress Reviews", "apprentice.reviews"),
            ("Action Plans", "shared.actions"),
            ("Assignments", "shared.assignments"),
            ("Skills Matrix", "shared.skills_matrix"),
            ("Functional Skills", "shared.functional_skills"),
            ("Qualifications", "shared.qualifications"),
            ("Documents", "shared.documents"),
        ]),
        ("Finishing", [
            ("Gateway", "apprentice.gateway"),
            ("End-Point Assessment", "apprentice.epa"),
        ]),
        ("Support & Feedback", [
            ("Support & Adjustments", "shared.support"),
            ("Awaiting Signature", "shared.signatures"),
            ("Complaints", "shared.complaints"),
            ("Appeals", "shared.appeals"),
            ("Surveys", "shared.surveys"),
        ]),
        ("Communication", [
            ("Messages", "shared.email"),
        ]),
    ],
    config.EMPLOYER: [
        ("Overview", [
            ("Dashboard", "employer.dashboard"),
            ("My Tasks", "shared.tasks"),
            ("Calendar", "shared.calendar"),
            ("Search", "shared.search"),
            ("My Apprentices", "employer.apprentices"),
            ("Learning Plans", "shared.learning_plan"),
            ("Skills Matrix", "shared.skills_matrix"),
            ("Qualifications", "shared.qualifications"),
            ("Support & Adjustments", "shared.support"),
        ]),
        ("Approvals", [
            ("Off-the-Job Hours", "employer.training"),
            ("Evidence", "employer.evidence"),
            ("Progress Reviews", "employer.reviews"),
            ("Action Plans", "shared.actions"),
            ("Awaiting Signature", "shared.signatures"),
            ("Documents", "shared.documents"),
        ]),
        ("Feedback", [
            ("Give Feedback", "employer.feedback"),
            ("Surveys", "shared.surveys"),
            ("Complaints", "shared.complaints"),
        ]),
        ("Communication", [
            ("Messages", "shared.email"),
        ]),
    ],
    config.END_POINT_ASSESSOR: [
        ("Overview", [
            ("Dashboard", "end_point_assessor.dashboard"),
            ("My Tasks", "shared.tasks"),
            ("Calendar", "shared.calendar"),
            ("Search", "shared.search"),
        ]),
        ("Assessment", [
            ("Gateway Requests", "end_point_assessor.gateway"),
            ("Bookings", "end_point_assessor.bookings"),
            ("Results", "end_point_assessor.results"),
            ("Resits", "end_point_assessor.resits"),
            ("Appeals", "shared.appeals"),
            ("EPA Documents", "shared.documents"),
            ("Complaints", "shared.complaints"),
        ]),
    ],
}


class ApprenticeshipsGUI:
    """The main window."""

    def __init__(self, auth, actor: Actor) -> None:
        self.auth = auth
        self.actor = actor
        self.root = tk.Tk()
        self.root.title(SYSTEM_NAME)
        window_sizing.fit(self.root, config.WIN_GEOMETRY, config.WIN_MINSIZE)

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.status_var = tk.StringVar(value="Ready")
        self.user_var = tk.StringVar(value=f"{actor.name} ({actor.role_label})")
        self.content_frame: ttk.Frame | None = None
        self._current: str | None = None

        self._idle_after: str | None = None
        self._idle_ms: int = 0
        self._build()
        self._open_default()
        self._start_idle_watch()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # There are five paths that destroy the root (idle timeout, close,
        # logout, switch to CLI, switch system) and a pending idle timer
        # outlives all of them: Tk then fires the callback into a torn-down
        # interpreter and reports
        #   invalid command name "<id>_idle_expired"
        # Cancelling on <Destroy> covers every path at once, including any
        # added later. <Destroy> fires for descendants too, so match the
        # root itself.
        self.root.bind("<Destroy>", self._cancel_idle_on_destroy, add="+")

    # ── Layout ──────────────────────────────────────────────────────

    def _build(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)

        self._build_header(main)
        self._build_nav(main)
        self._build_content(main)
        self._build_status(main)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        left = ttk.Frame(header)
        left.pack(side="left")
        ttk.Label(left, text=SYSTEM_NAME, font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(
            left,
            text=f"Signed in as {self.actor.name} — {self.actor.role_label}",
            foreground=config.MUTED_FG,
        ).pack(anchor="w")

        right = ttk.Frame(header)
        right.pack(side="right")
        ttk.Button(right, text="Switch to CLI", command=self._switch_to_cli).pack(
            side="left", padx=(0, 6)
        )
        try:
            from education_system.launcher.roles import is_superadmin

            if is_superadmin(getattr(self.auth, "current_user", None)):
                ttk.Button(
                    right, text="Switch System", command=self._switch_system
                ).pack(side="left", padx=(0, 6))
        except Exception:
            logger.debug("Could not evaluate superadmin status", exc_info=True)
        ttk.Button(right, text="Log out", command=self._logout).pack(side="left")
        ttk.Separator(parent, orient="horizontal").grid(
            row=0, column=0, columnspan=2, sticky="sew"
        )

    def _build_nav(self, parent: ttk.Frame) -> None:
        nav = ttk.LabelFrame(parent, text="Navigation", padding=6)
        nav.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        nav.rowconfigure(0, weight=1)
        nav.columnconfigure(0, weight=1)

        canvas = tk.Canvas(nav, width=250, highlightthickness=0)
        scrollbar = ttk.Scrollbar(nav, orient="vertical", command=canvas.yview)
        holder = ttk.Frame(canvas)
        holder_window = canvas.create_window((0, 0), window=holder, anchor="nw")

        holder.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(holder_window, width=event.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        def _on_wheel(event: tk.Event) -> str | None:
            """Scroll only when the pointer event came from this navigation pane."""
            widget = event.widget
            while widget is not None and widget is not canvas:
                try:
                    widget = widget.nametowidget(widget.winfo_parent())
                except (KeyError, tk.TclError):
                    widget = None
            if widget is not canvas:
                return None

            if getattr(event, "num", None) == 4:
                units = -1
            elif getattr(event, "num", None) == 5:
                units = 1
            else:
                delta = getattr(event, "delta", 0)
                if not delta:
                    return None
                units = -1 if delta > 0 else 1
            canvas.yview_scroll(units, "units")
            return "break"

        self.root.bind("<MouseWheel>", _on_wheel, add="+")
        self.root.bind("<Button-4>", _on_wheel, add="+")
        self.root.bind("<Button-5>", _on_wheel, add="+")

        for category, items in self.nav_tree():
            ttk.Label(
                holder, text=category.upper(), font=("", 8, "bold"),
                foreground=config.MUTED_FG,
            ).pack(anchor="w", pady=(10, 2))
            for label, module in items:
                ttk.Button(
                    holder, text=label, width=28,
                    command=self._opener(module, label),
                ).pack(anchor="w", pady=1)

        holder.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _build_content(self, parent: ttk.Frame) -> None:
        wrapper = ttk.Frame(parent, relief="flat")
        wrapper.grid(row=1, column=1, sticky="nsew")
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        self.content_frame = ttk.Frame(wrapper, padding=10)
        self.content_frame.grid(row=0, column=0, sticky="nsew")

    def _build_status(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent, orient="horizontal").grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(8, 4)
        )
        bar = ttk.Frame(parent)
        bar.grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Label(bar, textvariable=self.status_var, foreground=config.MUTED_FG).pack(
            side="left"
        )
        ttk.Label(
            bar, text=f"{FOOTER_LABEL} · v{VERSION}", foreground=config.MUTED_FG,
        ).pack(side="right")
        ttk.Label(bar, textvariable=self.user_var, foreground=config.MUTED_FG).pack()

    # ── Navigation ──────────────────────────────────────────────────

    def nav_tree(self) -> list[tuple[str, list[tuple[str, str]]]]:
        """The menu for this actor's role, plus the shared System group.

        An unrecognised role still gets the System group — enough to see
        who they are signed in as and why the rest is empty, which beats
        a blank window.
        """
        tree = list(NAV_BY_ROLE.get(self.actor.role, []))
        system = list(SYSTEM_CATEGORY)
        if self.actor.is_admin:
            system += SYSTEM_CATEGORY_ADMIN
        return [*tree, ("System", system)]

    def _opener(self, module: str, label: str) -> Callable[[], None]:
        return lambda: self.show(module, label)

    def show(self, module: str, label: str | None = None) -> None:
        """Render a screen into the content pane.

        A screen that fails to import or raises on render must not take
        the shell down with it — the user keeps their session and can
        navigate elsewhere, which matters more than surfacing the
        traceback in a dialog.
        """
        self.clear()
        assert self.content_frame is not None
        self._current = module
        title = label or module
        if module == "system.change_password":
            from education_system.platform.delivery.gui.change_password_gui import (
                ChangePasswordFrame,
            )

            ChangePasswordFrame(self.content_frame, auth=self.auth).pack(
                fill="both", expand=True
            )
            self.status_var.set("Account security · Change password")
            return
        if module == "system.mfa":
            # The shared multi-method wizard (authenticator app / SMS /
            # email / recovery codes), not the old TOTP-only settings frame.
            from education_system.platform.delivery.gui import mfa_setup_gui

            mfa_setup_gui.open_mfa(self, auth=self.auth)
            self.status_var.set("Account security · Multi-factor authentication")
            return
        try:
            screen = importlib.import_module(f"{_WINDOW_PACKAGE}.{module}")
            screen.render(self)
        except Exception as exc:
            logger.exception("Could not open %s", module)
            ttk.Label(
                self.content_frame, text=title, font=("", 16, "bold"),
            ).pack(anchor="w")
            ttk.Label(
                self.content_frame,
                text=f"This screen could not be opened.\n\n{exc}",
                foreground=config.ERROR_FG, justify="left",
            ).pack(anchor="w", pady=8)
            self.status_var.set(f"Failed to open {title}")
            return
        self.status_var.set(f"Opened: {title}")

    def refresh(self) -> None:
        """Re-render the current screen, after a change to its data."""
        if self._current:
            self.show(self._current)

    def clear(self) -> ttk.Frame:
        assert self.content_frame is not None
        for child in self.content_frame.winfo_children():
            child.destroy()
        return self.content_frame

    def _open_default(self) -> None:
        """Open the landing screen: the role's dashboard, or About.

        A role with no screens of its own still lands somewhere useful —
        About names the role and lists what it may do, which is exactly
        what someone seeing an unexpectedly bare menu needs to read.
        """
        role_tree = NAV_BY_ROLE.get(self.actor.role, [])
        if role_tree and role_tree[0][1]:
            label, module = role_tree[0][1][0]
        else:
            label, module = "About", "system.about"
        self.show(module, label)

    # ── Idle timeout ────────────────────────────────────────────────

    def _start_idle_watch(self) -> None:
        """Sign out after the user's idle timeout, if they set one.

        An apprenticeships desktop session sits on a shared provider
        workstation with an employer's whole cohort behind it, so an
        unattended one is a disclosure waiting to happen. Bound on the
        root with ``bind_all`` so activity anywhere — including inside a
        modal dialog — counts, and rescheduled rather than polled so an
        idle app does no work at all.
        """
        minutes = preferences.idle_timeout_minutes()
        if minutes <= 0:
            return
        self._idle_ms = minutes * 60 * 1000
        # Keys, clicks and the wheel, but not pointer motion: a mouse
        # nudged by a passing sleeve is not somebody using the machine,
        # and rescheduling the timer on every motion event would churn
        # for the whole session to no purpose.
        for sequence in ("<Any-KeyPress>", "<Any-Button>", "<MouseWheel>"):
            self.root.bind_all(sequence, self._note_activity, add="+")
        self._reschedule_idle()

    def _note_activity(self, _event=None) -> None:
        if self._idle_after is not None:
            self._reschedule_idle()

    def _reschedule_idle(self) -> None:
        if self._idle_after is not None:
            try:
                self.root.after_cancel(self._idle_after)
            except tk.TclError:
                pass
        self._idle_after = self.root.after(self._idle_ms, self._idle_expired)

    def _cancel_idle_on_destroy(self, event=None) -> None:
        """Drop any pending idle timer when the main window goes away."""
        if event is not None and event.widget is not self.root:
            return
        if self._idle_after is None:
            return
        try:
            self.root.after_cancel(self._idle_after)
        except tk.TclError:
            pass
        self._idle_after = None

    def _idle_expired(self) -> None:
        self._idle_after = None
        # The timer can still be in flight while the window is being torn
        # down; doing anything with a dead root raises TclError.
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return
        logger.info("Apprenticeships GUI idle timeout for user=%s", self.actor.username)
        from education_system import switch

        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout call failed", exc_info=True)
        messagebox.showinfo(
            "Signed out",
            "You were signed out after a period of inactivity.\n\n"
            "Change or switch this off under System → Settings.",
        )
        switch.request_logout("gui")
        self.root.destroy()

    # ── Session ─────────────────────────────────────────────────────

    def _switch_to_cli(self) -> None:
        from education_system import switch

        switch.request_switch("apprenticeships", "cli")
        self.root.destroy()

    def _switch_system(self) -> None:
        from education_system import switch
        from education_system.launcher.system_switch import pick_system_gui

        target = pick_system_gui(
            self.root, getattr(self.auth, "current_user", None), "apprenticeships"
        )
        if target:
            switch.request_switch(target, "gui")
            self.root.destroy()

    def _logout(self) -> None:
        if not messagebox.askyesno("Log out", "Sign out and return to the login screen?"):
            return
        from education_system import switch

        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout call failed", exc_info=True)
        switch.request_logout("gui")
        self.root.destroy()

    def _on_close(self) -> None:
        from education_system import switch

        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout call failed", exc_info=True)
        switch.request_exit()
        self.root.destroy()


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Launch the GUI for an already-authenticated session.

    The unified launcher calls this after the universal login succeeds.
    There is no per-system login — an unauthenticated call is a bug in
    the caller, not a prompt to ask for a password.
    """
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("Apprenticeships GUI invoked without a shared_auth session")
        raise RuntimeError(
            "The apprenticeships GUI must be launched via python -m education_system — "
            "no standalone login is available."
        )
    branding.set_system_name(SYSTEM_NAME)
    actor = resolve(user_info or shared_auth.current_user, role)
    # Loaded once here rather than per widget: ``widgets._display`` reads
    # them for every cell on the screen and has no actor to hand.
    preferences.activate(actor.username)
    logger.info(
        "Apprenticeships GUI starting for user=%s role=%s", actor.username, actor.role
    )
    app = ApprenticeshipsGUI(shared_auth, actor)
    app.root.mainloop()
    logger.info("Apprenticeships GUI exited for user=%s", actor.username)
    return 0


if __name__ == "__main__":
    print("Launch via: python -m education_system --apprenticeships --gui")
    raise SystemExit(2)
