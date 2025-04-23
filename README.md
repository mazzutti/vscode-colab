# vscode-colab: Connect VS Code to Google Colab and Kaggle Runtimes

[![PyPI version](https://img.shields.io/pypi/v/vscode-colab.svg)](https://pypi.org/project/vscode-colab/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/pypi/pyversions/vscode-colab.svg)](https://pypi.org/project/vscode-colab/)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/EssenceSentry/vscode-colab/blob/main/examples/simple_usage.ipynb)

![Logo](images/vscode_colab.png)

**vscode-colab** is a Python library that enables you to connect your Google Colab or Kaggle notebooks to your local Visual Studio Code (VS Code) editor using [VS Code Remote Tunnels](https://code.visualstudio.com/docs/remote/tunnels). This integration allows you to leverage the full capabilities of VS Code while utilizing the computational resources of cloud-based notebooks.

## 🚀 Features

- Seamless connection between Colab/Kaggle notebooks and local VS Code editor.
- Utilizes official VS Code Remote Tunnels for secure and efficient connectivity.
- Minimal setup with intuitive `login()` and `connect()` functions.
- Interactive UI elements within notebooks for enhanced user experience.

## 🧰 Installation

Install the package via pip:

```shell
pip install vscode-colab
```

## 📖 Usage

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/EssenceSentry/vscode-colab/blob/main/examples/simple_usage.ipynb)

### 1. Import the Library

In your Colab or Kaggle notebook, import the `vscode_colab` module:

```python
import vscode_colab
```

### 2. Authenticate with VS Code

Run the `login()` function to authenticate your session:

```python
vscode_colab.login()
```

![Login](images/login.png)

This will display a code and a URL. Click the URL, enter the code, and sign in with your GitHub or Microsoft account to authorize the connection.

### 3. Establish the Tunnel

After successful authentication, initiate the tunnel:

```python
vscode_colab.connect()
```

![Login](images/connect.png)

This will start the VS Code tunnel, allowing you to connect your local VS Code editor to the Colab/Kaggle environment.

### 4. Connect via VS Code

In your local VS Code editor:

1. Open the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`).
2. Select `Remote Tunnels: Connect to Tunnel...`.
3. Choose the tunnel corresponding to your notebook session.

You are now connected to your Colab/Kaggle environment through VS Code!

## ⚠️ Notes

- The `connect()` function will block the notebook cell execution as it maintains the tunnel connection. To terminate the tunnel, you can:
  - Interrupt the cell execution.
  - Close the notebook tab.
  - Shut down the notebook runtime.
- Ensure that your local VS Code editor has the [Remote Tunnels extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode.remote-server) installed.

## 🧪 Testing

To run the test suite:

```bash
git clone https://github.com/EssenceSentry/vscode-colab.git
cd vscode-colab
pip install -r requirements-dev.txt
pytest
```

## 🛠️ Development

The project uses `setup.cfg` for configuration and `requirements-dev.txt` for development dependencies. Contributions are welcome!

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/EssenceSentry/vscode-colab/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

Special thanks to the developers of [VS Code Remote Tunnels](https://code.visualstudio.com/docs/remote/tunnels) for enabling seamless remote development experiences.
