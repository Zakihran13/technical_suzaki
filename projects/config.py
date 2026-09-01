import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


ROOT_DIR = Path(__file__).resolve().parents[1]

SPOTIFY_ID = str(os.getenv("SPOTIFY_ID"))
SPOTIFY_SECRET = str(os.getenv("SPOTIFY_SECRET"))

DB_NAME = "massive_data_test"

# Spotify does not publish an exact quota, but bursts of concurrent requests
# are known to trip 429s that can lock the app out for hours. Keep this
# conservative; it is shared across all concurrent batches/requests.
SPOTIFY_MAX_REQUESTS_PER_SECOND = 3
SPOTIFY_MAX_CONCURRENT_BATCHES = 2

