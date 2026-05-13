from pathlib import Path
import sys

from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine


FCN_V4_COLUMNS = {
    "issuer": "VARCHAR",
    "tenor_months": "INTEGER",
    "issue_date": "DATE",
    "maturity_date": "DATE",
    "settlement_currency": "VARCHAR",
    "coupon_frequency": "VARCHAR",
    "next_observation_date": "DATE",
    "next_coupon_date": "DATE",
    "observation_dates_json": "TEXT",
    "coupon_dates_json": "TEXT",
}


def migrate() -> None:
    dialect = engine.dialect.name
    print(f"IXAI FCN v4 migration starting. dialect={dialect}")

    if dialect != "postgresql":
        print("Not a PostgreSQL connection. Skipping FCN v4 PostgreSQL migration.")
        return

    with engine.begin() as connection:
        inspector = inspect(connection)

        if not inspector.has_table("fcn_positions"):
            raise RuntimeError("Table fcn_positions does not exist.")

        existing_columns = {
            str(column["name"])
            for column in inspector.get_columns("fcn_positions")
        }
        print(f"Existing fcn_positions columns: {len(existing_columns)}")

        added = 0
        skipped = 0

        for column_name, column_type in FCN_V4_COLUMNS.items():
            if column_name in existing_columns:
                print(f"skip existing column: {column_name}")
                skipped += 1
                continue

            print(f"add column: {column_name} {column_type}")
            connection.execute(
                text(f"ALTER TABLE fcn_positions ADD COLUMN {column_name} {column_type}")
            )
            added += 1

    print(f"IXAI FCN v4 migration completed. added={added}, skipped={skipped}")


if __name__ == "__main__":
    migrate()
