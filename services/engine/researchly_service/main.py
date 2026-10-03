"""FastAPI application: routes of API contract v1 (ARCHITECTURE.md §7).

Route signatures and response models here are part of the contract and are
exported to packages/contract/openapi.json by `export_openapi.py`.

Layers, outermost first:

    CORSMiddleware            browser origins (RESEARCHLY_ALLOWED_ORIGINS)
    RequestContextMiddleware  request id · rate limit · 413 before parsing ·
                              500 error net · one JSON access-log line
    FastAPI                   422/400/404/405 → ErrorResponse (errors.py)
    routes                    → engine_adapter → researchly.api.analyze()

Run it with `python -m researchly_service` (see README.md).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import _core  # noqa: F401  (import path + tenant isolation first)
from . import __version__, engine_adapter, errors, logging_setup
from . import settings as settings_mod
from .middleware import RateLimiter, RequestContextMiddleware
from researchly import rules_grammar  # noqa: E402  (after _core)
from .schemas import (AnalyzeRequest, AnalyzeResponse, ErrorResponse,
                      HealthResponse, RulesResponse)

ERRORS = {
    400: {"model": ErrorResponse, "description": "Malformed request"},
    413: {"model": ErrorResponse, "description": "Document too large"},
    422: {"model": ErrorResponse, "description": "Request failed validation"},
    429: {"model": ErrorResponse, "description": "Rate limited"},
    500: {"model": ErrorResponse, "description": "Engine error (no document text in the body)"},
}

log = logging_setup.get("researchly.service")

router = APIRouter()


def _settings(request: Request) -> settings_mod.Settings:
    return request.app.state.settings


@router.post("/v1/analyze", response_model=AnalyzeResponse, responses=ERRORS,
             operation_id="analyze", tags=["analysis"])
def analyze(req: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    """Check one document and return typed, explained suggestions."""
    st = request.state
    # Sizes and counts only: these feed the access-log line.
    st.content_chars = len(req.content)
    st.format = req.format.value
    resp = engine_adapter.run_analysis(
        req.content, req.format.value, req.options,
        grammar_enabled=_settings(request).grammar_enabled)
    st.suggestions = len(resp.suggestions)
    st.counts = dict(resp.counts)
    st.hidden_preferences = resp.hidden_preferences
    return resp


@router.get("/v1/health", response_model=HealthResponse, operation_id="health",
            tags=["meta"])
def health(request: Request) -> HealthResponse:
    """Per-tier status. A degraded tier is reported, never hidden."""
    tiers = engine_adapter.health_tiers(_settings(request).grammar_enabled)
    return HealthResponse(
        status="degraded" if engine_adapter.is_degraded(tiers) else "ok",
        tiers=tiers, engine=engine_adapter.engine_info())


@router.get("/v1/rules", response_model=RulesResponse, operation_id="listRules",
            tags=["meta"])
def rules() -> RulesResponse:
    """The rule registry with why/source — powers Explain and settings UIs."""
    return RulesResponse(rules=engine_adapter.rule_infos())


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging_setup.setup()
    _core.isolate()
    s: settings_mod.Settings = app.state.settings
    log.info("starting", extra={
        "event": "startup", "service_version": __version__,
        "core_version": engine_adapter.researchly.__version__,
        "allowed_origins": s.allowed_origins,
        "rate_limit_per_min": s.rate_limit_per_min,
        "lt_url_set": bool(rules_grammar.remote_url()),
        "grammar": s.grammar_enabled})
    if s.warmup:
        # Before the port opens, so Cloud Run's startup probe — and the
        # first user — only ever see a warm engine.
        info = engine_adapter.warm_up(s.grammar_enabled)
        log.info("warm", extra=dict(info, event="warmup"))
    yield


def create_app(settings: Optional[settings_mod.Settings] = None) -> FastAPI:
    s = settings or settings_mod.load()
    app = FastAPI(
        title="Researchly Engine API",
        version=__version__,
        summary="Explainable, section-aware feedback on research writing. "
                "Advises; never drafts.",
        description="Document text is processed in memory for the duration of "
                    "a request and is never stored, logged or used for training "
                    "(ARCHITECTURE.md ADR-02).",
        lifespan=lifespan,
    )
    app.state.settings = s
    app.state.limiter = RateLimiter(s.rate_limit_per_min)
    app.include_router(router)
    app.add_exception_handler(RequestValidationError,
                              errors.on_validation_error)
    app.add_exception_handler(StarletteHTTPException, errors.on_http_error)
    # add_middleware wraps: the LAST one added is the outermost. CORS goes
    # outside the request middleware so 413/429/500 replies still carry CORS
    # headers and the browser can read the error body.
    app.add_middleware(RequestContextMiddleware, settings=s,
                       limiter=app.state.limiter)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID", "Retry-After"],
        allow_credentials=False,
        max_age=600,
    )
    return app


app = create_app()
