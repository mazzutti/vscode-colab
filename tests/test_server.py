import unittest
from unittest.mock import patch, MagicMock
from src.vscode_colab.server import setup_vscode_server

class TestVSCodeServerSetup(unittest.TestCase):

    @patch('src.vscode_colab.server.download_vscode_cli')
    @patch('src.vscode_colab.server.subprocess.Popen')
    def test_setup_vscode_server_success(self, mock_popen, mock_download):
        mock_download.return_value = True
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            "please log into https://github.com/login/device and use code ABCD-EFGH\n",
            "Open this link in your browser https://vscode.dev/tunnel/12345/67890\n"
        ]
        mock_popen.return_value = mock_process

        process = setup_vscode_server()

        self.assertIsNotNone(process)
        mock_download.assert_called_once()
        mock_popen.assert_called_once()

    @patch('src.vscode_colab.server.download_vscode_cli')
    def test_setup_vscode_server_download_failure(self, mock_download):
        mock_download.return_value = False

        process = setup_vscode_server()

        self.assertIsNone(process)
        mock_download.assert_called_once()

    @patch('src.vscode_colab.server.download_vscode_cli')
    @patch('src.vscode_colab.server.subprocess.Popen')
    def test_setup_vscode_server_no_tunnel_url(self, mock_popen, mock_download):
        mock_download.return_value = True
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            "please log into https://github.com/login/device and use code ABCD-EFGH\n",
            "How would you like to log in to Visual Studio Code?\n"
        ]
        mock_popen.return_value = mock_process

        process = setup_vscode_server()

        self.assertIsNotNone(process)
        mock_download.assert_called_once()
        mock_popen.assert_called_once()

if __name__ == '__main__':
    unittest.main()