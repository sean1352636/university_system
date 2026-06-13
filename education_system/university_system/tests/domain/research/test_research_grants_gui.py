"""Tests for Research Grants GUI — import verification and service integration."""

import pytest
pytestmark = pytest.mark.gui

import pytest


class TestResearchGrantsImports:
    def test_gui_class_importable(self):
        from education_system.university_system.modules.domain.research.gui.research_grants_gui import ResearchGrantsGUI
        assert ResearchGrantsGUI is not None

    def test_research_project_manager_importable(self):
        from education_system.university_system.modules.domain.research.services.research_grants_core import ResearchProjectManager
        assert ResearchProjectManager is not None

    def test_grant_application_manager_importable(self):
        from education_system.university_system.modules.domain.research.services.research_grants_core import GrantApplicationManager
        assert GrantApplicationManager is not None

    def test_publication_manager_importable(self):
        from education_system.university_system.modules.domain.research.services.research_grants_core import PublicationManager
        assert PublicationManager is not None

    def test_milestone_manager_importable(self):
        from education_system.university_system.modules.domain.research.services.research_grants_core import MilestoneManager
        assert MilestoneManager is not None

    def test_equipment_manager_importable(self):
        from education_system.university_system.modules.domain.research.services.research_grants_core import EquipmentManager
        assert EquipmentManager is not None

    def test_ethics_review_manager_importable(self):
        from education_system.university_system.modules.domain.research.services.research_grants_core import EthicsReviewManager
        assert EthicsReviewManager is not None

    def test_grant_tracker_service_importable(self):
        from education_system.university_system.modules.domain.research.services.research_grants_core import GrantTrackerService
        assert GrantTrackerService is not None
