import os
import sys
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import asyncio
from loguru import logger
from functools import partial
import aiometer
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection

from projects.client.spotify import SpotifyClient
from projects.utils.helper import load_song_data, split_batch, construct_search_query
from projects.config import SPOTIFY_ID, SPOTIFY_SECRET, DB_NAME
from data.client import get_async_mongodb
from data.statements import upsert_data



async def process_spotify_metadata(
    app, song_data: List[Dict], collection: AsyncIOMotorCollection
):
    metadata = []
    if not song_data:
        logger.error("no data is found")
        return

    search_query = construct_search_query(song_data)
    spotify_results = await asyncio.gather(
        *(app.search(query=query) for query in search_query)
    )

    metadata.extend(
        {
            **song,
            "spotify_search": items,
            "created_at": datetime.now(tz=timezone.utc),
        }
        for song, items in zip(song_data, spotify_results)
    )

    if metadata:
        try:
            await upsert_data(collection, metadata, conflict_cols=["CODE"])
        except Exception as e:
            unique_codes = " ".join(
                dict.fromkeys(str(d["CODE"]) for d in song_data if "CODE" in d)
            )
            logger.error(
                f"failed to insert the data: **{e}** \nerror_data: **{unique_codes}**"
            )


async def exec_spotify_metadata(song_data_df: pd.DataFrame = pd.DataFrame([])):
    if song_data_df.empty:
        song_data_df = load_song_data()

    logger.info("preparing db connection")
    db_mongo = get_async_mongodb(DB_NAME)
    coll_mongo = db_mongo["raw_spotify"]
    await coll_mongo.create_index(
        [("CODE", 1)],
        unique=1,
        name="code_unique",
    )

    song_data = split_batch(song_data_df.to_dict("records"), 10)

    async with SpotifyClient(SPOTIFY_ID, SPOTIFY_SECRET) as app:
        await app.auth_headers()

        tasks = [
            partial(process_spotify_metadata, app, data, coll_mongo)
            for data in song_data
        ]
        try:
            logger.info(f"initiating data process. found {len(tasks)} batch process.")
            await aiometer.run_all(tasks, max_at_once=5)
        except Exception as e:
            logger.error(f"failed while running the process: **{e}**")


if __name__ == "__main__":
    asyncio.run(exec_spotify_metadata())
