import asyncio
from collections.abc import Iterable
from datetime import datetime, timezone
from difflib import SequenceMatcher
import re
from typing import Any

from loguru import logger
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from data.client import AsyncMongoDBConnection, get_async_mongodb, init_async_db
from data.entities import (
    SongVideoMatch,
    SourceSong,
    YouTubeChannel,
    YouTubeVideo,
)
from projects.config import DB_NAME
from projects.transform.data_quality import (
    QualityIssue,
    record_quality_events,
    record_quality_run,
    validate_source_document,
)

TITLE_SIMILARITY_THRESHOLD = 0.90


async def _upsert(connection: AsyncConnection, table: Any, values: dict) -> None:
    statement = insert(table).values(**values)
    update_values = {
        column.name: statement.excluded[column.name]
        for column in table.__table__.columns
        if not column.primary_key and column.name in values
    }
    await connection.execute(
        statement.on_conflict_do_update(
            index_elements=list(table.__table__.primary_key.columns), set_=update_values
        )
    )


def _search_results(document: dict) -> Iterable[tuple[str, dict]]:
    """Extract search results and their queries from raw YouTube documents."""
    youtube_search = document.get("youtube_search")
    if isinstance(youtube_search, dict):
        yield document.get("q", ""), youtube_search


def _normalized_title(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", value.casefold())).strip()


def _parse_published_at(value: str | None) -> datetime | None:
    """Convert YouTube RFC 3339 timestamps to timezone-aware datetimes."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _title_similarity(source_title: str, candidate_title: str) -> float:
    source_tokens = set(source_title.split())
    candidate_tokens = set(candidate_title.split())
    if not source_tokens or not candidate_tokens:
        return 0.0

    return SequenceMatcher(None, source_title, candidate_title).ratio()


def _select_videos(document: dict, videos: list[dict]) -> list[tuple[int, dict]]:
    """Filter videos by title similarity to avoid description-only matches."""
    indexed_videos = list(enumerate(videos))
    if len(indexed_videos) <= 1:
        return indexed_videos

    song_title = _normalized_title(str(document.get("SONG TITLE", "")))
    if not song_title:
        return indexed_videos

    scored_videos = [
        (
            _title_similarity(
                song_title, _normalized_title(str(video.get("snippet", {}).get("title", "")))
            ),
            position,
            video,
        )
        for position, video in indexed_videos
    ]
    similar_videos = [
        (position, video)
        for similarity, position, video in scored_videos
        if similarity >= TITLE_SIMILARITY_THRESHOLD
    ]
    if similar_videos:
        return similar_videos

    _, position, video = max(scored_videos, key=lambda item: item[0])
    return [(position, video)]


async def _ingest_document(connection: AsyncConnection, document: dict) -> tuple[int, int, int]:
    issues = validate_source_document(document)
    if issues:
        await record_quality_events(connection, "youtube_normalization", document, issues)
        logger.warning("Skipping invalid MongoDB YouTube record.")
        return 0, 1, 0

    if not list(_search_results(document)):
        warning = QualityIssue(
            "warning",
            "youtube_search_payload",
            "YouTube search response is missing or malformed.",
        )
        await record_quality_events(connection, "youtube_normalization", document, [warning])
        return 0, 0, 1

    source_code = int(document["CODE"])

    match_count = 0
    for query, payload in _search_results(document):
        items = payload.get("items", [])
        for position, video_item in _select_videos(document, items):
            video_id_obj = video_item.get("id", {})
            video_id = video_id_obj.get("videoId") if isinstance(video_id_obj, dict) else video_id_obj
            
            if not video_id:
                continue

            snippet = video_item.get("snippet", {})
            channel_id = snippet.get("channelId")
            channel_title = snippet.get("channelTitle", "")
            video_title = snippet.get("title", "")
            description = snippet.get("description", "")
            published_at = _parse_published_at(snippet.get("publishedAt"))

            if channel_id:
                await _upsert(
                    connection,
                    YouTubeChannel,
                    {
                        "channel_id": channel_id,
                        "title": channel_title,
                        "youtube_url": f"https://www.youtube.com/channel/{channel_id}",
                    },
                )

            await _upsert(
                connection,
                YouTubeVideo,
                {
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "source_code": source_code,
                    "title": video_title,
                    "description": description,
                    "published_at": published_at,
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                },
            )
            await _upsert(
                connection,
                SongVideoMatch,
                {
                    "source_code": source_code,
                    "video_id": video_id,
                    "query": query,
                    "result_position": position,
                },
            )
            match_count += 1

    return match_count, 0, 0


async def ingest_youtube_metadata(batch_size: int = 250) -> int:
    """Load documents from MongoDB raw_youtube into normalized PostgreSQL tables."""
    AsyncMongoDBConnection.connect()
    await AsyncMongoDBConnection.verify_connection()
    collection = get_async_mongodb(DB_NAME)["raw_youtube"]
    engine = init_async_db()
    started_at = datetime.now(timezone.utc)
    ingested_matches = 0
    records_read = 0
    records_loaded = 0
    records_rejected = 0
    records_warned = 0
    documents: list[dict] = []
    try:
        async for document in collection.find({}):
            documents.append(document)
            if len(documents) == batch_size:
                async with engine.begin() as connection:
                    for item in documents:
                        match_count, rejected, warned = await _ingest_document(connection, item)
                        ingested_matches += match_count
                        records_rejected += rejected
                        records_warned += warned
                        records_read += 1
                        records_loaded += int(not rejected and not warned)
                documents.clear()
        if documents:
            async with engine.begin() as connection:
                for item in documents:
                    match_count, rejected, warned = await _ingest_document(connection, item)
                    ingested_matches += match_count
                    records_rejected += rejected
                    records_warned += warned
                    records_read += 1
                    records_loaded += int(not rejected and not warned)
        async with engine.begin() as connection:
            await record_quality_run(
                connection,
                "youtube_normalization",
                started_at,
                records_read,
                records_loaded,
                records_rejected,
                records_warned,
            )
    finally:
        await engine.dispose()
        AsyncMongoDBConnection.close()

    logger.info(f"Ingested {ingested_matches} YouTube video matches into PostgreSQL.")
    return ingested_matches


if __name__ == "__main__":
    asyncio.run(ingest_youtube_metadata())