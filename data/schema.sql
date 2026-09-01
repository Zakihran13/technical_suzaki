CREATE SCHEMA IF NOT EXISTS massive_music;

CREATE TABLE IF NOT EXISTS massive_music.source_songs (
    code BIGINT PRIMARY KEY,
    original_artist TEXT,
    song_title TEXT NOT NULL,
    search_query TEXT,
    source_created_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS massive_music.spotify_artists (
    spotify_id VARCHAR(64) PRIMARY KEY,
    name TEXT NOT NULL,
    spotify_url TEXT
);

CREATE TABLE IF NOT EXISTS massive_music.spotify_albums (
    spotify_id VARCHAR(64) PRIMARY KEY,
    name TEXT NOT NULL,
    album_type VARCHAR(32),
    release_date VARCHAR(10),
    release_date_precision VARCHAR(10),
    total_tracks INTEGER,
    spotify_url TEXT
);

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

CREATE TABLE IF NOT EXISTS massive_music.song_track_matches (
    source_code BIGINT REFERENCES massive_music.source_songs(code),
    track_spotify_id VARCHAR(64) REFERENCES massive_music.spotify_tracks(spotify_id),
    query TEXT NOT NULL,
    result_position INTEGER NOT NULL,
    PRIMARY KEY (source_code, track_spotify_id, query)
);

CREATE INDEX IF NOT EXISTS song_track_matches_track_idx 
    ON massive_music.song_track_matches (track_spotify_id);