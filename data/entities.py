from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

POSTGRES_SCHEMA = "massive_music"


class Base(DeclarativeBase):
    pass


class SourceSong(Base):
    __tablename__ = "source_songs"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    code: Mapped[int] = mapped_column(primary_key=True)
    original_artist: Mapped[str | None] = mapped_column(Text)
    song_title: Mapped[str] = mapped_column(Text, nullable=False)
    song_writers: Mapped[str | None] = mapped_column(Text)
    search_query: Mapped[str | None] = mapped_column(Text)
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SpotifyArtist(Base):
    __tablename__ = "spotify_artists"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    spotify_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    spotify_url: Mapped[str | None] = mapped_column(Text)


class SpotifyAlbum(Base):
    __tablename__ = "spotify_albums"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    spotify_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    album_type: Mapped[str | None] = mapped_column(String(32))
    release_date: Mapped[str | None] = mapped_column(String(10))
    release_date_precision: Mapped[str | None] = mapped_column(String(10))
    total_tracks: Mapped[int | None] = mapped_column(Integer)
    spotify_url: Mapped[str | None] = mapped_column(Text)


class SpotifyTrack(Base):
    __tablename__ = "spotify_tracks"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    spotify_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_code: Mapped[int | None] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.source_songs.code")
    )
    album_spotify_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.spotify_albums.spotify_id")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    explicit: Mapped[bool | None] = mapped_column(Boolean)
    isrc: Mapped[str | None] = mapped_column(String(32))
    disc_number: Mapped[int | None] = mapped_column(Integer)
    track_number: Mapped[int | None] = mapped_column(Integer)
    spotify_url: Mapped[str | None] = mapped_column(Text)


class TrackArtist(Base):
    __tablename__ = "track_artists"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    track_spotify_id: Mapped[str] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.spotify_tracks.spotify_id"), primary_key=True
    )
    artist_spotify_id: Mapped[str] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.spotify_artists.spotify_id"), primary_key=True
    )
    artist_position: Mapped[int] = mapped_column(Integer, nullable=False)


class MusicWriter(Base):
    __tablename__ = "music_writers"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    musicbrainz_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class SpotifyTrackWriter(Base):
    __tablename__ = "spotify_track_writers"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    track_spotify_id: Mapped[str] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.spotify_tracks.spotify_id"), primary_key=True
    )
    musicbrainz_writer_id: Mapped[str] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.music_writers.musicbrainz_id"),
        primary_key=True,
    )
    credit_role: Mapped[str] = mapped_column(String(32), primary_key=True)


class SongTrackMatch(Base):
    __tablename__ = "song_track_matches"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    source_code: Mapped[int] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.source_songs.code"), primary_key=True
    )
    track_spotify_id: Mapped[str] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.spotify_tracks.spotify_id"), primary_key=True
    )
    query: Mapped[str] = mapped_column(Text, primary_key=True)
    result_position: Mapped[int] = mapped_column(Integer, nullable=False)


class YouTubeChannel(Base):
    __tablename__ = "youtube_channels"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    channel_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    youtube_url: Mapped[str | None] = mapped_column(Text)


class YouTubeVideo(Base):
    __tablename__ = "youtube_videos"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    video_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.youtube_channels.channel_id")
    )
    source_code: Mapped[int | None] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.source_songs.code")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    youtube_url: Mapped[str | None] = mapped_column(Text)


class SongVideoMatch(Base):
    __tablename__ = "song_video_matches"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    source_code: Mapped[int] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.source_songs.code"), primary_key=True
    )
    video_id: Mapped[str] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.youtube_videos.video_id"), primary_key=True
    )
    query: Mapped[str] = mapped_column(Text, primary_key=True)
    result_position: Mapped[int] = mapped_column(Integer, nullable=False)


class YouTubeSpotifyMatch(Base):
    __tablename__ = "youtube_spotify_matches"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    source_code: Mapped[int] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.source_songs.code"), primary_key=True
    )
    track_spotify_id: Mapped[str] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.spotify_tracks.spotify_id"), primary_key=True
    )
    video_id: Mapped[str] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.youtube_videos.video_id"), primary_key=True
    )


class SongPlatformCatalog(Base):
    __tablename__ = "song_platform_catalog"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    source_code: Mapped[int] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.source_songs.code"), primary_key=True
    )
    track_spotify_id: Mapped[str] = mapped_column(
        ForeignKey(f"{POSTGRES_SCHEMA}.spotify_tracks.spotify_id"), primary_key=True
    )
    song_title: Mapped[str] = mapped_column(Text, nullable=False)
    song_writers: Mapped[str | None] = mapped_column(Text)
    isrc: Mapped[str | None] = mapped_column(String(32))
    artist_name: Mapped[str | None] = mapped_column(Text)
    recording_title: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    youtube_video_count: Mapped[int] = mapped_column(Integer, nullable=False)
    spotify_isrc_count: Mapped[int] = mapped_column(Integer, nullable=False)


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    event_id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_code: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)


class DataQualityRun(Base):
    __tablename__ = "data_quality_runs"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    run_id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_name: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    records_read: Mapped[int] = mapped_column(Integer, nullable=False)
    records_loaded: Mapped[int] = mapped_column(Integer, nullable=False)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False)
    records_warned: Mapped[int] = mapped_column(Integer, nullable=False)
