"""FastAPI application: routes of API contract v1 (ARCHITECTURE.md §7).

Route signatures and response models here are part of the contract and are
exported to packages/contract/openapi.json by `export_openapi.py`.
"""

from __future__ import annotations

from fastapi import FastAPI

from . import __version__
from .schemas import (AnalyzeRequest, AnalyzeResponse, ErrorResponse,
                      HealthResponse, RulesResponse)

ERRORS = {
    400: {"model": ErrorResponse, "description": "Malformed request"},
    413: {"model": ErrorResponse, "description": "Document too large"},
    422: {"model": ErrorResponse, "description": "Request failed validation"},
    429: {"model": ErrorResponse, "description": "Rate limited"},
    500: {"model": ErrorResponse, "description": "Engine error (no document text in the body)"},
}

app = FastAPI(
    title="Researchly Engine API",
    version=__version__,
    summary="Explainable, section-aware feedback on research writing. "
            "Advises; never drafts.",
    description="Document text is processed in memory for the duration of "
                "a request and is never stored, logged or used for training "
                "(ARCHITECTURE.md ADR-02).",
)


@app.post("/v1/analyze", response_model=AnalyzeResponse, responses=ERRORS,
          operation_id="analyze", tags=["analysis"])
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Check one document and return typed, explained suggestions."""
    raise NotImplementedError


@app.get("/v1/health", response_model=HealthResponse, operation_id="health",
         tags=["meta"])
def health() -> HealthResponse:
    """Per-tier status. A degraded tier is reported, never hidden."""
    raise NotImplementedError


@app.get("/v1/rules", response_model=RulesResponse, operation_id="listRules",
         tags=["meta"])
def rules() -> RulesResponse:
    """The rule registry with why/source — powers Explain and settings UIs."""
    raise NotImplementedError
