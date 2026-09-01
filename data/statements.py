from motor.motor_asyncio import AsyncIOMotorCollection
import pandas as pd
from pymongo import UpdateOne
from loguru import logger
import asyncio
from typing import List, Any

from projects.utils.helper import split_batch, log_bulk_write_results


async def process_chunk(
    coll: AsyncIOMotorCollection, chunk: list[dict], conflict_cols: list[str]
):
    batch_operations = [
        UpdateOne(
            {col: record[col] for col in conflict_cols}, {"$set": record}, upsert=True
        )
        for record in chunk
    ]

    return await coll.bulk_write(batch_operations, ordered=False)


async def upsert_data(
    coll: AsyncIOMotorCollection, data: List[Any], conflict_cols: list[str]
):
    if not conflict_cols:
        raise ValueError("conflict_cols cannot be empty.")

    unique_codes = " ".join(dict.fromkeys(str(d["CODE"]) for d in data if "CODE" in d))
    logger.info(f"inserting data for: **{unique_codes}**")

    batch_data = split_batch(data, 10_000)
    operation_tasks = [
        process_chunk(coll, chunk, conflict_cols) for chunk in batch_data
    ]

    if operation_tasks:
        try:
            results = await asyncio.gather(*operation_tasks, return_exceptions=True)
            log_bulk_write_results(results)
        except Exception as e:
            logger.error(f"An error occurred during bulk write: {e}")
