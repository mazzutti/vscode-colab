import os
from typing import List, Optional

from vscode_colab.logger_config import log as logger
from vscode_colab.system import System
from vscode_colab.utils import SystemOperationResult

GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
GET_PIP_SCRIPT_NAME = "get-pip.py"


def _determine_venv_python_executable(
    system: System,
    venv_path: str,  # Absolute path to venv directory
    base_python_executable_name: str,  # e.g., "python3.9" or "python"
) -> Optional[str]:
    """
    Attempts to determine the path to the Python executable within a created
    Linux virtual environment.
    """
    venv_bin_dir = system.get_absolute_path(os.path.join(venv_path, "bin"))

    potential_exe_names: List[str] = []
    # Start with the most specific names derived from the base Python executable
    if base_python_executable_name:
        potential_exe_names.append(base_python_executable_name)  # e.g., python3.9
        # Attempt to add variants like "pythonX.Y" if base is "pythonX.Y.Z"
        # or if base is "pythonX" then "pythonX" is already there.
        if base_python_executable_name.startswith("python"):
            version_part = base_python_executable_name[
                len("python") :
            ]  # e.g., "3.9" or "3.9.12"
            if version_part.count(".") > 1:  # like 3.9.12
                short_version = ".".join(version_part.split(".")[:2])  # 3.9
                potential_exe_names.append(f"python{short_version}")

    # Add common fallbacks
    potential_exe_names.extend(["python3", "python"])

    # Remove duplicates while preserving order (important for preference)
    unique_potential_exe_names: List[str] = list(dict.fromkeys(potential_exe_names))

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
    project_path: str,  # Should be absolute for clarity
    system: System,
) -> SystemOperationResult[str, Exception]:
    get_pip_script_path = system.get_absolute_path(
        os.path.join(project_path, GET_PIP_SCRIPT_NAME)
    )
    download_res = system.download_file(GET_PIP_URL, get_pip_script_path)
    if not download_res:
        return SystemOperationResult.Err(
            download_res.error or Exception("Failed to download get-pip.py"),
            message=f"Failed to download {GET_PIP_URL}: {download_res.message}",
        )
    logger.info(
        f"Successfully downloaded {GET_PIP_SCRIPT_NAME} to {get_pip_script_path}."
    )
    return SystemOperationResult.Ok(get_pip_script_path)


def _install_pip_with_script(
    system: System,
    venv_python_executable: str,  # Absolute path to venv python
    get_pip_script_path: str,  # Absolute path to get-pip.py script
    project_path: str,  # Absolute path to project directory (CWD for command)
    pip_check_cmd: List[str],
) -> SystemOperationResult[None, Exception]:
    try:
        logger.info(f"Running {get_pip_script_path} using {venv_python_executable}...")
        pip_install_cmd = [venv_python_executable, get_pip_script_path]

        try:
            pip_install_result = system.run_command(
                pip_install_cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as e_run:
            logger.error(f"Failed to execute get-pip.py script: {e_run}")
            return SystemOperationResult.Err(
                e_run, message="Execution of get-pip.py failed"
            )

        if pip_install_result.returncode != 0:
            err_msg_install = (
                pip_install_result.stderr.strip() or pip_install_result.stdout.strip()
            )
            full_err_msg_install = f"Failed to install pip using get-pip.py. RC: {pip_install_result.returncode}. Error: {err_msg_install}"
            logger.error(full_err_msg_install)
            return SystemOperationResult.Err(
                Exception("get-pip.py execution failed"), message=full_err_msg_install
            )

        logger.info(
            f"get-pip.py script executed successfully. Verifying pip installation..."
        )
        try:
            pip_verify_result = system.run_command(
                pip_check_cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as e_verify_run:
            logger.error(f"Failed to execute pip verification command: {e_verify_run}")
            return SystemOperationResult.Err(
                e_verify_run, message="Pip verification command failed"
            )

        if pip_verify_result.returncode != 0:
            err_msg_verify = (
                pip_verify_result.stderr.strip() or pip_verify_result.stdout.strip()
            )
            full_err_msg_verify = f"pip installed via get-pip.py but subsequent verification failed. RC: {pip_verify_result.returncode}. Error: {err_msg_verify}"
            logger.error(full_err_msg_verify)
            return SystemOperationResult.Err(
                Exception("Pip verification failed"), message=full_err_msg_verify
            )

        logger.info(
            f"pip verified successfully in the virtual environment: {pip_verify_result.stdout.strip()}"
        )
        return SystemOperationResult.Ok()

    finally:
        # Clean up get-pip.py script
        rm_res = system.remove_file(
            get_pip_script_path,
            missing_ok=True,
            log_success=False,
        )
        if not rm_res:  # Log if removal failed
            logger.warning(f"Could not remove {get_pip_script_path}: {rm_res.message}")


def _ensure_pip_in_venv(
    system: System,
    project_path: str,  # CWD for commands, should be absolute
    venv_python_executable: str,  # Absolute path to venv python
) -> SystemOperationResult[None, Exception]:
    """
    Checks for pip in the venv and attempts to install it via get-pip.py if not found or not working.
    """
    logger.info(f"Checking for pip using venv Python: {venv_python_executable}")
    pip_check_cmd = [venv_python_executable, "-m", "pip", "--version"]

    try:
        pip_check_result_proc = system.run_command(
            pip_check_cmd, cwd=project_path, capture_output=True, text=True, check=False
        )
    # Catch if run_command itself fails (e.g. venv_python_executable missing)
    except Exception as e_check_run:
        logger.error(f"Failed to run pip check command: {e_check_run}")
        return SystemOperationResult.Err(
            e_check_run, message="Execution of pip check command failed."
        )

    if pip_check_result_proc.returncode == 0:
        logger.info(
            f"pip is available and working in the virtual environment. Version: {pip_check_result_proc.stdout.strip()}"
        )
        return SystemOperationResult.Ok()

    logger.warning(
        f"pip check failed (RC: {pip_check_result_proc.returncode}) or pip not found. Stderr: {pip_check_result_proc.stderr.strip()}. Stdout: {pip_check_result_proc.stdout.strip()}. Attempting manual installation using get-pip.py."
    )

    download_script_res = _download_get_pip_script(project_path, system)
    if not download_script_res:
        return SystemOperationResult.Err(
            download_script_res.error or Exception("Download of get-pip.py failed"),
            message=f"Failed to download get-pip.py. Cannot proceed. {download_script_res.message}",
        )

    return _install_pip_with_script(
        system,
        venv_python_executable,
        download_script_res.value,  # Path to script
        project_path,
        pip_check_cmd,
    )


def _initialize_git_repo(
    system: System, project_path: str, venv_name: str
) -> SystemOperationResult[None, Exception]:
    logger.info("Initializing Git repository...")
    git_init_cmd = ["git", "init"]
    original_cwd = system.get_cwd()

    change_cwd_res = system.change_cwd(project_path)
    if not change_cwd_res:
        return SystemOperationResult.Err(
            change_cwd_res.error or Exception("CWD change failed"),
            message=f"Failed to change CWD to {project_path} for git init: {change_cwd_res.message}",
        )

    try:
        git_init_proc = system.run_command(
            git_init_cmd, capture_output=True, text=True, check=False
        )
    except Exception as e_git_run:
        system.change_cwd(original_cwd)  # Attempt to restore CWD
        logger.error(f"Failed to execute 'git init': {e_git_run}")
        return SystemOperationResult.Err(
            e_git_run, message="Execution of 'git init' failed."
        )

    if git_init_proc.returncode != 0:
        err_msg = git_init_proc.stderr.strip() or git_init_proc.stdout.strip()
        system.change_cwd(original_cwd)  # Restore CWD
        logger.warning(f"Failed to initialize Git repository: {err_msg}")
        return SystemOperationResult.Err(
            Exception("git init command failed"), message=f"git init error: {err_msg}"
        )

    logger.info("Git repository initialized successfully.")
    gitignore_template_res = system.read_package_asset("gitignore_template.txt")
    if not gitignore_template_res.is_ok or not gitignore_template_res.value:
        logger.warning(
            f"Could not read .gitignore template: {gitignore_template_res.message}"
        )

    gitignore_content = gitignore_template_res.value.replace(  # type: ignore
        "{{ venv_name }}", venv_name
    )
    write_res = system.write_file(
        os.path.join(project_path, ".gitignore"), gitignore_content
    )  # Ensure writing to correct path
    if not write_res:
        logger.warning(f"Could not create .gitignore file: {write_res.message}")

    system.change_cwd(original_cwd)  # Restore CWD
    return SystemOperationResult.Ok()


def _create_virtual_environment(
    system: System,
    project_path: str,  # Absolute path
    python_executable: str,  # Name or path of python to use for venv creation
    venv_name: str,
) -> SystemOperationResult[str, Exception]:  # Returns path to venv python on success
    """
    Creates a Python virtual environment in the specified project directory.
    """
    logger.info(
        f"Attempting to create virtual environment '{venv_name}' in '{project_path}' using Python: {python_executable}"
    )

    if not system.which(python_executable):  # Check if base python is findable
        err_msg = f"Base Python executable '{python_executable}' not found on PATH. Cannot create virtual environment."
        logger.error(err_msg)
        return SystemOperationResult.Err(
            FileNotFoundError(python_executable), message=err_msg
        )

    venv_cmd = [python_executable, "-m", "venv", venv_name]

    try:
        venv_creation_proc = system.run_command(
            venv_cmd, capture_output=True, text=True, cwd=project_path, check=False
        )
    except Exception as e_venv_run:
        logger.error(f"Failed to execute venv creation command: {e_venv_run}")
        return SystemOperationResult.Err(
            e_venv_run, message="Execution of venv command failed."
        )

    if venv_creation_proc.returncode != 0:
        err_msg_venv = (
            venv_creation_proc.stderr.strip() or venv_creation_proc.stdout.strip()
        )
        full_err_msg_venv = f"Failed to create venv '{venv_name}'. RC: {venv_creation_proc.returncode}. Error: {err_msg_venv}"
        logger.error(full_err_msg_venv)
        return SystemOperationResult.Err(
            Exception("Venv creation command failed"), message=full_err_msg_venv
        )

    logger.info(f"Virtual environment '{venv_name}' creation command reported success.")

    abs_venv_path = system.get_absolute_path(os.path.join(project_path, venv_name))
    base_python_exe_name = os.path.basename(python_executable)

    venv_python_exe_path = _determine_venv_python_executable(
        system, abs_venv_path, base_python_exe_name
    )
    if not venv_python_exe_path:
        err_msg_pip = f"Venv '{venv_name}' at {abs_venv_path} created, but its Python exe not found. Pip setup skipped."
        logger.error(err_msg_pip)
        return SystemOperationResult.Err(
            FileNotFoundError("Venv Python executable"), message=err_msg_pip
        )

    ensure_pip_res = _ensure_pip_in_venv(system, project_path, venv_python_exe_path)
    if not ensure_pip_res:
        logger.warning(
            f"WARNING: Failed to ensure pip in '{venv_name}'. Venv may not be fully usable. Error: {ensure_pip_res.message}"
        )
        return SystemOperationResult.Err(
            ensure_pip_res.error or Exception("Pip setup failed"),
            message=f"Pip setup in venv failed: {ensure_pip_res.message}",
        )

    logger.info(
        f"SUCCESS: Virtual environment '{venv_name}' with pip is ready at {abs_venv_path}. Venv Python: {venv_python_exe_path}"
    )
    return SystemOperationResult.Ok(venv_python_exe_path)


def setup_project_directory(
    system: System,
    project_name: str,
    base_path: str = ".",  # Relative to CWD at time of call
    python_executable: str = "python3",  # Python for creating the venv
    venv_name: str = ".venv",
) -> SystemOperationResult[str, Exception]:  # Returns absolute project path on success
    """
    Creates a project directory, initializes Git, and creates a Python virtual environment.
    Operations are performed relative to the project_path once created.
    """
    abs_base_path = system.get_absolute_path(base_path)
    project_path = system.get_absolute_path(os.path.join(abs_base_path, project_name))

    logger.debug(f"Attempting to set up project directory: {project_path}")

    if system.path_exists(project_path):
        logger.info(
            f"Project directory {project_path} already exists. Skipping creation and setup within it."
        )
        return SystemOperationResult.Ok(project_path)

    logger.info(f"Creating project directory at: {project_path}")
    mk_dir_res = system.make_dirs(project_path)
    if not mk_dir_res:
        return SystemOperationResult.Err(
            mk_dir_res.error or OSError("Failed to create project directory"),
            message=f"Failed to create project directory {project_path}: {mk_dir_res.message}",
        )

    # Initialize Git repository
    git_init_res = _initialize_git_repo(system, project_path, venv_name)
    if not git_init_res:
        logger.error(
            f"Failed to initialize Git repository in {project_path}. Project setup may be incomplete. Error: {git_init_res.message}"
        )
        # For now, let's consider it non-fatal for directory setup itself.

    # Create virtual environment
    # Note: _create_virtual_environment will use project_path as CWD for its commands
    venv_res = _create_virtual_environment(
        system,
        project_path,
        python_executable,
        venv_name,
    )
    if not venv_res:
        logger.error(
            f"Failed to create virtual environment '{venv_name}' in {project_path}. Project setup may be incomplete. Error: {venv_res.message}"
        )
        # This is more critical than git init failure.
        return SystemOperationResult.Err(
            venv_res.error or Exception("Venv creation failed"),
            message=f"Virtual environment setup failed: {venv_res.message}",
        )

    logger.info(f"Project '{project_name}' successfully set up at {project_path}")
    return SystemOperationResult.Ok(project_path)
