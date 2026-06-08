from fastapi.testclient import TestClient

from app.db.database import initialize_runtime
from app.main import app


if __name__ == "__main__":
    initialize_runtime(create_schema=True, seed=True)
    client = TestClient(app)

    # 健康检查
    health = client.get("/health")
    assert health.status_code == 200, health.text
    assert health.json()["status"] == "ok"

    # 首页 - 短剧列表
    r = client.get("/api/v1/dramas", params={"category": "推荐", "page": 1, "page_size": 10})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["code"] == 0, data
    assert len(data["data"]["data"]) >= 1, data

    # 首页 - 主推
    r = client.get("/api/v1/dramas/featured")
    assert r.status_code == 200
    assert r.json()["data"] is not None

    # 首页 - 热门
    r = client.get("/api/v1/dramas/hot", params={"count": 4})
    assert r.status_code == 200

    # 首页 - 热搜
    r = client.get("/api/v1/dramas/trending", params={"count": 5})
    assert r.status_code == 200

    # 首页 - 猜你喜欢
    r = client.get("/api/v1/dramas/recommended", params={"exclude_id": "drama_001"})
    assert r.status_code == 200

    # 详情页
    r = client.get("/api/v1/dramas/drama_001")
    assert r.status_code == 200
    assert r.json()["data"]["title"] == "妈妈不要哭泣"

    # 详情页 - 同类推荐
    r = client.get("/api/v1/dramas/drama_001/related")
    assert r.status_code == 200

    # 播放页 - 剧集列表
    r = client.get("/api/v1/dramas/drama_001/episodes")
    assert r.status_code == 200
    ep_data = r.json()
    assert ep_data["code"] == 0
    assert len(ep_data["data"]["list"]) >= 1

    # 辅助 - 反查 short ID
    r = client.get("/api/v1/dramas/by-user/user_mama")
    assert r.status_code == 200
    assert r.json()["data"]["dramaId"] == "drama_001"

    # 原有播放列表接口
    raw = client.get(
        "/api/v1/video/play-list/raw",
        params={"page": 1, "page_size": 10},
    )
    assert raw.status_code == 200

    wrapped = client.get("/api/v1/video/play-list", params={"page": 1, "page_size": 2})
    assert wrapped.status_code == 200
    assert wrapped.json()["code"] == 0

    # 管理端
    admin = client.get("/api/v1/admin/dramas")
    assert admin.status_code == 200
    assert admin.json()["code"] == 0

    print("Smoke tests passed.")
