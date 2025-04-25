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
        called["ran"] = True
        return mock.Mock()

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
    called = {}

    def fake_display(url, code):
        called["url"] = url
        called["code"] = code

    monkeypatch.setattr(server, "display_github_auth_link", fake_display)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    result = server.login()
    assert result is True
    assert called["url"].startswith("https://github.com")
    assert called["code"] == "ABCD-1234"


def test_login_timeout(monkeypatch):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    mock_proc = mock.Mock()
    # Simulate never finding URL/code, process never ends, timeout after 60s
    mock_proc.stdout.readline.side_effect = ["no url here\n"] * 5
    mock_proc.poll.side_effect = [None] * 10  # Always running
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


def test_connect_returns_none_if_cli_not_available(monkeypatch):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: False)
    result = server.connect()
    assert result is None


def test_connect_success(monkeypatch):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    # Simulate extensions
    monkeypatch.setattr(server, "define_extensions", lambda exts=None: ["ext1", "ext2"])
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

    def fake_display(url, name):
        called["url"] = url
        called["name"] = name

    monkeypatch.setattr(server, "display_vscode_connection_options", fake_display)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: mock_proc)
    result = server.connect(name="mytunnel", extensions=["ext1"])
    assert result == mock_proc
    assert called["url"].startswith("https://vscode.dev/tunnel/")
    assert called["name"] == "mytunnel"


def test_connect_timeout(monkeypatch):
    monkeypatch.setattr(server, "download_vscode_cli", lambda: True)
    monkeypatch.setattr(server, "define_extensions", lambda exts=None: ["ext1"])
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
    monkeypatch.setattr(server, "define_extensions", lambda exts=None: ["ext1"])
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
    monkeypatch.setattr(server, "define_extensions", lambda exts=None: ["ext1"])

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
    monkeypatch.setattr(server, "define_extensions", lambda exts=None: ["ext1"])
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
    monkeypatch.setattr(server, "define_extensions", lambda exts=None: ["ext1"])

    def fake_popen(*a, **k):
        raise Exception("fail")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = server.connect()
    assert result is None
    result = server.connect()
    assert result is None


def test_define_extensions_default():
    # Should return the default list when called with no arguments
    result = server.define_extensions()
    assert isinstance(result, list)
    assert "ms-python.python" in result
    assert "ms-toolsai.jupyter" in result


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
