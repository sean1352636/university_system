from ..facade import UserAuth

def create_delegation(auth: UserAuth, delegator_id, delegate_id, permissions):
    return auth.create_delegation(delegator_id, delegate_id, permissions)

def revoke_delegation(auth: UserAuth, delegation_id):
    return auth.revoke_delegation(delegation_id)
