from datetime import datetime, timezone
from functools import partial
from typing import Dict, List

import aiometer
import numpy as np
import pandas as pd
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorCollection

from data.client import get_async_mongodb
from data.statements import upsert_data
from projects.client.youtube import YouTubeClient
from projects.config import (
    DB_NAME,
    YOUTUBE_API_KEY,
    YOUTUBE_MAX_CONCURRENT_BATCHES,
    YOUTUBE_MAX_REQUESTS_PER_SECOND,
)
from projects.utils.helper import (
    construct_youtube_search_params,
    load_song_data,
    split_batch,
)
from projects.utils.rate_limiter import AsyncRateLimiter


async def process_youtube_metadata(
    song_data: List[Dict],
    collection: AsyncIOMotorCollection,
    rate_limiter: AsyncRateLimiter,
) -> None:
    if not song_data:
        logger.warning("no song data is found")
        return

    search_params = construct_youtube_search_params(song_data)
    async with YouTubeClient(YOUTUBE_API_KEY, rate_limiter=rate_limiter) as client:
        results = await aiometer.run_all(
            [partial(client.search, **params) for params in search_params],
            max_at_once=YOUTUBE_MAX_REQUESTS_PER_SECOND,
        )

    metadata = [
        {
            **record,
            "q": params["q"],
            "youtube_search": result,
            "created_at": datetime.now(tz=timezone.utc),
        }
        for record, params, result in zip(song_data, search_params, results)
    ]

    try:
        await upsert_data(collection, metadata, conflict_cols=["CODE"])
    except Exception as error:
        unique_codes = " ".join(
            dict.fromkeys(str(record["CODE"]) for record in song_data)
        )
        logger.error(
            f"failed to insert YouTube metadata: **{error}** "
            f"\nerror_data: **{unique_codes}**"
        )


async def exec_youtube_metadata(
    song_data_df: pd.DataFrame = pd.DataFrame(),
) -> None:
    if song_data_df.empty:
        song_data_df = load_song_data().replace({np.nan: None})

    if "CODE" not in song_data_df.columns:
        raise ValueError("song data must include a 'CODE' column")
    if "SONG TITLE" not in song_data_df.columns:
        raise ValueError("song data must include a 'SONG TITLE' column")
    if "ORIGINAL ARTIST" not in song_data_df.columns:
        raise ValueError("song data must include an 'ORIGINAL ARTIST' column")

    logger.info("preparing db connection")
    db_mongo = get_async_mongodb(DB_NAME)
    coll_mongo = db_mongo["raw_youtube"]
    await coll_mongo.create_index([("CODE", 1)], unique=True, name="code_unique")

    song_batches = split_batch(song_data_df.to_dict("records")[:5], 10)
    rate_limiter = AsyncRateLimiter(max_rate=YOUTUBE_MAX_REQUESTS_PER_SECOND)
    tasks = [
        partial(
            process_youtube_metadata,
            batch,
            coll_mongo,
            rate_limiter,
        )
        for batch in song_batches
    ]

    try:
        logger.info(f"initiating YouTube process. found {len(tasks)} batch process.")
        await aiometer.run_all(tasks, max_at_once=YOUTUBE_MAX_CONCURRENT_BATCHES)
    except Exception as error:
        logger.error(f"failed while running YouTube process: **{error}**")


if __name__ == "__main__":
    import asyncio

    asyncio.run(exec_youtube_metadata())
