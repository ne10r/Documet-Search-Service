import httpx
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health(base_url: str):
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_returns_documents_ordered_by_created_date(base_url: str):
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        response = await client.get("/posts/search", params={"text": "документ"})

    assert response.status_code == 200
    documents = response.json()
    assert isinstance(documents, list)
    assert len(documents) <= 20

    for document in documents:
        assert {"id", "rubrics", "text", "created_date"} <= document.keys()

    dates = [document["created_date"] for document in documents]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_empty_result(base_url: str):
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        response = await client.get(
            "/posts/search",
            params={"text": "absolutely_unique_query_xyz_12345"},
        )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_document(base_url: str):
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        search_response = await client.get("/posts/search", params={"text": "тест"})
        documents = search_response.json()
        assert documents

        document_id = documents[0]["id"]
        delete_response = await client.request(
            "DELETE",
            "/posts/delete",
            json={"id": document_id},
        )
        assert delete_response.status_code == 204

        search_after_delete = await client.get("/posts/search", params={"text": "тест"})
        remaining_ids = {item["id"] for item in search_after_delete.json()}
        assert document_id not in remaining_ids

        second_delete = await client.request(
            "DELETE",
            "/posts/delete",
            json={"id": document_id},
        )
        assert second_delete.status_code == 404
