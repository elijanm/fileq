class UserAlreadyExistsError(Exception):
    pass
class InvalidCredentialsError(Exception):
    pass
class AccountLockedError(Exception):
    pass
class RateLimitExceededError(Exception):
    pass
class ServiceUnavailableError(Exception):
    pass