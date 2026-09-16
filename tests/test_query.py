from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nova.query import SUPPORTED_QUESTIONS, UnsupportedQuestion, ask
from nova.agents.router import route
from nova.schemas import CustomerRules, ExtractionResult, RuleValidation, ValidationResult
from nova.persistence.storage import SQLiteResultStore, StoredResult


def result(run_id, *statuses):
    assessments = []
    for status in statuses:
        assessments.append(RuleValidation(
            rule="Only FOB or CIF Incoterms are accepted.", fields=["Incoterms"],
            status=status, found=None if status == "UNCERTAIN" else "EXW" if status == "MISMATCH" else "FOB",
            expected="FOB or CIF", reason="Fixture assessment.",
        ))
    validation = ValidationResult(results=assessments)
    return StoredResult(
        run_id=run_id, document_name="invoice.pdf",
        rules=CustomerRules(text="Only FOB or CIF Incoterms are accepted.", source="fixture"),
        extraction=ExtractionResult(fields=[]), validation=validation, decision=route(validation),
    )


class QueryTests(unittest.TestCase):
    def test_counts_outcomes_and_mismatches_independently(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nova.sqlite3"
            store = SQLiteResultStore(path)
            for item in (result("approved", "MATCH"), result("amend", "MISMATCH"),
                         result("review", "MISMATCH", "UNCERTAIN")):
                store.save(item)
            self.assertEqual(ask(SUPPORTED_QUESTIONS[0], path).count, 1)
            self.assertEqual(ask(SUPPORTED_QUESTIONS[1], path).count, 1)
            self.assertEqual(ask(SUPPORTED_QUESTIONS[2], path).count, 2)

    def test_field_frequency_counts_documents_not_duplicate_rule_findings(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nova.sqlite3"
            store = SQLiteResultStore(path)
            store.save(result("one", "MISMATCH", "MISMATCH"))
            store.save(result("two", "MISMATCH", "UNCERTAIN"))
            answer = ask(SUPPORTED_QUESTIONS[3], path)
            self.assertEqual(answer.field_counts, {"Incoterms": 2})
            self.assertIn("Incoterms: 2", answer.answer)

    def test_empty_store_has_zero_counts(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nova.sqlite3"
            SQLiteResultStore(path)
            self.assertEqual(ask(SUPPORTED_QUESTIONS[0], path).count, 0)
            self.assertEqual(ask(SUPPORTED_QUESTIONS[3], path).field_counts, {})

    def test_unsupported_filters_are_not_silently_ignored(self):
        for question in (
            "How many documents were auto-approved this week?",
            "How many documents were auto-approved for RheinTech?",
            "Delete all results",
        ):
            with self.subTest(question=question), self.assertRaises(UnsupportedQuestion):
                ask(question, "unused.sqlite3")


if __name__ == "__main__":
    unittest.main()
