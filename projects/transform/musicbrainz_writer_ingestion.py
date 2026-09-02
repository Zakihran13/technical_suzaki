import asyncio
from functools import partial
import os
from typing import Any

import aiometer
from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from data.client import init_async_db
from data.entities import MusicWriter, SpotifyTrack, SpotifyTrackWriter
from projects.client.musicbrainz import MusicBrainzClient
from projects.utils.rate_limiter import AsyncRateLimiter

load_dotenv()

MUSICBRAINZ_MAX_REQUESTS_PER_SECOND = 1


async def _upsert(connection: AsyncConnection, table: Any, values: dict) -> None:
    statement = insert(table).values(**values)
    update_values = {
        column.name: statement.excluded[column.name]
        for column in table.__table__.columns
        if not column.primary_key and column.name in values
    }
    if update_values:
        statement = statement.on_conflict_do_update(
            index_elements=list(table.__table__.primary_key.columns), set_=update_values
        )
    else:
        statement = statement.on_conflict_do_nothing(
            index_elements=list(table.__table__.primary_key.columns)
        )
    await connection.execute(statement)


def _writer_credits(work: dict) -> list[dict]:
    """Extract songwriter, composer, and lyricist artist relations from a work."""
    credit_types = {"writer", "composer", "lyricist"}
    credits = []
    for relation in work.get("relations", []):
        artist = relation.get("artist") or {}
        role = relation.get("type")
        if role in credit_types and artist.get("id") and artist.get("name"):
            credits.append({"id": artist["id"], "name": artist["name"], "role": role})
    return credits


async def _credits_for_isrc(client: MusicBrainzClient, isrc: str) -> list[dict]:
    recordings = await client.recordings_by_isrc(isrc)
    work_ids = {
        relation.get("work", {}).get("id")
        for recording_summary in recordings
        for relation in (await client.recording(recording_summary["id"])).get(
            "relations", []
        )
        if relation.get("work", {}).get("id")
    }
    credits: dict[tuple[str, str], dict] = {}
    for work_id in work_ids:
        for credit in _writer_credits(await client.work(work_id)):
            credits[(credit["id"], credit["role"])] = credit
    return list(credits.values())


async def enrich_spotify_track_writers() -> int:
    """Resolve MusicBrainz work credits for every Spotify track with an ISRC."""
    user_agent = os.getenv("MUSICBRAINZ_USER_AGENT")
    if not user_agent:
        raise ValueError("MUSICBRAINZ_USER_AGENT must be set before writer enrichment")

    engine = init_async_db()
    enriched_tracks = 0
    try:
        async with engine.begin() as connection:
            result = await connection.execute(
                select(SpotifyTrack.spotify_id, SpotifyTrack.isrc).where(
                    SpotifyTrack.isrc.is_not(None)
                )
            )
            tracks = [
                (spotify_id, isrc)
                for spotify_id, isrc in result.tuples().all()
                if isinstance(isrc, str) and isrc
            ]

            rate_limiter = AsyncRateLimiter(max_rate=MUSICBRAINZ_MAX_REQUESTS_PER_SECOND)
            async with MusicBrainzClient(user_agent, rate_limiter) as client:
                credits_by_track = await aiometer.run_all(
                    [
                        partial(_credits_for_isrc, client, isrc)
                        for _, isrc in tracks
                    ],
                    max_at_once=1,
                )

            for (spotify_id, _), credits in zip(tracks, credits_by_track):
                for credit in credits:
                    await _upsert(
                        connection,
                        MusicWriter,
                        {"musicbrainz_id": credit["id"], "name": credit["name"]},
                    )
                    await _upsert(
                        connection,
                        SpotifyTrackWriter,
                        {
                            "track_spotify_id": spotify_id,
                            "musicbrainz_writer_id": credit["id"],
                            "credit_role": credit["role"],
                        },
                    )
                if credits:
                    enriched_tracks += 1
    finally:
        await engine.dispose()

    logger.info(f"Enriched {enriched_tracks} Spotify tracks with MusicBrainz writers.")
    return enriched_tracks


if __name__ == "__main__":
    asyncio.run(enrich_spotify_track_writers())