class AppError(Exception):
    """Base application error."""


class EntityNotFoundError(AppError):
    """Raised when an external or persisted entity cannot be found."""


class ExternalServiceUnavailableError(AppError):
    """Raised when an upstream service is unavailable."""
