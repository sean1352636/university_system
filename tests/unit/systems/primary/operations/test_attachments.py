"""Record attachments (systems.primary.domain.operations.attachments.attachments)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.operations.attachments import attachments as AT

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _att(title="Consent form", **extra):
    data = {"entity_id": "P0001", "title": title, "file_ref": "store/abc.pdf"}
    data.update(extra)
    return AT.create_attachment(data)


# ── create / get ──

def test_create_stores_fields_and_defaults():
    a = AT.create_attachment({
        "entity_type": "Trip", "entity_id": " TR-7 ", "title": "  Risk assessment ",
        "file_ref": " docs/ra.pdf ", "file_name": "ra.pdf", "file_format": "PDF",
        "file_size_kb": "120", "uploaded_by": " ann ", "tagged_keywords": "trip, risk,, ",
        "contains_pii": 1, "retention_until": "2031-07-31", "description": "  "})
    got = AT.get_attachment(a.attachment_id)
    assert got == a
    assert (got.entity_type, got.entity_id, got.title, got.file_ref) == \
        ("Trip", "TR-7", "Risk assessment", "docs/ra.pdf")
    assert (got.category, got.visibility, got.status) == ("Other", "Internal", "Active")
    assert (got.file_size_kb, got.download_count, got.uploaded_by) == (120, 0, "ann")
    assert got.uploaded_on == TODAY.isoformat()
    assert got.contains_pii and not got.consent_recorded
    assert got.description is None
    assert got.keyword_list == ["trip", "risk"]
    assert got.is_active and not got.is_expired_retention


def test_entity_type_defaults_to_student():
    assert _att().entity_type == "Student"


def test_get_missing_returns_none():
    assert AT.get_attachment(1) is None


# ── validation ──

@pytest.mark.parametrize("field,value,message", [
    ("entity_type", "Spaceship", "Entity type must be one of"),
    ("category", "Meme", "Category must be one of"),
    ("visibility", "Secret", "Visibility must be one of"),
    ("status", "Gone", "Status must be one of"),
    ("entity_id", "  ", "Entity id is required"),
    ("title", "", "Title is required"),
    ("file_ref", " ", "File reference is required"),
    ("uploaded_on", "today", "Uploaded on must be YYYY-MM-DD"),
    ("retention_until", "2030/01/01", "Retention until must be YYYY-MM-DD"),
    ("last_accessed_on", "x", "Last accessed on must be YYYY-MM-DD"),
    ("file_size_kb", "big", r"File size \(kB\) must be an integer"),
    ("file_size_kb", -1, r"File size \(kB\) must be >= 0"),
    ("download_count", "many", "Download count must be an integer"),
    ("download_count", -2, "Download count must be >= 0"),
])
def test_validation_rules(field, value, message):
    with pytest.raises(AT.ValidationError, match=message):
        _att(**{field: value})


# ── update / delete ──

def test_update_replaces_and_refuses_unknown():
    a = _att(notes="old")
    out = AT.update_attachment(a.attachment_id, {"entity_id": "P0002", "title": "New",
                                                 "file_ref": "x", "category": "Letter"})
    assert (out.entity_id, out.title, out.category, out.notes) == ("P0002", "New", "Letter", None)
    with pytest.raises(AT.ValidationError, match="No attachment with id 50"):
        AT.update_attachment(50, {"entity_id": "x", "title": "x", "file_ref": "x"})


def test_delete():
    a = _att()
    assert AT.delete_attachment(a.attachment_id) is True
    assert AT.get_attachment(a.attachment_id) is None
    assert AT.delete_attachment(a.attachment_id) is False


# ── listing ──

def test_list_filters_and_order():
    a = _att("Medical letter", entity_id="P1", category="Medical", visibility="Confidential",
             contains_pii=True, uploaded_on="2025-01-01", tagged_keywords="asthma,inhaler",
             uploaded_by="nurse.jo")
    b = _att("Trip photo", entity_type="Trip", entity_id="T1", category="Photo",
             uploaded_on="2025-03-01", status="Archived")
    c = _att("Old consent", entity_id="P1", retention_until=_iso(-1), uploaded_on="2025-02-01")
    d = _att("Expired archived", entity_id="P2", retention_until=_iso(-1),
             uploaded_on="2025-02-01", status="Archived")

    def ids(**kw):
        return [x.attachment_id for x in AT.list_attachments(**kw)]

    assert ids() == [b.attachment_id, d.attachment_id, c.attachment_id, a.attachment_id]
    assert ids(entity_type="Trip") == [b.attachment_id]
    assert ids(entity_id="P1") == [c.attachment_id, a.attachment_id]
    assert [x.attachment_id for x in AT.attachments_for("Student", "P1")] == \
        [c.attachment_id, a.attachment_id]
    assert ids(category="Medical") == ids(visibility="Confidential") == [a.attachment_id]
    assert ids(status="Archived") == [b.attachment_id, d.attachment_id]
    assert ids(active_only=True) == [c.attachment_id, a.attachment_id]
    assert ids(pii_only=True) == [a.attachment_id]
    assert ids(retention_expired_only=True) == [c.attachment_id]
    assert ids(title_like="photo") == [b.attachment_id]
    assert ids(keyword_like="inhal") == [a.attachment_id]
    assert ids(uploaded_by_like="nurse") == [a.attachment_id]


def test_list_empty():
    assert AT.list_attachments() == []


# ── workflow ──

def test_status_shortcuts_keep_the_rest_of_the_record():
    a = _att(notes="keep me", file_size_kb=10)
    assert AT.quarantine(a.attachment_id).status == "Quarantined"
    assert AT.archive(a.attachment_id).status == "Archived"
    assert AT.soft_delete(a.attachment_id).status == "Deleted"
    back = AT.restore(a.attachment_id)
    assert back.status == "Active"
    assert (back.notes, back.file_size_kb, back.title) == ("keep me", 10, "Consent form")
    assert AT.set_status(a.attachment_id, "Archived").status == "Archived"
    with pytest.raises(AT.ValidationError, match="Status must be one of"):
        AT.set_status(a.attachment_id, "Lost")


@pytest.mark.parametrize("action", ["quarantine", "restore", "archive", "soft_delete",
                                    "record_access"])
def test_workflow_refuses_unknown(action):
    with pytest.raises(AT.ValidationError, match="No attachment with id 9"):
        getattr(AT, action)(9)


def test_set_status_unknown_attachment():
    with pytest.raises(AT.ValidationError, match="No attachment with id 9"):
        AT.set_status(9, "Active")


def test_record_access_counts_and_stamps():
    a = _att(download_count=2)
    once = AT.record_access(a.attachment_id)
    assert (once.download_count, once.last_accessed_on) == (3, TODAY.isoformat())
    assert AT.record_access(a.attachment_id, by=4).download_count == 7
    assert AT.record_access(a.attachment_id, by=-3).download_count == 7


def test_purge_expired_retention_soft_then_hard():
    old = _att("old", retention_until=_iso(-2))
    _att("future", retention_until=_iso(5))
    _att("archived old", retention_until=_iso(-2), status="Archived")
    assert AT.purge_expired_retention() == 1
    assert AT.get_attachment(old.attachment_id).status == "Deleted"
    assert AT.purge_expired_retention() == 0

    hard = _att("hard", retention_until=_iso(-1))
    assert AT.purge_expired_retention(hard_delete=True) == 1
    assert AT.get_attachment(hard.attachment_id) is None
    assert len(AT.list_attachments()) == 3


def test_retention_property():
    assert _att(retention_until=_iso(-1)).is_expired_retention
    assert not _att(retention_until=TODAY.isoformat()).is_expired_retention


# ── summary ──

def test_summary_figures():
    _att("a", entity_id="P1", file_size_kb=100, download_count=3, file_format="PDF",
         visibility="Confidential", contains_pii=True, category="Medical")
    _att("b", entity_id="P1", file_size_kb=50, file_format="PDF", retention_until=_iso(-1))
    _att("c", entity_type="Staff", entity_id="T1", file_format="JPG", status="Quarantined",
         download_count=1)
    _att("d", entity_id="P2", status="Archived", retention_until=_iso(-1))
    _att("e", entity_id="P2", status="Deleted")
    s = AT.summary()
    assert (s.total, s.active, s.quarantined, s.archived, s.deleted) == (5, 2, 1, 1, 1)
    assert (s.confidential, s.contains_pii, s.retention_expired) == (1, 1, 1)
    assert (s.total_size_kb, s.total_downloads, s.distinct_entities) == (150, 4, 3)
    assert s.by_entity_type == {"Student": 4, "Staff": 1}
    assert s.by_category == {"Medical": 1, "Other": 4}
    assert s.by_visibility == {"Confidential": 1, "Internal": 4}
    assert s.by_status == {"Active": 2, "Quarantined": 1, "Archived": 1, "Deleted": 1}
    assert s.by_format == {"PDF": 2, "JPG": 1, "—": 2}


def test_summary_empty():
    s = AT.summary()
    assert s.total == 0 and s.distinct_entities == 0 and s.by_status == {}
