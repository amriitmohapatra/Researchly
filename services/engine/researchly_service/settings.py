"""Service settings, from environment variables only (12-factor; Cloud Run).

These are OPERATOR settings for the deployment. They are not user settings —
those come per request (S1) and from accounts (S2) — and nothing here is
read from a file.

| Variable                         | Default          | Meaning |
|----------------------------------|------------------|---------|
| RESEARCHLY_ENV                   | production       | `development` enables localhost CORS |
| RESEARCHLY_ALLOWED_ORIGINS       | (none / dev: localhost:3000) | comma-separated CORS origins |
| RESEARCHLY_LT_URL                | (unset)          | LanguageTool server; unset = local JVM |
| RESEARCHLY_GRAMMAR               | on               | `off`: the deployment does not run grammar |
| RESEARCHLY_MAX_BODY_BYTES        | 8388608 (8 MiB)  | request bodies above this get 413 unread |
| RESEARCHLY_RATE_LIMIT_PER_MIN    | 30               | per client IP, per instance; 0 disables |
| RESEARCHLY_TRUSTED_PROXY_HOPS    | 0                | X-Forwarded-For entries appended by trusted proxies (Cloud Run: 1) |
| RESEARCHLY_WARMUP                | on               | warm spaCy/rules/LanguageTool before serving |
| PORT                             | 8080             | listen port (Cloud Run convention) |
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

DEV_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def _flag(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "off", "false", "no")


def _int(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name) or "").strip() or default)
    except ValueError:
        return default


def _origins(env: str) -> List[str]:
    raw = os.environ.get("RESEARCHLY_ALLOWED_ORIGINS")
    if raw is None or not raw.strip():
        return list(DEV_ORIGINS) if env == "development" else []
    out = []
    for o in raw.split(","):
        o = o.strip().rstrip("/")
        # A wildcard would let any website drive the engine from a visitor's
        # browser. Fail closed: name the origins.
        if o and o != "*":
            out.append(o)
    return out


# The body cap must admit every document the contract accepts: up to
# MAX_CONTENT_CHARS code points at up to 4 UTF-8 bytes each (emoji, maths
# letters such as U+1D445), plus JSON escaping of quotes/newlines and the
# envelope. 4 MiB rejected a valid 1M-character document before the content
# check could give its clearer message; 8 MiB leaves room. Pinned by
# tests/test_errors.py::test_body_cap_admits_any_valid_document.
DEFAULT_MAX_BODY_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    env: str = "production"
    allowed_origins: List[str] = field(default_factory=list)
    grammar_enabled: bool = True
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    rate_limit_per_min: int = 30
    trusted_proxy_hops: int = 0
    warmup: bool = True


def load() -> Settings:
    env = (os.environ.get("RESEARCHLY_ENV") or "production").strip().lower()
    return Settings(
        env=env,
        allowed_origins=_origins(env),
        grammar_enabled=_flag("RESEARCHLY_GRAMMAR", True),
        max_body_bytes=max(1024, _int("RESEARCHLY_MAX_BODY_BYTES",
                                      DEFAULT_MAX_BODY_BYTES)),
        rate_limit_per_min=max(0, _int("RESEARCHLY_RATE_LIMIT_PER_MIN", 30)),
        trusted_proxy_hops=max(0, _int("RESEARCHLY_TRUSTED_PROXY_HOPS", 0)),
        warmup=_flag("RESEARCHLY_WARMUP", True),
    )
