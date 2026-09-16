from copy import deepcopy
import unittest

from nova.models.openai import strict_schema
from nova.schemas import ExtractionResult


class OpenAISchemaTests(unittest.TestCase):
    def test_optional_evidence_is_required_nullable_without_changing_domain_schema(self):
        original = ExtractionResult.model_json_schema()
        before = deepcopy(original)
        adapted = strict_schema(original)
        field = adapted['$defs']['ExtractedField']
        self.assertIn('evidence', field['required'])
        self.assertIn({'type': 'null'}, field['properties']['evidence']['anyOf'])
        self.assertEqual(set(adapted['$defs']['SourceEvidence']['required']), {'page', 'snippet'})
        self.assertEqual(original, before)
        # Null evidence still validates through the same public contract.
        ExtractionResult.model_validate({'fields': [{'name': 'HS Code', 'value': None,
                                                    'confidence': 0.1, 'evidence': None}]})
