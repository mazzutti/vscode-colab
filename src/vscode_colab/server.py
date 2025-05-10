import os
import re
import subprocess
import time
from typing import List, Optional, Set, Tuple

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
from vscode_colab.utils import SystemOperationResult

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


def download_vscode_cli(
    system: System, force_download: bool = False
) -> SystemOperationResult[str, Exception]:
    """
    Downloads and extracts the Visual Studio Code CLI for Linux.
    Returns SystemOperationResult with the absolute path to the CLI executable directory on success.
    """
    # On Linux, the CLI is typically extracted into a directory, and the executable is within it.
    cli_dir_name = "code"  # The directory created by extracting the tarball
    cli_executable_name_in_dir = "code"

    cli_tarball_name = "vscode_cli_alpine_x64.tar.gz"  # More specific name

    # Paths relative to current CWD where download and extraction happen
    # The server.py functions assume they operate from a specific CWD.
    abs_cli_dir_path = system.get_absolute_path(cli_dir_name)
    abs_cli_executable_path = system.get_absolute_path(
        os.path.join(abs_cli_dir_path, cli_executable_name_in_dir)
    )
    abs_cli_tarball_path = system.get_absolute_path(cli_tarball_name)

    if system.is_executable(abs_cli_executable_path) and not force_download:
        logger.info(
            f"VS Code CLI already exists and is executable at {abs_cli_executable_path}. Skipping download."
        )
        return SystemOperationResult.Ok(abs_cli_executable_path)

    # If directory exists but not executable, or force_download, remove existing first
    if system.path_exists(abs_cli_dir_path) and force_download:
        logger.info(
            f"Force download: Removing existing VS Code CLI directory at {abs_cli_dir_path}"
        )
        rm_dir_res = system.remove_dir(abs_cli_dir_path, recursive=True)
        if not rm_dir_res:
            logger.warning(
                f"Failed to remove existing CLI directory {abs_cli_dir_path}: {rm_dir_res.message}"
            )

    logger.info(
        f"Downloading VS Code CLI (cli-alpine-x64) to {abs_cli_tarball_path}..."
    )
    download_res = system.download_file(
        "https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64",  # Hardcoded for Linux
        abs_cli_tarball_path,
    )
    if not download_res:
        return SystemOperationResult.Err(
            download_res.error or Exception("Download failed"),
            message=f"Failed to download VS Code CLI: {download_res.message}",
        )

    logger.info("VS Code CLI tarball downloaded. Extracting...")
    tar_exe = system.which("tar")
    if not tar_exe:
        msg = "'tar' command not found. Cannot extract VS Code CLI."
        logger.error(msg)
        system.remove_file(abs_cli_tarball_path, missing_ok=True, log_success=False)
        return SystemOperationResult.Err(FileNotFoundError("tar"), message=msg)

    # Tar typically extracts into the current working directory.
    # The archive is expected to contain a top-level directory (e.g., "code")
    extract_cmd = [
        tar_exe,
        "-xzf",
        abs_cli_tarball_path,
    ]  # -x: extract, -z: gzip, -f: file

    try:
        extract_proc = system.run_command(
            extract_cmd, capture_output=True, text=True, check=False
        )
    except Exception as e_extract_run:
        system.remove_file(abs_cli_tarball_path, missing_ok=True, log_success=False)
        return SystemOperationResult.Err(
            e_extract_run,
            message=f"VS Code CLI extraction command failed: {e_extract_run}",
        )
    finally:
        system.remove_file(
            abs_cli_tarball_path, missing_ok=True, log_success=False
        )  # Cleanup tarball

    if extract_proc.returncode != 0:
        err_msg = extract_proc.stderr.strip() or extract_proc.stdout.strip()
        full_err_msg = f"Failed to extract VS Code CLI. RC: {extract_proc.returncode}. Error: {err_msg}"
        logger.error(full_err_msg)
        return SystemOperationResult.Err(
            Exception("tar extraction failed"), message=full_err_msg
        )

    # After extraction, the executable should be at abs_cli_executable_path
    if not system.file_exists(abs_cli_executable_path):
        msg = f"VS Code CLI executable '{abs_cli_executable_path}' not found after extraction."
        logger.error(msg)
        # Check if the directory itself was created, maybe the exe name inside is different?
        if system.dir_exists(abs_cli_dir_path):
            logger.debug(
                f"Directory {abs_cli_dir_path} exists, but executable {cli_executable_name_in_dir} not found within."
            )
        return SystemOperationResult.Err(
            FileNotFoundError(abs_cli_executable_path), message=msg
        )

    # Ensure the extracted CLI binary is executable
    if not system.is_executable(abs_cli_executable_path):
        logger.info(
            f"VS Code CLI at {abs_cli_executable_path} is not executable. Attempting to set permissions."
        )
        # Get current permissions first, then add execute bits
        perm_res = system.get_permissions(abs_cli_executable_path)
        if perm_res.is_ok and perm_res.value is not None:
            chmod_res = system.change_permissions(
                abs_cli_executable_path, perm_res.value | 0o111
            )  # Add u+x, g+x, o+x
            if not chmod_res:
                msg = (
                    f"Could not set execute permission for {abs_cli_executable_path}: {chmod_res.message}. "
                    "Tunnel connection might fail."
                )
                logger.warning(msg)
                # Not returning Err here, as Popen might still work if OS allows execution.
            else:
                logger.info(f"Set execute permission for {abs_cli_executable_path}")
        elif perm_res.is_err:
            logger.warning(
                f"Could not get permissions for {abs_cli_executable_path} to make it executable: {perm_res.message}"
            )

        # Re-check after attempting to set permissions
        if not system.is_executable(abs_cli_executable_path):
            msg = f"VS Code CLI at {abs_cli_executable_path} is still not executable after attempting chmod."
            logger.error(msg)
            return SystemOperationResult.Err(PermissionError(msg), message=msg)

    logger.info(
        f"VS Code CLI setup successful. Executable at: '{abs_cli_executable_path}'."
    )
    return SystemOperationResult.Ok(abs_cli_executable_path)


def display_github_auth_link(url: str, code: str) -> None:
    html_content = render_github_auth_template(url=url, code=code)
    display(HTML(html_content))


def display_vscode_connection_options(tunnel_url: str, tunnel_name: str) -> None:
    html_content = render_vscode_connection_template(
        tunnel_url=tunnel_url, tunnel_name=tunnel_name
    )
    display(HTML(html_content))


def login(system: System, provider: str = "github") -> bool:
    """
    Handles the login process for VS Code Tunnel.
    Returns True on success (auth info displayed), False otherwise.
    """
    cli_download_res = download_vscode_cli(system=system)  # Downloads to CWD by default
    if not cli_download_res.is_ok or not cli_download_res.value:
        logger.error(
            f"VS Code CLI download/setup failed. Cannot perform login. Error: {cli_download_res.message}"
        )
        return False

    cli_exe_abs_path = cli_download_res.value

    # Command list for Popen (avoids shell=True)
    cmd_list = [cli_exe_abs_path, "tunnel", "user", "login", "--provider", provider]
    cmd_str_for_log = " ".join(cmd_list)  # For logging
    logger.info(f"Initiating VS Code Tunnel login with command: {cmd_str_for_log}")

    proc = None
    try:
        # Use CWD of the script/library for Popen, as CLI was downloaded there.
        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr with stdout
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True,  # For text=True
            cwd=system.get_cwd(),  # Explicitly use current CWD
        )

        if proc.stdout is None:
            logger.error("Failed to get login process stdout (proc.stdout is None).")
            if proc:
                proc.terminate()
                proc.wait()
            return False

        start_time = time.time()
        timeout_seconds = 60  # Increased from 60 for robustness

        # Regex for GitHub device flow URL and code
        url_re = re.compile(r"(https?://github\.com/login/device)")
        code_re = re.compile(
            r"enter the code\s+([A-Z0-9]{4,}-[A-Z0-9]{4,})"
        )  # Capture group for the code

        auth_url_found: Optional[str] = None
        auth_code_found: Optional[str] = None

        logger.info(
            "Monitoring login process output for GitHub authentication URL and code..."
        )
        for line in iter(proc.stdout.readline, ""):
            if time.time() - start_time > timeout_seconds:
                logger.warning(
                    f"Login process timed out after {timeout_seconds} seconds."
                )
                proc.terminate()
                proc.wait()
                return False

            logger.debug(f"Login STDOUT: {line.strip()}")

            if not auth_url_found:
                url_match = url_re.search(line)
                if url_match:
                    auth_url_found = url_match.group(1)
                    logger.info(f"Detected authentication URL: {auth_url_found}")

            if not auth_code_found:
                code_match = code_re.search(line)
                if code_match:
                    auth_code_found = code_match.group(1)
                    logger.info(f"Detected authentication code: {auth_code_found}")

            if auth_url_found and auth_code_found:
                logger.info("Authentication URL and code detected. Displaying to user.")
                display_github_auth_link(auth_url_found, auth_code_found)
                # The process should continue running in the background until login is complete or it times out/fails.
                return True

            if proc.poll() is not None:  # Process ended
                logger.info(
                    "Login process ended before URL and code were found or fully processed."
                )
                break

        # Loop ended (either EOF or process terminated)
        if not (auth_url_found and auth_code_found):
            logger.error(
                "Failed to detect GitHub authentication URL and code from CLI output before process ended."
            )
            if proc and proc.poll() is None:  # If somehow still running
                proc.terminate()
                proc.wait()
            return False

        # Should have returned True inside the loop if both found
        return False  # Fallback

    except FileNotFoundError:  # For cli_exe_abs_path
        logger.error(
            f"VS Code CLI ('{cli_exe_abs_path}') not found by Popen. Ensure it's downloaded and executable."
        )
        return False
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during VS Code Tunnel login: {e}"
        )
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait()
        return False


def _configure_environment_for_tunnel(
    system: System,
    git_user_name: Optional[str],
    git_user_email: Optional[str],
    setup_python_version: Optional[str],
    force_python_reinstall: bool,
    attempt_pyenv_dependency_install: bool,
    create_new_project: Optional[str],
    new_project_base_path: str,
    venv_name_for_project: str,
) -> Tuple[SystemOperationResult[str, Exception], str]:
    """
    Handles Git configuration, pyenv setup, and project creation.
    Returns a tuple: (SOR for python_executable_for_venv, project_path_for_tunnel_cwd).
    The SOR's value for python_executable_for_venv will be the path if pyenv setup was successful,
    otherwise it's an error. The project_path_for_tunnel_cwd is the CWD to use for the tunnel.
    """
    # Default Python executable for creating venvs if pyenv setup is skipped or fails
    default_python_for_venv = "python3"
    python_executable_for_venv_res: SystemOperationResult[str, Exception] = (
        SystemOperationResult.Ok(default_python_for_venv)
    )

    # Determine CWD for the tunnel. Default to current dir.
    project_path_for_tunnel_cwd = system.get_cwd()

    if git_user_name and git_user_email:
        git_config_res = configure_git(system, git_user_name, git_user_email)
        if not git_config_res:
            logger.warning(
                f"Git configuration failed: {git_config_res.message}. Continuing..."
            )

    if setup_python_version:
        logger.info(
            f"Attempting to set up Python version: {setup_python_version} using pyenv."
        )
        pyenv_manager = PythonEnvManager(system=system)
        pyenv_python_exe_res = pyenv_manager.setup_and_get_python_executable(
            python_version=setup_python_version,
            force_reinstall_python=force_python_reinstall,
            attempt_pyenv_dependency_install=attempt_pyenv_dependency_install,
        )

        if pyenv_python_exe_res.is_ok and pyenv_python_exe_res.value:
            logger.info(
                f"Using pyenv Python '{pyenv_python_exe_res.value}' for subsequent venv creation."
            )
            python_executable_for_venv_res = SystemOperationResult.Ok(
                pyenv_python_exe_res.value
            )
        else:
            msg = (
                f"Failed to set up pyenv Python {setup_python_version}: {pyenv_python_exe_res.message}. "
                f"Will use default '{default_python_for_venv}' for venv creation if applicable."
            )
            logger.warning(msg)
            python_executable_for_venv_res = SystemOperationResult.Err(
                pyenv_python_exe_res.error or Exception("Pyenv setup failed"),
                message=pyenv_python_exe_res.message,
            )
            # Even if pyenv fails, we still use the default python for project venv creation.

    current_python_for_venv = (
        python_executable_for_venv_res.value
        if python_executable_for_venv_res.is_ok
        else default_python_for_venv
    )

    if create_new_project:
        logger.info(
            f"Attempting to create project: '{create_new_project}' at '{new_project_base_path}'."
        )
        # setup_project_directory expects an absolute base_path if provided, or uses CWD.
        # Here, new_project_base_path is relative to the CWD when `connect` was called.
        abs_new_project_base_path = system.get_absolute_path(new_project_base_path)

        project_setup_res = setup_project_directory(
            system,
            project_name=create_new_project,
            base_path=abs_new_project_base_path,  # Pass absolute path
            python_executable=current_python_for_venv,  # Use result from pyenv setup or default
            venv_name=venv_name_for_project,
        )
        if project_setup_res.is_ok and project_setup_res.value:
            logger.info(
                f"Successfully created project at '{project_setup_res.value}'. Tunnel CWD set."
            )
            project_path_for_tunnel_cwd = project_setup_res.value
        else:
            msg = (
                f"Failed to create project '{create_new_project}': {project_setup_res.message}. "
                f"Tunnel will use CWD: {project_path_for_tunnel_cwd}."
            )
            logger.warning(msg)
            # Project creation failure is not necessarily fatal for the tunnel itself, it will just run in original CWD.

    return python_executable_for_venv_res, project_path_for_tunnel_cwd


def _prepare_vscode_tunnel_command(
    cli_executable_path: str,  # Absolute path to 'code' executable
    tunnel_name: str,
    include_default_extensions: bool,
    custom_extensions: Optional[List[str]],
) -> List[str]:
    """Prepares the command list for launching the VS Code tunnel."""
    final_extensions: Set[str] = set()
    if include_default_extensions:
        final_extensions.update(DEFAULT_EXTENSIONS)
    if custom_extensions:
        final_extensions.update(custom_extensions)

    cmd_list = [
        cli_executable_path,
        "tunnel",
        "--accept-server-license-terms",  # Required for unattended execution
        "--name",
        tunnel_name,
    ]
    if final_extensions:
        for ext_id in sorted(list(final_extensions)):
            cmd_list.extend(["--install-extension", ext_id])

    return cmd_list


def _launch_and_monitor_tunnel(
    command_list: List[str],
    tunnel_cwd: str,  # Absolute path for CWD
    tunnel_name: str,  # For display purposes
    timeout_seconds: int = 60,  # Timeout for detecting URL
) -> Optional[subprocess.Popen]:
    """
    Launches the VS Code tunnel command and monitors its output for the connection URL.
    Returns the Popen object if URL is detected, None otherwise.
    """
    logger.info(f"Starting VS Code tunnel with command: {' '.join(command_list)}")
    logger.info(f"Tunnel will run with CWD: {tunnel_cwd}")

    proc: Optional[subprocess.Popen] = None
    try:
        proc = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr to stdout
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True,
            cwd=tunnel_cwd,  # Set the CWD for the tunnel process
        )

        if proc.stdout is None:  # Should not happen with PIPE
            logger.error("Failed to get tunnel process stdout (proc.stdout is None).")
            if proc:
                proc.terminate()
                proc.wait()
            return None

        start_time = time.time()
        # Regex for vscode.dev tunnel URL
        url_re = re.compile(r"(https://vscode\.dev/tunnel/[^\s/]+(?:/[^\s/]+)?)")

        logger.info(
            f"Monitoring tunnel '{tunnel_name}' process output for connection URL..."
        )
        for line in iter(proc.stdout.readline, ""):
            if time.time() - start_time > timeout_seconds:
                logger.error(
                    f"Tunnel URL for '{tunnel_name}' not detected within {timeout_seconds}s. Timing out."
                )
                if proc:  # Check proc again as it might be None if Popen failed
                    proc.terminate()
                    proc.wait()
                return None

            logger.debug(f"Tunnel '{tunnel_name}' STDOUT: {line.strip()}")
            match = url_re.search(line)
            if match:
                tunnel_url = match.group(1)
                # Ensure it's not the generic access grant URL if we expect a named tunnel URL
                if (
                    tunnel_name.lower() in tunnel_url.lower()
                    or "tunnel" not in tunnel_url.lower()
                ):
                    logger.info(
                        f"VS Code Tunnel URL for '{tunnel_name}' detected: {tunnel_url}"
                    )
                    display_vscode_connection_options(tunnel_url, tunnel_name)
                    return proc  # Return the running process
                else:
                    logger.debug(
                        f"Detected a vscode.dev URL but it might be for access grant: {tunnel_url}"
                    )

            if proc.poll() is not None:  # Process ended
                logger.error(
                    f"Tunnel process '{tunnel_name}' exited prematurely (RC: {proc.returncode}) before URL was detected."
                )
                # Log remaining output if any
                if proc.stdout:  # Check if stdout is still available
                    remaining_output = proc.stdout.read()
                    if remaining_output:
                        logger.debug(
                            f"Remaining output from tunnel '{tunnel_name}':\n{remaining_output.strip()}"
                        )
                return None

        # Loop ended (EOF on stdout)
        logger.error(
            f"Tunnel process '{tunnel_name}' stdout stream ended before URL was detected."
        )
        if proc and proc.poll() is None:  # If somehow still running
            proc.terminate()
            proc.wait()
        return None

    except FileNotFoundError:  # For the CLI command itself
        logger.error(
            f"VS Code CLI ('{command_list[0]}') not found by Popen. Tunnel CWD: {tunnel_cwd}."
        )
        return None
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred while starting or monitoring tunnel '{tunnel_name}': {e}"
        )
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait()
        return None


def connect(
    system: System,
    name: str = "colab",  # Name of the tunnel
    include_default_extensions: bool = True,
    extensions: Optional[List[str]] = None,  # Custom extensions
    git_user_name: Optional[str] = None,
    git_user_email: Optional[str] = None,
    setup_python_version: Optional[str] = None,  # e.g., "3.9"
    force_python_reinstall: bool = False,
    attempt_pyenv_dependency_install: bool = True,  # Attempt to install pyenv OS deps
    create_new_project: Optional[str] = None,  # Name of project dir to create
    new_project_base_path: str = ".",  # Base path for new project (relative to initial CWD)
    venv_name_for_project: str = ".venv",  # Name of venv dir inside project
) -> Optional[subprocess.Popen]:
    """
    Establishes a VS Code tunnel connection with optional environment setup.
    """
    # Ensure VS Code CLI is available. Download/setup happens in CWD of this script.
    # This CWD needs to be stable for the CLI to be found later by Popen.
    initial_script_cwd = system.get_cwd()
    logger.info(f"Initial CWD for connect operation: {initial_script_cwd}")

    cli_download_res = download_vscode_cli(system, force_download=False)
    if not cli_download_res.is_ok or not cli_download_res.value:
        logger.error(
            f"VS Code CLI is not available, cannot start tunnel. Error: {cli_download_res.message}"
        )
        return None

    # cli_download_res.value is the absolute path to the 'code' executable
    cli_executable_abs_path = cli_download_res.value

    # Step 1: Configure environment (Git, Python via pyenv, Project directory)
    # This helper returns the Python executable to use for venv and the CWD for the tunnel.
    _py_exec_res, tunnel_run_cwd = _configure_environment_for_tunnel(
        system,
        git_user_name,
        git_user_email,
        setup_python_version,
        force_python_reinstall,
        attempt_pyenv_dependency_install,
        create_new_project,
        new_project_base_path,  # This is relative to initial_script_cwd
        venv_name_for_project,
    )

    # Step 2: Prepare the VS Code tunnel command
    # The CLI executable path is absolute, found/downloaded relative to initial_script_cwd.
    command_list = _prepare_vscode_tunnel_command(
        cli_executable_path=cli_executable_abs_path,
        tunnel_name=name,
        include_default_extensions=include_default_extensions,
        custom_extensions=extensions,
    )

    # Step 3: Launch and monitor the tunnel
    # The tunnel_run_cwd is where the 'code tunnel' command will execute.
    # This is important if the tunnel creates files or expects to be in a project dir.
    tunnel_proc = _launch_and_monitor_tunnel(
        command_list,
        tunnel_cwd=tunnel_run_cwd,  # Use the determined CWD
        tunnel_name=name,
    )

    if not tunnel_proc:
        logger.error(f"Failed to establish VS Code tunnel '{name}'.")
        return None

    logger.info(f"VS Code tunnel '{name}' process started successfully.")
    return tunnel_proc
