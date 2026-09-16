"""Queryable completed review results, separate from LangGraph checkpoints."""

from contextlib import closing
from pathlib import Path
import sqlite3

from pydantic import BaseModel, ConfigDict

from nova.schemas import (
    CustomerRules, ExtractionResult, NonBlankText, RoutingDecision, ValidationResult,
)


class StoredResult(BaseModel):
    """A completed review; the run ID links back to the document in checkpoints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: NonBlankText
    document_name: NonBlankText
    rules: CustomerRules
    extraction: ExtractionResult
    validation: ValidationResult
    decision: RoutingDecision


class SQLiteResultStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS review_results (
                    run_id TEXT PRIMARY KEY,
                    document_name TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    has_mismatches INTEGER NOT NULL,
                    saved_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    result_json TEXT NOT NULL
                )
            """)

    def save(self, result: StoredResult) -> None:
        """Repeated identical saves are harmless; conflicting run IDs are rejected."""
        payload = result.model_dump_json()
        has_mismatches = False
        for assessment in result.validation.results:
            if assessment.status == "MISMATCH":
                has_mismatches = True
                break
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                """INSERT INTO review_results
                   (run_id, document_name, outcome, has_mismatches, result_json)
                   VALUES (?, ?, ?, ?, ?) ON CONFLICT(run_id) DO NOTHING""",
                (result.run_id, result.document_name, result.decision.outcome, has_mismatches, payload),
            )
            existing = connection.execute(
                "SELECT result_json FROM review_results WHERE run_id = ?", (result.run_id,),
            ).fetchone()
            if existing[0] != payload:
                raise ValueError(f"A different result already exists for run: {result.run_id}")

    def get(self, run_id: str) -> StoredResult:
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                "SELECT result_json FROM review_results WHERE run_id = ?", (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"No stored result for run: {run_id}")
        return StoredResult.model_validate_json(row[0])
