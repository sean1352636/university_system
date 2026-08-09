from ..facade import UserAuth

def authenticate_sso(auth: UserAuth, provider, token):
    return auth.login_via_sso(provider, token)
