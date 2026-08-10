import io
import json
import unittest
import zipfile

from scripts.render_release_notes import render_release_notes
from scripts.stamp_neopos_release import build_manifest


class ReleaseNotesTests(unittest.TestCase):
    def test_renders_manifest_summary_and_compatibility(self):
        rendered = render_release_notes(
            {
                "app_version": "v0.3.6",
                "release_notes": "Muestra la versión instalada.",
                "database_migration": "additive",
                "breaking_changes": False,
            }
        )

        self.assertIn("NeoPOS Local v0.3.6", rendered)
        self.assertIn("Muestra la versión instalada.", rendered)
        self.assertIn("Actualización compatible", rendered)

    def test_rejects_empty_release_notes(self):
        with self.assertRaises(ValueError):
            render_release_notes({"app_version": "v0.3.6", "release_notes": ""})

    def test_public_manifest_exposes_stable_installer_downloads(self):
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("release-manifest.json", json.dumps({
                "app_version": "v0.3.8", "release_notes": "Actualización segura.",
            }))
        archive_bytes.seek(0)
        with zipfile.ZipFile(archive_bytes, "r") as archive:
            manifest = build_manifest(archive, "v0.3.8")

        self.assertEqual(manifest["version"], "v0.3.8")
        self.assertEqual(manifest["notes"], "Actualización segura.")
        self.assertTrue(manifest["download_urls"]["windows"].endswith("NeoPOS-Installer.exe"))
        self.assertTrue(manifest["download_urls"]["linux"].endswith("NeoPOS-Installer-Linux"))
