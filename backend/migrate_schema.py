"""
Database migration script to add claude_analysis column.
Run with: python backend/migrate_schema.py
"""
import sqlite3
from backend.config import DATABASE_URL

def migrate():
    # Extract path from sqlite:/// URL
    db_path = DATABASE_URL.replace("sqlite:///", "")

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if claude_analysis column exists
    cursor.execute("PRAGMA table_info(analysisresult)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'claude_analysis' not in columns:
        print("Adding claude_analysis column...")
        cursor.execute("""
            ALTER TABLE analysisresult
            ADD COLUMN claude_analysis TEXT
        """)
        conn.commit()
        print("✓ Added claude_analysis column")
    else:
        print("✓ claude_analysis column already exists")

    # Note: SQLite doesn't support dropping columns easily, and SQLModel
    # will ignore line_scores and diff columns since they're not in the model.
    # We can leave them in the database without issues.

    if 'line_scores' in columns or 'diff' in columns:
        print("Note: Old columns (line_scores, diff) still exist but will be ignored")

    conn.close()
    print("\nMigration complete!")

if __name__ == "__main__":
    migrate()
