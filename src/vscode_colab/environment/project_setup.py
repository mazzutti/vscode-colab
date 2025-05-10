import os
from typing import Optional

from vscode_colab.logger_config import log as logger
from vscode_colab.system import System

GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
GET_PIP_SCRIPT_NAME = "get-pip.py"


def _determine_venv_python_executable(
    system: System,
    venv_path: str,  # Absolute path to venv directory
    base_python_executable_name: str,  # e.g., "python3.9" or "python"
) -> Optional[str]:
    """
    Attempts to determine the path to the Python executable within a created virtual environment.
    """
    venv_bin_dir_name = (
        "Scripts" if system.get_platform_system() == "Windows" else "bin"
    )
    venv_bin_dir = system.get_absolute_path(os.path.join(venv_path, venv_bin_dir_name))

    potential_exe_names = []
    # Start with the most specific names
    if base_python_executable_name:
        potential_exe_names.append(base_python_executable_name)  # e.g., python3.9
        # Try to strip "python" prefix if it exists and is not just "python"
        if base_python_executable_name.startswith("python") and len(
            base_python_executable_name
        ) > len("python"):
            version_part = base_python_executable_name[len("python") :]  # e.g., "3.9"
            potential_exe_names.append(f"python{version_part}")  # python3.9

    potential_exe_names.extend(["python3", "python"])

    if system.get_platform_system() == "Windows":
        potential_exe_names = [name + ".exe" for name in potential_exe_names]

    seen_names = set()
    unique_potential_exe_names = []
    for name in potential_exe_names:
        if name not in seen_names:
            unique_potential_exe_names.append(name)
            seen_names.add(name)

    logger.debug(
        f"Looking for venv python in {venv_bin_dir} with names: {unique_potential_exe_names}"
    )
    for exe_name in unique_potential_exe_names:
        potential_path = system.get_absolute_path(os.path.join(venv_bin_dir, exe_name))
        if system.is_executable(potential_path):
            logger.info(f"Found venv python executable: {potential_path}")
            return potential_path

    logger.warning(
        f"Could not reliably determine python executable in {venv_bin_dir}. Venv structure might be incomplete or Python executable has an unexpected name."
    )
    return None


def _download_get_pip_script(
    project_path: str,
    system: System,
) -> Optional[str]:
    # Ensure get_pip_script_path is absolute for system.download_file
    get_pip_script_path = system.get_absolute_path(
        os.path.join(project_path, GET_PIP_SCRIPT_NAME)
    )
    download_success, download_err = system.download_file(
        GET_PIP_URL, get_pip_script_path
    )
    if not download_success:
        return None
    logger.info(f"Successfully downloaded {GET_PIP_SCRIPT_NAME}.")
    return get_pip_script_path


def _install_pip(
    system: System,
    venv_python_executable: str,  # Absolute path to venv python
    get_pip_script_path: str,  # Absolute path to get-pip.py script
    project_path: str,  # Absolute path to project directory
    pip_check_cmd: list[str],  # Command to check pip installation
):
    try:
        logger.info(f"Running {GET_PIP_SCRIPT_NAME} using {venv_python_executable}...")
        pip_install_cmd = [venv_python_executable, get_pip_script_path]
        pip_install_result = system.run_command(
            pip_install_cmd, cwd=project_path, capture_output=True, text=True
        )

        if pip_install_result.returncode == 0:
            logger.info(
                f"get-pip.py script executed successfully. Verifying pip installation..."
            )
            pip_verify_result = system.run_command(
                pip_check_cmd, cwd=project_path, capture_output=True, text=True
            )
            if pip_verify_result.returncode == 0:
                logger.info(
                    f"pip verified successfully in the virtual environment: {pip_verify_result.stdout.strip()}"
                )
                return True
            else:
                err_msg = (
                    pip_verify_result.stderr.strip() or pip_verify_result.stdout.strip()
                )
                logger.error(
                    f"pip installed via get-pip.py but subsequent verification failed. RC: {pip_verify_result.returncode}. Error: {err_msg}"
                )
                return False
        else:
            err_msg = (
                pip_install_result.stderr.strip() or pip_install_result.stdout.strip()
            )
            logger.error(
                f"Failed to install pip using get-pip.py. RC: {pip_install_result.returncode}. Error: {err_msg}"
            )
            return False
    finally:
        # Clean up get-pip.py script
        rm_success, rm_err = system.remove_file(
            get_pip_script_path, missing_ok=True, log_success=False
        )
        if not rm_success:
            logger.warning(f"Could not remove {get_pip_script_path}: {rm_err}")
        elif rm_success and system.file_exists(
            get_pip_script_path
        ):  # Should not happen if rm_success is True from system.remove_file
            logger.debug(f"Removed {GET_PIP_SCRIPT_NAME}.")


def _ensure_pip_in_venv(
    system: System,
    project_path: str,  # CWD for commands, should be absolute
    venv_python_executable: str,  # Absolute path to venv python
) -> bool:
    """
    Checks for pip in the venv and attempts to install it via get-pip.py if not found or not working.
    """
    logger.info(f"Checking for pip using venv Python: {venv_python_executable}")
    pip_check_cmd = [venv_python_executable, "-m", "pip", "--version"]
    pip_check_result = system.run_command(
        pip_check_cmd, cwd=project_path, capture_output=True, text=True
    )

    if pip_check_result.returncode == 0:
        logger.info(
            f"pip is available and working in the virtual environment. Version: {pip_check_result.stdout.strip()}"
        )
        return True

    logger.warning(
        f"pip check failed (RC: {pip_check_result.returncode}) or pip not found. Attempting manual installation using get-pip.py."
    )
    get_pip_script_path = _download_get_pip_script(project_path, system)
    if not get_pip_script_path:
        logger.error(
            f"Failed to download get-pip.py. Cannot proceed with pip installation."
        )
        return False

    pip_installed_successfully = _install_pip(
        system,
        venv_python_executable,
        get_pip_script_path,
        project_path,
        pip_check_cmd,
    )
    return pip_installed_successfully


def _initialize_git_repo(system: System, venv_name: str) -> bool:
    logger.info("Initializing Git repository...")
    git_init_cmd = ["git", "init"]
    git_init_result = system.run_command(git_init_cmd, capture_output=True, text=True)
    if git_init_result.returncode == 0:
        logger.info("Git repository initialized successfully.")
        gitignore_content_template, read_err = system.read_package_asset(
            "gitignore_template.txt"
        )
        if gitignore_content_template and not read_err:
            gitignore_content = gitignore_content_template.replace(
                "{{ venv_name }}", venv_name
            )
            write_success, write_err = system.write_file(
                ".gitignore", gitignore_content
            )
            if not write_success:
                logger.warning(f"Could not create .gitignore file: {write_err}")
        else:
            logger.warning(f"Could not read .gitignore template: {read_err}")
    else:
        err_msg = git_init_result.stderr.strip() or git_init_result.stdout.strip()
        logger.warning(f"Failed to initialize Git repository: {err_msg}")
        return False

    return True


def _create_virtual_environment(
    system: System,
    project_path: str,
    python_executable: str,
    venv_name: str,
) -> bool:
    """
    Creates a Python virtual environment in the specified project directory.
    """
    logger.info(
        f"Attempting to create virtual environment '{venv_name}' using Python: {python_executable}"
    )

    if not system.which(python_executable):
        logger.error(
            f"Python executable '{python_executable}' not found on PATH. Cannot create virtual environment."
        )
        return False

    venv_cmd = [python_executable, "-m", "venv", venv_name]

    venv_creation_result = system.run_command(
        venv_cmd, capture_output=True, text=True, cwd=project_path
    )
    if venv_creation_result.returncode != 0:
        err_msg = (
            venv_creation_result.stderr.strip() or venv_creation_result.stdout.strip()
        )
        logger.error(
            f"Failed to create venv '{venv_name}'. RC: {venv_creation_result.returncode}. Error: {err_msg}"
        )
        return False

    logger.info(f"Virtual environment '{venv_name}' creation command reported success.")

    venv_path = system.get_absolute_path(os.path.join(project_path, venv_name))
    base_python_exe_name = os.path.basename(python_executable)

    venv_python_exe = _determine_venv_python_executable(
        system, venv_path, base_python_exe_name
    )
    if not venv_python_exe:
        logger.error(
            f"Venv '{venv_name}' at {venv_path} created, but its Python exe not found. Pip setup skipped."
        )
        return False

    if not _ensure_pip_in_venv(system, project_path, venv_python_exe):
        logger.warning(
            f"WARNING: Failed to ensure pip in '{venv_name}'. Venv may not be fully usable."
        )
        return False

    logger.info(
        f"SUCCESS: Virtual environment '{venv_name}' with pip is ready at {venv_path}"
    )
    return True


def _restore_cwd(system: System, original_cwd: Optional[str]):
    current_cwd = system.get_cwd()
    if current_cwd != original_cwd:
        logger.debug(f"Attempting to restore CWD from {current_cwd} to {original_cwd}")
        restored_success, restored_err = system.change_cwd(original_cwd)
        if not restored_success:
            logger.error(
                f"Failed to restore original CWD {original_cwd}: {restored_err}"
            )


def setup_project_directory(
    system: System,
    project_name: str,
    base_path: str = ".",
    python_executable: str = "python3",
    venv_name: str = ".venv",
) -> Optional[str]:
    """
    Creates a project directory, initializes Git, and creates a Python virtual environment.
    """
    abs_base_path = system.get_absolute_path(base_path)
    project_path = system.get_absolute_path(os.path.join(abs_base_path, project_name))
    original_cwd: Optional[str] = system.get_cwd()

    logger.debug(f"Original CWD: {original_cwd}")

    try:
        if system.path_exists(project_path):
            logger.info(
                f"Project directory {project_path} already exists. Skipping creation and setup within it."
            )
            return project_path

        logger.info(f"Creating project directory at: {project_path}")

        mk_success, mk_err = system.make_dirs(project_path)
        if not mk_success:
            logger.error(f"Failed to create project directory {project_path}: {mk_err}")
            return None  # Critical failure if directory cannot be made

        system.change_cwd(project_path)

        # Initialize Git repository
        if not _initialize_git_repo(system, venv_name):
            logger.error(
                f"Failed to initialize Git repository in {project_path}. Project setup may be incomplete."
            )
            return project_path

        # Create virtual environment
        if not _create_virtual_environment(
            system,
            project_path,
            python_executable,
            venv_name,
        ):
            logger.error(
                f"Failed to create virtual environment '{venv_name}' in {project_path}. Project setup may be incomplete."
            )

        return project_path

    except Exception as e:
        logger.exception(
            f"An unexpected critical error occurred during project setup for '{project_name}': {e}"
        )
        return None
    finally:
        _restore_cwd(system, original_cwd)
