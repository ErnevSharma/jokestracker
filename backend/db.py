import os
import sqlite3
from sqlmodel import SQLModel, create_engine, Session
from backend.config import DATABASE_URL

# Ensure data directory exists for SQLite
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db():
    SQLModel.metadata.create_all(engine)
    _migrate_schema()


def _migrate_schema():
    """Run one-time schema migrations."""
    if not DATABASE_URL.startswith("sqlite:///"):
        return  # Only for SQLite

    db_path = DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if claude_analysis column exists
        cursor.execute("PRAGMA table_info(analysisresult)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'claude_analysis' not in columns:
            print("Running migration: adding claude_analysis column...")
            cursor.execute("ALTER TABLE analysisresult ADD COLUMN claude_analysis TEXT")
            conn.commit()
            print("✓ Migration complete")
    except sqlite3.OperationalError:
        # Table doesn't exist yet, will be created by create_all
        pass
    finally:
        conn.close()


def get_session():
    with Session(engine) as session:
        yield session
