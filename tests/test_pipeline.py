import json
import unittest

from nova.config import Settings
from nova.documents import DocumentInput
from nova.agents.extractor import Extractor
from nova.models.base import ModelRequest, ModelResponseError
from nova.pipeline import PipelineInput, PipelineState, build_pipeline
from nova.schemas import CustomerRules
from nova.agents.validator import Validator


class ScriptedProvider:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests: list[ModelRequest] = []

    def generate(self, request):
        self.requests.append(request)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return json.dumps(response)


def input_for(run_id):
    return PipelineInput(
        run_id=run_id,
        document=DocumentInput("invoice.png", "image/png", b"\x89PNG\r\n\x1a\n"),
        rules=CustomerRules(text="Only FOB or CIF Incoterms are accepted.", source="fixture"),
    )


def responses_for(value, confidence, status):
    return [
        {"fields": [{"name": "Incoterms", "value": value, "confidence": confidence}]},
        {"results": [{
            "rule": "Only FOB or CIF Incoterms are accepted.", "fields": ["Incoterms"],
            "status": status, "found": value, "expected": "FOB or CIF",
            "reason": "EXW is not accepted." if status == "MISMATCH" else "FOB is accepted.",
            "source_field_indices": [0],
        }]},
    ]


class PipelineTests(unittest.TestCase):
    def test_new_runs_generate_ids_and_keep_them_through_execution(self):
        inputs = input_for("fixture")
        first = PipelineInput(document=inputs.document, rules=inputs.rules)
        second = PipelineInput(document=inputs.document, rules=inputs.rules)
        self.assertNotEqual(first.run_id, second.run_id)
        provider = ScriptedProvider(responses_for("FOB", 0.95, "MATCH"))
        settings = Settings()
        graph = build_pipeline(Extractor(provider, settings), Validator(provider, settings))
        result = PipelineState.model_validate(graph.invoke(first))
        self.assertEqual(result.run_id, first.run_id)

    def test_three_business_outcomes_use_one_call_per_model_stage(self):
        for value, confidence, status, outcome in (
            ("FOB", 0.95, "MATCH", "AUTO_APPROVE"),
            ("EXW", 0.95, "MISMATCH", "AMENDMENT_REQUEST"),
            ("FOB", 0.2, "MATCH", "HUMAN_REVIEW"),
        ):
            with self.subTest(outcome=outcome):
                provider = ScriptedProvider(responses_for(value, confidence, status))
                settings = Settings()
                graph = build_pipeline(Extractor(provider, settings), Validator(provider, settings))
                state = PipelineState.model_validate(graph.invoke(input_for(outcome)))
                self.assertEqual(state.decision.outcome, outcome)
                self.assertEqual(state.last_completed_stage, "router")
                self.assertEqual(state.extraction.fields[0].value, value)
                self.assertEqual(len(provider.requests), 2)
                self.assertEqual(json.loads(provider.requests[1].text)["extracted_fields"][0]["value"], value)
                self.assertEqual(PipelineState.model_validate_json(state.model_dump_json()), state)

    def test_failure_stops_downstream_stages_without_graph_retry(self):
        extraction = responses_for("FOB", 0.95, "MATCH")[0]
        for responses, expected_stages in (
            ([ModelResponseError("Extraction failed")], []),
            ([extraction, ModelResponseError("Validation failed")], ["extractor"]),
        ):
            with self.subTest(expected_stages=expected_stages):
                provider = ScriptedProvider(responses)
                settings = Settings()
                graph = build_pipeline(Extractor(provider, settings), Validator(provider, settings))
                completed = []
                with self.assertRaises(ModelResponseError):
                    for update in graph.stream(input_for("failed-run"), stream_mode="updates"):
                        completed.extend(update)
                self.assertEqual(completed, expected_stages)
                self.assertEqual(len(provider.requests), len(responses))

    def test_reusing_graph_does_not_keep_previous_run_outputs(self):
        provider = ScriptedProvider(
            responses_for("EXW", 0.95, "MISMATCH") + responses_for("FOB", 0.95, "MATCH"))
        settings = Settings()
        graph = build_pipeline(Extractor(provider, settings), Validator(provider, settings))
        first = PipelineState.model_validate(graph.invoke(input_for("first")))
        second = PipelineState.model_validate(graph.invoke(input_for("second")))
        self.assertEqual(first.decision.outcome, "AMENDMENT_REQUEST")
        self.assertEqual(second.run_id, "second")
        self.assertEqual(second.decision.outcome, "AUTO_APPROVE")
        self.assertIsNone(second.decision.amendment_request)


if __name__ == "__main__":
    unittest.main()
