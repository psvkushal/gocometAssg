import unittest

from pydantic import ValidationError

from nova.schemas import ExtractedField, ExtractionResult


class ExtractionSchemaTests(unittest.TestCase):
    def test_json_round_trip_preserves_discovered_fields_and_repeated_names(self):
        payload = {"fields": [
            {"name": "Country of Origin", "value": "India", "confidence": 0.95},
            {"name": "Consignee / Address", "value": "Hamburg, Germany", "confidence": 0.95,
             "evidence": {"page": 1, "snippet": "Consignee: Address: Hamburg, Germany"}},
            {"name": "Buyer / Address", "value": "Berlin, Germany", "confidence": 0.95,
             "evidence": {"page": 1, "snippet": "Buyer: Address: Berlin, Germany"}},
            {"name": "HS Code", "value": "01234567", "confidence": 0.95,
             "evidence": {"page": 1, "snippet": "Item 1: HS Code 01234567"}},
            {"name": "HS Code", "value": "87654321", "confidence": 0.9,
             "evidence": {"page": 2, "snippet": "Item 2: HS Code 87654321"}},
            {"name": "Gross Weight", "value": "1,200 kg", "confidence": 0.95},
            {"name": "Incoterms", "value": "EXW", "confidence": 0.95},
        ]}
        result = ExtractionResult.model_validate(payload)
        restored = ExtractionResult.model_validate_json(result.model_dump_json())
        self.assertEqual(restored.model_dump(exclude_none=True), payload)

    def test_missing_targets_unreadable_values_and_low_confidence_are_preserved(self):
        result = ExtractionResult.model_validate({"fields": [
            {"name": "Invoice No.", "value": None, "confidence": 0.0},
            {"name": "Buyer", "value": "RheinTech?", "confidence": 0.2},
        ]})
        self.assertEqual(len(result.fields), 2)
        self.assertIsNone(result.fields[0].value)
        self.assertEqual(result.fields[1].name, "Buyer")
        self.assertEqual(result.fields[1].confidence, 0.2)
        self.assertEqual(ExtractionResult.model_validate({"fields": []}).fields, [])

    def test_rejects_malformed_field_output(self):
        valid = {"name": "Invoice No.", "value": "INV123", "confidence": 0.9}
        cases = [
            *(dict(valid, name=value) for value in ("", "   ", None, 123)),
            *(dict(valid, value=value) for value in (123, "", "   ")),
            *(dict(valid, confidence=value)
              for value in (-0.1, 1.1, float("nan"), float("inf"), "0.9", True)),
            dict(valid, invented="extra"),
            dict(valid, evidence={"page": 0}),
            *({key: value for key, value in valid.items() if key != missing}
              for missing in ("name", "value", "confidence")),
        ]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ExtractedField.model_validate(payload)

    def test_requires_a_list_and_rejects_old_fixed_shape(self):
        for payload in ({}, {"fields": None}, {"fields": {}},
                        {"hs_code": {"value": "01234567", "confidence": 0.9}},
                        {"fields": [], "unexpected": True}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ExtractionResult.model_validate(payload)

    def test_json_schema_describes_named_entries_with_nullable_values(self):
        schema = ExtractionResult.model_json_schema()
        self.assertEqual(schema["required"], ["fields"])
        self.assertEqual(schema["properties"]["fields"]["type"], "array")
        entry = schema["$defs"]["ExtractedField"]
        self.assertEqual(set(entry["required"]), {"name", "value", "confidence"})
        self.assertIn({"type": "null"}, entry["properties"]["value"]["anyOf"])
        self.assertNotIn("enum", entry["properties"]["name"])
        self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
