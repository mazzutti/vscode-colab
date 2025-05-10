from unittest.mock import MagicMock, patch

import pytest

# Assuming templating.py uses Jinja2
from jinja2 import Environment, TemplateNotFound

from vscode_colab.templating import (  # Assuming jinja_env is an Environment instance in templating.py; from vscode_colab.templating import jinja_env # If accessible for more direct mocking
    render_github_auth_template,
    render_vscode_connection_template,
)


@pytest.fixture
def mock_jinja_env():
    # Create a mock Jinja2 Environment
    # This allows us to control what get_template returns
    mock_env = MagicMock(spec=Environment)
    return mock_env


@patch("vscode_colab.templating.jinja_env")  # Patch the global jinja_env instance
def test_render_github_auth_template_success(mock_jinja_env_global, mock_jinja_env):
    # Use the locally created mock_jinja_env for setup,
    # but the patch targets the one imported by the templating module.
    # So, make the global patched one behave like our local mock.
    mock_jinja_env_global.get_template.return_value = (
        mock_jinja_env.get_template.return_value
    )

    mock_template = MagicMock()
    mock_template.render.return_value = "<html>GitHub Auth: test_url, test_code</html>"
    mock_jinja_env.get_template.return_value = mock_template  # Configure local mock
    mock_jinja_env_global.get_template.return_value = (
        mock_template  # Configure global patched mock
    )

    url = "test_url"
    code = "test_code"
    result = render_github_auth_template(url, code)

    assert result == "<html>GitHub Auth: test_url, test_code</html>"
    mock_jinja_env_global.get_template.assert_called_once_with(
        "github_auth_link.html.j2"
    )
    mock_template.render.assert_called_once_with(url=url, code=code)


@patch("vscode_colab.templating.jinja_env")
def test_render_vscode_connection_template_success(
    mock_jinja_env_global, mock_jinja_env
):
    mock_jinja_env_global.get_template.return_value = (
        mock_jinja_env.get_template.return_value
    )

    mock_template = MagicMock()
    mock_template.render.return_value = (
        "<html>VSCode Connect: test_tunnel_url, test_tunnel_name</html>"
    )
    mock_jinja_env.get_template.return_value = mock_template
    mock_jinja_env_global.get_template.return_value = mock_template

    tunnel_url = "test_tunnel_url"
    tunnel_name = "test_tunnel_name"
    result = render_vscode_connection_template(tunnel_url, tunnel_name)

    assert result == "<html>VSCode Connect: test_tunnel_url, test_tunnel_name</html>"
    mock_jinja_env_global.get_template.assert_called_once_with(
        "vscode_connection_options.html.j2"
    )
    mock_template.render.assert_called_once_with(
        tunnel_url=tunnel_url, tunnel_name=tunnel_name
    )


@patch("vscode_colab.templating.jinja_env")
def test_render_template_not_found(mock_jinja_env_global, mock_jinja_env):
    mock_jinja_env_global.get_template.return_value = (
        mock_jinja_env.get_template.return_value
    )
    mock_jinja_env.get_template.side_effect = TemplateNotFound("missing.html.j2")
    mock_jinja_env_global.get_template.side_effect = TemplateNotFound("missing.html.j2")

    with pytest.raises(TemplateNotFound):
        render_github_auth_template("url", "code")  # Will fail at get_template


@patch("vscode_colab.templating.jinja_env")
def test_render_template_render_error(mock_jinja_env_global, mock_jinja_env):
    # Test if template.render() itself raises an error
    mock_jinja_env_global.get_template.return_value = (
        mock_jinja_env.get_template.return_value
    )
    mock_template = MagicMock()
    mock_template.render.side_effect = Exception("Jinja Render Error")
    mock_jinja_env.get_template.return_value = mock_template
    mock_jinja_env_global.get_template.return_value = mock_template

    with pytest.raises(Exception, match="Jinja Render Error"):
        render_vscode_connection_template("url", "name")
