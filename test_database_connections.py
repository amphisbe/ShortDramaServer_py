from fastapi.routing import APIRoute
import pytest

from app.core.config import Settings
from app.db import dependencies
from app.db.database import build_database
from app.main import app


def test_with_db_connection_uses_connection_context(monkeypatch):
    events = []

    class FakeConnectionContext:
        def __enter__(self):
            events.append("enter")

        def __exit__(self, exc_type, exc_value, traceback):
            events.append("exit")

    class FakeDatabase:
        def connection_context(self):
            return FakeConnectionContext()

    monkeypatch.setattr(dependencies, "initialize_database", lambda: FakeDatabase())

    @dependencies.with_db_connection
    def handler(value):
        events.append("handler")
        return value * 2

    assert handler(3) == 6
    assert events == ["enter", "handler", "exit"]
    assert handler.__peewee_connection_wrapped__ is True


def test_with_db_connection_closes_context_on_exception(monkeypatch):
    events = []

    class FakeConnectionContext:
        def __enter__(self):
            events.append("enter")

        def __exit__(self, exc_type, exc_value, traceback):
            events.append("exit")

    class FakeDatabase:
        def connection_context(self):
            return FakeConnectionContext()

    monkeypatch.setattr(dependencies, "initialize_database", lambda: FakeDatabase())

    @dependencies.with_db_connection
    def handler():
        events.append("handler")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        handler()

    assert events == ["enter", "handler", "exit"]


def test_api_routes_are_wrapped_with_database_connection_context():
    unwrapped_routes = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/api/v1")
        and not getattr(route.endpoint, "__peewee_connection_wrapped__", False)
    ]

    assert unwrapped_routes == []


def test_mysql_pool_timeout_is_configured():
    settings = Settings(
        DB_DRIVER="mysql",
        MYSQL_DATABASE="short_drama_test",
        MYSQL_USER="root",
        MYSQL_PASSWORD="",
        MYSQL_HOST="127.0.0.1",
        MYSQL_PORT=3306,
        MYSQL_CHARSET="utf8mb4",
        MYSQL_MAX_CONNECTIONS=7,
        MYSQL_STALE_TIMEOUT=300,
        MYSQL_POOL_TIMEOUT=3,
    )

    db = build_database(settings)

    assert db._wait_timeout == 3
