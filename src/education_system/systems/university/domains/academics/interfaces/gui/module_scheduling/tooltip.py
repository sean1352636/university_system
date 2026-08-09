"""Tiny Tk tooltip helper.

Attach with ``Tooltip(widget, "text")``. The tooltip shows after a short
hover delay and disappears on mouse-leave. There's no system-wide tooltip
in stdlib Tk so each project re-rolls one of these — this is the smallest
version that handles the lifecycle correctly (no leaked Toplevels when the
user mouses out fast).
"""

import tkinter as tk

DEFAULT_DELAY_MS = 500


class Tooltip:
    """Simple hover-tooltip for any Tk widget.

    Usage:
        Tooltip(my_button, "What this button does")
    """

    def __init__(self, widget, text: str, *, delay_ms: int = DEFAULT_DELAY_MS):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self._cancel_pending()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event=None):
        self._cancel_pending()
        self._hide()

    def _cancel_pending(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        self._after_id = None
        if self._tip_window is not None or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except Exception:
            return
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background="#ffffe0", relief=tk.SOLID, borderwidth=1,
            font=("Arial", 9), padx=6, pady=3, wraplength=320,
        )
        label.pack()
        self._tip_window = tw

    def _hide(self):
        if self._tip_window is not None:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None
