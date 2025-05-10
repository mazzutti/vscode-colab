"""
Initialization of the vscode_colab package.
"""

import subprocess
from typing import List, Optional

from vscode_colab.server import DEFAULT_EXTENSIONS as server_default_extensions
from vscode_colab.server import connect as server_connect
from vscode_colab.server import login as server_login
from vscode_colab.system import System

_default_system_instance = System()


def login(provider: str = "github", system: Optional[System] = None) -> bool:
    """
    Attempts to log in to VS Code Tunnel using the specified authentication provider.

    Args:
        provider: The authentication provider to use. Only "github" is supported.

    Returns:
        bool: True if the login was successful, False otherwise.
    """
    active_system = system if system else _default_system_instance
    return server_login(provider=provider, system=active_system)


def connect(
    name: str = "colab",
    include_default_extensions: bool = True,
    extensions: Optional[List[str]] = None,
    git_user_name: Optional[str] = None,
    git_user_email: Optional[str] = None,
    setup_python_version: Optional[str] = None,
    force_python_reinstall: bool = False,
    update_pyenv_before_install: bool = True,
    create_new_project: Optional[str] = None,
    new_project_base_path: str = ".",
    venv_name_for_project: str = ".venv",
    system: Optional[System] = None,
) -> Optional[subprocess.Popen]:
    """
    Establishes a connection to a Colab-like server environment with optional configurations.

    Args:
        name (str): The name of the connection. Defaults to "colab".
        include_default_extensions (bool): Whether to include default extensions. Defaults to True.
        extensions (Optional[List[str]]): A list of additional extensions to include. Defaults to None.
        git_user_name (Optional[str]): The Git user name to configure. Defaults to None.
        git_user_email (Optional[str]): The Git user email to configure. Defaults to None.
        setup_python_version (Optional[str]): The Python version to set up. Defaults to None.
        force_python_reinstall (bool): Whether to force reinstall Python. Defaults to False.
        update_pyenv_before_install (bool): Whether to update pyenv before installing Python. Defaults to True.
        create_new_project (Optional[str]): The name of a new project to create. Defaults to None.
        new_project_base_path (str): The base path for the new project. Defaults to ".".
        venv_name_for_project (str): The name of the virtual environment for the project. Defaults to ".venv".

    Returns:
        Optional[subprocess.Popen]: A subprocess.Popen object representing the server connection, or None if the connection could not be established.
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
        create_new_project=create_new_project,
        new_project_base_path=new_project_base_path,
        venv_name_for_project=venv_name_for_project,
    )


# Expose DEFAULT_EXTENSIONS as a frozenset for immutability if users import it.
DEFAULT_EXTENSIONS: frozenset[str] = frozenset(server_default_extensions)

__all__ = [
    "login",
    "connect",
    "System",
    "DEFAULT_EXTENSIONS",
]
