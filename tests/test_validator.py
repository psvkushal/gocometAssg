import json
import unittest

from pydantic import ValidationError

from nova.config import Settings
from nova.model import ModelRequest
from nova.schemas import CustomerRules, ExtractionResult
from nova.validator import Validator


RULES = CustomerRules(text="Only FOB or CIF Incoterms are accepted.", source="fixture")


class FakeProvider:
    def __init__(self, response):
        self.response = json.dumps(response)
        self.requests: list[ModelRequest] = []

    def generate(self, request):
        self.requests.append(request)
        return self.response


def extraction(value="FOB", confidence=0.95):
    return ExtractionResult.model_validate({"fields": [
        {"name": "Trade Terms", "value": value, "confidence": confidence},
    ]})


def assessment(**overrides):
    return {"results": [{
        "rule": RULES.text, "fields": ["Incoterms"], "status": "MATCH",
        "found": "FOB", "expected": "FOB or CIF", "reason": "FOB is accepted.",
        "source_field_indices": [0], **overrides,
    }]}


class ValidatorTests(unittest.TestCase):
    def test_passes_rules_and_context_to_provider_and_accepts_match(self):
        provider = FakeProvider(assessment())
        result = Validator(provider, Settings()).validate(extraction(), RULES)
        self.assertEqual(result.results[0].status, "MATCH")
        request = provider.requests[0]
        data = json.loads(request.text)
        self.assertEqual(data["customer_rules"], RULES.text)
        self.assertEqual(data["extracted_fields"][0]["name"], "Trade Terms")
        self.assertIsNone(request.document)
        self.assertEqual(len(provider.requests), 1)

    def test_keeps_clear_mismatch_without_retry(self):
        provider = FakeProvider(assessment(status="MISMATCH", found="EXW", reason="EXW is not allowed."))
        result = Validator(provider, Settings()).validate(extraction("EXW"), RULES)
        self.assertEqual(result.results[0].status, "MISMATCH")
        self.assertEqual(result.results[0].found, "EXW")
        self.assertEqual(len(provider.requests), 1)

    def test_low_confidence_or_null_source_cannot_match_or_mismatch(self):
        for status in ("MATCH", "MISMATCH"):
            for value, confidence in ((None, 0.95), ("FOB", 0.2)):
                with self.subTest(status=status, value=value):
                    provider = FakeProvider(assessment(status=status))
                    result = Validator(provider, Settings()).validate(extraction(value, confidence), RULES)
                    self.assertEqual(result.results[0].status, "UNCERTAIN")
                    self.assertEqual(result.results[0].found, value)
                    self.assertEqual(len(provider.requests), 1)

    def test_missing_source_cannot_be_approved(self):
        provider = FakeProvider(assessment(source_field_indices=[]))
        result = Validator(provider, Settings()).validate(ExtractionResult(fields=[]), RULES)
        self.assertEqual(result.results[0].status, "UNCERTAIN")
        self.assertIsNone(result.results[0].found)

    def test_preserves_model_uncertainty_with_confident_extraction(self):
        provider = FakeProvider(assessment(status="UNCERTAIN", reason="The rule is ambiguous."))
        result = Validator(provider, Settings()).validate(extraction(), RULES)
        self.assertEqual(result.results[0].status, "UNCERTAIN")
        self.assertEqual(result.results[0].reason, "The rule is ambiguous.")

    def test_rejects_invalid_references_and_malformed_response_without_retry(self):
        for response, error in ((assessment(source_field_indices=[10]), ValueError),
                                ({"results": []}, ValidationError)):
            with self.subTest(response=response):
                provider = FakeProvider(response)
                with self.assertRaises(error):
                    Validator(provider, Settings()).validate(extraction(), RULES)
                self.assertEqual(len(provider.requests), 1)


if __name__ == "__main__":
    unittest.main()
