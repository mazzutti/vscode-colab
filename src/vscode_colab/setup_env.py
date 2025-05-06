import os
import platform
import shutil
import subprocess
import sys
import textwrap
import urllib.request  # Corrected import for urllib.request
from textwrap import dedent
from typing import Optional

from vscode_colab.logger_config import log as logger  # Use the new logger

# Configure Loguru
# Handler 1: Console output (INFO and above)
# logger.remove()  # Remove default handlers
# logger.add( # Removed old logger config
#     sys.stderr, # Removed old logger config
#     level="INFO", # Removed old logger config
#     format="{time:YYYY-MM-DD HH:mm:ss} - {level} - [{function}] {message}", # Removed old logger config
# ) # Removed old logger config
#  # Removed old logger config
# # Handler 2: File output (DEBUG and above, appending) # Removed old logger config
# # This handler saves all messages from DEBUG level upwards to a file. # Removed old logger config
# # It will append to the file if it already exists. # Removed old logger config
# logger.add( # Removed old logger config
#     "script_activity.log",  # Name of the log file # Removed old logger config
#     level="DEBUG",  # Log all messages from DEBUG level upwards # Removed old logger config
#     format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{module}:{function}:{line} - {message}",  # A more detailed format for file logs # Removed old logger config
#     mode="a",  # Explicitly set append mode (though it's default for files) # Removed old logger config
#     encoding="utf-8",  # Specify encoding for the log file # Removed old logger config
#     # Optional: Add rotation or retention policies if the log file might grow too large # Removed old logger config
#     # rotation="10 MB",    # e.g., rotate when file reaches 10 MB # Removed old logger config
#     # retention="7 days",  # e.g., keep logs for 7 days # Removed old logger config
# ) # Removed old logger config


def _run_command(
    command: list[str], cwd: str | None = None, env: dict | None = None
) -> tuple[bool, str, str]:
    """
    Helper function to run a shell command and capture its output.

    Args:
        command (list[str]): The command and its arguments as a list.
        cwd (str, optional): The working directory to run the command in. Defaults to None.
        env (dict, optional): Environment variables to set for the command. Defaults to None.

    Returns:
        tuple[bool, str, str]: A tuple containing:
            - bool: True if the command was successful (return code 0), False otherwise.
            - str: The standard output of the command.
            - str: The standard error of the command.
    """
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
        )
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            logger.info(f"Successfully executed: {' '.join(command)}")
            if stdout:
                logger.debug(f"Stdout: {stdout.strip()}")
            if stderr:
                logger.debug(
                    f"Stderr: {stderr.strip()}"
                )  # Some tools output to stderr on success
            return True, stdout, stderr
        else:
            logger.error(f"Error executing: {' '.join(command)}")
            logger.error(f"Return code: {process.returncode}")
            if stdout:
                logger.error(f"Stdout: {stdout.strip()}")
            if stderr:
                logger.error(f"Stderr: {stderr.strip()}")
            return False, stdout, stderr
    except FileNotFoundError:
        logger.error(f"Command not found: {command[0]}")
        return False, "", f"Command not found: {command[0]}"
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while running {' '.join(command)}: {e}"
        )
        return False, "", str(e)


def configure_git(
    git_user_name: Optional[str] = None,
    git_user_email: Optional[str] = None,
):
    """
    Configures global Git user name and email using the provided values.
    """
    if (git_user_name and not git_user_email) or (git_user_email and not git_user_name):
        logger.warning(
            "Both git_user_name and git_user_email must be provided together. Skipping git configuration."
        )
        return

    try:
        logger.info(
            f"Attempting to set git global user.name='{git_user_name}' and user.email='{git_user_email}'..."
        )
        name_success, _, name_err = _run_command(
            ["git", "config", "--global", "user.name", git_user_name]
        )
        if name_success:
            logger.info(f"Successfully set git global user.name='{git_user_name}'.")
        else:
            logger.error(f"Failed to set git global user.name: {name_err}")
            return

        email_success, _, email_err = _run_command(
            ["git", "config", "--global", "user.email", git_user_email]
        )
        if email_success:
            logger.info(f"Successfully set git global user.email='{git_user_email}'.")
        else:
            logger.error(f"Failed to set git global user.email: {email_err}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during git configuration: {e}")


def setup_project_directory(
    project_name: str,
    base_path: str = ".",
    python_executable: str = "python3",
    venv_name: str = ".venv",
) -> str | None:
    """
    Creates a new project directory, initializes a Git repository,
    and creates a Python virtual environment. Attempts to ensure pip is installed.

    Args:
        project_name (str): The name of the project and the directory to be
        created.
        base_path (str, optional): The path where the project directory will
        be created. Defaults to the current working directory.
        python_executable (str, optional): The Python executable to use for
        creating the virtual environment. Defaults to "python3".
        venv_name (str, optional): The name of the virtual environment
        directory. Defaults to ".venv".

    Returns:
        str | None: The absolute path to the created project directory
        if directory creation is successful, None otherwise.
        Messages will indicate the status of venv and pip setup via logging.
    """
    project_path = os.path.abspath(os.path.join(base_path, project_name))
    original_cwd = os.getcwd()

    if os.path.exists(project_path):
        logger.info(
            f"Project directory {project_path} already exists. Skipping creation."
        )
        return project_path

    logger.info(f"Creating project directory at: {project_path}")
    try:
        os.makedirs(project_path)
    except OSError as e:
        logger.error(f"Failed to create project directory {project_path}: {e}")
        return None

    venv_with_pip_ready = False

    try:
        os.chdir(project_path)
        logger.info(f"Changed working directory to {project_path}")

        logger.info("Initializing Git repository...")
        git_success, _, git_stderr = _run_command(["git", "init"])
        if not git_success:
            logger.warning(f"Failed to initialize Git repository: {git_stderr}")
        else:
            gitignore_content = textwrap.dedent(
                f"""\
                # Python
                __pycache__/
                *.py[cod]
                *$py.class

                # Virtual Environment
                {venv_name}/

                # IDE / Editor
                .vscode/
                .idea/
                *.swp
                *~
                """
            )
            try:
                with open(".gitignore", "w") as f:
                    f.write(gitignore_content)
                logger.info("Created .gitignore file.")
            except IOError as e:
                logger.warning(f"Could not create .gitignore file: {e}")

        logger.info(f"Creating virtual environment using Python: {python_executable}")
        venv_path = os.path.join(project_path, venv_name)

        if not shutil.which(python_executable):
            logger.error(
                f"Python executable '{python_executable}' not found. Cannot create virtual environment."
            )
            return project_path  # Return project_path as it was created, though venv failed

        venv_cmd = [python_executable, "-m", "venv", venv_name]
        venv_success, initial_venv_stdout, initial_venv_stderr = _run_command(
            venv_cmd, cwd=project_path
        )

        venv_bin_dir = os.path.join(
            venv_path, "Scripts" if sys.platform == "win32" else "bin"
        )
        expected_venv_exe_name = (
            "python.exe"
            if sys.platform == "win32"
            else os.path.basename(python_executable)
        )

        resolved_venv_python_exe = None
        potential_exe_path = os.path.join(venv_bin_dir, expected_venv_exe_name)

        if os.path.exists(potential_exe_path):
            resolved_venv_python_exe = potential_exe_path
        elif sys.platform != "win32":  # Fallback for non-Windows
            # Check common names like 'python' or 'python3' if basename(python_executable) doesn't exist
            # e.g. if python_executable was 'python3.9', basename is 'python3.9', but venv might create 'python'
            for name in [
                "python",
                "python3",
                os.path.basename(python_executable),
            ]:  # Add basename again for clarity
                fallback_path = os.path.join(venv_bin_dir, name)
                if os.path.exists(fallback_path):
                    resolved_venv_python_exe = fallback_path
                    logger.info(
                        f"Found venv python executable via fallback: {resolved_venv_python_exe}"
                    )
                    break

        if not resolved_venv_python_exe and os.path.isdir(venv_bin_dir):
            logger.warning(
                f"Could not reliably determine python executable in {venv_bin_dir} using common names."
            )

        if venv_success:
            logger.info(
                f"Initial venv command reported success (stdout: {initial_venv_stdout.strip()}). Checking for pip..."
            )
            if resolved_venv_python_exe:
                pip_check_cmd = [resolved_venv_python_exe, "-m", "pip", "--version"]
                pip_check_success, _, _ = _run_command(pip_check_cmd, cwd=project_path)
                if pip_check_success:
                    logger.info(
                        "pip is available and working in the virtual environment."
                    )
                    venv_with_pip_ready = True
                else:
                    logger.warning(
                        "Initial venv command succeeded, but pip is not working. Will attempt manual pip installation."
                    )
            else:
                logger.warning(
                    f"Venv structure might be present, but its Python executable not found in {venv_bin_dir}. Cannot check/install pip automatically."
                )
        else:
            logger.error(
                f"Initial virtual environment creation command failed. Stdout: {initial_venv_stdout.strip()}, Stderr: {initial_venv_stderr.strip()}"
            )

        if not venv_with_pip_ready:
            logger.info("Attempting to ensure pip is installed manually...")
            if resolved_venv_python_exe and os.path.exists(resolved_venv_python_exe):
                logger.info(
                    f"Using venv Python for manual pip install: {resolved_venv_python_exe}"
                )
                get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
                get_pip_script_path = os.path.join(project_path, "get-pip.py")

                try:
                    logger.info(f"Downloading {get_pip_url} to {get_pip_script_path}")
                    urllib.request.urlretrieve(get_pip_url, get_pip_script_path)

                    logger.info(
                        f"Running get-pip.py using {resolved_venv_python_exe}..."
                    )
                    pip_install_cmd = [resolved_venv_python_exe, get_pip_script_path]
                    pip_install_success, pip_stdout, pip_stderr = _run_command(
                        pip_install_cmd, cwd=project_path
                    )

                    if pip_install_success:
                        logger.info(
                            "Manual pip installation script executed successfully."
                        )
                        pip_verify_cmd = [
                            resolved_venv_python_exe,
                            "-m",
                            "pip",
                            "--version",
                        ]
                        verify_success, pip_ver_out, _ = _run_command(
                            pip_verify_cmd, cwd=project_path
                        )
                        if verify_success:
                            logger.info(
                                f"pip verified successfully in the virtual environment: {pip_ver_out.strip()}"
                            )
                            venv_with_pip_ready = True
                        else:
                            logger.error(
                                "pip installed via get-pip.py but subsequent verification failed."
                            )
                    else:
                        logger.error(
                            f"Failed to install pip using get-pip.py. Stdout: {pip_stdout.strip()}, Stderr: {pip_stderr.strip()}"
                        )

                except Exception as e:
                    logger.exception(
                        f"An error occurred during manual pip installation: {e}"
                    )
                finally:
                    if os.path.exists(get_pip_script_path):
                        os.remove(get_pip_script_path)
                        logger.info(f"Removed {get_pip_script_path}.")
            else:
                logger.error(
                    "Virtual environment's Python interpreter not found or venv structure incomplete. Cannot attempt manual pip installation."
                )

        if venv_with_pip_ready:
            logger.info(
                f"SUCCESS: Virtual environment '{venv_name}' with pip is ready at {venv_path}"
            )
        else:
            logger.warning(
                f"WARNING: Failed to ensure pip is installed in virtual environment '{venv_name}' at {venv_path}. The venv may not be fully usable."
            )

        return project_path

    except Exception as e:
        logger.exception(
            f"An unexpected critical error occurred during project setup: {e}"
        )
        return None  # project_path might be partially created, but operation failed critically
    finally:
        os.chdir(original_cwd)
        logger.info(f"Restored working directory to {original_cwd}")


def setup_pyenv_and_python_version(
    python_version: str,
    force_reinstall_python: bool = False,
    update_pyenv: bool = True,  # update_pyenv not used
) -> str | None:
    """
    Installs pyenv if not present, installs the specified Python version
    using pyenv, and sets it as the global version.

    Args:
        python_version (str): The Python version to install and set
        (e.g., "3.9.18").
        force_reinstall_python (bool, optional): Whether to reinstall
        the Python version if it already exists. Defaults to False.
        update_pyenv (bool, optional): Whether to update pyenv
        before installing Python. Defaults to True. (Currently not implemented)

    Returns:
        str | None: The absolute path to the `python` executable of
        the installed version if successful, None otherwise.
    """
    # The update_pyenv flag is not used in the original code, so I'll note it.
    if update_pyenv:
        logger.info(
            "pyenv update functionality is noted but not implemented in this version of the script."
        )
        # Example: _run_command([pyenv_bin, "update"], env=current_env) could be added here if desired.

    pyenv_root = os.path.expanduser("~/.pyenv")
    pyenv_bin = os.path.join(pyenv_root, "bin", "pyenv")
    current_env = os.environ.copy()
    current_env["PYENV_ROOT"] = pyenv_root
    # Ensure shims and bin are at the start of PATH for subprocesses
    new_path_parts = [
        os.path.join(pyenv_root, "bin"),
        os.path.join(pyenv_root, "shims"),
    ]
    existing_path = current_env.get("PATH", "")
    current_env["PATH"] = os.pathsep.join(new_path_parts) + os.pathsep + existing_path

    # 1. Check if pyenv is installed, if not, install it
    if not os.path.exists(pyenv_bin):
        logger.info("pyenv not found. Attempting to install pyenv...")
        installer_cmd = "curl -L https://pyenv.run | bash"
        try:
            # Using shell=True is generally a security risk if the command is not static.
            # Here, it's a fixed command.
            process = subprocess.run(
                installer_cmd,
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                env=current_env,
            )
            logger.info("pyenv installation script executed.")
            logger.debug(f"pyenv installer stdout: {process.stdout.strip()}")
            if process.stderr:
                logger.debug(f"pyenv installer stderr: {process.stderr.strip()}")
            if not os.path.exists(pyenv_bin):
                logger.error(
                    "pyenv installation script ran, but pyenv executable not found at expected location."
                )
                logger.info(
                    "You may need to manually add pyenv to your PATH or re-source your shell profile."
                )
                logger.info(f"Expected PYENV_ROOT: {pyenv_root}")
                return None
            logger.info(
                "pyenv installed successfully. You might need to restart your shell or source your profile for it to be available globally in new terminals."
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"pyenv installation script failed: {e}")
            logger.error(f"Stdout: {e.stdout.strip()}")
            logger.error(f"Stderr: {e.stderr.strip()}")
            return None
        except FileNotFoundError:
            logger.error("curl command not found. Cannot download pyenv installer.")
            return None
    else:
        logger.info(f"pyenv is already installed at {pyenv_root}")

    # Ensure pyenv shims and bin are in PATH for this script's subprocesses
    os.environ["PATH"] = current_env["PATH"]
    os.environ["PYENV_ROOT"] = pyenv_root

    # 2. Check if the desired Python version is installed by pyenv
    logger.info(f"Checking if Python version {python_version} is installed by pyenv...")
    versions_success, installed_versions_out, versions_err = _run_command(
        [pyenv_bin, "versions", "--bare"], env=current_env
    )

    is_installed = False
    if versions_success:
        if python_version in installed_versions_out.splitlines():
            is_installed = True
            logger.info(
                f"Python version {python_version} is already installed by pyenv."
            )
    else:
        logger.warning(f"Could not list pyenv versions. Stderr: {versions_err.strip()}")

    if is_installed and not force_reinstall_python:
        logger.info(f"Using existing installation of Python {python_version}.")
    else:
        if is_installed and force_reinstall_python:
            logger.info(f"Force reinstalling Python {python_version}...")
        else:
            logger.info(
                f"Python version {python_version} not found or forcing reinstall. Installing..."
            )

        install_env = current_env.copy()
        python_configure_opts = []
        if platform.system() == "Linux":
            python_configure_opts.extend(["--enable-shared"])

        if python_configure_opts:
            install_env["PYTHON_CONFIGURE_OPTS"] = " ".join(python_configure_opts)
            logger.info(
                f"Using PYTHON_CONFIGURE_OPTS: {install_env['PYTHON_CONFIGURE_OPTS']}"
            )

        logger.info(
            f"Attempting to install Python {python_version} with pyenv. This may take a while..."
        )
        # Forcing a re-run of pyenv init to ensure shims are set up for the install command if needed.
        # _run_command([pyenv_bin, "init", "-"], env=install_env)

        install_cmd = [pyenv_bin, "install"]
        if force_reinstall_python:
            install_cmd.append("--force")
        install_cmd.append(python_version)

        install_success, install_out, install_err = _run_command(
            install_cmd, env=install_env
        )
        if not install_success:
            logger.error(f"Failed to install Python {python_version} using pyenv.")
            logger.error(f"Install stdout: {install_out.strip()}")
            logger.error(f"Install stderr: {install_err.strip()}")
            logger.error(
                "Please ensure build dependencies are installed. Common ones include: build-essential, libssl-dev, zlib1g-dev, libbz2-dev, libreadline-dev, libsqlite3-dev, wget, curl, llvm, libncurses5-dev, libncursesw5-dev, xz-utils, tk-dev, libffi-dev, liblzma-dev, python-openssl, git"
            )
            return None
        logger.info(f"Python {python_version} installed successfully.")

    # 4. Set the Python version globally
    logger.info(f"Setting global Python version to {python_version} using pyenv...")
    global_success, global_out, global_err = _run_command(
        [pyenv_bin, "global", python_version], env=current_env
    )
    if not global_success:
        logger.error(
            f"Failed to set global Python version to {python_version}. Stdout: {global_out.strip()} Stderr: {global_err.strip()}"
        )
        return None
    logger.info(f"Global Python version set to {python_version}.")

    # 5. Verify and return the path to the Python executable
    expected_python_path = os.path.join(
        pyenv_root, "versions", python_version, "bin", "python"
    )
    if os.path.exists(expected_python_path) and os.access(
        expected_python_path, os.X_OK
    ):
        logger.info(f"Python executable found at: {expected_python_path}")
        return expected_python_path
    else:
        logger.info(
            f"Expected Python path {expected_python_path} not found or not executable. Trying 'pyenv which python'."
        )
        # `pyenv which python` should give the correct shimed path after global is set
        which_success, which_out, which_err = _run_command(
            [pyenv_bin, "which", "python"], env=current_env
        )
        if which_success and which_out.strip() and os.path.exists(which_out.strip()):
            found_path = os.path.realpath(
                which_out.strip()
            )  # Resolve symlink from shims
            logger.info(
                f"Python executable (via 'pyenv which python') resolved to: {found_path}"
            )
            if (
                os.path.samefile(found_path, expected_python_path)
                or python_version in found_path
            ):
                return found_path
            else:
                logger.warning(
                    f"'pyenv which python' ({found_path}) does not match expected version path ({expected_python_path})."
                )
                # Still return it as pyenv deems it correct, but log a warning.
                return found_path

        else:
            logger.error(
                f"Python executable not found at expected path {expected_python_path} or via 'pyenv which python' after setting global."
            )
            if which_err:
                logger.error(f"'pyenv which python' stderr: {which_err.strip()}")
            if which_out:  # If command succeeded but output was not a valid path
                logger.error(f"'pyenv which python' stdout: {which_out.strip()}")

            return None
