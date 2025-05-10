import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vscode_colab.environment.git_handler import configure_git
from vscode_colab.system import System
from vscode_colab.utils import SystemOperationResult


@pytest.fixture
def mock_system_git():
    mock_system = MagicMock(spec=System)
    mock_system.which.return_value = "/usr/bin/git"  # Assume git is found
    return mock_system


def test_configure_git_success_both_provided(mock_system_git):
    mock_system_git.run_command.side_effect = [
        MagicMock(
            returncode=0, stdout="name configured", stderr=""
        ),  # Name config success
        MagicMock(
            returncode=0, stdout="email configured", stderr=""
        ),  # Email config success
    ]

    result = configure_git(mock_system_git, "Test User", "test@example.com")

    assert result.is_ok
    assert mock_system_git.run_command.call_count == 2
    mock_system_git.run_command.assert_any_call(
        ["/usr/bin/git", "config", "--global", "user.name", "Test User"],
        capture_output=True,
        text=True,
        check=False,
    )
    mock_system_git.run_command.assert_any_call(
        ["/usr/bin/git", "config", "--global", "user.email", "test@example.com"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_configure_git_skipped_no_params(mock_system_git):
    result = configure_git(mock_system_git)
    assert result.is_ok  # Skipped is considered OK
    mock_system_git.run_command.assert_not_called()


def test_configure_git_skipped_only_name(mock_system_git):
    result = configure_git(mock_system_git, git_user_name="Test User")
    assert result.is_ok  # Skipped is considered OK
    mock_system_git.run_command.assert_not_called()


def test_configure_git_skipped_only_email(mock_system_git):
    result = configure_git(mock_system_git, git_user_email="test@example.com")
    assert result.is_ok  # Skipped is considered OK
    mock_system_git.run_command.assert_not_called()


def test_configure_git_name_config_fails(mock_system_git):
    mock_system_git.run_command.return_value = MagicMock(
        returncode=1, stdout="", stderr="git name error"
    )

    result = configure_git(mock_system_git, "Test User", "test@example.com")

    assert result.is_err
    assert "git name error" in result.message
    mock_system_git.run_command.assert_called_once_with(
        ["/usr/bin/git", "config", "--global", "user.name", "Test User"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_configure_git_email_config_fails(mock_system_git):
    mock_system_git.run_command.side_effect = [
        MagicMock(returncode=0, stdout="name configured", stderr=""),  # Name success
        MagicMock(returncode=1, stdout="", stderr="git email error"),  # Email fails
    ]

    result = configure_git(mock_system_git, "Test User", "test@example.com")

    assert result.is_err
    assert "git email error" in result.message
    assert mock_system_git.run_command.call_count == 2


def test_configure_git_command_not_found(mock_system_git):
    mock_system_git.which.return_value = None  # git not found

    result = configure_git(mock_system_git, "Test User", "test@example.com")

    assert result.is_err
    assert isinstance(result.error, FileNotFoundError)
    assert "'git' command not found" in result.message
    mock_system_git.run_command.assert_not_called()


def test_configure_git_run_command_raises_exception_for_name(mock_system_git):
    mock_system_git.run_command.side_effect = subprocess.SubprocessError(
        "Execution failed for name"
    )

    result = configure_git(mock_system_git, "Test User", "test@example.com")
    assert result.is_err
    assert "Execution failed for name" in result.message
    assert isinstance(result.error, Exception)  # Wraps the original error


def test_configure_git_run_command_raises_exception_for_email(mock_system_git):
    mock_system_git.run_command.side_effect = [
        MagicMock(returncode=0, stdout="name configured", stderr=""),
        subprocess.SubprocessError("Execution failed for email"),
    ]
    result = configure_git(mock_system_git, "Test User", "test@example.com")
    assert result.is_err
    assert "Execution failed for email" in result.message
    assert isinstance(result.error, Exception)
