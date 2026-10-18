from pathlib import Path

from fastapi.testclient import TestClient
from peewee import SqliteDatabase
import pytest

from app.db.database import database_proxy
from app.main import app
from app.models import ALL_MODELS, User
from app.services import auth_service


@pytest.fixture()
def auth_db(tmp_path: Path):
    db = SqliteDatabase(tmp_path / "auth_test.db")
    database_proxy.initialize(db)
    db.connect()
    db.create_tables(ALL_MODELS)
    try:
        yield db
    finally:
        db.drop_tables(ALL_MODELS)
        db.close()


def test_google_auth_creates_user_and_returns_backend_token(monkeypatch, auth_db):
    def fake_verify(id_token: str) -> dict:
        assert id_token == "valid-google-token"
        return {
            "sub": "google-sub-001",
            "email": "alice@example.com",
            "email_verified": True,
            "name": "Alice",
            "picture": "https://example.com/alice.png",
        }

    monkeypatch.setattr(auth_service, "verify_google_id_token", fake_verify)
    monkeypatch.setattr(auth_service.settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(auth_service.settings, "google_web_client_id", "test-client-id")

    client = TestClient(app)
    response = client.post("/api/v1/auth/google", json={"id_token": "valid-google-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["message"] == "success"
    assert body["data"]["token"]
    assert body["data"]["user"] == {
        "userId": "user_google_sub_001",
        "nickname": "Alice",
        "avatarUrl": "https://example.com/alice.png",
        "email": "alice@example.com",
        "emailVerified": True,
        "isVip": False,
        "watchedCount": 0,
        "favoriteCount": 0,
        "downloadCount": 0,
    }

    user = User.get(User.google_sub == "google-sub-001")
    assert user.external_user_id == "user_google_sub_001"
    assert user.email == "alice@example.com"
    assert user.nickname == "Alice"
    assert user.avatar_url == "https://example.com/alice.png"


def test_google_auth_rejects_invalid_token(monkeypatch, auth_db):
    def fake_verify(id_token: str) -> dict:
        raise auth_service.InvalidGoogleTokenError("invalid google token")

    monkeypatch.setattr(auth_service, "verify_google_id_token", fake_verify)

    client = TestClient(app)
    response = client.post("/api/v1/auth/google", json={"id_token": "bad-token"})

    assert response.status_code == 200
    assert response.json() == {
        "code": 401,
        "message": "invalid google token",
        "data": None,
    }
