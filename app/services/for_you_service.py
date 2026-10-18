"""Initial For You feed: independent random samples of playable episodes."""

from peewee import MySQLDatabase, fn

from app.core.config import get_settings
from app.core.security import ApiAuthError
from app.db.database import initialize_database
from app.models import (Drama, DramaEpisode, DramaEpisodeStat, User, UserDramaFavorite,
                        UserEpisodeLike, UserEpisodeProgress, UserFollow)
from app.services.drama_service import _build_episode_item


def _nonblank_url_expression(mysql: bool):
    # SQL TRIM alone does not remove tabs, line breaks or Unicode whitespace.
    # These are the characters stripped by Python str.strip() below.
    whitespace = (' \t\n\r\v\f\x1c\x1d\x1e\x1f\x85\xa0\u1680'
                  '\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a'
                  '\u2028\u2029\u202f\u205f\u3000')
    if mysql:
        return DramaEpisode.play_url.regexp('[^' + whitespace + ']')
    return fn.TRIM(DramaEpisode.play_url, whitespace) != ''


def _actual_play_url(raw: str) -> str:
    url = raw.strip()
    if url.startswith(('https://', 'http://', '//')):
        return url
    return get_settings().static_host.rstrip('/') + '/' + url.lstrip('/')


def random_feed(user_id: str, count: int = 5, content_lang: str = 'en') -> dict:
    viewer = User.get_or_none((User.external_user_id == user_id) & (User.status == 1))
    if viewer is None:
        raise ApiAuthError(401, '用户不存在或已停用')
    db = initialize_database()
    random_order = fn.RAND() if isinstance(db, MySQLDatabase) else fn.Random()
    episodes = list(
        DramaEpisode.select(DramaEpisode, Drama).join(Drama).where(
            (DramaEpisode.status == 1) & (Drama.status == 1)
            & (Drama.lang == content_lang)
            & _nonblank_url_expression(isinstance(db, MySQLDatabase))
            & Drama.external_drama_id.is_null(False)
            & (Drama.external_drama_id != '')
        ).order_by(random_order).limit(min(max(count, 1), 20))
    )
    if not episodes:
        return {'list': []}

    episode_ids = [e.id for e in episodes]
    drama_ids = {e.drama_id for e in episodes}
    author_ids = {e.drama.author_user_id for e in episodes}
    stats = {s.episode_id: s for s in DramaEpisodeStat.select().where(DramaEpisodeStat.episode.in_(episode_ids))}
    liked = {r.episode_id for r in UserEpisodeLike.select().where(
        (UserEpisodeLike.user == viewer) & UserEpisodeLike.episode.in_(episode_ids))}
    favorites = {r.drama_id for r in UserDramaFavorite.select().where(
        (UserDramaFavorite.user == viewer) & UserDramaFavorite.drama.in_(list(drama_ids)))}
    progress = {r.episode_id: r.position_seconds for r in UserEpisodeProgress.select().where(
        (UserEpisodeProgress.user == viewer) & UserEpisodeProgress.episode.in_(episode_ids))}
    following = {r.followed_user_id for r in UserFollow.select().where(
        (UserFollow.follower_user == viewer) & UserFollow.followed_user.in_(list(author_ids)))}

    items = []
    for episode in episodes:
        drama = episode.drama
        # An unsaved default avoids writes from the shared builder on missing stats.
        stat = stats.get(episode.id) or DramaEpisodeStat(episode=episode)
        item = _build_episode_item(
            episode, drama, None, stat, episode.id in liked,
            drama.author_user_id in following, progress.get(episode.id, 0), drama.id in favorites,
        )
        item.update({
            'dramaId': drama.external_drama_id,
            'title': drama.title,
            'episodeNo': episode.episode_no,
            'playurl': _actual_play_url(episode.play_url),
            'isFavorited': drama.id in favorites,
            'showLookAllBtn': episode.show_look_all_btn,
        })
        items.append(item)
    return {'list': items}
