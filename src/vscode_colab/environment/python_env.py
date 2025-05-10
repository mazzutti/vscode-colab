import os
from typing import Dict, List

from vscode_colab.logger_config import log as logger
from vscode_colab.system import System, SystemOperationResult

PYENV_INSTALLER_URL = "https://pyenv.run"
INSTALLER_SCRIPT_NAME = "pyenv-installer.sh"


class PythonEnvManager:
    """
    Manages pyenv installation and Python version installations via pyenv.
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

    def _get_env_vars(self) -> Dict[str, str]:
        """
        Constructs environment variables needed for pyenv commands.
        """
        current_env = os.environ.copy()
        current_env["PYENV_ROOT"] = self.pyenv_root

        pyenv_bin_path = self.system.get_absolute_path(
            os.path.join(self.pyenv_root, "bin")
        )
        pyenv_shims_path = self.system.get_absolute_path(
            os.path.join(self.pyenv_root, "shims")
        )
        new_path_parts: List[str] = [pyenv_bin_path, pyenv_shims_path]
        existing_path = current_env.get("PATH", "")
        current_env["PATH"] = (
            os.pathsep.join(new_path_parts) + os.pathsep + existing_path
        )
        return current_env

    def install_pyenv(self) -> SystemOperationResult:
        """Installs the pyenv executable.
        Returns SystemOperationResult with pyenv executable path in `value` on success.
        """
        logger.info(f"Attempting to install pyenv into {self.pyenv_root}...")

        if not self.system.dir_exists(self.pyenv_root):
            mkd_res = self.system.make_dirs(self.pyenv_root)
            if not mkd_res:
                logger.error(
                    f"Failed to create PYENV_ROOT directory {self.pyenv_root}: {mkd_res.error}"
                )
                return SystemOperationResult.Err(
                    mkd_res.error or Exception("Failed to create PYENV_ROOT")
                )

        installer_script_path = self.system.get_absolute_path(
            os.path.join(self.pyenv_root, INSTALLER_SCRIPT_NAME)
        )

        download_res = self.system.download_file(
            PYENV_INSTALLER_URL, installer_script_path
        )
        if not download_res:
            logger.error(
                f"Failed to download pyenv installer from {PYENV_INSTALLER_URL}: {download_res.error}"
            )
            self.system.remove_file(
                installer_script_path, missing_ok=True, log_success=False
            )
            return SystemOperationResult.Err(
                download_res.error or Exception("Download failed")
            )

        bash_exe = self.system.which("bash")
        if not bash_exe:
            err = Exception("bash not found, cannot execute pyenv installer script.")
            logger.error(str(err))
            self.system.remove_file(
                installer_script_path, missing_ok=True, log_success=False
            )
            return SystemOperationResult.Err(err)

        installer_cmd = [bash_exe, installer_script_path]
        installer_env = os.environ.copy()
        installer_env["PYENV_ROOT"] = self.pyenv_root

        logger.info(f"Executing pyenv installer script: {installer_script_path}")
        installer_proc_result = self.system.run_command(
            installer_cmd,
            env=installer_env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.system.remove_file(
            installer_script_path, missing_ok=True, log_success=False
        )

        if installer_proc_result.returncode != 0:
            err_msg = f"Pyenv installer script failed (RC: {installer_proc_result.returncode})."
            logger.error(err_msg)
            logger.debug(f"Installer stdout: {installer_proc_result.stdout.strip()}")
            logger.debug(f"Installer stderr: {installer_proc_result.stderr.strip()}")
            return SystemOperationResult.Err(Exception(err_msg))

        logger.debug(f"pyenv installer stdout: {installer_proc_result.stdout.strip()}")
        if installer_proc_result.stderr.strip():
            logger.debug(
                f"pyenv installer stderr: {installer_proc_result.stderr.strip()}"
            )

        if not self.system.is_executable(self.pyenv_executable_path):
            err = Exception(
                f"Pyenv script ran, but executable not found at {self.pyenv_executable_path}."
            )
            logger.error(str(err))
            return SystemOperationResult.Err(err)

        logger.info("pyenv installed successfully.")
        return SystemOperationResult.Ok(value=self.pyenv_executable_path)

    @property
    def is_pyenv_installed(self) -> bool:
        """
        Checks if the pyenv executable is present and executable.
        This is a pure check and does NOT trigger installation.
        """
        is_present = self.system.is_executable(self.pyenv_executable_path)
        if is_present:
            logger.debug(f"pyenv executable found at {self.pyenv_executable_path}")
        else:
            logger.debug(f"pyenv executable not found at {self.pyenv_executable_path}")
        return is_present

    def is_python_version_installed(self, python_version: str) -> SystemOperationResult:
        """
        Checks if a specific Python version is installed by pyenv.
        Returns SystemOperationResult with boolean in `value` indicating presence.
        This method assumes pyenv is already installed and executable.
        """
        if not self.is_pyenv_installed:
            return SystemOperationResult.Err(
                Exception("Pyenv is not installed, cannot check Python versions.")
            )

        pyenv_env = self._get_env_vars()
        logger.debug(
            f"Checking if Python version {python_version} is installed by pyenv..."
        )
        versions_cmd = [self.pyenv_executable_path, "versions", "--bare"]

        versions_proc_result = self.system.run_command(
            versions_cmd, env=pyenv_env, capture_output=True, text=True, check=False
        )

        if versions_proc_result.returncode == 0:
            is_present = (
                python_version in versions_proc_result.stdout.strip().splitlines()
            )
            logger.debug(
                f"Python version '{python_version}' present in pyenv: {is_present}."
            )
            return SystemOperationResult.Ok(value=is_present)
        else:
            err_msg = f"Could not list pyenv versions (RC: {versions_proc_result.returncode})."
            logger.warning(err_msg)
            logger.debug(
                f"Pyenv versions stdout: {versions_proc_result.stdout.strip()}"
            )
            logger.debug(
                f"Pyenv versions stderr: {versions_proc_result.stderr.strip()}"
            )
            return SystemOperationResult.Err(Exception(err_msg))

    def install_python_version(
        self, python_version: str, force_reinstall: bool = False
    ) -> SystemOperationResult:
        """Installs a specific Python version using pyenv. Assumes pyenv is installed."""
        if not self.is_pyenv_installed:
            return SystemOperationResult.Err(
                Exception("Pyenv is not installed, cannot install Python version.")
            )

        pyenv_env = self._get_env_vars()
        action = "Force reinstalling" if force_reinstall else "Installing"
        logger.info(
            f"{action} Python {python_version} with pyenv. This may take around 5 minutes..."
        )

        install_cmd_list = [self.pyenv_executable_path, "install"]
        if force_reinstall:
            install_cmd_list.append("--force")
        install_cmd_list.append(python_version)

        python_build_env = pyenv_env.copy()
        python_build_env["PYTHON_CONFIGURE_OPTS"] = "--enable-shared"
        logger.info(
            f"Using PYTHON_CONFIGURE_OPTS: {python_build_env['PYTHON_CONFIGURE_OPTS']}"
        )

        install_proc_result = self.system.run_command(
            install_cmd_list,
            env=python_build_env,
            capture_output=True,
            text=True,
            check=False,
        )

        if install_proc_result.returncode == 0:
            logger.info(f"Python {python_version} installed successfully via pyenv.")
            return SystemOperationResult.Ok()
        else:
            err_msg = f"Failed to install Python {python_version} using pyenv (RC: {install_proc_result.returncode})."
            logger.error(err_msg)
            logger.debug(f"Pyenv install stdout: {install_proc_result.stdout.strip()}")
            logger.debug(f"Pyenv install stderr: {install_proc_result.stderr.strip()}")
            logger.error(
                "Ensure build dependencies are installed (see pyenv docs/wiki for your OS)."
            )
            return SystemOperationResult.Err(Exception(err_msg))

    def set_global_python_version(self, python_version: str) -> SystemOperationResult:
        """Sets the global Python version using pyenv. Assumes pyenv is installed."""
        if not self.is_pyenv_installed:
            return SystemOperationResult.Err(
                Exception("Pyenv is not installed, cannot set global Python version.")
            )

        pyenv_env = self._get_env_vars()
        logger.info(f"Setting global Python version to {python_version} using pyenv...")
        global_cmd = [self.pyenv_executable_path, "global", python_version]

        global_proc_result = self.system.run_command(
            global_cmd, env=pyenv_env, capture_output=True, text=True, check=False
        )

        if global_proc_result.returncode == 0:
            logger.info(f"Global Python version successfully set to {python_version}.")
            return SystemOperationResult.Ok()
        else:
            err_msg = f"Failed to set global Python version to {python_version} (RC: {global_proc_result.returncode})."
            logger.error(err_msg)
            logger.debug(f"Pyenv global stdout: {global_proc_result.stdout.strip()}")
            logger.debug(f"Pyenv global stderr: {global_proc_result.stderr.strip()}")
            return SystemOperationResult.Err(Exception(err_msg))

    def get_python_executable_path(self, python_version: str) -> SystemOperationResult:
        """
        Gets the path to the Python executable managed by pyenv for the given version.
        Assumes pyenv is installed and the version is set globally.
        Returns SystemOperationResult with the path in `value` on success.
        """
        if not self.is_pyenv_installed:
            return SystemOperationResult.Err(
                Exception("Pyenv is not installed, cannot get Python path.")
            )

        pyenv_env = self._get_env_vars()
        logger.debug(
            f"Verifying Python executable location for version {python_version} via 'pyenv which python'..."
        )
        which_cmd = [self.pyenv_executable_path, "which", "python"]

        which_proc_result = self.system.run_command(
            which_cmd, env=pyenv_env, capture_output=True, text=True, check=False
        )

        if which_proc_result.returncode == 0 and which_proc_result.stdout.strip():
            found_path_via_which = self.system.get_absolute_path(
                which_proc_result.stdout.strip()
            )
            if self.system.is_executable(found_path_via_which):
                logger.debug(
                    f"Python executable (via 'pyenv which python') found at: {found_path_via_which}"
                )
                try:
                    resolved_path = self.system.get_absolute_path(
                        os.path.realpath(found_path_via_which)
                    )
                    logger.debug(f"Resolved Python executable path: {resolved_path}")

                    expected_version_dir = self.system.get_absolute_path(
                        os.path.join(self.pyenv_root, "versions", python_version)
                    )
                    if resolved_path.startswith(expected_version_dir):
                        return SystemOperationResult.Ok(value=resolved_path)
                    else:
                        logger.warning(
                            f"'pyenv which python' resolved to '{resolved_path}', which is not in the expected directory for version '{python_version}' ({expected_version_dir}). This might indicate the global pyenv version is not '{python_version}'."
                        )
                except Exception as e_real:
                    logger.warning(
                        f"Could not resolve real path for {found_path_via_which}: {e_real}. Proceeding with direct path check."
                    )
            else:
                logger.warning(
                    f"'pyenv which python' provided a non-executable path: {found_path_via_which}"
                )
        else:
            logger.warning(
                f"'pyenv which python' failed (RC: {which_proc_result.returncode}) or returned empty. Stderr: {which_proc_result.stderr.strip() or 'N/A'}"
            )

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
            return SystemOperationResult.Ok(value=expected_python_path_direct)

        err = Exception(
            f"Python executable for version {python_version} could not be reliably located."
        )
        logger.error(str(err))
        return SystemOperationResult.Err(err)

    def setup_and_get_python_executable(
        self,
        python_version: str,
        force_reinstall_python: bool = False,
    ) -> SystemOperationResult:
        """
        Ensures pyenv is installed, installs the specified Python version (if needed),
        sets it as global, and returns the path to its executable.

        Returns:
            SystemOperationResult: Success with the path to the Python executable in `value`,
                                   or failure with an error.
        """
        if not self.is_pyenv_installed:
            logger.info("Pyenv is not installed. Attempting to install pyenv.")
            install_pyenv_res = self.install_pyenv()
            if not install_pyenv_res:
                return SystemOperationResult.Err(
                    install_pyenv_res.error
                    or Exception("Pyenv installation failed during setup.")
                )

        version_installed_check_res = self.is_python_version_installed(python_version)
        if not version_installed_check_res:
            return SystemOperationResult.Err(
                version_installed_check_res.error
                or Exception("Failed to check installed Python versions")
            )

        is_python_already_installed = version_installed_check_res.value

        if not is_python_already_installed or force_reinstall_python:
            install_op_res = self.install_python_version(
                python_version, force_reinstall_python
            )
            if not install_op_res:
                return SystemOperationResult.Err(
                    install_op_res.error
                    or Exception(f"Failed to install Python {python_version}")
                )

        set_global_op_res = self.set_global_python_version(python_version)
        if not set_global_op_res:
            return SystemOperationResult.Err(
                set_global_op_res.error
                or Exception(f"Failed to set Python {python_version} as global")
            )

        return self.get_python_executable_path(python_version)
