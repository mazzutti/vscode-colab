import os
import re
import subprocess
import time
from typing import List, Optional, Set

from IPython.display import HTML, display

from vscode_colab.environment import (
    PythonEnvManager,
    configure_git,
    setup_project_directory,
)
from vscode_colab.logger_config import log as logger
from vscode_colab.system import System
from vscode_colab.templating import (
    render_github_auth_template,
    render_vscode_connection_template,
)

DEFAULT_EXTENSIONS: Set[str] = {
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


def download_vscode_cli(system: System, force_download: bool = False) -> bool:
    """
    Downloads and extracts the Visual Studio Code CLI.
    """
    cli_executable_path = "./code"
    cli_tarball_name = "vscode_cli.tar.gz"
    abs_cli_tarball_path = system.get_absolute_path(cli_tarball_name)
    abs_cli_executable_path = system.get_absolute_path(cli_executable_path)

    if system.path_exists(abs_cli_executable_path) and not force_download:
        logger.info(
            f"VS Code CLI already exists at {abs_cli_executable_path}. Skipping download."
        )
        return True

    logger.info("Downloading VS Code CLI...")
    download_success, download_err = system.download_file(
        "https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64",
        abs_cli_tarball_path,
    )
    if not download_success:
        logger.error(f"Failed to download VS Code CLI: {download_err}")
        return False

    logger.info("VS Code CLI tarball downloaded. Extracting...")
    tar_exe = system.which("tar")
    if not tar_exe:
        logger.error("'tar' command not found. Cannot extract VS Code CLI.")
        system.remove_file(abs_cli_tarball_path, missing_ok=True)  # Cleanup
        return False

    extract_cmd = [tar_exe, "-xf", abs_cli_tarball_path]
    extract_result = system.run_command(extract_cmd, capture_output=True, text=True)
    system.remove_file(
        abs_cli_tarball_path, missing_ok=True, log_success=False
    )  # Cleanup tarball

    if extract_result.returncode != 0:
        err_msg = (
            extract_result.stderr.strip()
            if extract_result.stderr
            else extract_result.stdout.strip()
        )
        logger.error(
            f"Failed to extract VS Code CLI. RC: {extract_result.returncode}. Error: {err_msg}"
        )
        return False

    if not system.path_exists(abs_cli_executable_path):  # Check if './code' was created
        logger.error(f"'{abs_cli_executable_path}' not found after extraction.")
        return False

    # The 'code' file within the extracted tarball needs execute permissions.
    # abs_cli_executable_path points to the *directory* ./code. The actual binary is inside.
    # The binary is typically just named 'code' inside this directory.
    actual_cli_binary = system.get_absolute_path(
        os.path.join(abs_cli_executable_path, "code")
    )

    if system.file_exists(actual_cli_binary):
        try:
            current_mode = system.get_permissions(actual_cli_binary)
            # Add execute for user, group, others
            system.change_permissions(actual_cli_binary, current_mode | 0o111)
            logger.info(f"Set execute permission for {actual_cli_binary}")
        except Exception as e_chmod:
            logger.warning(
                f"Could not set execute permission for {actual_cli_binary}: {e_chmod}"
            )
            # This might not be fatal if permissions are already okay or not strictly needed by Popen.
    else:
        logger.warning(
            f"VS Code CLI binary not found at expected path: {actual_cli_binary} inside {abs_cli_executable_path}"
        )

    logger.info(f"VS Code CLI extracted successfully to '{abs_cli_executable_path}'.")
    return True


def display_github_auth_link(url: str, code: str) -> None:
    html_content = render_github_auth_template(url=url, code=code)
    display(HTML(html_content))


def display_vscode_connection_options(
    tunnel_url: str,
    tunnel_name: str,
) -> None:
    html_content = render_vscode_connection_template(
        tunnel_url=tunnel_url, tunnel_name=tunnel_name
    )
    display(HTML(html_content))


def login(system: System, provider: str = "github") -> bool:
    """
    Handles the login process for VS Code Tunnel using the specified authentication provider.

    This function ensures that the VS Code CLI is available and executable. If the CLI is not found, it attempts to download it. The function monitors the CLI output to extract the authentication URL and code, which are then displayed to the user.

    Args:
        provider (str, optional): The authentication provider to use for login. Defaults to "github".

    Returns:
        bool: True if the login process successfully detects and displays the authentication URL and code, False otherwise.

    Notes:
        - The function uses a timeout of 60 seconds to monitor the CLI output for the authentication URL and code.
        - The function assumes success once the authentication URL and code are detected and displayed.
    """
    # Path to the CLI executable relative to the current working directory
    cli_exe_dir_path = system.get_absolute_path("./code")
    cli_exe_path = system.get_absolute_path(os.path.join(cli_exe_dir_path, "code"))

    if not system.is_executable(cli_exe_path):
        logger.info(
            f"VS Code CLI not found/executable at '{cli_exe_path}'. Attempting download for login."
        )
        if not download_vscode_cli(system=system):
            logger.error("VS Code CLI download failed. Cannot perform login.")
            return False
        # Re-check after download attempt
        if not system.is_executable(cli_exe_path):
            logger.error(
                f"VS Code CLI still not executable at '{cli_exe_path}' after download. Cannot perform login."
            )
            return False

    cmd_str = f"{cli_exe_path} tunnel user login --provider {provider}"
    logger.info(f"Initiating VS Code Tunnel login with command: {cmd_str}")

    proc = None
    try:
        proc = subprocess.Popen(
            cmd_str,  # Use the string command with shell=True
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        if proc.stdout is None:  # Should not happen with stdout=PIPE
            logger.error("Failed to get login process stdout.")
            if proc:
                proc.terminate()
            return False

        start_time = time.time()
        timeout_seconds = 60

        url_re = re.compile(r"https?://[^\s]+")
        code_re = re.compile(r"([A-Z0-9]{4,8}-[A-Z0-9]{4,8})")
        auth_url_found: Optional[str] = None
        auth_code_found: Optional[str] = None

        logger.info(
            "Monitoring login process output for authentication URL and code..."
        )
        for line in iter(proc.stdout.readline, ""):
            if time.time() - start_time > timeout_seconds:
                logger.warning(
                    f"Login process timed out after {timeout_seconds} seconds."
                )
                proc.terminate()
                proc.wait()
                return False

            logger.debug(f"> {line.strip()}")
            if not auth_url_found:
                um = url_re.search(line)
                if um and "github.com/login/device" in um.group(0):
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
                display_github_auth_link(auth_url_found, auth_code_found)
                return True  # Assume success once info is displayed

            if proc.poll() is not None:
                logger.info("Login process ended.")
                break

        # The stdout was closed and we didn't find the URL and code
        if not (auth_url_found and auth_code_found):
            logger.error(
                "Failed to detect GitHub authentication URL and code from CLI output."
            )
            if proc.poll() is None:
                proc.terminate()
                proc.wait()
            return False
        return True

    except FileNotFoundError:
        logger.error(
            f"VS Code CLI ('{cli_exe_path}') not found by Popen. Ensure it's in CWD or PATH for Popen."
        )
        return False
    except Exception as e:
        logger.exception(f"Error during login: {e}")
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait()
        return False


def connect(
    system: System,
    name: str = "colab",
    include_default_extensions: bool = True,
    extensions: Optional[List[str]] = None,
    git_user_name: Optional[str] = None,
    git_user_email: Optional[str] = None,
    setup_python_version: Optional[str] = None,
    force_python_reinstall: bool = False,
    create_new_project: Optional[str] = None,
    new_project_base_path: str = ".",
    venv_name_for_project: str = ".venv",
) -> Optional[subprocess.Popen]:
    """
    Establishes a VS Code tunnel connection, optionally configuring Python, Git, and project setup.

    Args:
        name (str, optional): The name of the VS Code tunnel. Defaults to "colab".
        include_default_extensions (bool, optional): Whether to include default VS Code extensions. Defaults to True.
        extensions (Optional[List[str]], optional): Additional VS Code extensions to install.
        git_user_name (Optional[str], optional): Git user name for configuration. Both `git_user_name` and `git_user_email` must be provided to configure Git. Defaults to None.
        git_user_email (Optional[str], optional): Git user email for configuration. Both `git_user_name` and `git_user_email` must be provided to configure Git. Defaults to None.
        setup_python_version (Optional[str], optional): Python version to set up using pyenv. Defaults to None.
        force_python_reinstall (bool, optional): Whether to force reinstall the specified Python version. Defaults to False.
        create_new_project (Optional[str], optional): Name of a new project to create. If provided, a new project directory will be set up. Defaults to None.
        new_project_base_path (str, optional): Base path for creating the new project. Defaults to the current directory ".".
        venv_name_for_project (str, optional): Name of the virtual environment directory for the project. Defaults to ".venv".

    Returns:
        Optional[subprocess.Popen]: A subprocess.Popen object representing the tunnel process if successful, or None if the connection could not be established.

    Notes:
        - This function attempts to download and configure the VS Code CLI if it is not already available.
        - If a specific Python version is requested, it will attempt to set it up using pyenv.
        - If a new project is created, the working directory for the tunnel will be set to the project's path.
        - The function monitors the tunnel process output to detect the connection URL and logs it.
        - If the tunnel process fails to start or the URL is not detected within a timeout, the process is terminated.
    """
    if not download_vscode_cli(system, force_download=False):
        logger.error("VS Code CLI not available, cannot start tunnel.")
        return None

    if git_user_name and git_user_email:  # Both must be provided
        configure_git(system, git_user_name, git_user_email)

    python_executable_for_venv = "python3"
    # Determine CWD for the tunnel. Default to current dir from system perspective.
    project_path_for_tunnel_cwd = system.get_cwd()

    if setup_python_version:
        logger.info(
            f"Attempting to set up Python version: {setup_python_version} using pyenv."
        )

        pyenv_manager = PythonEnvManager(system=system)

        pyenv_res = pyenv_manager.setup_and_get_python_executable(
            python_version=setup_python_version,
            force_reinstall_python=force_python_reinstall,
        )

        if pyenv_res:
            python_executable_for_venv = pyenv_res.value
            logger.info(
                f"Using pyenv Python '{python_executable_for_venv}' for subsequent venv creation."
            )
        else:
            logger.warning(
                f"Failed to set up pyenv Python {setup_python_version}. Using default '{python_executable_for_venv}'."
            )

    if create_new_project:
        logger.info(
            f"Attempting to create project: '{create_new_project}' at '{new_project_base_path}'."
        )
        abs_new_project_base_path = system.get_absolute_path(new_project_base_path)
        created_project_path = setup_project_directory(
            system,
            project_name=create_new_project,
            base_path=abs_new_project_base_path,
            python_executable=python_executable_for_venv,
            venv_name=venv_name_for_project,
        )
        if created_project_path:
            logger.info(
                f"Successfully created project at '{created_project_path}'. Tunnel CWD set."
            )
            project_path_for_tunnel_cwd = created_project_path
        else:
            logger.warning(
                f"Failed to create project '{create_new_project}'. Tunnel CWD: {project_path_for_tunnel_cwd}."
            )

    final_extensions: Set[str] = set()
    if include_default_extensions:
        final_extensions.update(DEFAULT_EXTENSIONS)
    if extensions:
        final_extensions.update(extensions)

    initial_cwd_of_script = system.get_cwd()
    cli_dir_abs_path = system.get_absolute_path(os.path.join(system.get_cwd(), "code"))
    cli_exe_abs_path = system.get_absolute_path(os.path.join(cli_dir_abs_path, "code"))

    if not system.is_executable(cli_exe_abs_path):
        logger.error(
            f"VS Code CLI binary not found or not executable at {cli_exe_abs_path}. This might happen if CWD changed after download."
        )
        logger.info(
            "Attempting to download VS Code CLI again into current CWD for connect..."
        )
        if not download_vscode_cli(
            system, force_download=True
        ):  # Force download into current CWD
            logger.error("VS Code CLI re-download failed. Cannot start tunnel.")
            return None
        cli_exe_for_popen = system.get_absolute_path("./code/code")
        if not system.is_executable(cli_exe_for_popen):
            logger.error(f"VS Code CLI still not executable at '{cli_exe_for_popen}'.")
            return None
    else:
        cli_exe_for_popen = cli_exe_abs_path

    cmd_list = [
        cli_exe_for_popen,
        "tunnel",
        "--accept-server-license-terms",
        "--name",
        name,
    ]
    if final_extensions:
        for ext_id in sorted(list(final_extensions)):
            cmd_list.extend(["--install-extension", ext_id])

    logger.info(f"Starting VS Code tunnel with command: {' '.join(cmd_list)}")
    logger.info(f"Tunnel will run with CWD: {project_path_for_tunnel_cwd}")

    proc = None
    try:
        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=project_path_for_tunnel_cwd,
        )
        if proc.stdout is None:
            logger.error("Failed to get tunnel process stdout.")
            if proc:
                proc.terminate()
            return None

        start_time = time.time()
        timeout_seconds = 60

        url_re = re.compile(r"https://vscode\.dev/tunnel/[\w-]+(?:/[\w-]+)?")

        logger.info("Monitoring tunnel process output for connection URL...")
        for line in iter(proc.stdout.readline, ""):
            if time.time() - start_time > timeout_seconds:
                logger.error(
                    f"Tunnel URL not detected within {timeout_seconds}s. Timing out."
                )
                proc.terminate()
                proc.wait()
                return None
            logger.debug(f"Tunnel output: {line.strip()}")
            m = url_re.search(line)
            if m:
                tunnel_url = m.group(0)
                logger.info(f"VS Code Tunnel URL detected: {tunnel_url}")
                display_vscode_connection_options(tunnel_url, name)
                return proc
            if proc.poll() is not None:
                logger.error("Tunnel process exited prematurely before URL detected.")
                if proc.stdout:
                    logger.debug(proc.stdout.read().strip())
                return None

        # EOF reached
        if proc.poll() is not None:
            logger.error("Tunnel process ended before URL detected (EOF).")
        else:
            logger.error("Tunnel URL not detected (EOF or unknown state).")
            proc.terminate()
            proc.wait()
        return None
    except FileNotFoundError:
        logger.error(
            f"VS Code CLI ('{cli_exe_for_popen}') not found by Popen. Ensure it is in CWD or PATH."
        )
        return None
    except Exception as e:
        logger.exception(f"Error starting tunnel: {e}")
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait()
        return None
