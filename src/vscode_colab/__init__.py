"""
Initialization of the vscode_colab package.
"""

import subprocess
from typing import List, Optional

from vscode_colab.server import DEFAULT_EXTENSIONS as server_default_extensions
from vscode_colab.server import connect as server_connect
from vscode_colab.server import login as server_login
from vscode_colab.system import System
from vscode_colab.utils import SystemOperationResult

_default_system_instance = System()


def login(provider: str = "github", system: Optional[System] = None) -> bool:
    """
    Attempts to log in to VS Code Tunnel using the specified authentication provider.
    On Linux, this involves running the 'code tunnel user login' command.

    Args:
        provider: The authentication provider to use. Typically "github".
        system: Optional System instance for dependency injection (testing).

    Returns:
        bool: True if the login process initiated successfully (auth info displayed), False otherwise.
    """
    active_system = system if system is not None else _default_system_instance
    # The server_login function handles the logic and returns a simple bool.
    return server_login(system=active_system, provider=provider)


def connect(
    name: str = "colab",
    include_default_extensions: bool = True,
    extensions: Optional[List[str]] = None,
    git_user_name: Optional[str] = None,
    git_user_email: Optional[str] = None,
    setup_python_version: Optional[str] = None,
    force_python_reinstall: bool = False,
    attempt_pyenv_dependency_install: bool = True,
    create_new_project: Optional[str] = None,
    new_project_base_path: str = ".",
    venv_name_for_project: str = ".venv",
    system: Optional[System] = None,
) -> Optional[subprocess.Popen]:
    """
    Establishes a VS Code tunnel connection on a Linux environment (e.g., Colab, Kaggle).

    Args:
        name (str): The name of the connection tunnel. Defaults to "colab".
        include_default_extensions (bool): Whether to include default extensions. Defaults to True.
        extensions (Optional[List[str]]): A list of additional VS Code extension IDs to install.
        git_user_name (Optional[str]): Git user name for global configuration.
        git_user_email (Optional[str]): Git user email for global configuration.
        setup_python_version (Optional[str]): Python version (e.g., "3.9.18") to set up using pyenv.
        force_python_reinstall (bool): If setup_python_version is provided, force reinstall it.
        attempt_pyenv_dependency_install (bool): Attempt to install pyenv OS dependencies (e.g. via apt). Requires sudo.
        create_new_project (Optional[str]): Name of a new project directory to create.
        new_project_base_path (str): Base path for the new project. Defaults to current directory ".".
        venv_name_for_project (str): Name of the virtual environment directory within the new project.
        system: Optional System instance for dependency injection (testing).

    Returns:
        Optional[subprocess.Popen]: A Popen object for the tunnel process if successful, None otherwise.
    """
    active_system = system if system is not None else _default_system_instance
    return server_connect(
        system=active_system,
        name=name,
        include_default_extensions=include_default_extensions,
        extensions=extensions,
        git_user_name=git_user_name,
        git_user_email=git_user_email,
        setup_python_version=setup_python_version,
        force_python_reinstall=force_python_reinstall,
        attempt_pyenv_dependency_install=attempt_pyenv_dependency_install,
        create_new_project=create_new_project,
        new_project_base_path=new_project_base_path,
        venv_name_for_project=venv_name_for_project,
    )


# Expose DEFAULT_EXTENSIONS as a frozenset for immutability if users import it.
DEFAULT_EXTENSIONS: frozenset[str] = frozenset(server_default_extensions)

__all__ = [
    "login",
    "connect",
    "DEFAULT_EXTENSIONS",
]
