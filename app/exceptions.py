class DomainError(Exception):
    """Base class for errors that can be safely translated at the HTTP boundary."""


class InvalidCredentialsError(DomainError):
    pass


class DuplicateEmailError(DomainError):
    pass


class UserNotFoundError(DomainError):
    pass


class ProhibitedLifecycleError(DomainError):
    pass


class InvalidResetCodeError(DomainError):
    pass


class TileDownloadError(DomainError):
    pass
