import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture(scope="function")
async def client():
    """Fixture that creates a test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
