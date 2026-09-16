import unittest

from pydantic import ValidationError

from nova.config import Settings
from nova.documents import DocumentInput
from nova.agents.extractor import Extractor
from nova.models.base import ModelRequest


class FakeProvider:
    def __init__(self, response: str):
        self.response = response
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> str:
        self.requests.append(request)
        return self.response


class ExtractorTests(unittest.TestCase):
    def test_accepts_alternate_provider_and_supplies_extraction_contract(self):
        provider = FakeProvider('{"fields": [{"name": "Country of Origin", "value": null, "confidence": 0.1}]}')
        settings = Settings(extractor_model="another-provider-model")
        document = DocumentInput("invoice.pdf", "application/pdf", b"%PDF-1.7\n")
        result = Extractor(provider, settings).extract(document)
        self.assertIsNone(result.fields[0].value)
        self.assertEqual(result.fields[0].confidence, 0.1)
        self.assertEqual(len(provider.requests), 1)
        request = provider.requests[0]
        self.assertEqual(request.model, "another-provider-model")
        self.assertEqual(request.document, document)
        self.assertEqual(request.response_schema["required"], ["fields"])
        self.assertEqual(request.max_output_tokens, settings.extractor_max_output_tokens)

    def test_rejects_invalid_provider_output_without_another_call(self):
        provider = FakeProvider('{"fields": [{"name": "Invoice No."}]}')
        with self.assertRaises(ValidationError):
            Extractor(provider, Settings()).extract(
                DocumentInput("invoice.pdf", "application/pdf", b"%PDF-1.7\n"))
        self.assertEqual(len(provider.requests), 1)


if __name__ == "__main__":
    unittest.main()
