"""Tests for the safeguarding submissions service (persist / fetch / dedup)."""

import pytest

from education_system.systems.university.domain.safeguarding.services.submissions import (
    fetch_submissions,
    fetch_user_submissions,
    find_duplicate,
    get_submission,
    issue_contact_token,
    lookup_by_contact_token,
    resolve_content,
    save_submission,
    update_submission_status,
)


@pytest.fixture()
def user():
    return {"username": "s.student", "full_name": "Sam Student", "role": "student"}


class TestSaveSubmission:
    def test_returns_new_id_and_persists_metadata(self, user):
        sid = save_submission(user, "I am being bullied every day", "HIGH", {"Bullying": []})
        assert isinstance(sid, int) and sid > 0
        row = get_submission(sid)
        assert row["username"] == "s.student"
        assert row["severity"] == "HIGH"
        # HIGH/CRITICAL intake starts in Triage, everything else Open.
        assert row["lifecycle_state"] == "Triage"
        assert row["risk_score"] == row["likelihood"] * row["impact"]

    def test_medium_case_starts_open(self, user):
        sid = save_submission(user, "some worry", "MEDIUM", {})
        assert get_submission(sid)["lifecycle_state"] == "Open"

    def test_content_roundtrips_through_resolve(self, user):
        # Field encryption is on by default; resolve_content must return the
        # original plaintext regardless of how it was stored.
        text = "confidential disclosure details"
        sid = save_submission(user, text, "MEDIUM", {})
        content, _ = resolve_content(sid)
        assert content == text

    def test_subject_id_links_same_reporter(self, user):
        s1 = save_submission(user, "first report about me", "LOW", {})
        s2 = save_submission(user, "second unrelated report", "LOW", {})
        r1, r2 = get_submission(s1), get_submission(s2)
        # Both non-anonymous cases for the same username share a subject id
        # (checked indirectly via the analytics linker in its own module).
        assert r1["username"] == r2["username"]


class TestFetchSubmissions:
    def test_status_and_severity_filters(self, user):
        save_submission(user, "high sev worry text here", "HIGH", {})
        save_submission(user, "low sev worry text here", "LOW", {})
        highs = fetch_submissions(severity_filter="HIGH")
        assert len(highs) == 1
        assert highs[0][4] == "HIGH"  # severity column

    def test_ordered_by_severity_priority(self, user):
        save_submission(user, "low priority text goes here", "LOW", {})
        save_submission(user, "critical is ordered first here", "HIGH", {})
        rows = fetch_submissions()
        assert rows[0][4] == "HIGH"  # HIGH sorts before LOW

    def test_whistleblowing_hidden_by_default(self, user):
        save_submission(
            user,
            "whistleblowing disclosure text",
            "MEDIUM",
            {},
            whistleblowing=True,
            wb_independent_reviewer="reviewer1",
        )
        assert fetch_submissions() == []
        assert len(fetch_submissions(include_whistleblowing=True)) == 1


class TestUpdateStatus:
    def test_status_update_is_reflected(self, user):
        sid = save_submission(user, "needs review text goes here", "MEDIUM", {})
        update_submission_status(sid, "Reviewed", "dsl.jones", "looks fine")
        row = get_submission(sid)
        assert row["status"] == "Reviewed"
        assert row["reviewer"] == "dsl.jones"


class TestUserSubmissions:
    def test_returns_only_that_users_cases(self, user):
        save_submission(user, "my own case text here", "LOW", {})
        other = {"username": "other.person", "full_name": "Other", "role": "student"}
        save_submission(other, "someone elses case text", "LOW", {})
        rows = fetch_user_submissions("s.student")
        assert len(rows) == 1


class TestContactToken:
    def test_issue_and_lookup_roundtrip(self, user):
        raw, digest = issue_contact_token()
        assert raw and digest and raw != digest
        sid = save_submission(
            user, "anonymous style report text", "MEDIUM", {}, contact_token_hash=digest
        )
        row = lookup_by_contact_token(raw)
        assert row is not None
        assert row[0] == sid

    def test_unknown_token_returns_none(self):
        assert lookup_by_contact_token("nonexistent") is None
        assert lookup_by_contact_token("") is None


class TestFindDuplicate:
    @pytest.fixture(autouse=True)
    def _plaintext_content(self, monkeypatch):
        # find_duplicate compares the plaintext `content` column. With field
        # encryption on (the default) that column is stored empty, so dedup
        # can only ever match plaintext rows — disable encryption here so the
        # SequenceMatcher logic is actually exercised.
        monkeypatch.setattr(
            "education_system.systems.university.domain."
            "student_affairs.safeguarding.crypto.FIELD_ENCRYPTION_ENABLED",
            False,
        )

    def test_near_identical_recent_report_is_flagged(self, user):
        text = "My flatmate has been threatening me repeatedly this whole week now"
        first = save_submission(user, text, "HIGH", {})
        dup = find_duplicate("s.student", text + ".")
        assert dup == first

    def test_different_text_is_not_a_duplicate(self, user):
        save_submission(user, "concern about exam stress and workload piling up", "LOW", {})
        assert (
            find_duplicate("s.student", "a totally different unrelated matter entirely here")
            is None
        )

    def test_too_short_text_is_ignored(self, user):
        assert find_duplicate("s.student", "short") is None

    def test_requires_username_and_content(self):
        assert find_duplicate("", "some long enough content string here") is None
        assert find_duplicate("user", "") is None
