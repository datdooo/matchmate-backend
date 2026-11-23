"""Import the five MatchMate tables into an empty, migrated PostgreSQL database."""

import argparse
import json
import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Base
from app.db.session import DATABASE_URL, create_db_engine

_BATCH_SIZE = 500
_MAX_ID = 2**63 - 1


def import_sqlite(source: Path, target: Engine) -> dict[str, int]:
    if not source.is_file():
        raise ValueError("SQLite source file does not exist")
    if target.dialect.name != "postgresql":
        raise ValueError("The import target must be PostgreSQL")

    source_uri = f"{source.resolve().as_uri()}?mode=ro"
    source_engine = create_engine(
        "sqlite://", creator=lambda: sqlite3.connect(source_uri, uri=True)
    )
    tables = Base.metadata.sorted_tables
    counts = {}
    try:
        with source_engine.connect() as origin, target.begin() as destination:
            origin.exec_driver_sql("BEGIN")
            integrity = origin.exec_driver_sql("PRAGMA integrity_check")
            if (
                integrity.scalars().all() != ["ok"]
                or origin.exec_driver_sql("PRAGMA foreign_key_check").first() is not None
            ):
                raise ValueError("SQLite source failed integrity or foreign-key checks")

            # These identifiers come only from the application's static table definitions.
            table_names = ", ".join(table.name for table in tables)
            destination.exec_driver_sql(f"LOCK TABLE {table_names} IN ACCESS EXCLUSIVE MODE")
            for table in tables:
                if destination.scalar(select(table.c.id).limit(1)) is not None:
                    raise ValueError(f"PostgreSQL target has existing rows in {table.name}")

            for table in tables:
                rows = origin.execute(select(table).order_by(table.c.id)).mappings()
                count, highest_id = 0, 0
                for rows_batch in rows.partitions(_BATCH_SIZE):
                    batch = [dict(row) for row in rows_batch]
                    destination.execute(table.insert(), batch)
                    ids = [row["id"] for row in batch]
                    imported = destination.execute(
                        select(table).where(table.c.id.in_(ids)).order_by(table.c.id)
                    ).mappings()
                    if [dict(row) for row in imported] != batch:
                        raise ValueError(f"Imported rows differ from SQLite in {table.name}")
                    count += len(batch)
                    highest_id = max(highest_id, ids[-1])

                if count:
                    if highest_id == _MAX_ID:
                        raise ValueError(f"No automatic IDs remain after importing {table.name}")
                    # ALTER ... RESTART is transactional, unlike setval().
                    destination.exec_driver_sql(
                        f"ALTER TABLE {table.name} ALTER COLUMN id RESTART WITH {highest_id + 1}"
                    )
                counts[table.name] = count
    finally:
        source_engine.dispose()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Path to the SQLite source file")
    args = parser.parse_args()

    engine = None
    try:
        engine = create_db_engine(DATABASE_URL)
        counts = import_sqlite(args.source, engine)
    except ValueError as error:
        parser.exit(1, f"Import failed: {error}\n")
    except (SQLAlchemyError, sqlite3.Error):
        # SQL/driver exceptions could include user data or connection credentials.
        parser.exit(1, "Import failed. Check connectivity, target schema and source integrity.\n")
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
