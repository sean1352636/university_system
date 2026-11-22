"""Follow-up tasks for refused onboarding consents.

A refused consent still completes its consent task (the decision is on
file), but someone has to act on it — tell the photographer, check the
medical plan, speak to the parent. :func:`after_consent` is called by the
screens after :func:`onboarding.record_consent` (and is safe to call
again): when the decision is *Refused* it opens one follow-up task on the
same checklist, "Follow up refused <purpose>" (e.g. "Follow up refused
photo consent"). When consent is later granted, the open follow-up is
ticked from the new consent record.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)

logger = logging.getLogger(__name__)

#: ``item_key`` prefix of a follow-up task; the consent task key follows.
KEY_PREFIX = "Follow up refused: "
SOURCE = "consent follow-up"


def followup_key(consent_key: str) -> str:
    return f"{KEY_PREFIX}{consent_key}"


def followup_name(consent_key: str) -> str:
    """"Photo consent" -> "Follow up refused photo consent"."""
    label = consent_key.split("(")[0].strip()
    label = label.replace(" form", "").strip()
    if "consent" not in label.lower():
        label = f"{label} consent"
    return f"Follow up refused {label[0].lower()}{label[1:]}"


def _followups(checklist_id: int, key: str) -> list[ob.Item]:
    return [i for i in ob.list_items(checklist_id=checklist_id)
            if i.key == key]


def after_consent(link: ob.ConsentLink) -> ob.Item | None:
    """Open (or return the existing open) follow-up task when *link* is
    a refused consent; when consent is now granted, tick an open
    follow-up from the consent record. Returns the follow-up task, or
    None when there is none. Idempotent."""
    ob._require_writer("adding onboarding follow-up tasks")
    item = link.item
    key = followup_key(item.key)
    existing = _followups(item.checklist_id, key)
    open_ = [i for i in existing if not i.is_done]
    if link.state == "Granted":
        for f in open_:
            try:
                ob.set_item_status(f.item_id, "Done")
            except ob.ValidationError:
                logger.info("Follow-up #%s left open", f.item_id)
        return (ob.get_item(open_[0].item_id) if open_ else None)
    if link.state != "Refused":
        return open_[0] if open_ else None
    if open_:
        return open_[0]
    marker = f"consent #{link.consent_id}"
    for f in existing:            # already followed up for this refusal
        if marker in (f.notes or ""):
            return f
    return ob.create_item({
        "checklist_id": item.checklist_id,
        "task_name": followup_name(item.key),
        "category": item.category,
        "required": False,
        "item_key": key,
        "source": SOURCE,
        "notes": f"{link.purpose} refused ({marker}). Tell the staff who "
                 "need to know and agree what happens instead.",
    })


def after_record(item_id: int) -> ob.Item | None:
    """:func:`after_consent` for the consent task *item_id* (for callers
    holding only the task id)."""
    item = ob.get_item(item_id)
    if item is None:
        raise ob.ValidationError(f"No item #{item_id}")
    link = next((lk for lk in ob.consent_links(item.checklist_id)
                 if lk.item.item_id == item_id), None)
    if link is None:
        raise ob.ValidationError(f"'{item.task_name}' is not a consent task")
    return after_consent(link)


def _granted_rule(consent_key: str):
    def rule(sid: str, item: Any) -> tuple[bool | None, str | None, str]:
        state, c = ob.consent_state(sid, consent_key)
        if state == "Granted":
            return True, f"gdpr:{c.consent_id}", ""
        return None, None, ""     # the follow-up itself is staff's word
    return rule


def register_rules() -> None:
    for key in ob.CONSENT_ITEMS:
        ob.register_evidence_rule(followup_key(key), _granted_rule(key))
