from jinja2 import Environment, PackageLoader, select_autoescape

# Initialize Jinja2 environment
jinja_env = Environment(
    loader=PackageLoader("vscode_colab", "assets/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_github_auth_template(url: str, code: str) -> str:
    """Renders the GitHub authentication link HTML."""
    template = jinja_env.get_template("github_auth_link.html.j2")
    return template.render(url=url, code=code)


def render_vscode_connection_template(tunnel_url: str, tunnel_name: str) -> str:
    """Renders the VS Code connection options HTML."""
    template = jinja_env.get_template("vscode_connection_options.html.j2")
    return template.render(tunnel_url=tunnel_url, tunnel_name=tunnel_name)
