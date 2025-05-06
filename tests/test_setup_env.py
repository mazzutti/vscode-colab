import os
import subprocess
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

# Assuming your setup_env.py is in src/vscode_colab
from vscode_colab import setup_env
from vscode_colab.setup_env import (
    _run_command,
    configure_git,
    setup_project_directory,
    setup_pyenv_and_python_version,
)


# Fixture to capture log messages
@pytest.fixture
def mock_logger():
    with patch("vscode_colab.setup_env.logger", autospec=True) as mock_log:
        yield mock_log


# Tests for _run_command
@patch("subprocess.Popen")
def test_run_command_success(mock_popen, mock_logger):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("stdout", "stderr")
    mock_proc.returncode = 0
    mock_popen.return_value = mock_proc

    success, stdout, stderr = _run_command(["echo", "hello"])

    assert success is True
    assert stdout == "stdout"
    assert stderr == "stderr"
    mock_popen.assert_called_once_with(
        ["echo", "hello"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=None,
        env=None,
    )
    mock_logger.info.assert_any_call("Successfully executed: echo hello")
    mock_logger.debug.assert_any_call("Stdout: stdout")
    mock_logger.debug.assert_any_call("Stderr: stderr")


@patch("subprocess.Popen")
def test_run_command_failure(mock_popen, mock_logger):
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("stdout_fail", "stderr_fail")
    mock_proc.returncode = 1
    mock_popen.return_value = mock_proc

    success, stdout, stderr = _run_command(["false_command"])

    assert success is False
    assert stdout == "stdout_fail"
    assert stderr == "stderr_fail"
    mock_logger.error.assert_any_call("Error executing: false_command")
    mock_logger.error.assert_any_call("Return code: 1")
    mock_logger.error.assert_any_call("Stdout: stdout_fail")
    mock_logger.error.assert_any_call("Stderr: stderr_fail")


@patch("subprocess.Popen", side_effect=FileNotFoundError("Command not found"))
def test_run_command_file_not_found(mock_popen, mock_logger):
    success, stdout, stderr = _run_command(["non_existent_cmd"])

    assert success is False
    assert stdout == ""
    assert stderr == "Command not found: non_existent_cmd"
    mock_logger.error.assert_any_call("Command not found: non_existent_cmd")


@patch("subprocess.Popen", side_effect=Exception("Unexpected error"))
def test_run_command_unexpected_exception(mock_popen, mock_logger):
    success, stdout, stderr = _run_command(["cmd_that_raises"])

    assert success is False
    assert stdout == ""
    assert stderr == "Unexpected error"
    mock_logger.error.assert_any_call(
        "An unexpected error occurred while running cmd_that_raises: Unexpected error"
    )


# Tests for configure_git
@patch("vscode_colab.setup_env._run_command")
def test_configure_git_both_params_provided_success(mock_run_command, mock_logger):
    mock_run_command.side_effect = [
        (True, "name_stdout", "name_stderr"),  # Success for git config user.name
        (True, "email_stdout", "email_stderr"),  # Success for git config user.email
    ]
    configure_git("Test User", "test@example.com")

    assert mock_run_command.call_count == 2
    mock_run_command.assert_any_call(
        ["git", "config", "--global", "user.name", "Test User"]
    )
    mock_run_command.assert_any_call(
        ["git", "config", "--global", "user.email", "test@example.com"]
    )
    mock_logger.info.assert_any_call(
        "Attempting to set git global user.name='Test User' and user.email='test@example.com'..."
    )
    mock_logger.info.assert_any_call(
        "Successfully set git global user.name='Test User'."
    )
    mock_logger.info.assert_any_call(
        "Successfully set git global user.email='test@example.com'."
    )


@patch("vscode_colab.setup_env._run_command")
def test_configure_git_only_name_provided_logs_warning(mock_run_command, mock_logger):
    configure_git(git_user_name="Test User")
    mock_run_command.assert_not_called()
    mock_logger.warning.assert_called_once_with(
        "Both git_user_name and git_user_email must be provided together. Skipping git configuration."
    )


@patch("vscode_colab.setup_env._run_command")
def test_configure_git_only_email_provided_logs_warning(mock_run_command, mock_logger):
    configure_git(git_user_email="test@example.com")
    mock_run_command.assert_not_called()
    mock_logger.warning.assert_called_once_with(
        "Both git_user_name and git_user_email must be provided together. Skipping git configuration."
    )


@patch("vscode_colab.setup_env._run_command")
def test_configure_git_name_config_fails(mock_run_command, mock_logger):
    mock_run_command.return_value = (
        False,
        "stdout_fail",
        "stderr_fail_name",
    )  # Fail for name
    configure_git("Test User", "test@example.com")

    mock_run_command.assert_called_once_with(
        ["git", "config", "--global", "user.name", "Test User"]
    )
    mock_logger.error.assert_any_call(
        "Failed to set git global user.name: stderr_fail_name"
    )


@patch("vscode_colab.setup_env._run_command")
def test_configure_git_email_config_fails(mock_run_command, mock_logger):
    mock_run_command.side_effect = [
        (True, "name_stdout", "name_stderr"),  # Success for name
        (False, "email_stdout_fail", "email_stderr_fail"),  # Fail for email
    ]
    configure_git("Test User", "test@example.com")

    assert mock_run_command.call_count == 2
    mock_run_command.assert_any_call(
        ["git", "config", "--global", "user.name", "Test User"]
    )
    mock_run_command.assert_any_call(
        ["git", "config", "--global", "user.email", "test@example.com"]
    )
    mock_logger.info.assert_any_call(
        "Successfully set git global user.name='Test User'."
    )
    mock_logger.error.assert_any_call(
        "Failed to set git global user.email: email_stderr_fail"
    )


@patch(
    "vscode_colab.setup_env._run_command", side_effect=Exception("Unexpected Git Error")
)
def test_configure_git_unexpected_exception(mock_run_command, mock_logger):
    configure_git("Test User", "test@example.com")
    mock_run_command.assert_called_once_with(
        ["git", "config", "--global", "user.name", "Test User"]
    )
    mock_logger.exception.assert_called_once_with(
        "An unexpected error occurred during git configuration: Unexpected Git Error"
    )


@patch("os.path.exists")
@patch("os.path.abspath")
def test_setup_project_directory_already_exists(
    mock_os_path_abspath, mock_os_path_exists, mock_logger, tmp_path
):
    project_name = "existing_project"
    base_path = str(tmp_path)
    abs_project_path = os.path.join(base_path, project_name)

    mock_os_path_abspath.return_value = abs_project_path
    mock_os_path_exists.return_value = True  # Project already exists

    result_path = setup_project_directory(project_name, base_path=base_path)

    assert result_path == abs_project_path
    mock_logger.info.assert_called_once_with(
        f"Project directory {abs_project_path} already exists. Skipping creation."
    )


@patch("os.makedirs", side_effect=OSError("Permission denied to create"))
@patch("os.path.exists", return_value=False)
@patch("os.path.abspath")
def test_setup_project_directory_creation_fails(
    mock_os_path_abspath,
    mock_os_path_exists_creation_fail,
    mock_os_makedirs,
    mock_logger,
    tmp_path,
):
    project_name = "fail_project_creation"
    base_path = str(tmp_path)
    abs_project_path = os.path.join(base_path, project_name)
    mock_os_path_abspath.return_value = abs_project_path

    result_path = setup_project_directory(project_name, base_path=base_path)

    assert result_path is None
    mock_os_makedirs.assert_called_once_with(abs_project_path)
    mock_logger.error.assert_called_once_with(
        f"Failed to create project directory {abs_project_path}: Permission denied to create"
    )


@patch("os.makedirs")
@patch("os.path.exists")
@patch("os.path.abspath")
@patch("os.getcwd")
@patch("os.chdir")
@patch("vscode_colab.setup_env._run_command")
@patch("shutil.which")
@patch("builtins.open", new_callable=mock.mock_open)  # Mock open for .gitignore
def test_setup_project_directory_venv_python_not_found(
    mock_open_file_venv_fail,  # Renamed mock
    mock_shutil_which,
    mock_run_command_venv_fail,  # Renamed mock
    mock_os_chdir,
    mock_os_getcwd,
    mock_os_path_abspath,
    mock_os_path_exists_venv_fail,  # Renamed mock
    mock_os_makedirs,
    mock_logger,
    tmp_path,
):
    project_name = "venv_fail_project_python_missing"
    base_path = str(tmp_path)
    python_executable = "non_existent_python_v2"
    abs_project_path = os.path.join(base_path, project_name)

    mock_os_path_abspath.return_value = abs_project_path
    mock_os_path_exists_venv_fail.return_value = (
        False  # Project does not exist initially
    )
    mock_os_getcwd.return_value = "/original/cwd"
    mock_shutil_which.return_value = None  # Python executable does NOT exist

    # _run_command for git init (success), .gitignore is also created
    mock_run_command_venv_fail.return_value = (True, "git init stdout", "")

    result_path = setup_project_directory(
        project_name, base_path=base_path, python_executable=python_executable
    )

    assert result_path == abs_project_path  # Project dir is created
    mock_os_makedirs.assert_called_once_with(abs_project_path)
    mock_run_command_venv_fail.assert_called_once_with(
        ["git", "init"]
    )  # Git init is attempted
    mock_open_file_venv_fail.assert_called_once_with(
        ".gitignore", "w"  # Corrected: open is called after chdir
    )

    mock_logger.error.assert_any_call(
        f"Python executable '{python_executable}' not found. Cannot create virtual environment."
    )
    # Check that venv creation command was NOT called
    for call_args in mock_run_command_venv_fail.call_args_list:
        command_list = call_args[0][
            0
        ]  # The command list is the first element of the first arg
        if (
            len(command_list) > 1
            and command_list[1] == "-m"
            and command_list[2] == "venv"
        ):
            pytest.fail("Venv creation command should not have been called")


# Tests for setup_pyenv_and_python_version
@patch("os.path.exists")
@patch("vscode_colab.setup_env._run_command")
@patch("subprocess.run")
@patch("os.environ", {})  # Mock os.environ for this test suite
def test_setup_pyenv_and_python_version_pyenv_not_installed_curl_fails(
    mock_subprocess_run, mock_run_command, mock_os_path_exists, mock_logger
):
    mock_os_path_exists.return_value = False  # pyenv not installed
    mock_subprocess_run.side_effect = FileNotFoundError("curl not found")

    result = setup_pyenv_and_python_version("3.9.18")

    assert result is None
    mock_logger.info.assert_any_call("pyenv not found. Attempting to install pyenv...")
    mock_logger.error.assert_any_call(
        "curl command not found. Cannot download pyenv installer."
    )
    mock_run_command.assert_not_called()


@patch("os.path.exists")
@patch("vscode_colab.setup_env._run_command")
@patch("subprocess.run")
@patch("os.environ", {})
def test_setup_pyenv_and_python_version_pyenv_not_installed_script_fails(
    mock_subprocess_run, mock_run_command, mock_os_path_exists, mock_logger
):
    # First call to os.path.exists is for pyenv_bin (False), second is after install script (False)
    mock_os_path_exists.side_effect = [False, False]
    mock_proc = MagicMock()
    mock_proc.stdout = "pyenv installed"
    mock_proc.stderr = ""
    mock_subprocess_run.return_value = mock_proc  # pyenv install script runs

    result = setup_pyenv_and_python_version("3.9.18")

    assert result is None
    mock_logger.info.assert_any_call("pyenv not found. Attempting to install pyenv...")
    mock_logger.error.assert_any_call(
        "pyenv installation script ran, but pyenv executable not found at expected location."
    )
    mock_run_command.assert_not_called()


@patch("os.path.exists")
@patch("vscode_colab.setup_env._run_command")
@patch("subprocess.run")
@patch("os.access")
@patch("os.path.realpath")
@patch("os.environ", {})
def test_setup_pyenv_and_python_version_pyenv_install_success_python_install_success(
    mock_os_path_realpath,
    mock_os_access,
    mock_subprocess_run,
    mock_run_command,
    mock_os_path_exists,
    mock_logger,
):
    pyenv_root = os.path.expanduser("~/.pyenv")
    pyenv_bin = os.path.join(pyenv_root, "bin", "pyenv")
    python_version = "3.9.18"
    expected_python_path = os.path.join(
        pyenv_root, "versions", python_version, "bin", "python"
    )

    # os.path.exists:
    # 1. pyenv_bin (False - pyenv not installed initially)
    # 2. pyenv_bin (True - pyenv installed after script)
    # 3. expected_python_path (True - python version is installed and found)
    mock_os_path_exists.side_effect = lambda path: (
        {
            pyenv_bin: True,  # Simulate pyenv is now "installed"
            expected_python_path: True,
        }.get(path, False)
        if mock_subprocess_run.called
        else False
    )  # Only True after subprocess.run (pyenv install)

    mock_os_access.return_value = True
    mock_os_path_realpath.return_value = expected_python_path

    mock_pyenv_install_proc = MagicMock()
    mock_pyenv_install_proc.stdout = "pyenv installed"
    mock_pyenv_install_proc.stderr = ""
    mock_subprocess_run.return_value = (
        mock_pyenv_install_proc  # pyenv install script runs
    )

    # _run_command:
    # 1. pyenv versions --bare (simulating python_version not in output)
    # 2. pyenv install <version>
    # 3. pyenv global <version>
    mock_run_command.side_effect = [
        (True, "3.8.0\\n3.10.0", ""),  # pyenv versions
        (True, "install_stdout", ""),  # pyenv install
        (True, "global_stdout", ""),  # pyenv global
    ]

    result = setup_pyenv_and_python_version(python_version)

    assert result == expected_python_path
    mock_logger.info.assert_any_call("pyenv not found. Attempting to install pyenv...")
    mock_logger.info.assert_any_call(
        "pyenv installed successfully. You might need to restart your shell or source your profile for it to be available globally in new terminals."
    )
    mock_logger.info.assert_any_call(
        f"Checking if Python version {python_version} is installed by pyenv..."
    )
    mock_logger.info.assert_any_call(
        f"Python version {python_version} not found or forcing reinstall. Installing..."
    )
    mock_logger.info.assert_any_call(
        f"Attempting to install Python {python_version} with pyenv. This may take a while..."
    )
    mock_logger.info.assert_any_call(f"Python {python_version} installed successfully.")
    mock_logger.info.assert_any_call(
        f"Setting global Python version to {python_version} using pyenv..."
    )
    mock_logger.info.assert_any_call(f"Global Python version set to {python_version}.")
    mock_logger.info.assert_any_call(
        f"Python executable found at: {expected_python_path}"
    )

    assert mock_run_command.call_count == 3
    mock_run_command.assert_any_call([pyenv_bin, "versions", "--bare"], env=mock.ANY)
    mock_run_command.assert_any_call(
        [pyenv_bin, "install", python_version], env=mock.ANY
    )
    mock_run_command.assert_any_call(
        [pyenv_bin, "global", python_version], env=mock.ANY
    )


@patch("os.path.exists")
@patch("vscode_colab.setup_env._run_command")
@patch("os.environ", {})
def test_setup_pyenv_and_python_version_python_install_fails(
    mock_run_command, mock_os_path_exists, mock_logger
):
    pyenv_root = os.path.expanduser("~/.pyenv")
    pyenv_bin = os.path.join(pyenv_root, "bin", "pyenv")
    python_version = "3.9.18"

    mock_os_path_exists.return_value = True  # pyenv is installed

    # _run_command:
    # 1. pyenv versions --bare (simulating python_version not in output)
    # 2. pyenv install <version> (FAILS)
    mock_run_command.side_effect = [
        (True, "3.8.0", ""),  # pyenv versions
        (False, "install_stdout_fail", "install_stderr_fail"),  # pyenv install FAILS
    ]

    result = setup_pyenv_and_python_version(python_version)

    assert result is None
    mock_logger.error.assert_any_call(
        f"Failed to install Python {python_version} using pyenv."
    )
    mock_logger.error.assert_any_call("Install stdout: install_stdout_fail")
    mock_logger.error.assert_any_call("Install stderr: install_stderr_fail")
    assert mock_run_command.call_count == 2
    mock_run_command.assert_any_call(
        [pyenv_bin, "install", python_version], env=mock.ANY
    )


@patch("os.path.exists")
@patch("vscode_colab.setup_env._run_command")
@patch("os.environ", {})
def test_setup_pyenv_and_python_version_pyenv_global_fails(
    mock_run_command, mock_os_path_exists, mock_logger
):
    pyenv_root = os.path.expanduser("~/.pyenv")
    pyenv_bin = os.path.join(pyenv_root, "bin", "pyenv")
    python_version = "3.9.18"

    mock_os_path_exists.return_value = True  # pyenv is installed

    # _run_command:
    # 1. pyenv versions --bare
    # 2. pyenv install <version>
    # 3. pyenv global <version> (FAILS)
    mock_run_command.side_effect = [
        (True, "3.8.0", ""),  # pyenv versions
        (True, "install_stdout", ""),  # pyenv install
        (False, "global_stdout_fail", "global_stderr_fail"),  # pyenv global FAILS
    ]

    result = setup_pyenv_and_python_version(python_version)

    assert result is None
    mock_logger.error.assert_any_call(
        f"Failed to set global Python version to {python_version}. Stdout: global_stdout_fail Stderr: global_stderr_fail"
    )
    assert mock_run_command.call_count == 3
    mock_run_command.assert_any_call(
        [pyenv_bin, "global", python_version], env=mock.ANY
    )


@patch("os.path.exists")
@patch("vscode_colab.setup_env._run_command")
@patch("os.access")
@patch("os.environ", {})
def test_setup_pyenv_and_python_version_executable_not_found_at_all(
    mock_os_access, mock_run_command, mock_os_path_exists, mock_logger
):
    pyenv_root = os.path.expanduser("~/.pyenv")
    pyenv_bin = os.path.join(pyenv_root, "bin", "pyenv")
    python_version = "3.9.18"
    expected_python_path_direct = os.path.join(
        pyenv_root, "versions", python_version, "bin", "python"
    )

    # All os.path.exists calls for python executables return False
    mock_os_path_exists.side_effect = lambda path: {
        pyenv_bin: True,
        expected_python_path_direct: False,
    }.get(
        path, False
    )  # Any other path (like from 'pyenv which') will also be False

    mock_os_access.return_value = False  # For expected_python_path_direct

    # _run_command:
    # 1. pyenv versions --bare
    # 2. pyenv install <version>
    # 3. pyenv global <version>
    # 4. pyenv which python (FAILS or returns non-existent path)
    mock_run_command.side_effect = [
        (True, "3.8.0", ""),  # pyenv versions
        (True, "install_stdout", ""),  # pyenv install
        (True, "global_stdout", ""),  # pyenv global
        (False, "", "which_stderr"),  # pyenv which python fails
    ]

    result = setup_pyenv_and_python_version(python_version)

    assert result is None
    mock_logger.error.assert_any_call(
        f"Python executable not found at expected path {expected_python_path_direct} or via 'pyenv which python' after setting global."
    )
    mock_logger.error.assert_any_call("'pyenv which python' stderr: which_stderr")
    assert mock_run_command.call_count == 4


@patch("os.path.exists", return_value=True)  # pyenv is installed
@patch("vscode_colab.setup_env._run_command")
@patch("os.access", return_value=True)
@patch("os.path.realpath")
@patch("os.environ", {})
def test_setup_pyenv_and_python_version_update_pyenv_true(
    mock_os_path_realpath,
    mock_os_access,
    mock_run_command,
    mock_os_path_exists,  # Keep this even if not directly used by name due to decorator order
    mock_logger,
):
    python_version = "3.9.18"
    pyenv_root = os.path.expanduser("~/.pyenv")
    expected_python_path = os.path.join(
        pyenv_root, "versions", python_version, "bin", "python"
    )
    mock_os_path_realpath.return_value = expected_python_path

    mock_run_command.side_effect = [
        (True, python_version, ""),  # versions
        (True, "", ""),  # global
    ]
    # mock_os_path_exists needs to be more specific for this test
    mock_os_path_exists.side_effect = (
        lambda path: path == os.path.join(pyenv_root, "bin", "pyenv")
        or path == expected_python_path
    )

    setup_pyenv_and_python_version(python_version, update_pyenv=True)

    mock_logger.info.assert_any_call(
        "pyenv update functionality is noted but not implemented in this version of the script."
    )
