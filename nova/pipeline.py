"""Acyclic LangGraph orchestration of document review and result storage."""

from typing import Literal
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, ConfigDict, Field

from nova.documents import DocumentInput
from nova.agents.extractor import Extractor
from nova.agents.router import route
from nova.schemas import (
    CustomerRules, ExtractionResult, NonBlankText, RoutingDecision, ValidationResult,
)
from nova.agents.validator import Validator
from nova.persistence.storage import SQLiteResultStore, StoredResult


class PipelineInput(BaseModel):
    """One run's input; generate an ID unless a caller supplies one."""

    model_config = ConfigDict(
        extra="forbid", ser_json_bytes="base64", val_json_bytes="base64",
    )

    run_id: NonBlankText = Field(default_factory=lambda: str(uuid4()))
    document: DocumentInput
    rules: CustomerRules


class PipelineState(PipelineInput):
    """Completed stage outputs; no clients or secrets are stored in state."""

    # Saved state must retain its original ID, never generate a replacement.
    run_id: NonBlankText = Field(...)
    extraction: ExtractionResult | None = None
    validation: ValidationResult | None = None
    decision: RoutingDecision | None = None
    last_completed_stage: Literal["extractor", "validator", "router", "storage"] | None = None


def build_pipeline(
    extractor: Extractor, validator: Validator, *, checkpointer: BaseCheckpointSaver | None = None,
    store: SQLiteResultStore | None = None,
) -> CompiledStateGraph:
    """Build the graph with an optional caller-owned checkpointer.

    Technical exceptions propagate and stop downstream execution. The graph adds
    no retries: provider strategies own bounded transient-failure handling.
    """
    def extract_node(state: PipelineState) -> dict:
        return {
            "extraction": extractor.extract(state.document),
            "last_completed_stage": "extractor",
        }

    def validate_node(state: PipelineState) -> dict:
        if state.extraction is None:
            raise ValueError("Validator stage requires extraction output")
        return {
            "validation": validator.validate(state.extraction, state.rules),
            "last_completed_stage": "validator",
        }

    def route_node(state: PipelineState) -> dict:
        if state.validation is None:
            raise ValueError("Router stage requires validation output")
        return {
            "decision": route(state.validation),
            "last_completed_stage": "router",
        }

    def store_node(state: PipelineState) -> dict:
        if store is None or state.extraction is None or state.validation is None or state.decision is None:
            raise ValueError("Storage stage requires a store and all completed outputs")
        store.save(StoredResult(
            run_id=state.run_id, document_name=state.document.filename, rules=state.rules,
            extraction=state.extraction, validation=state.validation, decision=state.decision,
        ))
        return {"last_completed_stage": "storage"}

    graph = StateGraph(PipelineState, input_schema=PipelineInput)
    graph.add_node("extractor", extract_node)
    graph.add_node("validator", validate_node)
    graph.add_node("router", route_node)
    graph.add_edge(START, "extractor")
    graph.add_edge("extractor", "validator")
    graph.add_edge("validator", "router")
    if store is not None:
        graph.add_node("storage", store_node)
        graph.add_edge("router", "storage")
        graph.add_edge("storage", END)
    else:
        graph.add_edge("router", END)
    return graph.compile(checkpointer=checkpointer)
