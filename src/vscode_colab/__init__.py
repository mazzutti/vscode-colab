"""
Initialization of the vscode_colab package.

This package provides functionality to set up a VS Code server in Google Colab.
"""

from .server import setup_vscode_server

__all__ = [
    "setup_vscode_server",
]
