from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound=Exception)


class SystemOperationResult(Generic[T, E]):
    """
    Represents the result of a system operation, which can either be a success (Ok) or a failure (Err).
    """

    def __init__(
        self,
        is_success: bool,
        value: Optional[T] = None,
        error: Optional[E] = None,
        message: Optional[str] = None,
    ):
        self._is_success: bool = is_success
        self._value: Optional[T] = value
        self._error: Optional[E] = error
        self._message: Optional[str] = message  # Additional context for the error

        if is_success and error is not None:
            raise ValueError("Successful result cannot have an error.")
        if not is_success and error is None:
            raise ValueError("Failed result must have an error.")
        if is_success and value is None:
            # Allow successful operations to have no specific return value (like a void function)
            # but ensure _value is explicitly set to something (even if None) to type hint correctly
            pass

    @property
    def is_ok(self) -> bool:
        return self._is_success

    @property
    def is_err(self) -> bool:
        return not self._is_success

    @property
    def value(self) -> Optional[T]:
        if not self._is_success:
            return None
        return self._value

    @property
    def error(self) -> Optional[E]:
        return self._error

    @property
    def message(self) -> Optional[str]:
        """
        Returns an optional descriptive message, typically used for errors.
        """
        return self._message

    @staticmethod
    def Ok(
        value: Optional[T] = None,
    ) -> "SystemOperationResult[T, Any]":  # Using Any for E in Ok case
        # If value is None, it's like a void success.
        return SystemOperationResult(is_success=True, value=value, error=None)

    @staticmethod
    def Err(
        error: E, message: Optional[str] = None
    ) -> "SystemOperationResult[Any, E]":  # Using Any for T in Err case
        return SystemOperationResult(
            is_success=False, value=None, error=error, message=message or str(error)
        )

    def __bool__(self) -> bool:
        return self._is_success

    def __str__(self) -> str:
        if self._is_success:
            return f"Ok(value={self._value})"
        return f"Err(error={self._error}, message={self._message})"
