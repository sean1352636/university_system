"""Fixtures for dashboard module tests."""

import pytest

from education_system.college_system.modules.domain.data_dashboard.services.data_dashboard_service import DataDashboardService
from education_system.college_system.modules.domain.kpi_dashboard.services.kpi_dashboard_service import KPIDashboardService
from education_system.college_system.modules.domain.mobile_dashboard.services.mobile_dashboard_service import MobileDashboardService
from education_system.college_system.modules.domain.activity_feed.services.activity_feed_service import ActivityFeedService
from education_system.college_system.modules.domain.advanced_search.services.advanced_search_service import AdvancedSearchService


@pytest.fixture
def data_dashboard_service(db_path):
    return DataDashboardService(db_path)


@pytest.fixture
def kpi_dashboard_service(db_path):
    return KPIDashboardService(db_path)


@pytest.fixture
def mobile_dashboard_service(db_path):
    return MobileDashboardService(db_path)


@pytest.fixture
def activity_feed_service(db_path):
    return ActivityFeedService(db_path)


@pytest.fixture
def advanced_search_service(db_path):
    return AdvancedSearchService(db_path)
