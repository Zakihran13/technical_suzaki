import asyncio

import httpx

from projects.client.musicbrainz import MusicBrainzClient


def test_recordings_by_isrc_normalizes_to_uppercase():
    async def run_test():
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/ws/2/isrc/USHM20871973"
            return httpx.Response(200, json={"recordings": []})

        client = MusicBrainzClient("test-client/1.0 (test@example.com)")
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            assert await client.recordings_by_isrc("ushm20871973") == []
        finally:
            await client._client.aclose()

    asyncio.run(run_test())