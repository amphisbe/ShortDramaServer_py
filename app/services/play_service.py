from __future__ import annotations

import json
from typing import Any

from peewee import DoesNotExist

from app.models import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    User,
    UserEpisodeLike,
    UserEpisodeProgress,
    UserFollow,
)


def _exists(query) -> bool:
    return query.exists()


def get_viewer_by_external_id(external_user_id: str | None) -> User | None:
    if not external_user_id:
        return None
    try:
        return User.get(User.external_user_id == external_user_id)
    except DoesNotExist:
        return None


def _build_default_tool_info(like_count: int) -> list[dict[str, Any]]:
    return [
        {"icon": "shoucang", "text": "追剧"},
        {"icon": "dianzan", "num": like_count, "text": "点赞"},
        {"icon": "share", "text": "分享"},
    ]


def _load_tool_info(raw_json: str | None, like_count: int) -> list[dict[str, Any]]:
    if not raw_json:
        return _build_default_tool_info(like_count)

    try:
        value = json.loads(raw_json)
    except json.JSONDecodeError:
        return _build_default_tool_info(like_count)

    if isinstance(value, list):
        return value
    return _build_default_tool_info(like_count)


def build_play_item(episode: DramaEpisode, viewer: User | None = None) -> dict[str, Any]:
    drama: Drama = episode.drama
    author: User = drama.author_user

    try:
        stat = DramaEpisodeStat.get(DramaEpisodeStat.episode == episode)
    except DoesNotExist:
        stat = DramaEpisodeStat.create(episode=episode)

    is_follow = False
    is_liked = False
    position = 0

    if viewer:
        is_follow = _exists(
            UserFollow.select().where(
                (UserFollow.follower_user == viewer) & (UserFollow.followed_user == author)
            )
        )
        is_liked = _exists(
            UserEpisodeLike.select().where(
                (UserEpisodeLike.user == viewer) & (UserEpisodeLike.episode == episode)
            )
        )
        try:
            progress = UserEpisodeProgress.get(
                (UserEpisodeProgress.user == viewer) & (UserEpisodeProgress.episode == episode)
            )
            position = progress.position_seconds
        except DoesNotExist:
            position = 0

    vip_text = "vip免费" if drama.vip_free else "付费观看"
    look_all_btn_text = episode.look_all_btn_text or f"观看完整短剧 · 全{drama.total_episodes}集"
    bottom_area_btn_text = episode.bottom_area_btn_text or f"选集 · 全{drama.total_episodes}集 · {vip_text}"

    return {
        "userId": author.external_user_id,
        "avatar": author.avatar_url,
        "nickname": episode.display_nickname or author.nickname,
        "isfollow": is_follow,
        "videoId": episode.external_video_id,
        "playurl": episode.play_url,
        "poster": episode.poster_url,
        "vduser": drama.display_author_name or author.nickname,
        "vdtitle": episode.title,
        "loop": episode.loop,
        "duration": episode.duration_seconds,
        "playIng": episode.play_ing,
        "muted": episode.muted,
        "likeSum": stat.like_count,
        "isLiked": is_liked,
        "commemtSum": stat.comment_count,
        "shareSum": stat.share_count,
        "isPlaying": episode.is_playing,
        "position": position,
        "showTitleArrow": episode.show_title_arrow,
        "showLookAllBtn": episode.show_look_all_btn,
        "lookAllBtnText": look_all_btn_text,
        "total": drama.total_episodes,
        "showBottomArea": episode.show_bottom_area,
        "bottomAreaBtnText": bottom_area_btn_text,
        "toolInfo": _load_tool_info(episode.tool_info_json, stat.like_count),
    }


def list_play_items(
    viewer_external_user_id: str | None = None,
    drama_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], bool]:
    viewer = get_viewer_by_external_id(viewer_external_user_id)

    query = (
        DramaEpisode.select(DramaEpisode, Drama, User)
        .join(Drama)
        .join(User, on=(Drama.author_user == User.id))
        .where((DramaEpisode.status == 1) & (Drama.status == 1))
        .order_by(DramaEpisode.sort_order.asc(), DramaEpisode.episode_no.asc())
    )

    if drama_id is not None:
        query = query.where(DramaEpisode.drama == drama_id)

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    total = query.count()
    episodes = list(query.paginate(page, page_size))
    has_more = page * page_size < total

    return [build_play_item(episode, viewer) for episode in episodes], has_more


def list_dramas() -> list[dict[str, Any]]:
    rows = Drama.select(Drama, User).join(User, on=(Drama.author_user == User.id)).order_by(Drama.id.desc())
    return [
        {
            "id": drama.id,
            "externalDramaId": drama.external_drama_id,
            "title": drama.title,
            "displayAuthorName": drama.display_author_name,
            "authorUserId": drama.author_user.external_user_id,
            "totalEpisodes": drama.total_episodes,
            "coverUrl": drama.cover_url,
            "vipFree": drama.vip_free,
            "status": drama.status,
        }
        for drama in rows
    ]
