"""Tracing hooks.

This file intentionally avoids binding to one provider. Students can plug in LangSmith,
Langfuse, OpenTelemetry, or simple JSON traces.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Minimal span context used by the skeleton.

    The returned span dictionary is intentionally provider-agnostic so the workflow can
    record traces locally or enrich them with LangSmith/Langfuse/OpenTelemetry later.
    """

    started = perf_counter()
    span: dict[str, Any] = {"name": name, "attributes": attributes or {}, "duration_seconds": None, "status": "ok", "error": None}
    try:
        yield span
    except Exception as exc:  # pragma: no cover - bookkeeping path
        span["status"] = "error"
        span["error"] = str(exc)
        raise
    finally:
        span["duration_seconds"] = perf_counter() - started


def render_json_trace(payload: Any) -> str:
    """Render trace payload as simple JSON."""

    return json.dumps(payload, indent=2, ensure_ascii=False)
