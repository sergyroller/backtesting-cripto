"""Domain exceptions shared by all backtesting modules."""


class DomainError(Exception):
    """Base class for every domain error."""


class ConfigurationError(DomainError):
    """Invalid strategy or backtest configuration."""


class DataValidationError(DomainError):
    """A dataset failed integrity or consistency checks."""


class InsufficientDataError(DomainError):
    """Not enough data is available for the requested operation."""
