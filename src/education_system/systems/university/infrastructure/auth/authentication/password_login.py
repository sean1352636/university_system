from ..facade import UserAuth

def authenticate(auth: UserAuth, username, password):
    return auth.login(username, password)
