import os
import tempfile
from typing import Dict, List, Optional, Set

from vscode_colab.logger_config import log as logger
from vscode_colab.system import System
from vscode_colab.utils import SystemOperationResult

PYENV_INSTALLER_URL = "https://pyenv.run"
INSTALLER_SCRIPT_NAME = "pyenv-installer.sh"

# Common pyenv build dependencies for Debian/Ubuntu-based systems
# Source: https://github.com/pyenv/pyenv/wiki#suggested-build-environment
PYENV_BUILD_DEPENDENCIES: Set[str] = {
    "build-essential",
    "curl",
    "libbz2-dev",
    "libffi-dev",
    "liblzma-dev",
    "libncurses5-dev",
    "libncursesw5-dev",
    "libreadline-dev",
    "libsqlite3-dev",
    "libssl-dev",
    "libxml2-dev",
    "libxmlsec1-dev",
    "llvm",
    "make",
    "tk-dev",
    "wget",
    "xz-utils",
    "zlib1g-dev",
}


class PythonEnvManager:
    """
    Manages pyenv installation and Python version installations via pyenv on Linux.
    """

    def __init__(self, system: System) -> None:
        """
        Initializes the PythonEnvManager with a System instance.
        """
        self.system = system
        self.pyenv_root = self.system.expand_user_path("~/.pyenv")
        self.pyenv_executable_path = self.system.get_absolute_path(
            os.path.join(self.pyenv_root, "bin", "pyenv")
        )

    def _get_pyenv_env_vars(self) -> Dict[str, str]:
        """
        Constructs environment variables needed for pyenv commands.
        """
        current_env = os.environ.copy()
        current_env["PYENV_ROOT"] = self.pyenv_root

        # pyenv's own init script would typically add these to the shell's PATH
        # For direct command execution, ensure pyenv's bin and shims are in PATH
        pyenv_bin_path = self.system.get_absolute_path(
            os.path.join(self.pyenv_root, "bin")
        )
        pyenv_shims_path = self.system.get_absolute_path(
            os.path.join(self.pyenv_root, "shims")
        )

        new_path_parts: List[str] = [pyenv_bin_path, pyenv_shims_path]
        existing_path = current_env.get("PATH", "")
        if existing_path:
            new_path_parts.append(existing_path)
        current_env["PATH"] = os.pathsep.join(new_path_parts)

        return current_env

    def install_pyenv_dependencies(self) -> SystemOperationResult[None, Exception]:
        """
        Installs pyenv build dependencies using apt. Assumes a Debian/Ubuntu-based system.
        Requires sudo privileges.
        """
        logger.info("Attempting to install pyenv build dependencies...")

        # Check for sudo
        sudo_path = self.system.which("sudo")
        if not sudo_path:
            msg = "sudo command not found. Cannot install dependencies."
            logger.warning(msg)
            return SystemOperationResult.Err(FileNotFoundError("sudo"), message=msg)

        apt_path = self.system.which("apt")
        if not apt_path:
            msg = "apt command not found. Cannot install dependencies."
            logger.warning(msg)
            return SystemOperationResult.Err(FileNotFoundError("apt"), message=msg)

        # Step 1: apt update
        update_cmd = [sudo_path, apt_path, "update", "-y"]

        logger.info(f"Running: {' '.join(update_cmd)}")
        try:
            update_proc = self.system.run_command(
                update_cmd, capture_output=True, text=True, check=False
            )
        except Exception as e_update_run:
            logger.error(f"Failed to execute apt-get update: {e_update_run}")
            return SystemOperationResult.Err(
                e_update_run, message="apt-get update execution failed"
            )

        if update_proc.returncode != 0:
            err_msg = f"apt-get update failed (RC: {update_proc.returncode}). Stdout: {update_proc.stdout.strip()} Stderr: {update_proc.stderr.strip()}"
            logger.error(err_msg)
            return SystemOperationResult.Err(
                Exception("apt update failed"), message=err_msg
            )
        logger.info("apt update completed successfully.")

        # Step 2: apt install dependencies
        install_cmd = [sudo_path, apt_path, "install", "-y"]
        install_cmd.extend(sorted(list(PYENV_BUILD_DEPENDENCIES)))

        logger.info(f"Running: {' '.join(install_cmd)} (this might take a moment)")
        try:
            install_proc = self.system.run_command(
                install_cmd, capture_output=True, text=True, check=False
            )
        except Exception as e_install_run:
            logger.error(
                f"Failed to execute apt install for pyenv dependencies: {e_install_run}"
            )
            return SystemOperationResult.Err(
                e_install_run, message="apt install dependencies execution failed"
            )

        if install_proc.returncode != 0:
            err_msg_install = f"apt install pyenv dependencies failed (RC: {install_proc.returncode}). Stdout: {install_proc.stdout.strip()} Stderr: {install_proc.stderr.strip()}"
            logger.error(err_msg_install)
            logger.warning(
                "One or more dependencies might have failed to install. Check apt output above."
            )
            return SystemOperationResult.Err(
                Exception("apt install dependencies failed"),
                message=err_msg_install,
            )

        logger.info("Successfully installed pyenv build dependencies.")
        return SystemOperationResult.Ok()

    def install_pyenv(
        self, attempt_to_install_deps: bool = True
    ) -> SystemOperationResult[str, Exception]:
        """
        Installs the pyenv executable.
        Returns SystemOperationResult with pyenv executable path in `value` on success.
        """
        logger.info(f"Attempting to install pyenv into {self.pyenv_root}...")

        if attempt_to_install_deps:
            logger.info("Checking and installing pyenv build dependencies first...")
            deps_res = self.install_pyenv_dependencies()
            if not deps_res:
                logger.warning(
                    f"Failed to install pyenv dependencies: {deps_res.message}. Pyenv installation might fail."
                )

        # The pyenv installer script expects to create PYENV_ROOT or find it as a valid git repo.

        temp_installer_script_path: Optional[str] = None
        try:
            # Create a temporary file to download the installer script to.
            # We use delete=False because we need to pass the name to an external command (bash).
            # We will manually delete it in the finally block.
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".sh", prefix="pyenv-installer-"
            ) as tf:
                temp_installer_script_path = tf.name

            logger.debug(
                f"Downloading pyenv installer to temporary path: {temp_installer_script_path}"
            )
            download_res = self.system.download_file(
                PYENV_INSTALLER_URL, temp_installer_script_path
            )
            if not download_res:
                return SystemOperationResult.Err(
                    download_res.error or Exception("Download failed"),
                    message=f"Failed to download pyenv installer from {PYENV_INSTALLER_URL} to {temp_installer_script_path}: {download_res.message}",
                )

            bash_exe = self.system.which("bash")
            if not bash_exe:
                err = FileNotFoundError(
                    "bash not found, cannot execute pyenv installer script."
                )
                logger.error(err.args[0])
                return SystemOperationResult.Err(err, message=err.args[0])

            installer_cmd = [bash_exe, temp_installer_script_path]
            # PYENV_ROOT is often set as an env var for the installer script itself
            pyenv_installer_env = os.environ.copy()
            pyenv_installer_env["PYENV_ROOT"] = self.pyenv_root

            logger.info(
                f"Executing pyenv installer script: {' '.join(installer_cmd)} with PYENV_ROOT={self.pyenv_root}"
            )

            installer_proc_result = self.system.run_command(
                installer_cmd,
                env=pyenv_installer_env,
                capture_output=True,
                text=True,
                check=False,  # We check returncode manually
            )

            if installer_proc_result.returncode != 0:
                err_msg = [
                    f"Pyenv installer script failed (RC: {installer_proc_result.returncode})."
                ]
                if installer_proc_result.stdout:
                    err_msg.append(
                        f"Pyenv installer script stdout: {installer_proc_result.stdout.strip()}"
                    )
                if installer_proc_result.stderr:
                    err_msg.append(
                        f"Pyenv installer script stderr: {installer_proc_result.stderr.strip()}"
                    )
                err_msg = "\n".join(err_msg)

                logger.error(err_msg)
                return SystemOperationResult.Err(
                    Exception("Pyenv installer script failed"), message=err_msg
                )

            if installer_proc_result.stdout:
                logger.info(
                    f"pyenv installer stdout: {installer_proc_result.stdout.strip()}"
                )
            if installer_proc_result.stderr:
                logger.error(
                    f"pyenv installer stderr: {installer_proc_result.stderr.strip()}"
                )

            if not self.system.is_executable(self.pyenv_executable_path):
                err = Exception(
                    f"Pyenv installer script ran, but pyenv executable not found at {self.pyenv_executable_path}."
                )
                logger.error(err.args[0])
                return SystemOperationResult.Err(err, message=err.args[0])

            logger.info(
                f"pyenv installed successfully into {self.pyenv_root}. Executable: {self.pyenv_executable_path}"
            )
            return SystemOperationResult.Ok(value=self.pyenv_executable_path)

        except (
            Exception
        ) as e_install_run:  # Catch exceptions from run_command or other operations
            logger.error(
                f"An exception occurred during pyenv installation process: {e_install_run}"
            )
            return SystemOperationResult.Err(
                e_install_run,
                message=f"Pyenv installation process failed: {e_install_run}",
            )
        finally:
            if temp_installer_script_path:
                logger.debug(
                    f"Removing temporary installer script: {temp_installer_script_path}"
                )
                self.system.remove_file(
                    temp_installer_script_path, missing_ok=True, log_success=False
                )

    @property
    def is_pyenv_installed(self) -> bool:
        """Checks if the pyenv executable is present and executable."""
        is_present = self.system.is_executable(self.pyenv_executable_path)
        logger.debug(
            f"pyenv executable {'found' if is_present else 'not found'} at {self.pyenv_executable_path}"
        )
        return is_present

    def is_python_version_installed(
        self, python_version: str
    ) -> SystemOperationResult[bool, Exception]:
        """Checks if a specific Python version is installed by pyenv."""
        if not self.is_pyenv_installed:
            return SystemOperationResult.Err(
                Exception("Pyenv is not installed, cannot check Python versions.")
            )

        pyenv_env = self._get_pyenv_env_vars()
        logger.debug(
            f"Checking if Python version {python_version} is installed by pyenv..."
        )
        versions_cmd = [self.pyenv_executable_path, "versions", "--bare"]

        try:
            versions_proc_result = self.system.run_command(
                versions_cmd, env=pyenv_env, capture_output=True, text=True, check=False
            )
        except Exception as e_run:
            return SystemOperationResult.Err(
                e_run, message=f"Failed to run 'pyenv versions': {e_run}"
            )

        if versions_proc_result.returncode == 0:
            installed_versions = versions_proc_result.stdout.strip().splitlines()
            is_present = python_version in installed_versions
            logger.debug(
                f"Python version '{python_version}' present in pyenv: {is_present}. Installed: {installed_versions}"
            )
            return SystemOperationResult.Ok(is_present)
        else:
            err_msg = (
                f"Could not list pyenv versions (RC: {versions_proc_result.returncode}). "
                f"Stdout: {versions_proc_result.stdout.strip()} Stderr: {versions_proc_result.stderr.strip()}"
            )
            logger.warning(err_msg)
            return SystemOperationResult.Err(
                Exception("Failed to list pyenv versions"), message=err_msg
            )

    def install_python_version(
        self, python_version: str, force_reinstall: bool = False
    ) -> SystemOperationResult[None, Exception]:
        """Installs a specific Python version using pyenv. Assumes pyenv is installed."""
        if not self.is_pyenv_installed:
            return SystemOperationResult.Err(
                Exception("Pyenv is not installed, cannot install Python version.")
            )

        pyenv_env = self._get_pyenv_env_vars()
        action = "Force reinstalling" if force_reinstall else "Installing"
        logger.info(
            f"{action} Python {python_version} with pyenv. This may take around 5-10 minutes..."
        )

        install_cmd_list = [self.pyenv_executable_path, "install"]
        if force_reinstall:
            install_cmd_list.append("--force")
        install_cmd_list.append(python_version)

        # Add PYTHON_CONFIGURE_OPTS for shared library, crucial for some tools like venv/virtualenv with pyenv python
        python_build_env = pyenv_env.copy()
        python_build_env["PYTHON_CONFIGURE_OPTS"] = "--enable-shared"
        # Can also add CFLAGS for optimizations if needed, e.g.
        # python_build_env["CFLAGS"] = "-O2 -march=native" (be careful with march=native in shared envs)
        logger.info(
            f"Using PYTHON_CONFIGURE_OPTS: {python_build_env['PYTHON_CONFIGURE_OPTS']}"
        )

        try:
            install_proc_result = self.system.run_command(
                install_cmd_list,
                env=python_build_env,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as e_run:
            return SystemOperationResult.Err(
                e_run,
                message=f"Failed to run 'pyenv install {python_version}': {e_run}",
            )

        if install_proc_result.returncode == 0:
            logger.info(f"Python {python_version} installed successfully via pyenv.")
            return SystemOperationResult.Ok()

        err_msg = (
            f"Failed to install Python {python_version} using pyenv (RC: {install_proc_result.returncode}). "
            f"Stdout: {install_proc_result.stdout.strip()} Stderr: {install_proc_result.stderr.strip()}"
        )
        logger.error(err_msg)
        logger.error(
            "Ensure build dependencies are installed (see pyenv docs/wiki or try `install_pyenv_dependencies()`)."
        )
        return SystemOperationResult.Err(
            Exception(f"Pyenv install {python_version} failed"), message=err_msg
        )

    def set_global_python_version(
        self, python_version: str
    ) -> SystemOperationResult[None, Exception]:
        """Sets the global Python version using pyenv. Assumes pyenv is installed."""
        if not self.is_pyenv_installed:
            return SystemOperationResult.Err(
                Exception("Pyenv is not installed, cannot set global Python version.")
            )

        pyenv_env = self._get_pyenv_env_vars()
        logger.info(f"Setting global Python version to {python_version} using pyenv...")
        global_cmd = [self.pyenv_executable_path, "global", python_version]

        try:
            global_proc_result = self.system.run_command(
                global_cmd, env=pyenv_env, capture_output=True, text=True, check=False
            )
        except Exception as e_run:
            return SystemOperationResult.Err(
                e_run, message=f"Failed to run 'pyenv global {python_version}': {e_run}"
            )

        if global_proc_result.returncode == 0:
            logger.info(f"Global Python version successfully set to {python_version}.")
            return SystemOperationResult.Ok()

        err_msg = (
            f"Failed to set global Python version to {python_version} (RC: {global_proc_result.returncode}). "
            f"Stdout: {global_proc_result.stdout.strip()} Stderr: {global_proc_result.stderr.strip()}"
        )
        logger.error(err_msg)
        return SystemOperationResult.Err(
            Exception(f"pyenv global {python_version} failed"), message=err_msg
        )

    def get_python_executable_path(
        self, python_version: str
    ) -> SystemOperationResult[str, Exception]:
        """
        Gets the path to the Python executable managed by pyenv for the given version.
        Assumes pyenv is installed and the version is set globally or is otherwise findable by `pyenv which`.
        """
        if not self.is_pyenv_installed:
            return SystemOperationResult.Err(
                Exception("Pyenv is not installed, cannot get Python path.")
            )

        pyenv_env = self._get_pyenv_env_vars()
        logger.debug(
            f"Verifying Python executable for version {python_version} via 'pyenv which python'..."
        )
        # 'pyenv which python' should give the path for the currently active python version (e.g., global)
        which_cmd = [self.pyenv_executable_path, "which", "python"]

        try:
            which_proc_result = self.system.run_command(
                which_cmd, env=pyenv_env, capture_output=True, text=True, check=False
            )
        except Exception as e_run:
            return SystemOperationResult.Err(
                e_run, message=f"Failed to run 'pyenv which python': {e_run}"
            )

        found_path_via_which: Optional[str] = None
        if which_proc_result.returncode != 0 or not which_proc_result.stdout.strip():
            message = (
                f"pyenv which python failed (RC: {which_proc_result.returncode}) or returned empty. "
                f"Stdout: {which_proc_result.stdout.strip()} Stderr: {which_proc_result.stderr.strip()}"
            )
            logger.warning(message)

        candidate_path = self.system.get_absolute_path(which_proc_result.stdout.strip())

        if not self.system.is_executable(candidate_path):
            logger.warning(
                f"'pyenv which python' provided a non-executable path: {candidate_path}"
            )

        try:
            # Resolve symlinks to ensure we're checking the actual binary's location
            resolved_path = self.system.get_absolute_path(
                os.path.realpath(candidate_path)
            )
            expected_version_dir_prefix = self.system.get_absolute_path(
                os.path.join(self.pyenv_root, "versions", python_version)
            )
            # Check if the resolved path is within the expected version's directory
            if resolved_path.startswith(expected_version_dir_prefix):
                logger.debug(
                    f"Python executable for '{python_version}' (via 'pyenv which') found at: {resolved_path}"
                )
                found_path_via_which = resolved_path
            else:
                message = (
                    f"'pyenv which python' resolved to '{resolved_path}', which is not in the expected directory "
                    f"for version '{python_version}' ({expected_version_dir_prefix}). This might indicate the "
                    f"global pyenv version is not '{python_version}' or pyenv state is unexpected."
                )
                logger.warning(message)
        except Exception as e_real:  # os.path.realpath can fail
            logger.warning(
                f"Could not resolve real path for {candidate_path}: {e_real}. Using direct path check."
            )

        if found_path_via_which:
            return SystemOperationResult.Ok(found_path_via_which)

        # Fallback: Construct the path directly. This is less robust if shims/global aren't set.
        # However, if 'pyenv global <version>' was successful, this should be correct.
        expected_python_path_direct = self.system.get_absolute_path(
            os.path.join(self.pyenv_root, "versions", python_version, "bin", "python")
        )
        logger.debug(
            f"Checking direct path for Python {python_version}: {expected_python_path_direct}"
        )
        if self.system.is_executable(expected_python_path_direct):
            logger.info(
                f"Python executable for version {python_version} found at direct path: {expected_python_path_direct}"
            )
            return SystemOperationResult.Ok(expected_python_path_direct)

        err_msg_final = f"Python executable for version {python_version} could not be reliably located via 'pyenv which' or direct path."
        logger.error(err_msg_final)
        return SystemOperationResult.Err(
            FileNotFoundError(err_msg_final), message=err_msg_final
        )

    def setup_and_get_python_executable(
        self,
        python_version: str,
        force_reinstall_python: bool = False,
        attempt_pyenv_dependency_install: bool = True,  # New parameter
    ) -> SystemOperationResult[str, Exception]:
        """
        Ensures pyenv is installed (optionally installing its deps), installs the specified Python version
        (if needed or forced), sets it as global, and returns the path to its executable.
        """
        if not self.is_pyenv_installed:
            logger.info("Pyenv is not installed. Attempting to install pyenv.")
            # Pass the dependency install flag to install_pyenv
            install_pyenv_res = self.install_pyenv(
                attempt_to_install_deps=attempt_pyenv_dependency_install
            )
            if not install_pyenv_res:
                return SystemOperationResult.Err(
                    install_pyenv_res.error
                    or Exception("Pyenv installation failed during setup."),
                    message=f"Pyenv installation failed: {install_pyenv_res.message}",
                )

        version_installed_check_res = self.is_python_version_installed(python_version)
        if not version_installed_check_res:
            return SystemOperationResult.Err(
                version_installed_check_res.error
                or Exception("Failed to check installed Python versions"),
                message=f"Failed to check installed Python versions: {version_installed_check_res.message}",
            )

        is_python_already_installed = version_installed_check_res.value

        if not is_python_already_installed or force_reinstall_python:
            install_op_res = self.install_python_version(
                python_version, force_reinstall_python
            )
            if not install_op_res:
                return SystemOperationResult.Err(
                    install_op_res.error
                    or Exception(f"Failed to install Python {python_version}"),
                    message=f"Failed to install Python {python_version}: {install_op_res.message}",
                )
        else:
            logger.info(
                f"Python version {python_version} is already installed. Skipping installation."
            )

        set_global_op_res = self.set_global_python_version(python_version)
        if not set_global_op_res:
            return SystemOperationResult.Err(
                set_global_op_res.error
                or Exception(f"Failed to set Python {python_version} as global"),
                message=f"Failed to set Python {python_version} as global: {set_global_op_res.message}",
            )

        return self.get_python_executable_path(python_version)
