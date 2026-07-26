"""Tests for ParentChildLinkService."""

import pytest

from education_system.platform.services.parent_child_link import (
    ParentChildLinkService,
    init_parent_links_db,
)


@pytest.fixture()
def svc(tmp_path):
    db = str(tmp_path / "links.db")
    init_parent_links_db(db)
    return ParentChildLinkService(db)


# ── link / unlink ────────────────────────────────────────────────────

def test_link_child(svc):
    link = svc.link_child(
        parent_user_id=1,
        child_student_id="STU001",
        child_system_key="secondary",
        relationship="parent",
    )
    assert link["parent_user_id"] == 1
    assert link["child_student_id"] == "STU001"
    assert link["is_active"] == 1
    assert link["relationship"] == "parent"


def test_link_child_idempotent(svc):
    svc.link_child(1, "STU001", "secondary", "parent")
    link2 = svc.link_child(1, "STU001", "secondary", "guardian")
    # upsert updates relationship
    assert link2["relationship"] == "guardian"
    assert link2["is_active"] == 1


def test_unlink_child(svc):
    svc.link_child(1, "STU001", "secondary")
    assert svc.unlink_child(1, "STU001", "secondary") is True

    children = svc.get_children(parent_user_id=1)
    assert len(children) == 0


def test_unlink_child_already_inactive(svc):
    svc.link_child(1, "STU001", "secondary")
    svc.unlink_child(1, "STU001", "secondary")
    # second unlink returns False — nothing updated
    assert svc.unlink_child(1, "STU001", "secondary") is False


# ── get children / parents ───────────────────────────────────────────

def test_get_children(svc):
    svc.link_child(1, "STU001", "secondary")
    svc.link_child(1, "STU002", "sixth_form")
    svc.link_child(1, "STU003", "primary")

    children = svc.get_children(parent_user_id=1)
    assert len(children) == 3
    ids = {c["child_student_id"] for c in children}
    assert ids == {"STU001", "STU002", "STU003"}


def test_get_parents(svc):
    svc.link_child(10, "STU001", "secondary", "parent")
    svc.link_child(20, "STU001", "secondary", "guardian")

    parents = svc.get_parents("STU001", "secondary")
    assert len(parents) == 2

    parent_ids = {p["parent_user_id"] for p in parents}
    assert parent_ids == {10, 20}


def test_get_parents_across_systems(svc):
    svc.link_child(10, "STU001", "secondary")
    svc.link_child(10, "STU001", "sixth_form")

    # without system filter returns both
    parents = svc.get_parents("STU001")
    assert len(parents) == 2


# ── verify_parent_access ────────────────────────────────────────────

def test_verify_parent_access_active(svc):
    svc.link_child(1, "STU001", "secondary")
    assert svc.verify_parent_access(1, "STU001", "secondary") is True


def test_verify_parent_access_inactive(svc):
    svc.link_child(1, "STU001", "secondary")
    svc.unlink_child(1, "STU001", "secondary")
    assert svc.verify_parent_access(1, "STU001", "secondary") is False


def test_verify_parent_access_no_link(svc):
    assert svc.verify_parent_access(99, "STU999", "secondary") is False


def test_verify_parent_access_any_system(svc):
    svc.link_child(1, "STU001", "secondary")
    # no system_key filter — should still find it
    assert svc.verify_parent_access(1, "STU001") is True


# ── reactivation ─────────────────────────────────────────────────────

def test_reactivation_after_unlink(svc):
    svc.link_child(1, "STU001", "secondary")
    svc.unlink_child(1, "STU001", "secondary")
    assert svc.verify_parent_access(1, "STU001", "secondary") is False

    # re-link should reactivate
    svc.link_child(1, "STU001", "secondary")
    assert svc.verify_parent_access(1, "STU001", "secondary") is True
