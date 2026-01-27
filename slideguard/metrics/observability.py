from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from langfuse import Langfuse


logger = logging.getLogger(__name__)


@contextmanager
def metrics_trace(
    run_id: str,
    operation: str,
    metadata: Optional[dict[str, Any]] = None,
    langfuse_client: Optional[Langfuse] = None,
) -> Iterator[Optional[Any]]:
    if not langfuse_client:
        yield None
        return
    trace = None
    try:
        trace = langfuse_client.trace(
            name=operation,
            input={"run_id": run_id},
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.warning("Failed to initialize Langfuse trace: %s", exc, exc_info=True)
    try:
        yield trace
    finally:
        if trace:
            try:
                trace.end()
            except Exception as exc:
                logger.warning("Failed to end Langfuse trace: %s", exc, exc_info=True)
        if langfuse_client:
            try:
                langfuse_client.flush()
            except Exception as exc:
                logger.warning("Failed to flush Langfuse client: %s", exc, exc_info=True)







