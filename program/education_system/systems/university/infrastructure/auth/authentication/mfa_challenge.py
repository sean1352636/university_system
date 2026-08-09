from ..facade import UserAuth

def complete_mfa(auth: UserAuth, user_id, code):
    return auth.complete_two_fa_login(user_id, code)
