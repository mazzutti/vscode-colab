import pytest

from vscode_colab.utils import SystemOperationResult


class TestSystemOperationResult:

    def test_ok_with_value(self):
        result = SystemOperationResult.Ok("success_value")
        assert result.is_ok is True
        assert result.is_err is False
        assert result.value == "success_value"
        assert result.error is None
        assert result.message is None
        assert bool(result) is True
        assert str(result) == "Ok(value=success_value)"

    def test_ok_without_value(self):
        result = SystemOperationResult.Ok()  # Represents a void success
        assert result.is_ok is True
        assert result.is_err is False
        assert result.value is None
        assert result.error is None
        assert result.message is None
        assert bool(result) is True
        assert str(result) == "Ok(value=None)"

    def test_err_with_exception_and_message(self):
        custom_error = ValueError("A custom error occurred")
        result = SystemOperationResult.Err(
            custom_error, message="Detailed error description"
        )
        assert result.is_ok is False
        assert result.is_err is True
        assert result.value is None
        assert result.error == custom_error
        assert result.message == "Detailed error description"
        assert bool(result) is False
        assert (
            str(result)
            == "Err(error=A custom error occurred, message=Detailed error description)"
        )

    def test_err_with_exception_no_custom_message(self):
        custom_error = TypeError("Type mismatch")
        result = SystemOperationResult.Err(custom_error)
        assert result.is_ok is False
        assert result.is_err is True
        assert result.value is None
        assert result.error == custom_error
        assert result.message == "Type mismatch"  # Default message is str(error)
        assert bool(result) is False
        assert str(result) == "Err(error=Type mismatch, message=Type mismatch)"

    def test_err_accessing_value_returns_none(self):
        result = SystemOperationResult.Err(Exception("test error"))
        assert result.value is None  # As per current implementation

    def test_constructor_integrity_ok_with_error(self):
        with pytest.raises(ValueError, match="Successful result cannot have an error."):
            SystemOperationResult(is_success=True, value="val", error=Exception("err"))

    def test_constructor_integrity_err_without_error(self):
        with pytest.raises(ValueError, match="Failed result must have an error."):
            SystemOperationResult(is_success=False, value="val", error=None)

    def test_generic_type_ok(self):
        result_int: SystemOperationResult[int, Exception] = SystemOperationResult.Ok(
            123
        )
        assert result_int.value == 123

        result_none: SystemOperationResult[None, Exception] = SystemOperationResult.Ok()
        assert result_none.value is None

    def test_generic_type_err(self):
        error = ValueError("Bad value")
        result_str_err: SystemOperationResult[str, ValueError] = (
            SystemOperationResult.Err(error)
        )
        assert result_str_err.error == error
        assert isinstance(result_str_err.error, ValueError)
