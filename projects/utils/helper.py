from typing import List, Any
import re
import asyncio
import pandas as pd
import inflection
import pandas
from pathlib import Path
from typing import List, Any
from loguru import logger

from projects.config import ROOT_DIR


def split_batch(data: List[Any], batch_size: int) -> List[List[Any]]:
    """Splits a list into smaller lists of the specified size."""
    if batch_size <= 0:
        raise ValueError("Batch size must be greater than 0.")

    return [data[i : i + batch_size] for i in range(0, len(data), batch_size)]


def _to_snake_case(col: Any) -> str:
    col_str = str(col).strip()
    col_str = col_str.replace("&", "_and_")
    col_str = col_str.replace("%", "_percent")
    col_str = col_str.replace("#", "_num_")
    col_str = inflection.underscore(col_str)
    col_str = re.sub(r"[^a-zA-Z0-9]+", "_", col_str)
    col_str = re.sub(r"_+", "_", col_str)
    return col_str.strip("_").lower()


def snake_case_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renames all columns in a pandas DataFrame to snake_case
    using the inflection library and regex formatting.
    """
    df = df.copy()
    df.columns = [_to_snake_case(col) for col in df.columns]
    return df


async def cancel_pending_tasks(tasks: list[asyncio.Task]) -> None:
    """Cancels pending tasks and waits for cancellation to settle."""

    pending_tasks = [task for task in tasks if not task.done()]
    for task in pending_tasks:
        task.cancel()

    if pending_tasks:
        await asyncio.gather(*pending_tasks, return_exceptions=True)


def load_song_data(data_path: List[Any] | None = None):
    if not data_path:
        data_dir = Path.joinpath(ROOT_DIR, "data")
        data_path = [str(f) for f in data_dir.glob("*.csv")]

    if not data_path:
        return pd.DataFrame()

    if len(data_path) > 1:
        return pd.concat((pd.read_csv(f) for f in data_path), ignore_index=True)

    return pd.read_csv(data_path[0])


# def _sanitize_query_value(value: str) -> str:
#     # double quotes break Spotify's phrase grouping, so strip them
#     return str(value).replace('"', "").strip()


def construct_multisearch_query(data: list[dict]) -> list[list[str]]:
    """Build ordered Spotify search query candidates for each song."""
    constructed_queries = []

    for n in data:
        song_name = n["SONG TITLE"]
        artist_name = n["ORIGINAL ARTIST"]
        queries = [f'track:"{song_name}"']

        if artist_name:
            queries = [
                f"track:{song_name} artist:{artist_name}",
                *queries,
                f'artist:"{artist_name}"',
                f"{song_name} {artist_name}",
            ]

        constructed_queries.append(queries)

    return constructed_queries


def construct_search_query(data: list[dict]) -> list[str]:
    """Build ordered Spotify search query candidates for each song."""
    constructed_queries = []

    for n in data:
        song_name = n["SONG TITLE"]
        artist_name = n["ORIGINAL ARTIST"]

        if artist_name:
            queries = f"track:{song_name} artist:{artist_name}"
        else:
            queries = f'track:{song_name}'

        constructed_queries.append(queries)

    return constructed_queries


def log_bulk_write_results(results: list) -> None:
    """
    Parses a list of BulkWriteResult objects and Exceptions from asyncio.gather,
    aggregates the counts, and logs the final result.
    """
    total_matched = 0
    total_modified = 0
    total_upserted = 0

    for res in results:
        if isinstance(res, Exception):
            # Log individual chunk failures
            logger.error(f"A specific chunk failed during bulk write: {res}")
        else:
            # Aggregate success metrics
            total_matched += res.matched_count
            total_modified += res.modified_count
            total_upserted += res.upserted_count

    logger.info(
        f"**_Upsert data successful!_** "
        f"Total Matched: {total_matched} | "
        f"Total Modified: {total_modified} | "
        f"Total Inserted: {total_upserted}"
    )
