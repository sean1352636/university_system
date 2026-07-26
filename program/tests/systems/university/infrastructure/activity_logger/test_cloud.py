"""Tests for simple_activity_logger.cloud"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from education_system.systems.university.infrastructure.utils.activity_logger.cloud import (
    CloudIntegration,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


class TestCloudIntegration:
    def test_init_no_services(self):
        ci = CloudIntegration({})
        assert ci.enabled_services == []

    def test_init_with_services(self):
        ci = CloudIntegration({"enabled_services": ["webhook"]})
        assert "webhook" in ci.enabled_services

    def test_send_to_cloud_no_services(self, make_log_entry):
        ci = CloudIntegration({})
        # Should complete without error and without scheduling tasks
        asyncio.run(ci.send_to_cloud(make_log_entry()))

    def test_send_to_cloud_dispatches_all(self, make_log_entry):
        ci = CloudIntegration({"enabled_services": ["aws_cloudwatch", "elasticsearch", "webhook", "splunk"]})
        # Replace internals with async no-ops to avoid network
        async def noop(_):
            return None
        ci._send_to_cloudwatch = noop
        ci._send_to_elasticsearch = noop
        ci._send_webhook = noop
        ci._send_to_splunk = noop
        asyncio.run(ci.send_to_cloud(make_log_entry()))

    def test_webhook_sends_when_url_set(self, make_log_entry):
        ci = CloudIntegration({"enabled_services": ["webhook"], "webhook_url": "https://example.com/hook"})
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        ci.session = MagicMock()
        ci.session.post = MagicMock(return_value=mock_resp)
        asyncio.run(ci._send_webhook(make_log_entry()))
        ci.session.post.assert_called_once()

    def test_webhook_skipped_without_url(self, make_log_entry):
        ci = CloudIntegration({"enabled_services": ["webhook"]})
        ci.session = MagicMock()
        asyncio.run(ci._send_webhook(make_log_entry()))
        ci.session.post.assert_not_called()

    def test_elasticsearch_uses_session(self, make_log_entry):
        ci = CloudIntegration({
            "enabled_services": ["elasticsearch"],
            "elasticsearch": {"url": "http://localhost:9200", "index": "x"},
        })
        ci.session = MagicMock()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        ci.session.post = MagicMock(return_value=resp)
        asyncio.run(ci._send_to_elasticsearch(make_log_entry()))
        assert ci.session.post.called

    def test_splunk_skipped_without_creds(self, make_log_entry):
        ci = CloudIntegration({"enabled_services": ["splunk"], "splunk": {}})
        ci.session = MagicMock()
        asyncio.run(ci._send_to_splunk(make_log_entry()))
        ci.session.post.assert_not_called()

    def test_splunk_sends_when_configured(self, make_log_entry):
        ci = CloudIntegration({
            "enabled_services": ["splunk"],
            "splunk": {"hec_url": "https://splunk.example.com/event", "hec_token": "tok"},
        })
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        ci.session = MagicMock()
        ci.session.post = MagicMock(return_value=resp)
        # Use timestamp format compatible with strptime
        entry = make_log_entry(timestamp="2026-05-06 12:00:00.000")
        asyncio.run(ci._send_to_splunk(entry))
        ci.session.post.assert_called_once()

    def test_cloudwatch_placeholder(self, make_log_entry, capsys):
        ci = CloudIntegration({"enabled_services": ["aws_cloudwatch"], "aws_cloudwatch": {"log_group": "g", "log_stream": "s"}})
        asyncio.run(ci._send_to_cloudwatch(make_log_entry()))
        captured = capsys.readouterr()
        assert "CloudWatch" in captured.out

    def test_test_connectivity_webhook(self):
        ci = CloudIntegration({"enabled_services": ["webhook"], "webhook_url": "https://example.com"})
        ci.session = MagicMock()
        head_resp = MagicMock(status_code=200)
        ci.session.head = MagicMock(return_value=head_resp)
        results = ci.test_connectivity()
        assert results["webhook"] is True

    def test_test_connectivity_webhook_no_url(self):
        ci = CloudIntegration({"enabled_services": ["webhook"]})
        ci.session = MagicMock()
        results = ci.test_connectivity()
        assert results["webhook"] is False

    def test_test_connectivity_elasticsearch(self):
        ci = CloudIntegration({"enabled_services": ["elasticsearch"]})
        ci.session = MagicMock()
        ci.session.get = MagicMock(return_value=MagicMock(status_code=200))
        results = ci.test_connectivity()
        assert results["elasticsearch"] is True

    def test_test_connectivity_unknown_service(self):
        ci = CloudIntegration({"enabled_services": ["other"]})
        ci.session = MagicMock()
        results = ci.test_connectivity()
        assert results["other"] is True

    def test_test_connectivity_handles_exception(self):
        ci = CloudIntegration({"enabled_services": ["elasticsearch"]})
        ci.session = MagicMock()
        ci.session.get = MagicMock(side_effect=RuntimeError("boom"))
        results = ci.test_connectivity()
        assert results["elasticsearch"] is False
