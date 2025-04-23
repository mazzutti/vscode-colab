# vscode-colab: Connect VS Code to Google Colab Runtimes

[![PyPI version](https://img.shields.io/pypi/v/vscode-colab.svg)](https://pypi.org/project/vscode-colab/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/pypi/pyversions/vscode-colab.svg)](https://pypi.org/project/vscode-colab/)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/EssenceSentry/vscode-colab/blob/main/examples/simple_usage.ipynb)

`vscode-colab` is a Python library designed to facilitate the connection of a Visual Studio Code instance (desktop or web-based) to a remote runtime environment, specifically Google Colab or Kaggle notebooks.

It automates the setup of a secure tunnel, enabling users to leverage the features of VS Code while utilizing the computational resources provided by these cloud platforms.

## Key Features & Advantages

### Official VS Code Tunnels

Establishes the connection using the official `code tunnel` feature from VS Code. This provides a secure, end-to-end encrypted tunnel managed via Microsoft's infrastructure.
  
### Simplified Setup

The `login` and `connect()` functions streamlines the process by:
  
* Downloading the required VS Code CLI tool.
* Initiating the `code tunnel` process.
* Parsing and displaying GitHub device authentication prompts within the notebook for user action.
* Automatically installing a default set of useful Python development extensions (e.g., Python language support, Pylance, Black formatter, isort, Jupyter tools).
* Detecting and displaying the connection URL (`vscode.dev`) and desktop connection instructions.

### Flexible Connectivity

Supports connecting to the remote runtime via:

* The web-based VS Code editor at `vscode.dev`.
* A locally installed VS Code desktop application through the "Remote - Tunnels" extension.

## Installation

Install the library using pip:

```bash
pip install vscode-colab
```

## Usage

<a target="_blank" href="https://colab.research.google.com/github/EssenceSentry/vscode-colab/blob/main/examples/simple_usage.ipynb">
  <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>
</a>

To set up the VS Code server in Google Colab, simply import the library and call the `login()` and then `connect()`:

```python
from vscode_colab import login, connect

# Start the VS Code server
login()
```

![Login](images/login.png)

```python
connect()
```

![Login](images/connect.png)

Follow the on-screen instructions for authentication and connection.

Check out the `examples/simple_usage.ipynb` notebook for a detailed example of how to use the `vscode-colab` library in Google Colab.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
