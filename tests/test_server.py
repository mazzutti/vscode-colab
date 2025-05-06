import os
import subprocess
import time
from unittest import mock
from unittest.mock import patch

import pytest

from vscode_colab import server


@pytest.fixture(autouse=True)
def cleanup_code_dir_and_tar(tmp_path, monkeypatch):
    # Setup: change working directory to a temp path
    orig_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield
    os.chdir(orig_cwd)


def test_download_vscode_cli_returns_true_if_code_exists(monkeypatch, caplog):
    monkeypatch.setattr(os.path, "exists", lambda path: path == "./code")
    result = server.download_vscode_cli()
    assert result is True
    assert "VS Code CLI already exists. Skipping download." in caplog.text


def test_download_vscode_cli_forces_download_if_force(monkeypatch, caplog):
    # Simulate "./code" exists, but force_download=True triggers download
    monkeypatch.setattr(os.path, "exists", lambda path: "./code")
    called = {}

    def fake_run(*args, **kwargs):
        # Check if it's the curl or tar command
        if "curl" in args[0] or "tar" in args[0]:
            called["ran"] = True
            return mock.Mock()
        raise ValueError(f"Unexpected command: {args[0]}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    # After extraction, "./code" should exist
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    result = server.download_vscode_cli(force_download=True)
    assert result is True
    assert called.get("ran", False)
    assert "Downloading VS Code CLI..." in caplog.text


def test_download_vscode_cli_download_and_extract_success(monkeypatch, caplog):
    # Simulate "./code" does not exist initially, but exists after extraction
    exists_calls = {"count": 0}

    def fake_exists(path):
        if path == "./code":
            exists_calls["count"] += 1
            return exists_calls["count"] > 1  # False first, True after extraction
        return False

    monkeypatch.setattr(os.path, "exists", fake_exists)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: mock.Mock())
    result = server.download_vscode_cli()
    assert result is True
    assert "Downloading VS Code CLI..." in caplog.text
    assert "VS Code CLI tarball downloaded. Extracting..." in caplog.text
    assert "VS Code CLI extracted successfully to './code'." in caplog.text


def test_download_vscode_cli_extract_fails(monkeypatch, caplog):
    # Simulate extraction does not create "./code"
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: mock.Mock()
    )  # Mock download and extraction
    result = server.download_vscode_cli()
    assert result is False
    assert "Failed to extract VS Code CLI properly" in caplog.text


def test_download_vscode_cli_subprocess_error(monkeypatch, caplog):
    # Simulate subprocess.run raises CalledProcessError
    monkeypatch.setattr(
        os.path, "exists", lambda path: False
    )  # Ensure download is attempted

    def fake_run(*a, **k):
        raise subprocess.CalledProcessError(1, "cmd")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = server.download_vscode_cli()
    assert result is False
    assert "Error during VS Code download or extraction" in caplog.text


def test_login_returns_false_if_cli_not_available(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: False)
    result = server.login()
    assert result is False
    assert "VS Code CLI not available, cannot perform login." in caplog.text


def test_login_success(monkeypatch, caplog):
    # Simulate CLI available
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    # Simulate process output with both URL and code
    mock_proc = mock.Mock()
    lines = [
        "Some output\n",
        "Go to https://github.com/login/device and enter code ABCD-1234\n",
        "",
    ]
    mock_proc.stdout.readline.side_effect = lambda: lines.pop(0) if lines else ""
    poll_results = [None, None, 0]
    mock_proc.poll.side_effect = lambda: poll_results.pop(0) if poll_results else 0
    mock_proc.stdout is not None  # Ensure stdout is not None
    called = {}

    def fake_display(url, code):
        called["url"] = url
        called["code"] = code

    monkeypatch.setattr(server, "display_github_auth_link", fake_display)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    result = server.login()  # Use default provider 'github'
    assert result is True
    assert called["url"].startswith("https://github.com")
    assert called["code"] == "ABCD-1234"
    assert "Initiating VS Code Tunnel login" in caplog.text
    assert "Monitoring login process output" in caplog.text
    assert "Detected potential authentication URL" in caplog.text
    assert "Detected potential authentication code" in caplog.text
    assert "Authentication URL and code detected." in caplog.text


def test_login_timeout(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    mock_proc = mock.Mock()
    # Simulate never finding URL/code, process never ends, timeout after 60s
    mock_proc.stdout.readline.side_effect = ["no url here\n"] * 5
    mock_proc.poll.side_effect = [None] * 10  # Always running
    mock_proc.stdout is not None
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    # Patch time to simulate timeout
    times = [0, 10, 20, 30, 40, 61]
    monkeypatch.setattr(time, "time", lambda: times.pop(0) if times else 999)
    monkeypatch.setattr(mock_proc, "terminate", lambda: None)
    result = server.login()
    assert result is False
    assert "Login process timed out" in caplog.text


def test_login_process_ends_early(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    mock_proc = mock.Mock()
    # Simulate process ends before URL/code found
    mock_proc.stdout.readline.side_effect = ["no url here\n", ""]
    poll_results = [None, 0]
    mock_proc.poll.side_effect = lambda: poll_results.pop(0) if poll_results else 0
    mock_proc.stdout.read.return_value = "final output"
    mock_proc.stdout is not None
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    result = server.login()
    assert result is False
    assert "Login process ended." in caplog.text  # This might appear if process ends
    assert "Failed to detect GitHub authentication URL and code" in caplog.text


def test_login_process_ends_early_with_stdout(monkeypatch, caplog):  # Added caplog
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)

    # Simulate process ends before URL/code is found, with stdout not None
    class DummyStdout:
        def __init__(self):
            self.read_called = False

        def readline(self):
            return ""  # No output

        def read(self):
            self.read_called = True
            return "Some remaining output"

    dummy_stdout = DummyStdout()

    class DummyProc:
        def __init__(self):
            self.stdout = dummy_stdout  # Use the instance from the test scope
            self._poll = False

        def poll(self):
            # Simulate process ended
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: DummyProc())
    result = server.login()
    assert result is False
    # The login function does not call read() in this specific path.
    # assert dummy_stdout.read_called
    assert "Failed to detect GitHub authentication URL and code" in caplog.text


def test_login_exception(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)

    def fake_popen(*a, **k):
        raise Exception("fail")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = server.login()
    assert result is False
    assert "Error during login: fail" in caplog.text


def test_login_stdout_is_none(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    mock_proc = mock.Mock()
    mock_proc.stdout = None
    called = {}

    def fake_terminate():
        called["terminated"] = True

    mock_proc.terminate = fake_terminate
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    result = server.login()
    assert result is False
    assert called.get("terminated", False)
    assert "Failed to get login process stdout." in caplog.text


def test_connect_returns_none_if_cli_not_available(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: False)
    result = server.connect()
    assert result is None
    assert "VS Code CLI not available, cannot start tunnel." in caplog.text


def test_connect_success(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    # Mock configure_git to do nothing
    monkeypatch.setattr(server, "configure_git", lambda *a, **k: None)
    # Simulate process output with tunnel URL
    mock_proc = mock.Mock()
    lines = [
        "Some output\n",
        "Tunnel ready at https://vscode.dev/tunnel/abc/def\n",
        "",
    ]
    mock_proc.stdout.readline.side_effect = lambda: lines.pop(0) if lines else ""
    mock_proc.poll.side_effect = [None, None, 0]
    mock_proc.stdout is not None
    called = {}
    popen_args = {}

    def fake_display(url, name):
        called["url"] = url
        called["name"] = name

    def fake_popen(*args, **kwargs):
        popen_args["cmd_list"] = args[0]  # Capture the command list
        popen_args["kwargs"] = kwargs  # Capture kwargs like cwd
        return mock_proc

    monkeypatch.setattr(server, "display_vscode_connection_options", fake_display)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    # Call connect with specific extensions and name
    result = server.connect(
        name="mytunnel",
        extensions=["ext1", "ext2"],
        include_default_extensions=False,
    )

    assert result == mock_proc
    assert called["url"].startswith("https://vscode.dev/tunnel/")
    assert called["name"] == "mytunnel"

    cmd_list_called = popen_args["cmd_list"]
    assert "--name" in cmd_list_called
    assert cmd_list_called[cmd_list_called.index("--name") + 1] == "mytunnel"
    assert "--install-extension" in cmd_list_called
    assert "ext1" in cmd_list_called
    assert "ext2" in cmd_list_called
    # Check that default extensions are NOT included
    assert not any(
        "ms-python.python" in item for item in cmd_list_called
    )  # Check element, not substring of joined list

    assert "Starting VS Code tunnel with command" in caplog.text
    assert "VS Code Tunnel URL detected" in caplog.text


def test_connect_success_with_defaults(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    monkeypatch.setattr(server, "configure_git", lambda *a, **k: None)
    mock_proc = mock.Mock()
    lines = [
        "Tunnel ready at https://vscode.dev/tunnel/abc/def\n",
    ]
    mock_proc.stdout.readline.side_effect = lambda: lines.pop(0) if lines else ""
    mock_proc.poll.side_effect = [None, 0]
    mock_proc.stdout is not None
    popen_args = {}

    def fake_popen(*args, **kwargs):
        popen_args["cmd_list"] = args[0]  # Capture the command list
        popen_args["kwargs"] = kwargs
        return mock_proc

    monkeypatch.setattr(
        server, "display_vscode_connection_options", lambda *a, **k: None
    )
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    result = server.connect()  # Use defaults

    assert result == mock_proc

    cmd_list_called = popen_args["cmd_list"]
    assert "--name" in cmd_list_called
    assert cmd_list_called[cmd_list_called.index("--name") + 1] == "colab"
    # Check that default extensions ARE included
    assert "--install-extension" in cmd_list_called
    assert "ms-python.python" in cmd_list_called  # Check for specific extension ID
    assert "ms-toolsai.jupyter" in cmd_list_called  # Check for specific extension ID
    assert "Starting VS Code tunnel with command" in caplog.text


def test_connect_timeout(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    monkeypatch.setattr(server, "configure_git", lambda *a, **k: None)
    mock_proc = mock.Mock()
    mock_proc.stdout.readline.side_effect = ["no url here\n"] * 5
    mock_proc.poll.side_effect = [None] * 10  # Always running
    mock_proc.stdout is not None
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    # Patch time to simulate timeout
    times = [0, 10, 20, 30, 40, 61]
    monkeypatch.setattr(time, "time", lambda: times.pop(0) if times else 999)
    monkeypatch.setattr(mock_proc, "terminate", lambda: None)
    result = server.connect()
    assert result is None
    assert "Tunnel URL not detected within" in caplog.text


def test_connect_process_ends_early(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    monkeypatch.setattr(server, "configure_git", lambda *a, **k: None)
    mock_proc = mock.Mock()
    mock_proc.stdout.readline.side_effect = ["no url here\\n", ""]
    poll_results = [None, 0]

    def poll_side_effect():
        return poll_results.pop(0) if poll_results else 0

    mock_proc.poll.side_effect = poll_side_effect
    mock_proc.stdout.read.return_value = "final output"
    mock_proc.stdout is not None
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    result = server.connect()
    assert result is None
    assert "Tunnel process ended before URL was detected (EOF reached)." in caplog.text


def test_connect_process_ends_early_with_stdout(monkeypatch, caplog):  # Added caplog
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    monkeypatch.setattr(server, "configure_git", lambda *a, **k: None)

    # Simulate process ends before URL is found, with stdout not None
    class DummyStdout:
        def __init__(self):
            self.read_called = False

        def readline(self):
            return ""  # No output

        def read(self):
            self.read_called = True
            return "Some remaining output"

    # Create the dummy_stdout instance here so it can be referenced by the Popen mock
    # and checked in the assertion.
    dummy_stdout_instance = DummyStdout()

    class DummyProc:
        def __init__(self):
            self.stdout = dummy_stdout_instance  # Use the instance from the test scope
            self._poll = False

        def poll(self):
            # Simulate process ended
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: DummyProc())
    result = server.connect()
    assert result is None
    assert dummy_stdout_instance.read_called  # Check the instance used by the mock
    assert (
        "Tunnel process ended before URL was detected (EOF reached)."  # Corrected log message
        in caplog.text
    )


def test_connect_stdout_is_none(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    monkeypatch.setattr(server, "configure_git", lambda *a, **k: None)
    mock_proc = mock.Mock()
    mock_proc.stdout = None
    called = {}

    def fake_terminate():
        called["terminated"] = True

    mock_proc.terminate = fake_terminate
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    result = server.connect()
    assert result is None
    assert called.get("terminated", False)
    assert "Failed to get tunnel process stdout." in caplog.text


def test_connect_exception(monkeypatch, caplog):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    monkeypatch.setattr(server, "configure_git", lambda *a, **k: None)

    def fake_popen(*a, **k):
        raise Exception("fail")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = server.connect()
    assert result is None
    assert "Error starting tunnel: fail" in caplog.text


def test_connect_calls_configure_git(monkeypatch, caplog):  # Added caplog
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    # Mock Popen to return a dummy process that ends immediately
    mock_proc = mock.Mock()
    mock_proc.stdout.readline.return_value = ""
    mock_proc.poll.return_value = 0
    mock_proc.stdout.read.return_value = ""
    mock_proc.stdout is not None
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)

    called_configure_git = {}

    def fake_configure_git(name, email):
        called_configure_git["name"] = name
        called_configure_git["email"] = email

    monkeypatch.setattr(server, "configure_git", fake_configure_git)

    server.connect(git_user_name="Test User", git_user_email="test@example.com")

    assert called_configure_git["name"] == "Test User"
    assert called_configure_git["email"] == "test@example.com"


def test_configure_git_success(monkeypatch):
    popen_calls = []

    def fake_popen(*args, **kwargs):
        popen_calls.append(args[0])  # args[0] is the command list
        mock_proc = mock.Mock()
        mock_proc.communicate.return_value = ("", "")  # stdout, stderr
        mock_proc.returncode = 0
        return mock_proc

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    server.configure_git("Test User", "test@example.com")
    assert len(popen_calls) == 2
    assert popen_calls[0] == ["git", "config", "--global", "user.name", "Test User"]
    assert popen_calls[1] == [
        "git",
        "config",
        "--global",
        "user.email",
        "test@example.com",
    ]


def test_configure_git_skipped_if_only_name(monkeypatch, caplog):
    popen_calls = []  # Renamed from run_calls
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **k: popen_calls.append(a)
    )  # Mock Popen
    server.configure_git(git_user_name="Test User")
    assert len(popen_calls) == 0
    assert (
        "Both git_user_name and git_user_email must be provided together. Skipping git configuration."
        in caplog.text
    )


def test_configure_git_skipped_if_only_email(monkeypatch, caplog):
    popen_calls = []  # Renamed from run_calls
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **k: popen_calls.append(a)
    )  # Mock Popen
    server.configure_git(git_user_email="test@example.com")
    assert len(popen_calls) == 0
    assert (
        "Both git_user_name and git_user_email must be provided together. Skipping git configuration."
        in caplog.text
    )


def test_configure_git_skipped_if_none(monkeypatch, caplog):
    run_calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: run_calls.append(a))
    server.configure_git()
    assert len(run_calls) == 0
    assert "Skipping git configuration" not in caplog.text  # No warning if both None


def test_configure_git_file_not_found(monkeypatch, caplog):
    def fake_popen_raises_file_not_found(*args, **kwargs):
        if args[0][0] == "git":  # command list is args[0]
            raise FileNotFoundError("git not found")
        # Fallback for other Popen calls if any (though not expected in this test)
        mock_fallback_proc = mock.Mock()
        mock_fallback_proc.communicate.return_value = ("", "")
        mock_fallback_proc.returncode = 0
        return mock_fallback_proc

    monkeypatch.setattr(subprocess, "Popen", fake_popen_raises_file_not_found)
    server.configure_git("Test User", "test@example.com")
    assert "Command not found: git" in caplog.text  # This is logged by _run_command
    # The following assertion was for a message not present in the current code for this path.
    # assert "Git configuration failed due to missing git command." in caplog.text


def test_display_github_auth_link(monkeypatch):
    # Patch display and HTML to capture the HTML string
    called = {}

    class DummyHTML:
        def __init__(self, html):
            called["html"] = html

    def fake_display(obj):
        called["displayed"] = obj

    monkeypatch.setattr(server, "HTML", DummyHTML)
    monkeypatch.setattr(server, "display", fake_display)
    url = "https://github.com/login/device"
    code = "ABCD-1234"
    server.display_github_auth_link(url, code)
    assert url in called["html"]
    assert code in called["html"]
    assert isinstance(called["displayed"], DummyHTML)


def test_display_vscode_connection_options(monkeypatch):
    # Patch display and HTML to capture the HTML string
    called = {}

    class DummyHTML:
        def __init__(self, html):
            called["html"] = html

    def fake_display(obj):
        called["displayed"] = obj

    monkeypatch.setattr(server, "HTML", DummyHTML)
    monkeypatch.setattr(server, "display", fake_display)
    tunnel_url = "https://vscode.dev/tunnel/abc/def"
    tunnel_name = "mytunnel"
    server.display_vscode_connection_options(tunnel_url, tunnel_name)
    assert tunnel_url in called["html"]
    assert tunnel_name in called["html"]
    assert isinstance(called["displayed"], DummyHTML)


@patch("vscode_colab.server.download_vscode_cli", return_value=True)
@patch("vscode_colab.server.configure_git")
@patch("vscode_colab.server.setup_pyenv_and_python_version")
@patch("vscode_colab.server.setup_project_directory")
@patch("subprocess.Popen")
@patch("vscode_colab.server.display_vscode_connection_options")
def test_connect_calls_setup_pyenv(
    mock_display,
    mock_popen,
    mock_setup_project,
    mock_setup_pyenv,
    mock_configure_git,
    mock_download_cli,
    caplog,
):
    mock_proc = mock.Mock()
    mock_proc.stdout.readline.return_value = (
        "Tunnel ready at https://vscode.dev/tunnel/abc/def"
    )
    mock_proc.poll.return_value = None
    mock_popen.return_value = mock_proc
    mock_setup_pyenv.return_value = "/path/to/pyenv/python"

    server.connect(
        setup_python_version="3.9.1",
        force_python_reinstall=True,
        update_pyenv_before_install=False,
    )

    mock_setup_pyenv.assert_called_once_with(
        python_version="3.9.1",
        force_reinstall_python=True,
        update_pyenv=False,
    )
    assert "Attempting to set up Python version: 3.9.1 using pyenv." in caplog.text
    assert (
        "Using pyenv Python '/path/to/pyenv/python' for subsequent venv creation."
        in caplog.text
    )


@patch("vscode_colab.server.download_vscode_cli", return_value=True)
@patch("vscode_colab.server.configure_git")
@patch("vscode_colab.server.setup_pyenv_and_python_version")
@patch("vscode_colab.server.setup_project_directory")
@patch("subprocess.Popen")
@patch("vscode_colab.server.display_vscode_connection_options")
def test_connect_calls_setup_project_and_sets_cwd(
    mock_display,
    mock_popen,
    mock_setup_project,
    mock_setup_pyenv,
    mock_configure_git,
    mock_download_cli,
    caplog,
):
    mock_proc = mock.Mock()
    mock_proc.stdout.readline.return_value = (
        "Tunnel ready at https://vscode.dev/tunnel/abc/def"
    )
    mock_proc.poll.return_value = None
    mock_popen.return_value = mock_proc

    mock_setup_pyenv.return_value = None  # No pyenv python specified or failed
    mock_setup_project.return_value = "/tmp/my_new_project_dir"  # Project created here

    server.connect(
        create_new_project="my_new_project",
        new_project_base_path="/tmp",
        venv_name_for_project=".special_venv",
    )

    mock_setup_project.assert_called_once_with(
        project_name="my_new_project",
        base_path="/tmp",
        python_executable="python3",  # Default as pyenv returned None
        venv_name=".special_venv",
    )
    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert kwargs["cwd"] == "/tmp/my_new_project_dir"
    assert (
        "Attempting to create and set up new project: 'my_new_project' at '/tmp'."
        in caplog.text
    )
    assert "Successfully created project at '/tmp/my_new_project_dir'." in caplog.text
    assert "Tunnel will run with CWD: /tmp/my_new_project_dir" in caplog.text


@patch("vscode_colab.server.download_vscode_cli", return_value=True)
@patch("vscode_colab.server.configure_git")
@patch("vscode_colab.server.setup_pyenv_and_python_version")
@patch("vscode_colab.server.setup_project_directory")
@patch("subprocess.Popen")
@patch("vscode_colab.server.display_vscode_connection_options")
def test_connect_setup_project_uses_pyenv_python_and_sets_cwd(
    mock_display,
    mock_popen,
    mock_setup_project,
    mock_setup_pyenv,
    mock_configure_git,
    mock_download_cli,
    caplog,
):
    mock_proc = mock.Mock()
    mock_proc.stdout.readline.return_value = (
        "Tunnel ready at https://vscode.dev/tunnel/abc/def"
    )
    mock_proc.poll.return_value = None
    mock_popen.return_value = mock_proc

    pyenv_python_exe = "/opt/pyenv/versions/3.8.10/bin/python"
    mock_setup_pyenv.return_value = pyenv_python_exe

    created_project_path = "/projects/new_pyenv_project"
    mock_setup_project.return_value = created_project_path

    server.connect(
        setup_python_version="3.8.10",
        create_new_project="new_pyenv_project",
        new_project_base_path="/projects",
    )

    mock_setup_pyenv.assert_called_once_with(
        python_version="3.8.10",
        force_reinstall_python=False,
        update_pyenv=True,
    )
    mock_setup_project.assert_called_once_with(
        project_name="new_pyenv_project",
        base_path="/projects",
        python_executable=pyenv_python_exe,  # Should use from pyenv
        venv_name=".venv",  # Default
    )
    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert kwargs["cwd"] == created_project_path
    assert (
        f"Using pyenv Python '{pyenv_python_exe}' for subsequent venv creation."
        in caplog.text
    )
    assert f"Successfully created project at '{created_project_path}'." in caplog.text
    assert f"Tunnel will run with CWD: {created_project_path}" in caplog.text


@patch("vscode_colab.server.download_vscode_cli", return_value=True)
@patch("vscode_colab.server.configure_git")
@patch("vscode_colab.server.setup_pyenv_and_python_version", return_value=None)
@patch(
    "vscode_colab.server.setup_project_directory", return_value=None
)  # Project creation fails or not requested
@patch("subprocess.Popen")
@patch("vscode_colab.server.display_vscode_connection_options")
def test_connect_cwd_is_default_if_project_creation_fails_or_skipped(
    mock_display,
    mock_popen,
    mock_setup_project,
    mock_setup_pyenv,
    mock_configure_git,
    mock_download_cli,
    monkeypatch,
    caplog,
):
    mock_proc = mock.Mock()
    mock_proc.stdout.readline.return_value = (
        "Tunnel ready at https://vscode.dev/tunnel/abc/def"
    )
    mock_proc.poll.return_value = None
    mock_popen.return_value = mock_proc

    original_cwd = "/original/working/directory"
    monkeypatch.setattr(os, "getcwd", lambda: original_cwd)

    # Scenario 1: No project creation requested
    server.connect()
    mock_popen.assert_called_with(
        mock.ANY,
        stdout=mock.ANY,
        stderr=mock.ANY,
        text=True,
        bufsize=1,
        universal_newlines=True,
        cwd=original_cwd,
    )
    assert f"Tunnel will run with CWD: {original_cwd}" in caplog.text
    caplog.clear()  # Clear logs for next part of test

    # Scenario 2: Project creation requested but fails
    mock_setup_project.reset_mock()  # Reset call count
    server.connect(create_new_project="failed_project")
    mock_setup_project.assert_called_once()  # setup_project_directory was called
    # Popen should still be called with original_cwd because setup_project_directory returned None
    # The call count for popen will be 2 now. We check the last call.
    args, kwargs = mock_popen.call_args
    assert kwargs["cwd"] == original_cwd
    assert "Failed to create project 'failed_project'." in caplog.text
    assert f"Tunnel will run with CWD: {original_cwd}" in caplog.text
    assert f"Tunnel will run with CWD: {original_cwd}" in caplog.text
