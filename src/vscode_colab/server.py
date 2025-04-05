"""
This module contains the implementation of the setup_vscode_server function
along with any helper functions required for setting up the VS Code server
in Google Colab.
"""

import os
import re
import subprocess
import time

from IPython.display import HTML, display


def download_vscode_cli(force_download=False):
    if os.path.exists("./code") and not force_download:
        return True

    try:
        result = subprocess.run(
            "curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output 'vscode_cli.tar.gz'",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        result = subprocess.run(
            "tar -xf vscode_cli.tar.gz",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if not os.path.exists("./code"):
            print("❌ Error: Failed to extract VS Code CLI properly.")
            return False

        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during VS Code download or extraction: {e}")
        return False


def define_extensions():
    extensions = [
        "mgesbert.python-path",
        "ms-python.black-formatter",
        "ms-python.isort",
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-python.debugpy",
        "ms-toolsai.jupyter",
        "ms-toolsai.jupyter-keymap",
        "ms-toolsai.jupyter-renderers",
        "ms-toolsai.tensorboard",
    ]

    return extensions


def display_github_auth_link(output_line):
    pattern = (
        r"please log into (https://github\.com/login/device) and use code ([A-Z0-9\-]+)"
    )
    match = re.search(pattern, output_line)

    if not match:
        return False

    url, code = match.groups()

    html_content = f"""
    <div style="padding: 15px; background-color: #f0f7ff; border-radius: 8px; margin: 15px 0; font-family: Arial, sans-serif; border: 1px solid #c8e1ff;">
        <h3 style="margin-top: 0; color: #0366d6; font-size: 18px;">GitHub Authentication Required</h3>
        <p style="margin-bottom: 15px;">Please authenticate by clicking the link below and entering the code:</p>
        <div style="display: flex; align-items: center; margin-bottom: 10px; flex-wrap: wrap;">
            <a href="{url}" target="_blank" style="background-color: #2ea44f; color: white; padding: 10px 16px; text-decoration: none; border-radius: 6px; margin-right: 15px; margin-bottom: 10px; font-weight: 500;">
                Open GitHub Authentication
            </a>
            <div style="background-color: #ffffff; border: 1px solid #d1d5da; border-radius: 6px; padding: 10px 16px; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; position: relative; display: flex; align-items: center; margin-bottom: 10px;">
                <span id="auth-code" style="margin-right: 15px; font-size: 16px;">{code}</span>
                <button id="copyButton" onclick="copyAuthCode()" style="background-color: #f6f8fa; border: 1px solid #d1d5da; border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 14px;">
                    Copy
                </button>
            </div>
        </div>
        <script>
            function copyAuthCode() {{
                const code = "{code}";
                const copyButton = document.getElementById('copyButton');
                
                navigator.clipboard.writeText(code).then(() => {{
                    copyButton.textContent = 'Copied!';
                    copyButton.style.backgroundColor = '#dff0d8';
                    copyButton.style.borderColor = '#d6e9c6';
                    copyButton.style.color = '#3c763d';
                    
                    setTimeout(() => {{
                        copyButton.textContent = 'Copy';
                        copyButton.style.backgroundColor = '#f6f8fa';
                        copyButton.style.borderColor = '#d1d5da';
                        copyButton.style.color = '';
                    }}, 2000);
                }});
            }}
        </script>
    </div>
    """

    display(HTML(html_content))
    return True


def display_vscode_connection_options(tunnel_url, tunnel_name):
    html_content = f"""
    <div style="padding: 15px; background-color: #f5f9ff; border-radius: 8px; margin: 15px 0; font-family: Arial, sans-serif; border: 1px solid #c8e1ff;">
        <h3 style="margin-top: 0; color: #0366d6; font-size: 18px;">✅ VS Code Server Ready!</h3>
        
        <div style="margin-bottom: 20px;">
            <h4 style="margin-bottom: 10px; color: #24292e; font-size: 16px;">Option 1: Open in Browser</h4>
            <p style="margin-bottom: 15px;">Click the button below to open VS Code directly in your browser:</p>
            <a href="{tunnel_url}" target="_blank" style="background-color: #0366d6; color: white; padding: 10px 16px; text-decoration: none; border-radius: 6px; font-weight: 500; display: inline-block; margin-bottom: 10px;">
                Open VS Code in Browser
            </a>
        </div>
        
        <div style="margin-bottom: 20px;">
            <h4 style="margin-bottom: 10px; color: #24292e; font-size: 16px;">Option 2: Connect from Desktop VS Code</h4>
            <p style="margin-bottom: 8px;">To connect from your local VS Code:</p>
            <ol style="margin-left: 20px; margin-bottom: 15px;">
                <li>Make sure you're signed in with the same GitHub account in VS Code</li>
                <li>Open the Remote Explorer sidebar in VS Code (<kbd>Ctrl+Shift+P</kbd> or <kbd>Cmd+Shift+P</kbd>, then type "Remote Explorer")</li>
                <li>Look for "<strong>{tunnel_name}</strong>" under "Tunnels" and click to connect</li>
            </ol>
        </div>
    </div>
    """

    display(HTML(html_content))


def setup_vscode_server(tunnel_name="colab"):
    if not download_vscode_cli():
        print("❌ Failed to download VS Code CLI. Aborting setup.")
        return None

    extensions = define_extensions()

    command = f"./code tunnel --accept-server-license-terms --name {tunnel_name}"

    if extensions:
        ext_args = " ".join(f"--install-extension {ext}" for ext in extensions)
        command = f"{command} {ext_args}"

    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
        )

        github_auth_shown = False
        tunnel_url = None

        github_auth_regex = r"please log into (https://github\.com/login/device) and use code ([A-Z0-9\-]+)"
        tunnel_url_regex = (
            r"Open this link in your browser (https://vscode\.dev/tunnel/[\w-]+/[\w-]+)"
        )
        login_prompt = "How would you like to log in to Visual Studio Code?"

        while process.poll() is None:
            output = process.stdout.readline()
            if not output:
                continue

            if login_prompt in output and not github_auth_shown:
                process.stdin.write("\x1b[B\n")
                process.stdin.flush()

            github_match = re.search(github_auth_regex, output)
            if github_match and not github_auth_shown:
                display_github_auth_link(output)
                github_auth_shown = True

            tunnel_match = re.search(tunnel_url_regex, output)
            if tunnel_match:
                tunnel_url = tunnel_match.group(1)
                display_vscode_connection_options(tunnel_url, tunnel_name)
                break

        if not tunnel_url:
            start_time = time.time()
            while time.time() - start_time < 30:
                output = process.stdout.readline()
                if not output:
                    time.sleep(0.1)
                    continue

                tunnel_match = re.search(tunnel_url_regex, output)
                if tunnel_match:
                    tunnel_url = tunnel_match.group(1)
                    display_vscode_connection_options(tunnel_url, tunnel_name)
                    break

            if not tunnel_url:
                print("⚠️ VS Code server started, but couldn't find connection URL.")
                print(
                    "   Once the server is ready, look for a URL like https://vscode.dev/tunnel/..."
                )

        return process

    except Exception as e:
        print(f"❌ Error setting up VS Code server: {e}")
        return None
