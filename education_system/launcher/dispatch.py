"""GUI and CLI dispatch loops with system-switch handling."""

import logging
import sys

from education_system.launcher.auth import gui_universal_login, cli_universal_login
from education_system.launcher.roles import is_superadmin, pick_role_gui, pick_role_cli
from education_system.launcher.systems import (
    LAUNCHERS,
    AUTH_GUI_SYSTEMS,
    AUTH_CLI_SYSTEMS,
)

logger = logging.getLogger(__name__)


def dispatch_gui(user_info, system, role, shared_auth):
    """Run the GUI dispatch loop, handling system switches and superadmin."""
    mode = "gui"

    while True:
        if system == "__superadmin__":
            try:
                from education_system.shared.gui.superadmin_dashboard import SuperAdminDashboard
                dashboard = SuperAdminDashboard(user_info, shared_auth)
                dashboard.mainloop()

                if dashboard.shutdown:
                    print("\n  Shutting down. Goodbye.\n")
                    sys.exit(0)

                if dashboard.switch_to_cli:
                    print("\n  Switching to CLI dashboard...\n")
                    dispatch_cli(user_info, "__superadmin__", role, shared_auth)
                    break

                if dashboard.logged_out:
                    result = gui_universal_login()
                    if result is None:
                        break
                    user_info, system, role, shared_auth = result
                    continue

                if dashboard.launch_system:
                    system = dashboard.launch_system
                    role = pick_role_gui(system)
                    continue

                break
            except Exception as e:
                logger.error("Superadmin dashboard error: %s", e, exc_info=True)
                print(f"\n  Dashboard error: {e}")
                break

        launcher = LAUNCHERS.get((system, mode))
        if launcher is None:
            print(f"  Unknown combination: {system} + {mode}")
            sys.exit(1)

        try:
            if system in AUTH_GUI_SYSTEMS:
                launcher(user_info=user_info, role=role, shared_auth=shared_auth)
            else:
                launcher()
        except KeyboardInterrupt:
            print("\n\n  Interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error("Error: %s", e, exc_info=True)
            print(f"\n  Error: {e}")
            sys.exit(1)

        from education_system.switch import consume
        switch_request = consume()
        if switch_request is not None and switch_request[0] == "__exit__":
            # The window-manager close handler asked for a clean
            # exit. Honour that even for superadmins — don't bounce
            # them back to the superadmin dashboard.
            break
        if switch_request is None:
            if is_superadmin(user_info):
                system = "__superadmin__"
                continue
            break
        system, mode = switch_request

        # If the switch flips into CLI mode (the user chose "Switch to CLI",
        # or a CLI launcher we ran requested logout), hand the session to the
        # CLI dispatcher. That way its CLI login prompt is used on any later
        # logout — not the GUI login. Symmetric with dispatch_cli below.
        if mode == "cli":
            if system == "__login__":
                result = cli_universal_login()
                if result is None:
                    break
                user_info, system, role, shared_auth = result
            dispatch_cli(user_info, system, role, shared_auth)
            return

        if system == "__login__":
            result = gui_universal_login()
            if result is None:
                break
            user_info, system, role, shared_auth = result
            continue

        if system == "__superadmin__":
            continue

        print(f"\n  Switching to {system} ({mode})...\n")

        if mode == "gui":
            target_role = None
            if user_info:
                for s in user_info.get("systems", []):
                    if s["system_key"] == system:
                        target_role = s["role"]
                        break
            if target_role:
                if is_superadmin(user_info):
                    role = pick_role_gui(system)
                else:
                    role = target_role
            else:
                result = gui_universal_login()
                if result is None:
                    break
                user_info, system, role, shared_auth = result


def dispatch_cli(user_info, system, role, shared_auth):
    """Run the CLI dispatch loop, handling system switches and superadmin."""
    mode = "cli"

    while True:
        if system == "__superadmin__":
            try:
                from education_system.shared.cli.superadmin_cli import run as superadmin_cli_run
                result = superadmin_cli_run(user_info, shared_auth)
                if result:
                    system, _launch_role = result
                    role = pick_role_cli(system)
                    continue

                # CLI returned None — might be a scheduled mode switch.
                from education_system.switch import consume
                pending = consume()
                if pending == ("__superadmin__", "gui"):
                    dispatch_gui(user_info, "__superadmin__", role, shared_auth)
                    break

                result = cli_universal_login()
                if result is None:
                    break
                user_info, system, role, shared_auth = result
                continue
            except KeyboardInterrupt:
                print("\n\n  Interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error("Error: %s", e, exc_info=True)
                print(f"\n  Error: {e}")
                sys.exit(1)

        launcher = LAUNCHERS.get((system, mode))
        if launcher is None:
            print(f"  Unknown combination: {system} + {mode}")  # lgtm[py/clear-text-logging-sensitive-data]
            sys.exit(1)

        try:
            if system in AUTH_CLI_SYSTEMS:
                launcher(user_info=user_info, role=role, shared_auth=shared_auth)
            else:
                launcher()
        except KeyboardInterrupt:
            print("\n\n  Interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error("Error: %s", e, exc_info=True)
            print(f"\n  Error: {e}")
            sys.exit(1)

        from education_system.switch import consume
        switch_request = consume()
        if switch_request is not None and switch_request[0] == "__exit__":
            break
        if switch_request is None:
            if is_superadmin(user_info):
                system = "__superadmin__"
                continue
            break
        system, mode = switch_request

        # Mirror of dispatch_gui: if the switch flips into GUI mode, hand the
        # session to the GUI dispatcher so its GUI login is used on any later
        # logout — not the CLI login.
        if mode == "gui":
            if system == "__login__":
                result = gui_universal_login()
                if result is None:
                    break
                user_info, system, role, shared_auth = result
            dispatch_gui(user_info, system, role, shared_auth)
            return

        if system == "__login__":
            result = cli_universal_login()
            if result is None:
                break
            user_info, system, role, shared_auth = result
            continue

        if system == "__superadmin__":
            continue

        print(f"\n  Switching to {system} ({mode})...\n")

        if mode == "cli":
            target_role = None
            if user_info:
                for s in user_info.get("systems", []):
                    if s["system_key"] == system:
                        target_role = s["role"]
                        break
            if target_role:
                if is_superadmin(user_info):
                    role = pick_role_cli(system)
                else:
                    role = target_role
            else:
                result = cli_universal_login()
                if result is None:
                    break
                user_info, system, role, shared_auth = result
