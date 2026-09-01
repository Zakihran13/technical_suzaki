from dataclasses import dataclass
import re

from projects.client.client import BaseAPIClient


@dataclass(frozen=True)
class YouTubeVideoMetadata:
    video_id: str
    channel_id: str
    song_title: str
    artist: str | None
    video_title: str


class YouTubeClient(BaseAPIClient):
    """Async client for the YouTube Data API v3."""

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key

    async def request(self, method: str, endpoint: str, *, params=None, **kwargs):
        params = {"key": self.api_key, **(params or {})}
        return await super().request(method, endpoint, params=params, **kwargs)

    async def video(self, video_id: str) -> dict:
        """Return the raw YouTube Data API response for one video."""
        response = await self.request(
            "GET",
            "/videos",
            params={"part": "snippet", "id": video_id},
        )
        if not isinstance(response, dict):
            raise ValueError("YouTube API returned an invalid response")
        return response

    async def video_metadata(self, video_id: str) -> YouTubeVideoMetadata:
        """Retrieve video metadata and infer music credits from its title."""
        response = await self.video(video_id)
        items = response.get("items", [])
        if not items:
            raise ValueError(f"YouTube video not found: {video_id}")

        item = items[0]
        snippet = item["snippet"]
        video_title = snippet["title"]
        artist, song_title = self._parse_music_title(video_title)

        return YouTubeVideoMetadata(
            video_id=item["id"],
            channel_id=snippet["channelId"],
            song_title=song_title,
            artist=artist,
            video_title=video_title,
        )

    @staticmethod
    def _parse_music_title(video_title: str) -> tuple[str | None, str]:
        """Parse common music-video titles such as 'Artist - Song (Official Video)'."""
        title = re.sub(
            r"\s*[\[(](?:official (?:music )?video|official audio|lyrics?|audio)[^\])]*[\])]\s*$",
            "",
            video_title,
            flags=re.IGNORECASE,
        ).strip()
        for separator in (" - ", " -", " | ", " – ", " — "):
            if separator in title:
                artist, song_title = title.split(separator, maxsplit=1)
                if artist.strip() and song_title.strip():
                    return artist.strip(), song_title.strip()
        return None, title
