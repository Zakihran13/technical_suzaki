import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text
from data.client import init_async_db


async def create_metadata_schema() -> None:
    """Create the metadata tables defined in schema.sql."""
    schema_path = Path(__file__).with_name("schema.sql")
    statements = [
        statement.strip()
        for statement in schema_path.read_text().split(";")
        if statement.strip()
    ]
    engine = init_async_db()
    try:
        async with engine.begin() as connection:
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_metadata_schema())
