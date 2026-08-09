import unittest

from scripts.render_release_notes import render_release_notes


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
