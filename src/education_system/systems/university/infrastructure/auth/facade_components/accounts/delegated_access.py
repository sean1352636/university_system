"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthAccountsDelegatedAccessMixin:
    def create_delegation(self, delegate_user_id, scope_keys, relationship=None, expires_at=None):
        """Create a delegation granting access to another user"""
        return self.delegated_access_manager.create_delegation(
            delegate_user_id, scope_keys, relationship, expires_at
        )

    def revoke_delegation(self, delegation_id):
        """Revoke a delegation"""
        return self.delegated_access_manager.revoke_delegation(delegation_id)

    def get_delegations_for_user(self, user_id=None, direction='granted'):
        """Get delegations for a user"""
        return self.delegated_access_manager.get_delegations_for_user(user_id, direction)

    def check_delegated_permission(self, delegate_user_id, target_user_id, permission):
        """Check if delegate has a specific delegated permission"""
        return self.delegated_access_manager.check_delegated_permission(
            delegate_user_id, target_user_id, permission
        )

    def create_delegation_request(self, target_user_id, relationship, scope_keys, reason=None):
        """Request delegated access to a user's records"""
        return self.delegated_access_manager.create_delegation_request(
            target_user_id, relationship, scope_keys, reason
        )

    def approve_delegation_request(self, request_id):
        """Approve a delegation request"""
        return self.delegated_access_manager.approve_delegation_request(request_id)

    def reject_delegation_request(self, request_id, reason=None):
        """Reject a delegation request"""
        return self.delegated_access_manager.reject_delegation_request(request_id, reason)

    def get_delegation_requests(self, status='pending', direction='incoming'):
        """Get delegation requests"""
        return self.delegated_access_manager.get_delegation_requests(status, direction)

    def expire_delegations(self):
        """Expire all overdue delegations"""
        return self.delegated_access_manager.expire_delegations()
