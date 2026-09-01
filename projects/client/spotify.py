import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import base64

from projects.client.client import BaseAPIClient


class SpotifyClient(BaseAPIClient):
    BASE_URL = "https://api.spotify.com/v1"
    TOKEN_URL = "https://accounts.spotify.com/api/token"

    def __init__(self, client_id: str, client_secret: str):
        super().__init__()

        self.client_id = client_id
        self.client_secret = client_secret

        self._token = None

    async def auth_headers(self):

        if self._token is None:
            await self.refresh_token()

        return {"Authorization": f"Bearer {self._token}"}

    async def refresh_token(self):

        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        response = await self.client.post(
            self.TOKEN_URL,
            headers={"Authorization": f"Basic {auth}"},
            data={"grant_type": "client_credentials"},
        )

        response.raise_for_status()

        self._token = response.json()["access_token"]

    async def search(
        self,
        query: str,
        search_type="track",
        limit=10,
        offset=0,
    ):

        return await self.request(
            "GET",
            "/search",
            params={
                "q": query,
                "type": search_type,
                "limit": limit,
                "offset": offset,
            },
        )

    async def artist(self, artist_id: str):
        return await self.request(
            "GET",
            f"/artists/{artist_id}",
        )

    async def album(self, album_id: str):
        return await self.request(
            "GET",
            f"/albums/{album_id}",
        )

    async def track(self, track_id: str):
        return await self.request(
            "GET",
            f"/tracks/{track_id}",
        )
