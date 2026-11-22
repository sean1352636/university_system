"""Role filtering for a system's menus, shared by its GUI and CLI.

Each school system declares its own rule as a :class:`MenuPolicy` in
``systems/<system>/domain/access.py``; this module holds the mechanics so the
rule itself is the only thing a system has to state.

The rule, in order:

* admin and platform superadmin open everything;
* staff open everything except the policy's ``admin_only`` labels and, unless
  flagged as a safeguarding lead, its ``dsl_only`` labels. A label missing from
  the policy therefore stays open to staff;
* students and parents open only the policy's ``learner_labels``, plus the
  own-record screens the policy's ``own_menus`` give their role. Those screens
  open for nobody else: staff and admins never see or reach them;
* any other role, or none, opens nothing.

Labels are the menu text, which is what both interfaces already dispatch on.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

logger = logging.getLogger(__name__)

STAFF_ROLES = frozenset({"teacher", "staff"})
LEARNER_ROLES = frozenset({"student", "parent"})

#: A signed-in student or parent still has to look after their own account.
ACCOUNT_LABELS = frozenset({
    "Change Password", "Multi-Factor Authentication", "Multi-Language",
})


def _item_label(item: Any) -> str:
    """A menu item is either its label, or ``(label, handler_name)``."""
    return item if isinstance(item, str) else item[0]


@dataclass(frozen=True)
class Principal:
    """Who is signed in to one system, as far as its menus are concerned."""

    username: str
    role: str
    policy: "MenuPolicy"
    is_superadmin: bool = False
    is_dsl: bool = False

    @property
    def is_admin(self) -> bool:
        return self.is_superadmin or self.role == "admin"

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def is_learner(self) -> bool:
        return self.role in LEARNER_ROLES

    @property
    def has_staff_screens(self) -> bool:
        return self.is_admin or self.is_staff

    @property
    def can_view_safeguarding(self) -> bool:
        return self.is_admin or (self.is_staff and self.is_dsl)

    def can_open(self, label: str) -> bool:
        if label in self.policy.own_labels:
            return not self.is_admin and label in self.policy.own_labels_for(self.role)
        if self.is_admin:
            return True
        if self.is_staff:
            if label in self.policy.admin_only:
                return False
            return label not in self.policy.dsl_only or self.is_dsl
        if self.is_learner:
            return label in self.policy.learner_labels
        return False

    def opens_raise_only(self, label: str) -> bool:
        """True when this label should offer only "raise a concern"."""
        return (label in self.policy.raise_only
                and self.can_open(label)
                and not self.can_view_safeguarding)

    def filter_menu(self, categories: Sequence[tuple[str, list]]) -> list[tuple[str, list]]:
        """The categories this principal sees. Admins get them all, untouched;
        for anyone else a category left with no items is dropped."""
        if self.is_admin:
            return list(categories)
        visible = []
        for name, items in categories:
            allowed = [i for i in items if self.can_open(_item_label(i))]
            if allowed:
                visible.append((name, allowed))
        return visible

    def visible_menu(self, categories: Sequence[tuple[str, list]],
                     *, labels_only: bool = False) -> list[tuple[str, list]]:
        """This principal's own-record categories, then the filtered *categories*.

        A role with no own-record screens gets exactly :meth:`filter_menu`, so
        admin and staff menus are unaffected. *labels_only* gives the plain
        labels the CLI menus use instead of ``(label, handler)``.
        """
        own = [] if self.is_admin else self.policy.own_menus.get(self.role, [])
        if labels_only:
            own = [(name, [label for label, _handler in items]) for name, items in own]
        return self.filter_menu([*own, *categories])

    def notice(self) -> str:
        """What to tell someone with no working screens; empty for staff."""
        if self.has_staff_screens:
            return ""
        return self.policy.messages.get(self.role) or self.policy.messages.get("", "")

    def denied_message(self, label: str) -> str:
        return f"Your account does not have access to {label}."


class MenuPolicy:
    """One system's menu rule, plus the session's current principal."""

    def __init__(
        self,
        system_key: str,
        *,
        superadmin_check: Callable[[Any], bool],
        admin_only: Iterable[str] = (),
        dsl_only: Iterable[str] = (),
        raise_only: Iterable[str] = (),
        learner_labels: Iterable[str] = ACCOUNT_LABELS,
        messages: dict[str, str] | None = None,
        dsl_check: Callable[[str, str | None], bool] | None = None,
        own_menus: dict[str, list[tuple[str, list[tuple[str, str]]]]] | None = None,
    ) -> None:
        self.system_key = system_key
        self.admin_only = frozenset(admin_only)
        self.dsl_only = frozenset(dsl_only)
        self.raise_only = frozenset(raise_only)
        self.learner_labels = frozenset(learner_labels)
        self.messages = dict(messages or {})
        self.own_menus = dict(own_menus or {})
        self.own_labels = frozenset(
            label for menu in self.own_menus.values()
            for _name, items in menu for label, _handler in items)
        self._superadmin_check = superadmin_check
        self._dsl_check = dsl_check
        self.anonymous = Principal(username="", role="", policy=self)
        self._current = self.anonymous

    def own_labels_for(self, role: str) -> frozenset[str]:
        return frozenset(label for _name, items in self.own_menus.get(role, [])
                         for label, _handler in items)

    def own_handlers(self) -> dict[str, str]:
        """``{handler name: label}`` for every own-record screen."""
        return {handler: label for menu in self.own_menus.values()
                for _name, items in menu for label, handler in items}

    def _superadmin(self, systems: Any) -> bool:
        try:
            return bool(self._superadmin_check({"systems": systems or []}))
        except Exception:
            logger.exception("Could not evaluate superadmin status")
            return False

    def _dsl(self, username: str, email: str | None) -> bool:
        if self._dsl_check is None:
            return False
        try:
            return bool(self._dsl_check(username, email))
        except Exception:
            logger.exception("Could not read the safeguarding-lead flag for %s", username)
            return False

    def from_auth(self, auth: Any, role: str | None = None) -> Principal:
        """Principal for a shared-auth session.

        The account's own entry for this system wins over the launcher's
        ``role``, and a role held only in some other system counts for nothing
        here. No username or no role gives :attr:`anonymous`, which opens
        nothing.
        """
        user = getattr(auth, "current_user", None)
        if not isinstance(user, dict):
            return self.anonymous
        username = str(user.get("username") or "").strip()
        if not username:
            return self.anonymous
        systems = user.get("systems") or []
        for entry in systems:
            if isinstance(entry, dict) and entry.get("system_key") == self.system_key:
                role = entry.get("role") or role
                break
        effective = str(role or "").strip().lower()
        is_dsl = effective in STAFF_ROLES and self._dsl(username, user.get("email"))
        return Principal(
            username=username, role=effective, policy=self,
            is_superadmin=self._superadmin(systems), is_dsl=is_dsl)

    def set_current(self, principal: Principal) -> None:
        self._current = principal

    def current_for(self, auth: Any) -> Principal:
        """The session's principal, re-derived if *auth* is someone else."""
        user = getattr(auth, "current_user", None)
        username = user.get("username") if isinstance(user, dict) else None
        if self._current.username and self._current.username == username:
            return self._current
        return self.from_auth(auth)
