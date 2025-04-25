import os
import subprocess
import time
from unittest import mock

import pytest

from vscode_colab import server


@pytest.fixture(autouse=True)
def cleanup_code_dir_and_tar(tmp_path, monkeypatch):
    # Setup: change working directory to a temp path
    orig_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield
    os.chdir(orig_cwd)


def test_download_vscode_cli_returns_true_if_code_exists(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda path: path == "./code")
    result = server.download_vscode_cli()
    assert result is True


def test_download_vscode_cli_forces_download_if_force(monkeypatch):
    # Simulate "./code" exists, but force_download=True triggers download
    monkeypatch.setattr(os.path, "exists", lambda path: path == "./code")
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


def test_download_vscode_cli_download_and_extract_success(monkeypatch):
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


def test_download_vscode_cli_extract_fails(monkeypatch):
    # Simulate extraction does not create "./code"
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: mock.Mock())
    result = server.download_vscode_cli()
    assert result is False


def test_download_vscode_cli_subprocess_error(monkeypatch):
    # Simulate subprocess.run raises CalledProcessError
    monkeypatch.setattr(os.path, "exists", lambda path: False)

    def fake_run(*a, **k):
        raise subprocess.CalledProcessError(1, "cmd")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = server.download_vscode_cli()
    assert result is False


def test_login_returns_false_if_cli_not_available(monkeypatch):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: False)
    result = server.login()
    assert result is False


def test_login_success(monkeypatch):
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


def test_login_timeout(monkeypatch):
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


def test_login_process_ends_early(monkeypatch):
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


def test_login_process_ends_early_with_stdout(monkeypatch):
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
            self.stdout = dummy_stdout
            self._poll = False

        def poll(self):
            # Simulate process ended
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: DummyProc())
    result = server.login()
    assert result is False
    assert dummy_stdout.read_called


def test_login_exception(monkeypatch):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)

    def fake_popen(*a, **k):
        raise Exception("fail")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = server.login()
    assert result is False


def test_login_stdout_is_none(monkeypatch):
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


def test_connect_returns_none_if_cli_not_available(monkeypatch):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: False)
    result = server.connect()
    assert result is None


def test_connect_success(monkeypatch):
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
        popen_args["cmd"] = args[0]  # Capture the command
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
    # Check that the command includes the correct name and extensions
    assert "--name mytunnel" in popen_args["cmd"]
    assert "--install-extension ext1" in popen_args["cmd"]
    assert "--install-extension ext2" in popen_args["cmd"]
    # Check that default extensions are NOT included
    assert "ms-python.python" not in popen_args["cmd"]


def test_connect_success_with_defaults(monkeypatch):
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
        popen_args["cmd"] = args[0]
        return mock_proc

    monkeypatch.setattr(
        server, "display_vscode_connection_options", lambda *a, **k: None
    )
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    result = server.connect()  # Use defaults

    assert result == mock_proc
    assert "--name colab" in popen_args["cmd"]
    # Check that default extensions ARE included
    assert "ms-python.python" in popen_args["cmd"]
    assert "ms-toolsai.jupyter" in popen_args["cmd"]


def test_connect_timeout(monkeypatch):
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


def test_connect_process_ends_early(monkeypatch):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    monkeypatch.setattr(server, "configure_git", lambda *a, **k: None)
    mock_proc = mock.Mock()
    mock_proc.stdout.readline.side_effect = ["no url here\n", ""]
    poll_results = [None, 0]

    def poll_side_effect():
        return poll_results.pop(0) if poll_results else 0

    mock_proc.poll.side_effect = poll_side_effect
    mock_proc.stdout.read.return_value = "final output"
    mock_proc.stdout is not None
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    result = server.connect()
    assert result is None


def test_connect_process_ends_early_with_stdout(monkeypatch):
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

    dummy_stdout = DummyStdout()

    class DummyProc:
        def __init__(self):
            self.stdout = dummy_stdout
            self._poll = False

        def poll(self):
            # Simulate process ended
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: DummyProc())
    result = server.connect()
    assert result is None
    assert dummy_stdout.read_called


def test_connect_stdout_is_none(monkeypatch):
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


def test_connect_exception(monkeypatch):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    monkeypatch.setattr(server, "configure_git", lambda *a, **k: None)

    def fake_popen(*a, **k):
        raise Exception("fail")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = server.connect()
    assert result is None


def test_connect_calls_configure_git(monkeypatch):
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


# --- Tests for configure_git ---


def test_configure_git_success(monkeypatch):
    run_calls = []

    def fake_run(*args, **kwargs):
        run_calls.append(args[0])
        return mock.Mock()

    monkeypatch.setattr(subprocess, "run", fake_run)
    server.configure_git("Test User", "test@example.com")
    assert len(run_calls) == 2
    assert run_calls[0] == ["git", "config", "--global", "user.name", "Test User"]
    assert run_calls[1] == [
        "git",
        "config",
        "--global",
        "user.email",
        "test@example.com",
    ]


def test_configure_git_skipped_if_only_name(monkeypatch, caplog):
    run_calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: run_calls.append(a))
    server.configure_git(git_user_name="Test User")
    assert len(run_calls) == 0
    assert "Skipping git configuration" in caplog.text


def test_configure_git_skipped_if_only_email(monkeypatch, caplog):
    run_calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: run_calls.append(a))
    server.configure_git(git_user_email="test@example.com")
    assert len(run_calls) == 0
    assert "Skipping git configuration" in caplog.text


def test_configure_git_skipped_if_none(monkeypatch, caplog):
    run_calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: run_calls.append(a))
    server.configure_git()
    assert len(run_calls) == 0
    assert "Skipping git configuration" not in caplog.text  # No warning if both None


def test_configure_git_file_not_found(monkeypatch, caplog):
    def fake_run(*args, **kwargs):
        if args[0][0] == "git":
            raise FileNotFoundError("git not found")
        return mock.Mock()

    monkeypatch.setattr(subprocess, "run", fake_run)
    server.configure_git("Test User", "test@example.com")
    assert "git command not found" in caplog.text
    assert "Git configuration failed" in caplog.text


# --- Tests for display functions (unchanged logic, just ensure they run) ---


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
