"""Langfuse (OpenTelemetry) + PydanticAI instrumentation.

``Agent.instrument_all()`` once at startup and the Langfuse v3+ SDK does the
rest. Without keys in .env everything is a silent no-op: the benchmark runs
the same way.

Langfuse is for investigating errors. The benchmark's numbers come from
``results.jsonl``, never from Langfuse.
"""

import logging
import os
from contextlib import contextmanager

from football_graphrag.config import Settings

logger = logging.getLogger(__name__)


def setup_observability(settings: Settings) -> bool:
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info("Langfuse not configured; instrumentation off")
        return False
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

    from langfuse import get_client
    from pydantic_ai import Agent

    get_client()  # starts the Langfuse OTel exporter
    Agent.instrument_all()
    logger.info("Langfuse + PydanticAI instrumented")
    return True


@contextmanager
def span(name: str, *, active: bool, **metadata):
    """Group one unit of work (one question x arm x repeat) under a named span,
    so each trace is named after what was being measured. No-op when inactive."""
    if not active:
        yield
        return
    from langfuse import get_client

    with get_client().start_as_current_observation(name=name, as_type="span", metadata=metadata):
        yield


def current_trace_url(active: bool) -> str | None:
    """Langfuse URL of the trace being recorded, or None when inactive.

    Call inside ``span(...)``. The URL opens the trace in the Langfuse UI (it
    needs a login to the project).
    """
    if not active:
        return None
    from langfuse import get_client

    client = get_client()
    trace_id = client.get_current_trace_id()
    return client.get_trace_url(trace_id=trace_id) if trace_id else None


def flush(active: bool) -> None:
    """Send buffered spans. Short-lived scripts exit before the batch exporter fires."""
    if not active:
        return
    from langfuse import get_client

    get_client().flush()
