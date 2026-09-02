# Airflow Deployment and Monitoring

## Workflow

`dags/pipeline.py` defines `music_catalog_pipeline`, scheduled daily at `02:00`
UTC. It prevents concurrent runs and applies retries to network and database
work:

1. Create or update the PostgreSQL schema.
2. Collect Spotify and YouTube responses into MongoDB in parallel.
3. Normalize each source into PostgreSQL in parallel.
4. Enrich Spotify tracks with MusicBrainz writer credits and build platform
   matches.
5. Enforce the quality gate, then publish `song_platform_catalog`.

The quality gate fails the DAG when a normalized record is rejected or when a
pipeline's warning rate exceeds $1\%$. This makes the problem visible as a
failed task in the Airflow Grid view and prevents an incomplete catalog from
being published.

## Local deployment

Set the project root as both the Python import path and Airflow DAG folder. Put
the API and database credentials in `.env`, which is already loaded by the
project modules:

```bash
export PYTHONPATH="$PWD"
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/dags"
poetry run airflow standalone
```

Open the local Airflow URL printed by `standalone`, find
`music_catalog_pipeline`, and use the Grid view to trigger or monitor a run.
For production, run the scheduler and webserver with a persistent Airflow
metadata database, mount the repository or package it into the worker image,
and provide the same values through your secret manager:

```text
MONGO_URI
POSTGRESQL_DB_USER
POSTGRESQL_DB_PASSWORD
POSTGRESQL_DB_HOST
POSTGRESQL_DB_PORT
POSTGRESQL_DB_NAME
SPOTIFY_ID
SPOTIFY_SECRET
YOUTUBE_API_KEY
MUSICBRAINZ_USER_AGENT
```

## Monitoring and recovery

Use Airflow task logs for API, retry, and task-failure details. The
`enforce_quality_gate` task logs the current read/load/reject/warn counts and
returns them as an Airflow task result. Use the following queries in an
operations dashboard or alert job:

```sql
SELECT pipeline_name, completed_at, records_read, records_loaded,
       records_rejected, records_warned
FROM massive_music.data_quality_runs
ORDER BY completed_at DESC;
```

```sql
SELECT pipeline_name, source_code, severity, rule_name, message, detected_at
FROM massive_music.data_quality_events
WHERE resolved_at IS NULL
ORDER BY detected_at DESC;
```

To recover, inspect the event's `raw_record`, repair the source data or parser,
set `resolved_at` and `resolution_note`, then trigger a new DAG run. The
MongoDB and PostgreSQL upserts make the replay idempotent.