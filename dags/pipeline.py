import asyncio
from datetime import datetime, timedelta, timezone
import logging

from airflow.exceptions import AirflowException
from airflow.sdk import dag, task
from sqlalchemy import func, select

from data.client import init_async_db
from data.entities import DataQualityRun
from data.run_db import create_metadata_schema
from projects.ingestion.song_metadata import exec_spotify_metadata
from projects.ingestion.youtube_metadata import exec_youtube_metadata
from projects.transform.metadata_ingestion import ingest_spotify_metadata
from projects.transform.youtube_spotify_matching import (
	build_song_platform_catalog,
	create_youtube_spotify_matches,
)
from projects.transform.yotube_ingestion import ingest_youtube_metadata

logger = logging.getLogger(__name__)
QUALITY_PIPELINES = ("spotify_normalization", "youtube_normalization")
WARNING_RATE_THRESHOLD = 0.01


async def _latest_quality_runs() -> list[dict[str, int | str]]:
	latest_runs = (
		select(
			DataQualityRun.pipeline_name,
			func.max(DataQualityRun.completed_at).label("completed_at"),
		)
		.where(DataQualityRun.pipeline_name.in_(QUALITY_PIPELINES))
		.group_by(DataQualityRun.pipeline_name)
		.subquery()
	)
	statement = select(
		DataQualityRun.pipeline_name,
		DataQualityRun.records_read,
		DataQualityRun.records_loaded,
		DataQualityRun.records_rejected,
		DataQualityRun.records_warned,
	).join(
		latest_runs,
		(DataQualityRun.pipeline_name == latest_runs.c.pipeline_name)
		& (DataQualityRun.completed_at == latest_runs.c.completed_at),
	)
	engine = init_async_db()
	try:
		async with engine.connect() as connection:
			result = await connection.execute(statement)
			return [dict(row) for row in result.mappings()]
	finally:
		await engine.dispose()


@dag(
	dag_id="music_catalog_pipeline",
	schedule="0 2 * * *",
	start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
	catchup=False,
	max_active_runs=1,
	tags=["music", "metadata", "data-quality"],
	doc_md="""
	Collects music-platform metadata, normalizes it, builds the reporting catalog,
	and blocks publication when quality errors are detected.
	""",
)
def music_catalog_pipeline():
	@task(retries=2, retry_delay=timedelta(minutes=2))
	def initialize_schema() -> None:
		asyncio.run(create_metadata_schema())

	@task(retries=3, retry_delay=timedelta(minutes=5))
	def ingest_spotify_raw() -> None:
		asyncio.run(exec_spotify_metadata())

	@task(retries=3, retry_delay=timedelta(minutes=5))
	def ingest_youtube_raw() -> None:
		asyncio.run(exec_youtube_metadata())

	@task(retries=2, retry_delay=timedelta(minutes=2))
	def normalize_spotify() -> int:
		return asyncio.run(ingest_spotify_metadata())

	@task(retries=2, retry_delay=timedelta(minutes=2))
	def normalize_youtube() -> int:
		return asyncio.run(ingest_youtube_metadata())

	@task(retries=2, retry_delay=timedelta(minutes=2))
	def match_platforms() -> int:
		return asyncio.run(create_youtube_spotify_matches())

	@task(retries=2, retry_delay=timedelta(minutes=2))
	def build_catalog() -> int:
		return asyncio.run(build_song_platform_catalog())

	@task
	def enforce_quality_gate() -> dict[str, dict[str, int | float]]:
		runs = asyncio.run(_latest_quality_runs())
		runs_by_pipeline = {str(run["pipeline_name"]): run for run in runs}
		missing_pipelines = set(QUALITY_PIPELINES) - runs_by_pipeline.keys()
		if missing_pipelines:
			raise AirflowException(
				f"Missing quality metrics for: {', '.join(sorted(missing_pipelines))}"
			)

		summaries = {}
		failures = []
		for pipeline_name, run in runs_by_pipeline.items():
			records_read = int(run["records_read"])
			records_loaded = int(run["records_loaded"])
			records_rejected = int(run["records_rejected"])
			records_warned = int(run["records_warned"])
			warning_rate = records_warned / records_read if records_read else 0
			summaries[pipeline_name] = {
				"records_read": records_read,
				"records_loaded": records_loaded,
				"records_rejected": records_rejected,
				"records_warned": records_warned,
				"warning_rate": warning_rate,
			}
			logger.info("Data-quality summary for %s: %s", pipeline_name, summaries[pipeline_name])
			if records_rejected:
				failures.append(f"{pipeline_name}: {records_rejected} rejected")
			if warning_rate > WARNING_RATE_THRESHOLD:
				failures.append(f"{pipeline_name}: {warning_rate:.1%} warnings")

		if failures:
			raise AirflowException("Data-quality gate failed: " + "; ".join(failures))
		return summaries

	schema = initialize_schema()
	spotify_raw = ingest_spotify_raw()
	youtube_raw = ingest_youtube_raw()
	schema >> [spotify_raw, youtube_raw]

	spotify_normalized = normalize_spotify()
	youtube_normalized = normalize_youtube()
	spotify_raw >> spotify_normalized
	youtube_raw >> youtube_normalized

	platform_matches = match_platforms()
	[spotify_normalized, youtube_normalized] >> platform_matches

	quality_gate = enforce_quality_gate()
	[spotify_normalized, youtube_normalized] >> quality_gate

	catalog = build_catalog()
	[platform_matches, quality_gate] >> catalog


music_catalog_pipeline()
