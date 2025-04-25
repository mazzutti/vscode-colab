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

DEFAULT_EXTENSIONS = {
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
}


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


def display_github_auth_link(
    url: str,
    code: str,
) -> None:
    """
    Displays an HTML block in IPython with the GitHub authentication link and code.
    Dynamically adds a copy button only if clipboard access is likely available,
    and ensures the code text is visible. Simplifies copy feedback.

    Args:
        url (str): The GitHub device authentication URL.
        code (str): The user code to enter on GitHub.
    """
    # Ensure the code string is properly escaped for use in JavaScript strings
    # Escape backslashes first, then double quotes
    escaped_code = code.replace("\\", "\\\\").replace('"', '\\"')

    html = f"""
    <div style="padding: 15px; background-color: #f0f7ff; border-radius: 8px; margin: 15px 0; font-family: Arial, sans-serif; border: 1px solid #c8e1ff; line-height: 1.6;">
        <h3 style="margin-top: 0; color: #0366d6; font-size: 18px;">GitHub Authentication Required</h3>
        <p style="margin-bottom: 15px; color: #333333;">Please open the link below in a new tab and enter the following code:</p>
        <div style="display: flex; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 15px;">
            <a href="{url}" target="_blank"
                style="background-color: #2ea44f; color: white; padding: 10px 16px; text-decoration: none; border-radius: 6px; font-weight: 500; white-space: nowrap;">
                Open GitHub Authentication Page
            </a>
            <div id="code-container" style="background-color: #ffffff; border: 1px solid #d1d5da; border-radius: 6px; padding: 10px 16px; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; display: flex; align-items: center;">
                <span id="auth-code" style="margin-right: 15px; font-size: 16px; user-select: all; color: #24292e;">{code}</span>
            </div>
        </div>
        <p id="copy-fallback-note" style="font-size: small; color: #586069; margin-top: 10px; display: none;">
            Please select the code manually and copy it.
        </p>

        <script>
            (function() {{
                const code = "{escaped_code}";
                const codeContainer = document.getElementById('code-container');
                const fallbackNote = document.getElementById('copy-fallback-note');

                // Function to attempt copying
                function attemptCopy() {{
                    const copyButton = document.getElementById('dynamicCopyButton');
                    if (!copyButton) return;

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
                        }}, 2500);

                    }}).catch(err => {{
                        console.error('Failed to copy code automatically: ', err);
                        copyButton.textContent = 'Copy Failed';
                        copyButton.disabled = true;
                        copyButton.style.backgroundColor = '#f2dede';
                        copyButton.style.borderColor = '#ebccd1';
                        copyButton.style.color = '#a94442';
                        fallbackNote.style.display = 'block';
                    }});
                }}

                // Check if Clipboard API is available and likely usable
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    // Create and add the button dynamically
                    const button = document.createElement('button');
                    button.id = 'dynamicCopyButton';
                    button.textContent = 'Copy';
                    button.style.backgroundColor = '#f6f8fa';
                    button.style.border = '1px solid #d1d5da';
                    button.style.borderRadius = '6px';
                    button.style.padding = '6px 12px';
                    button.style.cursor = 'pointer';
                    button.style.fontSize = '14px';
                    button.style.whiteSpace = 'nowrap';
                    button.style.marginLeft = '10px'; // Add some space if button appears
                    button.onclick = attemptCopy; // Assign the copy function

                    // Append the button to the container
                    codeContainer.appendChild(button);

                }} else {{
                    // Clipboard API not available, ensure fallback note is visible
                    fallbackNote.style.display = 'block';
                }}
            }})();
        </script>
    </div>
    """
    display(HTML(html))


def display_vscode_connection_options(
    tunnel_url: str,
    tunnel_name: str,
) -> None:
    text_color = "#333333"
    html = f"""
    <div style="padding:15px; background:#f0f9f0; border-radius:8px; margin:15px 0; font-family:Arial,sans-serif; border:1px solid #c8e6c9; line-height: 1.6;">
        <h3 style="margin:0 0 15px; color:#2e7d32; font-size: 18px;">✅ VS Code Tunnel Ready!</h3>

        <p style="margin-bottom: 15px; color: {text_color};">You can connect in two ways:</p>

        <div style="margin-bottom: 15px;">
            <strong style="color: {text_color};">1. Open in Browser:</strong><br>
            <a href="{tunnel_url}" target="_blank"
                style="background-color:#1976d2; color:white; padding:10px 16px; border-radius:6px; text-decoration:none; font-weight:500; display:inline-block; margin-top: 5px;">
                Open VS Code Web
            </a>
        </div>

        <hr style="border: 0; border-top: 1px solid #c8e6c9; margin: 20px 0;" />

        <div style="margin-bottom: 10px; color: {text_color};">
            <strong style="color: {text_color};">2. Connect from Desktop VS Code:</strong>
            <ol style="margin-top: 5px; padding-left: 20px; color: {text_color};">
                <li>Make sure you have the <a href="https://marketplace.visualstudio.com/items?itemName=ms-vscode.remote-server" target="_blank" style="color: #1976d2;">Remote Tunnels</a> extension installed.</li>
                <li>Ensure you are signed in to VS Code with the <strong>same GitHub account</strong> used for authentication.</li>
                <li>Open the Command Palette (<kbd style="background: #e0e0e0; color: #333; padding: 2px 4px; border-radius: 3px; border: 1px solid #ccc; font-family: monospace;">Ctrl+Shift+P</kbd> or <kbd style="background: #e0e0e0; color: #333; padding: 2px 4px; border-radius: 3px; border: 1px solid #ccc; font-family: monospace;">Cmd+Shift+P</kbd>).</li>
                <li>Run the command: <code style="background: #e0e0e0; color: #333; padding: 2px 5px; border-radius: 3px;">Remote Tunnels: Connect to Tunnel</code></li>
                <li>Select the tunnel named "<strong style="color: {text_color};">{tunnel_name}</strong>" from the list.</li>
            </ol>
        </div>
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


def configure_git(
    git_user_name: Optional[str] = None,
    git_user_email: Optional[str] = None,
):
    """
    Configures global Git user name and email using the provided values.

    Both `git_user_name` and `git_user_email` must be provided together, or neither should be provided.
    If only one is provided, configuration is skipped and a warning is logged.

    Attempts to set the global Git configuration for user.name and user.email
    using the `git config --global` command. Logs the outcome of each operation,
    including any errors encountered (such as missing git command or subprocess errors).
    If configuration fails, a warning is logged to indicate that manual setup may be required.

    Args:
        git_user_name (Optional[str]): The Git user name to set globally. Must be provided with git_user_email.
        git_user_email (Optional[str]): The Git user email to set globally. Must be provided with git_user_name.

    Logs:
        - Info messages for attempted and successful configuration.
        - Warning messages for failures, missing git command, or incomplete parameters.
        - Error messages for unexpected exceptions.
    """
    if (git_user_name and not git_user_email) or (git_user_email and not git_user_name):
        logging.warning(
            "Both git_user_name and git_user_email must be provided together. Skipping git configuration."
        )
        return

    if not git_user_name and not git_user_email:
        return  # Nothing to configure

    git_configured = True  # Assume success unless proven otherwise
    try:
        logging.info(
            f"Attempting to set git global user.name='{git_user_name}' and user.email='{git_user_email}'..."
        )
        subprocess.run(
            ["git", "config", "--global", "user.name", git_user_name],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "--global", "user.email", git_user_email],
            check=True,
            capture_output=True,
            text=True,
        )
        logging.info("Successfully set git global user.name and user.email.")
    except FileNotFoundError:
        logging.warning(
            "git command not found. Cannot configure git user.name and user.email."
        )
        git_configured = False
    except subprocess.CalledProcessError as e:
        logging.warning(
            f"Failed to set git user.name or user.email. Error: {e.stderr.strip()}"
        )
        git_configured = False
    except Exception as e:
        logging.error(f"Unexpected error setting git user.name or user.email: {e}")
        git_configured = False

    if not git_configured:
        logging.warning("Git configuration failed. Commits might require manual setup.")


def connect(
    name: str = "colab",
    include_default_extensions: bool = True,
    extensions: Optional[List[str]] = None,
    git_user_name: Optional[str] = None,
    git_user_email: Optional[str] = None,
) -> Optional[subprocess.Popen]:
    """
    Establishes a VS Code tunnel connection using the VS Code CLI.

    This function attempts to start a VS Code tunnel with the specified tunnel name and optional extensions.
    It ensures the VS Code CLI is available, installs the requested extensions, and launches the tunnel.
    If successful, it detects and displays the tunnel URL for remote access.

    Args:
        name (str): The name to assign to the tunnel. Defaults to "colab".
        extensions (list or None): A list of VS Code extension identifiers to install before starting the tunnel.
        include_default_extensions (bool): Whether to include default extensions in the installation. Defaults to True. If False, only the provided extensions will be installed.
        git_user_name (str or None): The Git user name to set globally.
        git_user_email (str or None): The Git user email to set globally. Both must be provided together or the configuration is skipped with a warning.

    Returns:
        subprocess.Popen or None: The process object for the running tunnel if
        the URL was detected successfully, or None if an error occurred, the
        CLI is unavailable, or the URL wasn't found in time.
    """
    if not download_vscode_cli():
        logging.error("VS Code CLI not available, cannot start tunnel.")
        return None

    configure_git(git_user_name, git_user_email)

    exts = set(DEFAULT_EXTENSIONS) if include_default_extensions else set()
    if extensions:
        exts.update(extensions)
    ext_args = " ".join(f"--install-extension {e}" for e in sorted(exts))
    cmd = f"./code tunnel --accept-server-license-terms --name {name} {ext_args}"

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
                    display_vscode_connection_options(m.group(0), name)
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
