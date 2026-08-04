import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_installer_module():
    fake_ctk = types.ModuleType("customtkinter")
    fake_ctk.CTk = object
    fake_ctk.set_appearance_mode = lambda _value: None
    fake_ctk.set_default_color_theme = lambda _value: None
    sys.modules["customtkinter"] = fake_ctk

    fake_tk = types.ModuleType("tkinter")
    fake_tk.__path__ = []
    fake_messagebox = types.ModuleType("tkinter.messagebox")
    fake_simpledialog = types.ModuleType("tkinter.simpledialog")
    fake_simpledialog.askstring = lambda *_args, **_kwargs: None
    sys.modules["tkinter"] = fake_tk
    sys.modules["tkinter.messagebox"] = fake_messagebox
    sys.modules["tkinter.simpledialog"] = fake_simpledialog

    spec = importlib.util.spec_from_file_location("neopos_installer_main", ROOT / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer_main = load_installer_module()


def installer_without_ui():
    installer = installer_main.NeoPOSInstaller.__new__(installer_main.NeoPOSInstaller)
    installer._sudo_password = None
    installer._docker_requires_sudo = False
    installer.credentials_path = None
    installer.local_credentials = {}
    installer.logs = []
    installer.after = lambda _delay, callback: callback()
    installer.append_log = installer.logs.append
    return installer


class LinuxDockerTests(unittest.TestCase):
    @mock.patch.object(installer_main.platform, "system", return_value="Linux")
    @mock.patch.object(installer_main.os, "geteuid", return_value=1000)
    @mock.patch.object(installer_main.shutil, "which", return_value="/usr/bin/sudo")
    def test_admin_password_is_validated_through_stdin(self, _which, _geteuid, _system):
        installer = installer_without_ui()
        installer.ask_linux_admin_password = mock.Mock(return_value="correct-horse")

        with mock.patch.object(installer_main.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            installer.ensure_linux_admin_access()

        command = run.call_args.args[0]
        self.assertEqual(command, ["sudo", "-S", "-k", "-p", "", "--", "true"])
        self.assertNotIn("correct-horse", command)
        self.assertEqual(run.call_args.kwargs["input"], "correct-horse\n")
        self.assertEqual(installer._sudo_password, "correct-horse")

    @mock.patch.object(installer_main.time, "sleep", return_value=None)
    @mock.patch.object(installer_main.platform, "system", return_value="Linux")
    @mock.patch.object(installer_main.os, "geteuid", return_value=1000)
    def test_linux_starts_engine_and_uses_sudo_for_inaccessible_socket(
        self, _geteuid, _system, _sleep
    ):
        installer = installer_without_ui()
        installer._sudo_password = "correct-horse"
        installer.ensure_linux_admin_access = mock.Mock()
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            if command == ["/usr/bin/docker", "info"]:
                return subprocess.CompletedProcess(command, 1, "", "permission denied")
            return subprocess.CompletedProcess(command, 0, "ok", "")

        with mock.patch.object(installer_main.subprocess, "run", side_effect=fake_run):
            installer.ensure_linux_docker_ready("/usr/bin/docker")

        commands = [command for command, _kwargs in calls]
        self.assertIn(
            ["sudo", "-S", "-k", "-p", "", "--", "systemctl", "start", "docker"],
            commands,
        )
        self.assertIn(
            ["sudo", "-S", "-k", "-p", "", "--", "/usr/bin/docker", "info"],
            commands,
        )
        self.assertTrue(installer._docker_requires_sudo)
        self.assertFalse(any("Docker Desktop" in line for line in installer.logs))

    @mock.patch.object(installer_main.platform, "system", return_value="Linux")
    @mock.patch.object(installer_main.os, "geteuid", return_value=1000)
    @mock.patch.object(installer_main.shutil, "which", return_value="/usr/bin/sudo")
    def test_cancelled_admin_prompt_stops_immediately(self, _which, _geteuid, _system):
        installer = installer_without_ui()
        installer.ask_linux_admin_password = mock.Mock(return_value=None)

        with self.assertRaisesRegex(RuntimeError, "cancelada"):
            installer.ensure_linux_admin_access()

    @mock.patch.object(installer_main.platform, "system", return_value="Linux")
    def test_new_linux_install_writes_visible_credentials_with_distinct_users(self, _system):
        installer = installer_without_ui()
        with tempfile.TemporaryDirectory() as temporary_dir:
            install_dir = Path(temporary_dir) / "NeoPOS"
            backend_dir = install_dir / "local" / "backend"
            backend_dir.mkdir(parents=True)
            (backend_dir / ".env.example").write_text(
                "ADMIN_EMAIL=admin@pos.local\nCASHIER_EMAIL=cajero@neopos.com\n",
                encoding="utf-8",
            )
            visible_dir = Path(temporary_dir) / "Descargas"
            with mock.patch.object(installer_main.NeoPOSInstaller, "_credential_directory", return_value=str(visible_dir)):
                installer.ensure_runtime_environment(str(install_dir))

            values = installer._read_env_file(str(backend_dir / ".env"))
            self.assertRegex(values["ADMIN_EMAIL"], r"^admin-[0-9a-f]{8}@local\.neopos$")
            self.assertRegex(values["CASHIER_EMAIL"], r"^cajero-[0-9a-f]{8}@local\.neopos$")
            self.assertNotEqual(values["ADMIN_PASSWORD"], values["CASHIER_PASSWORD"])
            credentials_file = visible_dir / "admin-credentials.txt"
            self.assertTrue(credentials_file.is_file())
            self.assertEqual(installer.credentials_path, str(credentials_file))
            content = credentials_file.read_text(encoding="utf-8")
            self.assertIn(values["ADMIN_EMAIL"], content)
            self.assertIn(values["CASHIER_EMAIL"], content)
            if os.name != "nt":
                self.assertEqual(credentials_file.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
