"""Standalone Tk window for SSO identity providers (admin only).

Launched as a subprocess by the main GUI (``_NEW_FEATURE_MODULES``); the
signed-in user arrives via ``require_launcher_auth``. Lists, configures,
enables/disables and dry-run tests providers through ``SSOService`` via
``infrastructure.auth.sso_admin``. The login flow is untouched and SAML
fails closed while python3-saml is absent. No DB access at import time.
"""
from __future__ import annotations

import json
import logging
import pathlib
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

from education_system.systems.university.infrastructure.auth import sso_admin  # noqa: E402
from education_system.systems.university.infrastructure.i18n import get_text as _t  # noqa: E402

logger = logging.getLogger(__name__)

_CONFIG_HINT = (
    'Config as a JSON object, e.g.\n{"client_id": "...", "client_secret": "...", '
    '"authorization_endpoint": "...", "token_endpoint": "...", "redirect_uri": "..."}'
)


class SSOProvidersApp(tk.Frame):
    """Providers on the left; the selected provider's record (secrets masked) on the right."""

    def __init__(self, parent, user=None):
        super().__init__(parent)
        self._user = user or {}
        self._actor = str(self._user.get("username") or self._user.get("id") or "unknown")
        self._svc = sso_admin.build_sso_service()
        self._build()
        self.refresh()

    def _build(self):
        header = tk.Frame(self, bg="#2c3e50")
        header.pack(fill="x")
        tk.Label(header, text=_t("gui.admin.sso_providers.title", default="SSO Providers"),
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(side="left", padx=16, pady=8)
        tk.Label(header, text=f"Signed in: {self._actor} ({self._user.get('role') or '-'})",
                 bg="#2c3e50", fg="#bdc3c7").pack(side="right", padx=16)

        status = " | ".join(
            f"{row['label']}: {'available' if row['available'] else 'UNAVAILABLE (fails closed)'}"
            for row in sso_admin.provider_type_status())
        tk.Label(self, text=status, anchor="w", fg="#555555").pack(fill="x", padx=12, pady=(6, 0))

        bar = tk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        for label, cmd in (("Refresh", self.refresh), ("Add / Update", self.configure),
                           ("Enable", lambda: self.set_enabled(True)),
                           ("Disable", lambda: self.set_enabled(False)),
                           ("Test", self.test)):
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=4)

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("provider_id", "provider_type", "is_enabled", "display_name", "updated_at")
        self._tree = ttk.Treeview(panes, columns=cols, show="headings")
        for col, width in zip(cols, (160, 70, 70, 220, 140)):
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=width, stretch=col == "display_name")
        self._tree.bind("<<TreeviewSelect>>", lambda _e: self.show_detail())
        panes.add(self._tree, weight=3)
        self._detail = tk.Text(panes, wrap="word", state="disabled", width=55)
        panes.add(self._detail, weight=2)

    def _selected_id(self) -> str | None:
        sel = self._tree.focus()
        return self._tree.item(sel, "values")[0] if sel else None

    def _set_detail(self, text: str):
        self._detail.config(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", text)
        self._detail.config(state="disabled")

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        for p in self._svc.list_providers(enabled_only=False):
            self._tree.insert("", "end", values=(
                p["provider_id"], p["provider_type"], "yes" if p["is_enabled"] else "no",
                p["display_name"], str(p["updated_at"] or "")[:19]))
        self._set_detail("")

    def show_detail(self):
        provider = self._svc.get_provider(self._selected_id() or "")
        if not provider:
            return
        config = provider.pop("config", {})
        lines = [f"{key}: {value}" for key, value in provider.items()]
        lines.append("\nconfig:")
        for key, value in config.items():
            lines.append(f"  {key}: {'********' if 'secret' in key.lower() else value}")
        allowed, why = sso_admin.can_enable(provider)
        if not allowed:
            lines.append(f"\n{why}")
        self._set_detail("\n".join(lines))

    def configure(self):
        provider_id = simpledialog.askstring("Add / Update", "Provider ID (new or existing):",
                                             initialvalue=self._selected_id() or "", parent=self)
        if not provider_id:
            return
        provider_type = simpledialog.askstring("Add / Update", "Type (oidc/saml):", parent=self)
        display_name = simpledialog.askstring("Add / Update", "Display name:", parent=self)
        raw = simpledialog.askstring("Add / Update", _CONFIG_HINT, parent=self)
        if not provider_type or not display_name or raw is None:
            return
        try:
            config = json.loads(raw or "{}")
            if not isinstance(config, dict):
                raise ValueError("Config must be a JSON object")
            result = self._svc.register_provider(
                provider_id.strip(), provider_type.strip(), display_name.strip(), config)
        except (ValueError, *sso_admin.SSO_ERRORS) as exc:
            messagebox.showerror("Add / Update", str(exc), parent=self)
            return
        messagebox.showinfo("Add / Update", result["message"], parent=self)
        self.refresh()

    def set_enabled(self, enabled: bool):
        provider_id = self._selected_id()
        if not provider_id:
            messagebox.showwarning("SSO Providers", "Select a provider first.", parent=self)
            return
        provider = self._svc.get_provider(provider_id)
        if enabled and provider:
            allowed, why = sso_admin.can_enable(provider)
            if not allowed:
                messagebox.showerror("Enable", why, parent=self)
                return
        try:
            self._svc.set_provider_enabled(provider_id, enabled)
        except sso_admin.SSO_ERRORS as exc:
            messagebox.showerror("SSO Providers", str(exc), parent=self)
            return
        self.refresh()

    def test(self):
        provider = self._svc.get_provider(self._selected_id() or "")
        if not provider:
            messagebox.showwarning("Test", "Select a provider first.", parent=self)
            return
        result = sso_admin.test_provider(self._svc, provider)
        text = result["message"] + (f"\n\nauth_url:\n{result['auth_url']}" if result["auth_url"] else "")
        (messagebox.showinfo if result["ok"] else messagebox.showerror)("Test", text, parent=self)


def main() -> None:
    from education_system.platform.delivery.gui.window_sizing import install
    from education_system.systems.university.shell.gui.auth.launch_guard import require_launcher_auth

    user = require_launcher_auth("SSO Providers")
    if user is None:
        return
    if not sso_admin.is_admin(user):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("SSO Providers", "SSO provider management is admin only.")
        root.destroy()
        return
    install()
    root = tk.Tk()
    root.title(_t("gui.admin.sso_providers.title", default="SSO Providers"))
    root.geometry("1400x900")
    root.minsize(1200, 800)
    try:
        SSOProvidersApp(root, user=user).pack(fill="both", expand=True)
    except Exception as exc:
        logger.exception("SSO service unavailable")
        messagebox.showerror("SSO Providers", f"SSO service unavailable:\n{exc}", parent=root)
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
