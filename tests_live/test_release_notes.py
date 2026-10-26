"""Release notes must select exactly the requested version before publishing."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("release_notes", Path(__file__).resolve().parents[1] / "scripts/release_notes.py")
release_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_notes)


class ReleaseNotesTests(unittest.TestCase):
    def test_selects_exact_version_and_stops_at_next_section(self):
        changelog = "# Changes\n\n## [0.1.10] - 2026-10-26\nWrong\n\n## [0.1.1] - 2026-10-26\nExpected\n\n## [0.1.0] - 2026-10-26\nOlder\n"
        self.assertEqual(release_notes.section(changelog, "0.1.1"), "Expected\n")

    def test_missing_or_empty_version_fails(self):
        for content in ("## [0.1.10]\nWrong\n", "## [0.1.1]\n\n## [0.1.0]\nOlder\n"):
            with self.assertRaises(LookupError):
                release_notes.section(content, "0.1.1")
