import sqlite3
from pathlib import Path


DB_PATH = Path(
    r"C:\Users\edato\OneDrive\Masaüstü\paradoks-main"
    r"\crawler-pipeline\backend\vector_db_v2\chroma.sqlite3"
)

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

print("=" * 70)
print("EMBEDDINGS TABLE")
print("=" * 70)

columns = cursor.execute(
    "PRAGMA table_info(embeddings)"
).fetchall()

for column in columns:
    print(column)

print()
print("=" * 70)
print("EMBEDDING_METADATA TABLE")
print("=" * 70)

columns = cursor.execute(
    "PRAGMA table_info(embedding_metadata)"
).fetchall()

for column in columns:
    print(column)

print()
print("=" * 70)
print("SAMPLE EMBEDDINGS")
print("=" * 70)

rows = cursor.execute(
    """
    SELECT *
    FROM embeddings
    LIMIT 5
    """
).fetchall()

for row in rows:
    print(row)

print()
print("=" * 70)
print("SAMPLE METADATA")
print("=" * 70)

rows = cursor.execute(
    """
    SELECT *
    FROM embedding_metadata
    LIMIT 20
    """
).fetchall()

for row in rows:
    print(row)

connection.close()
