from datetime import datetime, timezone

from projects.transform.yotube_ingestion import _parse_published_at


def test_parse_published_at_converts_youtube_utc_timestamp():
    assert _parse_published_at("2025-09-23T17:53:56Z") == datetime(
        2025, 9, 23, 17, 53, 56, tzinfo=timezone.utc
    )


def test_parse_published_at_returns_none_when_missing():
    assert _parse_published_at(None) is None