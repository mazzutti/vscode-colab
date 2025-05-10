from typing import Optional

from vscode_colab.logger_config import log as logger
from vscode_colab.system import System
from vscode_colab.utils import SystemOperationResult


def configure_git(
    system: System,
    git_user_name: Optional[str] = None,
    git_user_email: Optional[str] = None,
) -> SystemOperationResult[None, Exception]:
    """
    Configures global Git user name and email using the provided values.
    """
    if not git_user_name and not git_user_email:
        logger.debug(
            "Both git_user_name and git_user_email are not provided. Skipping git configuration."
        )
        return SystemOperationResult.Ok()

    if not git_user_name or not git_user_email:
        msg = "Both git_user_name and git_user_email must be provided together. Skipping git configuration."
        logger.warning(msg)
        return SystemOperationResult.Ok()

    logger.info(
        f"Attempting to set git global user.name='{git_user_name}' and user.email='{git_user_email}'..."
    )

    git_exe = system.which("git")
    if not git_exe:
        err_msg = "'git' command not found. Cannot configure git."
        logger.error(err_msg)
        return SystemOperationResult.Err(FileNotFoundError("git"), message=err_msg)

    all_successful = True
    errors_encountered: list[str] = []

    # Configure user name
    name_cmd = [git_exe, "config", "--global", "user.name", git_user_name]
    try:
        result_name_proc = system.run_command(
            name_cmd, capture_output=True, text=True, check=False
        )
    except Exception as e_run_name:
        msg = f"Failed to execute git config user.name: {e_run_name}"
        logger.error(msg)
        errors_encountered.append(msg)
        all_successful = False
    else:
        if result_name_proc.returncode == 0:
            logger.info(f"Successfully set git global user.name='{git_user_name}'.")
        else:
            err_output_name = (
                result_name_proc.stderr.strip() or result_name_proc.stdout.strip()
            )
            msg = f"Failed to set git global user.name. RC: {result_name_proc.returncode}. Error: {err_output_name}"
            logger.error(msg)
            errors_encountered.append(msg)
            all_successful = False

    # Configure user email
    if not all_successful:
        logger.info(
            "Skipping git email configuration due to previous error in name configuration."
        )
        # If name configuration failed, assemble the error message and return
        final_err_msg = "Git user.name configuration failed. " + " | ".join(
            errors_encountered
        )
        return SystemOperationResult.Err(
            Exception("Git configuration failed"), message=final_err_msg
        )

    email_cmd = [git_exe, "config", "--global", "user.email", git_user_email]
    try:
        result_email_proc = system.run_command(
            email_cmd, capture_output=True, text=True, check=False
        )
    except Exception as e_run_email:
        msg = f"Failed to execute git config user.email: {e_run_email}"
        logger.error(msg)
        errors_encountered.append(msg)
        all_successful = False
    else:
        if result_email_proc.returncode == 0:
            logger.info(f"Successfully set git global user.email='{git_user_email}'.")
        else:
            err_output_email = (
                result_email_proc.stderr.strip() or result_email_proc.stdout.strip()
            )
            msg = f"Failed to set git global user.email. RC: {result_email_proc.returncode}. Error: {err_output_email}"
            logger.error(msg)
            errors_encountered.append(msg)
            all_successful = False

    if all_successful:
        return SystemOperationResult.Ok()
    else:
        final_err_msg = "One or more git configuration steps failed. " + " | ".join(
            errors_encountered
        )
        return SystemOperationResult.Err(
            Exception("Git configuration failed"), message=final_err_msg
        )
