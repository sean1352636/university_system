def complete_mfa(auth, user_id, code):
    return auth.complete_two_fa_login(user_id, code)
