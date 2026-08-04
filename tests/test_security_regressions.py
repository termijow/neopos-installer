from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecurityRegressionTests(unittest.TestCase):
    def test_uninstaller_never_runs_global_docker_prune(self):
        source = (ROOT / "uninstaller.py").read_text(encoding="utf-8")
        self.assertNotIn('"system", "prune"', source)

    def test_linux_service_uses_root_owned_runtime(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('LINUX_RUNTIME_DIR = "/opt/neopos-local"', source)
        self.assertIn("WorkingDirectory={LINUX_RUNTIME_DIR}", source)
        self.assertIn('"install", "-o", "root", "-g", "root"', source)
        self.assertIn("privileged=True", source)
        self.assertNotIn("WorkingDirectory={install_dir}", source)

    def test_sudo_password_is_not_passed_as_a_command_argument(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('input=password + "\\n"', source)
        self.assertIn('["sudo", "-S", "-k", "-p", "", "--", "true"]', source)
        self.assertNotIn('command.append(self._sudo_password)', source)


if __name__ == "__main__":
    unittest.main()
