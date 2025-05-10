import io
import os
import subprocess
import time
from unittest import mock
from unittest.mock import ANY, MagicMock, call, patch

import pytest
from IPython.display import HTML

from vscode_colab.environment import PythonEnvManager  # For type hinting if needed
from vscode_colab.server import (
    DEFAULT_EXTENSIONS,
    _configure_environment_for_tunnel,
    _launch_and_monitor_tunnel,
    _prepare_vscode_tunnel_command,
    connect,
    display_github_auth_link,
    display_vscode_connection_options,
    download_vscode_cli,
    login,
)
from vscode_colab.system import System
from vscode_colab.utils import SystemOperationResult


# --- Fixtures ---
@pytest.fixture
def mock_system_server():
    mock_sys = MagicMock(spec=System)
    mock_sys.get_absolute_path.side_effect = lambda x: (
        f"/abs/{x}" if not x.startswith("/") else x
    )
    mock_sys.is_executable.return_value = False  # Default: CLI not executable
    mock_sys.file_exists.return_value = False  # Default: File does not exist
    mock_sys.path_exists.return_value = False  # Default: Path does not exist
    mock_sys.which.return_value = "/usr/bin/tar"  # Default tar found
    mock_sys.get_cwd.return_value = "/current/test/dir"
    return mock_sys


@pytest.fixture
def mock_display_server(monkeypatch):
    mock_disp = MagicMock()
    monkeypatch.setattr("vscode_colab.server.display", mock_disp)
    # Also mock HTML if it's directly instantiated and then passed to display
    mock_html_constructor = MagicMock(return_value=MagicMock(spec=HTML))
    monkeypatch.setattr("vscode_colab.server.HTML", mock_html_constructor)
    return {"display": mock_disp, "HTML": mock_html_constructor}


# --- Tests for download_vscode_cli ---
CLI_DIR_NAME = "code"
CLI_EXE_NAME_IN_DIR = "code"
ABS_CLI_DIR_PATH = f"/abs/{CLI_DIR_NAME}"  # From mock_system_server.get_absolute_path
ABS_CLI_EXE_PATH = f"{ABS_CLI_DIR_PATH}/{CLI_EXE_NAME_IN_DIR}"


def test_download_vscode_cli_already_exists_executable(mock_system_server):
    mock_system_server.is_executable.return_value = (
        True  # CLI is already there and executable
    )

    result = download_vscode_cli(mock_system_server)

    assert result.is_ok
    assert result.value == ABS_CLI_EXE_PATH
    mock_system_server.download_file.assert_not_called()


def test_download_vscode_cli_success_full_download_and_setup(mock_system_server):
    # Simulate: not executable initially, download succeeds, tar extracts, chmod succeeds
    mock_system_server.is_executable.side_effect = [
        False,  # Initial check (download_vscode_cli L50)
        False,  # Before chmod (download_vscode_cli L140)
        True,  # After chmod (download_vscode_cli L165)
    ]
    mock_system_server.download_file.return_value = SystemOperationResult.Ok()
    mock_system_server.run_command.return_value = MagicMock(
        returncode=0, stdout="tar extracted"
    )  # tar command
    # After tar, the CLI executable file should exist
    mock_system_server.file_exists.return_value = True  # for abs_cli_executable_path
    # Mock permissions part
    mock_system_server.get_permissions.return_value = SystemOperationResult.Ok(0o644)
    mock_system_server.change_permissions.return_value = SystemOperationResult.Ok()

    result = download_vscode_cli(mock_system_server, force_download=False)

    assert result.is_ok
    assert result.value == ABS_CLI_EXE_PATH
    mock_system_server.download_file.assert_called_once()
    mock_system_server.run_command.assert_called_once()  # tar command
    mock_system_server.change_permissions.assert_called_once_with(
        ABS_CLI_EXE_PATH, 0o644 | 0o111
    )


def test_download_vscode_cli_force_download_removes_existing(mock_system_server):
    mock_system_server.path_exists.return_value = True  # CLI dir path exists
    mock_system_server.remove_dir.return_value = SystemOperationResult.Ok()
    # Continue with successful download and setup as above
    mock_system_server.is_executable.side_effect = [False, True]
    mock_system_server.download_file.return_value = SystemOperationResult.Ok()
    mock_system_server.run_command.return_value = MagicMock(returncode=0)
    mock_system_server.file_exists.return_value = True
    mock_system_server.get_permissions.return_value = SystemOperationResult.Ok(0o644)
    mock_system_server.change_permissions.return_value = SystemOperationResult.Ok()

    result = download_vscode_cli(mock_system_server, force_download=True)

    assert result.is_ok
    mock_system_server.remove_dir.assert_called_once_with(
        ABS_CLI_DIR_PATH, recursive=True
    )
    mock_system_server.download_file.assert_called_once()


def test_download_vscode_cli_download_fails(mock_system_server):
    mock_system_server.download_file.return_value = SystemOperationResult.Err(
        Exception("Network Error")
    )
    result = download_vscode_cli(mock_system_server)
    assert result.is_err
    assert "Network Error" in str(result.error)


def test_download_vscode_cli_tar_not_found(mock_system_server):
    mock_system_server.download_file.return_value = SystemOperationResult.Ok()
    mock_system_server.which.return_value = None  # tar not found
    result = download_vscode_cli(mock_system_server)
    assert result.is_err
    assert "'tar' command not found" in result.message


def test_download_vscode_cli_tar_extraction_fails(mock_system_server):
    mock_system_server.download_file.return_value = SystemOperationResult.Ok()
    # tar is found (default mock_system_server.which)
    mock_system_server.run_command.return_value = MagicMock(
        returncode=1, stderr="tar error"
    )  # tar fails
    result = download_vscode_cli(mock_system_server)
    assert result.is_err
    assert "Failed to extract VS Code CLI" in result.message
    assert "tar error" in result.message


def test_download_vscode_cli_executable_not_found_after_extraction(mock_system_server):
    mock_system_server.download_file.return_value = SystemOperationResult.Ok()
    mock_system_server.run_command.return_value = MagicMock(returncode=0)  # tar success
    mock_system_server.file_exists.return_value = (
        False  # But the executable is not there
    )

    result = download_vscode_cli(mock_system_server)
    assert result.is_err
    assert (
        f"VS Code CLI executable '{ABS_CLI_EXE_PATH}' not found after extraction"
        in result.message
    )


def test_download_vscode_cli_chmod_fails_but_still_not_executable(mock_system_server):
    mock_system_server.download_file.return_value = SystemOperationResult.Ok()
    mock_system_server.run_command.return_value = MagicMock(returncode=0)  # tar success
    mock_system_server.file_exists.return_value = True  # Exe exists
    # is_executable: False (initial), False (before chmod), False (after chmod fails)
    mock_system_server.is_executable.side_effect = [False, False, False]
    mock_system_server.get_permissions.return_value = SystemOperationResult.Ok(0o644)
    mock_system_server.change_permissions.return_value = SystemOperationResult.Err(
        OSError("chmod fail")
    )

    result = download_vscode_cli(mock_system_server)
    assert result.is_err  # Should fail if still not executable after trying
    assert "still not executable after attempting chmod" in result.message


# --- Tests for login ---
@patch("vscode_colab.server.download_vscode_cli")
@patch("subprocess.Popen", autospec=True)
def test_login_success(
    mock_popen, mock_download_cli, mock_system_server, mock_display_server
):
    mock_download_cli.return_value = SystemOperationResult.Ok(ABS_CLI_EXE_PATH)

    mock_proc = mock_popen.return_value
    # Explicitly create and spec stdout, as autospec might not handle it for Popen
    # The Popen call in login() uses text=True (universal_newlines=True),
    # so stdout will be a text stream.
    mock_proc.stdout = MagicMock(spec=io.TextIOWrapper)

    # Simulate process output with URL and code
    lines = [
        "Some output before\n",
        "To sign in, use a web browser to open the page https://github.com/login/device and enter the code ABCD-1234.\n",
        "Some output after\n",
        "",  # EOF
    ]
    mock_proc.stdout.readline.side_effect = lines
    # Poll: None (running) until after URL/code found, then maybe 0 or we don't care as func returns
    mock_proc.poll.return_value = None

    result = login(mock_system_server)

    assert result is True
    mock_download_cli.assert_called_once_with(system=mock_system_server)
    mock_popen.assert_called_once_with(
        [ABS_CLI_EXE_PATH, "tunnel", "user", "login", "--provider", "github"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        cwd=mock_system_server.get_cwd(),
    )
    mock_display_server["HTML"].assert_called_once()

    # Check if URL and code were correctly embedded in the HTML content
    # mock_display_server["HTML"] is the mock for the HTML constructor.
    # It's called as HTML(rendered_html_string)
    html_constructor_call_args = mock_display_server["HTML"].call_args

    # The first positional argument to the HTML constructor is the rendered HTML string
    assert html_constructor_call_args is not None, "HTML constructor was not called"
    rendered_html_string = html_constructor_call_args.args[0]

    assert "https://github.com/login/device" in rendered_html_string
    assert "ABCD-1234" in rendered_html_string

    mock_display_server["display"].assert_called_once()


@patch("vscode_colab.server.download_vscode_cli")
def test_login_cli_download_fails(mock_download_cli, mock_system_server):
    mock_download_cli.return_value = SystemOperationResult.Err(
        Exception("CLI download failed")
    )
    result = login(mock_system_server)
    assert result is False


@patch("vscode_colab.server.download_vscode_cli")
@patch("subprocess.Popen")
def test_login_timeout(mock_popen, mock_download_cli, mock_system_server):
    mock_download_cli.return_value = SystemOperationResult.Ok(ABS_CLI_EXE_PATH)
    mock_proc = mock_popen.return_value
    mock_proc.stdout.readline.return_value = (
        "no url or code here\n"  # Keeps outputting non-matching lines
    )
    mock_proc.poll.return_value = None  # Always running
    mock_popen.return_value = mock_proc

    # Patch time.time to simulate timeout
    original_time = time.time
    time_calls = [
        original_time(),
        original_time() + 70,
    ]  # Start, then time after timeout

    def time_side_effect():
        if time_calls:
            return time_calls.pop(0)
        return original_time() + 100  # Keep returning time well past timeout

    with patch("time.time", side_effect=time_side_effect):
        result = login(mock_system_server)

    assert result is False
    mock_proc.terminate.assert_called_once()


@patch("vscode_colab.server.download_vscode_cli")
@patch("subprocess.Popen")
def test_login_process_ends_before_auth_info(
    mock_popen, mock_download_cli, mock_system_server
):
    mock_download_cli.return_value = SystemOperationResult.Ok(ABS_CLI_EXE_PATH)
    mock_proc = mock_popen.return_value
    mock_proc.stdout.readline.side_effect = ["output\n", ""]  # EOF
    mock_proc.poll.return_value = 0  # Process ended
    mock_popen.return_value = mock_proc

    result = login(mock_system_server)
    assert result is False


# --- Tests for connect and its helpers ---


# _configure_environment_for_tunnel is complex, test its main branches
@patch("vscode_colab.server.configure_git")
@patch("vscode_colab.server.PythonEnvManager")
@patch("vscode_colab.server.setup_project_directory")
def test_configure_environment_defaults(
    mock_setup_proj, mock_pyenv_mgr_constructor, mock_conf_git, mock_system_server
):
    # No git, no pyenv, no project creation

    pyenv_res, tunnel_cwd = _configure_environment_for_tunnel(
        mock_system_server, None, None, None, False, False, None, ".", ".venv"
    )

    assert pyenv_res.is_ok  # Default python3
    assert pyenv_res.value == "python3"
    assert tunnel_cwd == mock_system_server.get_cwd()  # Should be initial CWD
    mock_conf_git.assert_not_called()
    mock_pyenv_mgr_constructor.assert_not_called()
    mock_setup_proj.assert_not_called()


@patch("vscode_colab.server.configure_git")
@patch("vscode_colab.server.PythonEnvManager")
@patch("vscode_colab.server.setup_project_directory")
def test_configure_environment_with_git_pyenv_project_success(
    mock_setup_proj, mock_pyenv_mgr_constructor, mock_conf_git, mock_system_server
):
    mock_conf_git.return_value = SystemOperationResult.Ok()

    mock_pyenv_mgr_instance = MagicMock()
    mock_pyenv_mgr_instance.setup_and_get_python_executable.return_value = (
        SystemOperationResult.Ok("/pyenv/python")
    )
    mock_pyenv_mgr_constructor.return_value = mock_pyenv_mgr_instance

    mock_setup_proj.return_value = SystemOperationResult.Ok("/abs/my_new_project_dir")

    pyenv_res, tunnel_cwd = _configure_environment_for_tunnel(
        mock_system_server,
        "Test User",
        "test@example.com",
        "3.9",
        False,
        True,
        "my_new_project",
        "/base",
        ".special_venv",
    )

    assert pyenv_res.is_ok
    assert pyenv_res.value == "/pyenv/python"
    assert tunnel_cwd == "/abs/my_new_project_dir"

    mock_conf_git.assert_called_once_with(
        mock_system_server, "Test User", "test@example.com"
    )
    mock_pyenv_mgr_constructor.assert_called_once_with(system=mock_system_server)
    mock_pyenv_mgr_instance.setup_and_get_python_executable.assert_called_once_with(
        python_version="3.9",
        force_reinstall_python=False,
        attempt_pyenv_dependency_install=True,
    )
    mock_setup_proj.assert_called_once_with(
        mock_system_server,
        project_name="my_new_project",
        base_path="/base",  # Corrected: mock_system_server.get_absolute_path("/base") returns "/base"
        python_executable="/pyenv/python",
        venv_name=".special_venv",
    )


def test_prepare_vscode_tunnel_command_defaults():
    cmd_list = _prepare_vscode_tunnel_command(
        ABS_CLI_EXE_PATH, "colab-tunnel", True, None
    )
    assert cmd_list[:5] == [
        ABS_CLI_EXE_PATH,
        "tunnel",
        "--accept-server-license-terms",
        "--name",
        "colab-tunnel",
    ]
    assert "--install-extension" in cmd_list
    # Check if a few default extensions are there
    assert "ms-python.python" in cmd_list
    assert "ms-toolsai.jupyter" in cmd_list


def test_prepare_vscode_tunnel_command_custom_extensions_no_defaults():
    custom_ext = ["ext1.foo", "ext2.bar"]
    cmd_list = _prepare_vscode_tunnel_command(
        ABS_CLI_EXE_PATH, "custom-tunnel", False, custom_ext
    )
    assert cmd_list[:5] == [
        ABS_CLI_EXE_PATH,
        "tunnel",
        "--accept-server-license-terms",
        "--name",
        "custom-tunnel",
    ]
    assert "--install-extension" in cmd_list
    assert "ext1.foo" in cmd_list
    assert "ext2.bar" in cmd_list
    assert "ms-python.python" not in cmd_list  # Default not included


@patch("subprocess.Popen")
def test_launch_and_monitor_tunnel_success(
    mock_popen, mock_system_server, mock_display_server
):
    mock_proc = mock_popen.return_value
    lines = [
        "Tunnel logs...\n",
        "Ready to connect to VS Code Tunnel: https://vscode.dev/tunnel/colab-tunnel/folder\n",
        "",
    ]
    mock_proc.stdout.readline.side_effect = lines
    mock_proc.poll.return_value = None  # Running
    mock_popen.return_value = mock_proc

    cmd_list = [ABS_CLI_EXE_PATH, "tunnel", "--name", "colab-tunnel"]
    tunnel_cwd = "/project/dir"

    result_proc = _launch_and_monitor_tunnel(cmd_list, tunnel_cwd, "colab-tunnel")

    assert result_proc == mock_proc
    mock_popen.assert_called_once_with(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        cwd=tunnel_cwd,
    )
    mock_display_server["HTML"].assert_called_once()
    html_args = mock_display_server["HTML"].call_args[0][
        0
    ]  # First arg is the rendered HTML string
    assert "https://vscode.dev/tunnel/colab-tunnel/folder" in html_args
    assert "colab-tunnel" in html_args


@patch("subprocess.Popen")
def test_launch_and_monitor_tunnel_timeout(mock_popen, mock_system_server):
    mock_proc = mock_popen.return_value
    mock_proc.stdout.readline.return_value = "Still waiting...\n"
    mock_proc.poll.return_value = None
    mock_popen.return_value = mock_proc

    original_time = time.time
    time_calls = [original_time(), original_time() + 70]  # Timeout is 60s

    with patch(
        "time.time",
        side_effect=lambda: time_calls.pop(0) if time_calls else original_time() + 100,
    ):
        result_proc = _launch_and_monitor_tunnel([], "/cwd", "test-tunnel")

    assert result_proc is None
    mock_proc.terminate.assert_called_once()


# Integration test for the main `connect` function, mocking its direct dependencies
@patch("vscode_colab.server.download_vscode_cli")
@patch("vscode_colab.server._configure_environment_for_tunnel")
@patch("vscode_colab.server._prepare_vscode_tunnel_command")
@patch("vscode_colab.server._launch_and_monitor_tunnel")
def test_connect_main_flow_success(
    mock_launch_monitor,
    mock_prepare_cmd,
    mock_config_env,
    mock_download_cli,
    mock_system_server,
):
    mock_download_cli.return_value = SystemOperationResult.Ok(ABS_CLI_EXE_PATH)
    # _configure_environment_for_tunnel returns (SOR_python_exe, tunnel_CWD)
    mock_config_env.return_value = (
        SystemOperationResult.Ok("python3"),
        "/configured/cwd",
    )

    expected_cmd_list = [ABS_CLI_EXE_PATH, "tunnel", "--name", "my-test-tunnel"]
    mock_prepare_cmd.return_value = expected_cmd_list

    mock_tunnel_proc = MagicMock(spec=subprocess.Popen)
    mock_launch_monitor.return_value = mock_tunnel_proc

    result = connect(mock_system_server, name="my-test-tunnel")

    assert result == mock_tunnel_proc
    mock_download_cli.assert_called_once_with(mock_system_server, force_download=False)
    mock_config_env.assert_called_once_with(
        mock_system_server,
        None,
        None,
        None,
        False,
        True,
        None,
        ".",
        ".venv",  # Defaults
    )
    mock_prepare_cmd.assert_called_once_with(
        cli_executable_path=ABS_CLI_EXE_PATH,
        tunnel_name="my-test-tunnel",
        include_default_extensions=True,
        custom_extensions=None,  # Defaults
    )
    mock_launch_monitor.assert_called_once_with(
        expected_cmd_list,  # Removed mock_system_server
        tunnel_cwd="/configured/cwd",
        tunnel_name="my-test-tunnel",
    )


@patch("vscode_colab.server.download_vscode_cli")
def test_connect_cli_download_fails_overall_connect_fails(
    mock_download_cli, mock_system_server
):
    mock_download_cli.return_value = SystemOperationResult.Err(
        Exception("Download Boom")
    )
    result = connect(mock_system_server)
    assert result is None
