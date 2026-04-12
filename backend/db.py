import os
from sqlmodel import SQLModel, create_engine, Session
from backend.config import DATABASE_URL

# Ensure data directory exists for SQLite
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
