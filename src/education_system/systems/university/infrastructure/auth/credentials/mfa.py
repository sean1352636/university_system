from ..facade import UserAuth

def enable_totp(auth: UserAuth, user_id):
    return auth.enable_two_fa(user_id)

def disable_totp(auth: UserAuth, user_id):
    return auth.disable_two_fa(user_id)
