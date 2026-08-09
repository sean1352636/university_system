from ..facade import UserAuth

def generate_codes(auth: UserAuth, user_id):
    return auth.generate_recovery_codes(user_id)

def use_code(auth: UserAuth, user_id, code):
    return auth.use_recovery_code(user_id, code)
