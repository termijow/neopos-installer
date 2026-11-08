import os
import tempfile
import shutil
import unittest
from unittest import mock
import main

class TestRustDeskIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_configured_exe_name_format(self):
        self.assertIn("host=2.24.66.112", main.RUSTDESK_CONFIGURED_EXE_NAME)
        self.assertIn("key=ZLRFJncjCLNFnWE5sL3BJ0uLK0HvV4edO2UqsA29+sc=", main.RUSTDESK_CONFIGURED_EXE_NAME)
        self.assertTrue(main.RUSTDESK_CONFIGURED_EXE_NAME.endswith(".exe"))

    @mock.patch("platform.system", return_value="Linux")
    def test_non_windows_skips_rustdesk(self, mock_system):
        app = mock.MagicMock(spec=main.NeoPOSInstaller)
        result = main.NeoPOSInstaller.find_rustdesk_installed(app)
        self.assertIsNone(result)

        main.NeoPOSInstaller.ensure_rustdesk_installed(app)
        app.find_rustdesk_installed.assert_not_called()

    @mock.patch("platform.system", return_value="Windows")
    def test_find_rustdesk_installed_when_present(self, mock_system):
        fake_exe = os.path.join(self.temp_dir, "RustDesk.exe")
        with open(fake_exe, "w") as f:
            f.write("mock")

        app = mock.MagicMock(spec=main.NeoPOSInstaller)
        with mock.patch("os.path.isfile", side_effect=lambda p: p == fake_exe):
            with mock.patch.dict(os.environ, {"ProgramFiles": self.temp_dir}):
                # Path candidate check
                with mock.patch("os.path.join", return_value=fake_exe):
                    found = main.NeoPOSInstaller.find_rustdesk_installed(app)
                    self.assertEqual(found, fake_exe)

    @mock.patch("platform.system", return_value="Windows")
    def test_offline_rustdesk_installer_discovery(self, mock_system):
        fake_installer = os.path.join(self.temp_dir, "rustdesk-1.3.8-x86_64.exe")
        with open(fake_installer, "wb") as f:
            f.write(b"0" * 6_000_000)

        app = mock.MagicMock(spec=main.NeoPOSInstaller)
        with mock.patch("os.path.isdir", return_value=True):
            with mock.patch("os.listdir", return_value=["rustdesk-1.3.8-x86_64.exe"]):
                with mock.patch("os.path.isfile", return_value=True):
                    with mock.patch("os.path.getsize", return_value=6_000_000):
                        found = main.NeoPOSInstaller.find_offline_rustdesk_installer(app)
                        self.assertIsNotNone(found)
                        self.assertTrue(found.lower().endswith(".exe"))

    @mock.patch("platform.system", return_value="Windows")
    def test_ensure_rustdesk_installed_already_present(self, mock_system):
        app = mock.MagicMock(spec=main.NeoPOSInstaller)
        app.find_rustdesk_installed.return_value = r"C:\Program Files\RustDesk\RustDesk.exe"
        
        main.NeoPOSInstaller.ensure_rustdesk_installed(app)
        # Should not attempt download or subprocess when already present
        app.find_offline_rustdesk_installer.assert_not_called()

    @mock.patch("platform.system", return_value="Windows")
    @mock.patch("subprocess.run")
    def test_ensure_rustdesk_installs_silently_with_offline_installer(self, mock_subproc, mock_system):
        mock_subproc.return_value = mock.MagicMock(returncode=0, stdout="", stderr="")
        app = mock.MagicMock(spec=main.NeoPOSInstaller)
        app.find_rustdesk_installed.return_value = None

        fake_offline = os.path.join(self.temp_dir, "rustdesk.exe")
        with open(fake_offline, "w") as f:
            f.write("mock installer")

        app.find_offline_rustdesk_installer.return_value = fake_offline

        with mock.patch("shutil.copyfile") as mock_copy:
            with mock.patch("os.path.isfile", return_value=True):
                main.NeoPOSInstaller.ensure_rustdesk_installed(app)
                mock_copy.assert_called_once()
                mock_subproc.assert_called_once()
                args, kwargs = mock_subproc.call_args
                self.assertIn("--silent-install", args[0])

    @mock.patch("platform.system", return_value="Windows")
    def test_ensure_rustdesk_error_does_not_raise(self, mock_system):
        app = mock.MagicMock(spec=main.NeoPOSInstaller)
        app.find_rustdesk_installed.side_effect = Exception("Registry error")
        # Ensure it does NOT throw
        try:
            main.NeoPOSInstaller.ensure_rustdesk_installed(app)
        except Exception as e:
            self.fail(f"ensure_rustdesk_installed raised an exception: {e}")

if __name__ == "__main__":
    unittest.main()
