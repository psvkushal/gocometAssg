"""Small, grounded question interface over completed review results."""

import argparse
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3


SUPPORTED_QUESTIONS = (
    "How many documents were auto-approved?",
    "How many documents required human review?",
    "How many documents had mismatches?",
    "Which fields most frequently failed validation?",
)

_QUESTION_TYPES = {
    "how many documents were auto approved": "approvals",
    "how many documents required human review": "reviews",
    "how many required human review": "reviews",
    "how many documents had mismatches": "mismatches",
    "how many had mismatches": "mismatches",
    "which fields most frequently failed validation": "fields",
    "which fields had the most mismatches": "fields",
}


@dataclass(frozen=True)
class QueryAnswer:
    question: str
    answer: str
    count: int | None = None
    field_counts: dict[str, int] = field(default_factory=dict)


class UnsupportedQuestion(ValueError):
    """The question cannot be answered by the available query templates."""


def ask(question: str, database: str | Path) -> QueryAnswer:
    """Answer a supported all-time question using only fixed, read-only SQL."""
    normalized = " ".join(question.strip().rstrip("?").lower().replace("-", " ").split())
    kind = _QUESTION_TYPES.get(normalized)
    if kind is None:
        raise UnsupportedQuestion("Unsupported question. Try:\n" + "\n".join(SUPPORTED_QUESTIONS))
    uri = Path(database).expanduser().resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        if kind == "fields":
            rows = connection.execute("""
                SELECT field.value, COUNT(DISTINCT review.run_id) AS documents
                FROM review_results AS review,
                     json_each(review.result_json, '$.validation.results') AS assessment,
                     json_each(assessment.value, '$.fields') AS field
                WHERE json_extract(assessment.value, '$.status') = 'MISMATCH'
                GROUP BY field.value
                ORDER BY documents DESC, field.value ASC
            """).fetchall()
            counts = dict(rows)
            details = "; ".join(f"{name}: {count}" for name, count in rows)
            answer = (
                f"Documents with mismatches by field (all stored results): {details}."
                if rows else "No field mismatches were found in stored results."
            )
            return QueryAnswer(question=question, answer=answer, field_counts=counts)
        if kind == "mismatches":
            count = connection.execute(
                "SELECT COUNT(*) FROM review_results WHERE has_mismatches = 1",
            ).fetchone()[0]
            description = "had at least one mismatch"
        else:
            outcome = "AUTO_APPROVE" if kind == "approvals" else "HUMAN_REVIEW"
            count = connection.execute(
                "SELECT COUNT(*) FROM review_results WHERE outcome = ?", (outcome,),
            ).fetchone()[0]
            description = "were auto-approved" if kind == "approvals" else "required human review"
    return QueryAnswer(
        question=question,
        answer=f"Across all stored results, {count} document(s) {description}.",
        count=count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a supported question about stored reviews.")
    parser.add_argument("question", help="A quoted question; see README for supported questions")
    parser.add_argument("--database", required=True, help="Existing Nova SQLite database")
    args = parser.parse_args()
    try:
        result = ask(args.question, args.database)
    except UnsupportedQuestion as error:
        parser.exit(2, f"{error}\n")
    except sqlite3.Error:
        parser.exit(2, "Cannot query this database. Check its path and that result storage is initialized.\n")
    print(result.answer)


if __name__ == "__main__":
    main()
