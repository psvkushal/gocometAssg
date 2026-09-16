from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nova.persistence.checkpoints import open_pipeline
from nova.config import Settings
from nova.agents.extractor import Extractor
from nova.models.base import ModelResponseError
from nova.agents.validator import Validator
from test_pipeline import ScriptedProvider, input_for, responses_for


def open_run(path, provider):
    settings = Settings()
    return open_pipeline(path, Extractor(provider, settings), Validator(provider, settings))


class CheckpointTests(unittest.TestCase):
    def test_reopen_and_resume_failed_validation_without_reextracting(self):
        extraction, validation = responses_for("FOB", 0.95, "MATCH")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoints.sqlite3"
            first_provider = ScriptedProvider([extraction, ModelResponseError("Provider unavailable")])
            with open_run(path, first_provider) as pipeline:
                with self.assertRaises(ModelResponseError):
                    pipeline.start(input_for("recoverable"))
            # Recreate the connection, graph, and services to avoid relying on memory.
            second_provider = ScriptedProvider([validation])
            with open_run(path, second_provider) as pipeline:
                snapshot = pipeline.inspect("recoverable")
                self.assertEqual(snapshot.values["last_completed_stage"], "extractor")
                self.assertEqual(snapshot.next, ("validator",))
                self.assertTrue(any(task.error for task in snapshot.tasks))
                self.assertEqual(snapshot.values["document"].content, input_for("recoverable").document.content)
                result = pipeline.resume("recoverable")
                self.assertEqual(result.decision.outcome, "AUTO_APPROVE")
                self.assertEqual(result.last_completed_stage, "storage")
                self.assertEqual(len(second_provider.requests), 1)
                self.assertIsNone(second_provider.requests[0].document)
                self.assertFalse(pipeline.inspect("recoverable").next)

    def test_completed_outcomes_survive_reopening_without_new_calls(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoints.sqlite3"
            cases = (("EXW", 0.95, "MISMATCH", "AMENDMENT_REQUEST"),
                     ("FOB", 0.2, "MATCH", "HUMAN_REVIEW"))
            for value, confidence, status, outcome in cases:
                provider = ScriptedProvider(responses_for(value, confidence, status))
                with open_run(path, provider) as pipeline:
                    pipeline.start(input_for(outcome))
            no_calls = ScriptedProvider([])
            with open_run(path, no_calls) as pipeline:
                for _, _, _, outcome in cases:
                    result = pipeline.resume(outcome)
                    self.assertEqual(result.decision.outcome, outcome)
                    with self.assertRaisesRegex(ValueError, "already exists"):
                        pipeline.start(input_for(outcome))
                self.assertEqual(no_calls.requests, [])
                with self.assertRaises(KeyError):
                    pipeline.resume("unknown")

    def test_failed_extraction_resumes_from_extractor(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoints.sqlite3"
            provider = ScriptedProvider([ModelResponseError("Extraction failed")])
            with open_run(path, provider) as pipeline:
                with self.assertRaises(ModelResponseError):
                    pipeline.start(input_for("retry-extraction"))
            recovered = ScriptedProvider(responses_for("FOB", 0.95, "MATCH"))
            with open_run(path, recovered) as pipeline:
                self.assertEqual(pipeline.inspect("retry-extraction").next, ("extractor",))
                result = pipeline.resume("retry-extraction")
                self.assertEqual(result.decision.outcome, "AUTO_APPROVE")
                self.assertEqual(len(recovered.requests), 2)


if __name__ == "__main__":
    unittest.main()
