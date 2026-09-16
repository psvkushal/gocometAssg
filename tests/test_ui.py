from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from nova.config import Settings
from nova.models.base import ModelResponseError
from test_pipeline import ScriptedProvider, responses_for


UI_PATH = Path(__file__).resolve().parent.parent / "nova" / "ui.py"


class UITests(unittest.TestCase):
    def test_upload_review_and_query_use_pipeline_results(self):
        with TemporaryDirectory() as directory:
            settings = Settings(validator_provider="openai", validator_model="gpt-5.4-nano",
                                storage_path=Path(directory) / "nova.sqlite3")
            provider = ScriptedProvider(responses_for("EXW", 0.95, "MISMATCH"))
            with patch("nova.config.load_settings", return_value=settings), patch(
                "nova.models.gemini.GeminiProvider.generate", side_effect=provider.generate,
            ), patch("nova.models.openai.OpenAIProvider.generate", side_effect=provider.generate):
                app = AppTest.from_file(str(UI_PATH), default_timeout=10).run()
                app.file_uploader[0].set_value(("invoice.pdf", b"%PDF-1.7\n", "application/pdf"))
                app.button[0].click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state["review_state"].decision.outcome, "AMENDMENT_REQUEST")
                self.assertTrue(any(element.value == "AMENDMENT REQUEST" for element in app.error))
                self.assertEqual(len(provider.requests), 2)
                run_id = app.session_state["review_state"].run_id
                self.assertIn("invoice.pdf", app.selectbox[0].options[0])
                app.selectbox[0].select(run_id)
                app.button[1].click().run()
                self.assertEqual(app.session_state["review_state"].run_id, run_id)
                self.assertEqual(len(provider.requests), 2)
                app.selectbox[1].select("How many documents had mismatches?")
                app.button[3].click().run()
                self.assertFalse(app.exception)
                self.assertTrue(any("1 document(s) had at least one mismatch" in item.value for item in app.text))
                self.assertEqual(len(provider.requests), 2)

    def test_failed_validation_is_visible_and_resumes_without_reextraction(self):
        with TemporaryDirectory() as directory:
            settings = Settings(gemini_api_key="test-key", storage_path=Path(directory) / "nova.sqlite3")
            extraction, validation = responses_for("FOB", 0.95, "MATCH")
            provider = ScriptedProvider([extraction, ModelResponseError("blocked response"), validation])
            with patch("nova.config.load_settings", return_value=settings), patch(
                "nova.models.gemini.GeminiProvider.generate", side_effect=provider.generate,
            ):
                app = AppTest.from_file(str(UI_PATH), default_timeout=10).run()
                app.file_uploader[0].set_value(("invoice.pdf", b"%PDF-1.7\n", "application/pdf"))
                app.button[0].click().run()
                self.assertFalse(app.exception)
                state = app.session_state["review_state"]
                self.assertEqual(state.last_completed_stage, "extractor")
                self.assertTrue(any("Operation failed" in item.value for item in app.error))
                app.selectbox[0].select(state.run_id)
                app.button[2].click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state["review_state"].last_completed_stage, "storage")
                self.assertTrue(any(item.value == "AUTO APPROVE" for item in app.success))
                self.assertEqual(len(provider.requests), 3)


if __name__ == "__main__":
    unittest.main()
