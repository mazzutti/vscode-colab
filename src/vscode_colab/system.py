import importlib.resources
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Union

import requests

from vscode_colab.logger_config import log as logger
from vscode_colab.utils import (  # E is the TypeVar for Exception
    E,
    SystemOperationResult,
)


class System:
    """
    A facade for interacting with the Linux operating system.
    This class centralizes OS-level operations to improve testability and
    isolate dependencies on modules like `os`, `shutil`, `subprocess`, etc.
    It is tailored for Linux environments as expected in Colab/Kaggle.
    """

    def run_command(
        self,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,  # If True, will raise CalledProcessError on non-zero exit
        stderr_to_stdout: bool = True,
    ) -> subprocess.CompletedProcess:
        """
        Executes a system command using `subprocess.run` with configurable options.
        This method directly returns subprocess.CompletedProcess. Other System methods might wrap this into a SystemOperationResult.
        """
        stdout_pipe = subprocess.PIPE if capture_output else None
        stderr_pipe = None
        if capture_output:
            stderr_pipe = subprocess.STDOUT if stderr_to_stdout else subprocess.PIPE

        # Log the command being run for easier debugging
        cmd_str_for_log = " ".join(command)
        logger.debug(
            f"Running command: '{cmd_str_for_log}' with CWD: {cwd or self.get_cwd()}"
        )

        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                text=text,
                check=check,  # Let subprocess.run handle raising CalledProcessError if check is True
                stdout=stdout_pipe,
                stderr=stderr_pipe,
            )
            if result.stdout and capture_output:
                logger.debug(
                    f"Command '{cmd_str_for_log}' STDOUT: {result.stdout.strip()}"
                )
            if (
                result.stderr and capture_output and not stderr_to_stdout
            ):  # only log if stderr wasn't redirected
                logger.debug(
                    f"Command '{cmd_str_for_log}' STDERR: {result.stderr.strip()}"
                )
            return result
        except FileNotFoundError as e_fnf:
            logger.error(f"Command not found: {command[0]}. Error: {e_fnf}")
            # Re-raise if check=True semantics are desired, or handle as SOR.Err in calling methods
            if check:
                raise
            raise  # Propagate FileNotFoundError to be handled by the caller or global exception handler

    def file_exists(self, path: str) -> bool:
        """Checks if a file exists at the given path."""
        return os.path.exists(path) and os.path.isfile(path)

    def dir_exists(self, path: str) -> bool:
        """Checks if a directory exists at the given path."""
        return os.path.exists(path) and os.path.isdir(path)

    def path_exists(self, path: str) -> bool:
        """Checks if a path (file or directory) exists."""
        return os.path.exists(path)

    def make_dirs(
        self,
        path: str,
        exist_ok: bool = True,
    ) -> SystemOperationResult[None, OSError]:
        """
        Ensures that the specified directory exists, creating it if necessary.
        Args:
            path (str): The path of the directory to create.
            exist_ok (bool, optional): If True, no exception is raised if the
                directory already exists. Defaults to True.
        Returns:
            SystemOperationResult: Ok if directory created/exists, Err otherwise.
        """
        try:
            os.makedirs(path, exist_ok=exist_ok)
            logger.debug(f"Ensured directory exists: {path} (exist_ok={exist_ok})")
            return SystemOperationResult.Ok()
        except OSError as e:
            logger.warning(f"Could not create directory {path}: {e}")
            return SystemOperationResult.Err(e)

    def get_absolute_path(self, path: str) -> str:
        """Returns the absolute version of a path."""
        return os.path.abspath(path)

    def which(self, command: str) -> Optional[str]:
        """Locates an executable, similar to the `which` shell command."""
        return shutil.which(command)

    def remove_file(
        self,
        path: str,
        missing_ok: bool = True,
        log_success: bool = True,
    ) -> SystemOperationResult[None, Union[OSError, FileNotFoundError]]:
        """
        Removes a file at the specified path.
        """
        if self.file_exists(path):
            try:
                os.remove(path)
                if log_success:
                    logger.debug(f"Successfully removed file: {path}")
                return SystemOperationResult.Ok()
            except OSError as e:
                logger.warning(f"Could not remove file {path}: {e}")
                return SystemOperationResult.Err(e)
        elif missing_ok:
            if log_success:
                logger.debug(
                    f"File not found (missing_ok=True), skipping removal: {path}"
                )
            return SystemOperationResult.Ok()
        else:
            err = FileNotFoundError(f"File not found, cannot remove: {path}")
            logger.warning(str(err))
            return SystemOperationResult.Err(err)

    def remove_dir(
        self,
        path: str,
        recursive: bool = True,
        missing_ok: bool = True,
        log_success: bool = True,
    ) -> SystemOperationResult[None, Union[OSError, FileNotFoundError]]:
        """
        Removes a directory at the specified path.
        """
        if self.dir_exists(path):
            try:
                if recursive:
                    shutil.rmtree(path)
                else:
                    os.rmdir(path)  # Note: os.rmdir only works on empty directories
                if log_success:
                    logger.debug(
                        f"Successfully removed directory: {path} (recursive={recursive})"
                    )
                return SystemOperationResult.Ok()
            except OSError as e:
                logger.warning(f"Could not remove directory {path}: {e}")
                return SystemOperationResult.Err(e)
        elif missing_ok:
            if log_success:
                logger.debug(
                    f"Directory not found (missing_ok=True), skipping removal: {path}"
                )
            return SystemOperationResult.Ok()
        else:
            err = FileNotFoundError(f"Directory not found, cannot remove: {path}")
            logger.warning(str(err))
            return SystemOperationResult.Err(err)

    def read_package_asset(
        self,
        asset_path: str,
        encoding: str = "utf-8",
    ) -> SystemOperationResult[str, Exception]:
        """
        Reads the specified asset file from package resources.
        """
        full_asset_path_for_log = f"vscode_colab:assets/{asset_path}"
        try:
            # For Python 3.9+
            content = (
                importlib.resources.files("vscode_colab")
                .joinpath("assets", asset_path)
                .read_text(encoding=encoding)
            )
            logger.debug(f"Successfully read package asset: {full_asset_path_for_log}")
            return SystemOperationResult.Ok(content)
        except AttributeError:  # Fallback for Python < 3.9 (e.g., 3.7, 3.8)
            try:
                with importlib.resources.path("vscode_colab.assets", asset_path) as p:
                    content = p.read_text(encoding=encoding)
                logger.debug(
                    f"Successfully read package asset (legacy path): {full_asset_path_for_log}"
                )
                return SystemOperationResult.Ok(content)
            except Exception as e_legacy:
                logger.warning(
                    f"Could not read package asset {full_asset_path_for_log} (legacy path): {e_legacy}"
                )
                return SystemOperationResult.Err(e_legacy)
        except Exception as e_modern:
            logger.warning(
                f"Could not read package asset {full_asset_path_for_log}: {e_modern}"
            )
            return SystemOperationResult.Err(e_modern)

    def write_file(
        self,
        path: str,
        content: Union[str, bytes],
        mode: str = "w",  # Default to text write
        encoding: Optional[str] = "utf-8",
    ) -> SystemOperationResult[None, Union[IOError, Exception]]:
        """
        Writes content to a file at the specified path.
        """
        open_kwargs: Dict[str, Any] = {"mode": mode}
        if "b" not in mode and encoding:
            open_kwargs["encoding"] = encoding
        elif "b" in mode and encoding:
            logger.debug(
                f"Encoding '{encoding}' provided but opening file in binary mode '{mode}'. Encoding will be ignored."
            )

        try:
            with open(path, **open_kwargs) as f:
                f.write(content)  # type: ignore
            logger.debug(f"Successfully wrote to file: {path}")
            return SystemOperationResult.Ok()
        except IOError as e_io:
            logger.warning(f"Could not write to file {path}: {e_io}")
            return SystemOperationResult.Err(e_io)
        except Exception as e:  # Catch other potential errors
            logger.warning(f"Unexpected error writing to file {path}: {e}")
            return SystemOperationResult.Err(e)

    def read_file(
        self,
        path: str,
        mode: str = "r",  # Default to text read
        encoding: Optional[str] = "utf-8",
    ) -> SystemOperationResult[
        Union[str, bytes], Union[FileNotFoundError, IOError, Exception]
    ]:
        """
        Reads the content of a file at the specified path.
        """
        open_kwargs: Dict[str, Any] = {"mode": mode}
        if "b" not in mode and encoding:
            open_kwargs["encoding"] = encoding
        elif (
            "b" in mode and encoding
        ):  # For binary mode, encoding should be None for open()
            open_kwargs["encoding"] = None

        try:
            with open(path, **open_kwargs) as f:  # type: ignore
                content_read = f.read()
            logger.debug(f"Successfully read file: {path}")
            return SystemOperationResult.Ok(content_read)
        except FileNotFoundError as e_fnf:
            logger.warning(f"Cannot read file {path}: File not found.")
            return SystemOperationResult.Err(e_fnf)
        except IOError as e_io:
            logger.warning(f"Could not read file {path}: {e_io}")
            return SystemOperationResult.Err(e_io)
        except Exception as e:  # Catch other potential errors
            logger.warning(f"Unexpected error reading file {path}: {e}")
            return SystemOperationResult.Err(e)

    def get_cwd(self) -> str:
        """Gets the current working directory."""
        return os.getcwd()

    def change_cwd(self, path: str) -> SystemOperationResult[
        None,
        Union[
            FileNotFoundError,
            NotADirectoryError,
            PermissionError,
            OSError,
            Exception,
        ],
    ]:
        """
        Changes the current working directory to the specified path.
        """
        try:
            os.chdir(path)
            logger.debug(f"Changed current working directory to: {path}")
            return SystemOperationResult.Ok()
        except FileNotFoundError as e_fnf:
            logger.warning(f"Cannot change CWD to {path}: Directory not found.")
            return SystemOperationResult.Err(e_fnf)
        except NotADirectoryError as e_nad:
            logger.warning(f"Cannot change CWD to {path}: Not a directory.")
            return SystemOperationResult.Err(e_nad)
        except PermissionError as e_perm:
            logger.warning(f"Cannot change CWD to {path}: Permission denied.")
            return SystemOperationResult.Err(e_perm)
        except OSError as e_os:  # Other OS-related errors
            logger.warning(f"Cannot change CWD to {path}: {e_os}")
            return SystemOperationResult.Err(e_os)
        except Exception as e:  # Catch any other unexpected exceptions
            logger.warning(f"Unexpected error changing CWD to {path}: {e}")
            return SystemOperationResult.Err(e)

    def download_file(
        self,
        url: str,
        destination_path: str,
        timeout: int = 30,
    ) -> SystemOperationResult[
        None,
        Union[
            requests.exceptions.RequestException,
            IOError,
            Exception,
        ],
    ]:
        """
        Downloads a file from a given URL and saves it to the specified destination path.
        """
        logger.debug(f"Attempting to download file from {url} to {destination_path}")
        try:
            response = requests.get(
                url, stream=True, allow_redirects=True, timeout=timeout
            )
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            with open(destination_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.debug(
                f"Successfully downloaded file from {url} to {destination_path}"
            )
            return SystemOperationResult.Ok()
        except (
            requests.exceptions.RequestException
        ) as e_req:  # Includes HTTPError, ConnectionError, Timeout, etc.
            logger.warning(f"Failed to download file from {url}: {e_req}")
            return SystemOperationResult.Err(e_req)
        except IOError as e_io:
            logger.warning(
                f"Failed to write downloaded file to {destination_path}: {e_io}"
            )
            return SystemOperationResult.Err(e_io)
        except Exception as e:  # Catch any other unexpected exceptions
            logger.warning(
                f"An unexpected error occurred during download from {url}: {e}"
            )
            return SystemOperationResult.Err(e)

    def expand_user_path(self, path: str) -> str:
        """Expands '~' and '~user' path components."""
        return os.path.expanduser(path)

    def get_env_var(
        self,
        name: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Gets an environment variable."""
        return os.environ.get(name, default)

    def is_executable(self, path: str) -> bool:
        """Checks if a path is an executable file."""
        return self.file_exists(path) and os.access(path, os.X_OK)

    def change_permissions(
        self, path: str, mode: int = 0o755
    ) -> SystemOperationResult[None, OSError]:
        """Changes the mode of a file or directory."""
        try:
            os.chmod(path, mode)
            logger.debug(f"Changed permissions of {path} to {oct(mode)}")
            return SystemOperationResult.Ok()
        except OSError as e:
            logger.warning(f"Could not change permissions of {path}: {e}")
            return SystemOperationResult.Err(e)

    def get_permissions(
        self,
        path: str,
    ) -> SystemOperationResult[int, OSError]:
        """Gets the permissions of a file or directory as an integer."""
        try:
            mode = os.stat(path).st_mode
            return SystemOperationResult.Ok(mode)
        except OSError as e:
            logger.warning(f"Could not get permissions of {path}: {e}")
            return SystemOperationResult.Err(e, message=f"Failed to stat {path}")

    def get_user_home_dir(self) -> str:
        """Returns the user's home directory."""
        return self.expand_user_path("~")
