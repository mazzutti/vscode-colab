# vscode-colab

## Overview

The `vscode-colab` library allows users to set up a Visual Studio Code server within Google Colab. This enables a powerful coding environment directly in your browser, leveraging the capabilities of VS Code while utilizing the resources of Google Colab.

## Features

- Easy setup of a VS Code server in Google Colab.
- Support for essential Python development extensions.
- User-friendly authentication and connection options.

## Installation

To use the `vscode-colab` library, you can clone the repository and install the required dependencies. Here’s how to do it:

```bash
git clone https://github.com/yourusername/vscode-colab.git
cd vscode-colab
pip install -e .
```

## Usage

To set up the VS Code server in Google Colab, simply import the library and call the `setup_vscode_server()` function:

```python
from vscode_colab import setup_vscode_server

# Start the VS Code server
setup_vscode_server()
```

Follow the on-screen instructions for authentication and connection.

## Examples

Check out the `examples/simple_usage.ipynb` notebook for a detailed example of how to use the `vscode-colab` library in Google Colab.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.