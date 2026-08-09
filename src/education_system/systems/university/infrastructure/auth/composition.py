from .facade import UserAuth
from .authentication.service import AuthenticationService
from .credentials.service import CredentialService
from .sessions.service import SessionService
from .recovery.service import RecoveryService

def compose_authentication(db_path=None, config_path=None):
    auth = UserAuth(db_path=db_path, config_path=config_path)
    return {
        "auth": auth,
        "authentication": AuthenticationService(auth),
        "credentials": CredentialService(auth),
        "sessions": SessionService(auth),
        "recovery": RecoveryService(auth),
    }
