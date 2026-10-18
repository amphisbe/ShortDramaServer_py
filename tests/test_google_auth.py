"""/auth/google：资料字段写入、空 claim 不覆盖、Google 库异常映射（不访问外网，monkeypatch 校验函数）。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from google.auth import exceptions as google_exceptions
from peewee import SqliteDatabase

from app.core.config import get_settings
from app.db.database import database_proxy
from app.main import app
from app.models import ALL_MODELS, User
from app.services import auth_service

CLIENT_ID = "test-web-client.apps.googleusercontent.com"


@pytest.fixture()
def db(tmp_path: Path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-google-auth-0123456789")
    monkeypatch.setattr(settings, "google_web_client_id", CLIENT_ID)
    database = SqliteDatabase(tmp_path / "google_auth_test.db")
    database_proxy.initialize(database)
    database.connect()
    database.create_tables(ALL_MODELS)
    try:
        yield database
    finally:
        database.drop_tables(ALL_MODELS)
        database.close()


@pytest.fixture()
def client():
    return TestClient(app)


def fake_verifier(claims=None, exc=None):
    def _verify(token, request, audience, clock_skew_in_seconds=0):
        assert audience == CLIENT_ID
        assert clock_skew_in_seconds == auth_service.GOOGLE_CLOCK_SKEW_SECONDS
        if exc is not None:
            raise exc
        return dict(claims)

    return _verify


BASE_CLAIMS = {
    "iss": "https://accounts.google.com",
    "sub": "109876543210987654321",
    "email": "alice@example.com",
    "email_verified": True,
    "name": "Alice G",
    "picture": "https://lh3.googleusercontent.com/a/alice",
}


def test_profile_fields_from_claims(client, db, monkeypatch):
    monkeypatch.setattr(auth_service.google_id_token, "verify_oauth2_token", fake_verifier(BASE_CLAIMS))
    body = client.post("/api/v1/auth/google", json={"id_token": "x"}).json()
    assert body["code"] == 0
    user = body["data"]["user"]
    assert user["nickname"] == "Alice G"
    assert user["avatarUrl"] == "https://lh3.googleusercontent.com/a/alice"
    assert user["email"] == "alice@example.com"
    assert user["emailVerified"] is True
    assert user["userId"].startswith("user_") and len(user["userId"]) <= 24


def test_empty_claims_do_not_overwrite(client, db, monkeypatch):
    monkeypatch.setattr(auth_service.google_id_token, "verify_oauth2_token", fake_verifier(BASE_CLAIMS))
    client.post("/api/v1/auth/google", json={"id_token": "x"})
    sparse = {"iss": "accounts.google.com", "sub": BASE_CLAIMS["sub"]}
    monkeypatch.setattr(auth_service.google_id_token, "verify_oauth2_token", fake_verifier(sparse))
    user = client.post("/api/v1/auth/google", json={"id_token": "x"}).json()["data"]["user"]
    assert user["nickname"] == "Alice G"
    assert user["avatarUrl"] == "https://lh3.googleusercontent.com/a/alice"
    assert user["email"] == "alice@example.com"
    assert User.select().count() == 1


def test_wrong_issuer_maps_to_401(client, db, monkeypatch):
    monkeypatch.setattr(
        auth_service.google_id_token,
        "verify_oauth2_token",
        fake_verifier(exc=google_exceptions.GoogleAuthError("Wrong issuer")),
    )
    body = client.post("/api/v1/auth/google", json={"id_token": "x"}).json()
    assert body["code"] == 401


def test_cert_fetch_failure_maps_to_500(client, db, monkeypatch):
    monkeypatch.setattr(
        auth_service.google_id_token,
        "verify_oauth2_token",
        fake_verifier(exc=google_exceptions.TransportError("no network")),
    )
    body = client.post("/api/v1/auth/google", json={"id_token": "x"}).json()
    assert body["code"] == 500
