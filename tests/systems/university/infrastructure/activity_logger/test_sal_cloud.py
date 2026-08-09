"""Tests for simple_activity_logger.cloud."""
import asyncio
from unittest.mock import MagicMock, patch

from education_system.systems.university.infrastructure.utils.activity_logger import cloud
from education_system.systems.university.infrastructure.utils.activity_logger.cloud import (
    CloudIntegration,
)
from education_system.systems.university.infrastructure.utils.activity_logger.models import LogEntry


def _entry():
    return LogEntry(
        timestamp="2026-05-28 10:00:00.000",
        user_id="u", username="alice", role="user",
        action="read", module="m", details="d", status="success",
        log_level="INFO", session_id="s", ip_address="1.1.1.1",
        user_agent="UA", request_size=0, response_size=0,
        processing_time=0.0, geolocation={}, security_level="LOW",
        trace_id="t",
    )


class TestCloudIntegrationInit:
    def test_session_created_when_requests_available(self):
        ci = CloudIntegration({"timeout": 5})
        assert ci.session is not None or cloud.requests is None

    def test_no_session_when_requests_missing(self):
        with patch.object(cloud, "requests", None):
            ci = CloudIntegration({})
            assert ci.session is None


class TestSendToCloud:
    def test_no_services_no_calls(self):
        ci = CloudIntegration({"enabled_services": []})
        asyncio.run(ci.send_to_cloud(_entry()))  # should be a no-op

    def test_cloudwatch_path_executed(self, capsys):
        ci = CloudIntegration({"enabled_services": ["aws_cloudwatch"]})
        asyncio.run(ci.send_to_cloud(_entry()))
        captured = capsys.readouterr()
        assert "CloudWatch" in captured.out

    def test_webhook_invoked(self):
        ci = CloudIntegration({"enabled_services": ["webhook"], "webhook_url": "https://example.com/h"})
        ci.session = MagicMock()
        ci.session.post.return_value.raise_for_status.return_value = None
        asyncio.run(ci.send_to_cloud(_entry()))
        ci.session.post.assert_called_once()

    def test_webhook_without_url_is_skipped(self):
        ci = CloudIntegration({"enabled_services": ["webhook"]})
        ci.session = MagicMock()
        asyncio.run(ci.send_to_cloud(_entry()))
        ci.session.post.assert_not_called()

    def test_elasticsearch_uses_session(self):
        ci = CloudIntegration({
            "enabled_services": ["elasticsearch"],
            "elasticsearch": {"url": "http://es:9200", "index": "logs"},
        })
        ci.session = MagicMock()
        ci.session.post.return_value.raise_for_status.return_value = None
        asyncio.run(ci.send_to_cloud(_entry()))
        ci.session.post.assert_called_once()


class TestTestConnectivity:
    def test_returns_false_when_no_session(self):
        ci = CloudIntegration({"enabled_services": ["webhook"]})
        ci.session = None
        assert ci.test_connectivity() == {"webhook": False}

    def test_webhook_no_url_is_false(self):
        ci = CloudIntegration({"enabled_services": ["webhook"]})
        ci.session = MagicMock()
        assert ci.test_connectivity()["webhook"] is False

    def test_webhook_with_good_status(self):
        ci = CloudIntegration({
            "enabled_services": ["webhook"],
            "webhook_url": "https://example.com/h",
        })
        ci.session = MagicMock()
        ci.session.head.return_value.status_code = 200
        assert ci.test_connectivity()["webhook"] is True

    def test_unknown_service_defaults_true(self):
        ci = CloudIntegration({"enabled_services": ["mystery"]})
        ci.session = MagicMock()
        assert ci.test_connectivity()["mystery"] is True

    def test_exception_marks_service_false(self):
        ci = CloudIntegration({
            "enabled_services": ["webhook"],
            "webhook_url": "https://example.com/h",
        })
        ci.session = MagicMock()
        ci.session.head.side_effect = RuntimeError("net down")
        assert ci.test_connectivity()["webhook"] is False
