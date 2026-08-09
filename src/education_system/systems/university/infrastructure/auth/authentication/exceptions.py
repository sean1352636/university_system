class AuthenticationServiceError(RuntimeError):
    pass

class InvalidAuthenticationMethod(AuthenticationServiceError):
    pass
