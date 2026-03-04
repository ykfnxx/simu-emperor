"""Memory module exception classes."""


class ParseError(Exception):
    """Exception raised when query parsing fails."""

    def __init__(self, message: str, **kwargs):
        """Initialize ParseError with message and optional context."""
        super().__init__(message)
        self.context = kwargs


class RetrievalError(Exception):
    """Exception raised when memory retrieval fails."""

    def __init__(self, message: str, **kwargs):
        """Initialize RetrievalError with message and optional context."""
        super().__init__(message)
        self.context = kwargs
