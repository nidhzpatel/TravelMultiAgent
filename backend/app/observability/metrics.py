"""CloudWatch Embedded Metric Format output without traveler content."""

from datetime import datetime, timezone
import json
import logging
from typing import Mapping

logger = logging.getLogger("voyagemind.metrics")


def emit_metrics(name: str, metrics: Mapping[str, float], dimensions: Mapping[str, str] | None = None) -> None:
    dimensions = dict(dimensions or {})
    payload: dict[str, object] = {
        "_aws": {
            "Timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "VoyageMind",
                "Dimensions": [list(dimensions)],
                "Metrics": [{"Name": metric} for metric in metrics],
            }],
        },
        "event": name,
        **dimensions,
        **metrics,
    }
    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))
