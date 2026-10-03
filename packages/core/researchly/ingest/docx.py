"""`.docx` adapter (OOXML). Placeholder until the S2 adapter lands."""

from __future__ import annotations

from . import IngestError


def load_docx(filename: str, data: bytes):
    raise IngestError("unsupported_file", ".docx reading is not available yet.")
