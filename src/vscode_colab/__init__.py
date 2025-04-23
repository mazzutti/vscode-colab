"""
Initialization of the vscode_colab package.

This package provides functionality to set up a VS Code server in Google Colab.
"""

from .server import connect, login

__all__ = [
    "login",
    "connect",
]
