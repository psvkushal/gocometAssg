"""SQLite-backed start/resume operations for one pipeline run at a time."""

from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from nova.documents import DocumentInput
from nova.agents.extractor import Extractor
from nova.pipeline import PipelineInput, PipelineState, build_pipeline
from nova.schemas import (
    CustomerRules, ExtractedField, ExtractionResult, RoutingDecision, RuleValidation,
    SourceEvidence, ValidationResult,
)
from nova.agents.validator import Validator
from nova.persistence.storage import SQLiteResultStore


class CheckpointedPipeline:
    """Local synchronous runner. Do not start/resume the same run concurrently."""

    def __init__(self, graph: CompiledStateGraph) -> None:
        self.graph = graph

    @staticmethod
    def _config(run_id: str) -> dict:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be non-blank")
        return {"configurable": {"thread_id": run_id}}

    def inspect(self, run_id: str) -> StateSnapshot:
        """Return persisted values, next stages, and task errors for an existing run."""
        snapshot = self.graph.get_state(self._config(run_id))
        if not snapshot.values:
            raise KeyError(f"Unknown pipeline run: {run_id}")
        return snapshot

    def list_runs(self) -> dict[str, str]:
        """Latest document label per run, including interrupted runs (local POC)."""
        runs = {}
        # Saver lists newest checkpoints first; skip earlier versions of each run.
        for saved in self.graph.checkpointer.list(None):
            config = saved.config["configurable"]
            run_id = config["thread_id"]
            if config.get("checkpoint_ns", "") or run_id in runs:
                continue
            values = saved.checkpoint["channel_values"]
            document = values.get("document")
            if document is None:
                continue
            stage = values.get("last_completed_stage") or "not completed"
            runs[run_id] = f"{document.filename} — {run_id} — {stage}"
        return runs

    def start(self, inputs: PipelineInput) -> PipelineState:
        config = self._config(inputs.run_id)
        if self.graph.get_state(config).values:
            raise ValueError(f"Run already exists; resume it or use a new ID: {inputs.run_id}")
        output = self.graph.invoke(inputs, config, durability="sync")
        return PipelineState.model_validate(output)

    def resume(self, run_id: str) -> PipelineState:
        snapshot = self.inspect(run_id)
        if not snapshot.next:
            return PipelineState.model_validate(snapshot.values)
        # None resumes pending work; supplying the original input would start over.
        output = self.graph.invoke(None, self._config(run_id), durability="sync")
        return PipelineState.model_validate(output)


@contextmanager
def open_pipeline(
    path: str | Path, extractor: Extractor, validator: Validator,
) -> Iterator[CheckpointedPipeline]:
    """Keep the SQLite connection alive for all operations inside the context."""
    database = Path(path).expanduser()
    database.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteResultStore(database)
    serde = JsonPlusSerializer(allowed_msgpack_modules=[
        DocumentInput, CustomerRules, SourceEvidence, ExtractedField, ExtractionResult,
        RuleValidation, ValidationResult, RoutingDecision, PipelineInput, PipelineState,
    ])
    with closing(sqlite3.connect(str(database), check_same_thread=False)) as connection:
        saver = SqliteSaver(connection, serde=serde)
        graph = build_pipeline(extractor, validator, checkpointer=saver, store=store)
        yield CheckpointedPipeline(graph)
