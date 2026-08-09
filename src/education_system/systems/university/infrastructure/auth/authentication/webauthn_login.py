from ..facade import UserAuth

def authenticate_webauthn(auth: UserAuth, credential):
    return auth.login_via_webauthn(credential)
