import logging
import os
import re
import subprocess
import time
from typing import List, Optional

from IPython.display import HTML, display

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def download_vscode_cli(force_download: bool = False) -> bool:
    """
    Downloads and extracts the Visual Studio Code CLI if it does not already exist in the current directory.

    Args:
        force_download (bool): If True, forces re-download and extraction even if the CLI already exists.

    Returns:
        bool: True if the CLI is successfully downloaded and extracted or already exists, False otherwise.

    Side Effects:
        - Downloads the VS Code CLI tarball using curl.
        - Extracts the tarball using tar.
        - Prints error messages to stdout if download or extraction fails.
    """
    if os.path.exists("./code") and not force_download:
        return True
    try:
        subprocess.run(
            "curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output 'vscode_cli.tar.gz'",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            "tar -xf vscode_cli.tar.gz",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not os.path.exists("./code"):
            logging.error("Failed to extract VS Code CLI properly.")
            return False
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during VS Code download or extraction: {e}")
        return False


def define_extensions(extensions: Optional[List[str]] = None) -> List[str]:
    if extensions is None:
        return [
            "mgesbert.python-path",
            "ms-python.black-formatter",
            "ms-python.isort",
            "ms-python.python",
            "ms-python.vscode-pylance",
            "ms-python.debugpy",
            "ms-toolsai.jupyter",
            "ms-toolsai.jupyter-keymap",
            "ms-toolsai.jupyter-renderers",
            "ms-toolsai.tensorboard",
        ]
    return extensions


def display_github_auth_link(url: str, code: str) -> None:
    html = f"""
        <div
        style="padding: 15px; background-color: #f0f7ff; border-radius: 8px; margin: 15px 0; font-family: Arial, sans-serif; border: 1px solid #c8e1ff;">
        <h3 style="margin-top: 0; color: #0366d6; font-size: 18px;">GitHub Authentication Required</h3>
        <p style="margin-bottom: 15px;">Please authenticate by clicking the link below and entering the code:</p>
        <div style="display: flex; align-items: center; margin-bottom: 10px; flex-wrap: wrap;">
            <a href="{url}" target="_blank"
                style="background-color: #2ea44f; color: white; padding: 10px 16px; text-decoration: none; border-radius: 6px; margin-right: 15px; margin-bottom: 10px; font-weight: 500;">
                Open GitHub Authentication
            </a>
            <div
                style="background-color: #ffffff; border: 1px solid #d1d5da; border-radius: 6px; padding: 10px 16px; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; position: relative; display: flex; align-items: center; margin-bottom: 10px;">
                <span id="auth-code" style="margin-right: 15px; font-size: 16px;">{code}</span>
                <button id="copyButton" onclick="copyAuthCode()"
                    style="background-color: #f6f8fa; border: 1px solid #d1d5da; border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 14px;">
                    Copy
                </button>
            </div>
        </div>
        <script>
            function copyAuthCode() {{
                const code = "{code}";
                const copyButton = document.getElementById('copyButton');
                
                navigator.clipboard.writeText(code).then(() => {{
                    copyButton.textContent = 'Copied!';
                    copyButton.style.backgroundColor = '#dff0d8';
                    copyButton.style.borderColor = '#d6e9c6';
                    copyButton.style.color = '#3c763d';
                    
                    setTimeout(() => {{
                        copyButton.textContent = 'Copy';
                        copyButton.style.backgroundColor = '#f6f8fa';
                        copyButton.style.borderColor = '#d1d5da';
                        copyButton.style.color = '';
                    }}, 2000);
                }});
            }}
        </script>
    </div>
    """
    display(HTML(html))


def display_vscode_connection_options(
    tunnel_url: str,
    tunnel_name: str,
) -> None:
    html = f"""
        <div
            style="padding:15px; background:#f5f9ff; border-radius:8px; margin:15px 0; font-family:Arial,sans-serif; border:1px solid #c8e1ff;">
            <h3 style="margin:0 0 10px; color:#0366d6;">✅ VS Code Server Ready!</h3>

            <a href="{tunnel_url}" target="_blank"
                style="background:#0366d6;color:white;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:500;display:inline-block;">Open
                VS Code in Browser</a>

            <hr style="margin:15px 0;" />
            <p><strong>Connect from desktop VS Code:</strong></p>
            <ol>
                <li>Sign in with the same GitHub account in VS Code.</li>
                <li>Open the Remote Explorer (<kbd>Ctrl+Shift+P</kbd>, type "Remote Explorer").</li>
                <li>Select "{tunnel_name}" under "Tunnels" and connect.</li>
            </ol>
        </div>
    """
    display(HTML(html))


def login(provider: str = "github") -> bool:
    """
    Attempts to log in to VS Code Tunnel using the specified authentication provider.

    This function ensures the VS Code CLI is available, then initiates the login process
    using the CLI with the given provider (default is "github"). It monitors the CLI output
    for a login URL and code, and displays them for user authentication. If successful,
    returns True; otherwise, prints an error message and returns False.

    Args:
        provider (str): The authentication provider to use for login (default: "github").

    Returns:
        bool: True if the login URL and code were detected and displayed, False otherwise.
    """
    if not download_vscode_cli():
        logging.error("VS Code CLI not available, cannot perform login.")
        return False

    cmd = f"./code tunnel user login --provider {provider}"
    try:
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        if proc.stdout is None:
            logging.error("Failed to get login process stdout.")
            proc.terminate()
            return False

        url_re = re.compile(r"https?://[^\s]+")
        code_re = re.compile(r"[A-Z0-9]{4}-[A-Z0-9]{4,}")

        start = time.time()
        while proc.poll() is None and time.time() - start < 60:
            line = proc.stdout.readline()
            if line:
                um = url_re.search(line)
                cm = code_re.search(line)
                if um and cm:
                    display_github_auth_link(um.group(0), cm.group(0))
                    return True  # Found URL and code

        # If loop finishes without finding URL/code
        if proc.poll() is None:  # Process still running, but timeout reached
            logging.warning(
                "Couldn't detect login URL and code within the timeout period."
            )
            proc.terminate()  # Clean up the process
        else:  # Process ended before URL/code was detected
            logging.warning(
                "Login process ended unexpectedly before URL/code could be detected."
            )
            # Optionally read remaining output
            if proc.stdout:
                remaining_output = proc.stdout.read()
                if remaining_output:
                    logging.debug("Login process output:\n%s", remaining_output)

        return False  # URL/code not found

    except Exception as e:
        logging.error(f"Error during login: {e}")
        # Ensure process is cleaned up if it exists and an exception occurred
        if "proc" in locals() and proc.poll() is None:
            proc.terminate()
        return False


def connect(
    tunnel_name: str = "colab",
    extensions: Optional[List[str]] = None,
) -> Optional[subprocess.Popen]:
    """
    Establishes a VS Code tunnel connection using the VS Code CLI.

    This function attempts to start a VS Code tunnel with the specified tunnel name and optional extensions.
    It ensures the VS Code CLI is available, installs the requested extensions, and launches the tunnel.
    If successful, it detects and displays the tunnel URL for remote access.

    Args:
        tunnel_name (str): The name to assign to the tunnel. Defaults to "colab".
        extensions (list or None): A list of VS Code extension identifiers to install before starting the tunnel.

    Returns:
        subprocess.Popen or None: The process object for the running tunnel if the URL was detected successfully,
                                  or None if an error occurred, the CLI is unavailable, or the URL wasn't found in time.
    """
    if not download_vscode_cli():
        logging.error("VS Code CLI not available, cannot start tunnel.")
        return None

    exts = define_extensions(extensions)
    ext_args = " ".join(f"--install-extension {e}" for e in exts)
    cmd = f"./code tunnel --accept-server-license-terms --name {tunnel_name} {ext_args}"

    try:
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        # Make sure stdout is available
        if proc.stdout is None:
            logging.error("Failed to get tunnel process stdout.")
            proc.terminate()  # Clean up the process
            return None

        url_re = re.compile(r"https://vscode\.dev/tunnel/[\w-]+/[\w-]+")
        start = time.time()
        timeout_seconds = 60
        while proc.poll() is None and time.time() - start < timeout_seconds:
            line = proc.stdout.readline()
            if line:
                logging.debug(line.strip())  # Log tunnel output line
                m = url_re.search(line)
                if m:
                    display_vscode_connection_options(m.group(0), tunnel_name)
                    return proc  # Return process only if URL is found

        # If loop finishes without finding URL (timeout or process ended)
        if proc.poll() is None:  # Process still running, but timeout reached
            logging.error(f"Tunnel URL not detected within {timeout_seconds} seconds.")
            proc.terminate()  # Clean up the process
            return None
        else:  # Process ended before URL was detected
            logging.error(
                "Tunnel process exited unexpectedly before URL could be detected."
            )
            remaining_output = proc.stdout.read()
            if remaining_output:
                logging.debug(
                    "Tunnel output:\n%s", remaining_output
                )  # Log remaining output as debug
            return None

    except Exception as e:
        logging.error(f"Error starting tunnel: {e}")
        # Ensure process is cleaned up if it exists and an exception occurred
        if "proc" in locals() and proc.poll() is None:
            proc.terminate()
        return None
