import os
import subprocess
from unittest import mock
from unittest.mock import MagicMock, call, patch

import pytest

from vscode_colab.environment.python_env import (
    INSTALLER_SCRIPT_NAME,
    PYENV_BUILD_DEPENDENCIES,
    PYENV_INSTALLER_URL,
    PythonEnvManager,
)
from vscode_colab.system import System
from vscode_colab.utils import SystemOperationResult


@pytest.fixture
def mock_system_pyenv():
    mock_system = MagicMock(spec=System)
    mock_system.expand_user_path.side_effect = lambda x: x.replace("~", "/home/user")
    mock_system.get_absolute_path.side_effect = lambda x: (
        x if x.startswith("/") else f"/abs/{x}"
    )
    mock_system.is_executable.return_value = False  # Default to not executable
    mock_system.which.return_value = "/usr/bin/bash"  # Default bash found
    return mock_system


@pytest.fixture
def pyenv_manager(mock_system_pyenv):
    return PythonEnvManager(mock_system_pyenv)


# Expected paths based on fixtures
PYENV_ROOT = "/home/user/.pyenv"
PYENV_EXECUTABLE = f"{PYENV_ROOT}/bin/pyenv"
INSTALLER_SCRIPT_AT_ROOT = f"{PYENV_ROOT}/{INSTALLER_SCRIPT_NAME}"


class TestPythonEnvManagerPropertiesPaths:
    def test_paths_initialized_correctly(self, pyenv_manager):
        assert pyenv_manager.pyenv_root == PYENV_ROOT
        assert pyenv_manager.pyenv_executable_path == PYENV_EXECUTABLE

    def test_get_pyenv_env_vars(self, pyenv_manager):
        with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            env_vars = pyenv_manager._get_pyenv_env_vars()

        assert env_vars["PYENV_ROOT"] == PYENV_ROOT
        expected_path = f"{PYENV_ROOT}/bin:{PYENV_ROOT}/shims:/usr/bin"
        assert env_vars["PATH"] == expected_path

    def test_is_pyenv_installed_true(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.is_executable.return_value = True
        assert pyenv_manager.is_pyenv_installed is True
        mock_system_pyenv.is_executable.assert_called_with(PYENV_EXECUTABLE)

    def test_is_pyenv_installed_false(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.is_executable.return_value = False
        assert pyenv_manager.is_pyenv_installed is False


class TestPyenvDependencyInstallation:
    def test_install_pyenv_dependencies_success(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.which.side_effect = (
            lambda cmd: f"/usr/bin/{cmd}"
        )  # sudo, apt found
        mock_system_pyenv.run_command.side_effect = [
            MagicMock(returncode=0, stdout="update done"),  # apt update
            MagicMock(returncode=0, stdout="install done"),  # apt install
        ]
        result = pyenv_manager.install_pyenv_dependencies()
        assert result.is_ok
        expected_install_cmd_start = [
            "/usr/bin/sudo",
            "/usr/bin/apt",
            "install",
            "-y",
        ]

        update_call = call(
            ["/usr/bin/sudo", "/usr/bin/apt", "update", "-y"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Check that the install command contains all dependencies
        install_cmd_call = mock_system_pyenv.run_command.call_args_list[1]
        actual_install_cmd_list = install_cmd_call[0][
            0
        ]  # First arg of the call tuple is the cmd list

        assert (
            actual_install_cmd_list[: len(expected_install_cmd_start)]
            == expected_install_cmd_start
        )
        assert (
            set(actual_install_cmd_list[len(expected_install_cmd_start) :])
            == PYENV_BUILD_DEPENDENCIES
        )
        assert mock_system_pyenv.run_command.call_args_list[0] == update_call

    def test_install_pyenv_dependencies_sudo_not_found(
        self, pyenv_manager, mock_system_pyenv
    ):
        mock_system_pyenv.which.side_effect = lambda cmd: (
            None if cmd == "sudo" else f"/usr/bin/{cmd}"
        )
        result = pyenv_manager.install_pyenv_dependencies()
        assert result.is_err
        assert "sudo command not found" in result.message

    def test_install_pyenv_dependencies_apt_update_fails(
        self, pyenv_manager, mock_system_pyenv
    ):
        mock_system_pyenv.which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=1, stderr="update error"
        )
        result = pyenv_manager.install_pyenv_dependencies()
        assert result.is_err
        assert "apt-get update failed" in result.message  # Changed to apt-get

    def test_install_pyenv_dependencies_apt_install_fails(
        self, pyenv_manager, mock_system_pyenv
    ):
        mock_system_pyenv.which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_system_pyenv.run_command.side_effect = [
            MagicMock(returncode=0),  # update success
            MagicMock(returncode=1, stderr="install error"),  # install fails
        ]
        result = pyenv_manager.install_pyenv_dependencies()
        assert result.is_err
        assert "apt install pyenv dependencies failed" in result.message


class TestPyenvInstallation:
    def test_install_pyenv_success(self, pyenv_manager, mock_system_pyenv):
        # Mock sequence: make_dirs -> download_file -> run_command (installer) -> is_executable (final check)
        mock_system_pyenv.make_dirs.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.download_file.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=0, stdout="pyenv installed"
        )
        # For the final check mock_system_pyenv.is_executable should return true
        mock_system_pyenv.is_executable.return_value = True  # After successful install

        # Mock dependency install to succeed without actually running its commands for this unit test
        with patch.object(
            pyenv_manager,
            "install_pyenv_dependencies",
            return_value=SystemOperationResult.Ok(),
        ) as mock_install_deps:
            result = pyenv_manager.install_pyenv(attempt_to_install_deps=True)

        assert result.is_ok
        assert result.value == PYENV_EXECUTABLE
        mock_install_deps.assert_called_once()
        mock_system_pyenv.make_dirs.assert_called_once_with(PYENV_ROOT)
        mock_system_pyenv.download_file.assert_called_once_with(
            PYENV_INSTALLER_URL, INSTALLER_SCRIPT_AT_ROOT
        )
        mock_system_pyenv.run_command.assert_called_once()  # For installer
        assert mock_system_pyenv.run_command.call_args[0][0] == [
            "/usr/bin/bash",
            INSTALLER_SCRIPT_AT_ROOT,
        ]
        mock_system_pyenv.remove_file.assert_called_with(
            INSTALLER_SCRIPT_AT_ROOT, missing_ok=True, log_success=False
        )

    def test_install_pyenv_deps_fail_continues_and_succeeds(
        self, pyenv_manager, mock_system_pyenv
    ):
        mock_system_pyenv.make_dirs.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.download_file.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.run_command.return_value = MagicMock(returncode=0)
        mock_system_pyenv.is_executable.return_value = True

        with patch.object(
            pyenv_manager,
            "install_pyenv_dependencies",
            return_value=SystemOperationResult.Err(Exception("deps fail")),
        ) as mock_install_deps:
            result = pyenv_manager.install_pyenv(attempt_to_install_deps=True)

        assert result.is_ok  # pyenv install itself succeeded
        mock_install_deps.assert_called_once()

    def test_install_pyenv_download_fails(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.make_dirs.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.download_file.return_value = SystemOperationResult.Err(
            Exception("Network Error")
        )

        with patch.object(
            pyenv_manager,
            "install_pyenv_dependencies",
            return_value=SystemOperationResult.Ok(),
        ):
            result = pyenv_manager.install_pyenv()

        assert result.is_err
        assert (
            "Failed to download pyenv installer" in result.message
        )  # Made message more specific
        mock_system_pyenv.remove_file.assert_called_once_with(
            INSTALLER_SCRIPT_AT_ROOT, missing_ok=True, log_success=False
        )

    def test_install_pyenv_installer_script_fails(
        self, pyenv_manager, mock_system_pyenv
    ):
        mock_system_pyenv.make_dirs.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.download_file.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=1, stderr="Installer error"
        )

        with patch.object(
            pyenv_manager,
            "install_pyenv_dependencies",
            return_value=SystemOperationResult.Ok(),
        ):
            result = pyenv_manager.install_pyenv()

        assert result.is_err
        assert "Pyenv installer script failed" in result.message

    def test_install_pyenv_not_executable_after_install(
        self, pyenv_manager, mock_system_pyenv
    ):
        mock_system_pyenv.make_dirs.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.download_file.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.run_command.return_value = MagicMock(returncode=0)
        mock_system_pyenv.is_executable.return_value = (
            False  # This is the key for this test
        )

        with patch.object(
            pyenv_manager,
            "install_pyenv_dependencies",
            return_value=SystemOperationResult.Ok(),
        ):
            result = pyenv_manager.install_pyenv()

        assert result.is_err
        assert "executable not found at" in str(result.error)


class TestPythonVersionManagement:
    PYTHON_VERSION = "3.9.5"

    @pytest.fixture(autouse=True)
    def _setup_pyenv_installed(self, pyenv_manager, mock_system_pyenv):
        # For these tests, assume pyenv itself is installed and executable
        mock_system_pyenv.is_executable.return_value = (
            True  # For pyenv_manager.is_pyenv_installed
        )

    def test_is_python_version_installed_true(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=0, stdout=f"3.8.0\n{self.PYTHON_VERSION}\n3.10.0"
        )
        result = pyenv_manager.is_python_version_installed(self.PYTHON_VERSION)
        assert result.is_ok
        assert result.value is True
        mock_system_pyenv.run_command.assert_called_once_with(
            [PYENV_EXECUTABLE, "versions", "--bare"],
            env=mock.ANY,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_is_python_version_installed_false(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=0, stdout="3.8.0\n3.10.0"
        )
        result = pyenv_manager.is_python_version_installed(self.PYTHON_VERSION)
        assert result.is_ok
        assert result.value is False

    def test_is_python_version_installed_pyenv_command_fails(
        self, pyenv_manager, mock_system_pyenv
    ):
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=1, stderr="pyenv versions error"
        )
        result = pyenv_manager.is_python_version_installed(self.PYTHON_VERSION)
        assert result.is_err
        assert (
            "Could not list pyenv versions" in result.message
        )  # Made message more specific

    def test_install_python_version_success(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=0, stdout="python installed"
        )
        result = pyenv_manager.install_python_version(self.PYTHON_VERSION)
        assert result.is_ok
        mock_system_pyenv.run_command.assert_called_once_with(
            [PYENV_EXECUTABLE, "install", self.PYTHON_VERSION],
            env=mock.ANY,
            capture_output=True,
            text=True,
            check=False,
        )
        # Check that PYTHON_CONFIGURE_OPTS was in env
        env_arg = mock_system_pyenv.run_command.call_args[1]["env"]
        assert "PYTHON_CONFIGURE_OPTS" in env_arg
        assert env_arg["PYTHON_CONFIGURE_OPTS"] == "--enable-shared"

    def test_install_python_version_fails(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=1, stderr="install error"
        )
        result = pyenv_manager.install_python_version(self.PYTHON_VERSION)
        assert result.is_err
        assert (
            f"Failed to install Python {self.PYTHON_VERSION} using pyenv"
            in result.message
        )  # Made message more specific

    def test_set_global_python_version_success(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.run_command.return_value = MagicMock(returncode=0)
        result = pyenv_manager.set_global_python_version(self.PYTHON_VERSION)
        assert result.is_ok
        mock_system_pyenv.run_command.assert_called_once_with(
            [PYENV_EXECUTABLE, "global", self.PYTHON_VERSION],
            env=mock.ANY,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_get_python_executable_path_via_which_success(
        self, pyenv_manager, mock_system_pyenv
    ):
        expected_path_via_which = (
            f"{PYENV_ROOT}/versions/{self.PYTHON_VERSION}/bin/python-via-which"
        )
        # Mock 'pyenv which python'
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=0, stdout=expected_path_via_which
        )
        # Mock is_executable for the path returned by 'which' and for pyenv itself
        mock_system_pyenv.is_executable.side_effect = (
            lambda p: p == expected_path_via_which or p == PYENV_EXECUTABLE
        )
        # Mock realpath
        mock_system_pyenv.get_absolute_path.side_effect = lambda p: (
            os.path.realpath(p) if "realpath" in str(p) else p
        )  # for os.path.realpath

        # Patch os.path.realpath as it's called directly
        with patch("os.path.realpath", return_value=expected_path_via_which):
            result = pyenv_manager.get_python_executable_path(self.PYTHON_VERSION)

        assert result.is_ok
        assert result.value == expected_path_via_which
        # is_executable called for PYENV_EXECUTABLE (by is_pyenv_installed) and expected_path_via_which
        assert mock_system_pyenv.is_executable.call_count >= 1

    def test_get_python_executable_path_direct_fallback_success(
        self, pyenv_manager, mock_system_pyenv
    ):
        direct_path = f"{PYENV_ROOT}/versions/{self.PYTHON_VERSION}/bin/python"
        # 'pyenv which python' fails or returns non-executable
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=1, stderr="which error"
        )
        # is_executable for direct_path is True, others False (except pyenv bin itself)
        mock_system_pyenv.is_executable.side_effect = (
            lambda p: p == PYENV_EXECUTABLE or p == direct_path
        )

        result = pyenv_manager.get_python_executable_path(self.PYTHON_VERSION)
        assert result.is_ok
        assert result.value == direct_path

    def test_get_python_executable_path_not_found(
        self, pyenv_manager, mock_system_pyenv
    ):
        # 'pyenv which python' fails
        mock_system_pyenv.run_command.return_value = MagicMock(
            returncode=1, stderr="which error"
        )
        # Direct path is also not executable (is_executable default is False, only True for PYENV_EXECUTABLE)
        mock_system_pyenv.is_executable.side_effect = lambda p: p == PYENV_EXECUTABLE

        result = pyenv_manager.get_python_executable_path(self.PYTHON_VERSION)
        assert result.is_err
        assert "could not be reliably located" in result.message


class TestSetupAndGetPythonExecutable:
    PYTHON_VERSION = "3.10.1"

    def test_setup_full_success_new_pyenv_new_python(
        self, pyenv_manager, mock_system_pyenv
    ):
        # Pyenv not installed initially
        # is_executable calls: pyenv_manager.is_pyenv_installed (False), pyenv after install (True),
        # python after install (True), python via which (True)
        pyenv_exe_path_after_install = PYENV_EXECUTABLE
        python_exe_path_after_install = (
            f"{PYENV_ROOT}/versions/{self.PYTHON_VERSION}/bin/python"
        )

        is_executable_call_count = 0

        def is_executable_side_effect(path_checked):
            nonlocal is_executable_call_count
            is_executable_call_count += 1
            if is_executable_call_count == 1:  # First is_pyenv_installed check
                return False
            if (
                path_checked == pyenv_exe_path_after_install
            ):  # pyenv after its install, or subsequent is_pyenv_installed
                return True
            if (
                path_checked == python_exe_path_after_install
            ):  # python version direct path check or from 'which'
                return True
            return False

        mock_system_pyenv.is_executable.side_effect = is_executable_side_effect

        # Mock calls for install_pyenv()
        mock_system_pyenv.make_dirs.return_value = SystemOperationResult.Ok()
        mock_system_pyenv.download_file.return_value = SystemOperationResult.Ok()
        # run_command calls: pyenv_installer, pyenv_versions, pyenv_install, pyenv_global, pyenv_which
        mock_system_pyenv.run_command.side_effect = [
            MagicMock(returncode=0, stdout="pyenv installer ok"),  # pyenv installer
            MagicMock(returncode=0, stdout=""),  # pyenv versions (empty)
            MagicMock(
                returncode=0, stdout="python install ok"
            ),  # pyenv install <version>
            MagicMock(returncode=0, stdout="global set ok"),  # pyenv global <version>
            MagicMock(
                returncode=0, stdout=python_exe_path_after_install
            ),  # pyenv which python
        ]

        # Mock dependency install to succeed
        with patch.object(
            pyenv_manager,
            "install_pyenv_dependencies",
            return_value=SystemOperationResult.Ok(),
        ) as mock_deps:
            result = pyenv_manager.setup_and_get_python_executable(
                self.PYTHON_VERSION, attempt_pyenv_dependency_install=True
            )

        assert result.is_ok
        assert result.value == python_exe_path_after_install
        mock_deps.assert_called_once()
        assert mock_system_pyenv.run_command.call_count == 5

    def test_setup_pyenv_install_fails(self, pyenv_manager, mock_system_pyenv):
        mock_system_pyenv.is_executable.return_value = False  # pyenv not installed
        mock_system_pyenv.make_dirs.return_value = SystemOperationResult.Err(
            OSError("cannot make dir")
        )  # pyenv install fails at mkdir

        with patch.object(
            pyenv_manager,
            "install_pyenv_dependencies",
            return_value=SystemOperationResult.Ok(),
        ):
            result = pyenv_manager.setup_and_get_python_executable(self.PYTHON_VERSION)

        assert result.is_err
        assert "Pyenv installation failed" in result.message

    def test_setup_python_already_installed_skip_install(
        self, pyenv_manager, mock_system_pyenv
    ):
        python_exe_path = f"{PYENV_ROOT}/versions/{self.PYTHON_VERSION}/bin/python"
        # Pyenv is installed, Python version is installed
        mock_system_pyenv.is_executable.side_effect = (
            lambda p: p == PYENV_EXECUTABLE or p == python_exe_path
        )
        mock_system_pyenv.run_command.side_effect = [
            MagicMock(
                returncode=0, stdout=self.PYTHON_VERSION
            ),  # pyenv versions (version present)
            MagicMock(returncode=0, stdout="global set ok"),  # pyenv global
            MagicMock(returncode=0, stdout=python_exe_path),  # pyenv which
        ]

        result = pyenv_manager.setup_and_get_python_executable(
            self.PYTHON_VERSION, force_reinstall_python=False
        )
        assert result.is_ok
        assert result.value == python_exe_path
        # Check that 'pyenv install <version>' was NOT in the calls
        pyenv_install_cmd_part = [PYENV_EXECUTABLE, "install", self.PYTHON_VERSION]
        for call_obj in mock_system_pyenv.run_command.call_args_list:
            assert (
                call_obj[0][0][:3] != pyenv_install_cmd_part
            )  # Check first 3 elements for safety
        assert mock_system_pyenv.run_command.call_count == 3  # versions, global, which
