"""Tests for PeerMentoringService."""

import pytest
from education_system.college_system.core.exceptions import PeerMentoringError, ValidationError


class TestPeerMentoringService:
    """Test suite for PeerMentoringService."""

    def test_create_pair(self, peer_mentoring_service):
        item = peer_mentoring_service.create_pair(mentor_id=1, mentee_id=1)
        assert item["id"] is not None

    def test_get_pair(self, peer_mentoring_service):
        item = peer_mentoring_service.create_pair(mentor_id=1, mentee_id=1)
        found = peer_mentoring_service.get_pair(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_pairs(self, peer_mentoring_service):
        peer_mentoring_service.create_pair(mentor_id=1, mentee_id=1)
        items = peer_mentoring_service.list_pairs()
        assert len(items) >= 1

    def test_update_pair(self, peer_mentoring_service):
        item = peer_mentoring_service.create_pair(mentor_id=1, mentee_id=1)
        updated = peer_mentoring_service.update_pair(item["id"], subject_area="updated_value")
        assert updated["subject_area"] == "updated_value"

    def test_delete_pair(self, peer_mentoring_service):
        item = peer_mentoring_service.create_pair(mentor_id=1, mentee_id=1)
        result = peer_mentoring_service.delete_pair(item["id"])
        assert result is True
        assert peer_mentoring_service.get_pair(item["id"]) is None

    def test_count_pairs(self, peer_mentoring_service):
        peer_mentoring_service.create_pair(mentor_id=1, mentee_id=1)
        count = peer_mentoring_service.count_pairs()
        assert count >= 1

    def test_delete_nonexistent_raises(self, peer_mentoring_service):
        with pytest.raises(PeerMentoringError):
            peer_mentoring_service.delete_pair(99999)
