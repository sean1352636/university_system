"""
Blockchain Credentials & Digital Badges CLI Interface

Command-line interface for managing blockchain credentials, digital badges,
badge issuances, verifications, and wallet management.

Delegates to the core service which already provides a full menu-driven CLI.
"""

from education_system.university_system.modules.domain.blockchain.services.blockchain_credentials_core import (
    display_blockchain_credentials_menu,
    create_blockchain_credential,
    view_blockchain_credentials,
    verify_blockchain_credential,
    revoke_blockchain_credential,
    create_digital_badge,
    view_digital_badges,
    issue_badge_to_student,
    view_student_badges,
    create_blockchain_wallet,
    view_blockchain_wallets,
    display_blockchain_statistics,
    init_blockchain_database,
)


class BlockchainCLI:
    """CLI interface for Blockchain Credentials & Digital Badges.

    Wraps the service-level menu for consistency with other domain CLIs
    that use a class-based pattern.
    """

    def __init__(self, auth=None):
        """Initialize the Blockchain CLI.

        Args:
            auth: Optional auth context for permission checks.
        """
        self.auth = auth

    def main_menu(self):
        """Launch the main blockchain credentials menu."""
        display_blockchain_credentials_menu(auth=self.auth)

    # Direct access to individual operations
    create_credential = staticmethod(create_blockchain_credential)
    view_credentials = staticmethod(view_blockchain_credentials)
    verify_credential = staticmethod(verify_blockchain_credential)
    revoke_credential = staticmethod(revoke_blockchain_credential)
    create_badge = staticmethod(create_digital_badge)
    view_badges = staticmethod(view_digital_badges)
    issue_badge = staticmethod(issue_badge_to_student)
    view_student_badges = staticmethod(view_student_badges)
    create_wallet = staticmethod(create_blockchain_wallet)
    view_wallets = staticmethod(view_blockchain_wallets)
    statistics = staticmethod(display_blockchain_statistics)


__all__ = [
    'BlockchainCLI',
    'display_blockchain_credentials_menu',
]
