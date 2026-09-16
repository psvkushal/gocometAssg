import os
from pathlib import Path
import unittest
from unittest.mock import patch

from nova.config import Settings, load_settings


class SettingsTests(unittest.TestCase):
    def test_defaults_without_credentials(self):
        settings = load_settings({})
        self.assertEqual(settings, Settings())
        self.assertIsNone(settings.gemini_api_key)
        self.assertEqual(settings.storage_path, Path("data/nova.sqlite3"))

    def test_environment_overrides(self):
        settings = load_settings({
            "GEMINI_API_KEY": "test-secret",
            "NOVA_EXTRACTOR_MODEL": "extractor-test",
            "NOVA_VALIDATOR_MODEL": "validator-test",
            "NOVA_CONFIDENCE_THRESHOLD": "0.9",
            "NOVA_MAX_RETRIES": "0",
            "NOVA_STORAGE_PATH": "/tmp/nova-test.sqlite3",
        })
        self.assertEqual(settings, Settings(
            gemini_api_key="test-secret",
            extractor_model="extractor-test",
            validator_model="validator-test",
            confidence_threshold=0.9,
            max_retries=0,
            storage_path=Path("/tmp/nova-test.sqlite3"),
        ))
        self.assertNotIn("test-secret", repr(settings))

    def test_reads_process_environment_only_when_requested(self):
        with patch.dict(os.environ, {"NOVA_MAX_RETRIES": "4"}, clear=True):
            self.assertEqual(load_settings().max_retries, 4)
            self.assertEqual(load_settings({}).max_retries, 2)

    def test_invalid_environment_values(self):
        cases = {
            "NOVA_CONFIDENCE_THRESHOLD": ["-0.1", "1.1", "nan", "inf", "", "bad"],
            "NOVA_MAX_RETRIES": ["-1", "1.5", "", "bad"],
            "NOVA_EXTRACTOR_MODEL": ["", " "],
            "NOVA_VALIDATOR_MODEL": ["", " "],
            "NOVA_STORAGE_PATH": ["", " ", "."],
        }
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    load_settings({name: value})

    def test_threshold_boundaries(self):
        for value in ("0", "1"):
            self.assertEqual(load_settings({"NOVA_CONFIDENCE_THRESHOLD": value}).confidence_threshold, float(value))

    def test_direct_construction_validates_settings(self):
        for override in ({"confidence_threshold": float("nan")}, {"max_retries": -1}, {"max_retries": True}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                Settings(**override)


if __name__ == "__main__":
    unittest.main()
