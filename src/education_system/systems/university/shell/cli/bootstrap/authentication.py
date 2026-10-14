from .integrations import UserAuth, get_auth, set_auth

def initialize_authentication():
    auth = get_auth() or UserAuth()
    set_auth(auth)
    return auth
