"""Overleaf `.zip` adapter. Placeholder until the S2 adapter lands."""

from __future__ import annotations

from . import IngestError


def load_zip(filename: str, data: bytes):
    raise IngestError("unsupported_file", ".zip projects are not supported yet.")
