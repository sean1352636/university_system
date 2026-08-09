"""
Password Reset Dashboard
------------------------
A Tkinter GUI to manage forced password resets across the education systems,
wired to the shared :class:`UserAuth` backend.

Features:
  * A master switch that turns the forced-password-reset policy ON/OFF for
    ALL systems at once.
  * An individual toggle for each education system (Nursery, Primary,
    Secondary, Sixth Form College, University).
  * A per-system "Force now" action that forces every user in that system to
    reset their password at their next login.
  * The master switch stays in sync with the individual states:
      - Turning master ON  -> every system policy ON.
      - Turning master OFF -> every system policy OFF.
      - If all systems are individually ON, the master shows ON automatically.

Every toggle persists to the shared ``auth_settings`` table via
``UserAuth.set_system_password_policy`` / ``force_system_password_reset``, so
this dashboard reflects and controls the real login behaviour.

Run standalone with:  python education_system/shared/gui/password_reset_dashboard.py
Or embed ``PasswordResetDashboardFrame(parent, auth)`` inside another window.
"""

import tkinter as tk
from tkinter import messagebox

try:  # absolute import works when run as part of the package
    from education_system.platform.identity.auth.defaults import SYSTEMS
except ModuleNotFoundError:  # allow running this file directly
    import os
    import sys
    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    )
    from education_system.platform.identity.auth.defaults import SYSTEMS


# ---- Configuration -------------------------------------------------------

# Display order for the education systems (youngest -> oldest). Any system in
# SYSTEMS but missing here is appended automatically (see __init__).
SYSTEM_ORDER = [
    "nursery", "primary", "secondary", "sixth_form", "university",
]

# Colors
COLOR_ON = "#2e7d32"       # green
COLOR_OFF = "#c62828"      # red
COLOR_BG = "#1e1e2e"
COLOR_CARD = "#2a2a3c"
COLOR_TEXT = "#e0e0e0"
COLOR_MUTED = "#9e9e9e"
COLOR_MASTER = "#3949ab"
COLOR_WARN = "#e67e22"


class PasswordResetDashboardFrame(tk.Frame):
    """Embeddable dashboard bound to a ``UserAuth`` instance.

    *parent* is any Tk container; *auth* is a shared ``UserAuth`` object
    exposing the per-system password-policy helpers.
    """

    def __init__(self, parent, auth):
        super().__init__(parent, bg=COLOR_BG)
        self.auth = auth

        # Only surface systems we actually know about, in display order.
        ordered = [k for k in SYSTEM_ORDER if k in SYSTEMS]
        # Include any extra systems defined in SYSTEMS but missing from the order.
        ordered += [k for k in SYSTEMS if k not in ordered]
        self.systems = [(k, SYSTEMS[k]) for k in ordered]

        # State: one boolean per system (True = policy ON)
        self.states = {k: tk.BooleanVar(value=False) for k, _ in self.systems}
        self.master_state = tk.BooleanVar(value=False)

        # Guard flag to avoid recursive callbacks when syncing states
        self._syncing = False

        self.system_buttons = {}
        self.system_dots = {}
        self.pending_labels = {}

        self._build_header()
        self._build_master_switch()
        self._build_system_list()
        self._build_status_bar()

        self._load_state()

    # ---- UI construction ------------------------------------------------

    def _build_header(self):
        tk.Label(
            self,
            text="\U0001f510  Forced Password Reset",
            font=("Segoe UI", 18, "bold"),
            bg=COLOR_BG,
            fg=COLOR_TEXT,
        ).pack(pady=(20, 5))

        tk.Label(
            self,
            text="Manage forced password resets across every education system",
            font=("Segoe UI", 10),
            bg=COLOR_BG,
            fg=COLOR_MUTED,
        ).pack(pady=(0, 15))

    def _build_master_switch(self):
        frame = tk.Frame(self, bg=COLOR_MASTER, padx=15, pady=12)
        frame.pack(fill="x", padx=20, pady=(0, 15))

        tk.Label(
            frame,
            text="ALL SYSTEMS",
            font=("Segoe UI", 12, "bold"),
            bg=COLOR_MASTER,
            fg="white",
        ).pack(side="left")

        self.master_btn = tk.Button(
            frame,
            text="OFF",
            width=8,
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            command=self._toggle_master,
            cursor="hand2",
        )
        self.master_btn.pack(side="right")

    def _build_system_list(self):
        # Scrollable list so all systems fit however small the window is.
        outer = tk.Frame(self, bg=COLOR_BG)
        outer.pack(fill="both", expand=True, padx=20)

        canvas = tk.Canvas(outer, bg=COLOR_BG, highlightthickness=0)
        scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        container = tk.Frame(canvas, bg=COLOR_BG)

        container.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        win = canvas.create_window((0, 0), window=container, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Mouse-wheel scrolling while the pointer is over the list.
        def _on_mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mw))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        for key, label in self.systems:
            card = tk.Frame(container, bg=COLOR_CARD, padx=12, pady=10)
            card.pack(fill="x", pady=5)

            # Status dot
            dot = tk.Label(
                card, text="●", font=("Segoe UI", 14),
                bg=COLOR_CARD, fg=COLOR_OFF,
            )
            dot.pack(side="left", padx=(0, 10))
            self.system_dots[key] = dot

            # Name + pending status stacked
            name_col = tk.Frame(card, bg=COLOR_CARD)
            name_col.pack(side="left", fill="x", expand=True)
            tk.Label(
                name_col, text=label, font=("Segoe UI", 12),
                bg=COLOR_CARD, fg=COLOR_TEXT, anchor="w",
            ).pack(anchor="w")
            pending = tk.Label(
                name_col, text="", font=("Segoe UI", 8),
                bg=COLOR_CARD, fg=COLOR_WARN, anchor="w",
            )
            pending.pack(anchor="w")
            self.pending_labels[key] = pending

            # "Force now" button (one-time forced reset for that system)
            tk.Button(
                card, text="Force now", font=("Segoe UI", 9),
                relief="flat", cursor="hand2", bg="#4a4a5e", fg="white",
                activebackground="#5a5a6e", activeforeground="white",
                command=lambda k=key: self._force_now(k),
            ).pack(side="right", padx=(0, 8))

            # Policy toggle button
            btn = tk.Button(
                card, text="OFF", width=8, font=("Segoe UI", 10, "bold"),
                relief="flat", cursor="hand2",
                command=lambda k=key: self._toggle_system(k),
            )
            btn.pack(side="right")
            self.system_buttons[key] = btn

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="")
        tk.Label(
            self,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            bg=COLOR_BG,
            fg=COLOR_MUTED,
        ).pack(pady=(10, 15))

    # ---- Backend sync ---------------------------------------------------

    def _load_state(self):
        """Pull the current policy + pending state from the auth backend."""
        overview = {}
        try:
            overview = {o["system"]: o for o in self.auth.get_password_policy_overview()}
        except Exception as exc:  # pragma: no cover - defensive
            messagebox.showerror(
                "Error", f"Could not load password policy: {exc}",
                parent=self.winfo_toplevel(),
            )
        for key, _ in self.systems:
            info = overview.get(key, {})
            self.states[key].set(bool(info.get("policy_enabled", False)))
            self._render_pending(key, info.get("pending_since"))
        self._refresh_all()

    def _persist_policy(self, key, value):
        """Write one system's policy to the backend; revert on failure."""
        try:
            self.auth.set_system_password_policy(key, value)
            return True
        except Exception as exc:
            self.states[key].set(not value)
            messagebox.showerror(
                "Error", f"Failed to update {key}: {exc}",
                parent=self.winfo_toplevel(),
            )
            return False

    def _render_pending(self, key, pending_since):
        label = self.pending_labels.get(key)
        if not label:
            return
        if pending_since:
            stamp = str(pending_since)[:16].replace("T", " ")
            label.config(text=f"⚠ forced reset pending since {stamp}")
        else:
            label.config(text="")

    # ---- Logic ----------------------------------------------------------

    def _toggle_master(self):
        """Force every system's policy to the master's new state."""
        new_value = not self.master_state.get()
        if not messagebox.askyesno(
            "All Systems",
            f"Turn the forced-password-reset policy {'ON' if new_value else 'OFF'} "
            "for ALL systems?",
            parent=self.winfo_toplevel(),
        ):
            return

        self.master_state.set(new_value)
        self._syncing = True
        for key, _ in self.systems:
            self.states[key].set(new_value)
            self._persist_policy(key, new_value)
        self._syncing = False
        self._refresh_all()

    def _toggle_system(self, key):
        """Flip a single system's policy, then re-derive the master state."""
        new_value = not self.states[key].get()
        self.states[key].set(new_value)
        if not self._persist_policy(key, new_value):
            self._refresh_all()
            return

        if not self._syncing:
            all_on = all(var.get() for var in self.states.values())
            self.master_state.set(all_on)
        self._refresh_all()

    def _force_now(self, key):
        """Force every user in *key* to reset their password on next login."""
        label = SYSTEMS.get(key, key)
        if not messagebox.askyesno(
            "Force Password Reset",
            f"Force all {label} users to reset their password on next login?",
            parent=self.winfo_toplevel(),
        ):
            return
        try:
            self.auth.force_system_password_reset(key)
        except Exception as exc:
            messagebox.showerror(
                "Error", f"Failed: {exc}", parent=self.winfo_toplevel(),
            )
            return
        # Reload so the pending indicator reflects the new epoch.
        self._load_state()
        messagebox.showinfo(
            "Done",
            f"{label} users will be prompted to reset at their next login.",
            parent=self.winfo_toplevel(),
        )

    # ---- Rendering ------------------------------------------------------

    def _refresh_all(self):
        self._style_button(self.master_btn, self.master_state.get())

        on_count = 0
        for key, _ in self.systems:
            is_on = self.states[key].get()
            on_count += is_on
            self._style_button(self.system_buttons[key], is_on)
            self.system_dots[key].config(fg=COLOR_ON if is_on else COLOR_OFF)

        self.status_var.set(
            f"{on_count} of {len(self.systems)} systems enforcing password reset"
        )

    @staticmethod
    def _style_button(button, is_on):
        button.config(
            text="ON" if is_on else "OFF",
            bg=COLOR_ON if is_on else COLOR_OFF,
            fg="white",
            activebackground=COLOR_ON if is_on else COLOR_OFF,
            activeforeground="white",
        )


class PasswordResetDashboard(tk.Tk):
    """Standalone window wrapper around :class:`PasswordResetDashboardFrame`."""

    def __init__(self, auth=None):
        super().__init__()
        self.title("Password Reset Dashboard")
        self.configure(bg=COLOR_BG)
        self.geometry("500x640")
        self.minsize(480, 560)

        if auth is None:
            from education_system.platform.identity.auth.core import UserAuth
            auth = UserAuth()

        self.frame = PasswordResetDashboardFrame(self, auth)
        self.frame.pack(fill="both", expand=True)


if __name__ == "__main__":
    PasswordResetDashboard().mainloop()
