import asyncio
from unittest.mock import AsyncMock, patch

from projects.ingestion.youtube_metadata import process_youtube_metadata
from projects.utils.rate_limiter import AsyncRateLimiter


def test_process_youtube_metadata_upserts_raw_search_response():
    async def run_test():
        collection = AsyncMock()
        result = {
            "items": [
                {
                    "id": {"videoId": "video-123"},
                    "snippet": {"title": "The Artist - The Song"},
                }
            ]
        }

        with (
            patch("projects.ingestion.youtube_metadata.YouTubeClient") as client_class,
            patch("projects.ingestion.youtube_metadata.upsert_data", new_callable=AsyncMock) as upsert,
        ):
            client = client_class.return_value
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            client.search = AsyncMock(return_value=result)

            await process_youtube_metadata(
                [
                    {
                        "CODE": 1,
                        "ORIGINAL ARTIST": "The Artist",
                        "SONG TITLE": "The Song",
                    }
                ],
                collection,
                AsyncRateLimiter(max_rate=3),
            )

        upsert.assert_awaited_once()
        _, metadata = upsert.call_args.args
        assert metadata == [
            {
                "CODE": 1,
                "ORIGINAL ARTIST": "The Artist",
                "SONG TITLE": "The Song",
                "q": "The Song The Artist",
				"youtube_search": result,
                "created_at": metadata[0]["created_at"],
            }
        ]
        assert metadata[0]["created_at"].tzinfo is not None

    asyncio.run(run_test())