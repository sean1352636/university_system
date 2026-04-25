"""Smoke test for the tutor_groups module."""
import os
import tempfile

import pytest

from education_system.university_system.modules.domain.academics.tutor_groups import (
    TutorGroupService,
    TutorGroupError,
)


def test_tutor_groups_smoke():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "tg.db")
        svc = TutorGroupService(db)

        gid = svc.create_group(
            "TG-A", "2025/26", "BSc CompSci", lead_tutor_id=101, capacity=2,
        )
        assert gid

        svc.add_member(gid, 1001)
        svc.add_member(gid, 1002)
        assert len(svc.list_members(gid)) == 2

        with pytest.raises(TutorGroupError, match="capacity"):
            svc.add_member(gid, 1003)

        with pytest.raises(TutorGroupError, match="already an active member"):
            svc.add_member(gid, 1001)

        gid2 = svc.create_group(
            "TG-B", "2025/26", "BSc CompSci", lead_tutor_id=102, capacity=5,
        )
        with pytest.raises(TutorGroupError, match="already active"):
            svc.add_member(gid2, 1001)

        aid = svc.assign_tutor(gid, tutor_id=201, role="personal_tutor")
        assert aid

        mid = svc.schedule_meeting(
            gid, "2025-01-15 10:00", duration_minutes=45,
            location="Room 101", agenda="Welcome",
        )
        svc.record_meeting(mid, attendance_count=2, notes="went well", status="held")

        with pytest.raises(TutorGroupError, match="YYYY-MM-DD"):
            svc.schedule_meeting(gid, "15/01/2025 10:00")

        s = svc.group_summary(gid)
        assert s["member_count"] == 2
        assert len(s["assignments"]) == 1
        assert len(s["recent_meetings"]) == 1
        assert len(s["upcoming_meetings"]) == 0
