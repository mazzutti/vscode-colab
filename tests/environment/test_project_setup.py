import os
from unittest.mock import MagicMock, call, patch

import pytest

from vscode_colab.environment.project_setup import (
    GET_PIP_SCRIPT_NAME,
    GET_PIP_URL,
    _create_virtual_environment,
    _determine_venv_python_executable,
    _download_get_pip_script,
    _ensure_pip_in_venv,
    _initialize_git_repo,
    _install_pip_with_script,
    setup_project_directory,
)
from vscode_colab.system import System
from vscode_colab.utils import SystemOperationResult


@pytest.fixture
def mock_system_project():
    mock_system = MagicMock(spec=System)
    mock_system.get_absolute_path = lambda x: (
        f"/abs/{x}" if not x.startswith("/") else x
    )
    mock_system.get_cwd.return_value = "/current/workdir"
    mock_system.which.return_value = "/usr/bin/python3"  # Default python3 found
    return mock_system


# Tests for _determine_venv_python_executable
@pytest.mark.parametrize(
    "base_exe_name, expected_searches, found_exe",
    [
        ("python3.9", ["python3.9", "python3", "python"], "python3.9"),
        ("python3", ["python3", "python"], "python3"),
        ("mycustompython", ["mycustompython", "python3", "python"], "mycustompython"),
        (
            "python3.9.12",
            ["python3.9.12", "python3.9", "python3", "python"],
            "python3.9",
        ),
        ("", ["python3", "python"], "python"),  # Empty base name
    ],
)
def test_determine_venv_python_executable_found(
    mock_system_project, base_exe_name, expected_searches, found_exe
):
    venv_path = "/abs/myproject/.venv"

    # Simulate which executable is found
    def is_executable_side_effect(path):
        exe_name_from_path = os.path.basename(path)
        return exe_name_from_path == found_exe

    mock_system_project.is_executable.side_effect = is_executable_side_effect

    result = _determine_venv_python_executable(
        mock_system_project, venv_path, base_exe_name
    )

    assert result == f"/abs/myproject/.venv/bin/{found_exe}"

    # Check that it tried the expected paths in order until found
    calls_made = []
    for search_name in expected_searches:
        calls_made.append(call(f"/abs/myproject/.venv/bin/{search_name}"))
        if search_name == found_exe:
            break
    mock_system_project.is_executable.assert_has_calls(calls_made)


def test_determine_venv_python_executable_not_found(mock_system_project):
    mock_system_project.is_executable.return_value = (
        False  # None of them are executable
    )
    result = _determine_venv_python_executable(
        mock_system_project, "/abs/myproject/.venv", "python3.9"
    )
    assert result is None


# Tests for _download_get_pip_script
def test_download_get_pip_script_success(mock_system_project):
    project_path = "/abs/myproject"
    expected_script_path = "/abs/myproject/get-pip.py"
    mock_system_project.download_file.return_value = SystemOperationResult.Ok()

    result = _download_get_pip_script(project_path, mock_system_project)

    assert result.is_ok
    assert result.value == expected_script_path
    mock_system_project.download_file.assert_called_once_with(
        GET_PIP_URL, expected_script_path
    )


def test_download_get_pip_script_failure(mock_system_project):
    project_path = "/abs/myproject"
    mock_system_project.download_file.return_value = SystemOperationResult.Err(
        Exception("Network Error")
    )
    result = _download_get_pip_script(project_path, mock_system_project)
    assert result.is_err


# Tests for _install_pip_with_script
def test_install_pip_with_script_success(mock_system_project):
    venv_python = "/abs/myproject/.venv/bin/python"
    script_path = "/abs/myproject/get-pip.py"
    project_path = "/abs/myproject"
    pip_check_cmd = [venv_python, "-m", "pip", "--version"]

    mock_system_project.run_command.side_effect = [
        MagicMock(
            returncode=0, stdout="pip installed", stderr=""
        ),  # get-pip.py success
        MagicMock(returncode=0, stdout="pip 20.0", stderr=""),  # pip verify success
    ]
    mock_system_project.remove_file.return_value = SystemOperationResult.Ok()

    result = _install_pip_with_script(
        mock_system_project, venv_python, script_path, project_path, pip_check_cmd
    )

    assert result.is_ok
    mock_system_project.run_command.assert_any_call(
        [venv_python, script_path],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    mock_system_project.run_command.assert_any_call(
        pip_check_cmd, cwd=project_path, capture_output=True, text=True, check=False
    )
    mock_system_project.remove_file.assert_called_once_with(
        script_path, missing_ok=True, log_success=False
    )


def test_install_pip_with_script_get_pip_fails(mock_system_project):
    # ... (similar setup)
    mock_system_project.run_command.return_value = MagicMock(
        returncode=1, stdout="", stderr="get-pip error"
    )
    # ...
    result = _install_pip_with_script(mock_system_project, "", "", "", [])
    assert result.is_err
    assert "Failed to install pip using get-pip.py" in result.message


def test_install_pip_with_script_verify_fails(mock_system_project):
    mock_system_project.run_command.side_effect = [
        MagicMock(returncode=0),  # get-pip.py success
        MagicMock(returncode=1, stderr="pip verify error"),  # pip verify fails
    ]
    result = _install_pip_with_script(mock_system_project, "", "", "", [])
    assert result.is_err
    assert "subsequent verification failed" in result.message


# Tests for _ensure_pip_in_venv
def test_ensure_pip_in_venv_already_present(mock_system_project):
    venv_python = "/abs/myproject/.venv/bin/python"
    project_path = "/abs/myproject"
    mock_system_project.run_command.return_value = MagicMock(
        returncode=0, stdout="pip 20.0"
    )  # pip check success

    result = _ensure_pip_in_venv(mock_system_project, project_path, venv_python)
    assert result.is_ok
    mock_system_project.download_file.assert_not_called()  # Should not download get-pip


def test_ensure_pip_in_venv_install_success(mock_system_project):
    venv_python = "/abs/myproject/.venv/bin/python"
    project_path = "/abs/myproject"

    # Simulate pip check fails, then download and install pip succeed
    mock_system_project.run_command.side_effect = [
        MagicMock(returncode=1, stderr="pip not found"),  # pip check fails
        MagicMock(returncode=0, stdout="pip installed by script"),  # get-pip.py success
        MagicMock(returncode=0, stdout="pip 20.0 verified"),  # pip verify success
    ]
    mock_system_project.download_file.return_value = SystemOperationResult.Ok(
        "/abs/myproject/get-pip.py"
    )
    mock_system_project.remove_file.return_value = SystemOperationResult.Ok()

    result = _ensure_pip_in_venv(mock_system_project, project_path, venv_python)
    assert result.is_ok
    mock_system_project.download_file.assert_called_once()


# Tests for _initialize_git_repo
def test_initialize_git_repo_success(mock_system_project):
    project_path = "/abs/myproject"
    venv_name = ".venv"
    mock_system_project.change_cwd.return_value = SystemOperationResult.Ok()
    mock_system_project.run_command.return_value = MagicMock(
        returncode=0, stdout="git init success"
    )  # git init
    mock_system_project.read_package_asset.return_value = SystemOperationResult.Ok(
        "venv_name: {{ venv_name }}"
    )
    mock_system_project.write_file.return_value = SystemOperationResult.Ok()

    result = _initialize_git_repo(mock_system_project, project_path, venv_name)

    assert result.is_ok
    mock_system_project.change_cwd.assert_any_call(project_path)  # Change to project
    mock_system_project.change_cwd.assert_any_call("/current/workdir")  # Change back
    mock_system_project.run_command.assert_called_once_with(
        ["git", "init"], capture_output=True, text=True, check=False
    )
    mock_system_project.write_file.assert_called_once_with(
        os.path.join(project_path, ".gitignore"), "venv_name: .venv"
    )


def test_initialize_git_repo_git_init_fails(mock_system_project):
    mock_system_project.change_cwd.return_value = SystemOperationResult.Ok()
    mock_system_project.run_command.return_value = MagicMock(
        returncode=1, stderr="git init error"
    )

    result = _initialize_git_repo(mock_system_project, "/abs/myproject", ".venv")
    assert result.is_err
    assert "git init error" in result.message


# Tests for _create_virtual_environment
@patch("vscode_colab.environment.project_setup._determine_venv_python_executable")
@patch("vscode_colab.environment.project_setup._ensure_pip_in_venv")
def test_create_virtual_environment_success(
    mock_ensure_pip, mock_determine_exe, mock_system_project
):
    project_path = "/abs/myproject"
    python_exe = "python3.9"  # Base python for venv creation
    venv_name = ".myenv"

    mock_system_project.which.return_value = (
        f"/usr/bin/{python_exe}"  # Base python exists
    )
    mock_system_project.run_command.return_value = MagicMock(
        returncode=0, stdout="venv created"
    )  # venv creation
    mock_determine_exe.return_value = f"{project_path}/{venv_name}/bin/python"
    mock_ensure_pip.return_value = SystemOperationResult.Ok()

    result = _create_virtual_environment(
        mock_system_project, project_path, python_exe, venv_name
    )

    assert result.is_ok
    assert result.value == f"{project_path}/{venv_name}/bin/python"
    mock_system_project.run_command.assert_called_once_with(
        [f"/usr/bin/{python_exe}", "-m", "venv", venv_name],
        capture_output=True,
        text=True,
        cwd=project_path,
        check=False,
    )
    mock_determine_exe.assert_called_once()
    mock_ensure_pip.assert_called_once()


def test_create_virtual_environment_base_python_not_found(mock_system_project):
    mock_system_project.which.return_value = None  # Base python not found
    result = _create_virtual_environment(mock_system_project, "", "nonexistentpy", "")
    assert result.is_err
    assert "Base Python executable 'nonexistentpy' not found" in result.message


# Tests for setup_project_directory (main function)
@patch("vscode_colab.environment.project_setup._initialize_git_repo")
@patch("vscode_colab.environment.project_setup._create_virtual_environment")
def test_setup_project_directory_new_project_success(
    mock_create_venv, mock_init_git, mock_system_project
):
    project_name = "new_proj"
    base_path = "/tmp"  # So abs_base_path = /tmp
    abs_project_path = (
        f"{base_path}/{project_name}"  # mock_system_project.get_absolute_path behavior
    )

    mock_system_project.path_exists.return_value = False  # Project does not exist
    mock_system_project.make_dirs.return_value = SystemOperationResult.Ok()
    mock_init_git.return_value = SystemOperationResult.Ok()
    mock_create_venv.return_value = SystemOperationResult.Ok(
        f"{abs_project_path}/.venv/bin/python"
    )

    # Mock get_absolute_path specifically for this test case flow
    def get_abs_path_side_effect(p):
        if p == base_path:
            return base_path  # Already absolute
        if p == os.path.join(base_path, project_name):
            return abs_project_path
        return f"/abs/{p}"  # Default mock

    mock_system_project.get_absolute_path.side_effect = get_abs_path_side_effect

    result = setup_project_directory(
        mock_system_project, project_name, base_path=base_path
    )

    assert result.is_ok
    assert result.value == abs_project_path
    mock_system_project.make_dirs.assert_called_once_with(abs_project_path)
    mock_init_git.assert_called_once_with(
        mock_system_project, abs_project_path, ".venv"
    )
    mock_create_venv.assert_called_once_with(
        mock_system_project, abs_project_path, "python3", ".venv"
    )


def test_setup_project_directory_already_exists(mock_system_project):
    project_name = "existing_proj"
    abs_project_path = f"/tmp/{project_name}"
    mock_system_project.get_absolute_path.return_value = abs_project_path
    mock_system_project.path_exists.return_value = True  # Project exists

    result = setup_project_directory(
        mock_system_project, project_name, base_path="/tmp"
    )

    assert result.is_ok
    assert result.value == abs_project_path
    mock_system_project.make_dirs.assert_not_called()


def test_setup_project_directory_creation_fails(mock_system_project):
    mock_system_project.path_exists.return_value = False
    mock_system_project.make_dirs.return_value = SystemOperationResult.Err(
        OSError("Cannot create")
    )

    result = setup_project_directory(mock_system_project, "fail_proj")
    assert result.is_err
    assert "Failed to create project directory" in result.message


@patch("vscode_colab.environment.project_setup._initialize_git_repo")
@patch("vscode_colab.environment.project_setup._create_virtual_environment")
def test_setup_project_directory_venv_fails(
    mock_create_venv, mock_init_git, mock_system_project
):
    mock_system_project.path_exists.return_value = False
    mock_system_project.make_dirs.return_value = SystemOperationResult.Ok()
    mock_init_git.return_value = SystemOperationResult.Ok()
    mock_create_venv.return_value = SystemOperationResult.Err(Exception("Venv boom"))

    result = setup_project_directory(mock_system_project, "proj_no_venv")
    assert result.is_err  # Venv failure is critical
    assert "Virtual environment setup failed" in result.message
