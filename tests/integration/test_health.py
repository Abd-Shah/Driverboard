from collections.abc import Iterator

from fastapi.testclient import TestClient

from driver_leaderboard.database import get_session
from driver_leaderboard.main import app


class FakeSession:
    def execute(self, statement: object) -> None:
        assert str(statement) == "SELECT 1"


def fake_session() -> Iterator[FakeSession]:
    yield FakeSession()


def test_health_reports_application_and_database_status() -> None:
    app.dependency_overrides[get_session] = fake_session
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}
