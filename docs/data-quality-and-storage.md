# Data Quality and Storage Design

## Current data flow

Spotify and YouTube API responses are retained in MongoDB as immutable raw input
for each source `CODE`. PostgreSQL holds the normalized relational model used by
the catalog and reporting queries. Both tiers use stable source and platform IDs
as their idempotency keys, so reruns update the same logical record rather than
creating duplicates.

## Validation and data-quality controls

Normalization applies these controls before a record reaches reporting tables:

- `CODE` must be present and convertible to an integer.
- `SONG TITLE` must be a non-empty string.
- A Spotify or YouTube search payload must have the expected structure.
- Candidate search results are normalized and filtered with a $0.90$ title
  similarity threshold. This limits accidental matches when the source lacks an
  artist.
- Missing optional values are retained as SQL `NULL`; `NaN` source values are
  converted to `NULL` before loading.
- PostgreSQL primary keys, foreign keys, unique MongoDB `CODE` indexes, and
  conflict-aware upserts enforce deduplication and referential integrity.

Invalid records are not loaded into normalized tables. They are written to
`massive_music.data_quality_events` with a rule name, severity, source code,
JSON-safe raw record, detection timestamp, and optional resolution fields. This
is the quarantine ledger: operators correct the upstream source or parser, mark
the event resolved, and rerun the idempotent pipeline for that `CODE`.

Each normalization execution writes `data_quality_runs`, which reconciles the
number of records read, loaded, rejected, and warned. Alert when any rejection
occurs, when warnings or rejection rate exceed $1\%$, or when the current row
count is materially below the previous successful run. A scheduled check should
also alert on unresolved `error` events older than one business day.

## Corruption and anomaly management

Raw MongoDB payloads provide replayable evidence of API responses. The pipeline
should store MongoDB backups and PostgreSQL point-in-time recovery backups in a
separate account and periodically restore-test them. Reconciliation metrics,
foreign-key constraints, and the quarantine ledger detect partial loads and
invalid relations. For semantic anomalies, monitor sudden shifts in empty search
results, candidate match counts, title-similarity distributions, and distinct
ISRC counts; route outliers to the same event ledger for review before publishing
them to reporting datasets.

## Scalable warehouse target

For production reporting, retain the existing MongoDB and PostgreSQL layers as
ingestion and operational stores, then publish validated PostgreSQL changes to
an Amazon S3 data lake in Parquet. Load that curated data into Amazon Redshift
Serverless (or Snowflake with the same S3 staging layout) as the analytical
warehouse.

Use a star schema with `dim_song`, `dim_artist`, `dim_album`, `dim_channel`,
and `fact_song_platform_match`. Partition S3 by ingestion date and dataset;
sort Redshift facts by `source_code` and distribute on the most common join key.
Incremental CDC loads and materialized reporting views keep dashboard queries
fast without loading API-facing PostgreSQL. This separates bursty ingestion from
concurrent BI workloads and scales warehouse compute independently.

Analysts receive read-only, role-based access to curated schemas through a BI
tool such as QuickSight, Tableau, or Power BI. Engineering retains write access
to staging only. Encrypt data at rest and in transit, use a secrets manager for
credentials, apply retention policies to raw payloads, and expose data-quality
run/event tables as an operational dashboard beside catalog reports.