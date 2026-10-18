import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from peewee import SqliteDatabase

from app.core.config import get_settings
from app.db.database import database_proxy
from app.main import app
from app.models import ALL_MODELS, Drama, User
from app.services import auth_service


@pytest.fixture()
def tag_env(tmp_path, monkeypatch):
    previous = database_proxy.obj
    db = SqliteDatabase(tmp_path / 'tags.db', pragmas={'foreign_keys': 1})
    database_proxy.initialize(db)
    db.connect()
    db.create_tables(ALL_MODELS)
    monkeypatch.setattr(get_settings(), 'admin_token', 'tags-admin')
    monkeypatch.setattr(get_settings(), 'jwt_secret', 'tag-tests-secret-01234567890123456789')
    user = User.create(external_user_id='tags_user')
    drama = Drama.create(external_drama_id='tags_drama', author_user=user, tags='["旧标签"]')
    try:
        yield TestClient(app), user, drama, db
    finally:
        db.close()
        database_proxy.initialize(previous)


ADMIN = {'X-Admin-Token': 'tags-admin'}


def create_tag(client, code='ROMANCE', translations=None):
    return client.post('/api/v1/admin/tags', headers=ADMIN, json={
        'code': code, 'translations': translations or {'en': 'Romance', 'zh-CN': '爱情'},
        'aliases': {'zh-CN': ['言情']} if code == 'ROMANCE' else {},
    })


def test_dictionary_auth_translation_and_fallback(tag_env):
    client, _, _, _ = tag_env
    assert client.post('/api/v1/admin/tags', json={'code': 'ROMANCE'}).json()['code'] == 403
    assert create_tag(client).json()['code'] == 0
    for locale, name in [('zh-CN', '爱情'), ('vi', 'Romance'), ('en-US', 'Romance')]:
        body = client.get('/api/v1/tags', params={'locale': locale}).json()
        assert body['data'] == [{'code': 'ROMANCE', 'name': name}]
    assert client.get('/api/v1/tags', headers={'Accept-Language': 'zh-CN, en;q=0.8'}).json()['data'][0]['name'] == '爱情'
    assert client.put('/api/v1/admin/tags/ROMANCE', headers=ADMIN, json={'status': 0}).json()['code'] == 0
    assert client.get('/api/v1/tags').json()['data'] == []
    assert client.get('/api/v1/admin/tags', headers=ADMIN).json()['data'][0]['code'] == 'ROMANCE'


def test_tag_validation_and_immutable_codes(tag_env):
    client, _, _, _ = tag_env
    for code in ['爱情', 'romance', 'ROMANCE-DRAMA', 'ROMANCE_']:
        assert create_tag(client, code).json()['code'] != 0
    assert create_tag(client).json()['code'] == 0
    assert create_tag(client).json()['code'] == 409
    assert client.put('/api/v1/admin/tags/ROMANCE', headers=ADMIN, json={'code': 'LOVE'}).status_code == 422
    response = client.post('/api/v1/admin/tags', headers=ADMIN, json={
        'code': 'LOVE', 'translations': {'en': 'Love'}, 'aliases': {'zh-CN': ['言情']},
    })
    assert response.json()['code'] == 409
    assert [t['code'] for t in client.get('/api/v1/tags').json()['data']] == ['ROMANCE']


def test_drama_weights_and_manual_protection(tag_env):
    client, _, drama, _ = tag_env
    create_tag(client)
    create_tag(client, 'URBAN', {'en': 'Urban'})
    url = '/api/v1/admin/dramas/tags_drama/tags'
    result = client.put(url, headers=ADMIN, json={'weights': {'ROMANCE': 7, 'URBAN': 3}}).json()
    assert result['code'] == 0
    assert result['data']['weights'] == {'ROMANCE': 0.7, 'URBAN': 0.3}
    saved = Drama.get_by_id(drama.id)
    assert json.loads(saved.tag_weights) == result['data']['weights']
    assert saved.tag_source == 'manual' and saved.tag_status == 'done'
    assert json.loads(saved.tags) == ['Romance', 'Urban']
    public = client.get('/api/v1/dramas/tags_drama/tags?locale=zh-CN').json()['data']
    assert public == [{'code': 'ROMANCE', 'name': '爱情', 'weight': 0.7}, {'code': 'URBAN', 'name': 'Urban', 'weight': 0.3}]
    assert client.put(url, headers=ADMIN, json={'source': 'auto', 'weights': {'ROMANCE': 1}}).json()['code'] == 409
    assert client.put(url, headers=ADMIN, json={'source': 'auto', 'replace_manual': True, 'weights': {'ROMANCE': 1}}).json()['code'] == 0
    for weights in [{}, {'UNKNOWN': 1}, {'ROMANCE': -1}, {'ROMANCE': 0}, {'ROMANCE': True}]:
        response = client.put(url, headers=ADMIN, json={'weights': weights})
        assert response.status_code == 422 or response.json()['code'] != 0
    client.put('/api/v1/admin/tags/ROMANCE', headers=ADMIN, json={'status': 0})
    assert client.put(url, headers=ADMIN, json={'weights': {'ROMANCE': 1}}).json()['code'] != 0
    assert client.get('/api/v1/dramas/tags_drama/tags').json()['data'] == []


def test_interests_are_private_decayed_and_resettable(tag_env):
    from app.models import UserTagWeight
    client, user, _, _ = tag_env
    create_tag(client)
    other = User.create(external_user_id='tags_other')
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    UserTagWeight.create(user=user, tag_code='ROMANCE', weight=100, weight_updated_at=old)
    UserTagWeight.create(user=other, tag_code='ROMANCE', weight=80, weight_updated_at=old)
    headers = {'Authorization': 'Bearer ' + auth_service._create_backend_token(user)}
    assert client.get('/api/v1/me/interests').json()['code'] == 401
    result = client.get('/api/v1/me/interests?locale=zh-CN', headers=headers).json()['data']
    assert len(result) == 1 and result[0]['name'] == '爱情'
    assert result[0]['weight'] == pytest.approx(95, abs=0.01)
    assert UserTagWeight.get(UserTagWeight.user == user).weight == 100
    assert client.delete('/api/v1/me/interests', headers=headers).json()['code'] == 0
    assert UserTagWeight.select().where(UserTagWeight.user == other).count() == 1
    assert client.get('/api/v1/me/interests', headers=headers).json()['data'] == []


def test_backfill_preview_unknown_and_idempotency(tag_env):
    from app.services.tag_service import backfill_drama_tags
    client, _, drama, _ = tag_env
    create_tag(client)
    Drama.update(tags=json.dumps(['言情', 'Romance'])).where(Drama.id == drama.id).execute()
    assert backfill_drama_tags(apply=False)['convertible'] == 1
    assert Drama.get_by_id(drama.id).tag_status == 'pending'
    assert backfill_drama_tags(apply=True)['updated'] == 1
    assert json.loads(Drama.get_by_id(drama.id).tag_weights) == {'ROMANCE': 1.0}
    assert backfill_drama_tags(apply=True)['updated'] == 0
    Drama.update(tags='["未知标签"]', tag_status='pending', tag_weights='{}', tag_source='').where(Drama.id == drama.id).execute()
    report = backfill_drama_tags(apply=True)
    assert report['updated'] == 0 and report['unresolved'][0]['tags'] == ['未知标签']
    assert Drama.get_by_id(drama.id).tags == '["未知标签"]'


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), 10 ** 309, '1', True])
def test_nonfinite_and_coerced_weights_are_rejected(tag_env, value):
    from app.services.tag_service import TagError, normalize_weights
    client, _, _, _ = tag_env
    create_tag(client)
    with pytest.raises(TagError):
        normalize_weights({'ROMANCE': value})


def test_locale_precedence_code_fallback_and_hidden_content(tag_env):
    from app.models import TagTranslation
    client, _, drama, _ = tag_env
    create_tag(client)
    assert client.get('/api/v1/tags', headers={'Accept-Language': 'en;q=0.3,zh-CN;q=0.9'}).json()['data'][0]['name'] == '爱情'
    assert client.get('/api/v1/tags?locale=en', headers={'Accept-Language': 'zh-CN'}).json()['data'][0]['name'] == 'Romance'
    assert client.get('/api/v1/tags?locale=invalid-language').json()['code'] == 400
    TagTranslation.delete().execute()
    assert client.get('/api/v1/tags?locale=vi').json()['data'] == [{'code': 'ROMANCE', 'name': 'ROMANCE'}]
    Drama.update(status=0).where(Drama.id == drama.id).execute()
    assert client.get('/api/v1/dramas/tags_drama/tags').json()['code'] == 404


def test_backfill_does_not_guess_ambiguous_translations_or_overwrite_manual(tag_env):
    from app.services.tag_service import backfill_drama_tags
    client, _, drama, _ = tag_env
    create_tag(client)
    create_tag(client, 'LOVE', {'en': 'Love', 'zh-CN': '爱情'})
    Drama.update(tags='["爱情"]').where(Drama.id == drama.id).execute()
    assert backfill_drama_tags(apply=True)['updated'] == 0
    assert Drama.get_by_id(drama.id).tag_weights == '{}'
    client.put('/api/v1/admin/dramas/tags_drama/tags', headers=ADMIN, json={'weights': {'ROMANCE': 1}})
    assert backfill_drama_tags(apply=True)['skipped'] == 1
    assert Drama.get_by_id(drama.id).tag_source == 'manual'


def test_disabled_user_and_reset_authentication(tag_env):
    client, user, _, _ = tag_env
    headers = {'Authorization': 'Bearer ' + auth_service._create_backend_token(user)}
    assert client.delete('/api/v1/me/interests').json()['code'] == 401
    User.update(status=0).where(User.id == user.id).execute()
    assert client.get('/api/v1/me/interests', headers=headers).json()['code'] == 401
    assert client.delete('/api/v1/me/interests', headers=headers).json()['code'] == 401


def test_any_english_region_can_supply_default_name(tag_env):
    client, _, _, _ = tag_env
    assert create_tag(client, translations={'en-AU': 'Romance AU'}).json()['code'] == 0
    for locale in ['en', 'vi', 'en-AU']:
        assert client.get('/api/v1/tags', params={'locale': locale}).json()['data'][0]['name'] == 'Romance AU'


def test_backfill_supports_real_legacy_comma_separated_tags(tag_env):
    from app.services.tag_service import backfill_drama_tags
    client, _, drama, _ = tag_env
    create_tag(client)
    create_tag(client, 'URBAN', {'en': 'Urban'})
    Drama.update(tags='Romance, Urban, ROMANCE').where(Drama.id == drama.id).execute()
    assert backfill_drama_tags(apply=False)['convertible'] == 1
    assert backfill_drama_tags(apply=True)['updated'] == 1
    assert json.loads(Drama.get_by_id(drama.id).tag_weights) == {'ROMANCE': 0.5, 'URBAN': 0.5}
    assert Drama.get_by_id(drama.id).tags == 'Romance, Urban, ROMANCE'
