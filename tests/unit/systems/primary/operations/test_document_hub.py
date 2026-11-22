"""Document Hub (systems.primary.domain.operations.document_hub.document_hub)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.operations.document_hub import document_hub as DH

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _doc(title="Behaviour Policy", **extra):
    return DH.create_document({"title": title, **extra})


# ── create / get ──

def test_create_stores_fields_and_defaults():
    d = DH.create_document({
        "title": "  Safeguarding Policy ", "category": "Safeguarding", "audience": "Staff",
        "access_level": "Restricted", "version": " 2.1 ", "file_ref": " pol/sg.pdf ",
        "file_size_kb": "300", "author": "DSL", "keywords": "kcsie, , child protection",
        "issued_on": "2025-09-01", "review_on": "2026-09-01", "expires_on": "2027-09-01",
        "notes": "  "})
    got = DH.get_document(d.document_id)
    assert got == d
    assert (got.title, got.category, got.audience, got.access_level, got.version) == \
        ("Safeguarding Policy", "Safeguarding", "Staff", "Restricted", "2.1")
    assert (got.file_ref, got.file_size_kb, got.download_count, got.notes) == \
        ("pol/sg.pdf", 300, 0, None)
    assert got.keyword_list == ["kcsie", "child protection"]
    assert got.status == "Draft" and not got.is_current


def test_defaults():
    d = _doc()
    assert (d.category, d.audience, d.access_level, d.version, d.status) == \
        ("Policy", "All", "Internal", "1.0", "Draft")
    assert d.supersedes_id is None and d.keyword_list == []


def test_get_missing():
    assert DH.get_document(3) is None


# ── validation ──

@pytest.mark.parametrize("field,value,message", [
    ("title", "  ", "Title is required"),
    ("category", "Novel", "Category must be one of"),
    ("audience", "Everyone", "Audience must be one of"),
    ("access_level", "Top Secret", "Access level must be one of"),
    ("status", "Live", "Status must be one of"),
    ("issued_on", "1 Sept", "Issued on must be YYYY-MM-DD"),
    ("review_on", "2025-02-30", "Review on must be YYYY-MM-DD"),
    ("expires_on", "soon", "Expires on must be YYYY-MM-DD"),
    ("supersedes_id", "abc", "Supersedes id must be an integer"),
    ("file_size_kb", "x", r"File size \(kB\) must be an integer"),
    ("file_size_kb", -5, r"File size \(kB\) must be >= 0"),
    ("download_count", "x", "Download count must be an integer"),
    ("download_count", -1, "Download count must be >= 0"),
])
def test_validation_rules(field, value, message):
    data = {"title": "Doc", field: value}
    if field == "title":
        data = {"title": value}
    with pytest.raises(DH.ValidationError, match=message):
        DH.create_document(data)


def test_review_and_expiry_cannot_precede_issue():
    with pytest.raises(DH.ValidationError, match="Review date cannot be before issue date"):
        _doc(issued_on="2025-09-01", review_on="2025-08-31")
    with pytest.raises(DH.ValidationError, match="Expiry date cannot be before issue date"):
        _doc(issued_on="2025-09-01", expires_on="2025-08-01")
    same = _doc(issued_on="2025-09-01", review_on="2025-09-01", expires_on="2025-09-01")
    assert same.review_on == same.expires_on == "2025-09-01"


def test_supersedes_unknown_document_is_refused():
    with pytest.raises(DH.ValidationError):
        _doc(supersedes_id=999)


def test_blank_version_falls_back():
    assert _doc(version="   ").version == "1.0"


# ── update / delete ──

def test_update_and_unknown():
    d = _doc(author="Head")
    out = DH.update_document(d.document_id, {"title": "Anti-bullying", "category": "Procedure"})
    assert (out.title, out.category, out.author) == ("Anti-bullying", "Procedure", None)
    with pytest.raises(DH.ValidationError, match="No document with id 44"):
        DH.update_document(44, {"title": "x"})


def test_delete_and_superseded_link_set_null():
    old = _doc(status="Published")
    new = DH.supersede(old.document_id, new_version="2.0")
    assert DH.delete_document(old.document_id) is True
    assert DH.get_document(new.document_id).supersedes_id is None
    assert DH.delete_document(old.document_id) is False


# ── listing ──

def test_list_filters_and_order():
    a = _doc("Zeta policy", status="Published", review_on=_iso(-1), keywords="online,safety",
             author="Mrs Head")
    b = _doc("Alpha policy", status="Approved", audience="Parents / Carers",
             access_level="Public")
    c = _doc("Uniform form", category="Form", version="1.0")
    c2 = _doc("Uniform form", category="Form", version="2.0")
    e = _doc("Draft handbook", category="Handbook", status="Draft", review_on=_iso(-10))

    def ids(**kw):
        return [x.document_id for x in DH.list_documents(**kw)]

    assert ids() == [c2.document_id, c.document_id, e.document_id, b.document_id, a.document_id]
    assert ids(category="Form") == [c2.document_id, c.document_id]
    assert ids(audience="Parents / Carers") == ids(access_level="Public") == [b.document_id]
    assert ids(status="Draft") == [c2.document_id, c.document_id, e.document_id]
    assert ids(current_only=True) == [b.document_id, a.document_id]
    assert ids(overdue_review_only=True) == [a.document_id]
    assert ids(title_like="uniform") == [c2.document_id, c.document_id]
    assert ids(keyword_like="safe") == ids(author_like="head") == [a.document_id]


# ── properties ──

def test_overdue_review_and_expiry_properties():
    assert _doc(status="Published", review_on=_iso(-1)).is_overdue_review
    assert not _doc(status="Draft", review_on=_iso(-1)).is_overdue_review
    assert not _doc(status="Approved", review_on=TODAY.isoformat()).is_overdue_review
    assert _doc(expires_on=_iso(-1)).is_expired
    assert not _doc(expires_on=TODAY.isoformat()).is_expired


# ── workflow ──

def test_review_approve_publish_withdraw_archive():
    d = _doc(notes="keep")
    assert DH.submit_for_review(d.document_id).status == "Under Review"
    ap = DH.approve(d.document_id, approved_by="Governors")
    assert (ap.status, ap.approved_by) == ("Approved", "Governors")
    assert ap.is_current
    pub = DH.publish(d.document_id, issued_on="2025-09-01")
    assert (pub.status, pub.issued_on, pub.approved_by, pub.notes) == \
        ("Published", "2025-09-01", "Governors", "keep")
    assert DH.withdraw(d.document_id).status == "Withdrawn"
    assert DH.archive(d.document_id).status == "Archived"


def test_publish_keeps_existing_issue_date_or_uses_today():
    kept = DH.publish(_doc(issued_on="2024-01-01").document_id)
    assert kept.issued_on == "2024-01-01"
    assert DH.publish(_doc().document_id).issued_on == TODAY.isoformat()


def test_approve_without_name_keeps_previous_approver():
    d = _doc(approved_by="Head")
    assert DH.approve(d.document_id).approved_by == "Head"


@pytest.mark.parametrize("action", ["submit_for_review", "approve", "publish", "withdraw",
                                    "archive", "increment_downloads"])
def test_workflow_refuses_unknown(action):
    with pytest.raises(DH.ValidationError, match="No document with id 8"):
        getattr(DH, action)(8)


def test_set_status():
    d = _doc()
    assert DH.set_status(d.document_id, "Superseded").status == "Superseded"
    with pytest.raises(DH.ValidationError, match="Status must be one of"):
        DH.set_status(d.document_id, "Binned")
    with pytest.raises(DH.ValidationError, match="No document with id 8"):
        DH.set_status(8, "Draft")


def test_supersede_with_carry_over():
    old = _doc(status="Published", issued_on="2024-09-01", review_on="2025-09-01",
               author="Head", keywords="k1", download_count=12, version="1.0")
    new = DH.supersede(old.document_id, new_version="1.1")
    assert (new.version, new.status, new.supersedes_id, new.download_count, new.issued_on) == \
        ("1.1", "Draft", old.document_id, 0, None)
    assert (new.author, new.keywords, new.review_on) == ("Head", "k1", "2025-09-01")
    assert DH.get_document(old.document_id).status == "Superseded"


def test_supersede_without_carry_over_copies_only_identity():
    old = _doc(category="Form", audience="Staff", access_level="Restricted", author="Head",
               notes="n")
    new = DH.supersede(old.document_id, new_version="2.0", carry_over=False)
    assert (new.title, new.category, new.audience, new.access_level) == \
        (old.title, "Form", "Staff", "Restricted")
    assert new.author is None and new.notes is None


def test_supersede_rules():
    old = _doc(version="3.0")
    with pytest.raises(DH.ValidationError, match="New version is required"):
        DH.supersede(old.document_id, new_version="  ")
    with pytest.raises(DH.ValidationError, match="must differ from current version"):
        DH.supersede(old.document_id, new_version="3.0")
    with pytest.raises(DH.ValidationError, match="No document with id 90"):
        DH.supersede(90, new_version="1")


def test_increment_downloads():
    d = _doc(download_count=5)
    assert DH.increment_downloads(d.document_id).download_count == 6
    assert DH.increment_downloads(d.document_id, by=10).download_count == 16
    assert DH.increment_downloads(d.document_id, by=-4).download_count == 16


def test_auto_archive_expired_only_current_documents():
    a = _doc("a", status="Published", expires_on=_iso(-1))
    b = _doc("b", status="Approved", expires_on=_iso(-30))
    c = _doc("c", status="Draft", expires_on=_iso(-1))
    d = _doc("d", status="Published", expires_on=TODAY.isoformat())
    assert DH.auto_archive_expired() == 2
    assert [DH.get_document(x.document_id).status for x in (a, b, c, d)] == \
        ["Archived", "Archived", "Draft", "Published"]
    assert DH.auto_archive_expired() == 0


# ── summary ──

def test_summary_figures():
    _doc("a", status="Published", review_on=_iso(-1), expires_on=_iso(-1), download_count=4,
         access_level="Confidential")
    _doc("b", status="Approved", audience="Staff", download_count=1)
    _doc("c", category="Form")
    _doc("d", status="Under Review")
    _doc("e", status="Superseded")
    _doc("f", status="Archived", expires_on=_iso(-3))
    _doc("g", status="Withdrawn")
    s = DH.summary()
    assert (s.total, s.drafts, s.under_review, s.approved, s.published, s.superseded,
            s.archived) == (7, 1, 1, 1, 1, 1, 1)
    assert (s.overdue_review, s.expired_unprocessed, s.confidential, s.total_downloads) == \
        (1, 1, 1, 5)
    assert s.by_category == {"Policy": 6, "Form": 1}
    assert s.by_audience == {"All": 6, "Staff": 1}
    assert s.by_access == {"Confidential": 1, "Internal": 6}
    assert s.by_status["Withdrawn"] == 1 and sum(s.by_status.values()) == 7


def test_summary_empty():
    s = DH.summary()
    assert s.total == 0 and s.by_category == {}
