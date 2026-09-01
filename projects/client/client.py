import httpx
import asyncio


class BaseAPIClient:
    BASE_URL: str = ""

    def __init__(
        self,
        timeout: float = 30,
        max_retries: int = 3,
        initial_backoff: float = 1,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @property
    def client(self):
        if self._client is None:
            raise RuntimeError("Use async with")
        return self._client

    async def auth_headers(self) -> dict:
        """Override in subclass."""
        return {}

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params=None,
        json=None,
        headers=None,
    ):
        headers = {
            **await self.auth_headers(),
            **(headers or {}),
        }
        url = endpoint if endpoint.startswith(("http://", "https://")) else self.BASE_URL + endpoint

        delay = self.initial_backoff

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=headers,
                )

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:

                if e.response.status_code == 429:
                    retry = int(e.response.headers.get("Retry-After", delay))
                    await asyncio.sleep(retry)

                elif e.response.status_code >= 500:
                    await asyncio.sleep(delay)
                    delay *= 2

                elif attempt == self.max_retries:
                    raise

            except httpx.RequestError:

                if attempt == self.max_retries:
                    raise

                await asyncio.sleep(delay)
                delay *= 2
