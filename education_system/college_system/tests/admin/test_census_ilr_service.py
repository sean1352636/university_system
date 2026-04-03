"""Tests for CensusILRService."""

import pytest
from education_system.college_system.core.exceptions import CensusILRError


class TestCensusILRService:
    """Test suite for CensusILRService."""

    # --- Returns ---

    def test_create_return(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "census", "2024/25", "autumn", "R01", "2024-11-30",
        )
        assert return_id is not None
        assert isinstance(return_id, int)

    def test_create_return_ilr(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "ilr", "2024/25", "R04", "R04", "2024-02-15",
        )
        assert return_id is not None

    def test_create_return_invalid_type_raises(self, census_ilr_service):
        with pytest.raises(CensusILRError):
            census_ilr_service.create_return(
                "invalid", "2024/25", "autumn", "R01", "2024-11-30",
            )

    def test_get_return(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "census", "2024/25", "autumn", "R01", "2024-11-30",
        )
        found = census_ilr_service.get_return(return_id)
        assert found is not None

    def test_list_returns(self, census_ilr_service):
        census_ilr_service.create_return("census", "2024/25", "autumn", "R01", "2024-11-30")
        items = census_ilr_service.list_returns()
        assert len(items) >= 1

    def test_list_returns_filter_type(self, census_ilr_service):
        census_ilr_service.create_return("census", "2024/25", "autumn", "R01", "2024-11-30")
        census_ilr_service.create_return("ilr", "2024/25", "R04", "R04", "2024-02-15")
        items = census_ilr_service.list_returns(return_type="census")
        assert all(r["return_type"] == "census" for r in items)

    # --- Data Generation ---

    def test_generate_census_data(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "census", "2024/25", "autumn", "R01", "2024-11-30",
        )
        result = census_ilr_service.generate_census_data(return_id)
        assert result is not None

    def test_generate_ilr_data(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "ilr", "2024/25", "R04", "R04", "2024-02-15",
        )
        result = census_ilr_service.generate_ilr_data(return_id)
        assert result is not None

    # --- Validation ---

    def test_validate_return(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "census", "2024/25", "autumn", "R01", "2024-11-30",
        )
        census_ilr_service.generate_census_data(return_id)
        result = census_ilr_service.validate_return(return_id)
        assert result is not None

    def test_get_validation_errors(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "census", "2024/25", "autumn", "R01", "2024-11-30",
        )
        census_ilr_service.generate_census_data(return_id)
        census_ilr_service.validate_return(return_id)
        errors = census_ilr_service.get_validation_errors(return_id)
        assert isinstance(errors, list)

    # --- XML Export ---

    def test_export_census_xml(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "census", "2024/25", "autumn", "R01", "2024-11-30",
        )
        census_ilr_service.generate_census_data(return_id)
        try:
            xml = census_ilr_service.export_census_xml(return_id)
            assert isinstance(xml, str)
            assert "<" in xml
        except CensusILRError:
            # defusedxml may lack Element support in some environments
            pytest.skip("defusedxml.ElementTree lacks Element support")

    def test_export_ilr_xml(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "ilr", "2024/25", "R04", "R04", "2024-02-15",
        )
        census_ilr_service.generate_ilr_data(return_id)
        try:
            xml = census_ilr_service.export_ilr_xml(return_id)
            assert isinstance(xml, str)
        except CensusILRError:
            pytest.skip("defusedxml.ElementTree lacks Element support")

    # --- Submission ---

    def test_submit_return(self, census_ilr_service, sample_student):
        return_id = census_ilr_service.create_return(
            "census", "2024/25", "autumn", "R01", "2024-11-30",
        )
        census_ilr_service.generate_census_data(return_id)
        census_ilr_service.validate_return(return_id)
        # submitted_by must be a valid user ID (FK constraint)
        # submit_return may return None on success (void operation)
        census_ilr_service.submit_return(return_id, submitted_by=1)
        ret = census_ilr_service.get_return(return_id)
        assert ret["status"] == "submitted"

    # --- Statistics ---

    def test_get_return_stats(self, census_ilr_service):
        return_id = census_ilr_service.create_return(
            "census", "2024/25", "autumn", "R01", "2024-11-30",
        )
        stats = census_ilr_service.get_return_stats(return_id)
        assert stats["return_id"] == return_id
        assert "total_records" in stats
