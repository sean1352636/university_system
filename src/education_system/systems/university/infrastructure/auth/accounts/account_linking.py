from ..facade import UserAuth

def create_link(auth: UserAuth, source_user_id, target_user_id):
    return auth.create_link_request(source_user_id, target_user_id)

def unlink(auth: UserAuth, user_id, linked_user_id):
    return auth.unlink_account(user_id, linked_user_id)
