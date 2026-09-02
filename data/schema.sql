CREATE SCHEMA IF NOT EXISTS massive_music;

CREATE TABLE IF NOT EXISTS massive_music.source_songs (
    code BIGINT PRIMARY KEY,
    original_artist TEXT,
    song_title TEXT NOT NULL,
    song_writers TEXT,
    search_query TEXT,
    source_created_at TIMESTAMPTZ
);

ALTER TABLE massive_music.source_songs
    ADD COLUMN IF NOT EXISTS song_writers TEXT;

CREATE TABLE IF NOT EXISTS massive_music.spotify_artists (
    spotify_id VARCHAR(64) PRIMARY KEY,
    name TEXT NOT NULL,
    spotify_url TEXT
);

CREATE TABLE IF NOT EXISTS massive_music.spotify_albums (
    spotify_id VARCHAR(64) PRIMARY KEY,
    name TEXT NOT NULL,
    label TEXT,
    album_type VARCHAR(32),
    release_date VARCHAR(10),
    release_date_precision VARCHAR(10),
    total_tracks INTEGER,
    spotify_url TEXT
);

ALTER TABLE massive_music.spotify_albums
    ADD COLUMN IF NOT EXISTS label TEXT;

CREATE TABLE IF NOT EXISTS massive_music.spotify_tracks (
    spotify_id VARCHAR(64) PRIMARY KEY,
    source_code BIGINT REFERENCES massive_music.source_songs(code),
    album_spotify_id VARCHAR(64) REFERENCES massive_music.spotify_albums(spotify_id),
    isrc VARCHAR(32),
    name TEXT NOT NULL,
    duration_ms INTEGER,
    explicit BOOLEAN,
    disc_number INTEGER,
    track_number INTEGER,
    spotify_url TEXT
);

CREATE TABLE IF NOT EXISTS massive_music.track_artists (
    track_spotify_id VARCHAR(64) REFERENCES massive_music.spotify_tracks(spotify_id),
    artist_spotify_id VARCHAR(64) REFERENCES massive_music.spotify_artists(spotify_id),
    artist_position INTEGER NOT NULL,
    PRIMARY KEY (track_spotify_id, artist_spotify_id)
);

CREATE TABLE IF NOT EXISTS massive_music.music_writers (
    musicbrainz_id VARCHAR(36) PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS massive_music.spotify_track_writers (
    track_spotify_id VARCHAR(64) REFERENCES massive_music.spotify_tracks(spotify_id),
    musicbrainz_writer_id VARCHAR(36) REFERENCES massive_music.music_writers(musicbrainz_id),
    credit_role VARCHAR(32) NOT NULL,
    PRIMARY KEY (track_spotify_id, musicbrainz_writer_id, credit_role)
);

CREATE TABLE IF NOT EXISTS massive_music.song_track_matches (
    source_code BIGINT REFERENCES massive_music.source_songs(code),
    track_spotify_id VARCHAR(64) REFERENCES massive_music.spotify_tracks(spotify_id),
    query TEXT NOT NULL,
    result_position INTEGER NOT NULL,
    PRIMARY KEY (source_code, track_spotify_id, query)
);

CREATE INDEX IF NOT EXISTS song_track_matches_track_idx 
    ON massive_music.song_track_matches (track_spotify_id);

CREATE INDEX IF NOT EXISTS spotify_track_writers_track_idx
    ON massive_music.spotify_track_writers (track_spotify_id);

CREATE TABLE IF NOT EXISTS massive_music.youtube_channels (
    channel_id VARCHAR(64) PRIMARY KEY,
    title TEXT NOT NULL,
    youtube_url TEXT
);

CREATE TABLE IF NOT EXISTS massive_music.youtube_videos (
    video_id VARCHAR(64) PRIMARY KEY,
    channel_id VARCHAR(64) REFERENCES massive_music.youtube_channels(channel_id),
    source_code BIGINT REFERENCES massive_music.source_songs(code),
    title TEXT NOT NULL,
    description TEXT,
    published_at TIMESTAMPTZ,
    youtube_url TEXT
);

CREATE TABLE IF NOT EXISTS massive_music.song_video_matches (
    source_code BIGINT REFERENCES massive_music.source_songs(code),
    video_id VARCHAR(64) REFERENCES massive_music.youtube_videos(video_id),
    query TEXT NOT NULL,
    result_position INTEGER NOT NULL,
    PRIMARY KEY (source_code, video_id, query)
);

CREATE INDEX IF NOT EXISTS song_video_matches_video_idx 
    ON massive_music.song_video_matches (video_id);

CREATE TABLE IF NOT EXISTS massive_music.youtube_spotify_matches (
    source_code BIGINT REFERENCES massive_music.source_songs(code),
    track_spotify_id VARCHAR(64) REFERENCES massive_music.spotify_tracks(spotify_id),
    video_id VARCHAR(64) REFERENCES massive_music.youtube_videos(video_id),
    PRIMARY KEY (source_code, track_spotify_id, video_id)
);

ALTER TABLE massive_music.youtube_spotify_matches
    DROP COLUMN IF EXISTS title_similarity,
    DROP COLUMN IF EXISTS context_similarity,
    DROP COLUMN IF EXISTS match_score;

CREATE INDEX IF NOT EXISTS youtube_spotify_matches_track_idx
    ON massive_music.youtube_spotify_matches (track_spotify_id);

CREATE TABLE IF NOT EXISTS massive_music.song_platform_catalog (
    source_code BIGINT REFERENCES massive_music.source_songs(code),
    track_spotify_id VARCHAR(64) REFERENCES massive_music.spotify_tracks(spotify_id),
    song_title TEXT NOT NULL,
    song_writers TEXT,
    isrc VARCHAR(32),
    artist_name TEXT,
    recording_title TEXT NOT NULL,
    label TEXT,
    youtube_video_count INTEGER NOT NULL,
    spotify_isrc_count INTEGER NOT NULL,
    PRIMARY KEY (source_code, track_spotify_id)
);

CREATE INDEX IF NOT EXISTS song_platform_catalog_source_idx
    ON massive_music.song_platform_catalog (source_code);

CREATE TABLE IF NOT EXISTS massive_music.data_quality_events (
    event_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(64) NOT NULL,
    source_code BIGINT,
    severity VARCHAR(16) NOT NULL CHECK (severity IN ('warning', 'error')),
    rule_name VARCHAR(128) NOT NULL,
    message TEXT NOT NULL,
    raw_record JSONB NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolution_note TEXT
);

CREATE INDEX IF NOT EXISTS data_quality_events_open_idx
    ON massive_music.data_quality_events (pipeline_name, severity, detected_at)
    WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS massive_music.data_quality_runs (
    run_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(64) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    records_read INTEGER NOT NULL CHECK (records_read >= 0),
    records_loaded INTEGER NOT NULL CHECK (records_loaded >= 0),
    records_rejected INTEGER NOT NULL CHECK (records_rejected >= 0),
    records_warned INTEGER NOT NULL CHECK (records_warned >= 0)
);

CREATE INDEX IF NOT EXISTS data_quality_runs_pipeline_idx
    ON massive_music.data_quality_runs (pipeline_name, completed_at DESC);