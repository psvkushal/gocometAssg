"""Bounded single-file input for the future vision Extractor."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class DocumentInput:
    filename: str
    media_type: Literal["application/pdf", "image/png", "image/jpeg"]
    content: bytes = field(repr=False)


def load_document(path: str | Path, *, max_bytes: int) -> DocumentInput:
    """Read a supported file with a byte limit; header checks do not prove readability."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    source = Path(path).expanduser()
    suffix = source.suffix.lower()
    if suffix not in (".pdf", ".png", ".jpg", ".jpeg"):
        raise ValueError("Supported document formats are PDF, PNG, and JPEG")
    with source.open("rb") as document:
        content = document.read(max_bytes + 1)
    if not content:
        raise ValueError("Document is empty")
    if len(content) > max_bytes:
        raise ValueError(f"Document exceeds the {max_bytes}-byte limit")

    if suffix == ".pdf" and content.startswith(b"%PDF-"):
        media_type = "application/pdf"
    elif suffix == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif suffix in (".jpg", ".jpeg") and content.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    else:
        raise ValueError("Document header does not match its file extension")
    return DocumentInput(filename=source.name, media_type=media_type, content=content)
