import unittest

from pydantic import ValidationError

from nova.schemas import RuleValidation, ValidationResult


def assessment(**overrides):
    return {
        "rule": "Only FOB or CIF Incoterms are accepted.",
        "fields": ["Incoterms"],
        "status": "MATCH",
        "found": "FOB",
        "expected": "FOB or CIF",
        "reason": "FOB is accepted by this rule.",
        **overrides,
    }


class ValidationSchemaTests(unittest.TestCase):
    def test_round_trip_all_three_outcomes_including_unextracted_field(self):
        payload = {"results": [
            assessment(),
            assessment(status="MISMATCH", found="EXW", reason="EXW is not accepted."),
            assessment(
                rule="Country of origin must be India.", fields=["Country of Origin"],
                status="UNCERTAIN", found=None, expected="India",
                reason="Country of origin is absent from extraction.",
            ),
        ]}
        result = ValidationResult.model_validate(payload)
        restored = ValidationResult.model_validate_json(result.model_dump_json())
        self.assertEqual(restored.model_dump(), payload)

    def test_missing_data_cannot_be_match_or_mismatch(self):
        for status in ("MATCH", "MISMATCH"):
            with self.subTest(status=status), self.assertRaises(ValidationError):
                RuleValidation.model_validate(assessment(status=status, found=None))

    def test_uncertainty_accepts_a_non_null_found_value(self):
        result = RuleValidation.model_validate(assessment(
            status="UNCERTAIN", found="FOB",
            reason="Extraction confidence is too low to evaluate this reliably.",
        ))
        self.assertEqual(result.found, "FOB")
        self.assertEqual(result.status, "UNCERTAIN")

    def test_rejects_incomplete_or_malformed_assessments(self):
        cases = [
            assessment(status="APPROVED"), assessment(fields=[]), assessment(fields=[" "]),
            assessment(rule=" "), assessment(expected=""), assessment(reason=""),
            assessment(found=" "), assessment(extra="unexpected"),
        ]
        for missing in ("rule", "fields", "status", "found", "expected", "reason"):
            payload = assessment()
            del payload[missing]
            cases.append(payload)
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                RuleValidation.model_validate(payload)

    def test_rejects_empty_results(self):
        with self.assertRaises(ValidationError):
            ValidationResult.model_validate({"results": []})

    def test_exports_required_results_and_allowed_statuses(self):
        schema = ValidationResult.model_json_schema()
        self.assertEqual(schema["required"], ["results"])
        self.assertEqual(
            schema["$defs"]["RuleValidation"]["properties"]["status"]["enum"],
            ["MATCH", "MISMATCH", "UNCERTAIN"],
        )


if __name__ == "__main__":
    unittest.main()
