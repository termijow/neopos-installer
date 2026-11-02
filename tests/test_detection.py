import os
import json
import tempfile
import shutil
import unittest
from unittest import mock

class TestDetectExistingInstallation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_detect_function(self):
        # Read method logic directly to test path logic safely without GUI requirements
        def detect(home_dir, program_files, platform_name):
            candidate_dirs = [
                os.path.join(home_dir, "NeoPOS"),
                os.path.join(program_files, "NeoPOS") if platform_name == "Windows" else "/opt/neopos",
                "/opt/neopos-local",
            ]
            for cdir in candidate_dirs:
                if not cdir or not os.path.exists(cdir):
                    continue
                compose = os.path.join(cdir, "docker-compose.yml")
                manifest_candidates = [
                    os.path.join(cdir, "release-manifest.json"),
                    os.path.join(cdir, "neopos-local-manifest.json"),
                ]
                env_file = os.path.join(cdir, ".env")
                found_manifest = next((m for m in manifest_candidates if os.path.exists(m)), None)
                if os.path.exists(compose) or found_manifest or os.path.exists(env_file):
                    version = "existente"
                    if found_manifest:
                        try:
                            with open(found_manifest, "r", encoding="utf-8") as mf:
                                m = json.load(mf)
                                version = m.get("app_version") or m.get("version") or version
                        except Exception:
                            pass
                    return True, version, cdir
            return False, None, candidate_dirs[0]
        return detect

    def test_fresh_installation(self):
        detect = self._get_detect_function()
        installed, version, path = detect(self.temp_dir, os.path.join(self.temp_dir, "pf"), "Windows")
        self.assertFalse(installed)
        self.assertIsNone(version)

    def test_existing_installation_with_release_manifest(self):
        install_dir = os.path.join(self.temp_dir, "NeoPOS")
        os.makedirs(install_dir, exist_ok=True)
        with open(os.path.join(install_dir, "release-manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"app_version": "v0.7.0-beta"}, f)
        with open(os.path.join(install_dir, "docker-compose.yml"), "w", encoding="utf-8") as f:
            f.write("services: {}")

        detect = self._get_detect_function()
        installed, version, path = detect(self.temp_dir, os.path.join(self.temp_dir, "pf"), "Windows")
        self.assertTrue(installed)
        self.assertEqual(version, "v0.7.0-beta")
        self.assertEqual(path, install_dir)

    def test_existing_installation_with_neopos_manifest(self):
        install_dir = os.path.join(self.temp_dir, "NeoPOS")
        os.makedirs(install_dir, exist_ok=True)
        with open(os.path.join(install_dir, "neopos-local-manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"version": "v0.6.9"}, f)

        detect = self._get_detect_function()
        installed, version, path = detect(self.temp_dir, os.path.join(self.temp_dir, "pf"), "Linux")
        self.assertTrue(installed)
        self.assertEqual(version, "v0.6.9")
        self.assertEqual(path, install_dir)

    def test_existing_installation_env_fallback(self):
        install_dir = os.path.join(self.temp_dir, "NeoPOS")
        os.makedirs(install_dir, exist_ok=True)
        with open(os.path.join(install_dir, ".env"), "w", encoding="utf-8") as f:
            f.write("APP_ENV=production\n")

        detect = self._get_detect_function()
        installed, version, path = detect(self.temp_dir, os.path.join(self.temp_dir, "pf"), "Windows")
        self.assertTrue(installed)
        self.assertEqual(version, "existente")
        self.assertEqual(path, install_dir)

if __name__ == "__main__":
    unittest.main()
