import unittest

from pydantic import ValidationError

from nova.agents.router import route
from nova.schemas import RoutingDecision, RuleValidation, ValidationResult


def incoterm(status="MATCH", found="FOB"):
    return RuleValidation(
        rule="Only FOB or CIF Incoterms are accepted.", fields=["Incoterms"],
        status=status, found=found, expected="FOB or CIF",
        reason={
            "MATCH": "FOB is accepted.",
            "MISMATCH": "EXW is not accepted.",
            "UNCERTAIN": "The extracted value has insufficient confidence.",
        }[status],
    )


class RouterTests(unittest.TestCase):
    def test_all_matches_auto_approve(self):
        decision = route(ValidationResult(results=[incoterm()]))
        self.assertEqual(decision.outcome, "AUTO_APPROVE")
        self.assertTrue(decision.reason)
        self.assertIsNone(decision.amendment_request)
        self.assertEqual(RoutingDecision.model_validate_json(decision.model_dump_json()), decision)

    def test_mismatches_produce_draft_with_every_discrepancy(self):
        invoice = RuleValidation(
            rule="Invoice number must start with INV followed by digits.",
            fields=["Invoice No."], status="MISMATCH", found="ABC123",
            expected="INV followed by digits", reason="ABC is not the required prefix.",
        )
        decision = route(ValidationResult(results=[incoterm("MISMATCH", "EXW"), invoice]))
        self.assertEqual(decision.outcome, "AMENDMENT_REQUEST")
        for text in ("Incoterms", "EXW", "FOB or CIF", "Invoice No.", "ABC123", "INV followed by digits"):
            self.assertIn(text, decision.amendment_request)

    def test_uncertainty_routes_to_review_with_or_without_found_value(self):
        for found in (None, "FOB"):
            with self.subTest(found=found):
                decision = route(ValidationResult(results=[incoterm("UNCERTAIN", found)]))
                self.assertEqual(decision.outcome, "HUMAN_REVIEW")
                self.assertIn("Incoterms", decision.reason)
                self.assertIn("insufficient confidence", decision.reason)
                self.assertIsNone(decision.amendment_request)

    def test_uncertainty_wins_over_mismatch_regardless_of_order(self):
        mismatch = incoterm("MISMATCH", "EXW")
        uncertain = incoterm("UNCERTAIN", None)
        for results in ([mismatch, uncertain], [uncertain, mismatch]):
            with self.subTest(results=results):
                decision = route(ValidationResult(results=results))
                self.assertEqual(decision.outcome, "HUMAN_REVIEW")
                self.assertIn("EXW", decision.reason)
                self.assertIn("Unavailable", decision.reason)
                self.assertIsNone(decision.amendment_request)

    def test_cleared_assessments_cannot_auto_approve(self):
        validation = ValidationResult(results=[incoterm()])
        validation.results.clear()
        with self.assertRaises(ValueError):
            route(validation)

    def test_decision_rejects_inconsistent_draft(self):
        for payload in (
            {"outcome": "AMENDMENT_REQUEST", "reason": "Mismatch"},
            {"outcome": "AUTO_APPROVE", "reason": "Matches", "amendment_request": "Fix this"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                RoutingDecision.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
