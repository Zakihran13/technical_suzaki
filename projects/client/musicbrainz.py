import httpx

from projects.client.client import BaseAPIClient
from projects.utils.rate_limiter import AsyncRateLimiter


class MusicBrainzClient(BaseAPIClient):
    """Async client for MusicBrainz recording and work credits."""

    BASE_URL = "https://musicbrainz.org/ws/2"

    def __init__(self, user_agent: str, rate_limiter: AsyncRateLimiter | None = None):
        super().__init__(rate_limiter=rate_limiter)
        self.user_agent = user_agent

    async def auth_headers(self) -> dict:
        return {"User-Agent": self.user_agent}

    async def recordings_by_isrc(self, isrc: str) -> list[dict]:
        try:
            response = await self.request(
                "GET",
                f"/isrc/{isrc.upper()}",
                params={"fmt": "json"},
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {400, 404}:
                return []
            raise
        return response.get("recordings", []) if isinstance(response, dict) else []

    async def recording(self, recording_id: str) -> dict:
        try:
            response = await self.request(
                "GET",
                f"/recording/{recording_id}",
                params={"fmt": "json", "inc": "work-rels"},
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return {}
            raise
        return response if isinstance(response, dict) else {}

    async def work(self, work_id: str) -> dict:
        try:
            response = await self.request(
                "GET",
                f"/work/{work_id}",
                params={"fmt": "json", "inc": "artist-rels"},
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return {}
            raise
        return response if isinstance(response, dict) else {}