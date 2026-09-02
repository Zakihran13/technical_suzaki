import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from data.entities import DataQualityEvent, DataQualityRun


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    rule_name: str
    message: str


def validate_source_document(document: dict[str, Any]) -> list[QualityIssue]:
    """Return errors that prevent a raw record from entering normalized tables."""
    issues = []
    code = document.get("CODE")
    if code is None or isinstance(code, bool):
        issues.append(QualityIssue("error", "required_code", "CODE is required."))
    else:
        try:
            int(code)
        except (TypeError, ValueError):
            issues.append(
                QualityIssue("error", "valid_code", "CODE must be an integer.")
            )

    title = document.get("SONG TITLE")
    if not isinstance(title, str) or not title.strip():
        issues.append(
            QualityIssue("error", "required_song_title", "SONG TITLE is required.")
        )
    return issues


def serializable_record(document: dict[str, Any]) -> dict[str, Any]:
    """Convert MongoDB-specific values into a JSONB-safe audit payload."""
    return json.loads(json.dumps(document, default=str))


async def record_quality_events(
    connection: AsyncConnection,
    pipeline_name: str,
    document: dict[str, Any],
    issues: list[QualityIssue],
) -> None:
    if not issues:
        return

    source_code = document.get("CODE")
    try:
        source_code = int(source_code) if source_code is not None else None
    except (TypeError, ValueError):
        source_code = None

    raw_record = serializable_record(document)
    await connection.execute(
        insert(DataQualityEvent),
        [
            {
                "pipeline_name": pipeline_name,
                "source_code": source_code,
                "severity": issue.severity,
                "rule_name": issue.rule_name,
                "message": issue.message,
                "raw_record": raw_record,
                "detected_at": datetime.now(timezone.utc),
            }
            for issue in issues
        ],
    )


async def record_quality_run(
    connection: AsyncConnection,
    pipeline_name: str,
    started_at: datetime,
    records_read: int,
    records_loaded: int,
    records_rejected: int,
    records_warned: int,
) -> None:
    await connection.execute(
        insert(DataQualityRun).values(
            pipeline_name=pipeline_name,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            records_read=records_read,
            records_loaded=records_loaded,
            records_rejected=records_rejected,
            records_warned=records_warned,
        )
    )