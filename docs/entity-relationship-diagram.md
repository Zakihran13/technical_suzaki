# Entity Relationship Diagram

This ERD documents the normalized PostgreSQL schema `massive_music` defined in
`data/schema.sql`. Raw Spotify and YouTube API responses remain in MongoDB and
are intentionally outside this relational diagram.

```mermaid
erDiagram
    SOURCE_SONGS {
        bigint code PK
        text original_artist
        text song_title
        text song_writers
        text search_query
        timestamptz source_created_at
    }

    SPOTIFY_ARTISTS {
        varchar spotify_id PK
        text name
        text spotify_url
    }

    SPOTIFY_ALBUMS {
        varchar spotify_id PK
        text name
        text label
        varchar album_type
        varchar release_date
    }

    SPOTIFY_TRACKS {
        varchar spotify_id PK
        bigint source_code FK
        varchar album_spotify_id FK
        varchar isrc
        text name
        integer duration_ms
    }

    TRACK_ARTISTS {
        varchar track_spotify_id PK, FK
        varchar artist_spotify_id PK, FK
        integer artist_position
    }

    SONG_TRACK_MATCHES {
        bigint source_code PK, FK
        varchar track_spotify_id PK, FK
        text query PK
        integer result_position
    }

    YOUTUBE_CHANNELS {
        varchar channel_id PK
        text title
        text youtube_url
    }

    YOUTUBE_VIDEOS {
        varchar video_id PK
        varchar channel_id FK
        bigint source_code FK
        text title
        timestamptz published_at
    }

    SONG_VIDEO_MATCHES {
        bigint source_code PK, FK
        varchar video_id PK, FK
        text query PK
        integer result_position
    }

    YOUTUBE_SPOTIFY_MATCHES {
        bigint source_code PK, FK
        varchar track_spotify_id PK, FK
        varchar video_id PK, FK
    }

    SONG_PLATFORM_CATALOG {
        bigint source_code PK, FK
        varchar track_spotify_id PK, FK
        text song_title
        varchar isrc
        integer youtube_video_count
        integer spotify_isrc_count
    }

    MUSIC_WRITERS {
        varchar musicbrainz_id PK
        text name
    }

    SPOTIFY_TRACK_WRITERS {
        varchar track_spotify_id PK, FK
        varchar musicbrainz_writer_id PK, FK
        varchar credit_role PK
    }

    DATA_QUALITY_EVENTS {
        bigint event_id PK
        varchar pipeline_name
        bigint source_code
        varchar severity
        varchar rule_name
        jsonb raw_record
        timestamptz detected_at
    }

    DATA_QUALITY_RUNS {
        bigint run_id PK
        varchar pipeline_name
        timestamptz started_at
        timestamptz completed_at
        integer records_read
        integer records_rejected
    }

    SOURCE_SONGS o|--o{ SPOTIFY_TRACKS : source_code
    SPOTIFY_ALBUMS o|--o{ SPOTIFY_TRACKS : album_spotify_id
    SPOTIFY_TRACKS ||--o{ TRACK_ARTISTS : track_spotify_id
    SPOTIFY_ARTISTS ||--o{ TRACK_ARTISTS : artist_spotify_id
    SOURCE_SONGS ||--o{ SONG_TRACK_MATCHES : source_code
    SPOTIFY_TRACKS ||--o{ SONG_TRACK_MATCHES : track_spotify_id
    SOURCE_SONGS o|--o{ YOUTUBE_VIDEOS : source_code
    YOUTUBE_CHANNELS o|--o{ YOUTUBE_VIDEOS : channel_id
    SOURCE_SONGS ||--o{ SONG_VIDEO_MATCHES : source_code
    YOUTUBE_VIDEOS ||--o{ SONG_VIDEO_MATCHES : video_id
    SOURCE_SONGS ||--o{ YOUTUBE_SPOTIFY_MATCHES : source_code
    SPOTIFY_TRACKS ||--o{ YOUTUBE_SPOTIFY_MATCHES : track_spotify_id
    YOUTUBE_VIDEOS ||--o{ YOUTUBE_SPOTIFY_MATCHES : video_id
    SOURCE_SONGS ||--o{ SONG_PLATFORM_CATALOG : source_code
    SPOTIFY_TRACKS ||--o{ SONG_PLATFORM_CATALOG : track_spotify_id
    SPOTIFY_TRACKS ||--o{ SPOTIFY_TRACK_WRITERS : track_spotify_id
    MUSIC_WRITERS ||--o{ SPOTIFY_TRACK_WRITERS : musicbrainz_writer_id
```

## Reporting and operations

`song_platform_catalog` is the reporting projection: one row per source song and
Spotify track with label, ISRC, artist, and cross-platform count fields. The
pipeline rebuilds it only after Spotify and YouTube metadata pass the quality
gate.

`data_quality_events` and `data_quality_runs` are operational audit tables.
They do not have foreign-key constraints because an invalid raw record can lack a
valid `source_code`; this permits reliable quarantine and diagnosis of malformed
input.

`music_writers` and `spotify_track_writers` are included because they are part of
the database schema. Their MusicBrainz enrichment task is currently disabled in
the Airflow DAG, so these tables are not populated by scheduled runs.