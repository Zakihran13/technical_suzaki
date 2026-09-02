import asyncio

import httpx

from client.youtube import YouTubeClient, YouTubeVideoMetadata


def test_video_metadata_normalizes_response_and_title():
    async def run_test():
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/youtube/v3/videos"
            assert request.url.params["key"] == "test-key"
            assert request.url.params["id"] == "video-123"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "video-123",
                            "snippet": {
                                "channelId": "channel-456",
                                "title": "The Artist - The Song (Official Video)",
                            },
                        }
                    ]
                },
            )

        client = YouTubeClient("test-key")
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            metadata = await client.video_metadata("video-123")
        finally:
            await client._client.aclose()

        assert metadata == YouTubeVideoMetadata(
            video_id="video-123",
            channel_id="channel-456",
            artist="The Artist",
            song_title="The Song",
            video_title="The Artist - The Song (Official Video)",
        )

    asyncio.run(run_test())