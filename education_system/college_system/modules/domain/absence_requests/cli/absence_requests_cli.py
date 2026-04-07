"""CLI interface for absence requests management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.absence_requests.services.absence_requests_service import (
    AbsenceRequestService, ABSENCE_TYPES, VALID_STATUSES,
)
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.shared.auth.role_manager import RoleManager


def _require_login(auth: UserAuth) -> dict | None:
    """Check the user is logged in. Returns current_user or None."""
    if not auth.is_logged_in:
        print("\n  Access denied. You must be logged in to use this module.")
        return None
    return auth.current_user


def _get_user_role(auth: UserAuth) -> str | None:
    """Get the user's role for the college system."""
    return auth.get_role_for_system("college")


def _is_staff_or_above(auth: UserAuth) -> bool:
    """Check if user has staff or admin role."""
    role = _get_user_role(auth)
    if not role:
        return False
    rm = RoleManager()
    return rm.has_minimum_role(role, "staff")


def _get_staff_id(user: dict) -> int:
    """Extract staff/user ID from the current user dict."""
    return user.get("user_id") or user.get("id")


_STATUS_COLOURS = {
    "pending": "\033[33m",    # yellow
    "approved": "\033[32m",   # green
    "rejected": "\033[31m",   # red
    "cancelled": "\033[90m",  # grey
}
_RESET = "\033[0m"


def _coloured_status(status: str) -> str:
    colour = _STATUS_COLOURS.get(status, "")
    return f"{colour}{status}{_RESET}" if colour else status


def absence_requests_menu(auth: UserAuth):
    """Absence Requests management menu."""
    user = _require_login(auth)
    if not user:
        return

    service = AbsenceRequestService(auth._db_path)
    is_manager = _is_staff_or_above(auth)
    display_name = user.get("display_name", user.get("username", "User"))

    while True:
        print_header("Absence Requests")
        print(f"  Logged in as: {display_name}")
        role = _get_user_role(auth) or "unknown"
        print(f"  Role: {role}\n")

        options = [
            ("1", "My Requests"),
            ("2", "Submit New Request"),
            ("3", "View Request Details"),
            ("4", "Cancel My Request"),
        ]
        if is_manager:
            options.extend([
                ("", "--- Manager Actions ---"),
                ("5", "All Requests"),
                ("6", "Filter Requests by Status"),
                ("7", "Approve Request"),
                ("8", "Reject Request"),
                ("9", "Update Request"),
                ("D", "Delete Request"),
            ])
        options.append(("0", "Back"))
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _my_requests(service, user)
        elif choice == "2":
            _submit_request(service, user)
        elif choice == "3":
            _view_request(service)
        elif choice == "4":
            _cancel_request(service, user)
        elif choice == "5" and is_manager:
            _list_requests(service)
        elif choice == "6" and is_manager:
            _filter_by_status(service)
        elif choice == "7" and is_manager:
            _approve_request(service, user)
        elif choice == "8" and is_manager:
            _reject_request(service, user)
        elif choice == "9" and is_manager:
            _update_request(service)
        elif choice == "D" and is_manager:
            _delete_request(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _print_request_table(items: list[dict]):
    """Print a formatted table of absence requests."""
    if not items:
        print("\n  No requests found.")
        return
    print()
    header = f"  {'ID':<6}{'Staff ID':<10}{'Type':<22}{'Start':<12}{'End':<12}{'Status':<12}"
    print(header)
    print(f"  {'-' * 74}")
    for item in items:
        status = str(item.get("status", ""))
        print(
            f"  {str(item.get('id', '')):<6}"
            f"{str(item.get('staff_id', '')):<10}"
            f"{str(item.get('absence_type', '')):<22}"
            f"{str(item.get('start_date', '')):<12}"
            f"{str(item.get('end_date', '')):<12}"
            f"{_coloured_status(status)}"
        )
    print(f"\n  Total: {len(items)} request(s)")


def _my_requests(service: AbsenceRequestService, user: dict):
    print_header("My Requests")
    try:
        staff_id = _get_staff_id(user)
        items = service.get_my_requests(staff_id)
        _print_request_table(items)
    except Exception as e:
        print(f"\n  Error: {e}")


def _submit_request(service: AbsenceRequestService, user: dict):
    print_header("Submit New Absence Request")
    try:
        staff_id = _get_staff_id(user)
        print(f"\n  Submitting as staff ID: {staff_id}")

        print(f"\n  Absence types: {', '.join(ABSENCE_TYPES)}")
        absence_type = input("  Absence type: ").strip()
        if not absence_type:
            print("\n  Cancelled - absence type is required.")
            return

        start_date = input("  Start date (YYYY-MM-DD): ").strip()
        if not start_date:
            print("\n  Cancelled - start date is required.")
            return

        end_date = input("  End date (YYYY-MM-DD): ").strip()
        if not end_date:
            print("\n  Cancelled - end date is required.")
            return

        reason = input("  Reason (optional): ").strip()

        data = {
            "staff_id": staff_id,
            "absence_type": absence_type,
            "start_date": start_date,
            "end_date": end_date,
        }
        if reason:
            data["reason"] = reason

        item = service.create_request(**data)
        print(f"\n  Request submitted successfully (ID: {item['id']}, status: pending)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_request(service: AbsenceRequestService):
    print_header("View Request Details")
    try:
        raw = input("  Enter request ID: ").strip()
        if not raw:
            print("\n  Cancelled.")
            return
        pk = int(raw)
        item = service.get_request(pk)
        if not item:
            print("\n  Request not found.")
            return
        print()
        for k, v in item.items():
            label = k.replace("_", " ").title()
            if k == "status":
                print(f"  {label}: {_coloured_status(str(v))}")
            else:
                print(f"  {label}: {v}")
    except ValueError:
        print("\n  Invalid ID - must be a number.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _cancel_request(service: AbsenceRequestService, user: dict):
    print_header("Cancel My Request")
    try:
        staff_id = _get_staff_id(user)
        # Show user's pending requests first
        pending = service.get_my_requests(staff_id, status="pending")
        if not pending:
            print("\n  You have no pending requests to cancel.")
            return
        print("\n  Your pending requests:")
        _print_request_table(pending)

        raw = input("\n  Enter request ID to cancel: ").strip()
        if not raw:
            print("\n  Cancelled.")
            return
        pk = int(raw)
        confirm = input(f"  Cancel request {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.cancel_request(pk, staff_id)
            print("\n  Request cancelled successfully.")
        else:
            print("\n  Not cancelled.")
    except ValueError:
        print("\n  Invalid ID - must be a number.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_requests(service: AbsenceRequestService):
    print_header("All Requests")
    try:
        items = service.list_requests()
        _print_request_table(items)
    except Exception as e:
        print(f"\n  Error: {e}")


def _filter_by_status(service: AbsenceRequestService):
    print_header("Filter Requests by Status")
    print(f"\n  Available statuses: {', '.join(VALID_STATUSES)}")
    status = input("  Enter status to filter by: ").strip()
    if not status:
        print("\n  Cancelled.")
        return
    if status not in VALID_STATUSES:
        print(f"\n  Invalid status. Choose from: {', '.join(VALID_STATUSES)}")
        return
    try:
        items = service.list_requests(status=status)
        _print_request_table(items)
    except Exception as e:
        print(f"\n  Error: {e}")


def _approve_request(service: AbsenceRequestService, user: dict):
    print_header("Approve Request")
    try:
        # Show pending requests
        pending = service.list_requests(status="pending")
        if not pending:
            print("\n  No pending requests to approve.")
            return
        print("\n  Pending requests:")
        _print_request_table(pending)

        raw = input("\n  Enter request ID to approve: ").strip()
        if not raw:
            print("\n  Cancelled.")
            return
        pk = int(raw)
        approver_id = _get_staff_id(user)
        service.approve_request(pk, approver_id)
        print(f"\n  Request {pk} approved.")
    except ValueError:
        print("\n  Invalid ID - must be a number.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _reject_request(service: AbsenceRequestService, user: dict):
    print_header("Reject Request")
    try:
        pending = service.list_requests(status="pending")
        if not pending:
            print("\n  No pending requests to reject.")
            return
        print("\n  Pending requests:")
        _print_request_table(pending)

        raw = input("\n  Enter request ID to reject: ").strip()
        if not raw:
            print("\n  Cancelled.")
            return
        pk = int(raw)
        approver_id = _get_staff_id(user)
        service.reject_request(pk, approver_id)
        print(f"\n  Request {pk} rejected.")
    except ValueError:
        print("\n  Invalid ID - must be a number.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_request(service: AbsenceRequestService):
    print_header("Update Request")
    try:
        raw = input("  Enter request ID: ").strip()
        if not raw:
            print("\n  Cancelled.")
            return
        pk = int(raw)
        item = service.get_request(pk)
        if not item:
            print("\n  Request not found.")
            return

        print("\n  Leave blank to keep current value.")
        print(f"  Absence types: {', '.join(ABSENCE_TYPES)}")
        data = {}
        for field in ["absence_type", "start_date", "end_date", "reason"]:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_request(pk, **data)
            print("\n  Request updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID - must be a number.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_request(service: AbsenceRequestService):
    print_header("Delete Request")
    try:
        raw = input("  Enter request ID: ").strip()
        if not raw:
            print("\n  Cancelled.")
            return
        pk = int(raw)
        item = service.get_request(pk)
        if not item:
            print("\n  Request not found.")
            return
        print(f"\n  Type: {item.get('absence_type')} | "
              f"Dates: {item.get('start_date')} to {item.get('end_date')} | "
              f"Status: {item.get('status')}")
        confirm = input(f"  Delete request {pk}? This cannot be undone. (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_request(pk)
            print("\n  Request deleted.")
        else:
            print("\n  Not deleted.")
    except ValueError:
        print("\n  Invalid ID - must be a number.")
    except Exception as e:
        print(f"\n  Error: {e}")
