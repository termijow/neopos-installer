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
        self.assertIn('"sudo", "install", "-o", "root", "-g", "root"', source)
        self.assertNotIn("WorkingDirectory={install_dir}", source)


if __name__ == "__main__":
    unittest.main()
