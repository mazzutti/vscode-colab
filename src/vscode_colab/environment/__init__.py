# This file makes the 'environment' directory a Python package.
from vscode_colab.git_handler import configure_git
from vscode_colab.project_setup import setup_project_directory
from vscode_colab.python_env import PythonEnvManager

__all__ = [
    "configure_git",
    "setup_project_directory",
    "PythonEnvManager",
]
