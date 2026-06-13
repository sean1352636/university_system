"""Shared switch state for transitioning between systems and interfaces."""

# Set this to a (system, mode) tuple to request a switch on exit.
# e.g. ("college", "cli"), ("university", "gui")
# ("__login__", "gui") means return to the universal login screen.
# None means exit normally.
next_action: tuple[str, str] | None = None


def request_switch(system: str, mode: str):
    """Request a switch to another system/mode after the current one exits."""
    global next_action
    next_action = (system, mode)


def request_logout(mode: str = "gui"):
    """Request a return to the universal login screen after the current system exits."""
    global next_action
    next_action = ("__login__", mode)


def request_exit():
    """Request a clean shutdown after the current system exits.

    Used by the window-manager close handler so a superadmin who is
    finished doesn't get bounced back to the superadmin dashboard
    after closing the system they were working in. The dispatcher
    treats the ``"__exit__"`` sentinel as a final break.
    """
    global next_action
    next_action = ("__exit__", "")


def consume() -> tuple[str, str] | None:
    """Return and clear the pending switch request."""
    global next_action
    action = next_action
    next_action = None
    return action
