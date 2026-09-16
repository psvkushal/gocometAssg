from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nova.persistence.storage import SQLiteResultStore
from test_checkpoints import open_run
from test_pipeline import ScriptedProvider, input_for, responses_for


class ResultStorageTests(unittest.TestCase):
    def test_pipeline_stores_all_outcomes_and_exact_results(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nova.sqlite3"
            for value, confidence, status, outcome in (
                ("FOB", 0.95, "MATCH", "AUTO_APPROVE"),
                ("EXW", 0.95, "MISMATCH", "AMENDMENT_REQUEST"),
                ("FOB", 0.2, "MATCH", "HUMAN_REVIEW"),
            ):
                with self.subTest(outcome=outcome):
                    provider = ScriptedProvider(responses_for(value, confidence, status))
                    with open_run(path, provider) as pipeline:
                        state = pipeline.start(input_for(outcome))
                    store = SQLiteResultStore(path)
                    result = store.get(outcome)
                    self.assertEqual(state.last_completed_stage, "storage")
                    self.assertEqual(result.extraction, state.extraction)
                    self.assertEqual(result.validation, state.validation)
                    self.assertEqual(result.decision, state.decision)
                    self.assertEqual(result.rules, state.rules)
                    store.save(result)
                    with closing(sqlite3.connect(path)) as connection:
                        rows = connection.execute(
                            "SELECT outcome, has_mismatches, saved_at FROM review_results WHERE run_id = ?",
                            (outcome,),
                        ).fetchall()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0][0], outcome)
                    self.assertEqual(bool(rows[0][1]), status == "MISMATCH")
                    self.assertTrue(rows[0][2])
                    changed = result.model_copy(update={"document_name": "different.pdf"})
                    with self.assertRaisesRegex(ValueError, "different result"):
                        store.save(changed)
                    self.assertEqual(store.get(outcome), result)

    def test_resume_after_write_before_checkpoint_does_not_repeat_models_or_duplicate_result(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nova.sqlite3"
            provider = ScriptedProvider(responses_for("FOB", 0.95, "MATCH"))
            original_save = SQLiteResultStore.save

            def save_then_fail(store, result):
                original_save(store, result)
                raise RuntimeError("Stopped after saving result")

            with open_run(path, provider) as pipeline:
                with patch.object(SQLiteResultStore, "save", save_then_fail):
                    with self.assertRaisesRegex(RuntimeError, "Stopped after"):
                        pipeline.start(input_for("recover-storage"))
                snapshot = pipeline.inspect("recover-storage")
                self.assertEqual(snapshot.next, ("storage",))
                self.assertEqual(snapshot.values["last_completed_stage"], "router")
            no_calls = ScriptedProvider([])
            with open_run(path, no_calls) as pipeline:
                state = pipeline.resume("recover-storage")
                self.assertEqual(state.last_completed_stage, "storage")
            self.assertEqual(no_calls.requests, [])
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM review_results").fetchone()[0], 1)

    def test_missing_result_is_explicit(self):
        with TemporaryDirectory() as directory:
            store = SQLiteResultStore(Path(directory) / "nova.sqlite3")
            with self.assertRaises(KeyError):
                store.get("unknown")


if __name__ == "__main__":
    unittest.main()
