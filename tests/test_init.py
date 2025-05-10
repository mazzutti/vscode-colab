import subprocess
from unittest.mock import MagicMock, patch

import pytest

# Functions and classes to test from __init__.py
from vscode_colab import (
    DEFAULT_EXTENSIONS,
    System,
    SystemOperationResult,
    connect,
    login,
)

# Also from vscode_colab.server import server_login, server_connect (if needed for patching)


@pytest.fixture
def mock_default_system_instance():
    # This fixture will patch the _default_system_instance in vscode_colab.__init__
    with patch("vscode_colab._default_system_instance", spec=System) as mock_system:
        yield mock_system


class TestInitLogin:
    @patch("vscode_colab.server_login")  # Patch the aliased server_login
    def test_login_uses_default_system_instance(
        self, mock_server_login_impl, mock_default_system_instance
    ):
        mock_server_login_impl.return_value = True  # Simulate successful login

        result = login(provider="test_provider")

        assert result is True
        # Check that server_login was called with the _default_system_instance
        mock_server_login_impl.assert_called_once_with(
            system=mock_default_system_instance, provider="test_provider"
        )

    @patch("vscode_colab.server_login")
    def test_login_uses_provided_system_instance(self, mock_server_login_impl):
        custom_mock_system = MagicMock(spec=System)
        mock_server_login_impl.return_value = False  # Simulate failed login

        result = login(provider="github", system=custom_mock_system)

        assert result is False
        # Check that server_login was called with the custom_mock_system
        mock_server_login_impl.assert_called_once_with(
            system=custom_mock_system, provider="github"
        )


class TestInitConnect:
    @patch("vscode_colab.server_connect")  # Patch the aliased server_connect
    def test_connect_uses_default_system_instance_with_defaults(
        self, mock_server_connect_impl, mock_default_system_instance
    ):
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_server_connect_impl.return_value = mock_proc

        result = connect()  # Call with all defaults

        assert result == mock_proc
        mock_server_connect_impl.assert_called_once_with(
            system=mock_default_system_instance,
            name="colab",
            include_default_extensions=True,
            extensions=None,
            git_user_name=None,
            git_user_email=None,
            setup_python_version=None,
            force_python_reinstall=False,
            attempt_pyenv_dependency_install=True,  # Default from __init__
            create_new_project=None,
            new_project_base_path=".",
            venv_name_for_project=".venv",
        )

    @patch("vscode_colab.server_connect")
    def test_connect_uses_provided_system_and_custom_args(
        self, mock_server_connect_impl
    ):
        custom_mock_system = MagicMock(spec=System)
        mock_server_connect_impl.return_value = None  # Simulate connection failure

        result = connect(
            name="custom_tunnel",
            include_default_extensions=False,
            extensions=["ext1"],
            git_user_name="Git User",
            git_user_email="git@email.com",
            setup_python_version="3.10",
            force_python_reinstall=True,
            attempt_pyenv_dependency_install=False,
            create_new_project="MyProj",
            new_project_base_path="/tmp/projects",
            venv_name_for_project=".custom_env",
            system=custom_mock_system,
        )

        assert result is None
        mock_server_connect_impl.assert_called_once_with(
            system=custom_mock_system,
            name="custom_tunnel",
            include_default_extensions=False,
            extensions=["ext1"],
            git_user_name="Git User",
            git_user_email="git@email.com",
            setup_python_version="3.10",
            force_python_reinstall=True,
            attempt_pyenv_dependency_install=False,
            create_new_project="MyProj",
            new_project_base_path="/tmp/projects",
            venv_name_for_project=".custom_env",
        )


class TestInitExports:
    def test_default_extensions_is_frozenset(self):
        assert isinstance(DEFAULT_EXTENSIONS, frozenset)
        # Check for a known default extension
        assert "ms-python.python" in DEFAULT_EXTENSIONS

    def test_system_class_is_exported(self):
        # Simple check that it's the class we expect
        assert System.__name__ == "System"
        # Further check: an instance of System from init should be an instance of the class type
        s = System()
        assert isinstance(s, System)

    def test_system_operation_result_is_exported(self):
        assert SystemOperationResult.__name__ == "SystemOperationResult"
        ok_res = SystemOperationResult.Ok("test")
        assert ok_res.is_ok
        err_res = SystemOperationResult.Err(ValueError("test"))
        assert err_res.is_err
