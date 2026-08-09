"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthAccountsAccountLinkingMixin:
    def create_link_request(self, target_user_id, reason=None):
        """Create a request to link another account"""
        return self.account_linking_manager.create_link_request(target_user_id, reason)

    def approve_link_request(self, request_id):
        """Approve a pending link request"""
        return self.account_linking_manager.approve_link_request(request_id)

    def reject_link_request(self, request_id, reason=None):
        """Reject a pending link request"""
        return self.account_linking_manager.reject_link_request(request_id, reason)

    def get_linked_accounts(self, user_id=None):
        """Get all linked accounts for a user"""
        return self.account_linking_manager.get_linked_accounts(user_id)

    def switch_active_role(self, linked_account_id):
        """Switch to a linked account's role"""
        return self.account_linking_manager.switch_active_role(linked_account_id)

    @staticmethod
    def _validate_username(username):
        """Validate username format"""
        from education_system.systems.university.infrastructure.auth.core_utils.utils import validate_username
        return validate_username(username)

    def revert_role(self):
        """Revert to original role after role switch"""
        return self.account_linking_manager.revert_role()

    def unlink_account(self, link_id):
        """Remove a link between accounts"""
        return self.account_linking_manager.unlink_account(link_id)

    def get_link_requests(self, status='pending', direction='incoming'):
        """Get account link requests"""
        return self.account_linking_manager.get_link_requests(status, direction)
