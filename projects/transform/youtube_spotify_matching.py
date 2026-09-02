import asyncio
from typing import Any

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from data.client import init_async_db
from data.entities import (
    SongPlatformCatalog,
    SongTrackMatch,
    SongVideoMatch,
    SourceSong,
    SpotifyAlbum,
    SpotifyArtist,
    SpotifyTrack,
    TrackArtist,
    YouTubeSpotifyMatch,
    YouTubeVideo,
)

load_dotenv()

async def _upsert(connection: AsyncConnection, table: Any, values: dict) -> None:
    statement = insert(table).values(**values)
    update_values = {
        column.name: statement.excluded[column.name]
        for column in table.__table__.columns
        if not column.primary_key and column.name in values
    }
    conflict_columns = list(table.__table__.primary_key.columns)
    if update_values:
        statement = statement.on_conflict_do_update(
            index_elements=conflict_columns, set_=update_values
        )
    else:
        statement = statement.on_conflict_do_nothing(index_elements=conflict_columns)
    await connection.execute(statement)


async def create_youtube_spotify_matches() -> int:
    """Join every Spotify track and YouTube video sharing a source code."""
    statement = (
        select(
            SongTrackMatch.source_code,
            SpotifyTrack.spotify_id,
            YouTubeVideo.video_id,
        )
        .join(SpotifyTrack, SpotifyTrack.spotify_id == SongTrackMatch.track_spotify_id)
        .join(SongVideoMatch, SongVideoMatch.source_code == SongTrackMatch.source_code)
        .join(YouTubeVideo, YouTubeVideo.video_id == SongVideoMatch.video_id)
    )
    engine = init_async_db()
    matched_count = 0
    try:
        async with engine.begin() as connection:
            result = await connection.execute(statement)
            for source_code, spotify_id, video_id in result.tuples():
                await _upsert(
                    connection,
                    YouTubeSpotifyMatch,
                    {
                        "source_code": source_code,
                        "track_spotify_id": spotify_id,
                        "video_id": video_id,
                    },
                )
                matched_count += 1
    finally:
        await engine.dispose()

    logger.info(f"Created {matched_count} YouTube-Spotify matches.")
    return matched_count


async def build_song_platform_catalog() -> int:
    """Build one Spotify-recording row per song with independent platform counts."""
    youtube_video_count = (
        select(func.count(func.distinct(SongVideoMatch.video_id)))
        .where(SongVideoMatch.source_code == SourceSong.code)
        .correlate(SourceSong)
        .scalar_subquery()
    )
    spotify_isrc_count = (
        select(func.count(func.distinct(SpotifyTrack.isrc)))
        .select_from(SongTrackMatch)
        .join(SpotifyTrack, SpotifyTrack.spotify_id == SongTrackMatch.track_spotify_id)
        .where(SongTrackMatch.source_code == SourceSong.code)
        .where(SpotifyTrack.isrc.is_not(None))
        .correlate(SourceSong)
        .scalar_subquery()
    )
    statement = (
        select(
            SourceSong.code,
            SourceSong.song_title,
            SourceSong.song_writers,
            SpotifyTrack.spotify_id,
            SpotifyTrack.isrc,
            SpotifyTrack.name,
            SpotifyArtist.name,
            SpotifyAlbum.label,
            youtube_video_count.label("youtube_video_count"),
            spotify_isrc_count.label("spotify_isrc_count"),
        )
        .join(SongTrackMatch, SongTrackMatch.source_code == SourceSong.code)
        .join(SpotifyTrack, SpotifyTrack.spotify_id == SongTrackMatch.track_spotify_id)
        .outerjoin(
            TrackArtist,
            (TrackArtist.track_spotify_id == SpotifyTrack.spotify_id)
            & (TrackArtist.artist_position == 0),
        )
        .outerjoin(SpotifyArtist, SpotifyArtist.spotify_id == TrackArtist.artist_spotify_id)
        .outerjoin(SpotifyAlbum, SpotifyAlbum.spotify_id == SpotifyTrack.album_spotify_id)
    )

    engine = init_async_db()
    record_count = 0
    try:
        async with engine.begin() as connection:
            result = await connection.execute(statement)
            for (
                source_code,
                song_title,
                song_writers,
                spotify_id,
                isrc,
                recording_title,
                artist_name,
                label,
                video_count,
                isrc_count,
            ) in result.tuples():
                await _upsert(
                    connection,
                    SongPlatformCatalog,
                    {
                        "source_code": source_code,
                        "track_spotify_id": spotify_id,
                        "song_title": song_title,
                        "song_writers": song_writers,
                        "isrc": isrc,
                        "artist_name": artist_name,
                        "recording_title": recording_title,
                        "label": label,
                        "youtube_video_count": video_count,
                        "spotify_isrc_count": isrc_count,
                    },
                )
                record_count += 1
    finally:
        await engine.dispose()

    logger.info(f"Built {record_count} song-platform catalog rows.")
    return record_count


if __name__ == "__main__":
    asyncio.run(build_song_platform_catalog())