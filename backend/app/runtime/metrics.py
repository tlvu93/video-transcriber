from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


logger = logging.getLogger("backend.runtime.metrics")


def metrics_enabled() -> bool:
    return os.environ.get("METRICS_RECORDING_ENABLED", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_default_metrics_lookback_hours() -> int:
    return int(os.environ.get("METRICS_DEFAULT_LOOKBACK_HOURS", "168"))


def normalize_metric_labels(labels: Optional[Dict[str, Any]]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key, value in (labels or {}).items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        normalized[normalized_key] = "" if value is None else str(value)
    return normalized


def record_metric_event(
    metric_name: str,
    value: float = 1.0,
    *,
    source: str,
    labels: Optional[Dict[str, Any]] = None,
    recorded_at: Optional[datetime] = None,
) -> None:
    if not metrics_enabled():
        return

    try:
        from backend.app.persistence.database import SessionLocal
        from backend.app.persistence.models import OperationalMetricEvent

        db = SessionLocal()
        try:
            db.add(
                OperationalMetricEvent(
                    metric_name=metric_name,
                    metric_source=source,
                    metric_value=float(value),
                    labels=normalize_metric_labels(labels),
                    recorded_at=recorded_at or datetime.utcnow(),
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception as error:
        logger.warning("Failed to record metric event %s: %s", metric_name, error)


def summarize_metric_events(*, lookback_hours: Optional[int] = None) -> Dict[str, Any]:
    from backend.app.persistence.database import SessionLocal
    from backend.app.persistence.models import OperationalMetricEvent

    effective_lookback_hours = lookback_hours or get_default_metrics_lookback_hours()
    cutoff = datetime.utcnow() - timedelta(hours=effective_lookback_hours)

    db = SessionLocal()
    try:
        events = (
            db.query(OperationalMetricEvent)
            .filter(OperationalMetricEvent.recorded_at >= cutoff)
            .order_by(OperationalMetricEvent.recorded_at.desc())
            .all()
        )
    finally:
        db.close()

    metric_summaries: Dict[str, Dict[str, Any]] = {}
    source_totals: Dict[str, int] = defaultdict(int)

    for event in events:
        source_totals[event.metric_source] += 1
        summary = metric_summaries.setdefault(
            event.metric_name,
            {
                "count": 0,
                "sum": 0.0,
                "min": None,
                "max": None,
                "latest_value": None,
                "latest_recorded_at": None,
                "sources": defaultdict(int),
                "latest_labels": None,
            },
        )
        summary["count"] += 1
        summary["sum"] += float(event.metric_value)
        summary["min"] = (
            float(event.metric_value)
            if summary["min"] is None
            else min(summary["min"], float(event.metric_value))
        )
        summary["max"] = (
            float(event.metric_value)
            if summary["max"] is None
            else max(summary["max"], float(event.metric_value))
        )
        summary["latest_value"] = float(event.metric_value)
        summary["latest_recorded_at"] = event.recorded_at.isoformat()
        summary["latest_labels"] = event.labels or {}
        summary["sources"][event.metric_source] += 1

    for metric_name, summary in metric_summaries.items():
        summary["average"] = round(summary["sum"] / summary["count"], 4) if summary["count"] else 0.0
        summary["sum"] = round(summary["sum"], 4)
        summary["sources"] = dict(summary["sources"])
        metric_summaries[metric_name] = summary

    recent_events = [
        {
            "metric_name": event.metric_name,
            "metric_source": event.metric_source,
            "metric_value": float(event.metric_value),
            "labels": event.labels or {},
            "recorded_at": event.recorded_at.isoformat(),
        }
        for event in events[:25]
    ]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "lookback_hours": effective_lookback_hours,
        "event_count": len(events),
        "metrics": metric_summaries,
        "sources": dict(source_totals),
        "recent_events": recent_events,
    }


def purge_metric_events(*, older_than_hours: int) -> int:
    from backend.app.persistence.database import SessionLocal
    from backend.app.persistence.models import OperationalMetricEvent

    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)

    db = SessionLocal()
    try:
        deleted_count = (
            db.query(OperationalMetricEvent)
            .filter(OperationalMetricEvent.recorded_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        return int(deleted_count or 0)
    finally:
        db.close()
