"""Extracted function implementation."""
import logging

logger = logging.getLogger(__name__)

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def open_in_workspace(self, title, builder, *, focus=True):
    """Render a feature inside the dashboard's notebook as a tab,
    instead of opening it as a Toplevel.

    Closes the "right content panel is decorative" gap from the
    8.117.16 layout review: any launcher that calls this method gets
    its UI hosted inside the main window's existing dashboard
    notebook (created by ``show_integrated_dashboard``) rather than
    spinning up a Toplevel that leaves the panel inert.

    Falls back gracefully when the workspace isn't available
    (e.g. user hasn't logged in yet, or the dashboard hasn't been
    rendered for this session). The caller's ``builder`` is invoked
    with the tab's frame regardless — but if there's no workspace
    notebook, the builder gets a freshly-created Toplevel's inner
    frame instead, preserving the old behaviour for the legacy path.

    Parameters
    ----------
    title : str
        Tab label. If a tab with this exact title already exists,
        the existing tab is raised rather than duplicated. Match is
        exact (case-sensitive) so a launcher that appends contextual
        info (e.g. ``"Library — S12345"``) will get a new tab while
        the same launcher with no context lands on the existing one.
    builder : callable(parent_frame) -> Any
        Populates the tab's frame. Return value is discarded; the
        builder is expected to ``pack``/``grid`` widgets onto the
        supplied frame.
    focus : bool
        If True (default), select the tab after construction so the
        user lands on what they just opened. Set to False for tabs
        that should open in the background.

    Returns
    -------
    Frame | None
        The frame the builder rendered into, or ``None`` if neither
        the workspace notebook nor a fallback Toplevel could be
        created.
    """
    import tkinter as tk
    from tkinter import ttk

    # Lazy-init the tracking dict — first launcher to opt in won't
    # have seen show_integrated_dashboard yet on a fresh session.
    if not hasattr(self, 'workspace_tabs') or self.workspace_tabs is None:
        self.workspace_tabs = {}

    nb = getattr(self, 'workspace_notebook', None)
    nb_alive = False
    if nb is not None:
        try:
            nb_alive = bool(nb.winfo_exists())
        except Exception:
            nb_alive = False

    if nb_alive:
        # Existing tab? Raise it.
        existing = self.workspace_tabs.get(title)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    if focus:
                        nb.select(existing)
                    return existing
            except Exception:
                # Stale entry — fall through and rebuild.
                self.workspace_tabs.pop(title, None)

        tab = ttk.Frame(nb)
        nb.add(tab, text=title)
        self.workspace_tabs[title] = tab

        # Add a small "✕" close affordance via right-click on the
        # tab's title cell. Cheap; no need for a custom tab
        # implementation.
        def _close_tab(_e=None, t=title, fr=tab):
            # forget() alone leaves the whole embedded portal alive under the
            # notebook; closing tabs leaked a screen each until X ran out of
            # pixmaps. Destroy it, which also clears the stale
            # workspace_tabs entry's winfo_exists() check on reopen.
            from education_system.platform.delivery.gui.portal_dismiss import forget_tab
            forget_tab(nb, fr)
            self.workspace_tabs.pop(t, None)
        try:
            # Tk doesn't expose per-tab right-click directly; bind
            # globally on the notebook and only act if the click
            # landed on this title's tab index.
            def _maybe_close(event, fr=tab, closer=_close_tab):
                try:
                    idx = nb.index(f"@{event.x},{event.y}")
                    if nb.tabs()[idx] == str(fr):
                        closer()
                except (tk.TclError, IndexError):
                    pass
            nb.bind("<Button-3>", _maybe_close, add="+")
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        try:
            builder(tab)
        except Exception:
            logger.exception("workspace tab builder failed for %s", title)
        if focus:
            try:
                nb.select(tab)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        return tab

    # Fallback: no workspace notebook (pre-login, or content area
    # was cleared and not rebuilt). Spin up a Toplevel and hand the
    # builder its inner frame — preserves the pre-8.117.18 launcher
    # behaviour so callers that haven't migrated still work.
    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(title)
        win.geometry("1400x900")
        try:
            win.transient(self.root)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        outer = ttk.Frame(win)
        outer.pack(fill="both", expand=True)
        try:
            builder(outer)
        except Exception:
            logger.exception("Toplevel-fallback builder failed for %s", title)
        return outer
    except Exception:
        logger.exception("open_in_workspace fallback Toplevel failed")
        return None
