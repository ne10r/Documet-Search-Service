import ast
import asyncio
import csv
import os
from datetime import datetime
from pathlib import Path

import asyncpg
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from config import get_pg_dsn

PG_DSN = get_pg_dsn()
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
ES_INDEX = os.getenv("ELASTICSEARCH_INDEX", "documents")
CSV_PATH = os.getenv("CSV_PATH", "data/posts.csv")
BATCH_SIZE = 500


def parse_rubrics(value: str) -> list[str]:
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(parsed, (list, tuple)):
        return [str(item) for item in parsed]
    return [str(parsed)]


def iter_document_batches(path: Path, batch_size: int):
    batch: list[tuple[list[str], str, datetime]] = []
    with path.open(encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue

            text, date_str, rubrics_str = row
            created_date = datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S")
            rubrics = parse_rubrics(rubrics_str)
            batch.append((rubrics, text, created_date))

            if len(batch) >= batch_size:
                yield batch
                batch = []

    if batch:
        yield batch


async def bulk_insert_pg(
    conn: asyncpg.Connection,
    batch: list[tuple[list[str], str, datetime]],
) -> list[asyncpg.Record]:
    await conn.execute("TRUNCATE documents_staging")
    await conn.copy_records_to_table(
        "documents_staging",
        records=batch,
        columns=["rubrics", "text", "created_date"],
    )
    return await conn.fetch(
        """
        INSERT INTO documents (rubrics, text, created_date)
        SELECT rubrics, text, created_date
        FROM documents_staging
        RETURNING id, text
        """
    )


async def bulk_insert_es(es: AsyncElasticsearch, rows: list[asyncpg.Record]) -> None:
    actions = (
        {
            "_index": ES_INDEX,
            "_id": str(row["id"]),
            "_source": {"text": row["text"]},
        }
        for row in rows
    )
    await async_bulk(es, actions)


async def main():
    path = Path(CSV_PATH)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    pool = await asyncpg.create_pool(PG_DSN)
    es = AsyncElasticsearch(ES_URL)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                rubrics TEXT[] NOT NULL,
                text TEXT NOT NULL,
                created_date TIMESTAMP NOT NULL
            )
            """
        )
        await conn.execute("TRUNCATE documents RESTART IDENTITY")

    if await es.indices.exists(index=ES_INDEX):
        await es.indices.delete(index=ES_INDEX)
    await es.indices.create(
        index=ES_INDEX,
        mappings={"properties": {"text": {"type": "text"}}},
    )

    total = 0
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TEMP TABLE documents_staging (
                rubrics TEXT[] NOT NULL,
                text TEXT NOT NULL,
                created_date TIMESTAMP NOT NULL
            ) ON COMMIT PRESERVE ROWS
            """
        )
        for batch in iter_document_batches(path, BATCH_SIZE):
            rows = await bulk_insert_pg(conn, batch)
            await bulk_insert_es(es, rows)
            total += len(rows)

    await es.indices.refresh(index=ES_INDEX)
    await es.close()
    await pool.close()
    print(f"Imported {total} documents")


if __name__ == "__main__":
    asyncio.run(main())
