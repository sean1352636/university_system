from __future__ import annotations

import pytest

from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.modules import progress, support


def test_goal_reviews_move_the_goal(learner):
    g = r.save(progress.GOALS, {"learner_id": learner, "title": "Get a job",
                                "category": "Employment"})
    r.save(progress.GOAL_REVIEWS, {"goal_id": g, "progress": 40, "comment": "ok"})
    row = r.get(progress.GOALS, g)
    assert (row["status"], row["progress"]) == ("In progress", 40)
    r.save(progress.GOAL_REVIEWS, {"goal_id": g, "progress": 100, "comment": "done"})
    assert r.get(progress.GOALS, g)["status"] == "Achieved"
    with pytest.raises(r.ValidationError, match="closed"):
        r.save(progress.GOAL_REVIEWS, {"goal_id": g, "progress": 50, "comment": "x"})


def test_complaint_needs_a_response_before_closing():
    with pytest.raises(r.ValidationError, match="response"):
        r.save(support.FEEDBACK, {"kind": "Complaint", "about": "x", "status": "Resolved"})
