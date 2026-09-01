import asyncio
from collections.abc import Iterable
from difflib import SequenceMatcher
import math
import re
from typing import Any

from loguru import logger
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from data.client import AsyncMongoDBConnection, get_async_mongodb, init_async_db
from data.entities import (
    SongTrackMatch,
    SourceSong,
    SpotifyAlbum,
    SpotifyArtist,
    SpotifyTrack,
    TrackArtist,
)
from projects.config import DB_NAME

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


def _search_payloads(document: dict) -> Iterable[tuple[str, dict]]:
    search = document.get("spotify_search")
    if isinstance(search, dict):
        yield document.get("q", ""), search
    elif isinstance(search, list):
        for entry in search:
            if isinstance(entry, dict) and isinstance(entry.get("result"), dict):
                yield entry.get("query", document.get("q", "")), entry["result"]


def _normalized_title(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", value.casefold())).strip()


def _title_similarity(source_title: str, candidate_title: str) -> float:
    source_tokens = set(source_title.split())
    candidate_tokens = set(candidate_title.split())
    if not source_tokens or not source_tokens <= candidate_tokens:
        return 0.0

    return SequenceMatcher(None, source_title, candidate_title).ratio()


def _null_if_nan(value: Any) -> Any:
    return None if isinstance(value, float) and math.isnan(value) else value


def _select_tracks(document: dict, tracks: list[dict]) -> list[tuple[int, dict]]:
    """Limit artistless searches to strong title matches, with one fallback."""
    indexed_tracks = list(enumerate(tracks))
    original_artist = _null_if_nan(document.get("ORIGINAL ARTIST"))
    if len(indexed_tracks) <= 1 or original_artist:
        return indexed_tracks

    song_title = _normalized_title(str(document["SONG TITLE"]))
    scored_tracks = [
        (
            _title_similarity(
                song_title, _normalized_title(str(track.get("name", "")))
            ),
            position,
            track,
        )
        for position, track in indexed_tracks
    ]
    similar_tracks = [
        (position, track)
        for similarity, position, track in scored_tracks
        if similarity >= TITLE_SIMILARITY_THRESHOLD
    ]
    if similar_tracks:
        return similar_tracks

    _, position, track = max(scored_tracks, key=lambda item: item[0])
    return [(position, track)]


async def _ingest_document(connection: AsyncConnection, document: dict) -> int:
    if document.get("CODE") is None or not document.get("SONG TITLE"):
        logger.warning("Skipping MongoDB record missing CODE or SONG TITLE.")
        return 0

    source_code = int(document["CODE"])
    original_artist = _null_if_nan(document.get("ORIGINAL ARTIST"))
    await _upsert(
        connection,
        SourceSong,
        {
            "code": source_code,
            "original_artist": original_artist,
            "song_title": document["SONG TITLE"],
            "search_query": document.get("q"),
            "source_created_at": document.get("created_at"),
        },
    )

    match_count = 0
    for query, payload in _search_payloads(document):
        tracks = payload.get("tracks", {}).get("items", [])
        for position, track in _select_tracks(document, tracks):
            track_id = track.get("id")
            album = track.get("album") or {}
            album_id = album.get("id")
            if not track_id or not album_id:
                continue

            for artist in [*album.get("artists", []), *track.get("artists", [])]:
                artist_id = artist.get("id")
                if artist_id:
                    await _upsert(
                        connection,
                        SpotifyArtist,
                        {
                            "spotify_id": artist_id,
                            "name": artist.get("name", ""),
                            "spotify_url": artist.get("external_urls", {}).get(
                                "spotify"
                            ),
                        },
                    )

            await _upsert(
                connection,
                SpotifyAlbum,
                {
                    "spotify_id": album_id,
                    "name": album.get("name", ""),
                    "album_type": album.get("album_type"),
                    "release_date": album.get("release_date"),
                    "release_date_precision": album.get("release_date_precision"),
                    "total_tracks": album.get("total_tracks"),
                    "spotify_url": album.get("external_urls", {}).get("spotify"),
                },
            )
            await _upsert(
                connection,
                SpotifyTrack,
                {
                    "spotify_id": track_id,
                    "source_code": source_code,
                    "album_spotify_id": album_id,
                    "name": track.get("name", ""),
                    "duration_ms": track.get("duration_ms"),
                    "explicit": track.get("explicit"),
                    "isrc": track.get("external_ids", {}).get("isrc"),
                    "disc_number": track.get("disc_number"),
                    "track_number": track.get("track_number"),
                    "spotify_url": track.get("external_urls", {}).get("spotify"),
                },
            )
            for artist_position, artist in enumerate(track.get("artists", [])):
                if artist.get("id"):
                    await _upsert(
                        connection,
                        TrackArtist,
                        {
                            "track_spotify_id": track_id,
                            "artist_spotify_id": artist["id"],
                            "artist_position": artist_position,
                        },
                    )
            await _upsert(
                connection,
                SongTrackMatch,
                {
                    "source_code": source_code,
                    "track_spotify_id": track_id,
                    "query": query,
                    "result_position": position,
                },
            )
            match_count += 1
    return match_count


async def ingest_spotify_metadata(batch_size: int = 250) -> int:
    """Load documents from MongoDB raw_spotify into normalized PostgreSQL tables."""
    AsyncMongoDBConnection.connect()
    await AsyncMongoDBConnection.verify_connection()
    collection = get_async_mongodb(DB_NAME)["raw_spotify"]
    engine = init_async_db()
    ingested_matches = 0
    documents: list[dict] = []
    try:
        async for document in collection.find({}):
            documents.append(document)
            if len(documents) == batch_size:
                async with engine.begin() as connection:
                    for item in documents:
                        ingested_matches += await _ingest_document(connection, item)
                documents.clear()
        if documents:
            async with engine.begin() as connection:
                for item in documents:
                    ingested_matches += await _ingest_document(connection, item)
    finally:
        await engine.dispose()
        AsyncMongoDBConnection.close()

    logger.info(f"Ingested {ingested_matches} Spotify track matches into PostgreSQL.")
    return ingested_matches


if __name__ == "__main__":
    asyncio.run(ingest_spotify_metadata())
