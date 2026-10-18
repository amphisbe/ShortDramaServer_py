from fastapi.testclient import TestClient
from peewee import SqliteDatabase
import pytest

from app.core.config import get_settings
from app.db.database import database_proxy
from app.main import app
from app.models import (ALL_MODELS, Drama, DramaEpisode, DramaEpisodeStat, User,
                        UserDramaFavorite, UserEpisodeLike, UserEpisodeProgress)
from app.services import auth_service


@pytest.fixture()
def feed_env(tmp_path, monkeypatch):
    previous = database_proxy.obj
    db = SqliteDatabase(tmp_path / 'feed.db')
    database_proxy.initialize(db)
    db.connect()
    db.create_tables(ALL_MODELS)
    monkeypatch.setattr(get_settings(), 'jwt_secret', 'feed-tests-secret-01234567890123456789')
    monkeypatch.setattr(get_settings(), 'static_host', 'https://media.example.com/')
    monkeypatch.setattr(get_settings(), 'video_mode', 'demo')
    monkeypatch.setattr(get_settings(), 'video_list', 'https://demo.example.com/wrong.mp4')
    viewer = User.create(external_user_id='feed_viewer')
    author = User.create(external_user_id='feed_author')
    drama = Drama.create(external_drama_id='feed_drama', author_user=author)
    episodes = [DramaEpisode.create(drama=drama, external_video_id=f'feed_{i}', episode_no=i,
                                   play_url=f'episodes/{i}.mp4') for i in range(1, 8)]
    headers = {'Authorization': 'Bearer ' + auth_service._create_backend_token(viewer)}
    try:
        yield TestClient(app), viewer, drama, episodes, headers, db
    finally:
        db.close()
        database_proxy.initialize(previous)


def test_random_feed_requires_login_and_defaults_to_five(feed_env):
    client, _, _, _, headers, _ = feed_env
    assert client.get('/api/v1/for-you').json()['code'] == 401
    result = client.get('/api/v1/for-you', headers=headers).json()
    assert result['code'] == 0
    items = result['data']['list']
    assert len(items) == len({x['videoId'] for x in items}) == 5
    for item in items:
        assert item['dramaId'] == 'feed_drama'
        assert item['playurl'].startswith('https://media.example.com/episodes/')
        assert item['duration'] == 0  # random phase doesn't require measured duration or labels
        assert item['isFavorited'] is False
        assert item['episodeId'] and 'toolInfo' in item
    # A read request must not create statistics rows.
    assert DramaEpisodeStat.select().count() == 0


def test_random_feed_filters_unavailable_content_and_supports_language(feed_env):
    client, _, drama, episodes, headers, _ = feed_env
    DramaEpisode.update(status=0).where(DramaEpisode.id == episodes[0].id).execute()
    DramaEpisode.update(play_url='   ').where(DramaEpisode.id == episodes[1].id).execute()
    for number, blank in [(8, '\t\n'), (9, '\u3000\u00a0')]:
        DramaEpisode.create(drama=drama, external_video_id=f'blank_{number}',
                            episode_no=number, play_url=blank)
    other = Drama.create(external_drama_id='feed_vi', author_user=drama.author_user_id, lang='vi')
    DramaEpisode.create(drama=other, external_video_id='vi_1', episode_no=1,
                        play_url='https://remote.example.com/real.mp4')
    result = client.get('/api/v1/for-you?count=20', headers=headers).json()['data']['list']
    assert {x['videoId'] for x in result} == {e.external_video_id for e in episodes[2:]}
    vi = client.get('/api/v1/for-you?content_lang=vi', headers=headers).json()['data']['list']
    assert len(vi) == 1 and vi[0]['playurl'] == 'https://remote.example.com/real.mp4'
    Drama.update(status=0).where(Drama.id == other.id).execute()
    assert client.get('/api/v1/for-you?content_lang=vi', headers=headers).json()['data']['list'] == []
    assert client.get('/api/v1/for-you?count=0', headers=headers).status_code == 422
    assert client.get('/api/v1/for-you?count=21', headers=headers).status_code == 422


def test_random_feed_uses_current_user_state(feed_env):
    client, viewer, drama, episodes, headers, _ = feed_env
    ep = episodes[0]
    DramaEpisode.update(status=0).where(DramaEpisode.id != ep.id).execute()
    UserEpisodeLike.create(user=viewer, episode=ep)
    UserDramaFavorite.create(user=viewer, drama=drama)
    UserEpisodeProgress.create(user=viewer, episode=ep, position_seconds=12)
    item = client.get('/api/v1/for-you', headers=headers).json()['data']['list'][0]
    assert item['isLiked'] and item['isFavorited'] and item['isFavorite']
    assert item['position'] == 12
    assert item['showLookAllBtn'] is True
    other = User.create(external_user_id='feed_other')
    other_headers = {'Authorization': 'Bearer ' + auth_service._create_backend_token(other)}
    item = client.get('/api/v1/for-you?viewer_user_id=feed_viewer', headers=other_headers).json()['data']['list'][0]
    assert item['isLiked'] is False and item['isFavorited'] is False and item['position'] == 0
    User.update(status=0).where(User.id == other.id).execute()
    assert client.get('/api/v1/for-you', headers=other_headers).json()['code'] == 401
