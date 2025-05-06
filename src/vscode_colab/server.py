import os
import re
import subprocess
import time
from typing import List, Optional

from IPython.display import HTML, display

from vscode_colab.logger_config import log as logger
from vscode_colab.setup_env import (
    configure_git,
    setup_project_directory,
    setup_pyenv_and_python_version,
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
    Downloads and extracts the Visual Studio Code CLI if it does not already exist.
    (Content of this function remains the same as in the original file)
    """
    if os.path.exists("./code") and not force_download:
        logger.info("VS Code CLI already exists. Skipping download.")
        return True
    logger.info("Downloading VS Code CLI...")
    try:
        subprocess.run(
            "curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output 'vscode_cli.tar.gz'",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        logger.info("VS Code CLI tarball downloaded. Extracting...")
        subprocess.run(
            "tar -xf vscode_cli.tar.gz",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not os.path.exists("./code"):
            logger.error(
                "Failed to extract VS Code CLI properly. './code' directory not found after extraction."
            )
            return False
        logger.info("VS Code CLI extracted successfully to './code'.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during VS Code download or extraction: {e}")
        if e.stdout:
            logger.error(f"Stdout: {e.stdout.decode(errors='ignore')}")
        if e.stderr:
            logger.error(f"Stderr: {e.stderr.decode(errors='ignore')}")
        return False
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during VS Code CLI download/extraction: {e}"
        )
        return False


def display_github_auth_link(
    url: str,
    code: str,
) -> None:
    """
    Displays an HTML block in IPython with the GitHub authentication link and code.
    (Content of this function remains the same as in the original file)
    """
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
                function attemptCopy() {{
                    const copyButton = document.getElementById('dynamicCopyButton');
                    if (!copyButton) return;
                    navigator.clipboard.writeText(code).then(() => {{
                        copyButton.textContent = 'Copied!';
                        copyButton.style.backgroundColor = '#dff0d8'; copyButton.style.borderColor = '#d6e9c6'; copyButton.style.color = '#3c763d';
                        setTimeout(() => {{
                            copyButton.textContent = 'Copy';
                            copyButton.style.backgroundColor = '#f6f8fa'; copyButton.style.borderColor = '#d1d5da'; copyButton.style.color = '';
                        }}, 2500);
                    }}).catch(err => {{
                        console.error('Failed to copy code automatically: ', err);
                        copyButton.textContent = 'Copy Failed'; copyButton.disabled = true;
                        copyButton.style.backgroundColor = '#f2dede'; copyButton.style.borderColor = '#ebccd1'; copyButton.style.color = '#a94442';
                        fallbackNote.style.display = 'block';
                    }});
                }}
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    const button = document.createElement('button');
                    button.id = 'dynamicCopyButton'; button.textContent = 'Copy';
                    button.style.backgroundColor = '#f6f8fa'; button.style.border = '1px solid #d1d5da';
                    button.style.borderRadius = '6px'; button.style.padding = '6px 12px';
                    button.style.cursor = 'pointer'; button.style.fontSize = '14px';
                    button.style.whiteSpace = 'nowrap'; button.style.marginLeft = '10px';
                    button.onclick = attemptCopy;
                    codeContainer.appendChild(button);
                }} else {{
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
    """
    Displays an HTML block in IPython with VS Code connection options.
    (Content of this function remains the same as in the original file)
    """
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
    (Content of this function remains the same as in the original file)
    """
    if not download_vscode_cli():
        logger.error("VS Code CLI not available, cannot perform login.")
        return False

    cmd = f"./code tunnel user login --provider {provider}"
    logger.info(f"Initiating VS Code Tunnel login with command: {cmd}")
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        if proc.stdout is None:
            logger.error("Failed to get login process stdout.")
            proc.terminate()
            return False

        url_re = re.compile(r"https?://[^\s]+")
        # More specific regex for GitHub device codes
        code_re = re.compile(
            r"([A-Z0-9]{4,8}-[A-Z0-9]{4,8})"
        )  # Catches codes like ABCD-1234 or longer ones

        start = time.time()
        timeout_seconds = 60
        auth_url_found = None
        auth_code_found = None

        logger.info(
            "Monitoring login process output for authentication URL and code..."
        )
        for line in iter(proc.stdout.readline, ""):
            if time.time() - start > timeout_seconds:
                logger.warning(
                    f"Login process timed out after {timeout_seconds} seconds."
                )
                proc.terminate()
                return False

            logger.debug(f"Login output: {line.strip()}")
            if not auth_url_found:
                um = url_re.search(line)
                if um and "github.com/login/device" in um.group(
                    0
                ):  # Be more specific for auth URL
                    auth_url_found = um.group(0)
                    logger.info(
                        f"Detected potential authentication URL: {auth_url_found}"
                    )

            if not auth_code_found:
                cm = code_re.search(line)
                if cm:
                    auth_code_found = cm.group(0)
                    logger.info(
                        f"Detected potential authentication code: {auth_code_found}"
                    )

            if auth_url_found and auth_code_found:
                logger.info("Authentication URL and code detected.")
                display_github_auth_link(auth_url_found, auth_code_found)
                # Don't return immediately; let the login process complete or be managed by VS Code CLI
                # The CLI process itself handles the login state.
                # We just need to display the info.
                # The original `login` function waited for the process to potentially end,
                # but for user login, the CLI keeps running until auth or timeout.
                # We assume the user will complete auth. The CLI should then confirm.
                # For now, returning True once info is displayed.
                # The CLI command `tunnel user login` should ideally exit after successful login.
                # Let's wait for a bit or for a success message if one exists.
                # For simplicity, we'll assume displaying the link is "success" for this function's purpose.
                return True  # Assuming displaying info is the goal.

            if proc.poll() is not None:  # Process ended
                break

        # If loop finishes (either by readline returning "" or process ending)
        if proc.poll() is not None:
            logger.warning("Login process ended.")

        if not (auth_url_found and auth_code_found):
            logger.error(
                "Failed to detect GitHub authentication URL and code from CLI output."
            )
            if proc.poll() is None:
                proc.terminate()  # Ensure cleanup if still running
            return False

        return True  # Should have returned earlier if both found

    except Exception as e:
        logger.error(f"Error during login: {e}")
        if "proc" in locals() and proc.poll() is None:
            proc.terminate()
        return False


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
) -> Optional[subprocess.Popen]:
    """
    Establishes a VS Code tunnel connection, with optional environment setup.

    Args:
        name (str): Name for the VS Code tunnel. Defaults to "colab".
        include_default_extensions (bool): If True, installs default Python/Jupyter extensions.
        extensions (Optional[List[str]]): List of additional VS Code extension IDs to install.
        git_user_name (Optional[str]): Git user name to configure globally.
        git_user_email (Optional[str]): Git user email to configure globally.
        setup_python_version (Optional[str]): Python version to install via pyenv (e.g., "3.9.18"). Requires environment_setup.py to be available.
        force_python_reinstall (bool): If True, forces reinstallation of the pyenv Python version.
        update_pyenv_before_install (bool): If True, updates pyenv before installing Python. Defaults to True.
        create_new_project (Optional[str]): If a name is provided, creates a new project directory with this name, initializes git, and sets up a venv. Requires environment_setup.py to be available.
        new_project_base_path (str): Base path for creating the new project. Defaults to ".".
        venv_name_for_project (str): Name of the virtual environment directory within the project. Defaults to ".venv".

    Returns:
        Optional[subprocess.Popen]: The Popen object for the tunnel process if successful, None otherwise.
    """
    if not download_vscode_cli():
        logger.error("VS Code CLI not available, cannot start tunnel.")
        return None

    configure_git(git_user_name, git_user_email)

    python_executable_for_venv = "python3"  # Default Python for creating venv
    project_path_for_tunnel_cwd = os.getcwd()  # Default CWD for tunnel

    # 1. Setup Python version with pyenv if requested
    if setup_python_version:
        logger.info(
            f"Attempting to set up Python version: {setup_python_version} using pyenv."
        )
        pyenv_python_path = setup_pyenv_and_python_version(
            python_version=setup_python_version,
            force_reinstall_python=force_python_reinstall,
            update_pyenv=update_pyenv_before_install,
        )
        if pyenv_python_path:
            python_executable_for_venv = pyenv_python_path
            logger.info(
                f"Using pyenv Python '{python_executable_for_venv}' for subsequent venv creation."
            )
        else:
            logger.warning(
                f"Failed to set up Python version {setup_python_version} with pyenv. Proceeding with default Python '{python_executable_for_venv}' for venv creation if applicable."
            )

    # 2. Create new project directory if requested
    if create_new_project:
        logger.info(
            f"Attempting to create and set up new project: '{create_new_project}' at '{new_project_base_path}'."
        )
        created_project_path = setup_project_directory(
            project_name=create_new_project,
            base_path=new_project_base_path,
            python_executable=python_executable_for_venv,
            venv_name=venv_name_for_project,
        )
        if created_project_path:
            logger.info(
                f"Successfully created project at '{created_project_path}'. Tunnel will attempt to use this directory as current working directory."
            )
            project_path_for_tunnel_cwd = created_project_path
        else:
            logger.warning(
                f"Failed to create project '{create_new_project}'. Tunnel will start in the default directory: {project_path_for_tunnel_cwd}."
            )

    exts = set(DEFAULT_EXTENSIONS) if include_default_extensions else set()
    if extensions:
        exts.update(extensions)
    ext_args = " ".join(f"--install-extension {e}" for e in sorted(list(exts)))

    # Use a list for Popen for better handling of spaces in names/paths if any
    cmd_list = ["./code", "tunnel", "--accept-server-license-terms", "--name", name]
    if ext_args:
        # Split ext_args into individual extension commands
        for ext_arg_part in ext_args.split("--install-extension"):
            ext_id = ext_arg_part.strip()
            if ext_id:
                cmd_list.extend(["--install-extension", ext_id])

    cmd_str_for_logging = " ".join(cmd_list)  # For logging purposes
    logger.info(f"Starting VS Code tunnel with command: {cmd_str_for_logging}")
    logger.info(f"Tunnel will run with CWD: {project_path_for_tunnel_cwd}")

    try:
        proc = subprocess.Popen(
            cmd_list,  # Use list of args
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True,  # For text mode
            cwd=project_path_for_tunnel_cwd,  # Set CWD for the tunnel process
        )
        if proc.stdout is None:
            logger.error("Failed to get tunnel process stdout.")
            proc.terminate()
            return None

        url_re = re.compile(r"https://vscode\.dev/tunnel/[\w-]+(?:/[\w-]+)?")
        start_time = time.time()
        timeout_seconds = 60

        logger.info("Monitoring tunnel process output for connection URL...")
        for line in iter(proc.stdout.readline, ""):
            if time.time() - start_time > timeout_seconds:
                logger.error(
                    f"Tunnel URL not detected within {timeout_seconds} seconds. Timing out."
                )
                proc.terminate()
                proc.wait()  # Wait for termination
                return None

            logger.debug(f"Tunnel output: {line.strip()}")
            m = url_re.search(line)
            if m:
                tunnel_url = m.group(0)
                logger.info(f"VS Code Tunnel URL detected: {tunnel_url}")
                display_vscode_connection_options(tunnel_url, name)
                return proc

            if proc.poll() is not None:  # Process ended prematurely
                logger.error(
                    "Tunnel process exited prematurely before URL could be detected."
                )
                remaining_output = proc.stdout.read()
                if remaining_output:
                    logger.debug(
                        f"Remaining tunnel output:\n{remaining_output.strip()}'"
                    )
                return None

        # If loop finishes because readline returned "" (EOF) and URL not found
        if proc.poll() is not None:  # Process ended
            logger.error("Tunnel process ended before URL was detected (EOF reached).")
        else:  # Should not happen if iter(..., "") is used correctly with timeout
            logger.error("Tunnel URL not detected (EOF or unknown state).")
            proc.terminate()
            proc.wait()
        return None

    except FileNotFoundError:
        logger.error(
            "VS Code CLI ('./code') not found in current directory. Cannot start tunnel."
        )
        return None
    except Exception as e:
        logger.error(f"Error starting tunnel: {e}")
        if "proc" in locals() and proc.poll() is None:
            proc.terminate()
            proc.wait()
        return None
