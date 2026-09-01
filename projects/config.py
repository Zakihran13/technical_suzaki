import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


ROOT_DIR = Path(__file__).resolve().parents[1]

SPOTIFY_ID = str(os.getenv("SPOTIFY_ID"))
SPOTIFY_SECRET = str(os.getenv("SPOTIFY_SECRET"))

DB_NAME = "massive_data_test"
