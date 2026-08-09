"""Deprecated compatibility façade for the authentication core."""
from .facade import MinimalVoiceInterface, UserAuth
from .context import get_auth_instance, get_current_user, set_auth_instance
from .context import __getattr__
from .bootstrap.consistency_checks import test_authentication_fix, test_authentication_with_ai_detector, test_plagiarism_authentication, simple_login_test, test_trip_integration, quick_test_integration
from .bootstrap.default_accounts import setup_default_accounts

__all__ = [
    "UserAuth", "MinimalVoiceInterface", "get_current_user",
    "set_auth_instance", "get_auth_instance", "setup_default_accounts",
    'test_authentication_fix', 'test_authentication_with_ai_detector', 'test_plagiarism_authentication', 'simple_login_test', 'test_trip_integration', 'quick_test_integration'
]

if __name__ == "__main__":
    print("UserAuth Core Module")
    print("=" * 50)
    print("This module provides the central authentication orchestration layer.")
    print("Available test functions:")
    print("  - test_authentication_fix()")
    print("  - test_authentication_with_ai_detector()")
    print("  - test_plagiarism_authentication()")
    print("  - simple_login_test()")
    print("  - test_trip_integration()")
    print("  - quick_test_integration()")
    print("  - setup_default_accounts()")
    print("\nRun quick_test_integration() for a basic test...")
    print("=" * 50)

    # Run quick test
    quick_test_integration()
