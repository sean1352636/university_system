"""Import-boundary tests for the sixth form Communications vertical slice.

The rules live in ``tests/unit/systems/sixth_form/domains/conftest.py``; this
module supplies only what Communications currently violates. The allow-list is
a ratchet — see ``_assert_ratchet`` — so it can only shrink.
"""

from __future__ import annotations

SLICE = "communications"

_SF = "education_system.systems.sixth_form"

#: Real findings, recorded rather than tolerated. Each is work left in this slice.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # Direct SQL driver in a domain module — should go through
    # sixth_form.infrastructure.database.
    ("domain/activity_feed/activity_feed.py", "sqlite3"),
    ("domain/announcements/announcements.py", "sqlite3"),
    ("domain/attachments/attachments.py", "sqlite3"),
    ("domain/document_hub/document_hub.py", "sqlite3"),
    ("domain/letter_templates/letter_templates.py", "sqlite3"),
    ("domain/messages/messages.py", "sqlite3"),
    ("domain/notices/notices.py", "sqlite3"),
    ("domain/notifications/notifications.py", "sqlite3"),
    ("domain/parent_contacts/parent_contacts.py", "sqlite3"),
    ("domain/parents_evenings/parents_evenings.py", "sqlite3"),
    # Domain rules reaching into other sixth form areas still under the legacy
    # domain/ tree: learner lookups (students), staff names, alumni recipients
    # and the access gate (user_management). Each becomes a port when the
    # owning area moves into domains/.
    ("domain/activity_feed/activity_feed.py", f"{_SF}.domain.governance.user_management"),
    ("domain/attachments/attachments.py", f"{_SF}.domain.governance.user_management"),
    ("domain/messages/messages.py", f"{_SF}.domain.learners.alumni"),
    ("domain/messages/messages.py", f"{_SF}.domain.learners.students"),
    ("domain/messages/messages.py", f"{_SF}.domain.staff"),
    ("domain/notices/notices.py", f"{_SF}.domain.staff"),
    ("domain/notifications/channel_delivery.py", f"{_SF}.domain.learners.students"),
    ("domain/notifications/channel_delivery.py", f"{_SF}.domain.staff"),
    ("domain/notifications/notifications.py", f"{_SF}.domain.learners.students"),
    ("domain/notifications/notifications.py", f"{_SF}.domain.staff"),
    ("domain/parent_contacts/parent_contacts.py", f"{_SF}.domain.learners.students"),
    ("domain/parents_evenings/parents_evenings.py", f"{_SF}.domain.learners.students"),
    ("domain/parents_evenings/parents_evenings.py", f"{_SF}.domain.staff"),
    # Communications screens and menus reading other areas directly: student
    # and staff pickers, and the access gate.
    ("interfaces/cli/messages/messages_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/messages/messages_cli.py", f"{_SF}.domain.staff"),
    ("interfaces/cli/notices/notices_cli.py", f"{_SF}.domain.staff"),
    ("interfaces/cli/notifications/notifications_cli.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/cli/parent_contacts/parent_contacts_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/parents_evenings/parents_evenings_cli.py", f"{_SF}.domain.learners.students"),
    ("interfaces/cli/parents_evenings/parents_evenings_cli.py", f"{_SF}.domain.staff"),
    ("interfaces/gui/messages/messages_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/messages/messages_views.py", f"{_SF}.domain.staff"),
    ("interfaces/gui/notices/notices_views.py", f"{_SF}.domain.staff"),
    ("interfaces/gui/notifications/notifications_views.py", f"{_SF}.domain.governance.user_management"),
    ("interfaces/gui/parent_contacts/parent_contacts_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/parents_evenings/parents_evenings_views.py", f"{_SF}.domain.learners.students"),
    ("interfaces/gui/parents_evenings/parents_evenings_views.py", f"{_SF}.domain.staff"),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
