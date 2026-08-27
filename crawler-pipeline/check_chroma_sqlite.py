import sqlite3
from pathlib import Path


db_path = Path(
    r"C:\Users\edato\OneDrive\Masaüstü\paradoks-main"
    r"\crawler-pipeline\backend\vector_db_v2\chroma.sqlite3"
)

print("DB:", db_path)
print("VAR MI:", db_path.exists())

connection = sqlite3.connect(db_path)
cursor = connection.cursor()

print()
print("=" * 70)
print("SQLITE INTEGRITY")
print("=" * 70)

integrity = cursor.execute(
    "PRAGMA integrity_check"
).fetchone()

print("INTEGRITY:", integrity[0])

print()
print("=" * 70)
print("TABLES")
print("=" * 70)

tables = cursor.execute(
    """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
    """
).fetchall()

table_names = [
    row[0]
    for row in tables
]

for table_name in table_names:
    print(table_name)

print()
print("=" * 70)
print("KRITIK TABLE COUNTS")
print("=" * 70)

critical_tables = [
    "embeddings",
    "embedding_metadata",
    "embeddings_queue",
]

for table_name in critical_tables:
    if table_name not in table_names:
        print(
            table_name,
            "-> YOK",
        )
        continue

    count = cursor.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()[0]

    print(
        table_name,
        "->",
        count,
    )

connection.close()