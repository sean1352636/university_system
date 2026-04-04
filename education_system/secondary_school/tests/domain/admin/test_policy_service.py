"""Tests for PolicyService."""
import pytest


class TestPolicy:
    def test_add_policy(self, policy_service):
        policy = policy_service.add_policy(
            title="Behaviour Policy", category="behaviour",
            approved_by="Headteacher",
        )
        assert policy["title"] == "Behaviour Policy"
        assert policy["category"] == "behaviour"

    def test_list_policies(self, policy_service):
        policy_service.add_policy("Policy A", category="general")
        policy_service.add_policy("Policy B", category="hr")
        policies = policy_service.list_policies()
        assert len(policies) >= 2

    def test_list_policies_filters_by_category(self, policy_service):
        policy_service.add_policy("Policy A", category="safeguarding")
        policy_service.add_policy("Policy B", category="hr")
        policies = policy_service.list_policies(category="safeguarding")
        assert all(p["category"] == "safeguarding" for p in policies)

    def test_delete_policy(self, policy_service):
        policy = policy_service.add_policy("Delete Me")
        policy_service.delete_policy(policy["id"])
        policies = policy_service.list_policies()
        assert all(p["id"] != policy["id"] for p in policies)

    def test_acknowledge(self, policy_service):
        policy = policy_service.add_policy("Ack Policy")
        policy_service.acknowledge(policy["id"], "Mr Smith")
        count = policy_service.acknowledgement_count(policy["id"])
        assert count == 1

    def test_list_acknowledgements(self, policy_service):
        policy = policy_service.add_policy("Ack List Policy")
        policy_service.acknowledge(policy["id"], "Mr Smith")
        policy_service.acknowledge(policy["id"], "Mrs Jones")
        acks = policy_service.list_acknowledgements(policy["id"])
        assert len(acks) == 2

    def test_acknowledgement_count(self, policy_service):
        policy = policy_service.add_policy("Count Policy")
        assert policy_service.acknowledgement_count(policy["id"]) == 0
        policy_service.acknowledge(policy["id"], "Staff A")
        assert policy_service.acknowledgement_count(policy["id"]) == 1
