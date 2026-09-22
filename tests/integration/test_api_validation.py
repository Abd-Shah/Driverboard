from fastapi.testclient import TestClient

from driver_leaderboard.main import app


def test_review_write_requires_identity_and_idempotency_headers() -> None:
    response = TestClient(app).put(
        "/trips/00000000-0000-0000-0000-000000000001/review", json={"rating": 5}
    )
    assert response.status_code == 422


def test_rating_outside_domain_is_rejected_before_database_access() -> None:
    response = TestClient(app).put(
        "/trips/00000000-0000-0000-0000-000000000001/review",
        headers={
            "Idempotency-Key": "validation-test",
            "X-Rider-ID": "00000000-0000-0000-0000-000000000002",
        },
        json={"rating": 6},
    )
    assert response.status_code == 422
