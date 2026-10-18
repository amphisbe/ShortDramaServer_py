"""Opt in: TAG_TEST_MYSQL=1 python -m pytest tests/test_tags_mysql.py -q.

Creates and drops ONLY a UUID-named scratch database using configured MySQL credentials.
"""

import os
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.database import build_database, database_proxy
from app.db.tag_migration import ensure_tag_schema, seed_tag_catalog
from app.main import app
from app.models import ALL_MODELS, Drama, Tag, User, UserTagWeight
from app.services import auth_service, tag_service


@pytest.mark.skipif(os.environ.get('TAG_TEST_MYSQL') != '1', reason='explicit MySQL scratch DB opt-in required')
def test_mysql_schema_and_tag_flow(monkeypatch):
    settings = get_settings()
    if settings.db_driver != 'mysql':
        pytest.skip('MySQL configuration required')
    schema = 'codex_tag_test_' + uuid.uuid4().hex
    assert re.fullmatch(r'codex_tag_test_[0-9a-f]{32}', schema)
    admin_db = build_database(settings)
    scratch = build_database(settings.model_copy(update={'mysql_database': schema}))
    previous = database_proxy.obj
    created = False
    try:
        admin_db.connect()
        admin_db.execute_sql(f'CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        created = True
        database_proxy.initialize(scratch)
        scratch.connect()
        # Production's legacy users.id is INT; new tables must support that shape.
        scratch.execute_sql('CREATE TABLE users (id INT PRIMARY KEY)')
        ensure_tag_schema()
        assert scratch.table_exists('user_tag_weights')
        from app.models.tag import TAG_MODELS
        scratch.drop_tables(TAG_MODELS)
        scratch.execute_sql('DROP TABLE users')
        # Build real models, then emulate an old drama schema missing our four fields.
        scratch.create_tables(ALL_MODELS)
        user = User.create(external_user_id='mysql_tags_user')
        drama = Drama.create(external_drama_id='mysql_tags_drama', author_user=user, tags='["言情"]')
        for name in ('tag_weights', 'tag_status', 'tag_source', 'tag_version'):
            scratch.execute_sql(f'ALTER TABLE dramas DROP COLUMN `{name}`')
        ensure_tag_schema()
        ensure_tag_schema()
        assert Drama.get_by_id(drama.id).tag_status == 'pending'
        seed_tag_catalog()
        seed_tag_catalog()
        assert Tag.select().count() == 10
        assert tag_service.backfill_drama_tags(apply=False)['convertible'] == 1
        assert tag_service.backfill_drama_tags(apply=True)['updated'] == 1
        assert tag_service.backfill_drama_tags(apply=True)['updated'] == 0
        monkeypatch.setattr(settings, 'admin_token', 'mysql-tags-admin')
        monkeypatch.setattr(settings, 'jwt_secret', 'mysql-tags-secret-01234567890123456789')
        client = TestClient(app)
        assert client.get('/api/v1/tags?locale=zh-CN').json()['code'] == 0
        response = client.put('/api/v1/admin/dramas/mysql_tags_drama/tags',
                              headers={'X-Admin-Token': 'mysql-tags-admin'},
                              json={'weights': {'ROMANCE': 7, 'URBAN': 3}}).json()
        assert response['code'] == 0
        assert response['data']['weights'] == {'ROMANCE': 0.7, 'URBAN': 0.3}
        UserTagWeight.create(user=user, tag_code='ROMANCE', weight=100)
        bearer = {'Authorization': 'Bearer ' + auth_service._create_backend_token(user)}
        result = client.get('/api/v1/me/interests?locale=vi', headers=bearer).json()
        assert result['code'] == 0 and result['data'][0]['name'] == 'Tình cảm'
        assert client.delete('/api/v1/me/interests', headers=bearer).json()['data']['deleted'] == 1
    finally:
        if not scratch.is_closed():
            scratch.close()
        database_proxy.initialize(previous)
        if created:
            # schema is generated above and validated; never accept an external target.
            admin_db.execute_sql(f'DROP DATABASE `{schema}`')
        if not admin_db.is_closed():
            admin_db.close()
