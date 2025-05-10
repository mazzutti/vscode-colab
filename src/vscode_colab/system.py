import importlib.resources
import os
import platform
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple, Type, Union

import requests

from vscode_colab.logger_config import log as logger


class System:
    """
    A facade for interacting with the operating system.
    This class centralizes OS-level operations to improve testability and
    isolate dependencies on modules like `os`, `shutil`, `subprocess`, etc.
    """

    def run_command(
        self,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        stderr_to_stdout: bool = True,
    ) -> subprocess.CompletedProcess:
        stdout_pipe = subprocess.PIPE if capture_output else None
        stderr_pipe = None
        if capture_output:
            stderr_pipe = subprocess.STDOUT if stderr_to_stdout else subprocess.PIPE
        """
        Executes a system command using `subprocess.run` with configurable options.

        Args:
            command (List[str]): The command to execute as a list of strings.
            cwd (Optional[str], optional): The working directory to execute the command in.
                Defaults to None, which uses the current working directory.
            env (Optional[Dict[str, str]], optional): A dictionary of environment variables
                to set for the command. Defaults to None, which uses the current environment.
            capture_output (bool, optional): Whether to capture the command's output.
                Defaults to True.
            text (bool, optional): Whether to decode the output as text (if True) or leave
                it as bytes (if False). Defaults to True.
            check (bool, optional): Whether to raise a `subprocess.CalledProcessError` if
                the command exits with a non-zero status. Defaults to False.
            stderr_to_stdout (bool, optional): Whether to redirect stderr to stdout.
                Defaults to True.

        Returns:
            subprocess.CompletedProcess: The result of the executed command, containing
            information such as the return code, stdout, and stderr.

        Raises:
            subprocess.CalledProcessError: If `check` is True and the command exits with
            a non-zero status.
        """
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            text=text,
            check=check,
            stdout=stdout_pipe,
            stderr=stderr_pipe,
        )

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
    ) -> Tuple[bool, Optional[Exception]]:
        """
        Ensures that the specified directory exists, creating it if necessary.
        Args:
            path (str): The path of the directory to create.
            exist_ok (bool, optional): If True, no exception is raised if the
                directory already exists. Defaults to True.
        Returns:
            Tuple[bool, Optional[Exception]]: A tuple where the first element is
            a boolean indicating success (True if the directory was created or
            already exists, False otherwise), and the second element is an
            exception object if an error occurred, or None if no error occurred.
        """
        try:
            os.makedirs(path, exist_ok=exist_ok)
            logger.debug(f"Ensured directory exists: {path} (exist_ok={exist_ok})")
            return True, None
        except OSError as e:
            logger.warning(f"Could not create directory {path}: {e}")
            return False, e

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
    ) -> Tuple[bool, Optional[Exception]]:
        """
        Removes a file at the specified path.

        Args:
            path (str): The path to the file to be removed.
            missing_ok (bool, optional): If True, no error is raised if the file does not exist. Defaults to True.
            log_success (bool, optional): If True, logs a debug message upon successful removal or if the file is missing but `missing_ok` is True. Defaults to True.

        Returns:
            Tuple[bool, Optional[Exception]]: A tuple where the first element is a boolean indicating success (True if the file was removed or does not exist and `missing_ok` is True, False otherwise), and the second element is an exception object if an error occurred, or None if no error occurred.

        Raises:
            FileNotFoundError: If the file does not exist and `missing_ok` is False.
        """
        if self.file_exists(path):
            try:
                os.remove(path)
                if log_success:
                    logger.debug(f"Successfully removed file: {path}")
                return True, None
            except OSError as e:
                logger.warning(f"Could not remove file {path}: {e}")
                return False, e
        elif missing_ok:
            if log_success:
                logger.debug(
                    f"File not found (missing_ok=True), skipping removal: {path}"
                )
            return True, None
        else:
            err = FileNotFoundError(f"File not found, cannot remove: {path}")
            logger.warning(str(err))
            return False, err

    def remove_dir(
        self,
        path: str,
        recursive: bool = True,
        missing_ok: bool = True,
        log_success: bool = True,
    ) -> Tuple[bool, Optional[Exception]]:
        """
        Removes a directory at the specified path.

        Args:
            path (str): The path to the directory to be removed.
            recursive (bool, optional): If True, removes the directory and all its contents recursively. Defaults to True.
            missing_ok (bool, optional): If True, no exception is raised if the directory does not exist. Defaults to True.
            log_success (bool, optional): If True, logs a debug message upon successful removal. Defaults to True.

        Returns:
            Tuple[bool, Optional[Exception]]: A tuple where the first element is a boolean indicating success (True) or failure (False), and the second element is an exception object if an error occurred, or None if no error occurred.

        Raises:
            FileNotFoundError: If the directory does not exist and `missing_ok` is False.
        """
        if self.dir_exists(path):
            try:
                if recursive:
                    shutil.rmtree(path)
                else:
                    os.rmdir(path)
                if log_success:
                    logger.debug(
                        f"Successfully removed directory: {path} (recursive={recursive})"
                    )
                return True, None
            except OSError as e:
                logger.warning(f"Could not remove directory {path}: {e}")
                return False, e
        elif missing_ok:
            if log_success:
                logger.debug(
                    f"Directory not found (missing_ok=True), skipping removal: {path}"
                )
            return True, None
        else:
            err = FileNotFoundError(f"Directory not found, cannot remove: {path}")
            logger.warning(str(err))
            return False, err

    def read_package_asset(
        self,
        asset_path: str,
        encoding: str = "utf-8",
    ) -> Tuple[Optional[str], Optional[Exception]]:
        """
        This method attempts to read the specified asset file. Logs the success or failure of the operation.

        Args:
            asset_path (str): The relative path to the asset file within the 'assets' directory.
            encoding (str, optional): The encoding to use when reading the file. Defaults to "utf-8".

        Returns:
            Tuple[Optional[str], Optional[Exception]]: A tuple containing:
            - The content of the asset file as a string if successful, or None if an error occurred.
            - An exception object if an error occurred, or None if the operation was successful.

        Raises:
            None: This method does not raise exceptions directly but logs them and returns them as part of the result tuple.
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
            return content, None
        except AttributeError:
            # Fallback for Python < 3.9 (e.g., 3.7, 3.8)
            try:
                with importlib.resources.path("vscode_colab.assets", asset_path) as p:
                    content = p.read_text(encoding=encoding)
                logger.debug(
                    f"Successfully read package asset (legacy path): {full_asset_path_for_log}"
                )
                return content, None
            except Exception as e_legacy:
                logger.warning(
                    f"Could not read package asset {full_asset_path_for_log} (legacy path): {e_legacy}"
                )
                return None, e_legacy
        except Exception as e_modern:
            logger.warning(
                f"Could not read package asset {full_asset_path_for_log}: {e_modern}"
            )
            return None, e_modern

    def write_file(
        self,
        path: str,
        content: Union[str, bytes],
        mode: str = "w",
        encoding: Optional[str] = "utf-8",
    ) -> Tuple[bool, Optional[Exception]]:
        """
        Writes content to a file at the specified path.

        Args:
            path (str): The file path where the content will be written.
            content (Union[str, bytes]): The content to write to the file. Can be a string or bytes.
            mode (str, optional): The mode in which the file is opened. Defaults to "w". Use "b" in the mode for binary writing (e.g., "wb").
            encoding (Optional[str], optional): The encoding to use when writing text content. Ignored if the mode is binary. Defaults to "utf-8".

        Returns:
            Tuple[bool, Optional[Exception]]: A tuple where the first element is a boolean indicating success (True) or failure (False), and the second element is an exception object if an error occurred, or None if the operation was successful.

        Notes:
            - If the mode is binary (e.g., "wb"), the encoding parameter is ignored.
            - Logs debug messages for successful writes and warnings for errors.
        """
        open_kwargs = {"mode": mode}
        if "b" not in mode and encoding:  # Text mode with encoding
            open_kwargs["encoding"] = encoding
        elif "b" in mode and encoding:
            logger.debug(
                f"Encoding '{encoding}' provided but opening file in binary mode '{mode}'. Encoding will be ignored."
            )

        try:
            with open(path, **open_kwargs) as f:  # type: ignore
                f.write(content)  # type: ignore
            logger.debug(f"Successfully wrote to file: {path}")
            return True, None
        except IOError as e:
            logger.warning(f"Could not write to file {path}: {e}")
            return False, e
        except Exception as e:
            logger.warning(f"Unexpected error writing to file {path}: {e}")
            return False, e

    def read_file(
        self,
        path: str,
        mode: str = "r",
        encoding: Optional[str] = "utf-8",
    ) -> Tuple[Optional[Union[str, bytes]], Optional[Exception]]:
        """
        Reads the content of a file at the specified path.
        Args:
            path (str): The path to the file to be read.
            mode (str, optional): The mode in which the file should be opened. Defaults to "r". Use "r" for reading text files and "rb" for reading binary files.
            encoding (Optional[str], optional): The encoding to use when reading text files. Defaults to "utf-8". Ignored if the mode is binary.
        Returns:
            Tuple[Optional[Union[str, bytes]], Optional[Exception]]:
                - The content of the file as a string (for text mode) or bytes (for binary mode), or None if an error occurred.
                - An exception object if an error occurred, or None if the operation was successful.
        """
        open_kwargs = {"mode": mode}
        if "b" not in mode and encoding:  # Text mode
            open_kwargs["encoding"] = encoding
        elif "b" in mode and encoding:
            open_kwargs["encoding"] = None

        try:
            with open(path, **open_kwargs) as f:  # type: ignore
                content = f.read()
            logger.debug(f"Successfully read file: {path}")
            return content, None
        except FileNotFoundError as e_fnf:
            logger.warning(f"Cannot read file {path}: File not found.")
            return None, e_fnf
        except IOError as e_io:  # Other IO errors like permission denied
            logger.warning(f"Could not read file {path}: {e_io}")
            return None, e_io
        except Exception as e:
            logger.warning(f"Unexpected error reading file {path}: {e}")
            return None, e

    def get_cwd(self) -> str:
        """Gets the current working directory."""
        return os.getcwd()

    def change_cwd(self, path: str) -> Tuple[bool, Optional[Exception]]:
        """
        Changes the current working directory to the specified path.
        Args:
            path (str): The target directory path to change to.
        Returns:
            Tuple[bool, Optional[Exception]]: A tuple where the first element is a boolean indicating success (True) or failure (False), and the second element is an exception object if an error occurred, or None if the operation was successful.
        Exceptions Handled:
            - FileNotFoundError: Raised if the specified path does not exist.
            - NotADirectoryError: Raised if the specified path is not a directory.
            - PermissionError: Raised if the user does not have permission to access the directory.
            - OSError: Raised for other OS-related errors.
            - Exception: Catches any other unexpected exceptions.
        """

        try:
            os.chdir(path)
            logger.debug(f"Changed current working directory to: {path}")
            return True, None
        except FileNotFoundError as e_fnf:
            logger.warning(f"Cannot change CWD to {path}: Directory not found.")
            return False, e_fnf
        except NotADirectoryError as e_nad:
            logger.warning(f"Cannot change CWD to {path}: Not a directory.")
            return False, e_nad
        except PermissionError as e_perm:
            logger.warning(f"Cannot change CWD to {path}: Permission denied.")
            return False, e_perm
        except OSError as e_os:
            logger.warning(f"Cannot change CWD to {path}: {e_os}")
            return False, e_os
        except Exception as e:
            logger.warning(f"Unexpected error changing CWD to {path}: {e}")
            return False, e

    def download_file(
        self,
        url: str,
        destination_path: str,
        timeout: int = 30,
    ) -> Tuple[bool, Optional[Exception]]:
        """
        Downloads a file from a given URL and saves it to the specified destination path.

        Args:
            url (str): The URL of the file to download.
            destination_path (str): The local file path where the downloaded file will be saved.
            timeout (int, optional): The timeout in seconds for the download request. Defaults to 30.

        Returns:
            Tuple[bool, Optional[Exception]]: A tuple where the first element is a boolean indicating success (True) or failure (False), and the second element is an exception object if an error occurred, or None if the operation was successful.

        Exceptions Handled:
            - requests.exceptions.RequestException: Raised for network-related errors.
            - IOError: Raised for file writing errors.
            - Exception: Catches any other unexpected exceptions.
        """
        logger.debug(f"Attempting to download file from {url} to {destination_path}")
        try:
            response = requests.get(
                url, stream=True, allow_redirects=True, timeout=timeout
            )
            response.raise_for_status()
            with open(destination_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.debug(
                f"Successfully downloaded file from {url} to {destination_path}"
            )
            return True, None
        except requests.exceptions.RequestException as e_req:
            logger.warning(f"Failed to download file from {url}: {e_req}")
            return False, e_req
        except IOError as e_io:
            logger.warning(
                f"Failed to write downloaded file to {destination_path}: {e_io}"
            )
            return False, e_io
        except Exception as e:
            logger.warning(
                f"An unexpected error occurred during download from {url}: {e}"
            )
            return False, e

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
        # Ensure it's a file first, then check executable permission
        return self.file_exists(path) and os.access(path, os.X_OK)

    def change_permissions(self, path: str, mode: int = 0o755) -> None:
        """Changes the mode of a file or directory."""
        os.chmod(path, mode)

    def get_permissions(self, path: str) -> int:
        """Gets the permissions of a file or directory."""
        # os.stat returns a stat_result object, we want the mode
        return os.stat(path).st_mode

    def get_platform_system(self) -> str:
        """Returns the system/OS name, e.g., 'Linux', 'Darwin', 'Windows'."""
        return platform.system()

    def get_user_home_dir(self) -> str:
        """Returns the user's home directory."""
        return self.expand_user_path("~")
