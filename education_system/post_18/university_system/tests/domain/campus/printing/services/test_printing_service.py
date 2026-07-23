"""Tests for the campus printing service (print-quota system).

Uses the autouse ``_isolate_db`` fixture from the university-system conftest,
which patches ``DEFAULT_DB_PATH`` so every ``get_connection()`` call in the
module runs against a throw-away copy of the template DB. ``init_db()`` creates
the printing tables inside that isolated DB.
"""

import pytest

from education_system.post_18.university_system.modules.domain.campus.printing.services import (
    printing_service as ps,
)


@pytest.fixture
def printing_db(temp_db):
    """Ensure the printing tables exist in the isolated DB."""
    ps.init_db()
    return temp_db


# ---------------------------------------------------------------------------
# Pure logic — cost calculation
# ---------------------------------------------------------------------------

class TestCalculateCost:
    def test_mono_single_sided(self):
        # 10 pages x 1 copy x rate 1 = 10, no duplex discount
        assert ps.calculate_cost(10, 1, color=False, double_sided=False) == 10

    def test_colour_costs_double(self):
        assert ps.calculate_cost(10, 1, color=True, double_sided=False) == 20

    def test_double_sided_halves_rounding_up(self):
        # 10 mono pages -> duplex -> 10//2 + 10%2 = 5
        assert ps.calculate_cost(10, 1, color=False, double_sided=True) == 5
        # 5 mono pages -> duplex -> 2 + 1 = 3 (round up)
        assert ps.calculate_cost(5, 1, color=False, double_sided=True) == 3

    def test_multiple_copies(self):
        assert ps.calculate_cost(3, 4, color=False, double_sided=False) == 12

    def test_minimum_one_credit(self):
        assert ps.calculate_cost(1, 1, color=False, double_sided=True) == 1


# ---------------------------------------------------------------------------
# Quota management
# ---------------------------------------------------------------------------

class TestQuota:
    def test_ensure_quota_creates_default_row(self, printing_db):
        row = ps.get_quota("STU-P1")
        assert row["total_pages"] == 500
        assert row["used_pages"] == 0

    def test_ensure_quota_idempotent(self, printing_db):
        ps.get_quota("STU-P2")
        again = ps.get_quota("STU-P2")
        assert again["student_id"] == "STU-P2"
        # Only one row should exist
        with ps.get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM print_quotas WHERE student_id = ?", ("STU-P2",)
            ).fetchone()[0]
        assert n == 1

    def test_purchase_credits_increases_total(self, printing_db):
        ps.get_quota("STU-P3")
        ps.purchase_credits("STU-P3", 250, "4.50")
        row = ps.get_quota("STU-P3")
        assert row["total_pages"] == 750
        txns = ps.get_transactions("STU-P3")
        assert any(t["transaction_type"] == "credit" and t["amount"] == 250 for t in txns)


# ---------------------------------------------------------------------------
# Print jobs
# ---------------------------------------------------------------------------

class TestPrintJobs:
    def test_submit_job_deducts_credits(self, printing_db):
        cost = ps.submit_print_job(
            "STU-P4", "essay.pdf", pages=10, copies=1, color=False, double_sided=False
        )
        assert cost == 10
        row = ps.get_quota("STU-P4")
        assert row["used_pages"] == 10
        history = ps.get_print_history("STU-P4")
        assert len(history) == 1
        assert history[0]["file_name"] == "essay.pdf"
        assert history[0]["cost_credits"] == 10

    def test_submit_colour_job_tracks_colour_pages(self, printing_db):
        ps.submit_print_job(
            "STU-P5", "poster.pdf", pages=5, copies=2, color=True, double_sided=False
        )
        row = ps.get_quota("STU-P5")
        # colour pages added = pages*copies = 10
        assert row["color_pages_used"] == 10

    def test_submit_job_insufficient_credits_raises(self, printing_db):
        # Default quota is 500; request a job costing more than that.
        with pytest.raises(ValueError):
            ps.submit_print_job(
                "STU-P6", "huge.pdf", pages=600, copies=1, color=False, double_sided=False
            )
        # No job should have been recorded
        assert ps.get_print_history("STU-P6") == []

    def test_transactions_record_debit(self, printing_db):
        ps.submit_print_job(
            "STU-P7", "doc.pdf", pages=4, copies=1, color=False, double_sided=False
        )
        txns = ps.get_transactions("STU-P7")
        assert len(txns) == 1
        assert txns[0]["transaction_type"] == "debit"
        assert txns[0]["amount"] == -4
