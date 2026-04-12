import os
from dotenv import load_dotenv

load_dotenv()

R2_ENDPOINT_URL = os.environ["R2_ENDPOINT_URL"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET_NAME = os.environ["R2_BUCKET_NAME"]

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/db.sqlite")
MODAL_APP_NAME = os.environ.get("MODAL_APP_NAME", "jokestracker")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")
