"""鉴权守卫、点赞/收藏幂等、剧集个性化的接口测试（SQLite 临时库，不依赖外部服务）。"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from peewee import SqliteDatabase

from app.core.config import get_settings
from app.db.database import database_proxy
from app.main import app
from app.models import ALL_MODELS, Drama, DramaEpisode, User
from app.services import auth_service

SECRET = "test-secret-for-auth-guard-0123456789"


@pytest.fixture()
def db(tmp_path: Path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret", SECRET)
    monkeypatch.setattr(settings, "admin_token", "")
    database = SqliteDatabase(tmp_path / "guard_test.db")
    database_proxy.initialize(database)
    database.connect()
    database.create_tables(ALL_MODELS)
    try:
        yield database
    finally:
        database.drop_tables(ALL_MODELS)
        database.close()


@pytest.fixture()
def seed(db):
    alice = User.create(external_user_id="user_alice", nickname="Alice")
    bob = User.create(external_user_id="user_bob", nickname="Bob")
    drama = Drama.create(external_drama_id="drama_t1", title="T1", author_user=alice, total_episodes=1)
    episode = DramaEpisode.create(
        drama=drama, external_video_id="video_t1_01", episode_no=1, play_url="t1/01.mp4"
    )
    return {"alice": alice, "bob": bob, "drama": drama, "episode": episode}


@pytest.fixture()
def client():
    # 不进入 with 上下文，避免 lifespan 初始化默认数据库
    return TestClient(app)


def bearer(user: User) -> dict:
    return {"Authorization": "Bearer " + auth_service._create_backend_token(user)}


def test_user_routes_require_token(client, seed):
    r = client.get("/api/v1/user/user_alice/profile")
    assert r.status_code == 200
    assert r.json()["code"] == 401

    r = client.get("/api/v1/user/user_alice/profile", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.json()["code"] == 401

    expired = jwt.encode(
        {"sub": "user_alice", "exp": int((datetime.now(timezone.utc) - timedelta(seconds=10)).timestamp())},
        SECRET,
        algorithm="HS256",
    )
    r = client.get("/api/v1/user/user_alice/profile", headers={"Authorization": "Bearer " + expired})
    assert r.json()["code"] == 401

    wrong_secret = jwt.encode(
        {"sub": "user_alice", "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())},
        "other-secret",
        algorithm="HS256",
    )
    r = client.get("/api/v1/user/user_alice/profile", headers={"Authorization": "Bearer " + wrong_secret})
    assert r.json()["code"] == 401


def test_user_routes_reject_other_user(client, seed):
    r = client.get("/api/v1/user/user_alice/profile", headers=bearer(seed["bob"]))
    assert r.json()["code"] == 403
    r = client.post(
        "/api/v1/user/user_alice/like",
        json={"video_id": seed["episode"].id, "is_like": True},
        headers=bearer(seed["bob"]),
    )
    assert r.json()["code"] == 403


def test_user_routes_accept_matching_token(client, seed):
    r = client.get("/api/v1/user/user_alice/profile", headers=bearer(seed["alice"]))
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["userId"] == "user_alice"


def test_like_is_idempotent_and_toggle_compatible(client, seed):
    url = "/api/v1/user/user_alice/like"
    h = bearer(seed["alice"])
    vid = seed["episode"].id

    for _ in range(2):
        d = client.post(url, json={"video_id": vid, "is_like": True}, headers=h).json()["data"]
        assert d == {"liked": True, "likeCount": 1}
    for _ in range(2):
        d = client.post(url, json={"video_id": vid, "is_like": False}, headers=h).json()["data"]
        assert d == {"liked": False, "likeCount": 0}
    # 不传 is_like：保持旧 toggle 行为
    d = client.post(url, json={"video_id": vid}, headers=h).json()["data"]
    assert d == {"liked": True, "likeCount": 1}
    d = client.post(url, json={"video_id": vid}, headers=h).json()["data"]
    assert d == {"liked": False, "likeCount": 0}


def test_favorite_is_idempotent_and_toggle_compatible(client, seed):
    url = "/api/v1/user/user_alice/favorite"
    h = bearer(seed["alice"])
    vid = seed["episode"].id

    for _ in range(2):
        d = client.post(url, json={"video_id": vid, "is_favorite": True}, headers=h).json()["data"]
        assert d == {"favorited": True, "followCount": 1}
    d = client.post(url, json={"video_id": vid, "is_favorite": False}, headers=h).json()["data"]
    assert d == {"favorited": False, "followCount": 0}
    d = client.post(url, json={"video_id": vid}, headers=h).json()["data"]
    assert d == {"favorited": True, "followCount": 1}


def test_episodes_use_token_user_when_viewer_absent(client, seed):
    h = bearer(seed["alice"])
    vid = seed["episode"].id
    client.post("/api/v1/user/user_alice/like", json={"video_id": vid, "is_like": True}, headers=h)
    client.post("/api/v1/user/user_alice/favorite", json={"video_id": vid, "is_favorite": True}, headers=h)

    anon = client.get("/api/v1/dramas/drama_t1/episodes").json()["data"]["list"][0]
    assert anon["isLiked"] is False and anon["isFavorite"] is False
    icons = {t["icon"] for t in anon["toolInfo"]}
    assert {"dianzan", "shoucang"} <= icons

    mine = client.get("/api/v1/dramas/drama_t1/episodes", headers=h).json()["data"]["list"][0]
    assert mine["isLiked"] is True and mine["isFavorite"] is True
    icons = {t["icon"] for t in mine["toolInfo"]}
    assert {"dianzan_h", "shoucang_h"} <= icons
    assert mine["subtitleUrl"] == "" and mine["subtitleEnabled"] is False

    # 无效令牌按匿名处理，不报错
    bad = client.get("/api/v1/dramas/drama_t1/episodes", headers={"Authorization": "Bearer bad"}).json()
    assert bad["code"] == 0 and bad["data"]["list"][0]["isLiked"] is False


def test_admin_routes_guard(client, seed, monkeypatch):
    r = client.get("/api/v1/admin/dramas")
    assert r.json()["code"] == 403  # ADMIN_TOKEN 未配置 => 禁用

    monkeypatch.setattr(get_settings(), "admin_token", "adm-123")
    assert client.get("/api/v1/admin/dramas").json()["code"] == 403
    assert client.get("/api/v1/admin/dramas", headers={"X-Admin-Token": "nope"}).json()["code"] == 403
    r = client.get("/api/v1/admin/dramas", headers={"X-Admin-Token": "adm-123"})
    assert r.json()["code"] == 0


def test_progress_requires_matching_token(client, seed):
    url = "/api/v1/user/user_alice/progress"
    body = {"video_id": "video_t1_01", "position": 10}
    assert client.post(url, json=body).json()["code"] == 401
    assert client.post(url, json=body, headers=bearer(seed["bob"])).json()["code"] == 403
    r = client.get("/api/v1/user/user_alice/progress/drama_t1", headers=bearer(seed["bob"]))
    assert r.json()["code"] == 403


def test_progress_keeps_latest_position_and_sticky_finished(client, seed):
    url = "/api/v1/user/user_alice/progress"
    h = bearer(seed["alice"])

    def current():
        data = client.get("/api/v1/user/user_alice/progress/drama_t1", headers=h).json()["data"]["data"]
        assert len(data) == 1
        return data[0]["positionSeconds"], data[0]["isFinished"]

    assert client.post(url, json={"video_id": "video_t1_01", "position": 100}, headers=h).json()["code"] == 0
    assert current() == (100, False)
    client.post(url, json={"video_id": "video_t1_01", "position": 40}, headers=h)
    assert current() == (40, False)  # 续播位置取最新上报值，而非历史最大值
    client.post(url, json={"video_id": "video_t1_01", "position": 90, "is_finished": True}, headers=h)
    assert current() == (90, True)
    client.post(url, json={"video_id": "video_t1_01", "position": 5, "is_finished": False}, headers=h)
    assert current() == (5, True)  # is_finished 置位后不回退
    assert client.post(url, json={"video_id": "missing", "position": 1}, headers=h).json()["code"] == 404
