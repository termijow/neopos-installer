import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
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
                "ADMIN_EMAIL=admin@pos.local\nCASHIER_EMAIL=cajero@neopos.com\n"
                "SYNC_REMOTE_URL=https://api.neopos.com.co\n",
                encoding="utf-8",
            )
            visible_dir = Path(temporary_dir) / "Descargas"
            with mock.patch.object(installer_main.NeoPOSInstaller, "_credential_directory", return_value=str(visible_dir)):
                installer.ensure_runtime_environment(str(install_dir))

            values = installer._read_env_file(str(backend_dir / ".env"))
            self.assertRegex(values["ADMIN_EMAIL"], r"^admin-[0-9a-f]{8}@local\.neopos$")
            self.assertRegex(values["CASHIER_EMAIL"], r"^cajero-[0-9a-f]{8}@local\.neopos$")
            self.assertNotEqual(values["ADMIN_PASSWORD"], values["CASHIER_PASSWORD"])
            self.assertEqual(values["SYNC_REMOTE_URL"], "https://api.neopos.com.co")
            credentials_file = visible_dir / "admin-credentials.txt"
            self.assertTrue(credentials_file.is_file())
            self.assertEqual(installer.credentials_path, str(credentials_file))
            content = credentials_file.read_text(encoding="utf-8")
            self.assertIn(values["ADMIN_EMAIL"], content)
            self.assertIn(values["CASHIER_EMAIL"], content)
            if os.name != "nt":
                self.assertEqual(credentials_file.stat().st_mode & 0o777, 0o600)

    def test_prepare_update_stops_before_changes_when_backup_fails(self):
        installer = installer_without_ui()
        compose = "postgres-data:/var/lib/postgresql/data\nminio-data:/data\n"
        with tempfile.TemporaryDirectory() as temporary_dir:
            install_dir = Path(temporary_dir) / "NeoPOS"
            install_dir.mkdir()
            (install_dir / "docker-compose.yml").write_text(compose, encoding="utf-8")
            (install_dir / "release-manifest.json").write_text(
                json.dumps({"app_version": "v0.3.7", "database_migration": "additive"}), encoding="utf-8"
            )
            archive_path = Path(temporary_dir) / "release.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("docker-compose.yml", compose)
                archive.writestr("release-manifest.json", json.dumps({"app_version": "v0.3.8", "database_migration": "additive"}))
            installer.backup_database = mock.Mock(side_effect=RuntimeError("pg_dump failed"))

            with zipfile.ZipFile(archive_path, "r") as archive:
                with self.assertRaisesRegex(RuntimeError, "pg_dump failed"):
                    installer.prepare_update(str(install_dir), archive)

            self.assertEqual((install_dir / "docker-compose.yml").read_text(encoding="utf-8"), compose)
            self.assertFalse((install_dir / "release-images.json").exists())

    @mock.patch.object(installer_main.time, "sleep", return_value=None)
    def test_failed_pg_dump_does_not_publish_a_backup(self, _sleep):
        installer = installer_without_ui()
        installer.find_docker_cli = mock.Mock(return_value="/usr/bin/docker")
        compose_result = subprocess.CompletedProcess([], 0, b"", b"")
        failed_dump = subprocess.CompletedProcess([], 1, b"", b"pg_dump failed")
        installer.run_docker_process = mock.Mock(side_effect=[compose_result] + [failed_dump] * 30)
        with tempfile.TemporaryDirectory() as temporary_dir:
            install_dir = Path(temporary_dir) / "NeoPOS"
            install_dir.mkdir()
            (install_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "No se pudo crear el respaldo"):
                installer.backup_database(str(install_dir))

            backups = list((install_dir / "backups").glob("*"))
            self.assertEqual(backups, [])

    def test_existing_runtime_configuration_is_preserved_during_update(self):
        installer = installer_without_ui()
        with tempfile.TemporaryDirectory() as temporary_dir:
            install_dir = Path(temporary_dir) / "NeoPOS"
            backend_dir = install_dir / "local" / "backend"
            backend_dir.mkdir(parents=True)
            (install_dir / ".env").write_text(
                "POSTGRES_PASSWORD=keep-postgres\nMINIO_ROOT_USER=keep-user\nMINIO_ROOT_PASSWORD=keep-minio\nCUSTOM_ROOT=value\n",
                encoding="utf-8",
            )
            (backend_dir / ".env").write_text(
                "DATABASE_URL=postgres://custom\nADMIN_EMAIL=owner@example.com\nADMIN_PASSWORD=keep-admin-password\n"
                "CASHIER_EMAIL=cashier@example.com\nCASHIER_PASSWORD=keep-cashier-password\nCUSTOM_SETTING=keep-me\n",
                encoding="utf-8",
            )
            (install_dir / "release-manifest.json").write_text(
                json.dumps({"app_version": "v0.3.8"}), encoding="utf-8"
            )

            installer.ensure_runtime_environment(str(install_dir))

            root_values = installer._read_env_file(str(install_dir / ".env"))
            backend_values = installer._read_env_file(str(backend_dir / ".env"))
            self.assertEqual(root_values["POSTGRES_PASSWORD"], "keep-postgres")
            self.assertEqual(root_values["CUSTOM_ROOT"], "value")
            self.assertEqual(backend_values["DATABASE_URL"], "postgres://custom")
            self.assertEqual(backend_values["ADMIN_PASSWORD"], "keep-admin-password")
            self.assertEqual(backend_values["CASHIER_PASSWORD"], "keep-cashier-password")
            self.assertEqual(backend_values["CUSTOM_SETTING"], "keep-me")
            self.assertEqual(backend_values["APP_VERSION"], "0.3.8")
            self.assertEqual(backend_values["UPDATE_MANIFEST_URL"], installer_main.DEFAULT_UPDATE_MANIFEST_URL)


if __name__ == "__main__":
    unittest.main()
