from typing import Optional

from vscode_colab.logger_config import log as logger
from vscode_colab.system import System


def configure_git(
    system: System,
    git_user_name: Optional[str] = None,
    git_user_email: Optional[str] = None,
) -> bool:
    """
    Configures global Git user name and email using the provided values.

    Args:
        system: An instance of the System class for command execution.
        git_user_name: Git user name to configure.
        git_user_email: Git user email to configure.

    Returns:
        True if configuration was successful or skipped, False if a configuration attempt failed.
    """
    if not git_user_name and not git_user_email:
        logger.debug(
            "Both git_user_name and git_user_email are not provided. Skipping git configuration."
        )
        return True

    if (git_user_name and not git_user_email) or (git_user_email and not git_user_name):
        logger.warning(
            "Both git_user_name and git_user_email must be provided together. Skipping git configuration."
        )
        return True  # Treat as skipped successfully

    logger.info(
        f"Attempting to set git global user.name='{git_user_name}' and user.email='{git_user_email}'..."
    )

    # Configure user name
    if git_user_name:
        name_cmd = ["git", "config", "--global", "user.name", git_user_name]
        # Not using check=True here, will inspect returncode
        result_name = system.run_command(
            name_cmd, capture_output=True, text=True, check=False
        )

        if result_name.returncode == 0:
            logger.info(f"Successfully set git global user.name='{git_user_name}'.")
        else:
            err_output_name = (
                result_name.stderr.strip()
                if result_name.stderr
                else result_name.stdout.strip()
            )
            logger.error(
                f"Failed to set git global user.name. Return code: {result_name.returncode}. Error: {err_output_name}"
            )
            return False

    # Configure user email
    if git_user_email:
        email_cmd = ["git", "config", "--global", "user.email", git_user_email]
        result_email = system.run_command(
            email_cmd, capture_output=True, text=True, check=False
        )

        if result_email.returncode == 0:
            logger.info(f"Successfully set git global user.email='{git_user_email}'.")
        else:
            err_output_email = (
                result_email.stderr.strip()
                if result_email.stderr
                else result_email.stdout.strip()
            )
            logger.error(
                f"Failed to set git global user.email. Return code: {result_email.returncode}. Error: {err_output_email}"
            )
            return False

    return True
