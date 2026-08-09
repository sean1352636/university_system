from ..facade import UserAuth

def change_password(auth: UserAuth, user_id, current_password, new_password):
    return auth.change_password(user_id, current_password, new_password)
