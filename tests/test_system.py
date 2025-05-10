import os
import shutil
import subprocess
from unittest import mock
from unittest.mock import MagicMock, mock_open, patch

import pytest
import requests

from vscode_colab.system import System


@pytest.fixture
def mock_system_dependencies(monkeypatch):
    """Mocks external dependencies for the System class."""
    mock_os = MagicMock(spec=os)
    mock_shutil = MagicMock(spec=shutil)
    mock_subprocess = MagicMock(spec=subprocess)
    mock_requests = MagicMock(spec=requests)
    # FIX: Ensure real requests.exceptions are used for try-except blocks in system.py
    mock_requests.exceptions = requests.exceptions
    mock_importlib_resources = MagicMock()

    monkeypatch.setattr("vscode_colab.system.os", mock_os)
    monkeypatch.setattr("vscode_colab.system.shutil", mock_shutil)
    monkeypatch.setattr("vscode_colab.system.subprocess", mock_subprocess)
    monkeypatch.setattr("vscode_colab.system.requests", mock_requests)
    monkeypatch.setattr(
        "vscode_colab.system.importlib.resources", mock_importlib_resources
    )

    # Specific os attributes that might be called directly
    mock_os.path = MagicMock(spec=os.path)
    mock_os.path.exists.return_value = False
    mock_os.path.isfile.return_value = False
    mock_os.path.isdir.return_value = False
    # FIX: mock_os.path.abspath should be a MagicMock for assertion capabilities
    mock_os.path.abspath = MagicMock(side_effect=lambda x: "/abs/" + x)

    # Mock logger used within System class
    mock_logger_system = MagicMock()
    monkeypatch.setattr("vscode_colab.system.logger", mock_logger_system)

    mock_subprocess.PIPE = subprocess.PIPE
    mock_subprocess.STDOUT = subprocess.STDOUT
    mock_os.X_OK = os.X_OK
    # FIX: Ensure os.getcwd() returns None for the logger assertion in test_run_command_success
    # when the run_command's cwd parameter is None.
    mock_os.getcwd.return_value = None

    return {
        "os": mock_os,
        "shutil": mock_shutil,
        "subprocess": mock_subprocess,
        "requests": mock_requests,
        "importlib_resources": mock_importlib_resources,
        "logger": mock_logger_system,
    }


@pytest.fixture
def system_instance():
    """Returns an instance of the System class."""
    return System()


class TestSystemRunCommand:

    def test_run_command_success(self, system_instance, mock_system_dependencies):
        mock_proc = MagicMock(spec=subprocess.CompletedProcess)
        mock_proc.returncode = 0
        mock_proc.stdout = "output"
        mock_proc.stderr = ""
        mock_system_dependencies["subprocess"].run.return_value = mock_proc

        cmd = ["echo", "hello"]
        result = system_instance.run_command(cmd)

        mock_system_dependencies["subprocess"].run.assert_called_once_with(
            cmd,
            cwd=None,
            env=None,
            capture_output=True,
            text=True,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Default stderr_to_stdout is True
        )
        assert result == mock_proc
        mock_system_dependencies["logger"].debug.assert_any_call(
            "Running command: 'echo hello' with CWD: None"
        )

    def test_run_command_failure_no_check(
        self, system_instance, mock_system_dependencies
    ):
        mock_proc = MagicMock(spec=subprocess.CompletedProcess)
        mock_proc.returncode = 1
        mock_proc.stdout = "output"
        mock_proc.stderr = (
            "error"  # This won't be in mock_proc.stderr if stderr_to_stdout=True
        )
        mock_system_dependencies["subprocess"].run.return_value = mock_proc

        cmd = ["false_command"]
        result = system_instance.run_command(
            cmd, stderr_to_stdout=False
        )  # Test with separate stderr

        mock_system_dependencies["subprocess"].run.assert_called_once_with(
            cmd,
            cwd=None,
            env=None,
            capture_output=True,
            text=True,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Because stderr_to_stdout=False
        )
        assert result.returncode == 1
        mock_system_dependencies["logger"].debug.assert_any_call(
            "Command 'false_command' STDERR: error"
        )

    def test_run_command_with_check_raises(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["subprocess"].run.side_effect = (
            subprocess.CalledProcessError(1, "cmd", "output", "error")
        )
        cmd = ["failing_cmd"]
        with pytest.raises(subprocess.CalledProcessError):
            system_instance.run_command(cmd, check=True)

    def test_run_command_file_not_found_raises(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["subprocess"].run.side_effect = FileNotFoundError(
            "No such file"
        )
        cmd = ["non_existent_cmd"]
        with pytest.raises(FileNotFoundError):
            system_instance.run_command(cmd)
        mock_system_dependencies["logger"].error.assert_called_once_with(
            "Command not found: non_existent_cmd. Error: No such file"
        )


class TestSystemFileDirOperations:

    def test_file_exists_true(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["os"].path.exists.return_value = True
        mock_system_dependencies["os"].path.isfile.return_value = True
        assert system_instance.file_exists("file.txt") is True
        mock_system_dependencies["os"].path.exists.assert_called_with("file.txt")
        mock_system_dependencies["os"].path.isfile.assert_called_with("file.txt")

    def test_file_exists_false_not_a_file(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].path.exists.return_value = True
        mock_system_dependencies["os"].path.isfile.return_value = False
        assert system_instance.file_exists("dir/") is False

    def test_dir_exists_true(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["os"].path.exists.return_value = True
        mock_system_dependencies["os"].path.isdir.return_value = True
        assert system_instance.dir_exists("folder") is True

    def test_make_dirs_success(self, system_instance, mock_system_dependencies):
        result = system_instance.make_dirs("/new/dir")
        mock_system_dependencies["os"].makedirs.assert_called_once_with(
            "/new/dir", exist_ok=True
        )
        assert result.is_ok
        assert result.error is None

    def test_make_dirs_failure(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["os"].makedirs.side_effect = OSError(
            "Permission denied"
        )
        result = system_instance.make_dirs("/restricted/dir")
        assert result.is_err
        assert isinstance(result.error, OSError)
        assert "Permission denied" in str(result.message)
        mock_system_dependencies["logger"].warning.assert_called_once_with(
            "Could not create directory /restricted/dir: Permission denied"
        )

    def test_remove_file_success(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["os"].path.exists.return_value = (
            True  # for file_exists
        )
        mock_system_dependencies["os"].path.isfile.return_value = (
            True  # for file_exists
        )
        result = system_instance.remove_file("file.txt")
        mock_system_dependencies["os"].remove.assert_called_once_with("file.txt")
        assert result.is_ok

    def test_remove_file_missing_ok_true(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].path.exists.return_value = (
            False  # for file_exists
        )
        result = system_instance.remove_file("missing.txt", missing_ok=True)
        assert result.is_ok
        mock_system_dependencies["os"].remove.assert_not_called()

    def test_remove_file_missing_ok_false(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].path.exists.return_value = (
            False  # for file_exists
        )
        result = system_instance.remove_file("missing.txt", missing_ok=False)
        assert result.is_err
        assert isinstance(result.error, FileNotFoundError)
        mock_system_dependencies["logger"].warning.assert_called_once_with(
            "File not found, cannot remove: missing.txt"
        )

    def test_remove_dir_recursive_success(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].path.exists.return_value = True  # for dir_exists
        mock_system_dependencies["os"].path.isdir.return_value = True  # for dir_exists
        result = system_instance.remove_dir("/my/dir")
        mock_system_dependencies["shutil"].rmtree.assert_called_once_with("/my/dir")
        assert result.is_ok

    def test_remove_dir_non_recursive_success(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].path.exists.return_value = True
        mock_system_dependencies["os"].path.isdir.return_value = True
        result = system_instance.remove_dir("/empty/dir", recursive=False)
        mock_system_dependencies["os"].rmdir.assert_called_once_with("/empty/dir")
        assert result.is_ok


class TestSystemPathUtils:
    def test_get_absolute_path(self, system_instance, mock_system_dependencies):
        # The mock for os.path.abspath is simple: lambda x: "/abs/" + x
        assert (
            system_instance.get_absolute_path("relative/path") == "/abs/relative/path"
        )
        mock_system_dependencies["os"].path.abspath.assert_called_with("relative/path")

    def test_which_found(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["shutil"].which.return_value = "/usr/bin/git"
        assert system_instance.which("git") == "/usr/bin/git"

    def test_which_not_found(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["shutil"].which.return_value = None
        assert system_instance.which("nonexistentcmd") is None

    def test_expand_user_path(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["os"].path.expanduser.return_value = (
            "/home/user/somepath"
        )
        assert system_instance.expand_user_path("~/somepath") == "/home/user/somepath"
        mock_system_dependencies["os"].path.expanduser.assert_called_with("~/somepath")

    def test_get_cwd(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["os"].getcwd.return_value = "/current/working/dir"
        assert system_instance.get_cwd() == "/current/working/dir"

    def test_change_cwd_success(self, system_instance, mock_system_dependencies):
        result = system_instance.change_cwd("/new/path")
        mock_system_dependencies["os"].chdir.assert_called_once_with("/new/path")
        assert result.is_ok

    def test_change_cwd_failure_filenotfound(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].chdir.side_effect = FileNotFoundError(
            "No such directory"
        )
        result = system_instance.change_cwd("/invalid/path")
        assert result.is_err
        assert isinstance(result.error, FileNotFoundError)


class TestSystemReadWriteAssets:

    def test_read_package_asset_success_py39plus(
        self, system_instance, mock_system_dependencies
    ):
        mock_files_obj = MagicMock()
        mock_path_obj = MagicMock()
        mock_path_obj.read_text.return_value = "asset content"
        mock_files_obj.joinpath.return_value = mock_path_obj
        mock_system_dependencies["importlib_resources"].files.return_value = (
            mock_files_obj
        )
        # Ensure AttributeError is NOT raised to simulate Python 3.9+
        # This is tricky as importlib.resources.files exists or not.
        # We can control by NOT setting side_effect=AttributeError for .files

        result = system_instance.read_package_asset("my_asset.txt")

        assert result.is_ok
        assert result.value == "asset content"
        mock_system_dependencies["importlib_resources"].files.assert_called_with(
            "vscode_colab"
        )
        mock_files_obj.joinpath.assert_called_with("assets", "my_asset.txt")
        mock_path_obj.read_text.assert_called_with(encoding="utf-8")

    def test_read_package_asset_success_legacy(
        self, system_instance, mock_system_dependencies
    ):
        # Simulate Python < 3.9 by making importlib.resources.files raise AttributeError
        mock_system_dependencies["importlib_resources"].files.side_effect = (
            AttributeError
        )

        # Mock the legacy importlib.resources.path context manager
        mock_legacy_path_obj = MagicMock()
        mock_legacy_path_obj.read_text.return_value = "legacy asset content"

        # The __enter__ method of the context manager should return the path object
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_legacy_path_obj
        mock_cm.__exit__.return_value = None
        mock_system_dependencies["importlib_resources"].path.return_value = mock_cm

        result = system_instance.read_package_asset("legacy_asset.txt")

        assert result.is_ok
        assert result.value == "legacy asset content"
        mock_system_dependencies["importlib_resources"].path.assert_called_with(
            "vscode_colab.assets", "legacy_asset.txt"
        )
        mock_legacy_path_obj.read_text.assert_called_with(encoding="utf-8")

    def test_read_package_asset_failure(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["importlib_resources"].files.side_effect = Exception(
            "Read error"
        )
        result = system_instance.read_package_asset("bad_asset.txt")
        assert result.is_err
        assert "Read error" in str(result.error)

    def test_write_file_text_success(self, system_instance, mock_system_dependencies):
        m = mock_open()
        with patch("builtins.open", m):
            result = system_instance.write_file("out.txt", "content")

        m.assert_called_once_with("out.txt", mode="w", encoding="utf-8")
        m().write.assert_called_once_with("content")
        assert result.is_ok

    def test_write_file_binary_success(self, system_instance, mock_system_dependencies):
        m = mock_open()
        with patch("builtins.open", m):
            result = system_instance.write_file("out.bin", b"binary", mode="wb")

        m.assert_called_once_with(
            "out.bin", mode="wb"
        )  # Encoding not passed for binary
        m().write.assert_called_once_with(b"binary")
        assert result.is_ok

    def test_write_file_failure(self, system_instance, mock_system_dependencies):
        m = mock_open()
        m.side_effect = IOError("Disk full")
        with patch("builtins.open", m):
            result = system_instance.write_file("out.txt", "content")
        assert result.is_err
        assert isinstance(result.error, IOError)

    def test_read_file_success(self, system_instance, mock_system_dependencies):
        m = mock_open(read_data="file content")
        with patch("builtins.open", m):
            result = system_instance.read_file("in.txt")

        m.assert_called_once_with("in.txt", mode="r", encoding="utf-8")
        assert result.is_ok
        assert result.value == "file content"

    def test_read_file_not_found(self, system_instance, mock_system_dependencies):
        m = mock_open()
        m.side_effect = FileNotFoundError("No such file")
        with patch("builtins.open", m):
            result = system_instance.read_file("missing.txt")
        assert result.is_err
        assert isinstance(result.error, FileNotFoundError)


class TestSystemNetworkOperations:

    def test_download_file_success(self, system_instance, mock_system_dependencies):
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.return_value = None  # No exception
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_system_dependencies["requests"].get.return_value = mock_response

        m_open = mock_open()
        with patch("builtins.open", m_open):
            result = system_instance.download_file(
                "http://example.com/file", "local_file"
            )

        mock_system_dependencies["requests"].get.assert_called_once_with(
            "http://example.com/file", stream=True, allow_redirects=True, timeout=30
        )
        mock_response.raise_for_status.assert_called_once()
        m_open.assert_called_once_with("local_file", "wb")
        m_open().write.assert_any_call(b"chunk1")
        m_open().write.assert_any_call(b"chunk2")
        assert result.is_ok

    def test_download_file_request_exception(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["requests"].get.side_effect = (
            requests.exceptions.RequestException("Network error")
        )
        result = system_instance.download_file("http://example.com/file", "local_file")
        assert result.is_err
        assert isinstance(result.error, requests.exceptions.RequestException)

    def test_download_file_http_error(self, system_instance, mock_system_dependencies):
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )
        mock_system_dependencies["requests"].get.return_value = mock_response

        result = system_instance.download_file(
            "http://example.com/notfound", "local_file"
        )
        assert result.is_err
        assert isinstance(result.error, requests.exceptions.HTTPError)


class TestSystemPermissionsAndMisc:
    def test_get_env_var_found(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["os"].environ.get.return_value = "my_value"
        assert system_instance.get_env_var("MY_VAR") == "my_value"
        mock_system_dependencies["os"].environ.get.assert_called_once_with(
            "MY_VAR", None
        )

    def test_get_env_var_not_found_with_default(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].environ.get.return_value = (
            "default_val"  # Mocking .get behavior
        )
        assert (
            system_instance.get_env_var("NON_EXISTENT", "default_val") == "default_val"
        )
        mock_system_dependencies["os"].environ.get.assert_called_once_with(
            "NON_EXISTENT", "default_val"
        )

    def test_is_executable_true(self, system_instance, mock_system_dependencies):
        # Simulate file_exists returning true
        mock_system_dependencies["os"].path.exists.return_value = True
        mock_system_dependencies["os"].path.isfile.return_value = True
        # Simulate os.access returning true for X_OK
        mock_system_dependencies["os"].access.return_value = True

        assert system_instance.is_executable("script.sh") is True
        mock_system_dependencies["os"].access.assert_called_once_with(
            "script.sh", os.X_OK
        )

    def test_is_executable_false_not_a_file(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].path.exists.return_value = True
        mock_system_dependencies["os"].path.isfile.return_value = (
            False  # It's a directory
        )
        assert system_instance.is_executable("folder/") is False
        mock_system_dependencies[
            "os"
        ].access.assert_not_called()  # Should not be called if not a file

    def test_is_executable_false_no_x_permission(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].path.exists.return_value = True
        mock_system_dependencies["os"].path.isfile.return_value = True
        mock_system_dependencies["os"].access.return_value = (
            False  # No execute permission
        )
        assert system_instance.is_executable("non_exec_file.txt") is False

    def test_change_permissions_success(
        self, system_instance, mock_system_dependencies
    ):
        result = system_instance.change_permissions("file.txt", 0o777)
        mock_system_dependencies["os"].chmod.assert_called_once_with("file.txt", 0o777)
        assert result.is_ok

    def test_change_permissions_failure(
        self, system_instance, mock_system_dependencies
    ):
        mock_system_dependencies["os"].chmod.side_effect = OSError(
            "Operation not permitted"
        )
        result = system_instance.change_permissions("file.txt", 0o777)
        assert result.is_err
        assert isinstance(result.error, OSError)

    def test_get_permissions_success(self, system_instance, mock_system_dependencies):
        mock_stat_result = MagicMock()
        mock_stat_result.st_mode = 0o644
        mock_system_dependencies["os"].stat.return_value = mock_stat_result

        result = system_instance.get_permissions("file.txt")
        mock_system_dependencies["os"].stat.assert_called_once_with("file.txt")
        assert result.is_ok
        assert result.value == 0o644

    def test_get_permissions_failure(self, system_instance, mock_system_dependencies):
        mock_system_dependencies["os"].stat.side_effect = OSError("File not found")
        result = system_instance.get_permissions("missing.txt")
        assert result.is_err
        assert isinstance(result.error, OSError)

    def test_get_user_home_dir(self, system_instance, mock_system_dependencies):
        # Relies on expand_user_path, which is already tested.
        # Just ensure it calls expand_user_path with "~"
        mock_system_dependencies["os"].path.expanduser.return_value = (
            "/home/testuser"  # Mock its behavior
        )
        assert system_instance.get_user_home_dir() == "/home/testuser"
        mock_system_dependencies["os"].path.expanduser.assert_called_once_with("~")
