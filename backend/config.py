import os
from dotenv import load_dotenv

load_dotenv()


def get_required_env(name: str) -> str:
    """Get required environment variable or raise clear error."""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


R2_ENDPOINT_URL = get_required_env("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = get_required_env("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = get_required_env("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = get_required_env("R2_BUCKET_NAME")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/db.sqlite")
MODAL_APP_NAME = os.getenv("MODAL_APP_NAME", "jokestracker")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
