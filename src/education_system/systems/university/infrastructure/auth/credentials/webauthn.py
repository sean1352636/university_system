from ..facade import UserAuth

def register_key(auth: UserAuth, user_id, key_name):
    return auth.register_webauthn_key(user_id, key_name)

def remove_key(auth: UserAuth, user_id, key_id):
    return auth.remove_webauthn_key(user_id, key_id)
