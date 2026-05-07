from fastapi.testclient import TestClient

from app.db.database import initialize_runtime
from app.main import app


if __name__ == "__main__":
    initialize_runtime(create_schema=True, seed=True)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200, health.text
    assert health.json()["status"] == "ok"

    raw = client.get(
        "/api/v1/video/play-list/raw",
        params={"viewer_user_id": "666dd802f366f40a8b9a4aa1", "page": 1, "page_size": 10},
    )
    assert raw.status_code == 200, raw.text
    raw_data = raw.json()
    assert isinstance(raw_data, list), raw_data
    assert len(raw_data) >= 1, raw_data
    assert {"userId", "avatar", "nickname", "videoId", "playurl", "poster", "vdtitle"}.issubset(raw_data[0].keys())

    wrapped = client.get("/api/v1/video/play-list", params={"page": 1, "page_size": 2})
    assert wrapped.status_code == 200, wrapped.text
    wrapped_data = wrapped.json()
    assert wrapped_data["code"] == 0, wrapped_data
    assert "list" in wrapped_data["data"], wrapped_data

    admin = client.get("/api/v1/admin/dramas")
    assert admin.status_code == 200, admin.text
    assert admin.json()["code"] == 0

    print("Smoke tests passed.")
