from __future__ import annotations

import os
from contextlib import asynccontextmanager

import asyncpg
from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from config import get_pg_dsn

PG_DSN = get_pg_dsn()
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
ES_INDEX = os.getenv("ELASTICSEARCH_INDEX", "documents")

pg_pool: asyncpg.Pool | None = None
es: AsyncElasticsearch | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global pg_pool, es

    pg_pool = await asyncpg.create_pool(PG_DSN)
    async with pg_pool.acquire() as conn:
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

    es = AsyncElasticsearch(ES_URL)
    if not await es.indices.exists(index=ES_INDEX):
        await es.indices.create(
            index=ES_INDEX,
            mappings={"properties": {"text": {"type": "text"}}},
        )

    yield

    await es.close()
    await pg_pool.close()


app = FastAPI(title="Document Search Service", version="1.0.0", lifespan=lifespan)


class DeleteBody(BaseModel):
    id: int


@app.get("/posts/search")
async def search(text: str = Query(..., min_length=1)):
    result = await es.search(
        index=ES_INDEX,
        query={"match": {"text": text}},
        _source=False,
    )
    ids = [int(hit["_id"]) for hit in result["hits"]["hits"]]
    if not ids:
        return []

    rows = await pg_pool.fetch(
        """
        SELECT id, rubrics, text, created_date
        FROM documents
        WHERE id = ANY($1::int[])
        ORDER BY created_date DESC
        LIMIT 20
        """,
        ids,
    )
    return [dict(row) for row in rows]


@app.delete("/posts/delete", status_code=204)
async def delete(body: DeleteBody):
    result = await pg_pool.execute("DELETE FROM documents WHERE id = $1", body.id)
    if not result.endswith("1"):
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        await es.delete(index=ES_INDEX, id=str(body.id), refresh=True)
    except NotFoundError:
        pass


@app.get("/health")
async def health():
    return {"status": "ok"}
